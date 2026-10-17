"""Adapter base: HTTP with timeout, retries with backoff and jitter, circuit breaker, payload validation.

Each adapter maps one source to `lifeline_contracts.Observation`. Adapters raise `AdapterError`
subclasses. `DataHub` catches them and applies the fallback order (cached, then mock).
"""

from __future__ import annotations

import asyncio
import math
import os
import random
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any, ClassVar

import httpx

from lifeline_contracts.observation import Observation, Status
from lifeline_data.settings import BROWSER_USER_AGENT, DataSettings

RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


class AdapterError(Exception):
    """Base error for one adapter call."""


class FetchError(AdapterError):
    """Network failure, timeout, or non-success HTTP status."""


class PayloadError(AdapterError):
    """The response parsed, but the data is empty or invalid."""


class CircuitOpenError(AdapterError):
    """The breaker is open; no request was sent."""


class MissingKeyError(AdapterError):
    """A required API key is not set. The message names the variable, never a value."""


class CircuitBreaker:
    """Opens after `threshold` consecutive failures. After `reset_seconds` it is half-open: one trial
    call goes through. Success closes it; failure opens it again."""

    def __init__(self, threshold: int = 3, reset_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self.threshold = threshold
        self.reset_seconds = reset_seconds
        self._clock = clock
        self.failures = 0
        self.opened_at: float | None = None

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        if self._clock() - self.opened_at >= self.reset_seconds:
            return "half-open"
        return "open"

    def allow(self) -> bool:
        return self.state != "open"

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.opened_at is not None or self.failures >= self.threshold:
            self.opened_at = self._clock()


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_number(raw: Any) -> float:
    """Parse a numeric payload value. Rejects empty, non-numeric, NaN and infinite values."""
    if raw is None or isinstance(raw, bool):
        raise PayloadError(f"non-numeric value: {raw!r}")
    if isinstance(raw, str):
        raw = raw.strip().replace(",", "")
        if raw == "":
            raise PayloadError("empty value")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise PayloadError(f"non-numeric value: {raw!r}") from exc
    if not math.isfinite(value):
        raise PayloadError(f"non-finite value: {raw!r}")
    return value


# Plausible ranges per unit. Adapters can override per series with `Adapter.bounds`.
UNIT_BOUNDS: dict[str, tuple[float, float]] = {
    "percent": (-100.0, 100.0),
    "gbp": (0.0, 100_000_000.0),
    "rate": (0.0, 1_000.0),
    "index": (0.0, 100_000.0),
}

EARLIEST_DATE = date(1900, 1, 1)


def validate_observations(
    observations: Iterable[Observation], bounds: dict[str, tuple[float, float]] | None = None
) -> list[Observation]:
    """Reject the payload when it is empty, a value is out of range, or a date is impossible."""
    items = list(observations)
    if not items:
        raise PayloadError("empty payload")
    latest = (utcnow() + timedelta(days=400)).date()
    for obs in items:
        if not (EARLIEST_DATE <= obs.date <= latest):
            raise PayloadError(f"date out of range for {obs.series_id}: {obs.date}")
        lo, hi = (bounds or {}).get(obs.series_id) or UNIT_BOUNDS.get(obs.unit, (-math.inf, math.inf))
        if not (lo <= obs.value <= hi):
            raise PayloadError(f"value out of range for {obs.series_id}: {obs.value}")
    return items


class Adapter:
    """Base for one source. Subclasses set `source_id` and implement `fetch()`."""

    source_id: ClassVar[str] = ""
    # Series fetched by the worker and used for the MacroTable: list of (series_id, region).
    default_series: ClassVar[tuple[tuple[str, str | None], ...]] = ()
    bounds: ClassVar[dict[str, tuple[float, float]]] = {}

    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: DataSettings,
        breaker: CircuitBreaker | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.client = client
        self.settings = settings
        self.breaker = breaker or CircuitBreaker(settings.breaker_threshold, settings.breaker_reset_seconds)
        self._sleep = sleep
        self._clock = clock
        # Short-lived memo of successful GET bodies. One payload often holds several series.
        self._memo: dict[str, tuple[float, str]] = {}
        self.memo_seconds = 120.0
        # Environment for API keys. DataHub injects its own mapping.
        self.env: Mapping[str, str] = os.environ

    async def fetch(self, series_id: str, region: str | None = None) -> list[Observation]:
        raise NotImplementedError

    async def fetch_validated(self, series_id: str, region: str | None = None) -> list[Observation]:
        """Fetch through the breaker and validate. Any failure counts against the breaker."""
        if not self.breaker.allow():
            raise CircuitOpenError(f"{self.source_id}: circuit open")
        try:
            result = validate_observations(await self.fetch(series_id, region), self.bounds)
        except AdapterError:
            self.breaker.record_failure()
            raise
        except Exception as exc:  # parse bugs, unexpected shapes
            self.breaker.record_failure()
            raise PayloadError(f"{self.source_id}: {type(exc).__name__}: {exc}") from exc
        self.breaker.record_success()
        return result

    async def get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        """GET body as text, memoised for `memo_seconds`."""
        key = url + "?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
        hit = self._memo.get(key)
        now = self._clock()
        if hit is not None and now - hit[0] < self.memo_seconds:
            return hit[1]
        text = (await self.get(url, params)).text
        self._memo[key] = (now, text)
        return text

    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        headers: dict[str, str] | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
    ) -> httpx.Response:
        """GET with timeout and retries. Retries only on timeout, 429 and 5xx."""
        return await self.request("GET", url, params=params, headers=headers, auth=auth)

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json_body: Any | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
    ) -> httpx.Response:
        """HTTP call with timeout and retries (only on timeout, 429 and 5xx).

        Error messages carry the source id and HTTP status only, never URLs, headers or keys.
        """
        tries = self.settings.http_retries
        last: Exception | None = None
        sent = {"User-Agent": BROWSER_USER_AGENT, "Accept": "*/*", **(headers or {})}
        for attempt in range(tries):
            try:
                resp = await self.client.request(
                    method,
                    url,
                    params=params,
                    headers=sent,
                    json=json_body,
                    auth=auth if auth is not None else httpx.USE_CLIENT_DEFAULT,
                    timeout=self.settings.http_timeout_seconds,
                    follow_redirects=True,
                )
            except httpx.TimeoutException as exc:
                last = FetchError(f"{self.source_id}: timeout")
                last.__cause__ = exc
            except httpx.HTTPError as exc:
                raise FetchError(f"{self.source_id}: {type(exc).__name__}") from exc
            else:
                if resp.status_code in RETRY_STATUS:
                    last = FetchError(f"{self.source_id}: HTTP {resp.status_code}")
                elif resp.status_code >= 400:
                    raise FetchError(f"{self.source_id}: HTTP {resp.status_code}")
                else:
                    return resp
            if attempt < tries - 1:
                base = self.settings.backoff_base_seconds * (2**attempt)
                await self._sleep(base + random.uniform(0, base))  # noqa: S311 - jitter, not crypto
        assert last is not None
        raise last

    def key(self, name: str) -> str:
        """Value of a required env var. Never logged. Missing -> MissingKeyError (hub serves mock)."""
        value = self.env.get(name, "")
        if not value:
            raise MissingKeyError(f"{name} not set")
        return value

    def obs(
        self, series_id: str, day: date, value: float, unit: str, region: str | None = None, status: Status = "live"
    ) -> Observation:
        return Observation(
            series_id=series_id,
            source=self.source_id,
            date=day,
            value=value,
            unit=unit,
            region=region,
            fetched_at=utcnow(),
            status=status,
        )
