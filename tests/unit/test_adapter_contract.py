from datetime import date

import pytest

from playyourself.adapters.base import (
    Capability,
    FinanceAdapter,
    SourceHealth,
    UnsupportedCapability,
)
from playyourself.adapters.mock import MockAdapter, list_personas
from playyourself.domain.models import Balance, Holding, Transaction

SINCE = date(2025, 1, 1)


def test_all_personas_present():
    assert {"steady_saver", "subscription_creep", "volatile_spender", "concentrated_isa"} <= set(
        list_personas()
    )
    assert {"friend_alex", "friend_sam", "friend_priya", "friend_jordan"} <= set(list_personas())


@pytest.fixture(params=list_personas())
def adapter(request, fixed_today) -> FinanceAdapter:
    return MockAdapter("monzo", request.param, today=fixed_today)


async def test_satisfies_protocol_and_returns_models(adapter):
    assert isinstance(adapter, FinanceAdapter)
    txs = await adapter.get_transactions(SINCE)
    assert txs and all(isinstance(t, Transaction) for t in txs)
    assert all(t.ts.tzinfo is not None for t in txs)
    bals = await adapter.get_balances()
    assert bals and all(isinstance(b, Balance) for b in bals)
    hold = await adapter.get_holdings()
    assert hold and all(isinstance(h, Holding) for h in hold)
    assert isinstance(await adapter.health(), SourceHealth)


async def test_history_shape(adapter, fixed_today):
    txs = await adapter.get_transactions(SINCE)
    assert all(t.ts.date() <= fixed_today for t in txs)
    months = {(t.ts.year, t.ts.month) for t in txs}
    assert len(months) == 13
    assert any(t.category == "income" and t.amount_pence > 0 for t in txs)
    assert any(t.is_transfer and t.category == "savings" for t in txs)


async def test_deterministic(fixed_today):
    a = MockAdapter("monzo", "steady_saver", today=fixed_today, seed=3)
    b = MockAdapter("monzo", "steady_saver", today=fixed_today, seed=3)
    c = MockAdapter("monzo", "steady_saver", today=fixed_today, seed=4)
    assert await a.get_transactions(SINCE) == await b.get_transactions(SINCE)
    assert await a.get_transactions(SINCE) != await c.get_transactions(SINCE)


async def test_capability_enforced(fixed_today):
    m = MockAdapter("monzo", "steady_saver", frozenset({Capability.BALANCES}), today=fixed_today)
    with pytest.raises(UnsupportedCapability) as ei:
        await m.get_holdings()
    assert ei.value.code == "unavailable" and not ei.value.retryable
    with pytest.raises(UnsupportedCapability):
        await m.get_transactions(SINCE)


async def test_balance_kinds_by_name(fixed_today):
    t212 = MockAdapter("trading212", "steady_saver", today=fixed_today)
    monzo = MockAdapter("monzo", "steady_saver", today=fixed_today)
    assert {b.kind for b in await t212.get_balances()} == {"isa_cash"}
    assert {b.kind for b in await monzo.get_balances()} == {"current", "pot"}


async def test_subscription_creep_grows(fixed_today):
    m = MockAdapter("monzo", "subscription_creep", today=fixed_today)
    txs = await m.get_transactions(SINCE)
    subs = {
        "NETFLIX",
        "SPOTIFY",
        "DISNEY PLUS",
        "AMAZON PRIME",
        "APPLE ICLOUD",
        "PUREGYM",
        "HBO MAX",
        "AUDIBLE",
        "DELIVEROO PLUS",
        "NOW TV",
    }
    early = {t.merchant for t in txs if t.merchant in subs and t.ts.date() < date(2025, 12, 1)}
    late = {t.merchant for t in txs if t.merchant in subs and t.ts.date() >= date(2026, 8, 1)}
    assert len(late) > len(early)
