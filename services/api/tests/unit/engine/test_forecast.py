"""The forecast Next Move maths (PENNY_V3_BUILD.md B2, ADR 0072). Hand-made snapshots, no lifeline_data."""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

import pytest

from lifeline_contracts.finance import Account, FinanceSnapshot, IncomeSource, Transaction
from lifeline_contracts.forecast import WhatIfChange, WhatIfResult
from lifeline_contracts.macro import MacroTable
from lifeline_engine import forecast as fc
from lifeline_engine.money.category import category_detail, full_months_before, statement_months
from tests.unit.engine.finance_builders import monthly, tx

TODAY = date(2026, 10, 18)


def _spending(per_day: float, start: str = "2026-07-01", end: date = TODAY) -> list[Transaction]:
    d, out = date.fromisoformat(start), []
    while d <= end:
        out.append(tx(d, -per_day, "TESCO STORES", "Tesco"))
        d += timedelta(days=1)
    return out


def snap(balance: float = 318.40, income: list[IncomeSource] | None = None, per_day: float = 17.50,
         extra: list[Transaction] | None = None, region: str = "scotland") -> FinanceSnapshot:
    """Eilidh from the canvas: phone £12 on the 24th, Spotify £5.99 on the 28th, rent £540 on the 3rd,
    SAAS loan + bursary on 2 November. Groceries £17.50 a day = £122.50 a week."""
    txs = [
        *monthly("2026-07-03", 4, -540.0, "MARCHMONT LETTINGS RENT", "Marchmont Lettings"),
        *monthly("2026-07-24", 3, -12.0, "EE LIMITED", "EE"),
        *monthly("2026-07-28", 3, -5.99, "SPOTIFY UK", "Spotify"),
        *_spending(per_day),
        *(extra or []),
    ]
    if income is None:
        income = [
            IncomeSource(id="saas", kind="maintenance_loan", amount=735.0, schedule="monthly",
                         dates=["2026-09-18", "2026-10-16", "2026-11-02"]),
            IncomeSource(id="ysb", kind="bursary", amount=166.0, schedule="monthly", dates=["2026-11-02"]),
        ]
    return FinanceSnapshot(
        status="mock", source="sample", as_of=TODAY.isoformat(), region=region,
        accounts=[Account(id="cur", name="Santander current account", kind="current", provider="Santander",
                          balance=balance),
                  Account(id="sav", name="Savings", kind="savings", provider="Santander", balance=300.0)],
        transactions=txs, income_sources=income,
    )


def run(s: FinanceSnapshot, buffer: fc.BufferPct = 10, cpi: float | None = 3.1, stress: int | None = None,
        rate: float | None = 2.06) -> fc.Forecast:
    return fc.compute(s, TODAY, buffer, cpi, 10.5, rate, stress)


def _adds_up(f: fc.Forecast) -> None:
    assert f.per_day >= 0 and f.per_week >= 0 and f.to_spend == round(f.per_day * f.days, 2)
    if f.money_now + f.expected_income_total - f.bills_total < 0:  # short: nothing to spend, never negative
        assert (f.per_day, f.per_week, f.buffer_amount, f.to_spend) == (0, 0, 0, 0)
        return
    available = Decimal(str(f.money_now)) + Decimal(str(f.expected_income_total))
    left = available - Decimal(str(f.bills_total)) - Decimal(str(f.buffer_amount))
    assert abs(left - Decimal(str(f.per_day)) * f.days) < Decimal("0.01")
    assert f.per_week == round(f.per_day * 7, 2)
    assert f.buffer_amount >= 0
    assert round(sum(b.amount for b in f.bills), 2) == f.bills_total


def test_canvas_example_on_track() -> None:
    f = run(snap())
    assert f.state == "on_track"
    assert f.next_money is not None
    assert (f.next_money.label, f.next_money.amount, f.next_money.date) == ("SAAS loan + bursary", 901.0, "2026-11-02")
    assert f.next_money.source.label == "SAAS payment schedule"
    assert f.money_now == 318.40 and [a.counted for a in f.accounts] == [True, False]
    assert [(b.name, b.amount, b.due_date) for b in f.bills] == [("EE", 12.0, "2026-10-24"),
                                                                 ("Spotify", 5.99, "2026-10-28")]
    assert f.bills_total == 17.99
    assert f.days == 14  # 19 Oct to 1 Nov
    # left 300.41; target buffer 30.04; per day floor(270.37 / 14) = 19.31; buffer takes the 3p remainder
    assert (f.per_day, f.per_week, f.buffer_amount) == (19.31, 135.17, 30.07)
    assert f.usual_weekly == 122.50 and f.usual_daily == 17.50
    assert [w.amount for w in f.usual_weeks] == [122.50] * 4
    assert (f.usual_weeks[0].start, f.usual_weeks[-1].end) == ("2026-09-20", "2026-10-17")
    assert f.spare == 25.34  # (135.17 - 122.50) x 14 / 7
    assert f.headline == "You'll make it to 2 November"
    assert f.budget_line == "You can spend £135 a week (about £19 a day)"
    assert f.budget_period == "week" and f.to_spend == 270.34
    assert f.habit_line == "You usually spend £123, so you'll have about £25 spare."
    assert f.suggestion is not None and f.suggestion.kind == "save_spare"
    assert f.suggestion.text == "Put your £25 spare aside on 2 November"
    assert f.suggestion.rate_pct == 2.06 and f.suggestion.source is not None
    assert f.run_out_date is None and not f.cpi_adjusted and f.stress is None
    _adds_up(f)


def test_steps_and_timeline() -> None:
    f = run(snap())
    assert [s.id for s in f.steps] == ["money_now", "bills", "buffer", "result"]
    assert [s.amount for s in f.steps] == [318.40, -17.99, -30.07, 135.17]
    assert all(s.sources for s in f.steps)
    assert "Savings are not counted" in f.steps[0].text
    assert "EE £12.00 and Spotify £5.99" in f.steps[1].text
    assert "3p" in f.steps[2].text
    assert "£270.34 ÷ 14 days = £19.31 a day, £135.17 a week" in f.steps[3].text
    assert [(p.kind, p.date) for p in f.timeline] == [
        ("today", "2026-10-18"), ("bill", "2026-10-24"), ("bill", "2026-10-28"), ("next_money", "2026-11-02")]


@pytest.mark.parametrize("buffer", [0, 5, 10, 15, 20])
def test_buffer_options_add_up(buffer: fc.BufferPct) -> None:
    f = run(snap(), buffer=buffer)
    _adds_up(f)
    target = round(buffer / 100 * (f.money_now - f.bills_total), 2)
    assert target <= f.buffer_amount < target + f.days * 0.01
    assert f.buffer_pct == buffer and f.steps[2].title == f"Safety buffer, {buffer}%"


def test_bigger_buffer_means_less_per_week() -> None:
    weeks = [run(snap(), buffer=b).per_week for b in (0, 5, 10, 15, 20)]
    assert weeks == sorted(weeks, reverse=True)


def test_bad_buffer_and_stress_rejected() -> None:
    with pytest.raises(ValueError):
        run(snap(), buffer=7)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        run(snap(), stress=2008)


def test_rounding_rule_random() -> None:
    rng = random.Random(72)
    for _ in range(500):
        days = rng.randint(1, 120)
        m = fc.maths(fc._d(rng.uniform(-500, 5000)), fc._d(rng.uniform(0, 1500)), rng.choice(fc.BUFFER_OPTIONS),
                     days)
        if m.left < 0:
            assert (m.per_day, m.buffer, m.per_week) == (0, 0, 0)
            continue
        assert m.money_now - m.bills_total - m.buffer == m.per_day * days  # exact, not just within 1p
        assert m.target_buffer <= m.buffer < m.target_buffer + Decimal("0.01") * days
        assert m.target_buffer >= 0
        assert m.per_week == m.per_day * 7


def test_running_short_and_run_out_date() -> None:
    f = run(snap(balance=150.0))
    assert f.state == "running_short"
    # left 132.01; usual daily 17.50 -> 7 whole days
    assert f.run_out_date == "2026-10-25"
    assert f.headline == "At this pace, you run out on 25 October"
    assert f.budget_line.startswith("Keep it under £")
    assert f.habit_line == "You usually spend £123. Groceries is your biggest cost: £123 a week."
    assert f.suggestion is not None and f.suggestion.kind == "cut_category"
    assert f.suggestion.category == "groceries" and f.suggestion.amount == 122.50
    assert f.spare is None
    assert ("run_out", "2026-10-25") in [(p.kind, p.date) for p in f.timeline]
    _adds_up(f)


def test_overdrawn() -> None:
    f = run(snap(balance=-371.03))
    assert f.money_now == -371.03 and f.state == "running_short"
    assert f.run_out_date == TODAY.isoformat()
    assert "overdrawn" in f.steps[0].text
    assert f.headline == "Your bills take all your money before 2 November"
    assert f.budget_line == "You are £389 short before 2 November"  # -371.03 - 17.99
    assert (f.per_day, f.per_week, f.to_spend, f.buffer_amount) == (0, 0, 0, 0)
    _adds_up(f)


def test_no_spare_suggestion_below_10() -> None:
    f = run(snap(balance=295.0))  # per week just above usual
    assert f.state == "on_track" and f.spare is not None and f.spare <= 10
    assert f.suggestion is None


def test_cpi_adjustment_for_gaps_over_6_weeks() -> None:
    loan = [IncomeSource(id="sfe", kind="maintenance_loan", amount=3612.0, schedule="termly",
                         dates=["2026-09-28", "2027-01-18"])]
    f = run(snap(balance=2500.0, income=loan, region="north-east"), cpi=3.1)
    assert f.next_money is not None and f.next_money.source.label == "Student Finance England payment dates"
    assert f.next_money.label == "Student Finance England loan"
    assert f.cpi_adjusted and f.cpi_note is not None and "ONS CPI" in f.cpi_note
    gap = (date(2027, 1, 18) - TODAY).days
    assert f.usual_weekly == round(122.5 * (1 + 0.031 * gap / 365), 2)
    # rent on the 3rd is due 3 Nov, 3 Dec and 3 Jan: each due date once
    assert [b.due_date for b in f.bills if b.kind == "rent"] == ["2026-11-03", "2026-12-03", "2027-01-03"]
    _adds_up(f)
    no_cpi = run(snap(balance=2500.0, income=loan, region="north-east"), cpi=None)
    assert not no_cpi.cpi_adjusted and no_cpi.usual_weekly == 122.5


def test_rent_counted_once_when_due_in_window() -> None:
    late = [IncomeSource(id="saas", kind="maintenance_loan", amount=735.0, schedule="monthly",
                         dates=["2026-11-10"])]
    f = run(snap(balance=1200.0, income=late))
    assert [b.name for b in f.bills].count("Marchmont Lettings") == 1
    assert not f.cpi_adjusted  # 23 days


def test_stress_2022() -> None:
    f = run(snap(), stress=2022)
    assert f.stress is not None
    assert f.stress.year == 2022 and f.stress.inflation_pct == 10.5
    assert f.stress.usual_weekly == round(122.5 * 1.105, 2)
    assert f.stress.per_week == f.per_week
    assert f.stress.state == "running_short" and f.stress.run_out_date is not None
    assert "like in 2022" in f.stress.text and f.stress.source.label.startswith("ONS CPI")
    assert run(snap(balance=1000.0), stress=2022).stress.state == "on_track"  # type: ignore[union-attr]


def test_no_next_money() -> None:
    f = run(snap(income=[]))
    assert f.state == "no_next_money" and f.next_money is None
    assert f.days == 28 and f.spare is None
    assert f.headline == "Add your next payment to see if your money lasts"
    assert f.steps[3].title == "The next 4 weeks"
    assert not any(p.kind == "next_money" for p in f.timeline)
    _adds_up(f)


def test_next_money_from_statement_when_nothing_entered() -> None:
    pay = monthly("2026-07-25", 3, 410.0, "BAR PAYROLL WAGES", "The Bar")
    f = run(snap(income=[], extra=pay))
    assert f.next_money is not None and f.next_money.date == "2026-10-25"
    assert f.next_money.source.label == "Your statement" and f.next_money.label == "Salary"


def test_macro_inputs_fallback() -> None:
    inp = fc.macro_inputs(MacroTable(values={}), TODAY)
    assert inp.cpi is None and inp.boe_easy_access_rate is None
    assert inp.inflation_2022 == fc.INFLATION_2022_FALLBACK


# ---------- All spending months and the Category screen ----------


def test_statement_months_and_category_detail() -> None:
    s = snap()
    assert statement_months(s) == ["2026-07", "2026-08", "2026-09", "2026-10"]
    assert full_months_before(s, "2026-10") == ["2026-07", "2026-08", "2026-09"]
    cd = category_detail(s, "groceries")
    assert cd.month == "2026-10" and cd.total == round(17.5 * 18, 2)
    assert cd.usual_monthly == round((17.5 * 31 + 17.5 * 31 + 17.5 * 30) / 3, 2)
    assert [(w.start, w.end) for w in cd.weeks] == [("2026-10-01", "2026-10-07"), ("2026-10-08", "2026-10-14"),
                                                    ("2026-10-15", "2026-10-18")]
    assert round(sum(w.amount for w in cd.weeks), 2) == cd.total
    assert len(cd.transactions) == 18 and cd.transactions[0].date == "2026-10-18"
    sep = category_detail(s, "groceries", "2026-09")
    assert sep.weeks[-1] == sep.weeks[-1].model_copy(update={"start": "2026-09-29", "end": "2026-09-30"})
    assert category_detail(s, "travel").total == 0 and category_detail(s, "travel").transactions == []


# ---------- main income source and expected income (BOSS decision, ADR 0072) ----------

LOAN = IncomeSource(id="saas", kind="maintenance_loan", amount=735.0, schedule="monthly",
                    dates=["2026-09-18", "2026-10-16", "2026-11-02"])
BURSARY = IncomeSource(id="ysb", kind="bursary", amount=166.0, schedule="monthly", dates=["2026-11-02"])
PAY = IncomeSource(id="bar", kind="part_time_job", amount=86.80, schedule="weekly",
                   dates=["2026-10-09", "2026-10-16", "2026-10-23"])


def test_main_income_is_next_money_and_smaller_income_is_expected() -> None:
    f = run(snap(income=[LOAN, BURSARY, PAY]))
    assert f.next_money is not None and f.next_money.date == "2026-11-02"  # loan, not the pay on 23 Oct
    assert [(e.label, e.amount, e.date) for e in f.expected_income] == [("Pay", 86.8, "2026-10-23"),
                                                                        ("Pay", 86.8, "2026-10-30")]
    assert f.expected_income_total == 173.60
    assert f.money_now == 318.40  # current accounts only
    left = Decimal("318.40") + Decimal("173.60") - Decimal("17.99") - Decimal(str(f.buffer_amount))
    assert left == Decimal(str(f.per_day)) * f.days
    assert f.steps[0].amount == 492.0 and "Expected before 2 Nov: Pay £173.60 (2 payments)" in f.steps[0].text


def test_one_off_money_is_never_main() -> None:
    gift = IncomeSource(id="gift", kind="family", amount=5000.0, schedule="one_off", dates=["2026-10-25"])
    f = run(snap(income=[LOAN, gift]))
    assert f.next_money is not None and f.next_money.date == "2026-11-02"
    assert f.expected_income_total == 5000.0


def test_biggest_monthly_source_wins() -> None:
    termly = IncomeSource(id="sfe", kind="maintenance_loan", amount=3000.0, schedule="termly",
                          dates=["2027-01-11"])  # 750 a month
    weekly = IncomeSource(id="job", kind="part_time_job", amount=200.0, schedule="weekly",
                          dates=["2026-10-16", "2026-10-23"])  # 866.67 a month
    f = run(snap(income=[termly, weekly]))
    assert f.next_money is not None and (f.next_money.label, f.next_money.date) == ("Pay", "2026-10-23")


# ---------- what if ----------


def wi(s: FinanceSnapshot, *changes: WhatIfChange) -> WhatIfResult:
    return fc.what_if(s, TODAY, 10, 3.1, 10.5, 2.06, list(changes))


def test_what_if_concert_on_the_30th() -> None:
    r = wi(snap(), WhatIfChange(kind="one_off_cost", amount=60, date="2026-10-30", label="Concert ticket"))
    assert r.after.bills_total == round(r.before.bills_total + 60, 2)
    assert r.after.per_week < r.before.per_week
    assert any(b.name == "Concert ticket" for b in r.after.bills)
    assert r.after.state == "running_short" and r.after.run_out_date is not None
    assert "run short" in r.summary and "(was £135 a week)" in r.summary
    later = wi(snap(), WhatIfChange(kind="one_off_cost", amount=60, date="2026-11-20", label="Concert ticket"))
    assert later.after.per_week == later.before.per_week and "does not change" in later.summary


def test_what_if_loan_a_week_late() -> None:
    r = wi(snap(balance=900.0), WhatIfChange(kind="move_payment", target="loan", amount=7))
    assert r.before.next_money is not None and r.after.next_money is not None
    assert (r.before.next_money.date, r.after.next_money.date) == ("2026-11-02", "2026-11-09")
    assert r.after.days == r.before.days + 7
    assert "Marchmont Lettings" in [b.name for b in r.after.bills]  # rent on 3 Nov is now inside the window
    assert r.after.per_week < r.before.per_week
    by_date = wi(snap(), WhatIfChange(kind="move_payment", date="2026-11-09"))
    assert by_date.after.next_money is not None and by_date.after.next_money.date == "2026-11-09"


def test_what_if_two_extra_shifts() -> None:
    s = snap(income=[LOAN, BURSARY, PAY])
    shift = fc.usual_pay(s)
    assert shift == 86.80
    r = wi(s, *[WhatIfChange(kind="extra_income", amount=shift, date=d, label="Extra shift")
                for d in ("2026-10-24", "2026-10-25")])
    assert r.after.expected_income_total == round(r.before.expected_income_total + 2 * 86.80, 2)
    assert r.after.per_week > r.before.per_week
    late = wi(s, WhatIfChange(kind="extra_income", amount=100, date="2026-11-05", label="Extra shift"))
    assert late.after.per_week == late.before.per_week and "does not help" in late.summary


def test_what_if_recurring_cost_change() -> None:
    r = wi(snap(), WhatIfChange(kind="recurring_cost_change", target="Spotify", amount=11.99))
    assert r.after.bills_total == round(r.before.bills_total + 6, 2)
    missing = wi(snap(), WhatIfChange(kind="recurring_cost_change", target="Netflix", amount=5))
    assert missing.after.bills_total == missing.before.bills_total and "No bill called Netflix" in missing.summary


def test_short_window_budget_until_next_money() -> None:
    soon = [IncomeSource(id="saas", kind="maintenance_loan", amount=735.0, schedule="monthly",
                         dates=["2026-10-26"])]
    f = run(snap(balance=900.0, income=soon))
    assert f.days == 7 and f.budget_period == "until_next_money"
    assert f.to_spend == round(f.per_day * 7, 2)
    assert f.budget_line == f"You can spend {fc.gbp0(f.to_spend)} until 26 October (about {fc.gbp0(f.per_day)} a day)"
    short = run(snap(balance=60.0, income=soon))
    assert short.state == "running_short" and short.budget_line.startswith("Keep it under £")
    assert short.budget_line.endswith(f"until 26 October (about {fc.gbp0(short.per_day)} a day)")
