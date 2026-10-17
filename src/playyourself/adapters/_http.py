"""Shared HTTP helper mapping transport/HTTP failures to SourceError.

No vendor limits are assumed here: 429 is handled generically via an optional Retry-After.
Error messages never include request headers or tokens.
"""

from typing import Any

import httpx

from playyourself.adapters.base import SourceError


def _retry_after(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None  # e.g. an HTTP-date; we do not guess
    return value if value >= 0 else None


async def request_json(
    client: httpx.AsyncClient, method: str, url: str, *, source: str, **kw: Any
) -> Any:
    try:
        resp = await client.request(method, url, **kw)
    except httpx.TimeoutException as exc:
        raise SourceError("timeout", f"{source} request timed out", retryable=True) from exc
    except httpx.HTTPError as exc:
        raise SourceError(
            "unavailable", f"{source} connection error ({type(exc).__name__})", retryable=True
        ) from exc

    status = resp.status_code
    if status in (401, 403):
        raise SourceError("auth", f"{source} rejected credentials (HTTP {status})")
    if status == 429:
        raise SourceError(
            "rate_limited",
            f"{source} rate limited (HTTP 429)",
            retryable=True,
            retry_after=_retry_after(resp),
        )
    if status >= 500:
        raise SourceError("unavailable", f"{source} server error (HTTP {status})", retryable=True)
    if status >= 400:
        raise SourceError("bad_data", f"{source} unexpected response (HTTP {status})")
    try:
        return resp.json()
    except ValueError as exc:
        raise SourceError("bad_data", f"{source} returned invalid JSON") from exc
