"""Async CPIC API client. Retries transport errors, HTTP 429, and HTTP 5xx."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .errors import CpicApiError

CPIC_BASE_URL = "https://api.cpicpgx.org/v1/"
USER_AGENT = "GENOMIQ/1.0 (cpic-ingest)"
GUIDELINE_PATH = "guideline"
RECOMMENDATION_PATH = "recommendation_view"
GUIDELINE_SELECT = "*,publication(title,pmid,year)"
_PAGE_SIZE = 1000
_NON_RETRYABLE_STATUS = {400, 401, 403, 404}

logger = logging.getLogger("cpic_ingest.client")


def _ensure_logger() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or 500 <= code <= 599
    return False


def _before_sleep(retry_state) -> None:
    _ensure_logger()
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "CPIC request will be retried (attempt %s/5): %s",
        retry_state.attempt_number,
        exc.__class__.__name__ if exc else "error",
    )


class CpicClient:
    """Reusable async client for the CPIC PostgREST API.

    Use it as an async context manager so the underlying ``httpx`` client is
    closed. ``timeout`` is the httpx timeout in seconds.
    """

    def __init__(
        self,
        *,
        base_url: str = CPIC_BASE_URL,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url if base_url.endswith("/") else base_url + "/"
        self.timeout = timeout
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "CpicClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            transport=self._transport,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch_guidelines(self) -> list[dict]:
        """GET /guideline ordered by name, including publication pmid and year."""
        return await self._get_all(
            GUIDELINE_PATH,
            {"select": GUIDELINE_SELECT, "order": "name"},
        )

    async def fetch_recommendations(self, drugname: str) -> list[dict]:
        """GET /recommendation_view filtered to one drug name."""
        return await self._get_all(
            RECOMMENDATION_PATH,
            {"drugname": _eq_filter(drugname)},
        )

    async def _get_all(self, path: str, params: dict[str, str]) -> list[dict]:
        rows: list[dict] = []
        start = 0
        while True:
            try:
                response = await self._send(
                    path,
                    params=params,
                    headers={"Range": f"{start}-{start + _PAGE_SIZE - 1}"},
                )
            except httpx.HTTPStatusError as exc:
                _ensure_logger()
                logger.error(
                    "CPIC request failed after retries: GET %s HTTP %s",
                    path,
                    exc.response.status_code,
                )
                raise CpicApiError(f"CPIC HTTP {exc.response.status_code} for {path}") from exc
            except httpx.TransportError as exc:
                _ensure_logger()
                logger.error(
                    "CPIC request failed after retries: GET %s (%s)",
                    path,
                    exc.__class__.__name__,
                )
                raise CpicApiError(
                    f"CPIC transport failure for {path}: {exc.__class__.__name__}"
                ) from exc
            payload = response.json()
            if not isinstance(payload, list):
                raise CpicApiError(f"CPIC response for {path} was not a list")
            rows.extend(item for item in payload if isinstance(item, dict))
            if len(payload) < _PAGE_SIZE or not _has_more(response, len(rows)):
                break
            start += _PAGE_SIZE
        return rows

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential_jitter(initial=1, max=60),
        stop=stop_after_attempt(5),
        before_sleep=_before_sleep,
        reraise=True,
    )
    async def _send(self, path: str, *, params: dict[str, str], headers: dict[str, str]) -> httpx.Response:
        if self._client is None:
            raise CpicApiError("CPIC client is not open")
        try:
            response = await self._client.get(path, params=params, headers=headers)
        except httpx.TransportError as exc:
            _ensure_logger()
            logger.warning("CPIC transport error: GET %s (%s)", path, exc.__class__.__name__)
            raise
        code = response.status_code
        if code in _NON_RETRYABLE_STATUS:
            _ensure_logger()
            logger.error("CPIC request rejected: GET %s HTTP %s", path, code)
            raise CpicApiError(f"CPIC HTTP {code} for {path}")
        if code == 429 or 500 <= code <= 599:
            _ensure_logger()
            logger.warning("CPIC transient error: GET %s HTTP %s", path, code)
            raise httpx.HTTPStatusError(
                f"HTTP {code}",
                request=response.request,
                response=response,
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _ensure_logger()
            logger.error("CPIC request failed: GET %s HTTP %s", path, code)
            raise CpicApiError(f"CPIC HTTP {code} for {path}") from exc
        return response


def _eq_filter(value: str) -> str:
    """PostgREST ``eq`` filter. Quote values that contain reserved characters."""
    if any(char in value for char in ',.()"\\'):
        escaped = value.replace('"', '""')
        return f'eq."{escaped}"'
    return f"eq.{value}"


def _has_more(response: httpx.Response, seen: int) -> bool:
    content_range = response.headers.get("content-range")
    if not content_range or "/" not in content_range:
        return False
    total = content_range.rsplit("/", 1)[-1].strip()
    return total.isdigit() and seen < int(total)


def retry_policy() -> dict[str, Any]:
    """The tenacity settings attached to ``CpicClient._send``, for tests."""
    policy = CpicClient._send.retry
    return {"wait": policy.wait, "stop": policy.stop}
