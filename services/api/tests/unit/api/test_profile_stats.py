"""Profile stats: per-source connections and sections built only from the user's data (offline)."""

from __future__ import annotations

from datetime import date

import pytest

from lifeline_api import onboarding, profile_stats, samples
from lifeline_contracts.accounts import Holding, ProviderConnection
from lifeline_contracts.finance import Account, FinanceSnapshot
from lifeline_contracts.profile import ProfileStats

TODAY = date(2026, 10, 18)


def providers(monzo: bool = False, t212: bool = False) -> list[ProviderConnection]:
    def one(name: str, on: bool) -> ProviderConnection:
        return ProviderConnection(provider=name, connected=on, data_status="live" if on else "mock")  # type: ignore[arg-type]

    return [one("monzo", monzo), one("trading212", t212)]


def holding(name: str, value: float, cls: str = "equity") -> Holding:
    return Holding(instrument_id=name, name=name, quantity=1, value=value, asset_class=cls)  # type: ignore[arg-type]


def t212_snap(holdings: list[Holding]) -> FinanceSnapshot:
    return FinanceSnapshot(
        status="live", source="trading212", as_of="2026-10-17",
        accounts=[Account(id="t212-1", name="Trading 212 Stocks & Shares", kind="isa", provider="trading212",
                          balance=1500.0)],
        transactions=[], holdings=holdings,
    )


def sections(stats: ProfileStats) -> dict[str, object]:
    return {s.id: s for s in stats.sections}


def sample_snap() -> FinanceSnapshot:
    snap = samples.load("working")
    assert snap is not None
    return snap


def test_nothing_connected_everything_unavailable_with_hints() -> None:
    stats = profile_stats.build(None, None, providers())
    assert [c.id for c in stats.connections] == ["monzo", "trading212", "statement", "manual", "sample"]
    assert not any(c.connected for c in stats.connections)
    assert [s.id for s in stats.sections] == ["habits", "spending", "net_worth", "investments"]
    for s in stats.sections:
        assert not s.available and s.missing_hint and s.habits is None and s.spending is None
    assert "Connect Monzo" in stats.sections[0].missing_hint  # type: ignore[operator]


def test_trading212_only_has_investments_and_net_worth_but_no_habits_or_spending() -> None:
    snap = t212_snap([holding("A", 900), holding("B", 300), holding("Gilt", 100, "bond")])
    stats = profile_stats.build(snap, snap, providers(t212=True))
    sec = sections(stats)
    assert not sec["habits"].available and "Connect Monzo" in sec["habits"].missing_hint  # type: ignore[attr-defined]
    assert not sec["spending"].available  # type: ignore[attr-defined]
    nw = sec["net_worth"].net_worth  # type: ignore[attr-defined]
    assert (nw.net_worth, nw.cash, nw.investments, nw.other) == (1500.0, 0, 1500.0, 0)
    inv = sec["investments"].investments  # type: ignore[attr-defined]
    assert inv.total_value == 1500.0 and inv.invested_value == 1300.0 and inv.holdings_count == 3
    assert [h.name for h in inv.top_holdings] == ["A", "B", "Gilt"]
    assert [(m.asset_class, m.share_pct) for m in inv.mix] == [("equity", 92.3), ("bond", 7.7)]
    t = {c.id: c for c in stats.connections}["trading212"]
    assert t.connected and t.data_status == "live" and t.provides == "3 holdings"


def test_trading212_without_positions_says_so_and_invents_nothing() -> None:
    snap = t212_snap([])
    inv = profile_stats.build(snap, snap, providers(t212=True)).sections[3]
    assert inv.available and inv.investments is not None
    assert inv.investments.holdings_count == 0 and inv.investments.invested_value is None
    assert inv.investments.mix == [] and inv.investments.note


def test_monzo_user_has_habits_and_spending_from_engine() -> None:
    snap = sample_snap().model_copy(update={"status": "live", "source": "monzo", "persona": None})
    stats = profile_stats.build(snap, snap, providers(monzo=True))
    sec = sections(stats)
    habits, spend = sec["habits"], sec["spending"]
    assert habits.available and habits.sources == ["monzo"] and habits.habits is not None  # type: ignore[attr-defined]
    s = spend.spending  # type: ignore[attr-defined]
    assert spend.available and 1 <= len(s.top_categories) <= 3 and s.monthly_out > 0 and not s.partial  # type: ignore[attr-defined]
    assert s.top_categories == sorted(s.top_categories, key=lambda c: -c.amount)
    m = {c.id: c for c in stats.connections}["monzo"]
    assert m.provides and m.provides.startswith("Transactions since ") and m.data_status == "live"
    assert not sec["investments"].available  # type: ignore[attr-defined]


def test_sample_user_is_labelled_sample_data() -> None:
    snap = sample_snap()
    stats = profile_stats.build(snap, snap, providers())
    c = {x.id: x for x in stats.connections}
    assert c["sample"].connected and c["sample"].data_status == "mock" and c["sample"].label == "Sample data"
    assert not c["monzo"].connected and not c["statement"].connected
    assert sections(stats)["habits"].sources == ["sample"]  # type: ignore[attr-defined]


def test_habits_need_two_full_months() -> None:
    snap = sample_snap()
    short = snap.model_copy(update={"transactions": [t for t in snap.transactions if t.date >= "2026-09-01"]})
    sec = profile_stats.build(short, short, providers()).sections[0]
    assert not sec.available and sec.missing_hint and "full months" in sec.missing_hint


def test_typed_in_numbers_are_not_transactions_for_habits() -> None:
    synthetic = snap = sample_snap().model_copy(update={"source": "manual"})
    synthetic = snap.model_copy(update={"transactions": [
        t.model_copy(update={"provider_category": onboarding.USER_ENTERED}) for t in snap.transactions]})
    sec = profile_stats.build(synthetic, synthetic, providers()).sections[0]
    assert not sec.available


@pytest.mark.parametrize("n", [1, 2])
def test_holding_count_text(n: int) -> None:
    assert profile_stats._holdings_text(n) == ("1 holding" if n == 1 else "2 holdings")


def test_statement_merge_keeps_statement_when_trading212_connects_and_on_disconnect() -> None:
    stmt = sample_snap().model_copy(update={"source": "statement", "status": "live", "persona": None})
    merged = onboarding.merge_statement(stmt, t212_snap([holding("A", 900)]))
    assert merged.source == "statement" and len(merged.transactions) == len(stmt.transactions)
    assert len(merged.holdings) == 1 and any(a.provider == "trading212" for a in merged.accounts)
    # a new statement upload keeps the connected positions
    again = onboarding.merge_statement(merged, stmt)
    assert len(again.holdings) == 1 and any(a.provider == "trading212" for a in again.accounts)
    stripped = onboarding.without_trading212(merged)
    assert stripped.holdings == [] and not any(a.provider == "trading212" for a in stripped.accounts)
