"""ADR 0042: every Next Move carries a trade-off. Per kind: presence, the facts rule, summary length."""

from __future__ import annotations

import math
from datetime import date
from typing import get_args

import pytest

from lifeline_contracts.macro import MacroTable
from lifeline_contracts.next_move import Move, MoveKind, NextMoveResponse, TradeOff
from lifeline_engine import trade_offs as to
from lifeline_engine.investments import (
    CONCENTRATION_LIMIT_PCT,
    Holding,
    concentration,
    own_risk,
    spread_score,
)
from lifeline_engine.money.text import unsupported_numbers
from lifeline_engine.next_move import build_context, candidates, next_move, option_policy

from .finance_builders import homeowner
from .test_next_move import _overspender, _renter

TODAY = date(2026, 10, 17)


def check(t: TradeOff | None) -> TradeOff:
    assert t is not None
    assert 1 <= len(t.points) <= 4
    assert len(t.summary) <= to.SUMMARY_MAX, t.summary
    assert "—" not in t.summary
    all_facts = {f"{i}_{k}": v for i, p in enumerate(t.points) for k, v in p.facts.items()}
    assert unsupported_numbers(t.summary, all_facts) == [], t.summary
    for p in t.points:
        assert "—" not in p.text
        assert unsupported_numbers(p.text, p.facts) == [], p.text
    return t


# ---------- one test per move kind, built directly ----------


def _fix() -> TradeOff:
    return to.mortgage("fix_5y", 180_000, 4.98, 2027, 5, 98.0, "the 2021-2023 rate shock",
                       {"stress_start": 2021.0, "stress_end": 2023.0}, 0.25, 5.25)


def _tracker() -> TradeOff:
    return to.mortgage("tracker", 180_000, 4.23, 2027, None, 103.0, "the 2021-2023 rate shock",
                       {"stress_start": 2021.0, "stress_end": 2023.0}, 0.25, 5.25)


def _built(kind: MoveKind) -> TradeOff:
    match kind:
        case "fix_mortgage":
            return _fix()
        case "remortgage":
            return _tracker()
        case "move_savings":
            return to.move_savings(4.5, (2008, 5.0, 2.5))
        case "cancel_subscription":
            return to.cancel_subscription("Netflix", 13.99, "a month", 13.99)
        case "switch_subscription":
            return to.switch_subscription("Netflix", 5.0)
        case "switch_energy":
            return to.switch_energy(142.0, 1, 5)
        case "pay_off_debt":
            return to.pay_off_debt("savings", 3400, 0.0, 3400, 1.8, 1.25, 24.7)
        case "build_emergency_fund":
            return to.emergency_fund(4950, 1.5, 8.77, 1990, 2026)
        case "cut_budget":
            return to.cut_budget("groceries", 165, 402, 2, 6)
        case "spread_investments":
            return to.spread_investments("Nvidia", 62.0, 4400, 40.0)
    raise AssertionError(kind)


@pytest.mark.parametrize("kind", get_args(MoveKind))
def test_trade_off_per_kind(kind: MoveKind) -> None:
    t = check(_built(kind))
    assert t.summary and not t.summary[0].islower()


def test_fix_trade_off_uses_real_inputs() -> None:
    t = _fix()
    # ERC 1% to 5% of £180,000 = £1,800 to £9,000. Fixed for 5 years from 2027: until 2032.
    assert t.summary == "Fixed until 2032: a fee to leave early, and no gain if rates fall"
    assert t.points[0].text == (
        "Leaving before 2032 usually costs 1% to 5% of what you owe: £1,800 to £9,000 on £180,000."
    )
    assert t.points[1].text == "If rates fall, you still pay 4.98% until 2032."
    assert t.points[0].source is not None and t.points[0].source.series_id == "mortgage_erc_pct"


def test_trade_off_rules_reject_bad_text() -> None:
    with pytest.raises(ValueError):
        to.point("You pay £12 a month.", {})
    with pytest.raises(ValueError):
        to.make("x" * 91, [to.point("ok", {})])
    with pytest.raises(ValueError):
        to.make("Fee of £50", [to.point("ok", {})])


def test_typical_table_has_sources() -> None:
    for t in to.TYPICAL.values():
        assert t.source and t.low <= t.high


# ---------- every engine move carries a trade-off ----------


def _moves(r: NextMoveResponse) -> list[Move]:
    return [r.top, *r.runners_up]


def _personas() -> list:  # type: ignore[type-arg]
    snaps = [homeowner(), _renter(), _overspender()]
    try:
        from lifeline_data import finance
    except ImportError:
        return snaps
    return snaps + [
        finance.fixture_snapshot(f"persona:{p}")
        for p in ("homeowner-leeds", "renter-saver-london", "subscription-creep-manchester", "overspender-bristol")
    ]


def test_every_candidate_has_trade_off(macro: MacroTable) -> None:
    seen: set[str] = set()
    for snap in _personas():
        for c in candidates(build_context(snap, macro, TODAY)):
            check(c.move.trade_off)
            seen.add(c.move.kind)
            if c.move.kind == "build_emergency_fund":
                assert c.move.gain_kind == "months_of_cover" and c.move.cover_months == 3.0
            else:
                assert c.move.gain_kind == "gbp_per_year" and c.move.cover_months is None
        for m in _moves(next_move(snap, macro, TODAY)):
            check(m.trade_off)
    assert {"fix_mortgage", "move_savings", "pay_off_debt", "cut_budget", "switch_energy"} <= seen


def test_fallback_has_trade_off_and_cover(macro: MacroTable) -> None:
    from lifeline_contracts.finance import Account

    from .finance_builders import monthly, snapshot

    accounts = [Account(id="cur", name="Current", kind="current", provider="B", balance=30_000.0)]
    r = next_move(snapshot(monthly("2025-11-28", 11, 3000.0, "ACME SALARY"), accounts), macro, TODAY)
    check(r.top.trade_off)
    assert r.top.gain_kind == "months_of_cover" and r.top.cover_months is not None


def test_demo_top_trade_off(macro: MacroTable) -> None:
    top = next_move(homeowner(), macro, TODAY).top
    t = check(top.trade_off)
    if top.options[0].id.startswith("fix_"):
        assert t.summary.startswith("Fixed until")
    else:
        assert t.summary == "Your payment goes up if Bank Rate goes up"


# ---------- spread_investments ----------


def test_concentration_hand_case() -> None:
    # Total £10,000; largest £6,200 = 62%. Move 6,200 - 0.4 * 10,000 = £2,200.
    c = concentration([Holding("Nvidia", 6200), Holding("VWRL", 3000), Holding("Cash", 800)])
    assert c is not None
    assert (c.name, c.share_pct, c.total) == ("Nvidia", 62.0, 10_000)
    assert c.moved == pytest.approx(2200)
    assert concentration([Holding("A", 4000), Holding("B", 6000), Holding("C", 5000)]) is None  # 40% exactly
    assert concentration([Holding("A", 500)]) is None  # under MIN_ISA_VALUE
    assert concentration([]) is None


def test_spread_score_hand_case() -> None:
    # D^2 = 0.35^2 - 0.15^2 = 0.1; impact = 2200 * 0.1 / 2 = £110 a year.
    d = own_risk()
    assert d * d == pytest.approx(0.1)
    s = spread_score(2200)
    assert s.impact_per_year == pytest.approx(110.0)
    assert s.worst_case_per_year == pytest.approx(-2200 * 1.28 * math.sqrt(0.1))
    # P = Phi(sqrt(0.1) * sqrt(5) / 2) = Phi(0.3536) ~ 0.638
    assert s.confidence == pytest.approx(0.638, abs=1e-3)


def test_spread_move_from_holdings(macro: MacroTable) -> None:
    holdings = [Holding("NVIDIA 2", 6200), Holding("Vanguard FTSE All-World", 3000), Holding("Cash", 800)]
    ctx = build_context(homeowner(), macro, TODAY, holdings=holdings)
    moves = [c.move for c in candidates(ctx) if c.move.kind == "spread_investments"]
    assert len(moves) == 1
    m = moves[0]
    check(m.trade_off)
    assert m.trade_off is not None and len(m.trade_off.summary) <= 90
    assert m.headline == "NVIDIA is 62% of your ISA"  # digits stripped from the untrusted name
    assert m.concept_id == "diversification" and not m.testable
    assert f"{CONCENTRATION_LIMIT_PCT:g}%" in m.evidence[2].text
    for e in m.evidence:
        assert unsupported_numbers(e.text, e.facts) == []
    with pytest.raises(ValueError):
        option_policy(m, "spread")
    # No holdings: no spread move.
    assert all(c.move.kind != "spread_investments" for c in candidates(build_context(homeowner(), macro, TODAY)))
