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

from lifeline_contracts.chat import NewsItem, NewsResponse, RateDecisions
from lifeline_contracts.domain import SourceRef
from lifeline_contracts.finance import FinanceSnapshot
from lifeline_contracts.macro import MacroTable
from lifeline_contracts.observation import Observation, SourceStatus, Status
from lifeline_data.adapters import (
    ADAPTERS,
    BankHolidaysAdapter,
    BoeMpcAdapter,
    GuardianAdapter,
    OpenMeteoAdapter,
    PostcodesAdapter,
)
from lifeline_data.adapters.context import guardian_query
from lifeline_data.adapters.market import fx_pair
from lifeline_data.adapters.postcodes import LAT_RANGE, LON_RANGE, normalise_postcode
from lifeline_data.base import Adapter, CircuitBreaker, PayloadError, utcnow
from lifeline_data.cache import ObservationCache, SnapshotStore, UserSnapshotStore, obs_key
from lifeline_data.crypto import Sealer
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
from lifeline_data.sources import (
    DISABLED_IN_LIVE,
    SOURCES,
    UNRELIABLE_IN_LIVE,
    missing_key_message,
    missing_keys,
    served_sources,
)

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
            if status not in ("live", "cached", "mock", "unavailable"):
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
        # ADR 0027: in live mode nothing falls back to mock data.
        self.live_mode = self.settings.live_mode
        self.no_data: Status = "unavailable" if self.live_mode else "mock"
        self.cache = ObservationCache(redis=redis, url="" if offline else self.settings.redis_url, clock=clock)
        self.snapshots = SnapshotStore(engine=db, url="" if offline else self.settings.database_url)
        strict = self.live_mode or self.settings.app_env.lower() in ("prod", "production")
        self.user_snapshots = UserSnapshotStore(self.snapshots, Sealer(self._env, strict=strict), clock=clock)
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
        return missing_key_message(missing[0]) if missing else None

    def _fallback(self, source: str, series_id: str, region: str | None) -> list[Observation]:
        """Demo mode: labelled mock series. Live mode: nothing."""
        return [] if self.live_mode else mock_series(source, series_id, region)

    def _disabled_reason(self, source: str) -> str | None:
        """Live mode only: the ADR 0027 policy reason for a source that is switched off."""
        if not self.live_mode:
            return None
        reason = DISABLED_IN_LIVE.get(source)
        return f"Disabled: {reason}" if reason else None

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
                await self._set_state(source, self.no_data, f"internal error: {type(exc).__name__}")
            return self._fallback(source, series_id, region)

    async def _series(self, source: str, series_id: str, region: str | None, force: bool) -> list[Observation]:
        info = SOURCES.get(source)
        if info is None:
            return []
        disabled = self._disabled_reason(source)
        if disabled is not None:
            await self._set_state(source, "unavailable", disabled)
            return []
        key_error = self._missing_key_error(source)
        if key_error is not None:
            await self._set_state(source, self.no_data, key_error)
            return self._fallback(source, series_id, region)

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
        if self.live_mode and source in UNRELIABLE_IN_LIVE:
            error = f"Disabled: {UNRELIABLE_IN_LIVE[source]} ({error})"
        await self._set_state(source, self.no_data, error)
        return self._fallback(source, series_id, region)

    async def statuses(self) -> list[SourceStatus]:
        out: list[SourceStatus] = []
        for sid, info in served_sources().items():
            nd = self.no_data
            disabled = self._disabled_reason(sid)
            key_error = self._missing_key_error(sid)
            state = None if (key_error or disabled) is not None else await self._get_state(sid)
            if disabled is not None:
                state = SourceState("unavailable", None, disabled)
            elif key_error is not None:
                state = SourceState(nd, None, key_error)
            elif state is not None:
                state = self._age_state(sid, state)
                if self.live_mode and state.status == "mock":  # e.g. shared state written by a demo process
                    state = SourceState("unavailable", state.fetched_at, state.last_error, state.updated_at)
            elif sid not in ADAPTERS and sid != "postcodes":
                state = SourceState(nd, None, "no live adapter yet")
            elif not self.live_enabled:
                state = SourceState(nd, None, "offline mode")
            else:
                state = SourceState(nd, None, "not fetched yet")
            if (
                self.live_mode
                and state.status == "unavailable"
                and sid in UNRELIABLE_IN_LIVE
                and not (state.last_error or "").startswith("Disabled:")
            ):
                reason = f"Disabled: {UNRELIABLE_IN_LIVE[sid]} ({state.last_error})"
                state = SourceState("unavailable", state.fetched_at, reason, state.updated_at)
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
        """Annual MacroTable for 1990..2026. Never raises.

        Demo mode: gaps are filled from the labelled mock table; offline without a client gives the
        mock table. Live mode (ADR 0027): only live or cached values; gaps stay gaps; offline gives an
        empty table.
        """
        if not self.live_enabled:
            return MacroTable(values={}) if self.live_mode else mock_macro_table()
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
                observations = [o for batch in batches for o in batch]
                if self.live_mode:
                    real = [o for o in observations if o.status in ("live", "cached")]
                    table = build_macro_table(real, base=MacroTable(values={}))
                else:
                    table = build_macro_table(observations)
            except Exception:
                log.exception("macro table build failed")
                if self._macro is not None:
                    return self._macro[1]
                return MacroTable(values={}) if self.live_mode else mock_macro_table()
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
                await self._set_state("postcodes", self.no_data, "offline mode")
                return None if self.live_mode else mock_postcode(pc)
            try:
                result = await self.postcodes_adapter().lookup(pc)
            except Exception as exc:
                error = redact_urls(str(exc) or type(exc).__name__)
                if entry is not None:
                    await self._set_state("postcodes", "cached", error)
                    return entry.payload  # type: ignore[no-any-return]
                await self._set_state("postcodes", self.no_data, error)
                return None if self.live_mode else mock_postcode(pc)
            await self._set_state("postcodes", "live", None, utcnow())
            if result is not None:
                await self.cache.set_raw(ckey, result, keep_seconds=2 * ttl)
            return result
        except Exception:
            log.exception("postcode lookup failed")
            return None if self.live_mode else mock_postcode(pc)

    # --- finance (ADR 0016, ADR 0018) ---------------------------------------------------------

    async def finance_snapshot(self, subject: str) -> FinanceSnapshot | None:
        """The user's own money data (statement import, manual entry, logged payments), or None. Never raises.

        Both modes: no data of their own means None (the API answers has_data=false or 409 no_finance_data).
        The demo finance personas (`lifeline_data.finance`) are never served: they exist for tests only.
        """
        return await self.get_user_snapshot(subject)

    async def reverse_postcode(self, lat: float, lon: float) -> dict[str, str] | None:
        """{'postcode', 'region', 'town', 'status'} for the nearest postcode, via postcodes.io. Never raises.

        None outside the UK box (lat 49-61.5, lon -8.7-2.0), at sea, or when the lookup fails and no
        cached answer exists. Never a guess in live mode. Demo mode offline also returns None (a
        point cannot be mapped to a postcode without the service).
        """
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return None
        if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
            return None
        # About 100 m grid: nearby points share a cache entry; exact coordinates are not stored.
        ckey = f"lifeline:postcode-reverse:{lat:.3f}:{lon:.3f}"
        ttl = SOURCES["postcodes"].ttl_seconds
        try:
            entry = await self.cache.get_raw(ckey)
            if entry is not None and self._clock() - entry.stored_at < ttl:
                return None if entry.payload is None else {**entry.payload, "status": "live"}  # fresh copy
            if not self.live_enabled:
                await self._set_state("postcodes", self.no_data, "offline mode")
                return None
            try:
                result = await self.postcodes_adapter().reverse(lat, lon)
            except Exception as exc:
                error = redact_urls(str(exc) or type(exc).__name__)
                if entry is not None and entry.payload is not None:
                    await self._set_state("postcodes", "cached", error)
                    return {**entry.payload, "status": "cached"}
                await self._set_state("postcodes", self.no_data, error)
                return None
            await self._set_state("postcodes", "live", None, utcnow())
            await self.cache.set_raw(ckey, result, keep_seconds=2 * ttl)
            return None if result is None else {**result, "status": "live"}
        except Exception:
            log.exception("reverse postcode failed")
            return None

    # --- per-user finance data (ADR 0029) --------------------------------------------------------

    async def set_user_snapshot(self, subject: str, snapshot: FinanceSnapshot) -> bool:
        """Store the user's own FinanceSnapshot (imported statement or manual entry), encrypted.
        Replaces any previous one. Returns True when committed to Postgres, False when no database is
        configured (process memory). Raises StoreUnavailable when the database write fails, and
        EncryptionKeyMissing (a StoreUnavailable) when TOKEN_ENCRYPTION_KEY is missing in live mode or
        prod: nothing is stored in plaintext."""
        return await self.user_snapshots.put(subject, snapshot.model_dump_json())

    async def get_user_snapshot(self, subject: str) -> FinanceSnapshot | None:
        try:
            raw = await self.user_snapshots.get(subject)
            return None if raw is None else FinanceSnapshot.model_validate_json(raw)
        except Exception:
            log.warning("user snapshot unreadable; ignoring it")
            return None

    async def delete_user_snapshot(self, subject: str) -> None:
        """Account deletion and demo reset. Raises StoreUnavailable when the Postgres delete fails
        (the API answers 503 and does not revoke the account)."""
        await self.user_snapshots.delete(subject)

    # --- context: news and rate decisions (ADR 0030) -----------------------------------------------

    async def news(self, start: date, end: date, topic: str = "rates", *, limit: int = 20) -> NewsResponse:
        """Guardian headlines for a topic and date range. Never raises. Never mock (both modes).

        Order: fresh cache -> live -> stale cache ("cached") -> NewsResponse(status="unavailable", items=[]).
        """
        if end < start:
            start, end = end, start
        limit = max(1, min(limit, 50))
        try:
            guardian_query(topic)
        except PayloadError:
            return NewsResponse(status="unavailable", items=[])
        ckey = f"lifeline:news:{topic.strip().lower()}:{start.isoformat()}:{end.isoformat()}:{limit}"
        ttl = SOURCES["guardian"].ttl_seconds
        try:
            entry = await self.cache.get_raw(ckey)
            if entry is not None and self._clock() - entry.stored_at < ttl:
                return NewsResponse(status="live", items=[NewsItem.model_validate(i) for i in entry.payload])
            key_error = self._missing_key_error("guardian")
            error = key_error or "offline mode"
            adapter = self.adapter("guardian") if self.live_enabled and key_error is None else None
            if isinstance(adapter, GuardianAdapter):
                try:
                    items = await adapter.search_guarded(topic, start, end, limit)
                except Exception as exc:
                    error = redact_urls(str(exc) or type(exc).__name__)
                else:
                    await self.cache.set_raw(ckey, [i.model_dump() for i in items], keep_seconds=7 * 24 * 3600)
                    await self._set_state("guardian", "live", None, utcnow())
                    return NewsResponse(status="live", items=items)
            if entry is not None:
                await self._set_state("guardian", "cached", error)
                return NewsResponse(status="cached", items=[NewsItem.model_validate(i) for i in entry.payload])
            await self._set_state("guardian", "unavailable", error)
        except Exception:
            log.exception("news failed")
        return NewsResponse(status="unavailable", items=[])

    @staticmethod
    def _latest_real(observations: list[Observation]) -> tuple[float, date] | None:
        """Newest UK-level value with status live or cached. Mock values never count (ADR 0060: never invented)."""
        real = [o for o in observations if o.status in ("live", "cached") and o.region is None]
        if not real:
            return None
        newest = max(real, key=lambda o: o.date)
        return newest.value, newest.date

    async def fx_rate(self, base: str, quote: str) -> tuple[float, date] | None:
        """(units of `quote` per 1 `base`, ECB reference date) from Frankfurter, e.g. fx_rate("CNY", "GBP").
        Cached 6 h (live -> Redis -> Postgres last-good). None for an unsupported code, the same currency
        twice, or when no live or cached rate exists. Never raises."""
        try:
            pair = fx_pair(base, quote)
        except AttributeError:
            return None
        if pair is None:
            return None
        return self._latest_real(await self.series("frankfurter", pair))

    async def cpi(self) -> tuple[float, date] | None:
        """(latest ONS CPI annual rate in percent, month) from series D7G7. None when only mock data exists."""
        return self._latest_real(await self.series("ons", "D7G7"))

    async def rate_decisions(self, today: date | None = None) -> RateDecisions:
        """Bank of England MPC rate-decision dates. Never raises. Never mock (both modes)."""
        today = today or date.today()
        ckey = "lifeline:boe-mpc:dates"
        ttl = SOURCES["boe-mpc"].ttl_seconds

        def answer(days: list[date], status: Status, note: str | None = None) -> RateDecisions:
            upcoming = [d for d in days if d >= today]
            listed = (upcoming or days)[:24]
            return RateDecisions(
                status=status,
                next_decision=upcoming[0].isoformat() if upcoming else None,
                dates=[d.isoformat() for d in listed],
                source=SourceRef(source="boe-mpc", series_id="mpc-dates", status=status, note=note),
            )

        try:
            entry = await self.cache.get_raw(ckey)
            if entry is not None and self._clock() - entry.stored_at < ttl:
                return answer([date.fromisoformat(d) for d in entry.payload], "live")
            error = "offline mode"
            adapter = self.adapter("boe-mpc") if self.live_enabled else None
            if isinstance(adapter, BoeMpcAdapter):
                try:
                    days = await adapter.dates_guarded()
                except Exception as exc:
                    error = redact_urls(str(exc) or type(exc).__name__)
                else:
                    await self.cache.set_raw(ckey, [d.isoformat() for d in days], keep_seconds=60 * 24 * 3600)
                    await self._set_state("boe-mpc", "live", None, utcnow())
                    return answer(days, "live")
            if entry is not None:
                await self._set_state("boe-mpc", "cached", error)
                return answer([date.fromisoformat(d) for d in entry.payload], "cached")
            await self._set_state("boe-mpc", "unavailable", error)
        except Exception:
            log.exception("rate decisions failed")
        return RateDecisions(
            status="unavailable",
            next_decision=None,
            dates=[],
            source=SourceRef(source="boe-mpc", series_id="mpc-dates", status="unavailable"),
        )

    # --- prediction inputs (ADR 0017) ----------------------------------------------------------

    async def bank_holidays(self, region: str | None) -> set[date]:
        """Bank holidays for the gov.uk division of `region` (None = England and Wales). Never raises.

        Order: fresh cache -> live gov.uk -> stale cache ("cached") -> recorded gov.uk copy.
        The recorded copy is real gov.uk data saved on 2026-10-17: "mock" in demo mode, "cached" in
        live mode (ADR 0027 allows cached real data).
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
            if self.live_mode:
                await self._set_state("bankholidays", "cached", f"{error}; recorded gov.uk copy from 2026-10-17")
            else:
                await self._set_state("bankholidays", "mock", error)
        except Exception:
            log.exception("bank holidays failed; using the recorded fixture")
        return set(fixture_bank_holidays().get(division, frozenset()))

    async def daily_weather(
        self, region: str | None, start: date, end: date, *, today: date | None = None
    ) -> list[dict[str, Any]]:
        """[{date, temp_max_c, rain_mm, status}] for every day in start..end. Never raises.

        Live days come from Open-Meteo (archive for older days, forecast for recent and future days).
        Demo mode: days the source cannot give (or every day, when it fails) are labelled mock.
        Live mode (ADR 0027): only real days are returned; missing days are left out (may be []).
        """
        if end < start:
            return []
        today = today or date.today()
        ckey = f"lifeline:weather:{region or 'uk'}:{start.isoformat()}:{end.isoformat()}"
        ttl = SOURCES["openmeteo"].ttl_seconds
        try:
            entry = await self.cache.get_raw(ckey)
            if entry is not None and self._clock() - entry.stored_at < ttl:
                return self._weather_rows(entry.payload, region, start, end, "live", self.live_mode)
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
                    return self._weather_rows(payload, region, start, end, "live", self.live_mode)
            if entry is not None:
                await self._set_state("openmeteo", "cached", error)
                return self._weather_rows(entry.payload, region, start, end, "cached", self.live_mode)
            await self._set_state("openmeteo", self.no_data, error)
        except Exception:
            log.exception("daily weather failed")
        return [] if self.live_mode else mock_daily_weather(region, start, end)

    @staticmethod
    def _weather_rows(
        payload: dict[str, Any], region: str | None, start: date, end: date, status: Status, real_only: bool = False
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        day = start
        while day <= end:
            hit = payload.get(day.isoformat())
            if hit is None:
                if not real_only:
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
        # Context sources (ADR 0030): one call each keeps their shared status and cache current.
        today = date.today()
        await self.rate_decisions(today)
        await self.news(today - timedelta(days=7), today, "rates")
        return await self.statuses()

    async def probe_postcodes(self) -> None:
        """One live postcodes.io lookup so the shared status reflects reality. Never raises."""
        if not self.live_enabled:
            return
        try:
            result = await self.postcodes_adapter().lookup(PROBE_POSTCODE)
        except Exception as exc:
            await self._set_state("postcodes", self.no_data, redact_urls(str(exc) or type(exc).__name__))
            return
        if result is None:
            await self._set_state("postcodes", self.no_data, "probe postcode not found")
        else:
            await self._set_state("postcodes", "live", None, utcnow())

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        await self.cache.aclose()
        await self.snapshots.aclose()
