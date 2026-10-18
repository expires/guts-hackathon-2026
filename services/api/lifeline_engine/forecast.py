"""The forecast Next Move (PENNY_V3_BUILD.md B2, ADR 0072). Pure: no I/O, no clock, no RNG. Callers pass `today`.

Question: "Will my money last until my next money arrives, and how much can I spend each week?"

Calculation, in order:
1. Money now = the sum of current account balances (an overdraft is a negative balance). Savings are not counted.
2. Next money = the first expected income after today from the income schedule (entered `income_sources`; when there
   are none, regular credits found in the statement). Payments on the same day are added together.
3. Days to cover = tomorrow to the day before the next money (today's spending is already in the statement).
4. Bills = recurring bills and subscriptions (found in the statement) due from tomorrow to the day before the next
   money. Each due date counts once, so rent counts only when its due date is in that window, and never twice.
5. Left after bills = money now - bills. Buffer = buffer % x left after bills, never below 0.
6. Per day = (left after bills - buffer) / days. Per week = per day x 7.
7. Usual spending = the average of the last 4 full weeks (today - 28 days to yesterday) of non-rent, non-bill
   spending. When the next money is more than 6 weeks away, usual spending is raised by the ONS CPI rate for the
   time until then (CPI x days / 365).
8. On track when usual <= per week: spare = (per week - usual) x days / 7. Running short otherwise:
   run-out date = today + whole days of (money now - bills) / usual daily spending.

Rounding rule (the detailed breakdown adds up exactly):
- Every money value is in pence (2 decimals). Inputs are rounded half up to pence first.
- The target buffer is buffer % x max(0, left after bills), rounded half up to pence.
- Per day is (left after bills - target buffer) / days, rounded DOWN to pence (never more than there is).
- The buffer then takes the rounding remainder: buffer = left after bills - per day x days. It is the target buffer
  plus less than `days` pence. So money now - bills - buffer == per day x days exactly.
- Per week = per day x 7 exactly (no further rounding needed). To spend = per day x days exactly.
  Screens round to whole pounds.
- Exception: when money available minus bills is below 0, buffer, per day, per week and to spend are all 0 (never
  negative) and the budget line states the shortfall. Only then the sum does not close (the gap is the shortfall).
- Money available = money now + expected income (smaller payments before the main next money).
- Budget period: "until_next_money" when days < 14 (the card shows the total until then), else "week".
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Literal

from lifeline_contracts.finance import Account, Category, FinanceSnapshot, Transaction
from lifeline_contracts.forecast import (
    BufferPct,
    Forecast,
    ForecastAccount,
    ForecastBill,
    ForecastIncome,
    ForecastSource,
    ForecastState,
    ForecastStep,
    NextMoney,
    SpendWeek,
    StressTest,
    Suggestion,
    TimelinePoint,
    WhatIfChange,
    WhatIfResult,
)
from lifeline_contracts.macro import MacroKey, MacroTable
from lifeline_engine import rules
from lifeline_engine.macro_access import value_or
from lifeline_engine.money import dates, finance_meta
from lifeline_engine.money.categorise import categorise, label
from lifeline_engine.money.predict import is_daily_spend
from lifeline_engine.money.recurring import detect_recurring, step
from lifeline_engine.student import detect_income, entered_next_dates

PENNY = Decimal("0.01")
BUFFER_OPTIONS: tuple[int, ...] = (0, 5, 10, 15, 20)
DEFAULT_BUFFER = 10
USUAL_WEEKS = 4
CPI_GAP_DAYS = 42  # over 6 weeks to the next money: raise usual spending by CPI
SPARE_MIN = Decimal("10")  # suggest putting spare aside only above £10
SHORT_WINDOW_DAYS = 14  # below this, the card shows the total until the next money, not a weekly amount
NO_NEXT_MONEY_DAYS = 28  # without a known next payment, the forecast covers the next 4 weeks
STRESS_YEAR = 2022
# ONS CPI annual rate for 2022 (series D7G7, annual average 9.1%). Used only when the MacroTable has no 2022 value.
INFLATION_2022_FALLBACK = 9.1

URL_ONS_CPI = "https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23"
URL_BOE_RATES = "https://www.bankofengland.co.uk/boeapps/database/"

SRC_STATEMENT = ForecastSource(label="Your statement")
SRC_ENTERED = ForecastSource(label="Dates you entered")
SRC_SETTING = ForecastSource(label="Your setting")
SRC_ONS_CPI = ForecastSource(label="ONS CPI", url=URL_ONS_CPI)
SRC_BOE = ForecastSource(label="Bank of England", url=URL_BOE_RATES)

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")

# ---------- money helpers ----------


def _d(x: float | int | Decimal) -> Decimal:
    """A money value in pence, rounded half up."""
    return (x if isinstance(x, Decimal) else Decimal(str(x))).quantize(PENNY, rounding=ROUND_HALF_UP)


def _f(x: Decimal) -> float:
    return float(x.quantize(PENNY, rounding=ROUND_HALF_UP))


def gbp(x: Decimal | float) -> str:
    """'£12.00', '-£371.03'. Exact pence, for the maths and the breakdown."""
    v = _d(x)
    return f"-£{-v:,.2f}" if v < 0 else f"£{v:,.2f}"


def gbp0(x: Decimal | float) -> str:
    """'£135'. Whole pounds, rounded half up, for the card."""
    v = _d(x).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"-£{-v:,.0f}" if v < 0 else f"£{v:,.0f}"


def day_text(d: date) -> str:
    """'2 November'. The year is not shown."""
    return f"{d.day} {MONTHS[d.month - 1]}"


def short_day(d: date) -> str:
    """'2 Nov'."""
    return f"{d.day} {MONTHS[d.month - 1][:3]}"


# ---------- macro inputs ----------


@dataclass(frozen=True)
class MacroInputs:
    """The three national figures the forecast uses, with their sources. Built from the MacroTable."""

    cpi: float | None
    inflation_2022: float
    boe_easy_access_rate: float | None
    cpi_source: ForecastSource = field(default_factory=lambda: SRC_ONS_CPI)
    inflation_2022_source: ForecastSource = field(default_factory=lambda: SRC_ONS_CPI)
    rate_source: ForecastSource = field(default_factory=lambda: SRC_BOE)


def _latest(macro: MacroTable, key: MacroKey, year: int) -> tuple[int, float] | None:
    years = [y for y in macro.years(key) if y <= year]
    if not years:
        return None
    y = years[-1]
    return y, value_or(macro, key, y, None, 0.0)


def macro_inputs(macro: MacroTable, today: date) -> MacroInputs:
    """CPI (latest year up to today), 2022 CPI (table, else the ONS constant above) and the BoE easy-access rate."""
    cpi = _latest(macro, MacroKey.CPI_INFLATION, today.year)
    rate = _latest(macro, MacroKey.SAVINGS_RATE, today.year)
    in_table = STRESS_YEAR in macro.years(MacroKey.CPI_INFLATION)
    infl_2022 = value_or(macro, MacroKey.CPI_INFLATION, STRESS_YEAR, None, INFLATION_2022_FALLBACK)
    return MacroInputs(
        cpi=None if cpi is None else cpi[1],
        inflation_2022=infl_2022 if in_table else INFLATION_2022_FALLBACK,
        boe_easy_access_rate=None if rate is None else rate[1],
        cpi_source=ForecastSource(label=f"ONS CPI, {cpi[0]}" if cpi else "ONS CPI", url=URL_ONS_CPI),
        inflation_2022_source=ForecastSource(label="ONS CPI, 2022", url=URL_ONS_CPI),
        rate_source=ForecastSource(label="Bank of England, easy-access savings rate", url=URL_BOE_RATES),
    )


# ---------- next money ----------

KIND_WORDS: dict[str, str] = {
    "maintenance_loan": "loan",
    "bursary": "bursary",
    "scholarship": "scholarship",
    "grant": "grant",
    "family": "money from family",
    "part_time_job": "pay",
    "salary": "salary",
    "other": "payment",
}
KIND_ORDER = tuple(KIND_WORDS)

# (loan label prefix, schedule source label, official URL) per region. England is the default.
LOAN_BODIES: dict[str, tuple[str, str, str]] = {
    "scotland": ("SAAS", "SAAS payment schedule", rules.URL_SAAS),
    "wales": ("Student Finance Wales", "Student Finance Wales payment dates", rules.URL_SFW),
    "northern-ireland": ("Student Finance NI", "Student Finance NI payment dates", rules.URL_SFNI),
}
LOAN_ENGLAND = ("Student Finance England", "Student Finance England payment dates", rules.URL_SFE_PAID)


@dataclass(frozen=True)
class _Source:
    id: str
    kind: str
    amount: Decimal
    schedule: str  # weekly, monthly, termly, yearly, one_off
    known: tuple[date, ...]  # known future dates (after today), oldest first
    last: date | None  # the latest known date (past or future), for projecting weekly and monthly money

    @property
    def monthly(self) -> Decimal:
        """Monthly-normalised amount: weekly x 52/12, fortnightly x 26/12, termly x 3/12, yearly / 12, monthly as
        is, one-off 0."""
        factor = {"weekly": Decimal(52) / 12, "fortnightly": Decimal(26) / 12, "monthly": Decimal(1),
                  "termly": Decimal(3) / 12,
                  "yearly": Decimal(1) / 12}.get(self.schedule, Decimal(0))
        return self.amount * factor

    def dates_before(self, today: date, end: date, step_days: int | None) -> list[date]:
        """Payment dates from tomorrow to the day before `end`. Weekly, fortnightly and monthly money is
        projected forward by its own rhythm (the gap between its last two dates, else its schedule); other money
        only on its known dates."""
        out = {d for d in self.known if today < d < end}
        if self.last is not None and self.schedule in ("weekly", "fortnightly", "monthly"):
            d = self.last
            while d < end:
                d = d + timedelta(days=step_days) if step_days else dates.add_months(d, 1)
                if today < d < end:
                    out.add(d)
        return sorted(out)


def _region(snap: FinanceSnapshot) -> str | None:
    return snap.region or (snap.holder.region if snap.holder is not None else None)


def _step_days(src: _Source, all_dates: Sequence[date]) -> int | None:
    if src.schedule == "fortnightly":
        return 14
    if src.schedule != "weekly":
        return None
    if len(all_dates) >= 2:
        gap = (all_dates[-1] - all_dates[-2]).days
        if 5 <= gap <= 16:
            return gap
    return 7


def _sources(snap: FinanceSnapshot, today: date) -> tuple[list[tuple[_Source, int | None]], bool]:
    """The income schedule (entered sources; else regular credits found in the statement) and whether it was entered."""
    out: list[tuple[_Source, int | None]] = []
    for src in snap.income_sources:
        known = entered_next_dates(src, today)
        every = sorted({*(dates.parse(x) for x in src.dates), *known})
        s = _Source(src.id, src.kind, _d(src.amount), src.schedule, known, every[-1] if every else None)
        out.append((s, _step_days(s, every)))
    if out:
        return out, True
    for i, found in enumerate(detect_income(snap.transactions, today)):
        s = _Source(f"found{i}", found.kind, _d(found.amount), "monthly", found.next_dates,
                    found.next_dates[-1] if found.next_dates else None)
        out.append((s, None))
    return out, False


def _words(snap: FinanceSnapshot, kinds: Sequence[str]) -> tuple[str, ForecastSource | None]:
    """'SAAS loan + bursary' and the official schedule source when one applies."""
    body = LOAN_BODIES.get(_region(snap) or "", LOAN_ENGLAND)
    ordered = sorted(kinds, key=lambda k: KIND_ORDER.index(k) if k in KIND_ORDER else 99)
    words: list[str] = []
    for k in ordered:
        w = f"{body[0]} loan" if k == "maintenance_loan" else KIND_WORDS.get(k, "payment")
        if w not in words:
            words.append(w)
    text = " + ".join(words)
    official = "maintenance_loan" in kinds or (body[0] == "SAAS" and "bursary" in kinds)
    return (text[0].upper() + text[1:])[:80], (ForecastSource(label=body[1], url=body[2]) if official else None)


@dataclass(frozen=True)
class IncomePlan:
    next_money: NextMoney | None
    expected: list[ForecastIncome]


def income_plan(snap: FinanceSnapshot, today: date, end_if_none: date, move_to: date | None = None) -> IncomePlan:
    """Next money = the next payment of the MAIN income source: the recurring source with the largest
    monthly-normalised amount (one-off money is never main). Payments of other sources on that day join it
    ('SAAS loan + bursary'). Every other payment from tomorrow to the day before is expected income, added to the
    money available. Without a main source, the window ends at `end_if_none`. `move_to` (what-if): the main payment
    arrives on that day instead; it is then not expected income on its old day."""
    srcs, entered = _sources(snap, today)
    plain = SRC_ENTERED if entered and snap.source == "manual" else SRC_STATEMENT
    mains = [s for s, _ in srcs if s.schedule != "one_off" and s.known]
    main = max(mains, key=lambda s: (s.monthly, -s.known[0].toordinal(), s.id), default=None)
    end = main.known[0] if main is not None else end_if_none
    nm: NextMoney | None = None
    moved: set[tuple[str, date]] = set()
    if main is not None:
        same = [s for s, _ in srcs if end in s.known]
        text, official = _words(snap, [s.kind for s in same])
        if move_to is not None:
            moved = {(s.id, end) for s in same}
            end = move_to
        nm = NextMoney(label=text, amount=_f(sum((s.amount for s in same), Decimal(0))), date=dates.iso(end),
                       source=official or plain)
    expected: list[ForecastIncome] = []
    for s, step_days in srcs:
        for d in s.dates_before(today, end, step_days):
            if (s.id, d) in moved:
                continue
            text, official = _words(snap, [s.kind])
            expected.append(ForecastIncome(label=text, amount=_f(s.amount), date=dates.iso(d),
                                           source=official or plain))
    expected.sort(key=lambda e: (e.date, e.label))
    return IncomePlan(nm, expected)


def next_money(snap: FinanceSnapshot, today: date) -> NextMoney | None:
    return income_plan(snap, today, today + timedelta(days=NO_NEXT_MONEY_DAYS + 1)).next_money


# ---------- bills ----------

_BILL_KIND: dict[str, Literal["bill", "subscription", "rent", "loan", "other"]] = {
    "bill": "bill", "subscription": "subscription", "rent": "rent", "mortgage": "rent", "loan": "loan", "card": "loan",
}


def bills_between(txs: Sequence[Transaction], today: date, end: date) -> list[ForecastBill]:
    """Recurring bills and subscriptions due from tomorrow up to the day before `end`. Each due date counts once."""
    out: list[ForecastBill] = []
    for r in detect_recurring(txs, today):
        d = r.next_due(today)
        while d <= today:
            d = step(d, r.cadence)
        while d < end:
            out.append(ForecastBill(name=r.name[:80], kind=_BILL_KIND.get(r.kind, "other"), amount=_f(_d(r.amount)),
                                    due_date=dates.iso(d)))
            d = step(d, r.cadence)
    out.sort(key=lambda b: (b.due_date, b.name))
    return out


# ---------- usual spending ----------


def usual_weeks(txs: Sequence[Transaction], today: date, weeks: int = USUAL_WEEKS) -> list[SpendWeek]:
    """The last `weeks` full weeks before today, oldest first. Non-rent, non-bill spending only."""
    out: list[SpendWeek] = []
    for w in range(weeks, 0, -1):
        start = today - timedelta(days=7 * w)
        end = start + timedelta(days=6)
        total = sum((_d(-t.amount) for t in txs if is_daily_spend(t) and start <= dates.parse(t.date) <= end),
                    Decimal(0))
        out.append(SpendWeek(start=dates.iso(start), end=dates.iso(end), amount=_f(total)))
    return out


def biggest_category(txs: Sequence[Transaction], today: date, weeks: int = USUAL_WEEKS
                     ) -> tuple[Category, Decimal] | None:
    """The biggest non-rent, non-bill category over the usual weeks, with its weekly amount."""
    start = today - timedelta(days=7 * weeks)
    totals: dict[Category, Decimal] = defaultdict(Decimal)
    for t in txs:
        if is_daily_spend(t) and start <= dates.parse(t.date) < today:
            totals[categorise(t)] += _d(-t.amount)
    if not totals:
        return None
    cat = max(totals, key=lambda c: (totals[c], c))
    return cat, _d(totals[cat] / weeks)


# ---------- the forecast ----------


def _accounts(snap: FinanceSnapshot) -> list[ForecastAccount]:
    def kind(a: Account) -> Literal["current", "savings", "credit", "overdraft", "other"]:
        if a.kind == "current":
            return "current"
        if a.kind in ("savings", "isa"):
            return "savings"
        if a.kind == "credit":
            return "credit"
        return "other"

    return [ForecastAccount(name=a.name[:80], kind=kind(a), balance=_f(_d(a.balance)), counted=a.kind == "current")
            for a in snap.accounts]


def _join(items: Sequence[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


@dataclass(frozen=True)
class _Maths:
    """The exact sums (Decimal, pence)."""

    money_now: Decimal
    expected: Decimal
    bills_total: Decimal
    left: Decimal
    target_buffer: Decimal
    buffer: Decimal
    per_day: Decimal
    per_week: Decimal


def maths(money_now: Decimal, bills_total: Decimal, buffer_pct: int, days: int,
          expected: Decimal = Decimal(0)) -> _Maths:
    """The core sum with the rounding rule of the module docstring. `days` >= 1."""
    left = money_now + expected - bills_total
    if left <= 0:  # nothing to spend: never a negative budget (BOSS, ADR 0072)
        return _Maths(money_now, expected, bills_total, left, Decimal(0), Decimal(0), Decimal(0), Decimal(0))
    target = _d(Decimal(buffer_pct) / 100 * left)
    per_day = ((left - target) / days).quantize(PENNY, rounding=ROUND_FLOOR)
    buffer = left - per_day * days
    return _Maths(money_now, expected, bills_total, left, target, buffer, per_day, per_day * 7)


def _run_out(today: date, left: Decimal, usual_weekly: Decimal) -> date:
    """today + whole days of (money now - bills) / usual daily spending. Today when nothing is left."""
    if left <= 0 or usual_weekly <= 0:
        return today
    return today + timedelta(days=int(left * 7 / usual_weekly))


def compute(
    snapshot: FinanceSnapshot,
    today: date,
    buffer_pct: BufferPct,
    cpi: float | None,
    inflation_2022: float,
    boe_easy_access_rate: float | None,
    stress: int | None = None,
    *,
    sources: MacroInputs | None = None,
    changes: Sequence[WhatIfChange] = (),
    notes: list[str] | None = None,
) -> Forecast:
    """The forecast for `snapshot` on `today`. `changes` (what-if) are applied to the next money, bills and expected
    income; a change that does not apply adds a sentence to `notes`. `cpi` and the rate may be None when the
    MacroTable has no value: then there is no CPI adjustment and the spare suggestion has no rate.
    `stress=2022` adds Forecast.stress."""
    if buffer_pct not in BUFFER_OPTIONS:
        raise ValueError(f"buffer_pct must be one of {BUFFER_OPTIONS}")
    if stress is not None and stress != STRESS_YEAR:
        raise ValueError(f"stress must be {STRESS_YEAR}")
    src = sources or MacroInputs(cpi=cpi, inflation_2022=inflation_2022, boe_easy_access_rate=boe_easy_access_rate)
    txs = snapshot.transactions

    no_end = today + timedelta(days=NO_NEXT_MONEY_DAYS + 1)
    plan = income_plan(snapshot, today, no_end)
    new_end = _moved_next_money(changes, plan.next_money, today, notes)
    if new_end is not None:
        plan = income_plan(snapshot, today, no_end, move_to=new_end)
    nm = plan.next_money
    if nm is not None:
        next_date = dates.parse(nm.date)
        days = max(1, (next_date - today).days - 1)
    else:
        next_date = today + timedelta(days=NO_NEXT_MONEY_DAYS + 1)
        days = NO_NEXT_MONEY_DAYS
    gap_days = (next_date - today).days

    money_now = sum((_d(a.balance) for a in snapshot.accounts if a.kind == "current"), Decimal(0))
    bills = bills_between(txs, today, next_date)
    expected_list = list(plan.expected)
    if changes:
        bills, expected_list = _apply_changes(changes, bills, expected_list, today, next_date, nm, notes)
        plan = IncomePlan(nm, expected_list)
    bills_total = sum((_d(b.amount) for b in bills), Decimal(0))
    expected_total = sum((_d(e.amount) for e in plan.expected), Decimal(0))
    m = maths(money_now, bills_total, int(buffer_pct), days, expected_total)

    weeks = usual_weeks(txs, today)
    usual_raw = _d(sum((_d(w.amount) for w in weeks), Decimal(0)) / len(weeks))
    cpi_adjusted = nm is not None and gap_days > CPI_GAP_DAYS and cpi is not None and cpi > 0
    usual = usual_raw
    cpi_note: str | None = None
    if cpi_adjusted:
        assert cpi is not None
        usual = _d(usual_raw * (1 + Decimal(str(cpi)) / 100 * gap_days / 365))
        cpi_note = (f"Your next money is {gap_days} days away, so your usual spending is raised by ONS CPI "
                    f"({cpi:g}% a year) for that time: {gbp(usual_raw)} becomes {gbp(usual)} a week.")
    usual_daily = _d(usual / 7)

    state: ForecastState = (
        "no_next_money" if nm is None else "on_track" if usual <= m.per_week else "running_short")
    spare: Decimal | None = None
    run_out: date | None = None
    if state == "on_track":
        spare = _d((m.per_week - usual) * days / 7)
    elif usual > m.per_week:
        run_out = _run_out(today, m.left, usual)

    big = biggest_category(txs, today)
    suggestion = _suggestion(state, spare, big, next_date, boe_easy_access_rate, src.rate_source)
    when = day_text(next_date)

    period: Literal["week", "until_next_money"] = (
        "until_next_money" if nm is not None and days < SHORT_WINDOW_DAYS else "week")
    headline, budget_line, habit_line = _card_text(state, m, usual, spare, run_out, big, nm, next_date, days,
                                                   period)
    steps = _steps(snapshot, m, bills, int(buffer_pct), days, nm, next_date, plan.expected)

    timeline = [TimelinePoint(date=dates.iso(today), kind="today", label="Today", amount=_f(money_now))]
    timeline += [TimelinePoint(date=b.due_date, kind="bill", label=b.name, amount=b.amount) for b in bills]
    if nm is not None:
        timeline.append(TimelinePoint(date=nm.date, kind="next_money", label=nm.label, amount=nm.amount))
    if run_out is not None and run_out < next_date:
        timeline.append(TimelinePoint(date=dates.iso(run_out), kind="run_out", label="Runs out"))
    order = {"today": 0, "bill": 1, "run_out": 2, "next_money": 3}
    timeline.sort(key=lambda p: (p.date, order[p.kind]))

    all_sources: list[ForecastSource] = [SRC_STATEMENT]
    if nm is not None:
        all_sources.append(nm.source)
    all_sources += [e.source for e in plan.expected]
    if cpi_adjusted:
        all_sources.append(src.cpi_source)
    if suggestion is not None and suggestion.source is not None:
        all_sources.append(suggestion.source)

    stress_test: StressTest | None = None
    if stress == STRESS_YEAR:
        stress_test = _stress(today, m, usual_raw, inflation_2022, state, next_date, when, src.inflation_2022_source)
        all_sources.append(src.inflation_2022_source)

    return Forecast(
        meta=finance_meta(snapshot),
        state=state,
        today=dates.iso(today),
        headline=headline,
        budget_line=budget_line,
        habit_line=habit_line,
        next_money=nm,
        money_now=_f(money_now),
        expected_income=plan.expected,
        expected_income_total=_f(expected_total),
        accounts=_accounts(snapshot),
        bills=bills,
        bills_total=_f(bills_total),
        buffer_pct=buffer_pct,
        buffer_amount=_f(m.buffer),
        days=days,
        per_day=_f(m.per_day),
        per_week=_f(m.per_week),
        budget_period=period,
        to_spend=_f(m.per_day * days),
        usual_weekly=_f(usual),
        usual_daily=_f(usual_daily),
        usual_weeks=weeks,
        cpi_adjusted=cpi_adjusted,
        cpi_note=cpi_note,
        spare=None if spare is None else _f(spare),
        run_out_date=None if run_out is None else dates.iso(run_out),
        suggestion=suggestion,
        steps=steps,
        timeline=timeline,
        sources=list({(s.label, s.url): s for s in all_sources}.values()),
        stress=stress_test,
    )


def _card_text(state: ForecastState, m: _Maths, usual: Decimal, spare: Decimal | None, run_out: date | None,
               big: tuple[Category, Decimal] | None, nm: NextMoney | None, next_date: date, days: int,
               period: str) -> tuple[str, str, str]:
    when = day_text(next_date)
    to_spend = m.per_day * days
    if period == "until_next_money":
        amount = f"{gbp0(to_spend)} until {when} (about {gbp0(m.per_day)} a day)"
    else:
        amount = f"{gbp0(m.per_week)} a week (about {gbp0(m.per_day)} a day)"
    if state == "no_next_money":
        headline = "Add your next payment to see if your money lasts"
        budget = (f"For the next 4 weeks, you can spend {amount}" if m.left > 0
                  else "Your bills take all your money for the next 4 weeks")
        return headline, budget, f"You usually spend {gbp0(usual)} a week."
    if state == "on_track":
        headline = f"You'll make it to {when}"
        budget = f"You can spend {amount}"
        assert spare is not None
        habit = (f"You usually spend {gbp0(usual)}, so you'll have about {gbp0(spare)} spare."
                 if gbp0(spare) != "£0" else f"You usually spend {gbp0(usual)}, so you'll just make it.")
        return headline, budget, habit
    assert run_out is not None
    if m.left <= 0:
        # Overdrawn with no bills due (Callum) is not a bills problem: say what is true (V5 F3).
        headline = (f"Your bills take all your money before {when}" if m.bills_total > 0
                    else f"You have no money to spend before {when}")
    elif run_out < next_date:
        headline = f"At this pace, you run out on {day_text(run_out)}"
    else:  # the money lasts, but only by using the safety buffer
        headline = f"At this pace, you use your safety buffer before {when}"
    if m.left < 0:
        budget = f"You are {gbp0(-m.left)} short before {when}"
    elif m.left == 0:
        budget = f"You have nothing left to spend until {when}"
    else:
        budget = f"Keep it under {amount}"
    habit = f"You usually spend {gbp0(usual)}."
    if big is not None:
        habit += f" {label(big[0])} is your biggest cost: {gbp0(big[1])} a week."
    return headline, budget, habit


def _suggestion(state: ForecastState, spare: Decimal | None, big: tuple[Category, Decimal] | None,
                next_date: date, rate: float | None, rate_source: ForecastSource) -> Suggestion | None:
    if state == "on_track" and spare is not None and spare > SPARE_MIN:
        return Suggestion(
            kind="save_spare",
            text=f"Put your {gbp0(spare)} spare aside on {day_text(next_date)}",
            amount=_f(spare),
            rate_pct=rate,
            source=rate_source if rate is not None else None,
        )
    if state != "on_track" and big is not None:
        name = label(big[0])
        return Suggestion(
            kind="cut_category",
            text=f"Spend less on {name.lower()}. It is your biggest cost: {gbp0(big[1])} a week.",
            amount=_f(big[1]),
            category=big[0],
            source=SRC_STATEMENT,
        )
    return None


def _steps(snap: FinanceSnapshot, m: _Maths, bills: Sequence[ForecastBill], buffer_pct: int, days: int,
           nm: NextMoney | None, next_date: date, expected: Sequence[ForecastIncome] = ()) -> list[ForecastStep]:
    current = [a for a in snap.accounts if a.kind == "current"]
    saved = any(a.kind in ("savings", "isa") for a in snap.accounts)
    not_saved = " Savings are not counted." if saved else ""
    if m.money_now < 0:
        t1 = f"Your current account is {gbp(-m.money_now)} overdrawn, so you start at {gbp(m.money_now)}.{not_saved}"
    else:
        acc = "Your current account" if len(current) <= 1 else "Your current accounts"
        t1 = f"{acc} today: {gbp(m.money_now)}.{not_saved}"
    s1_sources = [SRC_STATEMENT]
    title = "Money now"
    if expected:
        groups: dict[str, list[Decimal]] = {}
        for e in expected:
            groups.setdefault(e.label, []).append(_d(e.amount))
        parts = [f"{k} {gbp(sum(v, Decimal(0)))}" + (f" ({len(v)} payments)" if len(v) > 1 else "")
                 for k, v in groups.items()]
        avail = m.money_now + m.expected
        more = (f" Expected before {short_day(next_date)}: {_join(parts)}. "
                f"Money available: {gbp(avail)}.")
        if len(t1 + more) > 240:
            more = f" Expected before {short_day(next_date)}: {gbp(m.expected)}. Money available: {gbp(avail)}."
        t1 += more
        title = "Money now and expected"
        s1_sources += [e.source for e in expected if e.source not in s1_sources][:3]
    s1 = ForecastStep(id="money_now", title=title, amount=_f(m.money_now + m.expected), text=t1[:240],
                      sources=s1_sources[:4])

    before = day_text(next_date) if nm is not None else "the end of the next 4 weeks"
    if bills:
        names = [f"{b.name} {gbp(b.amount)}" for b in bills]
        shown = names if len(names) <= 3 else [*names[:2], f"{len(names) - 2} more"]
        t2 = f"{_join(shown)}: {gbp(m.bills_total)} in total, found in your statement."
        if len(t2) > 240:
            t2 = f"{len(names)} bills: {gbp(m.bills_total)} in total, found in your statement."
    else:
        t2 = f"No bills or subscriptions are due before {before} in your statement."
    s2 = ForecastStep(id="bills", title=f"Bills before {short_day(next_date)}" if nm else "Bills in the next 4 weeks",
                      amount=0.0 - _f(m.bills_total), text=t2, sources=[SRC_STATEMENT])

    if m.left <= 0:
        t3 = f"Nothing is left after bills ({gbp(m.left)}), so there is no buffer."
    elif buffer_pct == 0:
        t3 = "No safety buffer. 10% is recommended. You can change it."
    else:
        t3 = (f"{buffer_pct}% of what's left after bills ({gbp(m.left)}), kept back for surprises. "
              f"10% is recommended. You can change it.")
    extra = m.buffer - m.target_buffer
    if extra > 0:
        t3 += f" It includes {int(extra * 100)}p so the days add up exactly."
    s3 = ForecastStep(id="buffer", title=f"Safety buffer, {buffer_pct}%", amount=0.0 - _f(m.buffer), text=t3,
                      sources=[SRC_SETTING])

    spend = m.left - m.buffer
    sum_text = (f"{gbp(spend)} ÷ {days} days = {gbp(m.per_day)} a day, {gbp(m.per_week)} a week."
                if m.left >= 0 else f"Bills take {gbp(-m.left)} more than you have, so there is nothing to spend.")
    if nm is not None:
        t4 = f"Your next money: {nm.label}, {gbp(nm.amount)}, expected {day_text(next_date)}. {sum_text}"
        if len(t4) > 240:
            t4 = f"Next money expected {day_text(next_date)}. {sum_text}"
        s4 = ForecastStep(id="result", title=f"Next money: {short_day(next_date)}", amount=_f(m.per_week), text=t4,
                          sources=[nm.source])
    else:
        t4 = f"We don't know when your next money comes, so this covers the next 4 weeks. {sum_text}"
        s4 = ForecastStep(id="result", title="The next 4 weeks", amount=_f(m.per_week), text=t4,
                          sources=[SRC_STATEMENT])
    return [s1, s2, s3, s4]


def _stress(today: date, m: _Maths, usual_raw: Decimal, inflation: float, state: ForecastState, next_date: date,
            when: str, source: ForecastSource) -> StressTest:
    """Usual spending x (1 + 2022 CPI). Same money, bills and buffer."""
    usual = _d(usual_raw * (1 + Decimal(str(inflation)) / 100))
    run_out: date | None = None
    s_state: ForecastState = (
        "no_next_money" if state == "no_next_money" else "on_track" if usual <= m.per_week else "running_short")
    head = f"If prices rose {inflation:g}% like in 2022, your usual week would cost {gbp0(usual)}."
    if s_state == "running_short":
        run_out = _run_out(today, m.left, usual)
        tail = (f" You would run out on {day_text(run_out)}." if run_out < next_date
                else f" You would use your safety buffer before {when}.")
    elif s_state == "on_track":
        tail = f" You would still make it to {when}."
    else:
        tail = f" You can spend {gbp0(m.per_week)} a week."
    return StressTest(year=STRESS_YEAR, inflation_pct=inflation, state=s_state, per_week=_f(m.per_week),
                      usual_weekly=_f(usual), run_out_date=None if run_out is None else dates.iso(run_out),
                      text=(head + tail)[:240], source=source)


# ---------- what if (Penny's forecast_what_if tool) ----------

SRC_WHAT_IF = ForecastSource(label="Your what-if")
NEXT_MONEY_WORDS = ("next money", "next_money", "next payment", "income")


def _is_next_money(target: str | None, nm: NextMoney) -> bool:
    if target is None:
        return True
    t = target.strip().lower()
    lab = nm.label.lower()
    return t in NEXT_MONEY_WORDS or t in lab or lab in t or any(w in lab.split() for w in t.split() if len(w) > 2)


def _bill_matches(target: str | None, b: ForecastBill) -> bool:
    if not target:
        return False
    t, name = target.strip().lower(), b.name.lower()
    return t in name or name in t or t == b.kind


def _moved_next_money(changes: Sequence[WhatIfChange], nm: NextMoney | None, today: date,
                      notes: list[str] | None) -> date | None:
    """The new next money date of a move_payment change that targets the next money (not a bill)."""
    for c in changes:
        if c.kind != "move_payment" or nm is None:
            continue
        bill_named = c.target is not None and not _is_next_money(c.target, nm)
        if bill_named:
            continue
        old = dates.parse(nm.date)
        new = dates.parse(c.date) if c.date else old + timedelta(days=int(c.amount or 0))
        if new <= today:
            if notes is not None:
                notes.append("The new date for your next money is not after today, so it was not moved.")
            continue
        return new
    return None


def _apply_changes(changes: Sequence[WhatIfChange], bills: list[ForecastBill], expected: list[ForecastIncome],
                   today: date, end: date, nm: NextMoney | None, notes: list[str] | None
                   ) -> tuple[list[ForecastBill], list[ForecastIncome]]:
    """One-off costs and extra income inside the window count; outside it they do not (with a note). Bills move or
    change amount by name."""
    out_bills, out_income = list(bills), list(expected)

    def note(text: str) -> None:
        if notes is not None:
            notes.append(text)

    for c in changes:
        when = dates.parse(c.date) if c.date else today + timedelta(days=1)
        inside = today < when < end
        if c.kind == "one_off_cost":
            name = (c.label or "One-off cost")[:80]
            if inside:
                out_bills.append(ForecastBill(name=name, kind="other", amount=_f(_d(abs(c.amount or 0))),
                                              due_date=dates.iso(when)))
            else:
                note(f"{name} on {day_text(when)} is not before your next money, so it does not change this.")
        elif c.kind == "extra_income":
            name = (c.label or "Extra income")[:80]
            if inside:
                out_income.append(ForecastIncome(label=name, amount=_f(_d(abs(c.amount or 0))),
                                                 date=dates.iso(when), source=SRC_WHAT_IF))
            else:
                note(f"{name} on {day_text(when)} comes after your next money, so it does not help before then.")
        elif c.kind == "move_payment":
            if nm is not None and (c.target is None or _is_next_money(c.target, nm)):
                continue  # handled before the window was set
            hit = next((b for b in out_bills if _bill_matches(c.target, b)), None)
            if hit is None:
                note(f"No bill called {c.target} is due before your next money.")
                continue
            new = dates.parse(c.date) if c.date else dates.parse(hit.due_date) + timedelta(days=int(c.amount or 0))
            out_bills.remove(hit)
            if today < new < end:
                out_bills.append(hit.model_copy(update={"due_date": dates.iso(new)}))
            else:
                note(f"{hit.name} moves to {day_text(new)}, after your next money.")
        elif c.kind == "recurring_cost_change":
            hits = [b for b in out_bills if _bill_matches(c.target, b)]
            if not hits:
                note(f"No bill called {c.target} is due before your next money.")
                continue
            amount = _f(_d(abs(c.amount or 0)))
            out_bills = [b.model_copy(update={"amount": amount}) if b in hits else b for b in out_bills]
    out_bills.sort(key=lambda b: (b.due_date, b.name))
    out_income.sort(key=lambda e: (e.date, e.label))
    return out_bills, out_income


def usual_pay(snapshot: FinanceSnapshot) -> float | None:
    """The usual amount of one pay packet from the part-time job (or salary) in the income schedule. A what-if for
    'extra shifts' can use it. None without a job income."""
    for kind in ("part_time_job", "salary"):
        amounts = [s.amount for s in snapshot.income_sources if s.kind == kind]
        if amounts:
            return round(sum(amounts) / len(amounts), 2)
    return None


def _summary(before: Forecast, after: Forecast, notes: Sequence[str]) -> str:
    """'With this change you are still on track. You can spend £120 a week (about £17 a day) (was £135).'"""
    if after.state == "on_track":
        lead = "you are still on track" if before.state == "on_track" else "you would be on track"
    elif after.state == "running_short":
        lead = "you would run short" if before.state != "running_short" else "you still run short"
    else:
        lead = "we still don't know when your next money comes"
    was = (f"{gbp0(before.per_week)} a week" if before.budget_period == "week"
           else f"{gbp0(before.to_spend)} in total")
    changed = before.budget_line != after.budget_line
    text = f"With this change {lead}. {after.budget_line}" + (f" (was {was})" if changed else "") + "."
    next_money_date = after.next_money.date if after.next_money is not None else None
    runs_out_first = next_money_date is None or after.run_out_date is None or after.run_out_date < next_money_date
    if (after.state == "running_short" and after.run_out_date and after.run_out_date != after.today
            and runs_out_first):  # never a run-out date after the next money arrives (V2 warning)
        text += f" At this pace you run out on {day_text(dates.parse(after.run_out_date))}."
    for n in notes:
        if len(text) + len(n) + 1 <= 240:
            text += f" {n}"
    return text[:240]


def what_if(
    snapshot: FinanceSnapshot,
    today: date,
    buffer_pct: BufferPct,
    cpi: float | None,
    inflation_2022: float,
    boe_easy_access_rate: float | None,
    changes: Sequence[WhatIfChange],
    *,
    sources: MacroInputs | None = None,
) -> WhatIfResult:
    """The B2 forecast before and after `changes`, with one plain summary sentence. Pure."""
    before = compute(snapshot, today, buffer_pct, cpi, inflation_2022, boe_easy_access_rate, sources=sources)
    notes: list[str] = []
    after = compute(snapshot, today, buffer_pct, cpi, inflation_2022, boe_easy_access_rate, sources=sources,
                    changes=changes, notes=notes)
    return WhatIfResult(changes=list(changes), before=before, after=after,
                        summary=_summary(before, after, list(dict.fromkeys(notes))))
