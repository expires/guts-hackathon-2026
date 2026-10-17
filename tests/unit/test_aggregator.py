import time
from datetime import date

import pytest

from playyourself.adapters import aggregator
from playyourself.adapters.aggregator import build_adapters, fetch_snapshot
from playyourself.adapters.base import Capability, FinanceAdapter, SourceError, SourceHealth
from playyourself.adapters.credentials import CredentialStore
from playyourself.adapters.mock import MockAdapter
from playyourself.settings import Settings

SINCE = date(2025, 1, 1)
BAL = frozenset({Capability.BALANCES})


class Flaky:
    """Fake adapter failing `failures` times with `error` before succeeding."""

    last_dropped = 0

    def __init__(self, failures: int, error: SourceError | None = None, name="flaky"):
        self.name = name
        self.capabilities = BAL
        self.failures = failures
        self.error = error or SourceError("unavailable", "boom", retryable=True)
        self.calls = 0

    async def get_balances(self):
        from playyourself.domain.models import Balance

        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return [Balance(account_id="x", kind="current", value_pence=1)]

    async def get_transactions(self, since):
        raise AssertionError("not in capabilities")

    async def get_holdings(self):
        raise AssertionError("not in capabilities")

    async def health(self):
        return SourceHealth(name=self.name, ok=True)


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setattr(aggregator, "BACKOFF_BASE_S", 0.01)


def mocks(today, **slow_kwargs):
    return [
        MockAdapter(
            "monzo",
            "steady_saver",
            frozenset({Capability.BALANCES, Capability.TRANSACTIONS}),
            today=today,
            **slow_kwargs,
        ),
        MockAdapter(
            "trading212",
            "steady_saver",
            frozenset({Capability.HOLDINGS, Capability.BALANCES}),
            today=today,
        ),
    ]


async def test_merges_sources(snapshot_for):
    snap = await snapshot_for("steady_saver")
    assert snap.sources["monzo"].ok and snap.sources["trading212"].ok
    assert not snap.stale
    assert snap.transactions and snap.holdings
    assert {b.kind for b in snap.balances} == {"current", "pot", "isa_cash"}
    assert snap.isa_value_pence > 0


async def test_concurrent_and_timeout_isolated(fixed_today):
    adapters = mocks(fixed_today)
    adapters[0].latency_ms = 1000
    start = time.perf_counter()
    snap = await fetch_snapshot(adapters, SINCE, 0.1, 0, None)
    assert time.perf_counter() - start < 0.8
    assert not snap.sources["monzo"].ok
    assert snap.sources["monzo"].error_code == "timeout"
    assert snap.sources["trading212"].ok and snap.holdings


async def test_concurrency_overlaps(fixed_today):
    adapters = mocks(fixed_today)
    for a in adapters:
        a.latency_ms = 150
    start = time.perf_counter()
    await fetch_snapshot(adapters, SINCE, 5, 0, None)
    # monzo: 2 sequential calls (300ms); trading212: 2 calls (300ms); overlapped, not 600ms
    assert time.perf_counter() - start < 0.55


async def test_retry_succeeds(fixed_today):
    f = Flaky(2)
    snap = await fetch_snapshot([f], SINCE, 1, 2, None)
    assert snap.sources["flaky"].ok and f.calls == 3


async def test_retry_exhausted(fixed_today):
    f = Flaky(10)
    snap = await fetch_snapshot([f], SINCE, 1, 2, None)
    assert not snap.sources["flaky"].ok and f.calls == 3
    assert snap.sources["flaky"].error_code == "unavailable"


async def test_non_retryable_not_retried():
    f = Flaky(10, SourceError("auth", "nope", retryable=False))
    snap = await fetch_snapshot([f], SINCE, 1, 3, None)
    assert f.calls == 1 and snap.sources["flaky"].error_code == "auth"


async def test_retry_after_respected(monkeypatch):
    sleeps = []
    real = aggregator.asyncio.sleep

    async def fake_sleep(d):
        sleeps.append(d)
        await real(0)

    monkeypatch.setattr(aggregator.asyncio, "sleep", fake_sleep)
    f = Flaky(1, SourceError("rate_limited", "slow", retryable=True, retry_after=0.7))
    await fetch_snapshot([f], SINCE, 1, 1, None)
    assert sleeps == [0.7]


async def test_stale_cache_fallback(fixed_today, tmp_path):
    cache = tmp_path / "c"
    good = await fetch_snapshot(mocks(fixed_today), SINCE, 5, 0, cache)
    assert (cache / "monzo-mock-steady_saver.json").exists()
    adapters = mocks(fixed_today, fail_rate=1.0)
    snap = await fetch_snapshot(adapters, SINCE, 5, 0, cache)
    st = snap.sources["monzo"]
    assert st.stale and not st.ok and st.error_code == "unavailable"
    assert st.as_of == good.sources["monzo"].as_of
    assert snap.stale
    assert len(snap.transactions) == len(good.transactions)
    assert not snap.sources["trading212"].stale


async def test_failure_without_cache_is_empty(fixed_today, tmp_path):
    snap = await fetch_snapshot(mocks(fixed_today, fail_rate=1.0), SINCE, 5, 0, tmp_path)
    st = snap.sources["monzo"]
    assert not st.ok and not st.stale
    assert snap.transactions == [] and snap.holdings


async def test_dropped_counts_surface(fixed_today):
    snap = await fetch_snapshot(mocks(fixed_today, corrupt_rate=0.3), SINCE, 5, 0, None)
    assert snap.sources["monzo"].dropped > 0
    assert snap.sources["trading212"].dropped == 0
    assert snap.sources["monzo"].ok


def test_build_adapters_mock():
    s = Settings(_env_file=None)
    ads = build_adapters(s, CredentialStore())
    assert [a.name for a in ads] == ["monzo", "trading212"]
    assert all(isinstance(a, FinanceAdapter) for a in ads)


class AlwaysFailsLive:
    name = "monzo"
    mode = "live"
    cache_key = "monzo-live"
    capabilities = frozenset({Capability.BALANCES})
    last_dropped = 0

    async def get_balances(self):
        raise SourceError("auth", "rejected")


async def test_live_failure_never_falls_back_to_mock_cache(fixed_today, tmp_path):
    cache = tmp_path / "c"
    await fetch_snapshot(mocks(fixed_today), SINCE, 5, 0, cache)  # writes mock cache for monzo
    assert (cache / "monzo-mock-steady_saver.json").exists()
    snap = await fetch_snapshot([AlwaysFailsLive()], SINCE, 5, 0, cache)
    st = snap.sources["monzo"]
    assert not st.ok and not st.stale and st.error_code == "auth" and st.mode == "live"
    assert snap.balances == [] and snap.transactions == []


async def test_mock_cache_keyed_by_persona(fixed_today, tmp_path):
    cache = tmp_path / "c"
    await fetch_snapshot(mocks(fixed_today), SINCE, 5, 0, cache)
    other = MockAdapter(
        "monzo",
        "volatile_spender",
        frozenset({Capability.BALANCES}),
        today=fixed_today,
        fail_rate=1.0,
    )
    snap = await fetch_snapshot([other], SINCE, 5, 0, cache)
    assert not snap.sources["monzo"].stale
