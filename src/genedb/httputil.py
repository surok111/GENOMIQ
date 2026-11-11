"""HTTP-клиент на stdlib с паузами и повторами (NCBI / OMIM / ClinPGx)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "GENOMIQ/1.0 (gene-database-sync; https://github.com)"


def _redact_url(url: str) -> str:
    base = url.split("?", 1)[0]
    return base


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str, body: str = ""):
        super().__init__(f"HTTP {status} for {_redact_url(url)}")
        self.status = status
        self.url = url
        self.body = body


def get_json(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = 45,
    min_interval: float = 0.35,
    retries: int = 4,
) -> Any:
    if params:
        qs = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}?{qs}" if "?" not in url else f"{url}&{qs}"

    last_error: Exception | None = None
    for attempt in range(retries):
        if attempt:
            time.sleep(min(8.0, min_interval * (2 ** attempt)))
        else:
            time.sleep(min_interval)
        req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(url, headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                if retry_after:
                    try:
                        time.sleep(float(retry_after))
                    except ValueError:
                        pass
                last_error = HttpError(e.code, url, body)
                continue
            raise HttpError(e.code, url, body) from e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_error = e
            continue
    raise last_error or HttpError(0, url, "unknown error")
