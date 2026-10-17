"""Hand-calculated cash-flow projections (ADR 0033).

Fixture: today 2026-10-17. Complete months Jul, Aug, Sep 2026 each have rent £1,000, Netflix £10 and Tesco £490,
so outgoings = £1,500 a month. Salary £2,000 a month. Cash £3,000. Months of cover = 3,000 / 1,500 = 2.0.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lifeline_contracts.finance import Account, MortgageDetails
from lifeline_engine.finance import monthly_payment
from lifeline_engine.tools.cashflow import Cancel, JobLoss, OneOffCost, RateRise, cash_flow_projection

from .finance_builders import monthly, snapshot


def _snap(mortgage: MortgageDetails | None = None):  # type: ignore[no-untyped-def]
    txs = [
        *monthly("2026-04-28", 6, 2000.0, "ACME SALARY"),
        *monthly("2026-04-01", 6, -1000.0, "J SMITH LETTINGS RENT"),
        *monthly("2026-04-09", 6, -10.0, "NETFLIX.COM", "Netflix"),
        *monthly("2026-04-15", 6, -490.0, "TESCO STORES", "Tesco"),
    ]
    accounts = [Account(id="cur", name="Current", kind="current", provider="B", balance=3000.0)]
    return snapshot(txs, accounts, mortgage=mortgage)


def test_base_case() -> None:
    p = cash_flow_projection(_snap(), 6)
    assert (p.start_balance, p.monthly_income, p.monthly_outgoings) == (3000.0, 2000.0, 1500.0)
    assert p.months_of_cover == 2.0
    assert [r.balance for r in p.rows] == [3500, 4000, 4500, 5000, 5500, 6000]
    assert p.rows[0].date == "2026-11-01"
    assert p.run_out_month is None
    assert (p.lowest_balance, p.lowest_month, p.end_balance) == (3500, 1, 6000)


def test_job_loss_three_months() -> None:
    # 3,000 - 1,500 = 1,500; 0; -1,500 (runs out in month 3); then +500 a month: -1,000, -500, 0.
    p = cash_flow_projection(_snap(), 6, [JobLoss(months=3)])
    assert [r.balance for r in p.rows] == [1500, 0, -1500, -1000, -500, 0]
    assert p.run_out_month == 3
    assert (p.lowest_balance, p.lowest_month) == (-1500, 3)


def test_one_off_cost_and_cancel() -> None:
    p = cash_flow_projection(_snap(), 3, [OneOffCost(gbp=4000, month=2)])
    assert [r.balance for r in p.rows] == [3500, 0, 500]  # month 2: 3,500 + 500 - 4,000
    assert p.run_out_month is None and p.lowest_balance == 0
    c = cash_flow_projection(_snap(), 2, [Cancel(subscription_ids=["sub_netflix", "sub_unknown"])])
    assert c.cancelled_per_month == 10.0
    assert [r.balance for r in c.rows] == [3510, 4020]
    assert c.unknown_subscription_ids == ("sub_unknown",)


def test_rate_rise_after_fixed_deal() -> None:
    # £150,000 at 4% for 20 years, fixed until 2027-01-31. Rise of 2 points from month 4 (Feb 2027).
    m = MortgageDetails(balance=150_000, rate_pct=4.0, rate_type="fixed", fixed_until="2027-01-31", years_left=20,
                        property_value=250_000, monthly_payment=909.0)
    extra = monthly_payment(150_000, 6.0, 20) - monthly_payment(150_000, 4.0, 20)
    assert round(extra, 2) == 165.68  # 1,074.65 - 908.97 (hand-checked annuity)
    p = cash_flow_projection(_snap(m), 5, [RateRise(points=2)])
    assert p.mortgage_extra_per_month == 165.68
    assert [r.outgoings for r in p.rows] == [1500, 1500, 1500, round(1500 + extra, 2), round(1500 + extra, 2)]


def test_variable_mortgage_rises_from_month_one() -> None:
    m = MortgageDetails(balance=150_000, rate_pct=4.0, rate_type="variable", years_left=20, property_value=250_000,
                        monthly_payment=909.0)
    p = cash_flow_projection(_snap(m), 2, [RateRise(points=2)])
    assert p.rows[0].outgoings == round(1500 + p.mortgage_extra_per_month, 2)


def test_no_mortgage_rate_rise_has_no_effect() -> None:
    assert cash_flow_projection(_snap(), 2, [RateRise(points=3)]).mortgage_extra_per_month == 0


def test_bounds() -> None:
    with pytest.raises(ValueError):
        cash_flow_projection(_snap(), 0)
    with pytest.raises(ValidationError):
        JobLoss(months=0)
    with pytest.raises(ValidationError):
        RateRise(points=50)
    with pytest.raises(ValidationError):
        OneOffCost(gbp=-5, month=1)


def test_stocks_and_shares_isa_is_not_cash() -> None:
    from lifeline_engine.tools.wrappers import tool_finance_summary

    snap = _snap()
    snap = snap.model_copy(
        update={
            "accounts": [
                *snap.accounts,
                Account(id="isa", name="Vanguard Stocks and Shares ISA", kind="isa", provider="V", balance=8400.0),
                Account(id="cisa", name="Cash ISA", kind="isa", provider="N", balance=1500.0),
            ]
        }
    )
    p = cash_flow_projection(snap, 1)
    assert p.start_balance == 4500.0  # 3,000 current + 1,500 cash ISA; the £8,400 stocks ISA is not cash
    assert p.months_of_cover == 3.0  # 4,500 / 1,500
    facts = {f.id: f.value for f in tool_finance_summary(snap).facts}
    assert facts["finance.months_of_cover"] == 3.0 and facts["finance.balance"] == 4500.0


def test_no_spending_gives_no_months_of_cover() -> None:
    from lifeline_engine.tools.wrappers import tool_finance_summary

    snap = snapshot([], [Account(id="cur", name="Current", kind="current", provider="B", balance=500.0)])
    assert cash_flow_projection(snap, 2).months_of_cover is None
    assert "finance.months_of_cover" not in {f.id for f in tool_finance_summary(snap).facts}


def test_deal_ending_on_the_first_rises_that_month() -> None:
    # Fix ends 2027-02-01: February 2027 is month 4 (Nov, Dec, Jan, Feb), so the rise starts in month 4.
    m = MortgageDetails(balance=150_000, rate_pct=4.0, rate_type="fixed", fixed_until="2027-02-01", years_left=20,
                        property_value=250_000, monthly_payment=909.0)
    p = cash_flow_projection(_snap(m), 5, [RateRise(points=2)])
    assert [r.outgoings > 1500 for r in p.rows] == [False, False, False, True, True]
    assert p.rows[3].date == "2027-02-01"


def test_tool_horizon_up_to_60() -> None:
    from lifeline_engine.tools.wrappers import CashFlowInput

    assert CashFlowInput(months=60).months == 60
    with pytest.raises(ValidationError):
        CashFlowInput(months=61)
