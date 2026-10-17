"""Find income sources, debts and student status in imported transactions. Deterministic rules, no LLM.

Only facts the statement shows. Unknown values stay None (age, loan plan, savings rate).

Income (credits only; the first matching rule wins; text = merchant + description, lower case):
  bursary          "bursary"
  scholarship      "scholarship"
  grant            the word "grant"
  maintenance_loan "student loans company", "student finance", "slc", "maintenance loan"
  family           mum, mom, mam, dad, parent(s), family, nan, gran, grandma, grandad, "allowance", "pocket money"
  salary / part_time_job
                   salary, wage(s), payroll, "net pay", "rider payment", payout. Monthly equivalent of
                   £1,200 or more -> salary, else part_time_job.
  other            any other payer that paid 3+ times; refunds (card payment rows) are not income.
Schedule from the median gap between payments: <= 10 days weekly, <= 45 monthly, <= 200 termly, else yearly.
One payment: termly for loan, grant, bursary, scholarship; otherwise one_off.

Debts:
  overdraft  a charge row that says "overdraft", or a known negative closing balance. Balance = minus the
             closing balance when the file shows balances, else 0 (Monzo CSV has no balance). Rate from
             "NN% EAR" or "NN% APR" in the charge text.
  bnpl       payments to Klarna, Clearpay or PayPal Pay in 3. Pay in 3 model: payments of one amount to one
             shop, 25-35 days apart, form a plan of 3. Balance = unpaid instalments of plans whose last payment
             is within 35 days of the statement end. Rate 0 (Pay in 3 is interest free).

Student: True when a student income kind is found, or the spending shows student-only items (students'
union, 16-25 Railcard, student subscriptions, university payments). Otherwise None (not shown).
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta
from statistics import median

from lifeline_contracts.finance import Account, DebtItem, IncomeKind, IncomeSchedule, IncomeSource, Transaction

STUDENT_KINDS: set[str] = {"maintenance_loan", "scholarship", "bursary", "grant"}

_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("bursary", re.compile(r"bursary")),
    ("scholarship", re.compile(r"scholarship")),
    ("grant", re.compile(r"\bgrant\b")),
    ("maintenance_loan", re.compile(r"student loans? co|student finance|\bslc\b|maintenance loan")),
    ("family", re.compile(r"\b(mum|mom|mam|mummy|dad|daddy|parents?|family|nan|nana|gran|grandma|grandad|"
                          r"grandpa)\b|allowance|pocket money")),
    ("job", re.compile(r"\b(salary|wages?|payroll|net pay|rider payment|payout)\b")),
]
_STUDENT_MARKERS = re.compile(
    r"students'? union|student union|uni union|\bsu (bar|cafe|coffee|shop)\b|\byusu\b|16-25 railcard|unidays|"
    r"totum|spotify student|prime student|student loans co|university|uni of|\buoy\b"
)
_REFUND_TYPES = {"card payment", "eating out", "groceries", "shopping", "transport", "entertainment"}
_BNPL = re.compile(r"klarna|clearpay|paypal pay in 3|pay in 3")
_OVERDRAFT = re.compile(r"overdraft")
_RATE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:ear|apr)")
SALARY_MONTHLY_MIN = 1200.0


def _text(t: Transaction) -> str:
    return f"{t.merchant or ''} {t.description}".lower()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "unknown"


def _payer(t: Transaction) -> str:
    return _slug(t.merchant or t.description)


def _add_month(d: date) -> date:
    y, m = divmod(d.month, 12)
    return date(d.year + y, m + 1, min(d.day, 28))


def _schedule(kind: str, dates: list[date]) -> IncomeSchedule:
    if len(dates) < 2:
        return "termly" if kind in STUDENT_KINDS else "one_off"
    gap = median((b - a).days for a, b in zip(dates, dates[1:], strict=False))
    if gap <= 10:
        return "weekly"
    if gap <= 45:
        return "monthly"
    return "termly" if gap <= 200 else "yearly"


def _next_date(schedule: str, last: date) -> date | None:
    if schedule == "weekly":
        return last + timedelta(days=7)
    if schedule == "monthly":
        return _add_month(last)
    return None


def _is_refund(t: Transaction) -> bool:
    return (t.provider_category or "").lower() in _REFUND_TYPES


def detect_income(transactions: list[Transaction]) -> list[IncomeSource]:
    groups: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
    for t in transactions:
        if t.amount <= 0 or _is_refund(t) or (t.provider_category or "").lower() in ("savings", "pot transfer"):
            continue
        text = _text(t)
        kind = next((k for k, rx in _RULES if rx.search(text)), "other")
        groups[(kind, _payer(t))].append(t)
    out: list[IncomeSource] = []
    for (kind, payer), txs in sorted(groups.items()):
        txs.sort(key=lambda t: t.date)
        if kind == "other" and len(txs) < 3:
            continue
        dates = [date.fromisoformat(t.date) for t in txs]
        schedule = _schedule(kind, dates)
        amount = round(sum(t.amount for t in txs) / len(txs), 2)
        final_kind: IncomeKind
        if kind == "job":
            per_month = {"weekly": amount * 52 / 12, "monthly": amount}.get(schedule, amount)
            final_kind = "salary" if per_month >= SALARY_MONTHLY_MIN else "part_time_job"
        else:
            final_kind = kind  # type: ignore[assignment]
        nxt = _next_date(schedule, dates[-1])
        out.append(IncomeSource(
            id=f"{final_kind}_{payer}"[:60], kind=final_kind, amount=min(amount, 1_000_000.0), schedule=schedule,
            next_date=nxt.isoformat() if nxt else None, dates=[d.isoformat() for d in dates][-60:],
        ))
    return out[:20]


def _bnpl_plans(payments: list[Transaction], as_of: date) -> tuple[float, date | None]:
    """Unpaid Pay in 3 instalments and the next due date."""
    chains: dict[tuple[str, float], list[list[date]]] = defaultdict(list)
    for t in sorted(payments, key=lambda t: t.date):
        key = (_slug(t.description), round(-t.amount, 2))
        d = date.fromisoformat(t.date)
        runs = chains[key]
        if runs and len(runs[-1]) < 3 and 25 <= (d - runs[-1][-1]).days <= 35:
            runs[-1].append(d)
        else:
            runs.append([d])
    owed, due = 0.0, None
    for (_, amount), runs in chains.items():
        for run in runs:
            if len(run) < 3 and (as_of - run[-1]).days <= 35:
                owed += (3 - len(run)) * amount
                nxt = run[-1] + timedelta(days=30)
                due = nxt if due is None or nxt < due else due
    return round(owed, 2), due


def detect_debts(transactions: list[Transaction], accounts: list[Account], balance_known: bool,
                 as_of: date) -> list[DebtItem]:
    out: list[DebtItem] = []
    od_rows = [t for t in transactions if t.amount < 0 and _OVERDRAFT.search(_text(t))]
    current = [a for a in accounts if a.kind == "current"]
    closing = sum(a.balance for a in current) if balance_known and current else None
    if od_rows or (closing is not None and closing < 0):
        rate = None
        for t in reversed(od_rows):
            m = _RATE.search(_text(t))
            if m:
                rate = min(float(m.group(1)), 100.0)
                break
        out.append(DebtItem(id="overdraft", kind="overdraft",
                            balance=round(max(0.0, -closing), 2) if closing is not None else 0.0, rate_pct=rate))
    bnpl = [t for t in transactions if t.amount < 0 and _BNPL.search(_text(t))]
    if bnpl:
        owed, due = _bnpl_plans(bnpl, as_of)
        last = max(date.fromisoformat(t.date) for t in bnpl)
        if owed > 0 or (as_of - last).days <= 35:
            text = " ".join(_text(t) for t in bnpl)
            provider = next((p for p in ("klarna", "clearpay", "paypal") if p in text), "bnpl")
            out.append(DebtItem(id=f"bnpl_{provider}", kind="bnpl", balance=owed, rate_pct=0.0,
                                due_date=due.isoformat() if due else None))
    return out


def detect_is_student(transactions: list[Transaction], income: list[IncomeSource]) -> bool | None:
    if any(s.kind in STUDENT_KINDS for s in income):
        return True
    if any(_STUDENT_MARKERS.search(_text(t)) for t in transactions):
        return True
    return None
