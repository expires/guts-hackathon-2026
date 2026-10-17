"""Concurrent fetch with timeouts, bounded retries, record counting and stale-cache fallback."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from playyourself.adapters.base import Capability, FinanceAdapter, SourceError
from playyourself.adapters.credentials import CredentialStore
from playyourself.domain.models import (
    Balance,
    Holding,
    Snapshot,
    SourceStatus,
    Transaction,
)
from playyourself.settings import Settings

log = logging.getLogger(__name__)

T = TypeVar("T")
BACKOFF_BASE_S = 0.2


class _Portion(BaseModel):
    """One adapter's contribution to a snapshot; also the on-disk cache format."""

    as_of: datetime
    balances: list[Balance] = []
    transactions: list[Transaction] = []
    holdings: list[Holding] = []
    dropped: int = 0


async def _call[T](fn: Callable[[], Awaitable[T]], timeout_s: float, max_retries: int) -> T:
    attempt = 0
    while True:
        try:
            try:
                return await asyncio.wait_for(fn(), timeout_s)
            except TimeoutError as exc:
                raise SourceError(
                    "timeout", f"no response in {timeout_s}s", retryable=True
                ) from exc
        except SourceError as err:
            if not err.retryable or attempt >= max_retries:
                raise
            delay = err.retry_after if err.retry_after is not None else BACKOFF_BASE_S * 2**attempt
            attempt += 1
            await asyncio.sleep(delay)


async def _fetch_portion(
    adapter: FinanceAdapter, since: date, timeout_s: float, max_retries: int
) -> _Portion:
    caps = adapter.capabilities
    portion = _Portion(as_of=datetime.now(UTC))
    dropped = 0
    # Sequential per adapter so `last_dropped` is unambiguous; adapters run concurrently.
    if Capability.BALANCES in caps:
        portion.balances = await _call(adapter.get_balances, timeout_s, max_retries)
        dropped += getattr(adapter, "last_dropped", 0)
    if Capability.TRANSACTIONS in caps:
        portion.transactions = await _call(
            lambda: adapter.get_transactions(since), timeout_s, max_retries
        )
        dropped += getattr(adapter, "last_dropped", 0)
    if Capability.HOLDINGS in caps:
        portion.holdings = await _call(adapter.get_holdings, timeout_s, max_retries)
        dropped += getattr(adapter, "last_dropped", 0)
    portion.dropped = dropped
    return portion


def _cache_name(adapter: FinanceAdapter) -> str:
    """Cache files are keyed so that mock data can never be served as a live user's data."""
    return getattr(adapter, "cache_key", adapter.name)


def _status_mode(adapter: FinanceAdapter) -> str | None:
    return getattr(adapter, "mode", None)


def _cache_path(cache_dir: Path, name: str) -> Path:
    return cache_dir / f"{name}.json"


def _write_cache(cache_dir: Path, name: str, portion: _Portion) -> None:
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        _cache_path(cache_dir, name).write_text(portion.model_dump_json())
    except OSError:
        log.warning("could not write cache for %s", name)


def _read_cache(cache_dir: Path | None, name: str) -> _Portion | None:
    if cache_dir is None:
        return None
    try:
        return _Portion.model_validate_json(_cache_path(cache_dir, name).read_text())
    except (OSError, ValidationError):
        return None


async def _fetch_one(
    adapter: FinanceAdapter,
    since: date,
    timeout_s: float,
    max_retries: int,
    cache_dir: Path | None,
) -> tuple[_Portion, SourceStatus]:
    try:
        portion = await _fetch_portion(adapter, since, timeout_s, max_retries)
    except SourceError as err:
        code, message = err.code, err.message
    except Exception as err:  # never let one source take down the snapshot
        log.exception("unexpected error from %s", adapter.name)
        code, message = "unavailable", str(err)
    else:
        if cache_dir is not None:
            _write_cache(cache_dir, _cache_name(adapter), portion)
        return portion, SourceStatus(
            name=adapter.name,
            ok=True,
            as_of=portion.as_of,
            dropped=portion.dropped,
            mode=_status_mode(adapter),
        )

    cached = _read_cache(cache_dir, _cache_name(adapter))
    if cached is not None:
        return cached, SourceStatus(
            name=adapter.name,
            ok=False,
            stale=True,
            as_of=cached.as_of,
            error_code=code,
            error_message=message,
            dropped=cached.dropped,
            mode=_status_mode(adapter),
        )
    return _Portion(as_of=datetime.now(UTC)), SourceStatus(
        name=adapter.name,
        ok=False,
        error_code=code,
        error_message=message,
        mode=_status_mode(adapter),
    )


async def fetch_snapshot(
    adapters: list[FinanceAdapter],
    since: date,
    timeout_s: float,
    max_retries: int,
    cache_dir: Path | None,
) -> Snapshot:
    results = await asyncio.gather(
        *(_fetch_one(a, since, timeout_s, max_retries, cache_dir) for a in adapters)
    )
    balances: list[Balance] = []
    transactions: list[Transaction] = []
    holdings: list[Holding] = []
    sources: dict[str, SourceStatus] = {}
    for portion, status in results:
        balances += portion.balances
        transactions += portion.transactions
        holdings += portion.holdings
        sources[status.name] = status
    transactions.sort(key=lambda t: t.ts)
    return Snapshot(
        balances=balances,
        transactions=transactions,
        holdings=holdings,
        sources=sources,
        as_of=datetime.now(UTC),
    )


def effective_modes(settings: Settings, store: CredentialStore) -> dict[str, str]:
    """Per source: "live" if the store holds credentials or the mode is live, else "demo"."""
    return {
        "monzo": "live"
        if store.has_credentials("monzo") or settings.monzo_mode == "live"
        else "demo",
        "trading212": (
            "live"
            if store.has_credentials("trading212") or settings.t212_mode == "live"
            else "demo"
        ),
    }


def build_adapters(
    settings: Settings, store: CredentialStore, client: httpx.AsyncClient | None = None
) -> list[FinanceAdapter]:
    """Monzo mock: current/pot balances + transactions. T212 mock: isa_cash balance + holdings
    (MockAdapter picks balance kinds from the adapter name; see mock.py)."""
    from playyourself.adapters.mock import MockAdapter
    from playyourself.adapters.monzo import MonzoAdapter
    from playyourself.adapters.monzo_history import MonzoHistory
    from playyourself.adapters.monzo_oauth import refresh_access_token
    from playyourself.adapters.trading212 import Trading212Adapter

    modes = effective_modes(settings, store)
    adapters: list[FinanceAdapter] = []
    if modes["monzo"] == "live":
        creds = store.resolve("monzo") or {}
        refresher = None
        if creds.get("refresh_token"):

            async def refresher() -> str | None:
                return await refresh_access_token(settings, store, client)

        adapters.append(
            MonzoAdapter(
                settings,
                client,
                token=creds.get("access_token"),
                refresher=refresher,
                history=MonzoHistory(settings.credentials_dir),
            )
        )
    else:
        adapters.append(
            MockAdapter(
                name="monzo",
                persona=settings.mock_persona,
                capabilities=frozenset({Capability.BALANCES, Capability.TRANSACTIONS}),
            )
        )
    if modes["trading212"] == "live":
        creds = store.resolve("trading212") or {}
        adapters.append(
            Trading212Adapter(
                settings,
                client,
                api_key=creds.get("api_key"),
                api_secret=creds.get("api_secret"),
            )
        )
    else:
        adapters.append(
            MockAdapter(
                name="trading212",
                persona=settings.mock_persona,
                capabilities=frozenset({Capability.HOLDINGS, Capability.BALANCES}),
            )
        )
    return adapters
