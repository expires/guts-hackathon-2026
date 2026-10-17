from __future__ import annotations

from datetime import date

import pytest

from lifeline_contracts.accounts import Holding
from lifeline_contracts.finance import FinanceSnapshot
from lifeline_contracts.investing import ReturnSeries
from lifeline_contracts.macro import MacroTable
from lifeline_data.finance import DEMO_SUBJECT, fixture_snapshot
from lifeline_data.returns import load_returns
from lifeline_engine.money.text import unsupported_numbers
from lifeline_engine.next_move import KIND_ORDER, SPREAD_MIX, build_context, candidates, next_move
from lifeline_eval.isa_backtest import period_drawdowns

TODAY = date(2026, 10, 17)


def hold(name: str, value: float, asset_class: str = "equity", region: str | None = None) -> Holding:
    return Holding(instrument_id=name, name=name, quantity=1, value=value, asset_class=asset_class, region=region)  # type: ignore[arg-type]


def with_holdings(holdings: list[Holding]) -> FinanceSnapshot:
    return fixture_snapshot(DEMO_SUBJECT).model_copy(update={"holdings": holdings})


@pytest.fixture(scope="module")
def returns() -> ReturnSeries:
    return load_returns()


def spread_move(snap: FinanceSnapshot, macro: MacroTable, returns: ReturnSeries | None) -> object:
    ctx = build_context(snap, macro, TODAY, returns=returns)
    return next((c for c in candidates(ctx) if c.move.kind == "spread_isa"), None)


def test_kind_registered() -> None:
    assert "spread_isa" in KIND_ORDER


def test_concentrated_uk_equity_gets_spread_move(fixture_macro: MacroTable, returns: ReturnSeries) -> None:
    snap = with_holdings([hold("OneStock", 10_000, region="UK")])
    c = spread_move(snap, fixture_macro, returns)
    assert c is not None
    m = c.move  # type: ignore[attr-defined]
    assert m.kind == "spread_isa" and m.impact_per_year > 0 and m.worst_case_per_year <= 0
    assert m.concept_id == "diversification" and not m.testable and len(m.evidence) == 3
    for e in m.evidence:
        assert unsupported_numbers(e.text, e.facts) == []
    # evidence numbers trace to engine output
    mine = period_drawdowns({"uk_equity": 1.0}, returns)
    spread = period_drawdowns(SPREAD_MIX, returns)
    worst = max(mine, key=lambda p: (mine[p], p))
    assert m.evidence[1].facts["fell"] == round(mine[worst] * 100)
    assert m.evidence[1].facts["fell_spread"] == round(spread[worst] * 100)
    assert m.evidence[0].facts["top_share"] == 100
    assert [o.id for o in m.options] == ["spread", "keep"] and m.options[0].is_recommended
    assert 0 < m.confidence <= 1


def test_no_move_without_returns_or_when_spread(fixture_macro: MacroTable, returns: ReturnSeries) -> None:
    one = with_holdings([hold("OneStock", 10_000, region="UK")])
    assert spread_move(one, fixture_macro, None) is None
    spreadout = with_holdings([hold(f"H{i}", 1_000, region="UK") for i in range(10)])
    assert spread_move(spreadout, fixture_macro, returns) is None
    tiny = with_holdings([hold("OneStock", 500, region="UK")])
    assert spread_move(tiny, fixture_macro, returns) is None
    assert spread_move(with_holdings([]), fixture_macro, returns) is None


def test_next_move_valid_and_deterministic(fixture_macro: MacroTable, returns: ReturnSeries) -> None:
    snap = with_holdings([hold("OneStock", 200_000, region="UK")])
    a = next_move(snap, fixture_macro, TODAY, returns=returns)
    assert a == next_move(snap, fixture_macro, TODAY, returns=returns)
    kinds = [a.top.kind, *[r.kind for r in a.runners_up]]
    assert len(kinds) <= 3
    assert next_move(snap, fixture_macro, TODAY) is not None  # returns stay optional
