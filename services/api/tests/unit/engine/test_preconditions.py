"""ADR 0053 bugs 1, 3, 4, 5, 6 and 9: preconditions per move kind, no invented fields, confidence with sample,
months of cover only with known costs, interest only with a known rate, and the tracker figure by hand."""

from __future__ import annotations

from datetime import date

import pytest

from lifeline_contracts.finance import Account, EnergyDetails, FinanceSnapshot, MortgageDetails
from lifeline_contracts.macro import MacroTable
from lifeline_engine import preconditions as pre
from lifeline_engine.money.profile import known_monthly_costs, months_of_cover, personal_facts
from lifeline_engine.next_move import build_context, candidates, next_move
from lifeline_engine.wording import confidence_level, with_sample

from .finance_builders import homeowner, monthly, snapshot, tx

TODAY = date(2026, 10, 17)


def _bare(accounts: list[Account] | None = None, **kw: object) -> FinanceSnapshot:
    """Salary only: no costs, no savings, no debt, no mortgage, no energy, no subscriptions."""
    return snapshot(monthly("2025-11-28", 11, 2000.0, "ACME SALARY"), accounts, **kw)  # type: ignore[arg-type]


def _kinds(snap: FinanceSnapshot, macro: MacroTable) -> set[str]:
    return {c.move.kind for c in candidates(build_context(snap, macro, TODAY))}


def _fixed(until: str | None) -> MortgageDetails:
    return MortgageDetails(balance=150_000, rate_pct=4.0, rate_type="fixed", fixed_until=until, years_left=20,
                           property_value=250_000, monthly_payment=900)


# ---------- one test per kind: holds with the data, fails without it ----------


def test_fix_mortgage_precondition() -> None:
    assert pre.fix_mortgage(_bare(mortgage=_fixed("2027-03-31")), TODAY)
    assert not pre.fix_mortgage(_bare(), TODAY)  # no mortgage
    assert not pre.fix_mortgage(_bare(mortgage=_fixed(None)), TODAY)  # deal end date unknown: never invented
    assert not pre.fix_mortgage(_bare(mortgage=_fixed("2029-01-01")), TODAY)  # more than 365 days away


def test_remortgage_precondition() -> None:
    var = MortgageDetails(balance=150_000, rate_pct=7.5, rate_type="variable", years_left=20, property_value=250_000,
                          monthly_payment=1200)
    assert pre.remortgage(_bare(mortgage=var), TODAY)
    assert pre.remortgage(_bare(mortgage=_fixed("2026-01-01")), TODAY)  # deal ended
    assert not pre.remortgage(_bare(mortgage=_fixed(None)), TODAY)
    assert not pre.remortgage(_bare(), TODAY)


def test_move_savings_precondition() -> None:
    sav = [Account(id="cur", name="C", kind="current", provider="B", balance=100.0),
           Account(id="sav", name="S", kind="savings", provider="B", balance=5_000.0)]
    assert pre.move_savings(_bare(sav), TODAY)
    assert not pre.move_savings(_bare(), TODAY)


def test_cancel_subscription_precondition() -> None:
    txs = [*monthly("2025-11-28", 11, 2000.0, "ACME SALARY"),
           *monthly("2025-11-09", 12, [-12.99] * 7 + [-13.99] * 5, "NETFLIX.COM", "Netflix")]
    assert pre.cancel_subscription(snapshot(txs), TODAY)
    assert not pre.cancel_subscription(_bare(), TODAY)


def test_switch_subscription_never_offered() -> None:
    assert not pre.met("switch_subscription", homeowner(), TODAY)


def test_spread_investments_deprecated(macro: MacroTable) -> None:
    assert not pre.met("spread_investments", homeowner(), TODAY)
    assert "spread_investments" not in _kinds(homeowner(), macro)


def test_switch_energy_precondition() -> None:
    def e(tariff: str, until: str | None) -> FinanceSnapshot:
        return _bare(energy=EnergyDetails(supplier="X", tariff=tariff, monthly_cost=90.0, fixed_until=until))

    assert pre.switch_energy(e("Flexible", None), TODAY)  # variable tariff
    assert pre.switch_energy(e("Fixed 12m", "2026-11-30"), TODAY)  # deal ends in 44 days
    assert not pre.switch_energy(e("Fixed 12m", None), TODAY)  # fixed, end date unknown: never invented
    assert not pre.switch_energy(e("Fixed 12m", "2027-06-30"), TODAY)
    assert not pre.switch_energy(_bare(), TODAY)


def test_pay_off_debt_precondition() -> None:
    card = [Account(id="cur", name="C", kind="current", provider="B", balance=100.0),
            Account(id="card", name="Card", kind="credit", provider="V", balance=-900.0)]
    assert pre.pay_off_debt(_bare(card), TODAY)
    assert not pre.pay_off_debt(_bare(), TODAY)


def test_build_emergency_fund_precondition() -> None:
    txs = [*monthly("2025-11-28", 11, 2000.0, "ACME SALARY"), *monthly("2025-11-01", 12, -900.0, "RENT LETTINGS")]
    assert pre.build_emergency_fund(snapshot(txs), TODAY)  # £1,000 cash < 3 x £900
    assert not pre.build_emergency_fund(_bare(), TODAY)  # no costs known


def test_cut_budget_precondition() -> None:
    txs = [tx("2026-06-01", -60.0, "TESCO", "Tesco"), tx("2026-09-10", -60.0, "TESCO", "Tesco")]
    assert pre.cut_budget(snapshot(txs), TODAY)
    part = [tx("2026-08-17", -60.0, "TESCO", "Tesco"), tx("2026-09-10", -60.0, "TESCO", "Tesco")]
    assert not pre.cut_budget(snapshot(part), TODAY)  # August is a part month: no usual amount to compare
    assert not pre.cut_budget(_bare(), TODAY)


def test_bare_snapshot_gets_no_moves(macro: MacroTable) -> None:
    """Salary only: no kind's precondition holds, so only the fallback is shown."""
    assert _kinds(_bare(), macro) == set()
    r = next_move(_bare(), macro, TODAY)
    assert r.top.impact_per_year == 0 and r.runners_up == []


def test_every_offered_move_meets_its_precondition(macro: MacroTable) -> None:
    for snap in (homeowner(), _bare()):
        for c in candidates(build_context(snap, macro, TODAY)):
            assert pre.met(c.move.kind, snap, TODAY), c.move.kind


# ---------- confidence level and sample (bug 4) ----------


@pytest.mark.parametrize(
    ("share", "sample", "level"),
    [(0.8, 8, "high"), (0.8, 7, "medium"), (0.69, 20, "medium"), (0.6, 5, "medium"), (0.6, 4, "low"),
     (0.5, 50, "low"), (0.9, None, "low")],
)
def test_confidence_level_thresholds(share: float, sample: int | None, level: str) -> None:
    assert confidence_level(share, sample) == level
    assert confidence_level(0.0, None, deterministic=True) == "high"


def test_every_move_states_its_sample(macro: MacroTable) -> None:
    assert with_sample("Best in 8 of 10 similar cases", 6, "past periods") == (
        "Best in 8 of 10 similar cases (sample: 6 past periods)"
    )
    for c in candidates(build_context(homeowner(), macro, TODAY)):
        m = c.move
        assert m.confidence_level in ("low", "medium", "high")
        if m.sample_size is not None:
            assert f"(sample: {m.sample_size} " in m.confidence_label
        if m.confidence_level == "high" and m.kind != "cancel_subscription":
            assert m.sample_size is not None and m.sample_size >= 8
    moves = [c.move for c in candidates(build_context(homeowner(), macro, TODAY))]
    energy = next(m for m in moves if m.kind == "switch_energy")
    assert energy.sample_size == 5 and energy.confidence_level != "high"  # 5 matched years is not enough


# ---------- months of cover (bug 5) and interest (bug 6) ----------


def test_months_of_cover_none_without_costs() -> None:
    rich = [Account(id="cur", name="C", kind="current", provider="B", balance=40_000.0)]
    tiny = snapshot([*monthly("2025-11-28", 11, 2000.0, "ACME SALARY"), *monthly("2025-11-03", 12, -10.0, "CAFE")],
                    rich)
    assert known_monthly_costs(tiny, TODAY) is None  # £10 a month: costs not entered
    assert months_of_cover(tiny, TODAY) is None  # never 4,000 months
    assert all(f.id != "emergency_months" for f in personal_facts(tiny))


def test_interest_fact_only_with_known_rate() -> None:
    sav = [Account(id="cur", name="C", kind="current", provider="B", balance=100.0),
           Account(id="sav", name="S", kind="savings", provider="B", balance=5_000.0)]
    no_rate = _bare(sav)
    assert all(f.id != "savings_interest" for f in personal_facts(no_rate))
    with_rate = snapshot([*monthly("2025-11-28", 11, 2000.0, "ACME SALARY"),
                          *monthly("2025-11-30", 11, 10.0, "INTEREST PAID", None, "sav")], sav)
    assert any(f.id == "savings_interest" for f in personal_facts(with_rate))


def test_unknown_savings_rate_is_called_the_average(macro: MacroTable) -> None:
    sav = [Account(id="cur", name="C", kind="current", provider="B", balance=100.0),
           Account(id="sav", name="S", kind="savings", provider="B", balance=8_000.0)]
    m = next(c.move for c in candidates(build_context(_bare(sav), macro, TODAY)) if c.move.kind == "move_savings")
    assert "We do not know their rate, so we use the UK average" in m.evidence[0].text


# ---------- tracker figure by hand (bug 9) ----------


def _interest(balance: float, years_left: int, rates: list[float]) -> float:
    """Independent of the engine: monthly amortisation, re-priced at the start of each year."""
    paid = 0.0
    bal = balance
    n = years_left * 12
    for r in rates:
        i = r / 1200
        pay = bal * i / (1 - (1 + i) ** -n) if i > 0 else bal / n
        for _ in range(12):
            it = bal * i
            paid += it
            bal = bal + it - pay
            n -= 1
    return paid


def test_priya_tracker_gain_by_hand(macro: MacroTable) -> None:
    """Priya Shah (homeowner-leeds), mock macro, 2026-10-17. £180,000 left over 25 years; deal ends 2027-03-31.

    Today's rates (BoE, 2026): standard variable rate (doing nothing) 6.58%, tracker 4.23%.
    Matched past periods (5 years each): 2007, 2017, 2005, 2006, 2018. Each path = today's rate + the change in
    that series since the period's first year (delta method).

    Year 1 by hand: payment at 6.58% = £1,224.39 a month, interest in year 1 = £11,756.50.
    At 4.23%: £973.11 a month, interest in year 1 = £7,534.29. Year-1 saving = £4,222.21.

    Five-year interest, keep (SVR) minus tracker, divided by 5 years:
      2007: (33,578.03 - 20,727.27) / 5 = £2,570.15
      2017: (52,769.73 - 37,040.65) / 5 = £3,145.82
      2005: (54,554.28 - 36,766.66) / 5 = £3,557.52
      2006: (44,825.13 - 29,787.98) / 5 = £3,007.43
      2018: (56,997.40 - 40,971.48) / 5 = £3,205.18
    Mean = 15,486.10 / 5 = £3,097.22 a year. The engine's figure is correct: it is the average yearly interest
    saved against staying on the standard variable rate over 5 years, not the saving in year 1.
    """
    finance = pytest.importorskip("lifeline_data.finance")
    mock = pytest.importorskip("lifeline_data.macro").mock_macro_table()
    snap = finance.fixture_snapshot("persona:homeowner-leeds")
    paths = {
        2007: ([6.58, 4.28, 2.87, 2.81, 3.02], [4.23, 3.18, 1.79, 1.44, 1.50]),
        2017: ([6.58, 6.44, 6.31, 5.66, 5.65], [4.23, 4.24, 4.48, 4.73, 4.19]),
        2005: ([6.58, 7.21, 7.91, 5.61, 4.20], [4.23, 4.73, 5.37, 4.32, 2.93]),
        2006: ([6.58, 7.28, 4.98, 3.57, 3.51], [4.23, 4.87, 3.82, 2.43, 2.08]),
        2018: ([6.58, 6.45, 5.80, 5.79, 8.60], [4.23, 4.47, 4.72, 4.18, 6.67]),
    }
    assert round(_interest(180_000, 25, [6.58]), 2) == pytest.approx(11_756.50, abs=0.01)
    assert round(_interest(180_000, 25, [4.23]), 2) == pytest.approx(7_534.29, abs=0.01)
    gains = {s: (_interest(180_000, 25, k) - _interest(180_000, 25, t)) / 5 for s, (k, t) in paths.items()}
    assert gains[2007] == pytest.approx(2_570.15, abs=1.0)
    assert gains[2018] == pytest.approx(3_205.18, abs=1.0)
    by_hand = sum(gains.values()) / 5
    assert by_hand == pytest.approx(3_097.22, abs=2.0)  # rates above are rounded to 2 dp
    top = next_move(snap, mock, TODAY).top
    assert top.kind == "fix_mortgage" and top.action == "Take a tracker"
    assert top.impact_per_year == pytest.approx(by_hand, abs=2.0)


def test_monthly_spend_uses_whole_months_only() -> None:
    """A statement starting 17 July: July is a part month and is not counted. Aug £400, Sep £400 -> £400 a month
    (with July's £200 half month it would be (200 + 400 + 400) / 3 = £333)."""
    from lifeline_engine.money.profile import full_data_months, monthly_spend

    txs = [tx("2026-07-17", -200.0, "TESCO", "Tesco"), tx("2026-08-10", -400.0, "TESCO", "Tesco"),
           tx("2026-09-10", -400.0, "TESCO", "Tesco")]
    s = snapshot(txs)
    assert full_data_months(s, ["2026-07", "2026-08", "2026-09"]) == ["2026-08", "2026-09"]
    assert monthly_spend(s, TODAY) == 400.0
    s2 = snapshot([tx("2026-07-02", -200.0, "TESCO", "Tesco"), *txs[1:]])
    assert full_data_months(s2, ["2026-07", "2026-08", "2026-09"]) == ["2026-07", "2026-08", "2026-09"]


def test_fallback_has_no_confidence_level(macro: MacroTable) -> None:
    r = next_move(_bare(), macro, TODAY)
    assert r.top.impact_per_year == 0
    assert r.top.confidence_level is None and r.top.sample_size is None
    assert "sample" not in r.top.confidence_label


def test_arithmetic_moves_say_based_on_your_own_numbers(macro: MacroTable) -> None:
    sub = next(c.move for c in candidates(build_context(homeowner(), macro, TODAY))
               if c.move.kind == "cancel_subscription")
    assert sub.confidence_level == "high" and sub.sample_size is None
    assert sub.confidence_label == "Based on your own numbers"


def test_cut_budget_counts_only_months_with_data(macro: MacroTable) -> None:
    """A 3-month statement (17 July to 16 October): whole months Aug and Sep only, so 'of the last 2 months'."""
    txs = [tx("2026-07-17", -100.0, "PRET", "Pret"), tx("2026-08-12", -100.0, "PRET", "Pret"),
           tx("2026-09-12", -260.0, "PRET", "Pret"), tx("2026-10-05", -20.0, "PRET", "Pret")]
    snap = snapshot(txs, as_of="2026-10-16")
    moves = [c.move for c in candidates(build_context(snap, macro, date(2026, 10, 16))) if c.move.kind == "cut_budget"]
    assert len(moves) == 1
    m = moves[0]
    assert m.sample_size == 2
    assert m.confidence_label.startswith("You spent this little in 1 of the last 2 months")
    assert "of those 2 months" in m.evidence[2].text and "6 months" not in m.evidence[2].text
    assert m.evidence[1].text == "In the month before, you spent £100 a month."  # W-F-2: no "1 months"
