"""Student money inputs and calculations (ADR 0046). Pure: no I/O, no clock, no RNG.

FinanceSnapshot has no student fields yet. `StudentInputs` is the small typed input the engine needs; the caller
may pass one to `next_move(..., student=...)`. Without it, `from_snapshot` builds one from data only:
- age: a range from holder.birth_year (the birthday is unknown, so age is year - birth_year - 1 or year - birth_year).
- income: regular credits found in the transactions (monthly or weekly), with the next date one cadence after the
  last credit. Termly money (a maintenance loan) is used only when its dates are entered: never projected.
- debts: cards and loans from accounts. An overdraft counts as expensive only beyond a known free limit.
Nothing is invented (ADR 0053 bug 3).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from lifeline_contracts.finance import Cadence, FinanceSnapshot, Transaction
from lifeline_contracts.finance import IncomeSource as ContractIncome
from lifeline_engine.money import dates
from lifeline_engine.money.categorise import categorise, merchant_key
from lifeline_engine.money.predict import is_daily_spend
from lifeline_engine.money.recurring import detect_recurring, step

IncomeKind = str  # maintenance_loan, scholarship, bursary, grant, family, part_time_job, salary, other
DebtKind = str  # card, overdraft, bnpl, loan

_INCOME_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("maintenance_loan", ("student loan", "slc", "saas", "student finance")),
    ("scholarship", ("scholarship",)),
    ("bursary", ("bursary",)),
    ("grant", ("grant",)),
    ("salary", ("salary", "payroll", "wages", "pay from")),
    ("family", ("mum", "dad", "family", "parents")),
)


@dataclass(frozen=True)
class IncomeSource:
    kind: IncomeKind
    amount: float  # GBP per payment
    next_dates: tuple[date, ...] = ()  # known future payment dates, oldest first
    name: str = ""


@dataclass(frozen=True)
class Debt:
    kind: DebtKind
    balance: float  # GBP owed, >= 0
    rate_pct: float | None = None
    free_limit: float | None = None  # interest-free overdraft limit, when known

    @property
    def expensive(self) -> float:
        """GBP that costs interest: all of a card or loan; an overdraft only beyond its known free limit;
        BNPL only with a known rate above 0 (most plans are 0% when paid on time)."""
        if self.kind == "overdraft":
            if self.free_limit is not None:
                return max(0.0, self.balance - self.free_limit)
            # W-V2-4: an entered rate above 0 with no free limit means it costs from the first pound.
            return self.balance if self.rate_pct is not None and self.rate_pct > 0 else 0.0
        if self.kind == "bnpl":
            return self.balance if self.rate_pct is not None and self.rate_pct > 0 else 0.0
        return self.balance


@dataclass(frozen=True)
class StudentInputs:
    age_min: int | None = None
    age_max: int | None = None
    is_student: bool | None = None
    income: tuple[IncomeSource, ...] = ()
    debts: tuple[Debt, ...] = field(default_factory=tuple)

    def next_income(self, today: date) -> tuple[date, IncomeSource] | None:
        """The first known payment AFTER `today` (F-V2-4): money due today is treated as already in the balance."""
        found = [(d, s) for s in self.income for d in s.next_dates if d > today]
        return min(found, key=lambda x: (x[0], x[1].kind)) if found else None


def income_kind(t: Transaction) -> IncomeKind:
    text = f"{t.description} {t.merchant or ''}".lower()
    for kind, words in _INCOME_WORDS:
        if any(w in text for w in words):
            return kind
    return "other"


def detect_income(txs: Sequence[Transaction], today: date) -> tuple[IncomeSource, ...]:
    """Regular credits: the same payer, at least 2 credits a month apart (20 to 40 days) or 3 a week apart
    (5 to 9 days). Next date = last credit + one cadence; only dates after `today` are kept (a missed payment
    is not projected)."""
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in txs:
        credit = categorise(t) in ("income", "transfers", "other")
        if t.amount > 0 and credit and "interest" not in t.description.lower():
            groups[merchant_key(t)].append(t)
    out: list[IncomeSource] = []
    for key, items in sorted(groups.items()):
        items.sort(key=lambda t: t.date)
        ds = [dates.parse(t.date) for t in items if dates.parse(t.date) <= today]
        if len(ds) < 2:
            continue
        gaps = [(b - a).days for a, b in zip(ds, ds[1:], strict=False)]
        recent = gaps[-3:]
        if all(20 <= g <= 40 for g in recent):
            nxt = step(ds[-1], "monthly")
        elif len(ds) >= 3 and all(5 <= g <= 9 for g in recent):
            nxt = step(ds[-1], "weekly")
        elif len(ds) >= 3 and all(12 <= g <= 16 for g in recent):
            nxt = dates.add_days(ds[-1], 14)  # fortnightly pay
        else:
            continue
        if nxt <= today:  # due today or missed: the next one is not projected from this source
            continue
        last = items[-3:]
        amount = round(sum(t.amount for t in last) / len(last), 2)
        out.append(IncomeSource(kind=income_kind(items[-1]), amount=amount, next_dates=(nxt,), name=key))
    return tuple(out)


YEARLY_FACTOR: dict[str, float] = {"weekly": 52.0, "fortnightly": 26.0, "monthly": 12.0, "termly": 3.0, "yearly": 1.0,
                                   "one_off": 0.0}


def entered_next_dates(src: ContractIncome, today: date, horizon_days: int = 400) -> tuple[date, ...]:
    """Known future payment dates of an entered source: its `dates` and `next_date`. A weekly, fortnightly or monthly
    source with a next_date in the past steps forward by its own schedule. Termly, yearly and one-off money is used only
    on the dates entered (ADR 0053 bug 3)."""
    found = {dates.parse(d) for d in src.dates}
    if src.next_date is not None:
        d = dates.parse(src.next_date)
        if src.schedule == "fortnightly":
            while d <= today and (today - d).days < horizon_days:
                d = dates.add_days(d, 14)
        elif src.schedule in ("weekly", "monthly"):
            cad: Cadence = "weekly" if src.schedule == "weekly" else "monthly"
            while d <= today and (today - d).days < horizon_days:
                d = step(d, cad)
        found.add(d)
    return tuple(sorted(d for d in found if d > today))


def entered_monthly_income(s: FinanceSnapshot) -> float | None:
    """Average GBP a month from entered income sources (one-off money excluded). None when none are entered."""
    if not s.income_sources:
        return None
    return sum(src.amount * YEARLY_FACTOR[src.schedule] for src in s.income_sources) / 12


def from_snapshot(s: FinanceSnapshot, today: date) -> StudentInputs:
    """Entered fields first (ADR 0049 onboarding), then what the transactions show."""
    age_min = age_max = None
    if s.age is not None:
        age_min = age_max = s.age
    elif s.holder is not None:
        age_max = today.year - s.holder.birth_year
        age_min = age_max - 1
    entered = tuple(
        IncomeSource(kind=src.kind, amount=src.amount, next_dates=entered_next_dates(src, today), name=src.id)
        for src in s.income_sources
    )
    if s.debts:  # entered debts replace what the accounts show, so nothing is counted twice
        return StudentInputs(
            age_min=age_min, age_max=age_max, is_student=s.is_student,
            income=entered + detect_income(s.transactions, today),
            debts=tuple(Debt(kind=d.kind, balance=d.balance, rate_pct=d.rate_pct, free_limit=d.free_limit)
                        for d in s.debts),
        )
    debts = [
        Debt(kind="card" if a.kind == "credit" else "loan", balance=-a.balance)
        for a in s.accounts
        if a.kind in ("credit", "loan") and a.balance < 0
    ]
    debts += [Debt(kind="overdraft", balance=-a.balance) for a in s.accounts if a.kind == "current" and a.balance < 0]
    return StudentInputs(age_min=age_min, age_max=age_max, is_student=s.is_student,
                         income=entered + detect_income(s.transactions, today), debts=tuple(debts))


# ---------- weekly budget ----------

SPEND_WEEKS = 4  # weeks of recent spending used for the current pace


@dataclass(frozen=True)
class WeeklyBudget:
    next_date: date
    next_kind: IncomeKind
    days_left: int
    weeks_left: float
    cash: float
    bills_before: float  # regular bills due before the next payment
    safe_weekly: float  # (cash - bills_before) / weeks_left, never below 0
    weekly_pace: float  # median weekly day-to-day spending over the last SPEND_WEEKS weeks (usual week)
    weeks_covered: float  # weeks the cash lasts at the current pace (after bills)
    short_by: float  # bills before + pace x weeks - cash (ADR 0057), 0 when on track
    weeks_seen: int
    weeks_within: int  # past weeks whose spending was at or under safe_weekly


def bills_before(txs: Sequence[Transaction], today: date, until: date) -> float:
    """Regular outgoings (rent, bills, subscriptions) due from today up to `until`."""
    total = 0.0
    for r in detect_recurring(txs, today):
        d = r.next_due(today)
        while d < until:
            if d >= today:
                total += r.amount
            d = step(d, r.cadence)
    return round(total, 2)


def weekly_spend(txs: Sequence[Transaction], today: date, weeks: int = SPEND_WEEKS) -> list[float]:
    """Day-to-day spending per week for the last `weeks` full weeks before today (bills excluded)."""
    out: list[float] = []
    for w in range(weeks, 0, -1):
        start = dates.add_days(today, -7 * w)
        end = dates.add_days(start, 7)
        out.append(round(sum(-t.amount for t in txs if is_daily_spend(t) and start <= dates.parse(t.date) < end), 2))
    return out


def weekly_budget(s: FinanceSnapshot, inp: StudentInputs, today: date, cash: float) -> WeeklyBudget | None:
    """Money left until the next income arrives. None without a known next payment or without recent spending."""
    nxt = inp.next_income(today)
    if nxt is None:
        return None
    when, src = nxt
    days = (when - today).days
    if days <= 0:
        return None
    weeks_left = days / 7
    bills = bills_before(s.transactions, today, when)
    free = max(0.0, cash - bills)
    safe = free / weeks_left
    weeks = weekly_spend(s.transactions, today)
    if not any(weeks):
        return None
    pace = float(np.median(weeks))  # W-R-1: the usual week; one big purchase does not double the pace
    covered = free / pace if pace > 0 else weeks_left
    short = max(0.0, bills + pace * weeks_left - cash)
    within = sum(1 for w in weeks if w <= safe)
    return WeeklyBudget(when, src.kind, days, weeks_left, cash, bills, safe, pace, covered, short, len(weeks), within)


# ---------- Lifetime ISA ----------

LISA_BONUS_PCT = 25.0  # facts_table rule.lisa_bonus_rate
LISA_CAP = 4_000.0  # facts_table rule.lisa_allowance
LISA_CHARGE_PCT = 25.0  # facts_table rule.lisa_withdrawal_charge
LISA_MIN_AGE = 18  # rule.lisa_min_open_age
LISA_MAX_OPEN_AGE = 39  # must open before 40 (rule.lisa_open_age_limit)


def lisa_age_ok(inp: StudentInputs) -> bool:
    return (
        inp.age_min is not None and inp.age_max is not None
        and inp.age_min >= LISA_MIN_AGE and inp.age_max <= LISA_MAX_OPEN_AGE
    )


def lisa_bonus(contribution: float) -> float:
    """Government bonus: 25% of what you pay in, on up to £4,000 a year (max £1,000)."""
    return min(contribution, LISA_CAP) * LISA_BONUS_PCT / 100


def lisa_withdrawal_loss(contribution: float) -> float:
    """Money lost when taking it out for something other than a first home or after 60: the 25% charge on
    (contribution + bonus) minus the bonus. With £1,000 in: bonus £250, charge 25% of £1,250 = £312.50,
    loss = £62.50 (6.25% of what you paid in)."""
    c = min(contribution, LISA_CAP)
    return (c + lisa_bonus(c)) * LISA_CHARGE_PCT / 100 - lisa_bonus(c)
