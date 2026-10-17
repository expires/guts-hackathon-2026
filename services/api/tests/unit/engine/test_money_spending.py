from __future__ import annotations

from datetime import date

import pytest

from lifeline_contracts.finance import CreateGoalRequest
from lifeline_engine.money.spending import budgets, goal_from_request, months_between, spending

from .finance_builders import tx

TXS = [
    tx("2026-09-03", -100.0, "TESCO STORES", "Tesco"),
    tx("2026-09-10", -50.0, "PRET A MANGER", "Pret"),
    tx("2026-10-02", -120.0, "TESCO STORES", "Tesco"),
    tx("2026-10-05", -30.0, "TESCO STORES", "Tesco"),
    tx("2026-10-06", 10.0, "TESCO REFUND", "Tesco"),
    tx("2026-10-07", -60.0, "DELIVEROO", "Deliveroo"),
    tx("2026-10-08", -500.0, "TO EVERYDAY SAVER"),
    tx("2026-10-09", -300.0, "BARCLAYCARD PAYMENT"),
    tx("2026-10-28", 2500.0, "ACME SALARY"),
]


def test_spending_by_category_hand_case() -> None:
    cats = {c.category: c for c in spending(TXS, "2026-10")}
    assert set(cats) == {"groceries", "eating_out"}  # savings, card payment and salary excluded
    assert cats["groceries"].amount == 140.0  # 120 + 30 - 10 refund
    assert cats["groceries"].transactions == 3
    assert cats["eating_out"].amount == 60.0
    assert cats["groceries"].share == pytest.approx(0.7)
    assert cats["groceries"].change_pct == 40.0  # 100 -> 140
    assert cats["eating_out"].change_pct == 20.0  # 50 -> 60
    assert [c.category for c in spending(TXS, "2026-10")] == ["groceries", "eating_out"]


def test_budgets_status() -> None:
    items = {b.category: b for b in budgets(TXS, "2026-10", {"groceries": 150.0, "eating_out": 50.0, "travel": 0.0})}
    assert items["groceries"].progress == pytest.approx(140 / 150, abs=1e-4)
    assert items["groceries"].status == "near"
    assert items["eating_out"].status == "over" and items["eating_out"].progress == 1.2
    assert items["travel"].status == "ok" and items["travel"].progress == 0.0


def test_months_between() -> None:
    assert months_between(date(2026, 10, 17), date(2027, 4, 17)) == 6
    assert months_between(date(2026, 10, 17), date(2027, 4, 18)) == 7
    assert months_between(date(2026, 10, 17), date(2026, 10, 18)) == 1
    assert months_between(date(2026, 10, 17), date(2026, 10, 1)) == 0


def test_goal_arithmetic() -> None:
    g = goal_from_request(
        "g1", CreateGoalRequest(name="Holiday", target=1200, saved=300, target_date="2027-04-17"), date(2026, 10, 17)
    )
    assert g.progress == 0.25
    assert g.monthly_needed == 150.0  # 900 left over 6 months
    late = goal_from_request(
        "g2", CreateGoalRequest(name="Late", target=1000, saved=400, target_date="2026-01-01"), date(2026, 10, 17)
    )
    assert late.monthly_needed == 600.0
    none = goal_from_request("g3", CreateGoalRequest(name="Open", target=500), date(2026, 10, 17))
    assert none.monthly_needed is None and none.progress == 0.0
