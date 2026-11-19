"""Stream the ClinVar variant_summary release to disk. Does not parse it."""

from __future__ import annotations

import gzip
import logging
import time
from pathlib import Path

import requests

from .errors import ClinVarDownloadError

VARIANT_SUMMARY_URL = (
    "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"
)
USER_AGENT = "GENOMIQ/1.0 (clinvar-ingest)"
# Small enough that a stalled socket hits the read timeout instead of blocking
# inside one multi-megabyte read.
_CHUNK_BYTES = 256 * 1024
_PROGRESS_BYTES = 10 * 1024 * 1024
_CONNECT_TIMEOUT = 30.0
_READ_TIMEOUT = 60.0
_MAX_BACKOFF_SECONDS = 30.0
_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}

logger = logging.getLogger("clinvar_ingest.download")


class _Retry(Exception):
    """Attempt failed and may be repeated. The ``.part`` file is kept when reusable."""


def _ensure_logger() -> None:
    """Show progress on a CLI run without replacing a handler a test already installed."""
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _part_path(dest: Path) -> Path:
    return dest.with_suffix(dest.suffix + ".part")


def _part_size(part: Path) -> int:
    if not part.exists():
        return 0
    return part.stat().st_size


def _drop_empty(part: Path) -> None:
    if part.exists() and part.stat().st_size == 0:
        part.unlink()


def _delay(attempt: int, backoff: float) -> float:
    if backoff <= 0:
        return 0.0
    return min(_MAX_BACKOFF_SECONDS, backoff * (2 ** attempt))


def _timeout_pair(timeout: float | tuple[float, float]) -> tuple[float, float]:
    """``(connect, read)`` seconds. A single number is the read timeout."""
    if isinstance(timeout, tuple):
        connect, read = timeout
        return float(connect), float(read)
    read = float(timeout)
    return min(_CONNECT_TIMEOUT, read), read


def _header(response, name: str) -> str | None:
    headers = getattr(response, "headers", None)
    if headers is None or not hasattr(headers, "get"):
        return None
    value = headers.get(name)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _expected_size(response, status: int, offset: int) -> int | None:
    """Total object size from Content-Range or Content-Length, when the server sends one."""
    if status == 206:
        content_range = _header(response, "Content-Range")
        if content_range and "/" in content_range:
            total = content_range.rsplit("/", 1)[-1].strip()
            if total.isdigit():
                return int(total)
        length = _header(response, "Content-Length")
        if length and length.isdigit():
            return offset + int(length)
        return None
    length = _header(response, "Content-Length")
    if length and length.isdigit():
        return int(length)
    return None


def _log_progress(done: int, total: int | None) -> None:
    _ensure_logger()
    done_mb = done / (1024 * 1024)
    if total is None:
        logger.info("ClinVar download: %.1f MB", done_mb)
        return
    logger.info("ClinVar download: %.1f MB / %.1f MB", done_mb, total / (1024 * 1024))


def _note_progress(done: int, total: int | None, progress_every: int, last_mark: int) -> int:
    if progress_every <= 0:
        return last_mark
    mark = done // progress_every
    while last_mark < mark:
        last_mark += 1
        _log_progress(last_mark * progress_every, total)
    return last_mark


def _valid_gzip(path: Path) -> bool:
    """True only when the file exists and its gzip members read through to the CRC."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with gzip.open(path, "rb") as handle:
            while handle.read(1024 * 1024):
                pass
    except (OSError, EOFError, gzip.BadGzipFile):
        return False
    return True


def _transfer(url: str, part: Path, timeout: float | tuple[float, float], progress_every: int) -> None:
    """Stream one HTTP response into ``part``, resuming with Range when it already has bytes."""
    offset = _part_size(part)
    headers = {"User-Agent": USER_AGENT}
    if offset > 0:
        headers["Range"] = f"bytes={offset}-"
    try:
        response_cm = requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=_timeout_pair(timeout),
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        raise _Retry(f"ClinVar download failed: {exc.__class__.__name__}") from exc
    except OSError as exc:
        raise _Retry(f"ClinVar download failed: {exc.__class__.__name__}") from exc

    with response_cm as response:
        status = int(response.status_code)
        if status == 416 and offset > 0:
            part.unlink(missing_ok=True)
            raise _Retry("ClinVar download range was rejected")
        if status in _RETRYABLE_STATUS:
            raise _Retry(f"ClinVar download failed with HTTP {status}")
        if status >= 400:
            part.unlink(missing_ok=True)
            raise ClinVarDownloadError(f"ClinVar download failed with HTTP {status}")
        if status not in (200, 206):
            raise ClinVarDownloadError(f"ClinVar download failed with HTTP {status}")
        # 200 means a full body. A server that ignores Range must not be appended
        # onto the bytes already on disk.
        mode = "ab" if status == 206 and offset > 0 else "wb"
        expected = _expected_size(response, status, offset if mode == "ab" else 0)
        done = offset if mode == "ab" else 0
        last_mark = done // progress_every if progress_every > 0 else 0
        try:
            with part.open(mode) as handle:
                for block in response.iter_content(chunk_size=_CHUNK_BYTES):
                    if not block:
                        continue
                    handle.write(block)
                    done += len(block)
                    last_mark = _note_progress(done, expected, progress_every, last_mark)
        except (requests.RequestException, OSError) as exc:
            raise _Retry(f"ClinVar download failed: {exc.__class__.__name__}") from exc

    size = _part_size(part)
    if expected is not None and size < expected:
        raise _Retry("ClinVar download ended before the remote file was complete")
    if expected is not None and size > expected:
        part.unlink(missing_ok=True)
        raise _Retry("ClinVar download size exceeded the remote Content-Length")
    if not _valid_gzip(part):
        part.unlink(missing_ok=True)
        raise _Retry("ClinVar download is not a valid gzip file")


def download_variant_summary(
    dest: Path,
    url: str = VARIANT_SUMMARY_URL,
    timeout: float | tuple[float, float] = (_CONNECT_TIMEOUT, _READ_TIMEOUT),
    retries: int = 5,
    backoff: float = 1.0,
    progress_every: int = _PROGRESS_BYTES,
) -> Path:
    """Download ``url`` to ``dest`` with ``requests`` streaming.

    Connect and read timeouts are separate. Connection drops retry with
    exponential backoff. A ``.part`` file is reused with an HTTP Range request.
    Progress is logged every ``progress_every`` bytes (10 MB by default).
    The destination is replaced only after the byte count matches Content-Length,
    when the server sent one, and the gzip CRC validates. A failed final attempt
    leaves a non-empty ``.part`` in place when the bytes may still be resumed,
    and never publishes an incomplete file as ``dest``.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = _part_path(dest)
    attempts = max(0, retries) + 1
    last_message = "ClinVar download failed"

    for attempt in range(attempts):
        try:
            _transfer(url, part, timeout, progress_every)
        except ClinVarDownloadError:
            _drop_empty(part)
            raise
        except _Retry as exc:
            last_message = str(exc)
            _drop_empty(part)
            if attempt + 1 >= attempts:
                break
            delay = _delay(attempt, backoff)
            if delay:
                time.sleep(delay)
            continue
        part.replace(dest)
        return dest

    raise ClinVarDownloadError(last_message)
