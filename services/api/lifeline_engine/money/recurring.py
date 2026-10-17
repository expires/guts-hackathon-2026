"""Recurring payments: subscriptions, bills and salary (ADR 0016). Pure, no LLM.

A payee is recurring when:
- it has at least 3 charges (weekly or monthly) or 2 charges (quarterly or yearly);
- every gap between charges fits one cadence: weekly 5-9 days, monthly 25-35, quarterly 80-100,
  yearly 345-385;
- amounts are stable. Subscriptions: each charge is within 10% of the one before, except price
  rises (a step up of at most 50%). Bills (energy, water, council tax) can vary more: each charge
  is within 50% of the median charge.
- it is still active: the last charge is no more than 1.5 cadence steps before `today`.

Price rise: the latest charge is above the last different amount before it. `since` is the
first charge at the new amount.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Literal

from lifeline_contracts.finance import Bill, Cadence, Category, PriceRise, Subscription, Transaction
from lifeline_engine.money import dates
from lifeline_engine.money.categorise import (
    categorise,
    display_name,
    emoji,
    is_card_or_loan_payment,
    merchant_key,
)

CADENCE_GAPS: dict[Cadence, tuple[int, int]] = {
    "weekly": (5, 9),
    "monthly": (25, 35),
    "quarterly": (80, 100),
    "yearly": (345, 385),
}
CADENCE_DAYS: dict[Cadence, int] = {"weekly": 7, "monthly": 30, "quarterly": 91, "yearly": 365}
MONTHLY_FACTOR: dict[Cadence, float] = {"weekly": 52 / 12, "monthly": 1.0, "quarterly": 1 / 3, "yearly": 1 / 12}
MIN_CHARGES: dict[Cadence, int] = {"weekly": 3, "monthly": 3, "quarterly": 2, "yearly": 2}

SUBSCRIPTION_STEP = 0.10  # amount within 10% of the previous charge
PRICE_RISE_MAX = 0.50  # a single step up of at most 50% counts as a price rise
BILL_SPREAD = 0.50  # bills: each charge within 50% of the median
ACTIVE_STEPS = 1.5
DUE_SOON_DAYS = 3
BILL_WINDOW_DAYS = 30
OVERDUE_GRACE_DAYS = 5

BillKind = Literal["bill", "subscription", "rent", "mortgage", "loan", "card"]

BILL_CATEGORIES: frozenset[Category] = frozenset({"bills", "housing", "subscriptions"})


@dataclass(frozen=True)
class Recurring:
    key: str
    name: str
    category: Category
    cadence: Cadence
    charges: tuple[Transaction, ...]  # oldest first
    kind: str  # bill kind: bill, subscription, rent, mortgage, loan, card

    @property
    def amount(self) -> float:
        return abs(self.charges[-1].amount)

    @property
    def last_date(self) -> dates.date:
        return dates.parse(self.charges[-1].date)

    @property
    def monthly_cost(self) -> float:
        return round(self.amount * MONTHLY_FACTOR[self.cadence], 2)

    def next_due(self, after: dates.date) -> dates.date:
        """First due date on or after `after`, or the first missed one when it is within the grace period."""
        d = self._skip_break(step(self.last_date, self.cadence))
        while (after - d).days > OVERDUE_GRACE_DAYS:
            d = self._skip_break(step(d, self.cadence))
        return d

    def _skip_break(self, d: dates.date) -> dates.date:
        """Ten-payment council tax: no payment in February or March."""
        text = f"{self.charges[-1].description} {self.charges[-1].merchant or ''}".lower()
        if self.cadence == "monthly" and d.month in (2, 3) and any(w in text for w in TEN_PAYMENT_WORDS):
            return dates.add_months(d, 4 - d.month)
        return d


def step(d: dates.date, cadence: Cadence, n: int = 1) -> dates.date:
    if cadence == "weekly":
        return dates.add_days(d, 7 * n)
    months = {"monthly": 1, "quarterly": 3, "yearly": 12}[cadence]
    return dates.add_months(d, months * n)


def classify_cadence(gaps: Sequence[int]) -> Cadence | None:
    """The cadence that every gap fits, else None."""
    if not gaps:
        return None
    for cadence, (lo, hi) in CADENCE_GAPS.items():
        if all(lo <= g <= hi for g in gaps):
            return cadence
    return None


TEN_PAYMENT_WORDS = ("council tax", "ctax", "council")
TEN_PAYMENT_BREAK = (55, 100)  # the February-March break: one or two months skipped


def is_ten_payment_schedule(items: Sequence[Transaction], gaps: Sequence[int]) -> bool:
    """Council tax is often paid in 10 monthly instalments (April to January) with a February-March break.
    Accept monthly gaps plus at most one break of 55-100 days per 10 payments."""
    text = f"{items[-1].description} {items[-1].merchant or ''}".lower()
    if not any(w in text for w in TEN_PAYMENT_WORDS):
        return False
    lo, hi = CADENCE_GAPS["monthly"]
    breaks = [g for g in gaps if not lo <= g <= hi]
    allowed = 1 + len(items) // 10
    return all(TEN_PAYMENT_BREAK[0] <= g <= TEN_PAYMENT_BREAK[1] for g in breaks) and len(breaks) <= allowed


def stable_subscription_amounts(amounts: Sequence[float]) -> bool:
    """Each charge within 10% of the one before, or a step up of at most 50% (a price rise)."""
    for prev, cur in zip(amounts, amounts[1:], strict=False):
        if prev <= 0:
            return False
        change = (cur - prev) / prev
        if abs(change) <= SUBSCRIPTION_STEP:
            continue
        if 0 < change <= PRICE_RISE_MAX:
            continue
        return False
    return True


def stable_bill_amounts(amounts: Sequence[float]) -> bool:
    mid = median(amounts)
    return mid > 0 and all(abs(a - mid) <= BILL_SPREAD * mid for a in amounts)


def price_rise(charges: Sequence[Transaction]) -> PriceRise | None:
    """Latest charge above the last different amount before it."""
    amounts = [round(abs(t.amount), 2) for t in charges]
    if len(amounts) < 2:
        return None
    last = amounts[-1]
    i = len(amounts) - 1
    while i > 0 and amounts[i - 1] == last:
        i -= 1
    if i == 0:
        return None
    before = amounts[i - 1]
    if last <= before:
        return None
    return PriceRise(from_amount=before, to_amount=last, since=charges[i].date)


def bill_kind(category: Category, charges: Sequence[Transaction]) -> str:
    text = " ".join(f"{t.description} {t.merchant or ''}" for t in charges[-1:]).lower()
    if "mortgage" in text:
        return "mortgage"
    if is_card_or_loan_payment(charges[-1]):
        return "loan" if "loan" in text else "card"
    if category == "housing":
        return "rent"
    if category == "subscriptions":
        return "subscription"
    return "bill"


def detect_recurring(txs: Iterable[Transaction], today: dates.date | None = None) -> list[Recurring]:
    """Every recurring outflow. `today` defaults to the latest transaction date."""
    groups: dict[str, list[Transaction]] = defaultdict(list)
    all_txs = list(txs)
    for t in all_txs:
        if t.amount < 0:
            groups[merchant_key(t)].append(t)
    if today is None:
        today = max((dates.parse(t.date) for t in all_txs), default=dates.date(2000, 1, 1))
    out: list[Recurring] = []
    for key, items in groups.items():
        items.sort(key=lambda t: (t.date, t.id))
        found = _recurring_from(key, items, today)
        if found is not None:
            out.append(found)
    out.sort(key=lambda r: (-r.monthly_cost, r.key))
    return out


def _recurring_from(key: str, items: list[Transaction], today: dates.date) -> Recurring | None:
    ds = [dates.parse(t.date) for t in items]
    gaps = [(b - a).days for a, b in zip(ds, ds[1:], strict=False)]
    cadence = classify_cadence(gaps)
    if cadence is None and is_ten_payment_schedule(items, gaps):
        cadence = "monthly"
    if cadence is None or len(items) < MIN_CHARGES[cadence]:
        return None
    if (today - ds[-1]).days > ACTIVE_STEPS * CADENCE_DAYS[cadence]:
        return None
    category = categorise(items[-1])
    amounts = [abs(t.amount) for t in items]
    kind = bill_kind(category, items)
    if category == "subscriptions":
        if not stable_subscription_amounts(amounts):
            return None
    elif category in BILL_CATEGORIES or kind in ("card", "loan"):
        if not stable_bill_amounts(amounts):
            return None
    else:
        return None  # regular shopping is not a bill
    return Recurring(
        key=key, name=display_name(items[-1]), category=category, cadence=cadence, charges=tuple(items), kind=kind
    )


def _slug(text: str) -> str:
    return "-".join("".join(c if c.isalnum() else " " for c in text.lower()).split())[:48] or "item"


def detect_subscriptions(txs: Iterable[Transaction], today: dates.date | None = None) -> list[Subscription]:
    all_txs = list(txs)
    if today is None:
        today = max((dates.parse(t.date) for t in all_txs), default=dates.date(2000, 1, 1))
    out: list[Subscription] = []
    for r in detect_recurring(all_txs, today):
        if r.category != "subscriptions":
            continue
        out.append(
            Subscription(
                id=f"sub_{_slug(r.key)}",
                merchant=r.name,
                emoji=emoji(r.category),
                category=r.category,
                amount=round(r.amount, 2),
                cadence=r.cadence,
                monthly_cost=r.monthly_cost,
                next_payment=dates.iso(r.next_due(today)),
                price_rise=price_rise(r.charges),
            )
        )
    return out


_BILL_KINDS: dict[str, BillKind] = {
    "bill": "bill",
    "subscription": "subscription",
    "rent": "rent",
    "mortgage": "mortgage",
    "loan": "loan",
    "card": "card",
}
_KIND_EMOJI = {"mortgage": "🏠", "rent": "🏠", "card": "💳", "loan": "🏦", "subscription": "🔁"}


def upcoming_bills(txs: Iterable[Transaction], today: dates.date) -> list[Bill]:
    """Recurring outflows due in the next 30 days, plus missed ones within the grace period, by due date."""
    out: list[Bill] = []
    for r in detect_recurring(txs, today):
        due = r.next_due(today)
        days = (due - today).days
        if days > BILL_WINDOW_DAYS:
            continue
        status = "overdue" if days < 0 else "due_soon" if days <= DUE_SOON_DAYS else "upcoming"
        kind = _BILL_KINDS.get(r.kind, "bill")
        out.append(
            Bill(
                id=f"bill_{_slug(r.key)}",
                name=r.name,
                emoji=_KIND_EMOJI.get(kind, emoji(r.category)),
                kind=kind,
                amount=round(r.amount, 2),
                due_date=dates.iso(due),
                status=status,
            )
        )
    out.sort(key=lambda b: (b.due_date, b.name))
    return out


# ---------- salary ----------


@dataclass(frozen=True)
class Income:
    monthly_net: float
    payday_dates: tuple[dates.date, ...]


def detect_salary(txs: Iterable[Transaction]) -> Income | None:
    """Regular salary credits (category income, salary words, monthly). None when not found."""
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for t in txs:
        if t.amount > 0 and categorise(t) == "income" and _is_salary(t):
            groups[merchant_key(t)].append(t)
    best: Income | None = None
    for items in groups.values():
        items.sort(key=lambda t: t.date)
        ds = [dates.parse(t.date) for t in items]
        gaps = [(b - a).days for a, b in zip(ds, ds[1:], strict=False)]
        if len(items) < 2 or not all(20 <= g <= 40 for g in gaps):
            continue
        recent = items[-12:]
        monthly = sum(t.amount for t in recent) / len(recent)
        if best is None or monthly > best.monthly_net:
            best = Income(monthly_net=round(monthly, 2), payday_dates=tuple(ds))
    return best


def _is_salary(t: Transaction) -> bool:
    text = f"{t.description} {t.merchant or ''}".lower()
    return any(w in text for w in ("salary", "payroll", "wages", "pay from"))
