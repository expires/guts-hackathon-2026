from __future__ import annotations

from datetime import date

from lifeline_engine.money.recurring import (
    classify_cadence,
    detect_salary,
    detect_subscriptions,
    price_rise,
    stable_subscription_amounts,
    upcoming_bills,
)

from .finance_builders import every, monthly, tx

TODAY = date(2026, 10, 17)


def test_cadence_classes() -> None:
    assert classify_cadence([7, 7, 6]) == "weekly"
    assert classify_cadence([31, 30, 28]) == "monthly"
    assert classify_cadence([91, 92]) == "quarterly"
    assert classify_cadence([365]) == "yearly"
    assert classify_cadence([7, 30]) is None
    assert classify_cadence([]) is None


def test_amount_rule() -> None:
    assert stable_subscription_amounts([10.0, 10.5, 10.99])  # within 10% each step
    assert stable_subscription_amounts([10.0, 10.0, 14.0])  # one price rise of 40%
    assert not stable_subscription_amounts([10.0, 25.0])  # +150%
    assert not stable_subscription_amounts([10.0, 7.0])  # -30%


def test_monthly_subscription_with_price_rise() -> None:
    txs = monthly("2026-01-09", 10, [-12.99] * 6 + [-13.99] * 4, "NETFLIX.COM", "Netflix")
    subs = detect_subscriptions(txs, TODAY)
    assert len(subs) == 1
    s = subs[0]
    assert s.cadence == "monthly"
    assert s.amount == 13.99
    assert s.monthly_cost == 13.99
    assert s.next_payment == "2026-11-09"
    assert s.price_rise is not None
    assert (s.price_rise.from_amount, s.price_rise.to_amount, s.price_rise.since) == (12.99, 13.99, "2026-07-09")


def test_no_price_rise_when_flat_or_lower() -> None:
    assert price_rise(monthly("2026-01-01", 3, -9.99, "SPOTIFY")) is None
    assert price_rise(monthly("2026-01-01", 3, [-10.0, -10.0, -9.5], "SPOTIFY")) is None


def test_yearly_and_weekly_monthly_cost() -> None:
    yearly = [tx("2025-03-01", -95.0, "AMAZON PRIME", "Amazon Prime"), tx("2026-03-01", -95.0, "AMAZON PRIME",
                                                                            "Amazon Prime")]
    weekly = every("2026-09-01", 7, 7, -6.0, "PATREON MEMBERSHIP")
    subs = {s.merchant: s for s in detect_subscriptions(yearly + weekly, TODAY)}
    assert subs["Amazon Prime"].cadence == "yearly"
    assert subs["Amazon Prime"].monthly_cost == round(95 / 12, 2)
    assert subs["Patreon Membership"].cadence == "weekly"
    assert subs["Patreon Membership"].monthly_cost == round(6 * 52 / 12, 2)


def test_stopped_subscription_is_not_active() -> None:
    txs = monthly("2026-01-05", 4, -9.99, "DISNEY PLUS", "Disney+")  # last charge April
    assert detect_subscriptions(txs, TODAY) == []


def test_two_monthly_charges_are_not_enough() -> None:
    assert detect_subscriptions(monthly("2026-08-20", 2, -9.99, "SPOTIFY"), TODAY) == []


def test_groceries_are_not_bills() -> None:
    txs = every("2026-07-01", 15, 7, -80.0, "TESCO STORES", "Tesco")
    assert upcoming_bills(txs, TODAY) == []


def test_bills_status_and_window() -> None:
    txs = [
        *monthly("2026-05-18", 5, -22.0, "EE LIMITED", "EE"),  # next 2026-10-18 -> due_soon (1 day)
        *monthly("2026-05-01", 6, -822.03, "NATIONWIDE MORTGAGE", "Nationwide"),  # next 2026-11-01
        *monthly("2026-04-14", 6, -41.5, "YORKSHIRE WATER", "Yorkshire Water"),  # missed 2026-10-14 -> overdue
        *monthly("2026-05-25", 5, [-120.0, -100.0, -90.0, -110.0, -130.0], "OCTOPUS ENERGY", "Octopus"),
    ]
    bills = {b.name: b for b in upcoming_bills(txs, TODAY)}
    assert bills["EE"].status == "due_soon" and bills["EE"].due_date == "2026-10-18"
    assert bills["Nationwide"].kind == "mortgage" and bills["Nationwide"].status == "upcoming"
    assert bills["Yorkshire Water"].status == "overdue" and bills["Yorkshire Water"].due_date == "2026-10-14"
    assert bills["Octopus"].amount == 130.0  # variable bill accepted, latest amount
    assert [b.due_date for b in upcoming_bills(txs, TODAY)] == sorted(b.due_date for b in bills.values())


def test_salary_detection() -> None:
    txs = monthly("2026-01-28", 9, 2486.32, "NORTHGATE MEDIA LTD SALARY")
    inc = detect_salary(txs)
    assert inc is not None
    assert inc.monthly_net == 2486.32
    assert len(inc.payday_dates) == 9
    assert detect_salary([tx("2026-01-01", 50.0, "REFUND")]) is None


def test_council_tax_ten_payments_is_a_bill() -> None:
    # April 2026 to January 2027 pattern, shifted: 10 payments Apr..Jan, break Feb-Mar, then Apr..
    days = [f"2025-{m:02d}-01" for m in range(11, 13)] + [f"2026-{m:02d}-01" for m in (1, 4, 5, 6, 7, 8, 9, 10)]
    txs = [tx(d, -182.0, "LEEDS CITY COUNCIL CTAX", "Leeds City Council") for d in days]
    bills = {b.name: b for b in upcoming_bills(txs, TODAY)}
    assert "Leeds City Council" in bills
    assert bills["Leeds City Council"].due_date == "2026-11-01"


def test_council_tax_skips_february_and_march() -> None:
    from lifeline_engine.money.recurring import detect_recurring

    days = [f"2025-{m:02d}-01" for m in range(4, 13)] + ["2026-01-01"]
    txs = [tx(d, -150.0, "COUNCIL TAX", None) for d in days]
    rec = detect_recurring(txs, date(2026, 1, 15))
    assert len(rec) == 1
    assert rec[0].next_due(date(2026, 1, 15)) == date(2026, 4, 1)


def test_long_gap_still_rejected_for_other_payees() -> None:
    days = [f"2025-{m:02d}-01" for m in range(11, 13)] + [f"2026-{m:02d}-01" for m in (1, 4, 5, 6, 7, 8, 9, 10)]
    txs = [tx(d, -40.0, "YORKSHIRE WATER", "Yorkshire Water") for d in days]
    assert upcoming_bills(txs, TODAY) == []
