"""Generate the synthetic sample statements in demo/statements/ (ADR 0047). W1 owns this file.

Deterministic: each profile has a fixed seed. No network. Standard library only.
Run from the repo root:  uv run --project services/api python tools/gen_statements.py [out_dir]

Default output: services/api/lifeline_data/statements/samples/ (package data, read by the API) and
demo/statements/ (copy for judges). Both copies are byte-identical.
Output per profile: <id>.csv (Monzo CSV export columns), <id>.pdf (simple Monzo-style PDF statement with a
running balance), plus index.json (SampleStatement fields from lifeline_contracts.account and a `hints` object).
All people, account details and amounts are synthetic. Every file says "Sample data".
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import sys
import zlib
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

START = date(2026, 7, 17)
END = date(2026, 10, 16)  # last statement day; "today" in the demo is 2026-10-17
MONTHS = 3
REPO = Path(__file__).resolve().parents[1]
# Canonical copy is package data (the API image builds from services/api); demo/ is the copy for judges.
OUTPUT_DIRS = [REPO / "services" / "api" / "lifeline_data" / "statements" / "samples", REPO / "demo" / "statements"]
BANK_HOLIDAYS = {date(2026, 8, 31), date(2026, 12, 25), date(2026, 12, 28), date(2027, 1, 1)}  # England and Wales
TERM_START = date(2026, 9, 21)

MONZO_HEADER = [
    "Transaction ID", "Date", "Time", "Type", "Name", "Emoji", "Category", "Amount", "Currency", "Local amount",
    "Local currency", "Notes and #tags", "Address", "Receipt", "Description", "Category split", "Money Out",
    "Money In",
]


# ---------- dates ----------------------------------------------------------------------------------


def working_day(d: date) -> date:
    """BACS rule: a payment due on a weekend or bank holiday lands on the next working day."""
    while d.weekday() >= 5 or d in BANK_HOLIDAYS:
        d += timedelta(days=1)
    return d


def last_working_day(year: int, month: int) -> date:
    d = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    while d.weekday() >= 5 or d in BANK_HOLIDAYS:
        d -= timedelta(days=1)
    return d


def last_friday(year: int, month: int) -> date:
    d = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return d


def days(start: date = START, end: date = END) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def monthly(day: int, start: date = START, end: date = END, adjust: bool = True) -> list[date]:
    """The `day` of each month in range. `adjust` moves weekend/bank holiday dates to the next working day
    (bank transfers); card subscriptions keep the calendar date."""
    out = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        d = date(y, m, min(day, 28))
        d = working_day(d) if adjust else d
        if start <= d <= end:
            out.append(d)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def weekly(weekday: int, start: date = START, end: date = END) -> list[date]:
    return [d for d in days(start, end) if d.weekday() == weekday]


def add_month(d: date, n: int = 1) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, min(d.day, 28))


# ---------- model --------------------------------------------------------------------------------


@dataclass
class Tx:
    day: date
    time: str
    type: str
    name: str
    emoji: str
    category: str
    amount: float
    description: str
    balance: float = 0.0


@dataclass
class Habit:
    """Random everyday spend: `per_week` expected purchases, price uniform in [lo, hi]."""

    name: str
    emoji: str
    category: str
    description: str
    lo: float
    hi: float
    per_week: float
    term_only: bool = False
    weekdays_only: bool = False
    start: date | None = None
    end: date | None = None


@dataclass
class Profile:
    id: str
    title: str
    description: str
    seed: int
    holder: str
    opening_balance: float
    funding: list[str]
    hints: dict[str, object]
    habits: list[Habit] = field(default_factory=list)
    fixed: list[Tx] = field(default_factory=list)
    team: bool = False
    overdraft_ear_pct: float | None = None


def card(day: date, name: str, emoji: str, category: str, amount: float, description: str,
         time: str = "12:00:00", type_: str = "Card payment") -> Tx:
    return Tx(day, time, type_, name, emoji, category, -round(amount, 2), description)


def money_in(day: date, name: str, amount: float, description: str, type_: str = "Faster payment",
             category: str = "Income", time: str = "06:00:00") -> Tx:
    return Tx(day, time, type_, name, "", category, round(amount, 2), description)


def subscription(name: str, emoji: str, amount: float, day: int, description: str,
                 category: str = "Entertainment") -> list[Tx]:
    return [card(d, name, emoji, category, amount, description, "04:10:00") for d in monthly(day, adjust=False)]


def direct_debit(name: str, emoji: str, amount: float, day: int, description: str, category: str = "Bills") -> list[Tx]:
    return [card(d, name, emoji, category, amount, description, "05:30:00", "Direct Debit") for d in monthly(day)]


def standing_order(name: str, amount: float, day: int, description: str, category: str = "Bills") -> list[Tx]:
    return [card(d, name, "", category, amount, description, "07:00:00", "Faster payment") for d in monthly(day)]


def pot(dates: list[date], pot_name: str, amount: float) -> list[Tx]:
    return [Tx(d, "08:00:00", "Pot transfer", pot_name, "", "Savings", -amount, f"Moved to {pot_name} pot")
            for d in dates]


def klarna_plan(first: date, merchant: str, instalment: float) -> list[Tx]:
    """Klarna Pay in 3: one instalment at checkout, then two more 30 days apart. Only rows in range appear."""
    out = []
    for i in range(3):
        d = first + timedelta(days=30 * i)
        if START <= d <= END:
            out.append(card(d, "Klarna", "", "Shopping", instalment, f"KLARNA*{merchant}", "10:15:00"))
    return out


def klarna_remaining(plans: list[tuple[date, float]]) -> tuple[float, date | None]:
    """Balance still owed on Pay in 3 plans at END and the next due date."""
    owed, next_due = 0.0, None
    for first, inst in plans:
        for i in range(3):
            d = first + timedelta(days=30 * i)
            if d > END:
                owed += inst
                next_due = d if next_due is None or d < next_due else next_due
    return round(owed, 2), next_due


# ---------- profiles -----------------------------------------------------------------------------


def income_source(id_: str, kind: str, amount: float, schedule: str, dates: list[date],
                  next_date: date | None = None) -> dict[str, object]:
    """Shape of lifeline_contracts.finance.IncomeSource."""
    if next_date is None:
        later = [d for d in dates if d > END]
        next_date = later[0] if later else None
    return {"id": id_, "kind": kind, "amount": round(amount, 2), "schedule": schedule,
            "next_date": next_date.isoformat() if next_date else None, "dates": [d.isoformat() for d in dates]}


def debt(id_: str, kind: str, balance: float, rate_pct: float | None = None, free_limit: float | None = None,
         due: date | None = None) -> dict[str, object]:
    """Shape of lifeline_contracts.finance.DebtItem."""
    return {"id": id_, "kind": kind, "balance": round(balance, 2), "rate_pct": rate_pct, "free_limit": free_limit,
            "due_date": due.isoformat() if due else None}


def hints(is_student: bool, age: int, housing: str, plan: str | None, income: list[dict[str, object]],
          debts: list[dict[str, object]], monthly_costs: float) -> dict[str, object]:
    return {"is_student": is_student, "age": age, "housing": housing, "student_loan_plan": plan,
            "income_sources": income, "debts": debts, "monthly_costs": round(monthly_costs, 2)}


def scholarship() -> Profile:
    sch = [working_day(date(2026, m, 1)) for m in (8, 9, 10)]
    bur = [working_day(date(2026, m, 15)) for m in (7, 8, 9, 10) if START <= working_day(date(2026, m, 15)) <= END]
    fixed = [money_in(d, "University of Sheffield", 280.00, "SCHOLARSHIP LIVING ALLOWANCE", "Bacs (Direct Credit)")
             for d in sch]
    fixed += [money_in(d, "University of Sheffield", 140.00, "SHEFFIELD BURSARY MONTHLY", "Bacs (Direct Credit)")
              for d in bur]
    fixed += subscription("Spotify", "🎵", 5.99, 9, "SPOTIFY STUDENT")
    fixed += direct_debit("giffgaff", "📱", 10.00, 5, "GIFFGAFF MOBILE")
    fixed += pot([d + timedelta(days=1) for d in sch], "Rainy day", 60.00)
    fixed.append(card(date(2026, 9, 18), "Northern", "🚆", "Transport", 9.80, "NORTHERN TRAINS SHEFFIELD-LEEDS"))
    fixed.append(card(date(2026, 9, 24), "Blackwell's", "📚", "Shopping", 24.99, "BLACKWELLS SHEFFIELD"))
    habits = [
        Habit("Aldi", "🛒", "Groceries", "ALDI 112 SHEFFIELD", 12.0, 24.0, 1.2),
        Habit("Tesco", "🛒", "Groceries", "TESCO EXPRESS 3125 SHEFFIELD", 2.5, 8.0, 0.9),
        Habit("Greggs", "🥐", "Eating out", "GREGGS 1214 SHEFFIELD", 1.40, 4.25, 0.4),
        Habit("Stagecoach", "🚌", "Transport", "STAGECOACH YORKSHIRE", 3.00, 3.00, 0.8, term_only=True),
        Habit("Sheffield Students' Union", "☕", "Eating out", "SHEFFIELD SU COFFEE", 1.90, 2.80, 0.7,
              term_only=True),
        Habit("Sheffield Students' Union", "🍺", "Entertainment", "SHEFFIELD SU BAR", 5.0, 13.0, 0.35,
              term_only=True),
        Habit("Boots", "💊", "Personal care", "BOOTS 1102 SHEFFIELD", 2.5, 9.0, 0.2),
        Habit("Primark", "👕", "Shopping", "PRIMARK SHEFFIELD", 6.0, 18.0, 0.12),
        Habit("Odeon", "🎬", "Entertainment", "ODEON SHEFFIELD", 6.99, 6.99, 0.1),
    ]
    income = [
        income_source("scholarship_living", "scholarship", 280.00, "monthly",
                      [*sch, working_day(date(2026, 11, 1))]),
        income_source("bursary_monthly", "bursary", 140.00, "monthly", [*bur, working_day(date(2026, 11, 15))]),
    ]
    return Profile(
        "scholarship", "Scholarship student",
        "Scholarship and bursary of about £420 a month. Halls paid by the scholarship. No debt, steady habits.",
        1101, "Amara Okoye", 312.40, ["scholarship", "bursary"],
        hints(True, 19, "rent", "plan_5", income, [], 15.99), habits, fixed,
    )


def rich() -> Profile:
    allowance = [working_day(date(2026, m, 1)) for m in (8, 9, 10)]
    fixed = [money_in(d, "R Ashworth", 2000.00, "ALLOWANCE FROM DAD") for d in allowance]
    fixed += [money_in(date(2026, 9, 12), "J Ashworth", 150.00, "from mum x"),
              money_in(date(2026, 10, 10), "J Ashworth", 100.00, "mum - treat yourself")]
    fixed += standing_order("City Living Lettings", 895.00, 1, "RENT FLAT 4B CALLS LANDING")
    subs = [("Netflix", "🍿", 12.99, 4), ("Spotify", "🎵", 12.99, 11), ("Disney Plus", "🏰", 9.99, 14),
            ("Amazon Prime", "📦", 8.99, 21), ("Apple", "☁️", 2.99, 2), ("Xbox", "🎮", 22.99, 18),
            ("Uber One", "🚗", 5.99, 23), ("YouTube Premium", "▶️", 12.99, 27), ("Deliveroo Plus", "🛵", 3.49, 8)]
    desc = {"Netflix": "NETFLIX.COM", "Spotify": "SPOTIFY PREMIUM", "Disney Plus": "DISNEYPLUS",
            "Amazon Prime": "AMAZON PRIME*MEMBERSHIP", "Apple": "APPLE.COM/BILL ICLOUD 200GB",
            "Xbox": "MICROSOFT*XBOX GAME PASS ULTIMATE", "Uber One": "UBER ONE MEMBERSHIP",
            "YouTube Premium": "GOOGLE*YOUTUBE PREMIUM", "Deliveroo Plus": "DELIVEROO PLUS"}
    for name, emoji, amount, day in subs:
        fixed += subscription(name, emoji, amount, day, desc[name])
    fixed += direct_debit("PureGym", "🏋️", 29.99, 1, "PUREGYM LEEDS CITY", "Personal care")
    plans = [(date(2026, 7, 25), "SELFRIDGES", 65.00), (date(2026, 8, 10), "JD SPORTS", 49.99),
             (date(2026, 9, 20), "ZARA", 40.00), (date(2026, 10, 3), "ASOS", 29.00)]
    for first, merchant, inst in plans:
        fixed += klarna_plan(first, merchant, inst)
    owed, due = klarna_remaining([(f, i) for f, _, i in plans])
    habits = [
        Habit("Deliveroo", "🛵", "Eating out", "DELIVEROO LEEDS", 17.0, 34.0, 2.5),
        Habit("Uber", "🚗", "Transport", "UBER *TRIP", 6.0, 16.0, 3.0),
        Habit("Pret A Manger", "🥪", "Eating out", "PRET A MANGER LEEDS", 3.5, 9.0, 4.0),
        Habit("Tesco", "🛒", "Groceries", "TESCO EXPRESS 2290 LEEDS", 6.0, 22.0, 1.5),
        Habit("M&S Food", "🛒", "Groceries", "M&S SIMPLY FOOD LEEDS", 12.0, 30.0, 0.8),
        Habit("Leeds University Union", "🍺", "Entertainment", "LEEDS UNI UNION BAR", 8.0, 26.0, 1.5,
              term_only=True),
        Habit("Revolution", "🍸", "Entertainment", "REVOLUTION LEEDS", 20.0, 55.0, 0.7),
        Habit("Nando's", "🍗", "Eating out", "NANDOS LEEDS", 16.0, 28.0, 0.6),
        Habit("ASOS", "👕", "Shopping", "ASOS.COM", 25.0, 70.0, 0.25),
        Habit("Starbucks", "☕", "Eating out", "STARBUCKS LEEDS", 3.8, 6.5, 1.0),
    ]
    income = [
        income_source("family_allowance", "family", 2000.00, "monthly",
                      [*allowance, working_day(date(2026, 11, 1))]),
    ]
    debts = [debt("bnpl_klarna", "bnpl", owed, 0.0, None, due)]
    monthly_costs = 895 + sum(s[2] for s in subs) + 29.99
    return Profile(
        "rich", "Rich student",
        "About £2,000 a month from parents. Rents a city flat, many subscriptions, Klarna for clothes.",
        2202, "Hugo Ashworth", 900.00, ["family"],
        hints(True, 20, "rent", "plan_5", income, debts, monthly_costs), habits, fixed,
    )


def working() -> Profile:
    loan_day = date(2026, 9, 28)
    fixed = [money_in(loan_day, "Student Loans Company", 1638.00, "SLC MAINTENANCE LOAN", "Bacs (Direct Credit)")]
    rng = random.Random(3303)
    fridays = weekly(4)
    for d in fridays:
        pay = rng.uniform(105, 165) if d < TERM_START else rng.uniform(60, 110)
        fixed.append(money_in(d, "JD Wetherspoon", pay, "JDW WAGES", "Bacs (Direct Credit)"))
    fixed += standing_order("Headrow Lettings", 460.00, 1, "RENT 14 BRUDENELL RD")
    fixed += [Tx(d, "19:00:00", "Faster payment", "Ellie Shaw", "", "Bills", -38.00, "bills share")
              for d in monthly(5)]
    fixed += subscription("Spotify", "🎵", 5.99, 12, "SPOTIFY STUDENT")
    fixed += subscription("Netflix", "🍿", 5.99, 17, "NETFLIX.COM")
    fixed += direct_debit("Smarty", "📱", 8.00, 6, "SMARTY MOBILE")
    fixed.append(Tx(date(2026, 9, 29), "09:00:00", "Faster payment", "Headrow Lettings", "", "Bills", -460.00,
                    "RENT ARREARS JULY"))
    fixed.append(card(date(2026, 10, 2), "Currys", "💻", "Shopping", 549.00, "CURRYS LEEDS LAPTOP"))
    fixed.append(card(date(2026, 10, 4), "Ticketmaster", "🎟️", "Entertainment", 68.00, "TICKETMASTER UK"))
    fixed.append(card(date(2026, 10, 10), "Ryanair", "✈️", "Holidays", 94.00, "RYANAIR LEEDS BRADFORD"))
    fixed.append(card(date(2026, 10, 3), "Leeds University Union", "📚", "Shopping", 42.50, "LEEDS UNI UNION SHOP"))
    habits = [
        Habit("Lidl", "🛒", "Groceries", "LIDL GB LEEDS", 14.0, 28.0, 1.0),
        Habit("Tesco", "🛒", "Groceries", "TESCO EXPRESS 4410 LEEDS", 3.0, 10.0, 1.5),
        Habit("Greggs", "🥐", "Eating out", "GREGGS 0331 LEEDS", 1.40, 4.50, 2.0),
        Habit("First Bus", "🚌", "Transport", "FIRST WEST YORKSHIRE", 3.00, 3.00, 1.0),
        Habit("Domino's", "🍕", "Eating out", "DOMINOS PIZZA LEEDS", 12.0, 22.0, 0.6),
        Habit("JD Wetherspoon", "🍺", "Entertainment", "JD WETHERSPOON LEEDS", 5.0, 16.0, 0.8),
        Habit("Co-op", "🛒", "Groceries", "CO-OP GROUP 070 LEEDS", 2.0, 8.0, 0.6),
        Habit("Steam", "🎮", "Entertainment", "STEAMGAMES.COM", 4.99, 19.99, 0.15),
    ]
    income = [
        income_source("maintenance_loan_slc", "maintenance_loan", 1638.00, "termly",
                      [loan_day, date(2027, 1, 18), date(2027, 4, 26)]),
        income_source("part_time_jdw", "part_time_job", 100.00, "weekly", fridays[-4:], END + timedelta(days=7)),
    ]
    return Profile(
        "working", "Working student",
        "Maintenance loan plus weekly bar shifts with pay that changes. Often in the overdraft.",
        3303, "Callum Reid", 35.00, ["maintenance_loan", "part_time_job"],
        hints(True, 21, "rent", "plan_5", income, [], 460 + 38 + 5.99 + 5.99 + 8), habits, fixed,
        overdraft_ear_pct=39.0,
    )


def commuter() -> Profile:
    grant_day = date(2026, 10, 5)
    fixed = [money_in(grant_day, "University of Manchester", 1000.00, "ACCESS GRANT TERM 1", "Bacs (Direct Credit)")]
    fridays = weekly(4)
    fixed += [money_in(d, "S Patel", 40.00, "Mum - train money", time="17:30:00") for d in fridays]
    fixed += pot([d + timedelta(days=1) for d in fridays], "House deposit", 25.00)
    fixed += pot([grant_day], "House deposit", 400.00)
    fixed.append(card(date(2026, 9, 14), "16-25 Railcard", "🎫", "Transport", 35.00, "RAILCARD.CO.UK 16-25 RAILCARD"))
    fixed += subscription("Spotify", "🎵", 5.99, 3, "SPOTIFY STUDENT")
    fixed += subscription("Amazon Prime", "📦", 4.49, 19, "AMAZON PRIME STUDENT", "Shopping")
    habits = [
        Habit("Northern", "🚆", "Transport", "NORTHERN TRAINS BOLTON-MANCHESTER", 6.20, 6.20, 0.6,
              end=date(2026, 9, 13)),
        Habit("Northern", "🚆", "Transport", "NORTHERN TRAINS BOLTON-MANCHESTER", 4.10, 4.10, 4.0,
              weekdays_only=True, start=TERM_START),
        Habit("Tesco", "🛒", "Eating out", "TESCO EXPRESS OXFORD RD", 3.85, 3.85, 1.5, term_only=True,
              weekdays_only=True),
        Habit("Greggs", "🥐", "Eating out", "GREGGS MANCHESTER PICC", 1.40, 4.25, 0.7),
        Habit("Manchester Students' Union", "☕", "Eating out", "MANCHESTER SU CAFE", 1.80, 3.20, 0.8,
              term_only=True),
        Habit("Primark", "👕", "Shopping", "PRIMARK BOLTON", 6.0, 20.0, 0.15),
        Habit("Boots", "💊", "Personal care", "BOOTS BOLTON", 3.0, 10.0, 0.2),
        Habit("Vue", "🎬", "Entertainment", "VUE BOLTON", 7.49, 7.49, 0.1),
    ]
    income = [
        income_source("grant_access", "grant", 1000.00, "termly", [grant_day, date(2027, 2, 1), date(2027, 4, 26)]),
        income_source("family_mum", "family", 40.00, "weekly", fridays[-4:], END + timedelta(days=7)),
    ]
    return Profile(
        "commuter", "Commuter student",
        "Lives with family and takes the train in with a 16-25 Railcard. Grant plus family help. Saving for a deposit.",
        4404, "Priya Patel", 410.00, ["grant", "family"],
        hints(True, 19, "parents", "plan_5", income, [], 5.99 + 4.49 + 4 * 4.10 * 4.33), habits, fixed,
    )


def team1() -> Profile:
    loan_day = date(2026, 9, 28)
    fixed = [money_in(loan_day, "Student Loans Company", 3450.00, "SLC MAINTENANCE LOAN", "Bacs (Direct Credit)")]
    rng = random.Random(5505)
    fridays = weekly(4)
    for d in fridays:
        fixed.append(money_in(d, "Bean There Cafe Ltd", rng.uniform(95, 140), "PAYROLL", "Bacs (Direct Credit)"))
    fixed.append(card(date(2026, 10, 1), "University of York", "🏠", "Bills", 2350.00, "UOY ACCOMMODATION TERM 1",
                      type_="Faster payment"))
    fixed += subscription("Spotify", "🎵", 5.99, 7, "SPOTIFY STUDENT")
    fixed += subscription("Amazon Prime", "📦", 4.49, 15, "AMAZON PRIME STUDENT", "Shopping")
    habits = [
        Habit("York Students' Union", "🍺", "Entertainment", "YUSU BAR YORK", 5.0, 20.0, 2.0, term_only=True),
        Habit("Deliveroo", "🛵", "Eating out", "DELIVEROO YORK", 15.0, 26.0, 1.0),
        Habit("Tesco", "🛒", "Groceries", "TESCO STORES YORK", 8.0, 25.0, 1.5),
        Habit("Nando's", "🍗", "Eating out", "NANDOS YORK", 14.0, 22.0, 0.4),
        Habit("Uber", "🚗", "Transport", "UBER *TRIP", 6.0, 12.0, 0.5),
        Habit("Greggs", "🥐", "Eating out", "GREGGS YORK", 1.40, 4.50, 1.2),
    ]
    income = [
        income_source("maintenance_loan_slc", "maintenance_loan", 3450.00, "termly",
                      [loan_day, date(2027, 1, 18), date(2027, 4, 26)]),
        income_source("part_time_cafe", "part_time_job", 118.00, "weekly", fridays[-4:], END + timedelta(days=7)),
    ]
    return Profile(
        "team1", "Fresher in halls",
        "First year in halls. Maintenance loan and weekly cafe shifts. Freshers' spending is high.",
        5505, "Leo Grant", 260.00, ["maintenance_loan", "part_time_job"],
        hints(True, 18, "rent", "plan_5", income, [], 2350 / 3 + 5.99 + 4.49), habits, fixed, team=True,
    )


def team2() -> Profile:
    paydays = [last_friday(2026, m) for m in (7, 8, 9)]
    fixed = [money_in(d, "Northwind Analytics Ltd", 2145.60, "SALARY", "Bacs (Direct Credit)") for d in paydays]
    fixed += standing_order("Ancoats Lettings", 725.00, 1, "RENT APT 12 MURRAYS MILLS")
    fixed += direct_debit("Manchester City Council", "🏛️", 118.00, 1, "MANCHESTER CC COUNCIL TAX")
    fixed += direct_debit("Octopus Energy", "⚡", 64.00, 12, "OCTOPUS ENERGY")
    fixed += direct_debit("Hyperoptic", "🌐", 25.00, 9, "HYPEROPTIC BROADBAND")
    fixed += direct_debit("VOXI", "📱", 10.00, 20, "VOXI MOBILE")
    fixed += subscription("Netflix", "🍿", 12.99, 6, "NETFLIX.COM")
    fixed += subscription("Spotify", "🎵", 12.99, 16, "SPOTIFY PREMIUM")
    fixed += direct_debit("PureGym", "🏋️", 24.99, 1, "PUREGYM MANCHESTER", "Personal care")
    fixed += pot([d + timedelta(days=1) for d in paydays], "Emergency fund", 300.00)
    habits = [
        Habit("Tesco", "🛒", "Groceries", "TESCO STORES MANCHESTER", 10.0, 35.0, 1.5),
        Habit("Pret A Manger", "🥪", "Eating out", "PRET A MANGER MANCHESTER", 3.5, 8.0, 2.0, weekdays_only=True),
        Habit("Bee Network", "🚌", "Transport", "BEE NETWORK BUS", 2.00, 2.00, 5.0, weekdays_only=True),
        Habit("Dishoom", "🍛", "Eating out", "DISHOOM MANCHESTER", 18.0, 40.0, 0.5),
        Habit("Amazon", "📦", "Shopping", "AMAZON.CO.UK", 8.0, 35.0, 0.4),
    ]
    income = [income_source("salary_northwind", "salary", 2145.60, "monthly",
                             [*paydays, last_friday(2026, 10)])]
    return Profile(
        "team2", "Graduate, first job",
        "Graduated last year. Monthly salary, rent and bills, saves into an emergency pot. Repaying a Plan 2 loan.",
        6606, "Maya Collins", 1180.00, ["salary"],
        hints(False, 23, "rent", "plan_2", income, [], 725 + 118 + 64 + 25 + 10 + 12.99 + 12.99 + 24.99),
        habits, fixed, team=True,
    )


def team3() -> Profile:
    paydays = [last_working_day(2026, m) for m in (7, 8, 9)]
    fixed = [money_in(d, "Severnside Engineering Ltd", 1640.00, "SALARY PLACEMENT", "Bacs (Direct Credit)")
             for d in paydays]
    bursary_day = date(2026, 10, 9)
    fixed.append(money_in(bursary_day, "University of Bath", 500.00, "PLACEMENT BURSARY", "Bacs (Direct Credit)"))
    fixed += standing_order("Clifton Student Lets", 650.00, 1, "RENT 3 ST PAULS RD")
    fixed += subscription("Disney Plus", "🏰", 4.99, 10, "DISNEYPLUS")
    fixed += subscription("Spotify", "🎵", 12.99, 22, "SPOTIFY PREMIUM")
    fixed += subscription("Amazon Prime", "📦", 8.99, 3, "AMAZON PRIME*MEMBERSHIP", "Shopping")
    fixed += direct_debit("EE", "📱", 18.00, 14, "EE LIMITED")
    fixed += pot([d + timedelta(days=1) for d in paydays], "Final year fund", 150.00)
    habits = [
        Habit("First Bus", "🚌", "Transport", "FIRST BRISTOL DAY TICKET", 4.50, 4.50, 5.0, weekdays_only=True),
        Habit("Sainsbury's", "🛒", "Groceries", "SAINSBURYS BRISTOL", 12.0, 40.0, 1.2),
        Habit("Pret A Manger", "🥪", "Eating out", "PRET A MANGER BRISTOL", 3.5, 7.5, 1.0, weekdays_only=True),
        Habit("The Stag and Hounds", "🍺", "Entertainment", "STAG AND HOUNDS BRISTOL", 6.0, 24.0, 0.8),
        Habit("Boots", "💊", "Personal care", "BOOTS BRISTOL", 3.0, 12.0, 0.2),
    ]
    income = [
        income_source("salary_placement", "salary", 1640.00, "monthly", [*paydays, last_working_day(2026, 10)]),
        income_source("bursary_placement", "bursary", 500.00, "termly", [bursary_day, date(2027, 2, 5)]),
    ]
    return Profile(
        "team3", "Placement year",
        "Year in industry. Monthly placement salary plus a university bursary. Saves for final year.",
        7707, "Josh Bennett", 730.00, ["salary", "bursary"],
        hints(True, 21, "rent", "plan_5", income, [], 650 + 4.99 + 12.99 + 8.99 + 18 + 4.5 * 21.7),
        habits, fixed, team=True,
    )


def team4() -> Profile:
    rng = random.Random(8808)
    mondays = weekly(0)
    fixed = [money_in(d, "Roofoods Ltd", rng.uniform(45, 180), "DELIVEROO RIDER PAYMENT", "Bacs (Direct Credit)")
             for d in mondays]
    dad = monthly(28)
    fixed += [money_in(d, "M Okafor", 300.00, "Dad - rent help") for d in dad]
    fixed += standing_order("Nottingham Student Homes", 430.00, 1, "RENT 22 LENTON BLVD")
    fixed += subscription("Spotify", "🎵", 5.99, 8, "SPOTIFY STUDENT")
    fixed += subscription("Xbox", "🎮", 14.99, 12, "MICROSOFT*XBOX GAME PASS")
    fixed += subscription("Netflix", "🍿", 5.99, 25, "NETFLIX.COM")
    fixed += direct_debit("PureGym", "🏋️", 21.99, 1, "PUREGYM NOTTINGHAM", "Personal care")
    plans = [(date(2026, 8, 30), "CURRYS", 83.00), (date(2026, 9, 25), "NIKE", 33.33)]
    for first, merchant, inst in plans:
        fixed += klarna_plan(first, merchant, inst)
    owed, due = klarna_remaining([(f, i) for f, _, i in plans])
    habits = [
        Habit("McDonald's", "🍔", "Eating out", "MCDONALDS NOTTINGHAM", 4.0, 10.0, 2.0),
        Habit("Tesco", "🛒", "Groceries", "TESCO EXPRESS LENTON", 4.0, 18.0, 1.5),
        Habit("Co-op", "🥤", "Groceries", "CO-OP GROUP NOTTINGHAM", 1.5, 4.0, 2.0),
        Habit("Nottingham Students' Union", "🍺", "Entertainment", "NOTTS SU BAR", 5.0, 15.0, 0.5, term_only=True),
        Habit("Halfords", "🚲", "Transport", "HALFORDS NOTTINGHAM", 6.0, 25.0, 0.2),
    ]
    income = [
        income_source("gig_deliveroo", "part_time_job", 110.00, "weekly", mondays[-4:], END + timedelta(days=4)),
        income_source("family_dad", "family", 300.00, "monthly", [*dad, working_day(date(2026, 10, 28))]),
    ]
    debts = [debt("bnpl_klarna", "bnpl", owed, 0.0, None, due)]
    return Profile(
        "team4", "Delivery rider",
        "Rides for Deliveroo with pay that changes each week, gets rent help from family, and uses Klarna.",
        8808, "Tobi Okafor", 120.00, ["part_time_job", "family"],
        hints(True, 20, "rent", "plan_5", income, debts, 430 + 5.99 + 14.99 + 5.99 + 21.99), habits, fixed,
        team=True,
    )


PROFILES = [scholarship, rich, working, commuter, team1, team2, team3, team4]
# Money already in savings pots on the first statement day. Pot balance at the end = this + pot transfers.
OPENING_POTS = {"scholarship": 150.00, "commuter": 820.00, "team2": 1500.00, "team3": 600.00}


# ---------- simulation ---------------------------------------------------------------------------


def _time(rng: random.Random) -> str:
    return f"{rng.randint(7, 22):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"


def simulate(p: Profile) -> list[Tx]:
    rng = random.Random(p.seed)
    by_day: dict[date, list[Tx]] = {}
    for t in p.fixed:
        by_day.setdefault(t.day, []).append(t)
    for d in days():
        for h in p.habits:
            if h.term_only and d < TERM_START:
                continue
            if h.weekdays_only and d.weekday() >= 5:
                continue
            if (h.start and d < h.start) or (h.end and d > h.end):
                continue
            if rng.random() < h.per_week / (5 if h.weekdays_only else 7):
                amount = h.lo if h.lo == h.hi else rng.uniform(h.lo, h.hi)
                by_day.setdefault(d, []).append(card(d, h.name, h.emoji, h.category, amount, h.description,
                                                     _time(rng)))
    out: list[Tx] = []
    balance = p.opening_balance
    accrued = 0.0
    daily = (1 + (p.overdraft_ear_pct or 0) / 100) ** (1 / 365) - 1
    for d in days():
        todays = sorted(by_day.get(d, []), key=lambda t: t.time)
        if d.day == 1 and accrued >= 0.01:
            todays.insert(0, Tx(d, "00:30:00", "Overdraft", "Monzo", "", "Bills", -round(accrued, 2),
                                f"Overdraft interest, {p.overdraft_ear_pct:g}% EAR"))
            accrued = 0.0
        for t in todays:
            balance = round(balance + t.amount, 2)
            t.balance = balance
            out.append(t)
        if balance < 0 and p.overdraft_ear_pct:
            accrued += -balance * daily
    return out


def tx_id(p: Profile, i: int, t: Tx) -> str:
    return "tx_0000" + hashlib.sha256(f"{p.id}|{i}|{t.day}|{t.amount}|{t.description}".encode()).hexdigest()[:18]


# ---------- CSV ----------------------------------------------------------------------------------


def to_csv(p: Profile, txs: list[Tx]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(MONZO_HEADER)
    for i, t in enumerate(txs):
        amt = f"{t.amount:.2f}"
        w.writerow([tx_id(p, i, t), t.day.strftime("%d/%m/%Y"), t.time, t.type, t.name, t.emoji, t.category, amt,
                    "GBP", amt, "GBP", "", "", "", t.description, "", amt if t.amount < 0 else "",
                    amt if t.amount > 0 else ""])
    return buf.getvalue().encode("utf-8")


# ---------- PDF (minimal writer, Helvetica, WinAnsiEncoding) -------------------------------------

# Helvetica advance widths (1/1000 em) for the characters used in numbers.
_NUM_W = {**dict.fromkeys("0123456789", 556), ".": 278, ",": 278, "-": 333, "+": 584, "£": 556, " ": 278}


def _num_width(text: str, size: float) -> float:
    return sum(_NUM_W.get(c, 556) for c in text) * size / 1000


def _pdf_str(text: str) -> str:
    raw = text.encode("cp1252", "replace")
    out = []
    for b in raw:
        ch = chr(b)
        if ch in "()\\":
            out.append("\\" + ch)
        elif 32 <= b < 127:
            out.append(ch)
        else:
            out.append(f"\\{b:03o}")
    return "(" + "".join(out) + ")"


def _row(cells: list[tuple[float, float, str, str, float]]) -> str:
    """One BT..ET block per table row: each cell is (x, y, font, text, size). The parser reads one row per block."""
    parts = ["BT"]
    for x, y, font, text, size in cells:
        parts.append(f"/{font} {size:g} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm {_pdf_str(text)} Tj")
    parts.append("ET")
    return "\n".join(parts)


def _money(v: float) -> str:
    return f"{v:,.2f}"


def to_pdf(p: Profile, txs: list[Tx]) -> bytes:
    width, height, left, right = 595.0, 842.0, 40.0, 555.0
    first_page_rows, rows_per_page = 44, 55  # page 1 has the summary block
    pages_rows = [txs[:first_page_rows]] + [txs[i:i + rows_per_page]
                                            for i in range(first_page_rows, len(txs), rows_per_page)]
    money_in_total = sum(t.amount for t in txs if t.amount > 0)
    money_out_total = -sum(t.amount for t in txs if t.amount < 0)
    closing = txs[-1].balance if txs else p.opening_balance
    streams: list[str] = []
    for n, chunk in enumerate(pages_rows, start=1):
        ops: list[str] = []
        y = height - 50
        if n == 1:
            ops.append(_row([(left, y, "F2", "Monzo", 20)]))
            y -= 22
            ops.append(_row([(left, y, "F2", "Current account statement", 12)]))
            y -= 16
            ops.append(_row([(left, y, "F1", "Sample data. Synthetic statement for a demo. Not a real person or "
                                             "account.", 8)]))
            y -= 20
            ops.append(_row([(left, y, "F1", f"Account holder: {p.holder}", 9)]))
            y -= 13
            ops.append(_row([(left, y, "F1", f"Period: {START.strftime('%d/%m/%Y')} to {END.strftime('%d/%m/%Y')}",
                              9)]))
            y -= 13
            for label, value in (("Opening balance", p.opening_balance), ("Money in", money_in_total),
                                 ("Money out", money_out_total), ("Closing balance", closing)):
                text = _money(value)
                ops.append(_row([(left, y, "F1", label, 9), (200 - _num_width(text, 9), y, "F1", text, 9)]))
                y -= 12
            y -= 10
        ops.append(_row([(left, y, "F2", "Date", 9), (110, y, "F2", "Description", 9),
                         (430 - _num_width("Amount (GBP)", 9) * 1.1, y, "F2", "Amount (GBP)", 9),
                         (right - _num_width("Balance (GBP)", 9) * 1.1, y, "F2", "Balance (GBP)", 9)]))
        y -= 14
        for t in chunk:
            desc = t.name if t.description.upper() == t.name.upper() else f"{t.name} - {t.description}"
            amt, bal = _money(t.amount), _money(t.balance)
            ops.append(_row([(left, y, "F1", t.day.strftime("%d/%m/%Y"), 8), (110, y, "F1", desc[:62], 8),
                             (430 - _num_width(amt, 8), y, "F1", amt, 8),
                             (right - _num_width(bal, 8), y, "F1", bal, 8)]))
            y -= 13
        ops.append(_row([(left, 30, "F1", f"Page {n} of {len(pages_rows)}. Sample data.", 7)]))
        streams.append("\n".join(ops))

    objects: list[bytes] = []
    n_pages = len(streams)
    page_ids = [5 + 2 * i for i in range(n_pages)]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] /Count {n_pages} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    for i, s in enumerate(streams):
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:g} {height:g}] "
                       f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {page_ids[i] + 1} 0 R >>".encode())
        data = zlib.compress(s.encode("latin-1"), 9)
        objects.append(f"<< /Length {len(data)} /Filter /FlateDecode >>\nstream\n".encode() + data
                       + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info << /Title (Sample statement {p.id}) "
            f"/Producer (gen_statements.py) >> >>\nstartxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


# ---------- main ---------------------------------------------------------------------------------


def build(out_dir: Path) -> list[dict[str, object]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for make in PROFILES:
        p = make()
        txs = simulate(p)
        closing = txs[-1].balance
        h = dict(p.hints)
        debts = list(h["debts"])  # type: ignore[call-overload]
        if p.overdraft_ear_pct is not None:
            debts.append(debt("overdraft", "overdraft", max(0.0, -closing), p.overdraft_ear_pct, 0.0))
        h["debts"] = debts
        pots = round(OPENING_POTS.get(p.id, 0.0) - sum(t.amount for t in txs if t.type == "Pot transfer"), 2)
        # Shape of lifeline_contracts.finance.Account. The CSV has no balance column, so the API takes it from here.
        accounts: list[dict[str, object]] = [{"id": "monzo_current", "name": "Monzo Current Account",
                                              "kind": "current", "provider": "Monzo", "balance": closing}]
        if pots > 0:
            accounts.append({"id": "monzo_savings", "name": "Monzo Pots", "kind": "savings", "provider": "Monzo",
                             "balance": pots})
        h["accounts"] = accounts
        (out_dir / f"{p.id}.csv").write_bytes(to_csv(p, txs))
        (out_dir / f"{p.id}.pdf").write_bytes(to_pdf(p, txs))
        index.append({"id": p.id, "title": p.title, "description": p.description, "funding": p.funding,
                      "months": MONTHS, "team": p.team, "hints": h})
        print(f"{p.id:12s} rows={len(txs):4d} closing={closing:9.2f} min={min(t.balance for t in txs):9.2f}")
    (out_dir / "index.json").write_text(json.dumps({"samples": index}, indent=2,
                                                   ensure_ascii=False) + "\n")
    return index


if __name__ == "__main__":
    if len(sys.argv) > 1:
        build(Path(sys.argv[1]))
    else:
        for target in OUTPUT_DIRS:
            build(target)
