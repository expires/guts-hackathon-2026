"""The 10 sample students (PENNY_V3_BUILD.md A, ADR 0072). W1 owns this file. Pure and deterministic.

No network, no clock, standard library only. `statement(id, end)` builds one student's statement from
1 July 2026 to `end` (the day before the import). The import passes yesterday, so the data is never stale.
The demo files (CSV, PDF, index.json) are built for the fixed reference day REF_DAY by tools/gen_statements.py.

Rules (A1):
- Every income, rent and price figure has a source in `Profile.sources` (figure, value, source, url, checked date),
  or is marked "example within <source> range" with the range.
- Funding: SFE 2026/27 maximum loans from gov.uk; household-income taper is a simple example method (TAPER below).
  SAAS: £9,400 loan + £2,000 Young Students' Bursary. Minimum wage £12.71 (21+) and £10.85 (18 to 20).
  Tax and NI: one month on its own (month 1 basis), 20% over £1,047.50 and 8% over £1,047.50.
- Spending is real transactions: real UK merchants, groceries 2 to 3 times a week at £6 to £35, a bigger shop after
  money arrives, going out on Thursday to Saturday, a spike in the 7 days after a loan or pay, September higher,
  bills and subscriptions on fixed dates, rent once per period.
- Calibration: each category's monthly amount is set so the September non-rent total equals the A3 target
  (university average x profile multiplier); amounts are drawn, then scaled to that amount.
- Randomness: one random.Random per (student, month, category), so a month's rows do not change when the
  statement end moves. Rows after `end` are cut.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

REF_DAY = date(2026, 10, 18)  # reference import day for the demo files
REF_END = REF_DAY - timedelta(days=1)
START = date(2026, 7, 1)
CHECKED = "2026-10-18"
BANK_HOLIDAYS = {date(2026, 8, 31), date(2026, 12, 25), date(2026, 12, 28), date(2027, 1, 1), date(2027, 3, 26),
                 date(2027, 3, 29), date(2027, 5, 3), date(2027, 5, 31)}  # England and Wales

# ---------- sources (A2, A3) -----------------------------------------------------------------------

NSMS_URL = "https://www.savethestudent.org/money/student-budgeting/what-do-students-spend-their-money-on.html"
NSAS_URL = "https://www.savethestudent.org/money/surveys/national-student-accommodation-survey-2026.html"
NLW_URL = "https://www.gov.uk/government/news/national-living-wage-increases-to-1271-per-hour"
SFE_URL = "https://www.gov.uk/student-finance/new-fulltime-students"
SAAS_URL = "https://www.saas.gov.uk"
NSMS = "Save the Student, National Student Money Survey 2026"
NSAS = "Save the Student, National Student Accommodation Survey 2026"
NLW = "gov.uk, National Living Wage from 1 April 2026"
SFE = "gov.uk, Student Finance England 2026/27"
SAAS = "SAAS 2026/27 (saas.gov.uk)"

SFE_MAX_AWAY = 10_830.00  # away from home, outside London (A2)
SFE_MAX_HOME = 9_118.00  # living with parents (A2)
TAPER_START = 25_000.00  # example method: full loan up to this household income
TAPER = 7.08  # example method: £1 less for every £7.08 of household income above TAPER_START
WAGE_21 = 12.71
WAGE_18_20 = 10.85
SAAS_LOAN = 9_400.00
SAAS_YSB = 2_000.00
PERSONAL_ALLOWANCE_MONTH = 1_047.50  # £12,570 / 12
NI_THRESHOLD_MONTH = 1_047.50  # £12,570 / 12
BASIC_RATE = 0.20
NI_RATE = 0.08

# A3: university non-rent spending a month (NSMS 2026).
UNI_SPEND = {"Sheffield": 538.0, "Edinburgh": 637.0, "Manchester": 490.0, "Newcastle": 455.0, "Leeds": 549.0,
             "Birmingham": 577.0, "Warwick": 429.0, "Exeter": 443.0}

# SFE term payments (example dates within the SFE rule "paid at the start of each term").
SFE_TERM2 = date(2027, 1, 11)
SFE_TERM3 = date(2027, 4, 19)


def sfe_loan(household: float, home: bool = False) -> float:
    """Simple SFE maintenance loan from household income: full up to £25,000, then the taper. Never above the max."""
    top = SFE_MAX_HOME if home else SFE_MAX_AWAY
    cut = max(0.0, household - TAPER_START) / TAPER
    return round(max(top * 0.45, min(top, top - cut)), 2)


def thirds(total: float) -> list[float]:
    a = round(total / 3, 2)
    return [a, a, round(total - 2 * a, 2)]


def net_month(gross: float, pension: float = 0.0) -> tuple[float, float, float]:
    """(tax, ni, net) for one month, month 1 basis. Pension is taken before tax (net pay arrangement)."""
    tax = round(max(0.0, gross - pension - PERSONAL_ALLOWANCE_MONTH) * BASIC_RATE, 2)
    ni = round(max(0.0, gross - NI_THRESHOLD_MONTH) * NI_RATE, 2)
    return tax, ni, round(gross - pension - tax - ni, 2)


# ---------- dates -----------------------------------------------------------------------------------


def working_day(d: date) -> date:
    """BACS rule: a payment due on a weekend or bank holiday lands on the next working day."""
    while d.weekday() >= 5 or d in BANK_HOLIDAYS:
        d += timedelta(days=1)
    return d


def prev_working_day(d: date) -> date:
    """Payroll rule: a payday on a weekend or bank holiday moves to the working day before."""
    while d.weekday() >= 5 or d in BANK_HOLIDAYS:
        d -= timedelta(days=1)
    return d


def last_working_day(year: int, month: int) -> date:
    return prev_working_day(month_end(date(year, month, 1)))


def month_end(d: date) -> date:
    nxt = date(d.year + d.month // 12, d.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


HORIZON = date(2027, 6, 30)  # schedules are known to the end of the 2026/27 year


def monthly(day: int, start: date = START, end: date = HORIZON, adjust: bool = True) -> list[date]:
    out = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        d = date(y, m, min(day, 28))
        d = working_day(d) if adjust else d
        if start <= d <= end:
            out.append(d)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def weekly(weekday: int, start: date = START, end: date = HORIZON) -> list[date]:
    first = start + timedelta(days=(weekday - start.weekday()) % 7)
    return [first + timedelta(days=7 * i) for i in range((end - first).days // 7 + 1)]


def month_starts(start: date, end: date) -> list[date]:
    out, y, m = [], start.year, start.month
    while date(y, m, 1) <= end:
        out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


# ---------- model -----------------------------------------------------------------------------------

# Row kinds. Non-rent spending = every row out except "rent", "savings".
RENT, BILL, SUB, SPEND, ONE_OFF, BNPL, SAVINGS, INCOME = (
    "rent", "bill", "subscription", "spend", "one_off", "bnpl", "savings", "income")


@dataclass
class Tx:
    day: date
    time: str
    type: str
    name: str
    category: str  # the statement's own category label (CSV column)
    amount: float
    description: str
    kind: str
    stream: str | None = None  # income stream id for money in
    balance: float = 0.0


@dataclass
class Merchant:
    name: str
    description: str
    lo: float
    hi: float
    weight: float = 1.0


@dataclass
class Spend:
    """One everyday spending category. `share` of the student's variable spending; `per_week` purchases a week."""

    category: str
    share: float
    per_week: float
    merchants: list[Merchant]
    days: str = "any"  # any | thu_sat (nights out) | weekdays (commute) | weekend_heavy (eating out)
    term_only: bool = False
    clamp: tuple[float, float] | None = None  # allowed amount range after scaling


@dataclass
class Stream:
    """One way money arrives. `dates` covers the 2026/27 year; rows appear up to the statement end."""

    id: str
    kind: str  # lifeline_contracts.finance.IncomeKind
    schedule: str  # IncomeSchedule
    payer: str
    description: str
    dates: list[date]
    amounts: list[float]
    type: str = "Bacs (Direct Credit)"


@dataclass
class Fixed:
    """A payment out on fixed dates: rent, a bill, a subscription, a savings transfer or a one-off."""

    kind: str
    name: str
    category: str
    amount: float
    description: str
    dates: list[date]
    type: str = "Direct Debit"
    time: str = "06:00:00"


@dataclass
class Source:
    figure: str
    value: str
    source: str
    url: str | None
    note: str | None = None  # "example within <source> range: ..." when no official figure is given
    ref: str | None = None  # income stream id, "rent" or a fixed name the figure belongs to

    def as_dict(self) -> dict[str, object]:
        return {"figure": self.figure, "value": self.value, "source": self.source, "url": self.url,
                "checked": CHECKED, "example": self.note, "ref": self.ref}


@dataclass
class Card:
    avatar: str
    uni: str | None
    university: str | None  # A3 row
    city: str
    region: str
    funding_label: str
    housing: str
    money_in: list[tuple[str, str, str, str, int, bool]]  # label, stream id, period, dates, divisor, varies


@dataclass
class Profile:
    id: str
    title: str
    description: str
    seed: int
    holder: str
    age: int
    is_student: bool
    housing: str
    plan: str
    bank: str
    current_name: str
    savings_name: str | None
    closing_ref: float  # current account balance at REF_END; the opening balance is derived from it
    savings_open: float
    target: float  # September non-rent spending (A3 x multiplier, or A4)
    multiplier: float | None
    month_factor: dict[int, float]  # variable spending per month as a share of September's
    spends: list[Spend]
    streams: list[Stream]
    fixed: list[Fixed]
    sources: list[Source]
    card: Card
    budgets: list[tuple[str, float]]  # engine category, multiplier of the Aug/Sep average
    goals: list[tuple[str, str, float, str, bool]]  # name, emoji, target, date, from savings
    expected_state: str
    term_start: date = date(2026, 9, 21)
    lean: list[tuple[date, date]] = field(default_factory=list)  # low-money windows: fewer purchases
    overdraft_limit: float | None = None
    funding: list[str] = field(default_factory=list)


def fixed_monthly(kind: str, name: str, category: str, amount: float, day: int, description: str,
                  start: date = START, end: date = HORIZON, type_: str = "Direct Debit", adjust: bool = True,
                  time: str = "06:00:00") -> Fixed:
    return Fixed(kind, name, category, amount, description, monthly(day, start, end, adjust), type_, time)


def rent(name: str, amount: float, description: str, start: date = START, day: int = 1) -> Fixed:
    return fixed_monthly(RENT, name, "Housing", amount, day, description, start, type_="Standing order",
                         time="07:00:00")


def sub(name: str, amount: float, day: int, description: str, start: date = START) -> Fixed:
    return fixed_monthly(SUB, name, "Subscriptions", amount, day, description, start, type_="Card payment",
                         adjust=False, time="04:10:00")


def one_off(day: date, name: str, category: str, amount: float, description: str) -> Fixed:
    return Fixed(ONE_OFF, name, category, amount, description, [day], "Card payment", "14:20:00")


def to_savings(dates: list[date], amount: float, product: str) -> Fixed:
    return Fixed(SAVINGS, product, "Savings", amount, f"TO {product.upper()}", dates, "Transfer", "08:00:00")


def g(name: str, desc: str, lo: float, hi: float, weight: float = 1.0) -> Merchant:
    return Merchant(name, desc, lo, hi, weight)


GROCERY_CLAMP = (6.0, 35.0)


# ---------- the 10 students (A4) --------------------------------------------------------------------


def _common_sources(uni: str | None, target: float, multiplier: float | None) -> list[Source]:
    out = []
    if uni is not None and multiplier is not None:
        value = (f"£{target:,.0f} (A4: {uni} £{UNI_SPEND[uni]:,.0f} x {multiplier:g} = "
                 f"£{UNI_SPEND[uni] * multiplier:,.0f}, rounded)")
        out.append(Source("September non-rent spending target", value, NSMS, NSMS_URL, ref="target"))
    else:
        out.append(Source("September non-rent spending target", f"£{target:,.0f} (A4)", NSMS, NSMS_URL,
                          "example within NSMS 2026 range (average non-rent spending £595 a month)", ref="target"))
    out.append(Source("Shop prices and purchase sizes", "per merchant", NSMS, NSMS_URL,
                      "example within NSMS 2026 category averages (groceries £155, transport £73, bills £68, "
                      "going out £60, eating out £45, clothes £33 a month)", ref="prices"))
    return out


def _sfe_sources(stream: str, annual: float, household: float | None, home: bool) -> list[Source]:
    top = SFE_MAX_HOME if home else SFE_MAX_AWAY
    where = "living at home" if home else "away from home, outside London"
    if household is None or household <= TAPER_START:
        return [Source(f"SFE maintenance loan 2026/27 ({where})", f"£{annual:,.2f} a year (maximum £{top:,.0f})",
                       SFE, SFE_URL, ref=stream),
                Source("SFE payment dates", "3 payments, at the start of each term", SFE, SFE_URL,
                       "example within SFE schedule (start of each term): dates chosen per university", ref=stream)]
    return [Source(f"SFE maintenance loan 2026/27 ({where}), household income £{household:,.0f}",
                   f"£{annual:,.2f} a year = £{top:,.0f} - (£{household:,.0f} - £25,000) / {TAPER:g}", SFE, SFE_URL,
                   f"example within SFE range (maximum £{top:,.0f}): simple taper, £1 less per £{TAPER:g} of "
                   "household income above £25,000", ref=stream),
            Source("SFE payment dates", "3 payments, at the start of each term", SFE, SFE_URL,
                   "example within SFE schedule (start of each term): dates chosen per university", ref=stream)]


def _rent_source(value: str, region_avg: str, note: str | None = None) -> Source:
    return Source("Rent", value, NSAS, NSAS_URL, note or f"example within NSAS 2026 range ({region_avg})", ref="rent")


def amara() -> Profile:
    loan = SFE_MAX_AWAY
    t = thirds(loan)
    sfe = Stream("maintenance_loan_sfe", "maintenance_loan", "termly", "Student Loans Company",
                 "SLC MAINTENANCE LOAN", [date(2026, 9, 21), SFE_TERM2, SFE_TERM3], t)
    bursary = Stream("bursary_sheffield", "bursary", "termly", "University of Sheffield",
                     "UNIVERSITY OF SHEFFIELD BURSARY", [date(2026, 10, 9), date(2027, 2, 12)], [500.00, 500.00])
    halls_week = 139.00
    instalment = round(halls_week * 39 / 3, 2)
    fixed = [
        Fixed(RENT, "University of Sheffield", "Housing", instalment, "UNIVERSITY OF SHEFFIELD ACCOMMODATION RENT",
              [date(2026, 10, 5), date(2027, 1, 18), date(2027, 4, 26)], "Faster payment", "09:00:00"),
        fixed_monthly(BILL, "giffgaff", "Bills", 10.00, 5, "GIFFGAFF MOBILE"),
        sub("Spotify", 5.99, 9, "SPOTIFY STUDENT"),
        one_off(date(2026, 9, 23), "Blackwell's", "Education", 32.99, "BLACKWELLS SHEFFIELD BOOKS"),
        to_savings([date(2026, 9, 22), date(2026, 10, 10)], 150.00, "Flex Instant Saver"),
        to_savings(monthly(2, date(2026, 7, 1), HORIZON), 25.00, "Flex Instant Saver"),
    ]
    spends = [
        Spend("Groceries", 0.50, 2.6, [g("Aldi", "ALDI 112 SHEFFIELD", 12, 32, 2), g("Tesco", "TESCO EXPRESS "
              "3125 SHEFFIELD", 6, 15), g("Co-op", "CO-OP GROUP 412 SHEFFIELD", 6, 14)], clamp=GROCERY_CLAMP),
        Spend("Eating out", 0.13, 1.5, [g("Greggs", "GREGGS 1214 SHEFFIELD", 2.2, 6.5, 2),
              g("Sheffield Students' Union", "SHEFFIELD SU CAFE", 2.5, 6.0)], "weekend_heavy"),
        Spend("Transport", 0.16, 2.0, [g("Stagecoach", "STAGECOACH YORKSHIRE", 2.0, 4.5)], "weekdays"),
        Spend("Entertainment", 0.07, 0.4, [g("Odeon", "ODEON SHEFFIELD", 6.5, 9.0), g("The Leadmill",
              "THE LEADMILL SHEFFIELD", 6.0, 12.0)], "thu_sat"),
        Spend("Shopping", 0.09, 0.3, [g("Primark", "PRIMARK SHEFFIELD", 8, 25)]),
        Spend("Health", 0.05, 0.3, [g("Boots", "BOOTS 1102 SHEFFIELD", 3, 10)]),
    ]
    mult = 0.7
    target = 380.0  # A4: Sheffield £538 x 0.7
    sources = [
        *_sfe_sources(sfe.id, loan, None, False),
        Source("University of Sheffield bursary", "£1,000 a year, 2 payments of £500 (October, February)",
               "University of Sheffield", "https://www.sheffield.ac.uk",
               "example within published university bursary range for the lowest household band", ref=bursary.id),
        _rent_source(f"£{halls_week:.0f} a week x 39 weeks = £{halls_week * 39:,.0f} a year, "
                     f"3 instalments of £{instalment:,.2f} (about £{halls_week * 39 / 9:,.0f} a month)",
                     "university accommodation £641 a month"),
        *_common_sources("Sheffield", target, mult),
    ]
    return Profile(
        "scholarship", "Careful saver",
        "Sheffield student on the full loan and a university bursary. Halls paid each term. Saves a little each "
        "month.", 1101, "Amara Okoye", 19, True, "rent", "plan_5", "Nationwide", "FlexStudent",
        "Flex Instant Saver", 1950.00, 420.00, target, mult, {7: 0.6, 8: 0.6, 9: 1.0, 10: 0.92},
        spends, [sfe, bursary], fixed, sources,
        Card("face-teen-hijab", "University of Sheffield", "Sheffield", "Sheffield", "yorkshire-and-the-humber",
             "Student Finance England + bursary",
             f"Halls, £{instalment:,.0f} a term", [
                 ("Maintenance loan", sfe.id, "term", "21 Sep, 11 Jan, 19 Apr", 1, False),
                 ("University bursary", bursary.id, "year", "£500 in Oct and Feb", 1, False)]),
        [("groceries", 0.9)], [("Rainy day fund", "☔", 1500.0, "2027-06-30", True)], "on_track",
        funding=["maintenance_loan", "bursary"],
    )


def eilidh() -> Profile:
    months = monthly(25, date(2026, 9, 1), date(2027, 5, 31))
    loan, ysb = [round(SAAS_LOAN / 9, 2)] * 9, [round(SAAS_YSB / 9, 2)] * 9
    loan[-1] = round(SAAS_LOAN - 8 * loan[0], 2)
    ysb[-1] = round(SAAS_YSB - 8 * ysb[0], 2)
    saas = Stream("saas_loan", "maintenance_loan", "monthly", "Student Loans Company", "SAAS STUDENT LOAN",
                  months, loan)
    bursary = Stream("saas_ysb", "bursary", "monthly", "SAAS", "SAAS YOUNG STUDENTS BURSARY", months, ysb)
    fortnights = [d for d in weekly(4, date(2026, 7, 3)) if (d - date(2026, 7, 3)).days % 14 == 0]
    pay = [round((20 if d < date(2026, 9, 14) else 8) * 2 * WAGE_18_20, 2) for d in fortnights]
    cafe = Stream("cafe_job", "part_time_job", "fortnightly", "Brew Lab Coffee Ltd", "WAGES BREW LAB", fortnights,
                  pay)
    fixed = [
        rent("Marchmont Lettings", 650.00, "RENT 9F WARRENDER PARK RD"),
        fixed_monthly(BILL, "Flatmate", "Bills", 35.00, 3, "BILLS SHARE ENERGY AND BROADBAND",
                      type_="Faster payment"),
        fixed_monthly(BILL, "EE", "Bills", 12.00, 8, "EE LIMITED MOBILE"),
        one_off(date(2026, 9, 16), "Blackwell's", "Education", 38.50, "BLACKWELLS EDINBURGH BOOKS"),
        to_savings([date(2026, 8, 29)], 200.00, "Access Saver"),
        to_savings(monthly(26, date(2026, 9, 1)), 40.00, "Access Saver"),
    ]
    spends = [
        Spend("Groceries", 0.42, 2.6, [g("Lidl", "LIDL GB EDINBURGH", 12, 32, 2), g("Scotmid",
              "SCOTMID MARCHMONT", 6, 15), g("Sainsbury's", "SAINSBURYS LOCAL MARCHMONT", 6, 18)],
              clamp=GROCERY_CLAMP),
        Spend("Eating out", 0.10, 1.2, [g("Greggs", "GREGGS PRINCES ST", 2.2, 6.0), g("Pret A Manger",
              "PRET A MANGER EDINBURGH", 4.0, 9.0)], "weekend_heavy"),
        Spend("Entertainment", 0.19, 0.9, [g("Cabaret Voltaire", "CABARET VOLTAIRE NIGHTCLUB", 8, 18),
              g("Sneaky Pete's", "SNEAKY PETES NIGHTCLUB", 6, 14)], "thu_sat"),
        Spend("Transport", 0.08, 0.8, [g("Lothian Buses", "LOTHIAN BUSES NIGHT BUS", 3.0, 3.5),
              g("ScotRail", "SCOTRAIL EDINBURGH", 5.0, 14.0)]),
        Spend("Shopping", 0.13, 0.4, [g("H&M", "H&M PRINCES ST", 10, 28), g("TK Maxx", "TK MAXX EDINBURGH", 8, 25)]),
        Spend("Health", 0.08, 0.4, [g("Boots", "BOOTS EDINBURGH", 3, 12)]),
    ]
    mult = 0.9
    target = 560.0  # A4: Edinburgh £637 x 0.9
    sources = [
        Source("SAAS loan 2026/27, young student, household up to £20,999", f"£{SAAS_LOAN:,.0f} a year", SAAS,
               SAAS_URL, ref=saas.id),
        Source("SAAS Young Students' Bursary 2026/27", f"£{SAAS_YSB:,.0f} a year", SAAS, SAAS_URL, ref=bursary.id),
        Source("SAAS payment schedule", f"9 monthly payments around the 25th, Sep to May: £{loan[0]:,.2f} loan + "
               f"£{ysb[0]:,.2f} bursary", SAAS, SAAS_URL,
               "example within SAAS schedule (monthly); confirm dates on saas.gov.uk", ref=saas.id),
        Source("Café job pay", f"£{WAGE_18_20:.2f} an hour (age 18 to 20); 8 hours a week in term, 20 in summer, "
               "paid every 2 weeks", NLW, NLW_URL, "example hours within NSMS 2026 (59% of students work)",
               ref=cafe.id),
        _rent_source("£650 a month + £35 energy and broadband share", "Scotland average £703; energy £83 a month"),
        *_common_sources("Edinburgh", target, mult),
    ]
    return Profile(
        "scottish", "Scottish student",
        "Edinburgh student on SAAS: a monthly loan and Young Students' Bursary, plus a weekend café job.",
        9210, "Eilidh Fraser", 19, True, "rent", "plan_4", "Bank of Scotland", "Student Account", "Access Saver",
        860.00, 300.00, target, mult, {7: 0.78, 8: 0.85, 9: 1.0, 10: 0.9}, spends, [saas, bursary, cafe], fixed,
        sources,
        Card("face-blue-hair", "University of Edinburgh", "Edinburgh", "Edinburgh", "scotland", "SAAS + bursary",
             "Shared flat in Marchmont, £650 a month", [
                 ("SAAS loan", saas.id, "month", "Around the 25th, Sep to May", 1, False),
                 ("Young Students' Bursary", bursary.id, "month", "Same day as the SAAS loan", 1, False),
                 ("Café job", cafe.id, "week", "Paid every 2 weeks, 8 hours a week in term", 2, False)]),
        [("groceries", 0.9)], [("Rainy day fund", "☔", 1000.0, "2027-05-31", True)], "on_track",
        term_start=date(2026, 9, 14), funding=["maintenance_loan", "bursary", "part_time_job"],
    )


def priya() -> Profile:
    household = 35_000.0
    loan = sfe_loan(household, home=True)
    sfe = Stream("maintenance_loan_sfe", "maintenance_loan", "termly", "Student Loans Company",
                 "SLC MAINTENANCE LOAN", [date(2026, 9, 21), SFE_TERM2, SFE_TERM3], thirds(loan))
    fridays = weekly(4)
    mum = Stream("family_mum", "family", "weekly", "S Patel", "Mum - weekly", fridays, [40.00] * len(fridays),
                 "Faster payment")
    fixed = [
        Fixed(RENT, "S Patel", "Housing", 150.00, "RENT TO MUM BOARD", monthly(1), "Standing order", "07:00:00"),
        sub("Spotify", 5.99, 3, "SPOTIFY STUDENT"),
        one_off(date(2026, 9, 14), "16-25 Railcard", "Transport", 35.00, "RAILCARD.CO.UK 16-25 RAILCARD"),
        to_savings([d + timedelta(days=1) for d in fridays], 20.00, "Easy Access Saver"),
        to_savings([date(2026, 9, 22)], 900.00, "Easy Access Saver"),
    ]
    spends = [
        Spend("Transport", 0.36, 4.0, [g("Northern", "NORTHERN TRAINS BOLTON-MANCHESTER", 5.20, 5.20, 3),
              g("Bee Network", "BEE NETWORK BUS", 2.0, 2.0)], "weekdays", term_only=True),
        Spend("Groceries", 0.13, 2.0, [g("Tesco", "TESCO EXPRESS OXFORD RD", 6, 12)], clamp=GROCERY_CLAMP),
        Spend("Eating out", 0.22, 2.0, [g("Greggs", "GREGGS MANCHESTER PICC", 2.0, 6.0, 2),
              g("Manchester Students' Union", "MANCHESTER SU CAFE", 2.5, 6.5)], "weekend_heavy"),
        Spend("Entertainment", 0.09, 0.4, [g("Vue", "VUE CINEMA MANCHESTER", 7.5, 10.0), g("Ticketmaster",
              "TICKETMASTER UK", 15, 28)], "thu_sat"),
        Spend("Shopping", 0.12, 0.3, [g("Primark", "PRIMARK MANCHESTER", 8, 25)]),
        Spend("Health", 0.08, 0.4, [g("Boots", "BOOTS MANCHESTER", 3, 10)]),
    ]
    mult = 0.65
    target = 330.0  # A4: Manchester £490 x 0.65
    sources = [
        *_sfe_sources(sfe.id, loan, household, True),
        Source("Money from parents", "£40 every Friday", NSMS, NSMS_URL,
               "example within NSMS 2026 range (parents give £132 a month on average)", ref=mum.id),
        _rent_source("£150 a month board to her parents", "living with parents £400 a month",
                     "example within NSAS 2026 range (living with parents: £400 a month)"),
        Source("Train fare Bolton to Manchester", "£5.20 a day with a 16-25 Railcard; Railcard £35", NSMS, NSMS_URL,
               "example within NSMS 2026 transport range (£73 a month average)", ref="Northern"),
        *_common_sources("Manchester", target, mult),
    ]
    return Profile(
        "commuter", "Commuter student",
        "Lives with family in Bolton and takes the train to Manchester. Loan plus £40 a week from Mum. "
        "Saving for a first home.", 4404, "Priya Patel", 19, True, "parents", "plan_5", "Santander",
        "Edge Student Account", "Easy Access Saver", 1400.00, 1100.00, target, mult,
        {7: 0.55, 8: 0.55, 9: 1.0, 10: 1.0}, spends, [sfe, mum], fixed, sources,
        Card("face-priya", "University of Manchester", "Manchester", "Bolton", "north-west",
             "Student Finance England + family", "Lives at home with family, pays £150 board", [
                 ("Maintenance loan", sfe.id, "term", "21 Sep, 11 Jan, 19 Apr", 1, False),
                 ("Mum", mum.id, "week", "Every Friday", 1, False)]),
        [("eating_out", 0.9)], [("First home deposit", "🏠", 5000.0, "2028-06-30", True)], "on_track",
        funding=["maintenance_loan", "family"],
    )


def jordan() -> Profile:
    household = 30_000.0
    loan = sfe_loan(household)
    sfe = Stream("maintenance_loan_sfe", "maintenance_loan", "termly", "Student Loans Company",
                 "SLC MAINTENANCE LOAN", [date(2026, 9, 14), SFE_TERM2, SFE_TERM3], thirds(loan))
    tenancy = date(2026, 9, 1)
    fixed = [
        rent("Jesmond Student Lets", 560.00, "RENT 41 FOREST RD JESMOND", tenancy),
        fixed_monthly(BILL, "Housemate", "Bills", 45.00, 5, "BILLS SHARE 41 FOREST RD", tenancy,
                      type_="Faster payment"),
        sub("Spotify", 5.99, 14, "SPOTIFY STUDENT"),
        sub("Apple", 0.99, 2, "APPLE.COM/BILL ICLOUD"),
        fixed_monthly(BILL, "Smarty", "Bills", 10.00, 12, "SMARTY MOBILE"),
        one_off(date(2026, 9, 14), "Currys", "Shopping", 279.00, "CURRYS NEWCASTLE LAPTOP"),
    ]
    spends = [
        Spend("Eating out", 0.38, 3.2, [g("Deliveroo", "DELIVEROO NEWCASTLE", 14, 28, 2), g("Greggs",
              "GREGGS NORTHUMBERLAND ST", 2.2, 6.5, 2), g("JD Wetherspoon", "JD WETHERSPOON THE ARIEL", 6, 18)],
              "weekend_heavy"),
        Spend("Groceries", 0.28, 2.4, [g("Tesco", "TESCO EXPRESS JESMOND", 6, 30)], clamp=GROCERY_CLAMP),
        Spend("Entertainment", 0.22, 1.2, [g("Digital Newcastle", "DIGITAL NEWCASTLE NIGHTCLUB", 8, 22),
              g("Ticketmaster", "TICKETMASTER UK", 18, 35, 0.3)], "thu_sat"),
        Spend("Transport", 0.06, 1.0, [g("Nexus", "NEXUS METRO NEWCASTLE", 2.0, 3.6)]),
        Spend("Shopping", 0.06, 0.2, [g("JD Sports", "JD SPORTS NEWCASTLE", 15, 40)]),
    ]
    mult = 1.35
    target = 620.0  # A4: Newcastle £455 x 1.35
    sources = [
        *_sfe_sources(sfe.id, loan, household, False),
        _rent_source("£560 a month + £45 bills share", "North East average £557"),
        Source("Laptop", "£279 at Currys on loan day", NSMS, NSMS_URL, "example within NSMS 2026 range",
               ref="Currys"),
        *_common_sources("Newcastle", target, mult),
    ]
    return Profile(
        "loan_england", "Full loan student",
        "Newcastle student on the loan in 3 payments. Spends big after loan day; the money runs out before "
        "January.", 9109, "Jordan Hughes", 20, True, "rent", "plan_5", "HSBC", "Student Bank Account", None,
        2560.00, 0.0, target, mult, {7: 0.55, 8: 0.55, 9: 1.0, 10: 1.55}, spends, [sfe], fixed, sources,
        Card("face-teen", "Newcastle University", "Newcastle", "Newcastle", "north-east",
             "Student Finance England", "Shared house in Jesmond, £560 a month", [
                 ("Maintenance loan", sfe.id, "term", "14 Sep, 11 Jan, 19 Apr", 1, False)]),
        [("eating_out", 0.9)], [("Summer InterRail", "🚆", 400.0, "2027-06-01", False)], "running_short",
        term_start=date(2026, 9, 14), lean=[(date(2026, 7, 1), date(2026, 9, 13))],
        funding=["maintenance_loan"],
    )


def callum() -> Profile:
    household = 60_000.0
    loan = sfe_loan(household)
    sfe = Stream("maintenance_loan_sfe", "maintenance_loan", "termly", "Student Loans Company",
                 "SLC MAINTENANCE LOAN", [date(2026, 10, 26), SFE_TERM2, SFE_TERM3], thirds(loan))
    rng = random.Random(3303)
    fridays = weekly(4, date(2026, 7, 3))
    hours = [16 if d < date(2026, 9, 21) else rng.choice([8, 10, 10, 12, 14]) for d in fridays]
    bar = Stream("bar_job", "part_time_job", "weekly", "Hyde Park Social Ltd", "WAGES HYDE PARK SOCIAL", fridays,
                 [round(h * WAGE_21, 2) for h in hours])
    fixed = [
        rent("Hyde Park Lettings", 520.00, "RENT 14 BRUDENELL RD"),
        fixed_monthly(BILL, "Housemate", "Bills", 50.00, 5, "BILLS SHARE 14 BRUDENELL RD", type_="Faster payment"),
        sub("Spotify", 5.99, 12, "SPOTIFY STUDENT"),
        sub("Netflix", 5.99, 17, "NETFLIX.COM"),
        fixed_monthly(BILL, "Smarty", "Bills", 8.00, 6, "SMARTY MOBILE"),
    ]
    spends = [
        Spend("Eating out", 0.34, 2.8, [g("Deliveroo", "DELIVEROO LEEDS", 14, 30, 2), g("Greggs",
              "GREGGS HEADROW LEEDS", 2.2, 6.5)], "weekend_heavy"),
        Spend("Entertainment", 0.22, 1.4, [g("Revolution", "REVOLUTION LEEDS", 10, 30), g("Belgrave Music Hall",
              "BELGRAVE MUSIC HALL LEEDS", 8, 20)], "thu_sat"),
        Spend("Groceries", 0.22, 2.2, [g("Aldi", "ALDI HEADINGLEY", 12, 32, 2), g("Sainsbury's",
              "SAINSBURYS LOCAL HYDE PARK", 6, 15)], clamp=GROCERY_CLAMP),
        Spend("Transport", 0.17, 1.6, [g("Uber", "UBER *TRIP LEEDS", 7, 16), g("First Bus", "FIRST BUS LEEDS",
              2.0, 2.0)]),
        Spend("Shopping", 0.05, 0.2, [g("Primark", "PRIMARK LEEDS", 8, 20)]),
    ]
    mult = 1.2
    target = 650.0  # A4: Leeds £549 x 1.2
    sources = [
        *_sfe_sources(sfe.id, loan, household, False),
        Source("First SFE payment", "26 Oct 2026, late: SFE is still checking household income evidence", SFE,
               SFE_URL, "example within SFE rule (payment waits for household income evidence)", ref=sfe.id),
        Source("Bar job pay", f"£{WAGE_21:.2f} an hour (21 and over); 16 hours a week in summer, 8 to 14 in term, "
               "paid every Friday", NLW, NLW_URL, "example hours within NSMS 2026 (59% of students work)",
               ref=bar.id),
        Source("NatWest student overdraft", "interest-free arranged overdraft, limit £500 used here", "NatWest",
               "https://www.natwest.com/current-accounts/student-account.html",
               "example within NatWest student account range (interest-free arranged overdraft, tiered by year)",
               ref="overdraft"),
        _rent_source("£520 a month + £50 bills share", "Yorkshire average £557"),
        *_common_sources("Leeds", target, mult),
    ]
    return Profile(
        "working", "Working student",
        "Leeds student on a reduced loan whose first payment is late, plus weekly bar shifts. Now in the overdraft.",
        3303, "Callum Reid", 21, True, "rent", "plan_5", "NatWest", "Student Account", None,
        -385.00, 0.0, target, mult, {7: 0.9, 8: 0.9, 9: 1.0, 10: 0.95}, spends, [sfe, bar], fixed, sources,
        Card("face-man-beard", "University of Leeds", "Leeds", "Leeds", "yorkshire-and-the-humber",
             "Student Finance England + bar job", "Shared house in Hyde Park, £520 a month", [
                 ("Maintenance loan", sfe.id, "term", "First due 26 Oct (late), 11 Jan, 19 Apr", 1, False),
                 ("Bar job", bar.id, "week", "Every Friday, pay varies", 1, True)]),
        [("eating_out", 0.9)], [("Out of the overdraft", "🛟", 500.0, "2027-04-30", False)], "running_short",
        overdraft_limit=500.0, funding=["maintenance_loan", "part_time_job"],
    )


def grace() -> Profile:
    loan = SFE_MAX_AWAY  # independent student: her own income is the household income, under £25,000
    sfe = Stream("maintenance_loan_sfe", "maintenance_loan", "termly", "Student Loans Company",
                 "SLC MAINTENANCE LOAN", [date(2026, 9, 21), SFE_TERM2, SFE_TERM3], thirds(loan))
    lsf_dates = monthly(20, date(2026, 7, 1))
    lsf = Stream("nhs_lsf", "grant", "monthly", "NHSBSA", "NHS LEARNING SUPPORT FUND TRAINING GRANT", lsf_dates,
                 [416.67] * len(lsf_dates))
    hca_rate = 13.10
    shift_dates = monthly(5, date(2026, 7, 1))
    rng = random.Random(9311)
    shifts = [rng.choice([1, 2, 2]) for _ in shift_dates]
    bank = Stream("nhs_bank_shifts", "part_time_job", "monthly", "NHS Professionals", "NHSP PAYROLL BANK SHIFTS",
                  shift_dates, [round(n * 11.5 * hca_rate, 2) for n in shifts])
    fixed = [
        rent("Moseley Lettings", 520.00, "RENT 18 ALCESTER RD MOSELEY"),
        fixed_monthly(BILL, "Housemate", "Bills", 40.00, 4, "BILLS SHARE 18 ALCESTER RD", type_="Faster payment"),
        fixed_monthly(BILL, "Tesco Mobile", "Bills", 12.00, 17, "TESCO MOBILE"),
        sub("Netflix", 5.99, 24, "NETFLIX.COM"),
        one_off(date(2026, 9, 24), "Waterstones", "Education", 29.99, "WATERSTONES BIRMINGHAM"),
        to_savings([d + timedelta(days=1) for d in shift_dates], 100.00, "Savings"),
        to_savings([date(2026, 9, 22)], 600.00, "Savings"),
    ]
    spends = [
        Spend("Groceries", 0.40, 2.6, [g("Aldi", "ALDI MOSELEY", 12, 34, 2), g("Lidl", "LIDL GB BIRMINGHAM", 8, 30)],
              clamp=GROCERY_CLAMP),
        Spend("Transport", 0.26, 3.5, [g("National Express West Midlands", "NXWM BUS", 2.0, 2.0, 3),
              g("West Midlands Railway", "WEST MIDLANDS RAILWAY", 4.2, 7.8)], "weekdays"),
        Spend("Eating out", 0.12, 1.0, [g("Costa Coffee", "COSTA QEHB", 2.8, 6.5), g("Greggs",
              "GREGGS SELLY OAK", 2.2, 6.0)], "weekend_heavy"),
        Spend("Entertainment", 0.07, 0.3, [g("O2 Academy", "O2 ACADEMY BIRMINGHAM", 12, 28)], "thu_sat"),
        Spend("Shopping", 0.07, 0.25, [g("Primark", "PRIMARK BIRMINGHAM", 8, 22)]),
        Spend("Health", 0.08, 0.5, [g("Boots", "BOOTS BIRMINGHAM", 3, 12)]),
    ]
    mult = 0.9
    target = 520.0  # A4: Birmingham £577 x 0.9
    sources = [
        *_sfe_sources(sfe.id, loan, None, False),
        Source("NHS Learning Support Fund training grant", "£5,000 a year, paid as £416.67 around the 20th",
               "NHSBSA Learning Support Fund", "https://www.nhsbsa.nhs.uk/learning-support-fund-lsf",
               "example within NHS LSF range (training grant); monthly schedule not checked", ref=lsf.id),
        Source("NHS bank healthcare assistant pay", f"£{hca_rate:.2f} an hour, 11.5-hour shifts, 1 to 2 a month",
               NLW, NLW_URL, f"example within range: at or above the £{WAGE_21:.2f} National Living Wage",
               ref=bank.id),
        _rent_source("£520 a month + £40 bills share", "West Midlands average £484; private landlord £576"),
        *_common_sources("Birmingham", target, mult),
    ]
    return Profile(
        "mature", "Mature student",
        "29-year-old nursing student in Birmingham. Loan, NHS training grant and bank shifts. Careful with money.",
        9311, "Grace Mensah", 29, True, "rent", "plan_5", "Lloyds", "Classic Account", "Savings",
        2750.00, 1500.00, target, mult, {7: 0.85, 8: 0.85, 9: 1.0, 10: 0.92}, spends, [sfe, lsf, bank], fixed,
        sources,
        Card("face-woman-puff", "University of Birmingham", "Birmingham", "Birmingham", "west-midlands",
             "Student Finance England + NHS grant", "Shared house in Moseley, £520 a month", [
                 ("Maintenance loan", sfe.id, "term", "21 Sep, 11 Jan, 19 Apr", 1, False),
                 ("NHS Learning Support Fund", lsf.id, "month", "Around the 20th each month", 1, False),
                 ("NHS bank shifts", bank.id, "month", "Around the 5th each month, pay varies", 1, True)]),
        [("groceries", 0.9)], [("Emergency fund", "🛟", 3500.0, "2027-06-30", True)], "on_track",
        funding=["maintenance_loan", "grant", "part_time_job"],
    )


def yutong() -> Profile:
    cny = 15_000.00
    rates = {7: 0.1062, 8: 0.1058, 9: 0.1066, 10: 0.1071, 11: 0.1069, 12: 0.1065, 1: 0.1064, 2: 0.1066, 3: 0.1068,
             4: 0.1067, 5: 0.1066, 6: 0.1065}
    dates = monthly(3, date(2026, 7, 1))
    amounts = [round(cny * rates[d.month], 2) for d in dates]
    wise = Stream("family_wise", "family", "monthly", "Wise", "WISE CNY 15,000.00 > GBP FAMILY SUPPORT FROM CHEN "
                  "JIAN", dates, amounts, "Faster payment")
    week, weeks = 180.00, 51
    room = round(week * weeks / 12, 2)
    fixed = [
        rent("Unite Students", room, "UNITE STUDENTS COVENTRY ENSUITE"),
        fixed_monthly(BILL, "Three", "Bills", 12.00, 8, "THREE MOBILE"),
        sub("Spotify", 12.99, 11, "SPOTIFY PREMIUM"),
        sub("Apple", 2.99, 2, "APPLE.COM/BILL ICLOUD 200GB"),
        one_off(date(2026, 9, 26), "Warwick SU", "Education", 24.00, "WARWICK SU SHOP BOOKS"),
        to_savings([d + timedelta(days=1) for d in dates], 300.00, "Savings"),
    ]
    spends = [
        Spend("Groceries", 0.36, 2.5, [g("Tesco", "TESCO EXPRESS CANLEY", 6, 18, 2), g("Wing Yip",
              "WING YIP BIRMINGHAM", 25, 35), g("Hoo Hing", "HOO HING COVENTRY", 18, 35)], clamp=GROCERY_CLAMP),
        Spend("Eating out", 0.36, 3.5, [g("Chatime", "CHATIME COVENTRY", 4.6, 6.4, 2), g("Deliveroo",
              "DELIVEROO COVENTRY", 15, 30), g("Warwick Students' Union", "WARWICK SU CAFE", 3, 7)],
              "weekend_heavy"),
        Spend("Transport", 0.12, 1.5, [g("National Express Coventry", "NATIONAL EXPRESS COVENTRY", 2.0, 2.0, 2),
              g("Uber", "UBER *TRIP COVENTRY", 7, 15)]),
        Spend("Shopping", 0.11, 0.3, [g("Uniqlo", "UNIQLO BIRMINGHAM", 15, 40)]),
        Spend("Entertainment", 0.05, 0.3, [g("Kasbah", "KASBAH NIGHTCLUB COVENTRY", 6, 12)], "thu_sat"),
    ]
    mult = 1.2
    target = 520.0  # A4: Warwick £429 x 1.2
    sources = [
        Source("Money from parents", f"CNY {cny:,.0f} a month, about £{amounts[3]:,.0f} at "
               f"{rates[10]:.4f}", "Frankfurter (ECB reference rates)", "https://www.frankfurter.app",
               "example within Frankfurter CNY to GBP range (0.1058 to 0.1071 used); the live app reads the live rate",
               ref=wise.id),
        _rent_source(f"£{week:.0f} a week x {weeks} weeks, paid monthly: £{room:,.2f}",
                     "uni accommodation £641, London £793",
                     "example within NSAS 2026 range (uni accommodation £641 a month); check the current Unite "
                     "Students price at unitestudents.com"),
        *_common_sources("Warwick", target, mult),
    ]
    return Profile(
        "international", "International student",
        "From China, studying at Warwick. Parents send money each month by Wise (yuan to pounds). Saves for a "
        "flight home.", 9412, "Yutong Chen", 21, True, "rent", "none", "Barclays", "Student Account",
        "Savings", 1350.00, 300.00, target, mult, {7: 0.75, 8: 0.8, 9: 1.0, 10: 0.92}, spends, [wise], fixed,
        sources,
        Card("face-girl", "University of Warwick", "Warwick", "Coventry", "west-midlands", "Parents",
             f"Unite Students en-suite, £{room:,.0f} a month", [
                 ("Parents (by Wise)", wise.id, "month", "Around the 3rd; moves with the yuan", 1, False)]),
        [("eating_out", 0.9)], [("Flight home at Christmas", "✈️", 900.0, "2026-12-10", True)], "on_track",
        funding=["family"],
    )


def sam() -> Profile:
    household = 45_000.0
    loan = sfe_loan(household)
    sfe = Stream("maintenance_loan_sfe", "maintenance_loan", "termly", "Student Loans Company",
                 "SLC MAINTENANCE LOAN", [date(2026, 9, 21), SFE_TERM2, SFE_TERM3], thirds(loan))
    gross = 2_000.00
    tax, ni, net = net_month(gross)
    paydays = [last_working_day(2026, 7), last_working_day(2026, 8)]
    intern = Stream("internship", "salary", "one_off", "Exeter Analytics Ltd", "SALARY SUMMER INTERN", paydays,
                    [net, net])
    fixed = [
        rent("Exeter Student Lets", 600.00, "RENT 7 PENNSYLVANIA RD"),
        fixed_monthly(BILL, "Housemate", "Bills", 45.00, 5, "BILLS SHARE 7 PENNSYLVANIA RD", type_="Faster payment"),
        sub("Spotify", 5.99, 16, "SPOTIFY STUDENT"),
        fixed_monthly(BILL, "VOXI", "Bills", 10.00, 22, "VOXI MOBILE"),
        one_off(date(2026, 9, 2), "Ryanair", "Holidays", 96.00, "RYANAIR EXETER-FARO"),
        one_off(date(2026, 9, 3), "Hostelworld", "Holidays", 84.00, "HOSTELWORLD FARO 4 NIGHTS"),
        to_savings([d + timedelta(days=1) for d in paydays], 600.00, "Savings"),
        to_savings(monthly(22, date(2026, 9, 1)), 100.00, "Savings"),
    ]
    spends = [
        Spend("Groceries", 0.36, 2.4, [g("Co-op", "CO-OP GROUP SIDWELL ST", 6, 18), g("Tesco",
              "TESCO EXETER", 10, 34, 2)], clamp=GROCERY_CLAMP),
        Spend("Eating out", 0.18, 1.6, [g("Greggs", "GREGGS EXETER", 2.2, 6.0), g("Deliveroo",
              "DELIVEROO EXETER", 14, 26)], "weekend_heavy"),
        Spend("Entertainment", 0.20, 1.0, [g("Timepiece", "TIMEPIECE NIGHTCLUB EXETER", 8, 22)], "thu_sat"),
        Spend("Transport", 0.17, 2.5, [g("Stagecoach", "STAGECOACH SOUTH WEST", 2.0, 4.5)], "weekdays"),
        Spend("Shopping", 0.09, 0.25, [g("TK Maxx", "TK MAXX EXETER", 10, 30)]),
    ]
    mult = 1.15
    target = 520.0  # A4: Exeter £443 x 1.15
    sources = [
        *_sfe_sources(sfe.id, loan, household, False),
        Source("Summer internship pay", f"£{gross:,.0f} a month gross; tax £{tax:,.2f}, NI £{ni:,.2f}, "
               f"net £{net:,.2f}", "gov.uk income tax and National Insurance rates", "https://www.gov.uk/income-tax-rates",
               "example gross within NSMS 2026 range; tax and NI by a simple month-1 method (20% and 8% above "
               "£1,047.50)", ref=intern.id),
        _rent_source("£600 a month + £45 bills share", "South West average £610"),
        Source("Trip in September", "Ryanair £96 + Hostelworld £84", NSMS, NSMS_URL, "example within NSMS 2026 range",
               ref="trip"),
        *_common_sources("Exeter", target, mult),
    ]
    return Profile(
        "final_year", "Final year with internship",
        "Exeter final year. A paid summer internship, savings, a September trip, then the last year of the loan.",
        9513, "Sam Whitfield", 21, True, "rent", "plan_5", "Starling", "Personal Account", "Savings",
        4050.00, 400.00, target, mult, {7: 0.9, 8: 0.9, 9: 1.0, 10: 1.1}, spends, [intern, sfe], fixed, sources,
        Card("face-man-glasses", "University of Exeter", "Exeter", "Exeter", "south-west",
             "Student Finance England + internship", "Shared house in Exeter, £600 a month", [
                 ("Summer internship", intern.id, "month", "31 Jul and 28 Aug only", 1, False),
                 ("Maintenance loan", sfe.id, "term", "21 Sep, 11 Jan, 19 Apr", 1, False)]),
        [("eating_out", 0.9)], [("Deposit for a flat after uni", "🏠", 2500.0, "2027-08-31", True)], "on_track",
        funding=["salary", "maintenance_loan"],
    )


def hugo() -> Profile:
    dates = monthly(1, date(2026, 7, 1), adjust=False)
    parents = Stream("family_parents", "family", "monthly", "R Ashworth", "ALLOWANCE FROM DAD", dates,
                     [1500.00] * len(dates), "Faster payment")
    fixed = [
        rent("Leeds City Studios", 895.00, "RENT STUDIO 4B CALLS LANDING", day=1),
        sub("Netflix", 12.99, 4, "NETFLIX.COM"),
        sub("Spotify", 12.99, 11, "SPOTIFY PREMIUM"),
        sub("Amazon Prime", 8.99, 21, "AMAZON PRIME*MEMBERSHIP"),
        sub("Apple", 2.99, 2, "APPLE.COM/BILL ICLOUD 200GB"),
        fixed_monthly(SUB, "PureGym", "Subscriptions", 29.99, 1, "PUREGYM LEEDS CITY"),
        fixed_monthly(BILL, "EE", "Bills", 25.00, 9, "EE LIMITED MOBILE"),
    ]
    for first, shop, inst in ((date(2026, 7, 12), "ASOS", 34.00), (date(2026, 8, 20), "ASOS", 41.00),
                              (date(2026, 9, 6), "ZARA", 39.00), (date(2026, 10, 2), "ASOS", 46.00)):
        fixed.append(Fixed(BNPL, "Klarna", "Shopping", inst, f"KLARNA*{shop}",
                           [first + timedelta(days=30 * i) for i in range(3)], "Card payment", "10:15:00"))
    spends = [
        Spend("Eating out", 0.47, 7.0, [g("Deliveroo", "DELIVEROO LEEDS", 18, 36, 2), g("Ole & Steen",
              "OLE AND STEEN LEEDS", 4.5, 12.0, 2), g("Nando's", "NANDOS LEEDS", 16, 30),
              g("Leeds University Union", "LEEDS UNI UNION BAR", 6, 18, 0.5)], "weekend_heavy"),
        Spend("Transport", 0.15, 3.0, [g("Uber", "UBER *TRIP LEEDS", 7, 18)]),
        Spend("Entertainment", 0.17, 1.6, [g("Revolution", "REVOLUTION LEEDS", 20, 55), g("Ticketmaster",
              "TICKETMASTER UK", 30, 60, 0.4)], "thu_sat"),
        Spend("Groceries", 0.11, 2.0, [g("M&S Food", "M&S SIMPLY FOOD LEEDS", 8, 35), g("Tesco",
              "TESCO EXPRESS LEEDS STATION", 6, 20)], clamp=GROCERY_CLAMP),
        Spend("Shopping", 0.10, 0.5, [g("ASOS", "ASOS.COM", 25, 70)]),
    ]
    mult = 1.8
    target = 1000.0  # A4: Leeds £549 x 1.8
    sources = [
        Source("Money from parents", "£1,500 on the 1st of each month", NSMS, NSMS_URL,
               "example within NSMS 2026 range (parents give £132 a month on average; Hugo's are far above it)",
               ref=parents.id),
        _rent_source("£895 a month, bills included (city-centre studio)", "Yorkshire average £557",
                     "example within NSAS 2026 range (private landlord £576; London average £793 is the top region)"),
        *_common_sources("Leeds", target, mult),
    ]
    return Profile(
        "rich", "Rich student",
        "£1,500 a month from parents, a city studio, many subscriptions and Klarna for clothes. Runs short "
        "before the next payment.", 2202, "Hugo Ashworth", 20, True, "rent", "plan_5", "Barclays",
        "Student Account", None, 120.00, 0.0, target, mult, {7: 0.85, 8: 0.85, 9: 1.0, 10: 0.97}, spends,
        [parents], fixed, sources,
        Card("face-boy", "University of Leeds", "Leeds", "Leeds", "yorkshire-and-the-humber", "Parents",
             "City-centre studio, £895 a month, bills included", [
                 ("Parents", parents.id, "month", "1st of each month", 1, False)]),
        [("eating_out", 0.9), ("shopping", 0.9)], [("Ski trip with friends", "🎿", 800.0, "2027-02-01", False)],
        "running_short", funding=["family"],
    )


def lena() -> Profile:
    salary = 30_000.00
    gross = salary / 12
    pension = round((salary - 6_240) * 0.05 / 12, 2)
    tax = round((salary - pension * 12 - 12_570) * BASIC_RATE / 12, 2)
    ni = round((salary - 12_570) * NI_RATE / 12, 2)
    net = round(gross - pension - tax - ni, 2)
    paydays = [prev_working_day(date(2026, m, 25)) for m in (9, 10, 11, 12)]
    paydays += [prev_working_day(date(2027, m, 25)) for m in range(1, 7)]
    pay = Stream("salary", "salary", "monthly", "Halden Group Plc", "SALARY HALDEN GROUP", paydays,
                 [net] * len(paydays))
    mum = Stream("family_mum", "family", "one_off", "A Novak", "Mum - for the deposit", [date(2026, 8, 21)],
                 [400.00], "Faster payment")
    room = 900.00
    deposit = round(room * 12 / 52 * 5, 2)
    move_in = date(2026, 9, 1)
    fixed = [
        rent("Hackney Lettings", room, "RENT ROOM 3 MARE ST", move_in),
        Fixed(RENT, "Hackney Lettings", "Housing", deposit, "TENANCY DEPOSIT 5 WEEKS", [date(2026, 8, 24)],
              "Faster payment", "10:00:00"),
        fixed_monthly(SPEND, "TfL", "Transport", 191.40, 1, "TFL TRAVELCARD ZONES 1-2 MONTHLY", move_in,
                      type_="Card payment", adjust=False, time="07:40:00"),
        sub("Spotify", 12.99, 3, "SPOTIFY PREMIUM"),
        fixed_monthly(SUB, "PureGym", "Subscriptions", 32.99, 2, "PUREGYM LONDON HACKNEY", move_in),
        fixed_monthly(BILL, "giffgaff", "Bills", 12.00, 6, "GIFFGAFF MOBILE"),
        to_savings([d + timedelta(days=1) for d in paydays], 100.00, "Chase Saver"),
    ]
    spends = [
        Spend("Groceries", 0.42, 2.6, [g("Sainsbury's", "SAINSBURYS MARE ST", 8, 34, 2), g("Lidl",
              "LIDL GB HOMERTON", 10, 30)], clamp=GROCERY_CLAMP),
        Spend("Eating out", 0.33, 3.0, [g("Pret A Manger", "PRET A MANGER LIVERPOOL ST", 4.5, 9.5, 2),
              g("Dishoom", "DISHOOM SHOREDITCH", 25, 45, 0.3)], "weekend_heavy"),
        Spend("Entertainment", 0.12, 0.6, [g("Vue", "VUE CINEMA WESTFIELD STRATFORD", 9, 14), g("Ticketmaster",
              "TICKETMASTER UK", 25, 45, 0.5)], "thu_sat"),
        Spend("Shopping", 0.13, 0.4, [g("Uniqlo", "UNIQLO OXFORD ST", 20, 45)]),
    ]
    target = 700.0
    sources = [
        Source("Graduate salary", f"£{salary:,.0f} a year = £{gross:,.2f} a month gross; tax £{tax:,.2f}, NI "
               f"£{ni:,.2f}, pension £{pension:,.2f} (5% of earnings above £6,240); net £{net:,.2f}",
               "gov.uk income tax, National Insurance and workplace pension rules",
               "https://www.gov.uk/income-tax-rates",
               "example salary; tax 20% above £12,570, NI 8% above £12,570, pension by net pay arrangement",
               ref=pay.id),
        Source("Student loan repayments", "none yet: repayments start the April after graduation (April 2027)",
               "gov.uk, repaying your student loan", "https://www.gov.uk/repaying-your-student-loan",
               "rule not re-checked under the research limit", ref="student_loan"),
        _rent_source(f"Room in Hackney £{room:,.0f} a month, bills included; deposit 5 weeks £{deposit:,.2f}",
                     "London average £793"),
        Source("TfL monthly Travelcard zones 1 to 2", "£191.40 a month", "TfL", "https://tfl.gov.uk/fares",
               "example within NSMS 2026 transport range; fare not checked under the research limit", ref="TfL"),
        Source("Money from Mum for the deposit", "£400 once", NSMS, NSMS_URL,
               "example within NSMS 2026 range (parents give £132 a month on average)", ref=mum.id),
        *_common_sources(None, target, None),
    ]
    return Profile(
        "graduate", "Recent graduate",
        "Graduated in summer, started a London job in September on £30,000. First salary, first London rent.",
        9614, "Lena Novak", 22, False, "rent", "plan_5", "Chase", "Current Account", "Chase Saver",
        980.00, 400.00, target, None, {7: 0.55, 8: 0.6, 9: 1.0, 10: 0.95}, spends, [pay, mum], fixed, sources,
        Card("face-girl", None, None, "London", "london", "Salary", f"Room in Hackney, £{room:,.0f} a month, "
             "bills included", [("Graduate salary", pay.id, "month", "25th, or the Friday before", 1, False)]),
        [("eating_out", 0.9)], [("Emergency fund", "🛟", 3000.0, "2027-06-30", True)], "on_track",
        funding=["salary", "family"],
    )


PROFILES = [amara, eilidh, priya, jordan, callum, grace, yutong, sam, hugo, lena]
IDS = ["scholarship", "scottish", "commuter", "loan_england", "working", "mature", "international", "final_year",
       "rich", "graduate"]


def profile(sample_id: str) -> Profile:
    for make in PROFILES:
        p = make()
        if p.id == sample_id:
            return p
    raise KeyError(sample_id)


# ---------- simulation ------------------------------------------------------------------------------

NOT_SPENDING = {RENT, SAVINGS, INCOME}


def _income_rows(p: Profile, end: date) -> list[Tx]:
    out = []
    for s in p.streams:
        for d, amt in zip(s.dates, s.amounts, strict=True):
            if START <= d <= end:
                out.append(Tx(d, "06:00:00", s.type, s.payer, "Income", amt, s.description, INCOME, s.id))
    return out


def _fixed_rows(p: Profile, end: date) -> list[Tx]:
    out = []
    for f in p.fixed:
        for d in f.dates:
            if START <= d <= end:
                out.append(Tx(d, f.time, f.type, f.name, f.category, -round(f.amount, 2), f.description, f.kind))
    return out


def _eligible(s: Spend, d: date, p: Profile) -> bool:
    if s.term_only and d < p.term_start:
        return False
    if s.days == "weekdays" and d.weekday() >= 5:
        return False
    return not (s.days == "thu_sat" and d.weekday() not in (3, 4, 5))


def _weight(s: Spend, d: date, p: Profile, money_days: list[date]) -> float:
    w = 1.0
    if s.days == "weekend_heavy" and d.weekday() in (3, 4, 5):
        w *= 2.0
    if s.category != "Transport" and any(0 <= (d - m).days < 7 for m in money_days):
        w *= 1.8  # spending spike in the 7 days after a loan or pay
    if any(a <= d <= b for a, b in p.lean):
        w *= 0.45
    return w


def _time(rng: random.Random, s: Spend) -> str:
    if s.days == "thu_sat":
        h = rng.randint(20, 23)
    elif s.category == "Transport":
        h = rng.choice([7, 8, 8, 9, 17, 18])
    elif s.category == "Eating out":
        h = rng.choice([8, 12, 13, 13, 18, 19, 20, 21])
    else:
        h = rng.randint(9, 20)
    return f"{h:02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"


def _september_fixed(p: Profile) -> float:
    sep = (date(2026, 9, 1), date(2026, 9, 30))
    return round(sum(f.amount for f in p.fixed for d in f.dates if sep[0] <= d <= sep[1] and f.kind
                     not in NOT_SPENDING), 2)


def variable_budget(p: Profile) -> float:
    """September variable spending = target - September bills, subscriptions, one-offs and Klarna."""
    return round(p.target - _september_fixed(p), 2)


def _month_rows(p: Profile, month: date, money_days: list[date]) -> list[Tx]:
    factor = p.month_factor.get(month.month, p.month_factor.get(10, 1.0))
    budget = variable_budget(p) * factor
    last = month_end(month)
    days = [month + timedelta(days=i) for i in range((last - month).days + 1)]
    out: list[Tx] = []
    for ci, s in enumerate(p.spends):
        rng = random.Random(f"{p.seed}-{month.isoformat()}-{ci}")
        cat_budget = budget * s.share
        days_ok = [d for d in days if _eligible(s, d, p)]
        if cat_budget < 1 or not days_ok:
            continue
        weights = [_weight(s, d, p, money_days) for d in days_ok]
        mean_w = sum(weights) / len(weights)
        n = max(1, round(s.per_week * len(days_ok) / 7 * rng.uniform(0.9, 1.1) * min(1.3, mean_w)))
        chosen: list[date] = []
        pool, pw = list(days_ok), list(weights)
        for _ in range(min(n, len(pool))):
            k = rng.choices(range(len(pool)), weights=pw)[0]
            chosen.append(pool.pop(k))
            pw.pop(k)
        chosen.sort()
        events = []
        for d in chosen:
            m = rng.choices(s.merchants, weights=[x.weight for x in s.merchants])[0]
            amt = rng.uniform(m.lo, m.hi)
            if s.category == "Groceries" and any(0 <= (d - md).days <= 2 for md in money_days):
                amt = max(amt, rng.uniform(26.0, 34.0))  # a bigger shop after money arrives
            events.append([d, m, amt])
        for _ in range(4):  # scale to the category's monthly amount, then keep amounts in range
            total = sum(e[2] for e in events)
            scale = cat_budget / total if total else 1.0
            for e in events:
                e[2] = e[2] * scale
                if s.clamp:
                    e[2] = min(s.clamp[1], max(s.clamp[0], e[2]))
        for d, m, amt in events:
            out.append(Tx(d, _time(rng, s), "Card payment", m.name, s.category, -round(amt, 2), m.description,
                          SPEND))
    return out


def _all_rows(p: Profile, end: date) -> list[Tx]:
    income = _income_rows(p, end)
    money_days = sorted({s_d for s in p.streams for s_d, a in zip(s.dates, s.amounts, strict=True) if a >= 100})
    rows = income + _fixed_rows(p, end)
    for m in month_starts(START, end):
        rows += [t for t in _month_rows(p, m, money_days) if t.day <= end]
    rows.sort(key=lambda t: (t.day, t.time, t.description, t.amount))
    return rows


def opening_balance(p: Profile) -> float:
    rows = _all_rows(p, REF_END)
    return round(p.closing_ref - sum(t.amount for t in rows if t.kind != "transfer"), 2)


def statement(sample_id: str, end: date) -> tuple[Profile, list[Tx], float]:
    """(profile, rows with running balance, opening balance) from START to `end` inclusive."""
    p = profile(sample_id)
    rows = _all_rows(p, end)
    opening = opening_balance(p)
    bal = opening
    for t in rows:
        bal = round(bal + t.amount, 2)
        t.balance = bal
    return p, rows, opening


def savings_balance(p: Profile, rows: list[Tx]) -> float:
    return round(p.savings_open - sum(t.amount for t in rows if t.kind == SAVINGS), 2)


def non_rent_spending(rows: list[Tx], month: str) -> float:
    """Money out in `month` (YYYY-MM) except rent and savings transfers."""
    return round(-sum(t.amount for t in rows if t.amount < 0 and t.kind not in NOT_SPENDING
                      and t.day.isoformat()[:7] == month), 2)


# ---------- hints (what the statement cannot show) ---------------------------------------------------


def _klarna_owed(p: Profile, end: date) -> tuple[float, date | None]:
    owed, nxt = 0.0, None
    for f in p.fixed:
        if f.kind != BNPL:
            continue
        for d in f.dates:
            if d > end and any(x <= end for x in f.dates):
                owed += f.amount
                nxt = d if nxt is None or d < nxt else nxt
    return round(owed, 2), nxt


def income_sources(p: Profile, end: date) -> list[dict[str, object]]:
    out = []
    for s in p.streams:
        paid = [d for d in s.dates if START <= d <= end]
        later = [d for d in s.dates if d > end]
        if not paid and not later:
            continue
        amount = s.amounts[s.dates.index(paid[-1])] if paid else s.amounts[0]
        if s.kind == "part_time_job" and len(paid) >= 4 and s.schedule == "weekly":
            amount = round(sum(s.amounts[s.dates.index(d)] for d in paid[-4:]) / 4, 2)
        out.append({"id": s.id, "kind": s.kind, "amount": round(amount, 2), "schedule": s.schedule,
                    "next_date": later[0].isoformat() if later else None,
                    "dates": [d.isoformat() for d in (paid + later[:3])][-60:]})
    return out


def monthly_costs(p: Profile) -> float:
    total = 0.0
    for f in p.fixed:
        if f.kind in (RENT, BILL, SUB) and len(f.dates) > 1:
            gaps = (f.dates[-1] - f.dates[0]).days / max(1, len(f.dates) - 1)
            total += f.amount * 30.44 / gaps
    return round(total, 2)


def hints(p: Profile, rows: list[Tx], end: date) -> dict[str, object]:
    closing = rows[-1].balance if rows else opening_balance(p)
    slug = p.bank.lower().replace(" ", "_")
    accounts: list[dict[str, object]] = [{"id": f"{slug}_current", "name": f"{p.bank} {p.current_name}",
                                          "kind": "current", "provider": p.bank, "balance": closing}]
    savings = savings_balance(p, rows)
    if p.savings_name is not None:
        name = p.savings_name if p.savings_name.startswith(p.bank) else f"{p.bank} {p.savings_name}"
        accounts.append({"id": f"{slug}_savings", "name": name, "kind": "savings", "provider": p.bank,
                         "balance": savings})
    debts: list[dict[str, object]] = []
    if p.overdraft_limit is not None:
        debts.append({"id": "overdraft", "kind": "overdraft", "balance": round(max(0.0, -closing), 2),
                      "rate_pct": 0.0, "free_limit": p.overdraft_limit, "due_date": None})
    owed, due = _klarna_owed(p, end)
    if owed > 0:
        debts.append({"id": "bnpl_klarna", "kind": "bnpl", "balance": owed, "rate_pct": 0.0, "free_limit": None,
                      "due_date": due.isoformat() if due else None})
    return {
        "name": p.holder, "is_student": p.is_student, "age": p.age, "housing": p.housing,
        "student_loan_plan": p.plan, "income_sources": income_sources(p, end), "debts": debts,
        "monthly_costs": monthly_costs(p), "accounts": accounts, **plan_fields(p, rows, savings),
        "town": p.card.city, "region": p.card.region, "bank": p.bank, "as_of": end.isoformat(),
        "target_september": p.target, "sources": [s.as_dict() for s in p.sources],
    }


# Statement category -> engine category (lifeline_contracts.finance.Category), for budgets.
ENGINE_CATEGORY = {"Groceries": "groceries", "Eating out": "eating_out", "Transport": "transport",
                   "Shopping": "shopping", "Entertainment": "entertainment", "Bills": "bills",
                   "Subscriptions": "subscriptions", "Health": "health", "Education": "education",
                   "Holidays": "travel"}


def plan_fields(p: Profile, rows: list[Tx], savings: float) -> dict[str, object]:
    """Budgets (near the Aug/Sep average, a little under it) and goals (CreateGoalRequest + stable id)."""
    budgets = []
    for cat, mult in p.budgets:
        months = ("2026-08", "2026-09")
        spent = [-sum(t.amount for t in rows if t.amount < 0 and t.kind not in NOT_SPENDING
                      and ENGINE_CATEGORY.get(t.category) == cat and t.day.isoformat()[:7] == m) for m in months]
        avg = sum(spent) / 2 if spent else 0.0
        budgets.append({"category": cat, "limit": float(max(5, round(avg * mult / 5) * 5))})
    goals = [{"id": f"gl_sample_{p.id}_{i + 1}", "name": name, "emoji": emoji, "target": target,
              "saved": round(min(savings, target - 1), 2) if from_savings else 0.0, "target_date": when}
             for i, (name, emoji, target, when, from_savings) in enumerate(p.goals)]
    return {"budgets": budgets, "goals": goals}


# ---------- card ("Pick your student", ADR 0069) -----------------------------------------------------

HABIT_WORDS = {"Eating out": "eating out", "Groceries": "food shopping", "Entertainment": "nights out",
               "Transport": "travel", "Shopping": "clothes and shopping", "Holidays": "holidays",
               "Health": "health and beauty", "Education": "books"}


def habit_line(p: Profile, rows: list[Tx]) -> str:
    """One true sentence from the statement: the biggest everyday category and how the student saves."""
    spend: dict[str, float] = {}
    for t in rows:
        if t.amount < 0 and t.kind in (SPEND, ONE_OFF, BNPL):
            spend[t.category] = spend.get(t.category, 0.0) - t.amount
    top = max(spend, key=lambda c: spend[c])
    saved = -sum(t.amount for t in rows if t.kind == SAVINGS)
    days_below = len({t.day for t in rows if t.balance < 0})
    total_days = (rows[-1].day - rows[0].day).days + 1 if rows else 1
    if days_below * 2 >= total_days:
        tail = "often in the overdraft"
    elif days_below:
        tail = "dipped into the overdraft"
    elif saved > 0:
        tail = f"saved £{saved:,.0f} since July"
    elif any(t.kind == BNPL for t in rows):
        tail = "spreads payments with Klarna"
    else:
        tail = "no savings yet"
    return f"Not counting rent and bills, spends most on {HABIT_WORDS.get(top, top.lower())}; {tail}"


def card_money_in(p: Profile, rows: list[Tx]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for label, stream, period, dates, divisor, varies in p.card.money_in:
        paid = [t.amount for t in rows if t.stream == stream]
        if not paid:  # not paid yet (e.g. a late first loan payment): the first amount due
            paid = [a for s in p.streams if s.id == stream for a in s.amounts[:1]]
        amount = round(sum(paid[-4:]) / len(paid[-4:]), 2) if varies else paid[-1]
        if period == "year":
            amount = round(sum(a for s in p.streams if s.id == stream for a in s.amounts), 2)
        out.append({"label": label, "amount": round(amount / divisor, 2), "period": period, "dates": dates})
    return out


def card_fields(p: Profile, rows: list[Tx]) -> dict[str, object]:
    c = p.card
    return {"name": p.holder, "age": p.age, "avatar": c.avatar, "uni": c.uni, "city": c.city,
            "funding_label": c.funding_label, "money_in": card_money_in(p, rows), "housing": c.housing,
            "habit_line": habit_line(p, rows)}


def months_covered(end: date) -> int:
    return max(1, min(12, round(((end - START).days + 1) / 30.44)))


def index_entry(sample_id: str, end: date = REF_END) -> dict[str, object]:
    p, rows, _ = statement(sample_id, end)
    return {"id": p.id, "title": p.title, "description": p.description, "funding": p.funding,
            "months": months_covered(end), "team": False, **card_fields(p, rows), "hints": hints(p, rows, end)}


# ---------- statement files ---------------------------------------------------------------------------

CSV_HEADER = [
    "Transaction ID", "Date", "Time", "Type", "Name", "Emoji", "Category", "Amount", "Currency", "Local amount",
    "Local currency", "Notes and #tags", "Address", "Receipt", "Description", "Category split", "Money Out",
    "Money In",
]


def tx_id(p: Profile, i: int, t: Tx) -> str:
    import hashlib

    return "tx_0000" + hashlib.sha256(f"{p.id}|{i}|{t.day}|{t.amount}|{t.description}".encode()).hexdigest()[:18]


def to_csv(p: Profile, rows: list[Tx]) -> bytes:
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_HEADER)
    for i, t in enumerate(rows):
        amt = f"{t.amount:.2f}"
        w.writerow([tx_id(p, i, t), t.day.strftime("%d/%m/%Y"), t.time, t.type, t.name, "", t.category, amt,
                    "GBP", amt, "GBP", "", "", "", t.description, "", amt if t.amount < 0 else "",
                    amt if t.amount > 0 else ""])
    return buf.getvalue().encode("utf-8")


# ---------- expected forecast (data-side estimate of PENNY_V3_BUILD B2; the engine owns the real one) -------


def expected_forecast(p: Profile, rows: list[Tx], end: date, buffer_pct: float = 10.0) -> dict[str, object]:
    """B2 maths on the generator's own rows, so the seed can be checked against the A4 forecast states.
    Today = `end` (the statement's last day, as the import sets `as_of`)."""
    money = rows[-1].balance
    nxt = min((d for s in p.streams for d, a in zip(s.dates, s.amounts, strict=True) if d > end and a > 0),
              default=None)
    if nxt is None:
        return {"state": "no_next_money"}
    bills = round(sum(f.amount for f in p.fixed if f.kind in (RENT, BILL, SUB, BNPL)
                      for d in f.dates if end < d < nxt), 2)
    left = money - bills
    buffer = round(max(0.0, left) * buffer_pct / 100, 2)
    days = max(1, (nxt - end).days - 1)
    per_week = round((left - buffer) / days * 7, 2)
    since = end - timedelta(days=27)
    usual_weekly = round(-sum(t.amount for t in rows if t.amount < 0 and since <= t.day <= end
                              and t.kind in (SPEND, ONE_OFF)) / 4, 2)
    state = "on_track" if usual_weekly <= per_week else "running_short"
    out: dict[str, object] = {"state": state, "money_now": money, "next_money": nxt.isoformat(), "bills": bills,
                              "per_week": per_week, "usual_weekly": usual_weekly}
    if state == "running_short":
        daily = usual_weekly / 7
        out["run_out"] = (end + timedelta(days=max(0, int(left / daily)))).isoformat() if daily > 0 else None
    else:
        out["spare"] = round((per_week - usual_weekly) * days / 7, 2)
    return out
