"""HTTP helper for the personal-account providers (Monzo, Trading212).

Maps transport and HTTP failures to `ProviderError`. Messages carry the provider name and HTTP status
only: never URLs, headers, tokens or response bodies.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

# Epoch-looking x-ratelimit-reset values are above this (seconds since 1970 is about 1.7e9).
_EPOCH_THRESHOLD = 1_000_000_000


class ProviderError(Exception):
    """A provider call failed. `code` is one of: timeout, auth, rate_limited, unavailable, bad_data,
    not_configured, bad_state, offline."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        source: str = "provider",
        retryable: bool = False,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.source = source
        self.retryable = retryable
        self.retry_after = retry_after

    def to_error_body(self) -> dict[str, dict[str, str]]:
        """The API error envelope: {"error": {"code", "message", "source"}}."""
        return {"error": {"code": self.code, "message": self.message, "source": self.source}}


def _number(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None  # e.g. an HTTP-date; we do not guess
    return value if value >= 0 else None


def retry_after_seconds(headers: httpx.Headers, wall_clock: Callable[[], float] = time.time) -> float | None:
    """Retry-After (seconds), else x-ratelimit-reset.

    VERIFY: docs.trading212.com does not say whether x-ratelimit-reset is a seconds delta or an epoch
    timestamp, so both are handled.
    """
    value = _number(headers.get("Retry-After"))
    if value is not None:
        return value
    reset = _number(headers.get("x-ratelimit-reset"))
    if reset is None:
        return None
    return max(0.0, reset - wall_clock()) if reset >= _EPOCH_THRESHOLD else reset


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    source: str,
    wall_clock: Callable[[], float] = time.time,
    **kw: Any,
) -> Any:
    try:
        resp = await client.request(method, url, **kw)
    except httpx.TimeoutException as exc:
        raise ProviderError("timeout", f"{source} request timed out", source=source, retryable=True) from exc
    except httpx.HTTPError as exc:
        raise ProviderError(
            "unavailable", f"{source} connection error ({type(exc).__name__})", source=source, retryable=True
        ) from exc

    status = resp.status_code
    if status in (401, 403):
        raise ProviderError("auth", f"{source} rejected credentials (HTTP {status})", source=source)
    if status == 429:
        raise ProviderError(
            "rate_limited",
            f"{source} rate limited (HTTP 429)",
            source=source,
            retryable=True,
            retry_after=retry_after_seconds(resp.headers, wall_clock),
        )
    if status >= 500:
        raise ProviderError("unavailable", f"{source} server error (HTTP {status})", source=source, retryable=True)
    if status >= 400:
        raise ProviderError("bad_data", f"{source} unexpected response (HTTP {status})", source=source)
    try:
        return resp.json()
    except ValueError as exc:
        raise ProviderError("bad_data", f"{source} returned invalid JSON", source=source) from exc
