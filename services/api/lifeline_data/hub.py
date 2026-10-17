"""DataHub: implements `lifeline_contracts.interfaces.DataHub`.

Fallback order per series call:
1. Redis entry that is still fresh (inside the source TTL): returned as stored.
2. Live fetch through the adapter (timeout, retries, breaker, validation): status "live".
3. Stale Redis entry: status "cached".
4. Postgres last-good snapshot: status "cached".
5. Built-in mock from the mock MacroTable: status "mock".

The hub never raises to the caller. In offline mode (APP_ENV=test or DATA_OFFLINE=1) it sends no
network requests unless a client is injected (tests inject a respx-mocked client).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from lifeline_contracts.finance import FinanceSnapshot
from lifeline_contracts.macro import MacroTable
from lifeline_contracts.observation import Observation, SourceStatus, Status
from lifeline_data.adapters import ADAPTERS, BankHolidaysAdapter, OpenMeteoAdapter, PostcodesAdapter
from lifeline_data.adapters.postcodes import normalise_postcode
from lifeline_data.base import Adapter, CircuitBreaker, utcnow
from lifeline_data.cache import ObservationCache, SnapshotStore, obs_key
from lifeline_data.finance import DEMO_PERSONA_ID, fixture_snapshot
from lifeline_data.logsafe import quiet_http_loggers, redact_urls
from lifeline_data.macro import build_macro_table, mock_macro_table
from lifeline_data.mocks import mock_postcode, mock_series
from lifeline_data.prediction_inputs import (
    division_for_region,
    fixture_bank_holidays,
    mock_daily_weather,
    mock_weather_day,
)
from lifeline_data.settings import DataSettings
from lifeline_data.sources import SOURCES, missing_keys

log = logging.getLogger(__name__)
quiet_http_loggers()  # keys in query strings (Adzuna) must never reach logs; applies to API and worker

# Adapters that fetch one region per request. Others return every region in one payload.
PER_REGION_SOURCES = frozenset({"landregistry", "openmeteo"})


STATE_KEY = "lifeline:source_state:{sid}"
# Probe postcode for the worker: proves postcodes.io is reachable and records shared state.
PROBE_POSTCODE = "SW1A 1AA"


@dataclass
class SourceState:
    status: Status
    fetched_at: datetime | None = None
    last_error: str | None = None
    updated_at: float = 0.0  # unix seconds; newest state wins across processes

    def to_json(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "last_error": self.last_error,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_json(cls, doc: Any) -> SourceState | None:
        try:
            status = doc["status"]
            if status not in ("live", "cached", "mock"):
                return None
            fetched = datetime.fromisoformat(doc["fetched_at"]) if doc.get("fetched_at") else None
            return cls(status, fetched, doc.get("last_error"), float(doc.get("updated_at") or 0.0))
        except (KeyError, TypeError, ValueError):
            return None


class DataHub:
    def __init__(
        self,
        settings: Any | None = None,
        *,
        redis: Any | None = None,
        db: AsyncEngine | None = None,
        client: httpx.AsyncClient | None = None,
        env: Mapping[str, str] | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self.settings = DataSettings.from_any(settings)
        self._env: Mapping[str, str] = env if env is not None else os.environ
        self._clock = clock
        self._sleep = sleep or asyncio.sleep
        offline = self.settings.offline
        self.live_enabled = client is not None or not offline
        self.cache = ObservationCache(redis=redis, url="" if offline else self.settings.redis_url, clock=clock)
        self.snapshots = SnapshotStore(engine=db, url="" if offline else self.settings.database_url)
        self._client = client
        self._owns_client = client is None
        self._adapters: dict[str, Adapter] = {}
        self._postcodes: PostcodesAdapter | None = None
        self._state: dict[str, SourceState] = {}
        self._macro: tuple[float, MacroTable] | None = None
        self._macro_lock = asyncio.Lock()

    # --- plumbing ---------------------------------------------------------------------------

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.settings.http_timeout_seconds, follow_redirects=True)
        return self._client

    def adapter(self, source: str) -> Adapter | None:
        if source not in ADAPTERS:
            return None
        if source not in self._adapters:
            breaker = CircuitBreaker(
                self.settings.breaker_threshold, self.settings.breaker_reset_seconds, clock=self._clock
            )
            adapter = ADAPTERS[source](self._http(), self.settings, breaker, self._sleep, self._clock)
            adapter.env = self._env
            self._adapters[source] = adapter
        return self._adapters[source]

    def postcodes_adapter(self) -> PostcodesAdapter:
        if self._postcodes is None:
            breaker = CircuitBreaker(
                self.settings.breaker_threshold, self.settings.breaker_reset_seconds, clock=self._clock
            )
            self._postcodes = PostcodesAdapter(self._http(), self.settings, breaker, self._sleep, self._clock)
        return self._postcodes

    async def _set_state(
        self, source: str, status: Status, error: str | None = None, fetched_at: datetime | None = None
    ) -> None:
        """Record source health locally and in the shared cache (Redis), so every process sees it."""
        prev = await self._get_state(source)
        if fetched_at is None and prev is not None:
            fetched_at = prev.fetched_at
        state = SourceState(status, fetched_at, error, self._clock())
        self._state[source] = state
        try:
            await self.cache.set_raw(STATE_KEY.format(sid=source), state.to_json())
        except Exception as exc:
            log.warning("could not share state for %s (%s)", source, type(exc).__name__)

    async def _get_state(self, source: str) -> SourceState | None:
        """Newest of the local state and the shared state written by any process."""
        local = self._state.get(source)
        shared: SourceState | None = None
        try:
            entry = await self.cache.get_raw(STATE_KEY.format(sid=source))
            if entry is not None:
                shared = SourceState.from_json(entry.payload)
        except Exception as exc:
            log.warning("could not read shared state for %s (%s)", source, type(exc).__name__)
        if shared is not None and (local is None or shared.updated_at > local.updated_at):
            self._state[source] = shared  # last known state survives a later Redis outage
            return shared
        return local

    def _age_state(self, source: str, state: SourceState) -> SourceState:
        """A live state with no refresh for 2 x max(TTL, refresh interval) is reported as cached."""
        if state.status != "live" or state.fetched_at is None:
            return state
        limit = 2 * max(SOURCES[source].ttl_seconds, self.settings.data_refresh_interval_seconds)
        age = self._clock() - state.fetched_at.timestamp()
        if age > limit:
            return SourceState("cached", state.fetched_at, "not refreshed recently", state.updated_at)
        return state

    def _missing_key_error(self, source: str) -> str | None:
        info = SOURCES[source]
        missing = missing_keys(info, self._env)
        return f"{missing[0]} not set" if missing else None

    @staticmethod
    def _filter(observations: list[Observation], region: str | None) -> list[Observation]:
        if region is None:
            return observations
        return [o for o in observations if o.region == region]

    @staticmethod
    def _relabel(observations: list[Observation], status: Status) -> list[Observation]:
        return [o if o.status == status else o.model_copy(update={"status": status}) for o in observations]

    # --- DataHub protocol -------------------------------------------------------------------

    async def series(
        self, source: str, series_id: str, region: str | None = None, *, force: bool = False
    ) -> list[Observation]:
        """Observations for one series. region=None returns UK plus every region the source gives.

        Never raises. `force=True` skips the fresh-cache step (used by the worker).
        """
        try:
            return await self._series(source, series_id, region, force)
        except Exception as exc:  # last line of defence: never raise to the caller
            log.exception("series %s/%s failed", source, series_id)
            if source in SOURCES:
                await self._set_state(source, "mock", f"internal error: {type(exc).__name__}")
            return mock_series(source, series_id, region)

    async def _series(self, source: str, series_id: str, region: str | None, force: bool) -> list[Observation]:
        info = SOURCES.get(source)
        if info is None:
            return []
        key_error = self._missing_key_error(source)
        if key_error is not None:
            await self._set_state(source, "mock", key_error)
            return mock_series(source, series_id, region)

        fetch_region = region if source in PER_REGION_SOURCES else None
        ckey = obs_key(source, series_id, fetch_region)

        cached = await self.cache.get(ckey)
        if cached is not None and not force:
            stored_at, obs = cached
            if self._clock() - stored_at < info.ttl_seconds:
                if source not in self._state and obs:
                    newest = max(obs, key=lambda o: o.fetched_at)
                    self._state[source] = SourceState(newest.status, newest.fetched_at, None, stored_at)
                return self._filter(obs, region)

        adapter = self.adapter(source) if self.live_enabled else None
        error: str
        if adapter is None:
            error = "offline mode" if not self.live_enabled else "no live adapter yet"
        else:
            try:
                obs = await adapter.fetch_validated(series_id, fetch_region)
            except Exception as exc:
                error = redact_urls(str(exc) or type(exc).__name__)
                log.warning("live fetch failed for %s/%s: %s", source, series_id, error)
            else:
                await self.cache.set(ckey, obs)
                await self.snapshots.put(ckey, obs)
                await self._set_state(source, "live", None, utcnow())
                return self._filter(obs, region)

        if cached is not None:
            await self._set_state(source, "cached", error)
            return self._filter(self._relabel(cached[1], "cached"), region)
        snap = await self.snapshots.get(ckey)
        if snap:
            await self._set_state(source, "cached", error)
            return self._filter(self._relabel(snap, "cached"), region)
        await self._set_state(source, "mock", error)
        return mock_series(source, series_id, region)

    async def statuses(self) -> list[SourceStatus]:
        out: list[SourceStatus] = []
        for sid, info in SOURCES.items():
            key_error = self._missing_key_error(sid)
            state = None if key_error is not None else await self._get_state(sid)
            if key_error is not None:
                state = SourceState("mock", None, key_error)
            elif state is not None:
                state = self._age_state(sid, state)
            elif sid not in ADAPTERS and sid != "postcodes":
                state = SourceState("mock", None, "no live adapter yet")
            elif not self.live_enabled:
                state = SourceState("mock", None, "offline mode")
            else:
                state = SourceState("mock", None, "not fetched yet")
            out.append(
                SourceStatus(
                    id=sid,
                    name=info.name,
                    status=state.status,
                    fetched_at=state.fetched_at,
                    ttl_seconds=info.ttl_seconds,
                    coverage=info.coverage,
                    attribution=info.attribution,
                    licence=info.licence,
                    needs_key=info.needs_key,
                    last_error=state.last_error,
                )
            )
        return out

    async def macro_table(self, *, force: bool = False) -> MacroTable:
        """Annual MacroTable for 1990..2026. Never raises. Offline without a client: the mock table."""
        if not self.live_enabled:
            return mock_macro_table()
        async with self._macro_lock:
            now = time.monotonic()
            if not force and self._macro is not None and now - self._macro[0] < self.settings.macro_table_ttl_seconds:
                return self._macro[1]
            try:
                calls = [
                    self.series(source, series_id, region, force=force)
                    for source, cls in ADAPTERS.items()
                    for series_id, region in cls.default_series
                ]
                batches = await asyncio.gather(*calls)
                table = build_macro_table(o for batch in batches for o in batch)
            except Exception:
                log.exception("macro table build failed; using mock table")
                return self._macro[1] if self._macro is not None else mock_macro_table()
            self._macro = (now, table)
            return table

    async def lookup_postcode(self, postcode: str) -> dict[str, str] | None:
        """{'region', 'town', 'postcode'} or None for an invalid or unknown postcode. Never raises."""
        pc = normalise_postcode(postcode)
        if pc is None:
            return None
        ckey = f"lifeline:postcode:{pc.replace(' ', '')}"
        try:
            entry = await self.cache.get_raw(ckey)
            ttl = SOURCES["postcodes"].ttl_seconds
            if entry is not None and self._clock() - entry.stored_at < ttl:
                return entry.payload  # type: ignore[no-any-return]
            if not self.live_enabled:
                await self._set_state("postcodes", "mock", "offline mode")
                return mock_postcode(pc)
            try:
                result = await self.postcodes_adapter().lookup(pc)
            except Exception as exc:
                error = redact_urls(str(exc) or type(exc).__name__)
                if entry is not None:
                    await self._set_state("postcodes", "cached", error)
                    return entry.payload  # type: ignore[no-any-return]
                await self._set_state("postcodes", "mock", error)
                return mock_postcode(pc)
            await self._set_state("postcodes", "live", None, utcnow())
            if result is not None:
                await self.cache.set_raw(ckey, result, keep_seconds=2 * ttl)
            return result
        except Exception:
            log.exception("postcode lookup failed")
            return mock_postcode(pc)

    # --- finance (ADR 0016, ADR 0018) ---------------------------------------------------------

    async def finance_snapshot(self, subject: str) -> FinanceSnapshot:
        """Accounts, 12 months of transactions, mortgage and energy for one user. Never raises.

        Tier 1: labelled fixture persona (status "mock", source "fixtures"), chosen per subject.
        """
        try:
            return fixture_snapshot(subject)
        except Exception:
            log.exception("finance snapshot failed; using the demo persona")
            return fixture_snapshot(DEMO_PERSONA_ID)

    # --- prediction inputs (ADR 0017) ----------------------------------------------------------

    async def bank_holidays(self, region: str | None) -> set[date]:
        """Bank holidays for the gov.uk division of `region` (None = England and Wales). Never raises.

        Order: fresh cache -> live gov.uk -> stale cache ("cached") -> recorded gov.uk fixture ("mock").
        """
        division = division_for_region(region)
        ckey = "lifeline:bankholidays"
        ttl = SOURCES["bankholidays"].ttl_seconds
        try:
            entry = await self.cache.get_raw(ckey)
            if entry is not None and self._clock() - entry.stored_at < ttl:
                return {date.fromisoformat(d) for d in entry.payload.get(division, [])}
            error = "offline mode"
            adapter = self.adapter("bankholidays") if self.live_enabled else None
            if isinstance(adapter, BankHolidaysAdapter):
                try:
                    parsed = await adapter.fetch_holidays()
                except Exception as exc:
                    error = redact_urls(str(exc) or type(exc).__name__)
                else:
                    payload = {k: sorted(d.isoformat() for d in v) for k, v in parsed.items()}
                    await self.cache.set_raw(ckey, payload, keep_seconds=30 * ttl)
                    await self._set_state("bankholidays", "live", None, utcnow())
                    return set(parsed.get(division, set()))
            if entry is not None:
                await self._set_state("bankholidays", "cached", error)
                return {date.fromisoformat(d) for d in entry.payload.get(division, [])}
            await self._set_state("bankholidays", "mock", error)
        except Exception:
            log.exception("bank holidays failed; using the recorded fixture")
        return set(fixture_bank_holidays().get(division, frozenset()))

    async def daily_weather(
        self, region: str | None, start: date, end: date, *, today: date | None = None
    ) -> list[dict[str, Any]]:
        """[{date, temp_max_c, rain_mm, status}] for every day in start..end. Never raises.

        Live days come from Open-Meteo (archive for older days, forecast for recent and future days).
        Days the source cannot give (or every day, when it fails) are labelled mock.
        """
        if end < start:
            return []
        today = today or date.today()
        ckey = f"lifeline:weather:{region or 'uk'}:{start.isoformat()}:{end.isoformat()}"
        ttl = SOURCES["openmeteo"].ttl_seconds
        try:
            entry = await self.cache.get_raw(ckey)
            if entry is not None and self._clock() - entry.stored_at < ttl:
                return self._weather_rows(entry.payload, region, start, end, "live")
            error = "offline mode"
            adapter = self.adapter("openmeteo") if self.live_enabled else None
            if isinstance(adapter, OpenMeteoAdapter):
                try:
                    days = await adapter.daily_validated(region, start, end, today)
                except Exception as exc:
                    error = redact_urls(str(exc) or type(exc).__name__)
                else:
                    payload = {d.isoformat(): [t, r] for d, (t, r) in days.items()}
                    await self.cache.set_raw(ckey, payload, keep_seconds=24 * ttl)
                    await self._set_state("openmeteo", "live", None, utcnow())
                    return self._weather_rows(payload, region, start, end, "live")
            if entry is not None:
                await self._set_state("openmeteo", "cached", error)
                return self._weather_rows(entry.payload, region, start, end, "cached")
            await self._set_state("openmeteo", "mock", error)
        except Exception:
            log.exception("daily weather failed; using mock weather")
        return mock_daily_weather(region, start, end)

    @staticmethod
    def _weather_rows(
        payload: dict[str, Any], region: str | None, start: date, end: date, status: Status
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        day = start
        while day <= end:
            hit = payload.get(day.isoformat())
            if hit is None:
                rows.append(mock_weather_day(region, day))
            else:
                rows.append({"date": day, "temp_max_c": float(hit[0]), "rain_mm": float(hit[1]), "status": status})
            day += timedelta(days=1)
        return rows

    # --- worker support ---------------------------------------------------------------------

    async def refresh_all(self) -> list[SourceStatus]:
        """Fetch every default series live (skip fresh cache) and rebuild the MacroTable."""
        await self.macro_table(force=True)
        await self.probe_postcodes()
        return await self.statuses()

    async def probe_postcodes(self) -> None:
        """One live postcodes.io lookup so the shared status reflects reality. Never raises."""
        if not self.live_enabled:
            return
        try:
            result = await self.postcodes_adapter().lookup(PROBE_POSTCODE)
        except Exception as exc:
            await self._set_state("postcodes", "mock", redact_urls(str(exc) or type(exc).__name__))
            return
        if result is None:
            await self._set_state("postcodes", "mock", "probe postcode not found")
        else:
            await self._set_state("postcodes", "live", None, utcnow())

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        await self.cache.aclose()
        await self.snapshots.aclose()
