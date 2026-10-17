"""ADR 0046 student options: weekly budget, Lifetime ISA, keep as cash, expensive debt, facts table, habit score."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from lifeline_contracts.finance import (
    Account,
    AccountHolder,
    DebtItem,
    FinanceSnapshot,
    IncomeSource,
    MortgageDetails,
    Transaction,
)
from lifeline_contracts.macro import MacroTable
from lifeline_engine import preconditions as pre
from lifeline_engine import rules
from lifeline_engine.habits import COMPONENTS, habit_score
from lifeline_engine.money.text import unsupported_numbers
from lifeline_engine.next_move import build_context, candidates
from lifeline_engine.student import (
    Debt,
    detect_income,
    from_snapshot,
    lisa_bonus,
    lisa_withdrawal_loss,
    weekly_budget,
)

from .finance_builders import homeowner, monthly, snapshot, tx

TODAY = date(2026, 10, 17)


def _moves(snap: FinanceSnapshot, macro: MacroTable) -> dict[str, object]:
    return {c.move.kind: c.move for c in candidates(build_context(snap, macro, TODAY))}


# ---------- weekly budget ----------


def _short_student(cash: float) -> FinanceSnapshot:
    """Pay on the 28th (next 2026-10-28, 11 days away). £100 of day-to-day spend in each of the last 4 weeks,
    at 4 different shops so none is a regular bill."""
    txs = [*monthly("2026-07-28", 3, 900.0, "CAFE JOB SALARY")]
    for name, d in (("TESCO", 27), ("PRET", 20), ("ASOS", 13), ("LIDL", 6)):
        txs.append(tx(TODAY - timedelta(days=d), -100.0, name, name.title()))
    return snapshot(txs, [Account(id="cur", name="C", kind="current", provider="B", balance=cash)])


def test_weekly_budget_hand_case() -> None:
    """Cash £120, next pay in 11 days = 11/7 = 1.5714 weeks, no bills.
    safe = 120 / 1.5714 = £76.36 a week. Pace = (100 x 4) / 4 = £100 a week.
    At that pace: 100 x 1.5714 = £157.14 needed, so £37.14 short; cash lasts 120 / 100 = 1.2 weeks."""
    s = _short_student(120.0)
    wb = weekly_budget(s, from_snapshot(s, TODAY), TODAY, 120.0)
    assert wb is not None
    assert wb.next_date == date(2026, 10, 28) and wb.days_left == 11 and wb.next_kind == "salary"
    assert wb.bills_before == 0
    assert wb.weekly_pace == pytest.approx(100.0)
    assert wb.safe_weekly == pytest.approx(120 / (11 / 7))
    assert wb.short_by == pytest.approx(100 * 11 / 7 - 120)
    assert wb.weeks_covered == pytest.approx(1.2)
    assert wb.weeks_within == 0 and wb.weeks_seen == 4


def test_weekly_budget_move_and_preconditions(macro: MacroTable) -> None:
    short = _short_student(120.0)
    assert pre.weekly_budget(short, TODAY)
    m = _moves(short, macro)["weekly_budget"]
    assert m.action == "Spend up to £76 a week until 28 October"  # type: ignore[attr-defined]
    assert m.deadline == "2026-10-28" and m.confidence_level == "medium"  # type: ignore[attr-defined]
    # F-R-1: shortfall is plain (not annualised) and impact_per_year equals it.
    assert m.shortfall == pytest.approx(37.14, abs=0.01)  # type: ignore[attr-defined]
    assert m.impact_per_year == pytest.approx(m.shortfall)  # type: ignore[attr-defined]
    for e in m.evidence:  # type: ignore[attr-defined]
        assert unsupported_numbers(e.text, e.facts) == [], e.text
    assert not pre.weekly_budget(_short_student(2_000.0), TODAY)  # on track: no move
    broke = _moves(_short_student(0.0), macro)["weekly_budget"]  # F-V2-2: no cash at all still gets the move
    assert broke.action.startswith("Plan for £157 you are missing before 28 October")  # type: ignore[attr-defined]
    assert broke.headline == "You will be £157 short before 28 October"  # type: ignore[attr-defined]
    no_income = snapshot([t for t in _short_student(120.0).transactions if t.amount < 0])
    assert not pre.weekly_budget(no_income, TODAY)  # no known next payment: never invented


def test_termly_loan_is_not_projected() -> None:
    txs = [tx(d, 3_000.0, "STUDENT LOANS COMPANY") for d in ("2025-09-20", "2026-01-10", "2026-04-20")]
    assert detect_income(txs, TODAY) == ()
    weekly = [tx(TODAY - timedelta(days=7 * k - 1), 120.0, "BAR JOB WAGES") for k in (3, 2, 1)]
    found = detect_income(weekly, TODAY)
    assert len(found) == 1 and found[0].next_dates == (TODAY + timedelta(days=1),) and found[0].kind == "salary"
    due_today = [tx(TODAY - timedelta(days=7 * k), 120.0, "BAR JOB WAGES") for k in (3, 2, 1)]
    assert detect_income(due_today, TODAY) == ()  # F-V2-4: a payment due today is not the next one


# ---------- Lifetime ISA ----------


def test_lisa_bonus_and_charge_by_hand() -> None:
    # £1,000 in: bonus 25% = £250. Charge 25% of £1,250 = £312.50; back £937.50; loss £62.50 (6.25%).
    assert lisa_bonus(1_000) == 250
    assert lisa_withdrawal_loss(1_000) == pytest.approx(62.5)
    assert lisa_bonus(10_000) == 1_000  # capped at £4,000 a year


def _saver(birth_year: int, **update: object) -> FinanceSnapshot:
    txs = [*monthly("2025-11-28", 11, 1_400.0, "CAFE JOB SALARY"), *monthly("2025-11-01", 12, -600.0, "HALLS RENT")]
    accounts = [Account(id="cur", name="C", kind="current", provider="B", balance=400.0),
                Account(id="sav", name="S", kind="savings", provider="B", balance=9_000.0)]
    s = snapshot(txs, accounts)
    holder = AccountHolder(name="Sam", birth_year=birth_year)
    return s.model_copy(update={"holder": holder, **update})


def test_lifetime_isa_preconditions(macro: MacroTable) -> None:
    s = _saver(2006)
    assert pre.lifetime_isa(s, TODAY)
    m = _moves(s, macro)["lifetime_isa"]
    assert m.impact_per_year == lisa_bonus(pre.lisa_room(s, TODAY))  # type: ignore[attr-defined]
    assert m.worst_case_per_year < 0 and m.confidence_level == "high"  # type: ignore[attr-defined]
    assert m.trade_off.summary.startswith("A 25% charge")  # type: ignore[attr-defined]
    assert not pre.lifetime_isa(_saver(1980), TODAY)  # 45 or 46: too old to open
    assert not pre.lifetime_isa(_saver(2010), TODAY)  # 15 or 16: too young
    assert not pre.lifetime_isa(snapshot(_saver(2006).transactions, _saver(2006).accounts), TODAY)  # age unknown
    mort = MortgageDetails(balance=100_000, rate_pct=4, rate_type="variable", years_left=20, property_value=200_000,
                           monthly_payment=600)
    assert not pre.lifetime_isa(_saver(2006, mortgage=mort), TODAY)  # owns a home
    card = [*_saver(2006).accounts, Account(id="card", name="Card", kind="credit", provider="V", balance=-500.0)]
    assert not pre.lifetime_isa(_saver(2006, accounts=card), TODAY)  # clear card debt first


# ---------- keep as cash ----------


def test_keep_cash_needs_known_rate(macro: MacroTable) -> None:
    assert "keep_cash" not in _moves(homeowner(), macro)  # 1.24% < best easy-access rate: move_savings instead
    m = _moves(homeowner().model_copy(update={"savings_rate_pct": 6.0}), macro)["keep_cash"]
    # W-V2-1: gain = interest above the best easy-access rate, not all interest.
    assert m.impact_per_year == pytest.approx(6_800 * (6.0 - m.evidence[0].facts["best_rate"]) / 100,  # type: ignore[attr-defined]
                                              abs=1.0)
    assert m.trade_off.summary == "Rising prices can make your cash worth less over time"  # type: ignore[attr-defined]
    assert m.sample_size is not None  # type: ignore[attr-defined]
    no_rate = _saver(2006)
    assert not pre.keep_cash(no_rate, TODAY)


# ---------- expensive debt ----------


def test_expensive_debt_rules() -> None:
    assert Debt("card", 500).expensive == 500
    assert Debt("overdraft", 500).expensive == 0  # free limit unknown: not counted as expensive
    assert Debt("overdraft", 500, free_limit=300).expensive == 200
    assert Debt("bnpl", 300).expensive == 0  # 0% when paid on time
    assert Debt("bnpl", 300, rate_pct=29.9).expensive == 300
    od = snapshot(monthly("2025-11-28", 11, 900.0, "CAFE JOB SALARY"),
                  [Account(id="cur", name="C", kind="current", provider="B", balance=-800.0)])
    assert not pre.pay_off_debt(od, TODAY)


# ---------- facts table ----------


def test_student_facts_table() -> None:
    assert rules.get("lisa_withdrawal_charge").value == 25
    assert rules.get("maintenance_instalments_england").value == 3
    assert rules.get("railcard_16_25_price_1y").value == 35
    assert {f.topic for f in rules.FACTS} >= {"student_loan", "student_finance", "council_tax", "travel"}
    for plan in ("plan1", "plan2", "plan4", "plan5"):
        assert rules.get(f"student_loan_{plan}_threshold").value > 0
        assert rules.get(f"student_loan_rate_{plan}").value == 9
    assert rules.get("postgraduate_loan_rate").value == 6


# ---------- habit score ----------


def _person(scale: float, frugal: bool) -> FinanceSnapshot:
    txs: list[Transaction] = [*monthly("2026-04-28", 6, 1_000.0 * scale, "CAFE JOB SALARY"),
                              *monthly("2026-04-01", 7, -400.0 * scale, "HALLS RENT")]
    start = date(2026, 6, 1)
    for w in range(20):
        d = start + timedelta(days=7 * w)
        if frugal:
            txs.append(tx(d, -60.0 * scale, "ALDI", f"Aldi{w % 3}"))
        else:
            txs.append(tx(d, -(40.0 + 120.0 * (w % 3)) * scale, "ASOS", f"Asos{w % 4}"))
            txs.append(tx(d + timedelta(days=1), -50.0 * scale, "DELIVEROO", f"Deliveroo{w % 5}"))
    cash = (1_500.0 if frugal else 100.0) * scale
    accounts = [Account(id="cur", name="C", kind="current", provider="B", balance=cash)]
    if not frugal:
        accounts.append(Account(id="card", name="Card", kind="credit", provider="V", balance=-900.0 * scale))
    return snapshot(txs, accounts)


def test_habit_score_ignores_income_level() -> None:
    """Scaling every amount by 4 (a richer person with the same habits) gives the same scores."""
    for frugal in (True, False):
        a, b = habit_score(_person(1.0, frugal), TODAY), habit_score(_person(4.0, frugal), TODAY)
        assert a == b
        parts = a.components.model_dump()
        assert set(parts) == set(COMPONENTS)
        assert all(v is None or 0 <= v <= 100 for v in parts.values())


def test_habit_score_poorer_frugal_beats_richer_spender() -> None:
    poor_frugal = habit_score(_person(1.0, True), TODAY)
    rich_spender = habit_score(_person(3.0, False), TODAY)
    assert poor_frugal.overall is not None and rich_spender.overall is not None
    assert poor_frugal.overall > rich_spender.overall


def test_habit_score_unknown_inputs_are_none() -> None:
    empty = snapshot([])
    h = habit_score(empty, TODAY)
    assert h.overall is None and h.components.savings_rate is None and h.components.months_of_cover is None


# ---------- entered fields (ADR 0049 onboarding) ----------


def _spender(cash: float, **update: object) -> FinanceSnapshot:
    """No income in the transactions; £100 of day-to-day spend in each of the last 4 weeks."""
    txs = [tx(TODAY - timedelta(days=d), -100.0, n, n.title()) for n, d in (("TESCO", 27), ("PRET", 20),
                                                                              ("ASOS", 13), ("LIDL", 6))]
    s = snapshot(txs, [Account(id="cur", name="C", kind="current", provider="B", balance=cash)])
    return s.model_copy(update=update)


def test_entered_termly_loan_enables_weekly_budget(macro: MacroTable) -> None:
    """Loan instalment entered for 2027-01-05 (80 days away = 11.43 weeks). Cash £600:
    safe = 600 / (80 / 7) = £52.50 a week; at £100 a week you are 100 x 80/7 - 600 = £542.86 short."""
    loan = IncomeSource(id="slc", kind="maintenance_loan", amount=3_000, schedule="termly",
                        dates=["2026-09-22", "2027-01-05", "2027-04-20"])
    assert not pre.weekly_budget(_spender(600.0), TODAY)  # no known date: no move
    s = _spender(600.0, income_sources=[loan], is_student=True)
    assert pre.weekly_budget(s, TODAY)
    m = _moves(s, macro)["weekly_budget"]
    assert m.gain_kind == "weeks_of_cover"  # type: ignore[attr-defined]
    assert m.cover_weeks == pytest.approx(round(80 / 7, 1))  # type: ignore[attr-defined]
    assert m.safe_weekly_spend == pytest.approx(52.5)  # type: ignore[attr-defined]
    assert m.action == "Spend up to £52 a week until 5 January"  # type: ignore[attr-defined]
    assert "student loan payment" in m.evidence[0].text  # type: ignore[attr-defined]


def test_entered_monthly_source_steps_forward() -> None:
    fam = IncomeSource(id="fam", kind="family", amount=200, schedule="monthly", next_date="2026-09-30")
    inp = from_snapshot(_spender(100.0, income_sources=[fam]), TODAY)
    nxt = inp.next_income(TODAY)
    assert nxt is not None and nxt[0] == date(2026, 10, 30)
    one_off = IncomeSource(id="x", kind="other", amount=50, schedule="one_off", next_date="2026-09-01")
    assert from_snapshot(_spender(100.0, income_sources=[one_off]), TODAY).next_income(TODAY) is None


def test_entered_debts_drive_pay_off_debt(macro: MacroTable) -> None:
    within = _spender(500.0, debts=[DebtItem(id="od", kind="overdraft", balance=800, free_limit=1_000)])
    assert not pre.pay_off_debt(within, TODAY)  # inside the free overdraft
    over = _spender(500.0, monthly_costs=700.0, debts=[
        DebtItem(id="od", kind="overdraft", balance=1_300, free_limit=1_000, rate_pct=39.9),
        DebtItem(id="k", kind="bnpl", balance=240),
        DebtItem(id="c", kind="card", balance=600, rate_pct=24.9),
    ])
    assert pre.expensive_debt(over, TODAY) == 900  # £300 overdraft beyond the free limit + £600 card
    assert pre.pay_off_debt(over, TODAY)
    m = _moves(over, macro)["pay_off_debt"]
    # Weighted rate: (300 x 39.9 + 600 x 24.9) / 900 = 29.9%
    assert m.evidence[0].facts["card_rate"] == pytest.approx(29.9)  # type: ignore[attr-defined]


def test_entered_costs_and_rate() -> None:
    from lifeline_engine.money.profile import known_monthly_costs, months_of_cover, savings_rate_pct

    # ADR 0057: entered monthly_costs (regular costs) only without spending data.
    manual = snapshot([], [Account(id="cur", name="C", kind="current", provider="B", balance=2_100.0)]).model_copy(
        update={"monthly_costs": 700.0, "savings_rate_pct": 3.1})
    assert known_monthly_costs(manual, TODAY) == 700.0
    assert months_of_cover(manual, TODAY) == 3.0
    assert savings_rate_pct(manual, TODAY) == 3.1
    measured = snapshot(monthly("2026-07-05", 3, -400.0, "TESCO", "Tesco"),
                        [Account(id="cur", name="C", kind="current", provider="B", balance=2_000.0)])
    measured = measured.model_copy(update={"monthly_costs": 50.0})
    assert known_monthly_costs(measured, TODAY) == 400.0  # measured spending wins over entered bills
    assert months_of_cover(measured, TODAY) == 5.0
    assert from_snapshot(_spender(1.0, age=20), TODAY).age_min == 20


def test_weekly_pace_is_the_usual_week() -> None:
    """W-R-1: weeks of £100, £100, £1,100 (a laptop), £100. Median £100, not the £350 mean."""
    txs = [*monthly("2026-07-28", 3, 900.0, "CAFE JOB SALARY")]
    for name, d, amt in (("TESCO", 27, 100.0), ("PRET", 20, 100.0), ("CURRYS", 13, 1_100.0), ("LIDL", 6, 100.0)):
        txs.append(tx(TODAY - timedelta(days=d), -amt, name, name.title()))
    s = snapshot(txs, [Account(id="cur", name="C", kind="current", provider="B", balance=120.0)])
    wb = weekly_budget(s, from_snapshot(s, TODAY), TODAY, 120.0)
    assert wb is not None and wb.weekly_pace == pytest.approx(100.0)


def test_urgent_shortfall_ranks_first(macro: MacroTable) -> None:
    ranked = candidates(build_context(_short_student(0.0), macro, TODAY))
    assert ranked[0].move.kind == "weekly_budget" and (ranked[0].move.shortfall or 0) > 0
