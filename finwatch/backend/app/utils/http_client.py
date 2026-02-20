"""HTTP reliability helpers for crawling/downloading."""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx

RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
BLOCK_STATUS_CODES = {401, 403, 429, 503}
BLOCK_PATTERNS = (
    "captcha",
    "access denied",
    "forbidden",
    "cloudflare",
    "bot detection",
    "verify you are human",
)


def request_with_retries(
    method: str,
    url: str,
    *,
    retries: int = 3,
    timeout: float = 15.0,
    backoff_seconds: float = 0.6,
    max_backoff_seconds: float = 6.0,
    headers: Optional[dict[str, str]] = None,
    follow_redirects: bool = True,
    json: Optional[dict[str, Any]] = None,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = httpx.request(
                method=method,
                url=url,
                timeout=timeout,
                headers=headers,
                follow_redirects=follow_redirects,
                json=json,
            )
            if response.status_code in RETRYABLE_STATUSES and attempt < retries - 1:
                _sleep_with_backoff(attempt, backoff_seconds, max_backoff_seconds)
                continue
            return response
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.NetworkError) as exc:
            last_error = exc
            if attempt >= retries - 1:
                raise
            _sleep_with_backoff(attempt, backoff_seconds, max_backoff_seconds)

    if last_error:
        raise last_error
    raise RuntimeError("request_with_retries exhausted without response")


def is_blocked_response(response: httpx.Response) -> bool:
    if response.status_code in BLOCK_STATUS_CODES:
        return True
    text = (response.text or "")[:3000].lower()
    return any(pattern in text for pattern in BLOCK_PATTERNS)


def _sleep_with_backoff(attempt: int, base: float, cap: float):
    delay = min(cap, base * (2**attempt))
    if delay > 0:
        time.sleep(delay)
