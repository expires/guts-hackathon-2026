from __future__ import annotations

from datetime import date

import pytest

from lifeline_contracts.finance import Account, FinanceSnapshot, Transaction
from lifeline_engine.money.insights import spending_insights

TODAY = date(2026, 6, 30)
_n = 0


def tx(month: int, day: int, amount: float, description: str, merchant: str | None = None) -> Transaction:
    global _n
    _n += 1
    return Transaction(
        id=f"t{_n}", account_id="cur", date=f"2026-{month:02d}-{day:02d}", amount=amount,
        description=description, merchant=merchant,
    )


def snap(txs: list[Transaction], status: str = "mock") -> FinanceSnapshot:
    return FinanceSnapshot(
        status=status, source="fixtures", as_of="2026-06-30",  # type: ignore[arg-type]
        accounts=[Account(id="cur", name="Current", kind="current", provider="Monzo", balance=2000)],
        transactions=txs,
    )


def month_txs(m: int, groceries: float = 100.0) -> list[Transaction]:
    return [
        tx(m, 1, 3000, "Salary"),
        tx(m, 2, -1000, "Rent to landlord", "Landlord"),
        tx(m, 5, -10, "NETFLIX.COM", "Netflix"),
        tx(m, 10, -groceries, "TESCO", "Tesco"),
        tx(m, 11, -20, "TESCO", "Tesco"),
        tx(m, 12, -20, "TESCO", "Tesco"),
        tx(m, 13, -20, "TESCO", "Tesco"),
        tx(m, 14, -20, "TESCO", "Tesco"),
        tx(m, 20, -500, "Transfer to savings pot"),
    ]


def test_full_six_months() -> None:
    txs = [t for m in range(1, 7) for t in month_txs(m)]
    r = spending_insights(snap(txs), TODAY, 6)
    assert r.window_months == 6 and r.note is None and r.start_month == "2026-01" and r.end_month == "2026-06"
    assert r.meta.label == "Sample data"
    assert [m.income for m in r.monthly] == [3000.0] * 6
    assert [m.spend for m in r.monthly] == [1190.0] * 6  # rent 1000 + netflix 10 + tesco 180
    assert r.total_spend == 7140.0 and r.total_income == 18000.0
    top = r.categories[0]
    assert top.category == "housing" and top.amount == 6000.0 and top.share == pytest.approx(6000 / 7140, abs=1e-3)
    assert all(c.change_pct is None for c in r.categories)  # no history before January
    assert r.category_months[0] == "2026-01"
    assert next(s for s in r.category_by_month if s.category == "groceries").values == [180.0] * 6
    assert r.top_merchants[0].merchant == "Landlord"
    assert r.subscriptions.monthly_total == 10.0 and r.subscriptions.annual_total == 120.0
    assert 3 <= len(r.insights) <= 6
    assert all("—" not in s for s in r.insights)


def test_short_history_adapts_and_notes() -> None:
    txs = [t for m in (4, 5, 6) for t in month_txs(m)]
    r = spending_insights(snap(txs), TODAY, 6)
    assert r.window_months == 3 and r.requested_months == 6 and r.note == "Based on your last 3 months"
    assert [m.month for m in r.monthly] == ["2026-04", "2026-05", "2026-06"]
    assert spending_insights(snap(txs), TODAY, 3).note is None


def test_under_two_months_is_empty_with_a_note() -> None:
    r = spending_insights(snap(month_txs(6)), TODAY, 6)
    assert r.window_months == 0 and r.monthly == [] and r.insights == [] and r.note
    assert spending_insights(snap([]), TODAY, 6).window_months == 0


def test_change_vs_previous_window() -> None:
    txs = [t for m in range(1, 7) for t in month_txs(m, groceries=100 if m <= 3 else 200)]
    r = spending_insights(snap(txs), TODAY, 3)
    g = next(c for c in r.categories if c.category == "groceries")
    assert g.change_pct == pytest.approx((840 - 540) / 540 * 100, abs=0.1)  # (200+80)*3 vs (100+80)*3
    assert any("Groceries is up" in s for s in r.insights)


def test_transfers_and_savings_are_not_spending() -> None:
    txs = [t for m in range(1, 7) for t in month_txs(m)]
    base = spending_insights(snap(txs), TODAY, 6)
    jo = [tx(5, 3, -900, "Transfer to Jo"), tx(5, 4, 900, "Transfer from Jo")]
    extra = spending_insights(snap(txs + jo), TODAY, 6)
    assert extra.total_spend == base.total_spend and extra.total_income == base.total_income


def test_unusual_and_patterns() -> None:
    txs = [t for m in range(1, 7) for t in month_txs(m)] + [tx(5, 16, -400, "TESCO", "Tesco")]  # a Saturday
    r = spending_insights(snap(txs), TODAY, 6)
    assert r.unusual[0].amount == 400.0 and r.unusual[0].typical == 20.0
    assert r.patterns.biggest_day_amount == 1000.0  # a rent day beats the 400 shop
    assert r.patterns.biggest_weekday in {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
    assert len(r.patterns.by_weekday) == 7
    assert r.patterns.average_daily_spend == pytest.approx(r.total_spend / 181, abs=0.01)
