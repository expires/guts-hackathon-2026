"""All spending month switch and the Category screen (PENNY_V3_BUILD.md B3 points 5 and 6, ADR 0072). Pure.

- Statement months: every month from the first transaction to `as_of`, oldest first.
- Category detail: the month total (as in spending.by_category), the usual monthly amount (the average of the full
  statement months before this month; a month is full when the statement covers its first and last day), bars by
  week (days 1-7, 8-14, 15-21, 22-28, 29-end; the current month stops at `as_of`) and every transaction of the
  category in the month, newest first.
"""

from __future__ import annotations

from datetime import timedelta

from lifeline_contracts.finance import Category, FinanceSnapshot, Transaction
from lifeline_contracts.forecast import CategoryDetail, CategoryWeek
from lifeline_engine.money import dates
from lifeline_engine.money.categorise import categorise, label
from lifeline_engine.money.spending import by_category


def statement_months(snapshot: FinanceSnapshot) -> list[str]:
    """Every month the statement covers, oldest first. At least the `as_of` month."""
    last = dates.parse(snapshot.as_of)
    first = min((dates.parse(t.date) for t in snapshot.transactions), default=last)
    first = min(first, last)
    out: list[str] = []
    m = dates.month_of(first)
    while m <= dates.month_of(last):
        out.append(m)
        m = dates.month_of(dates.add_months(dates.month_bounds(m)[0], 1))
    return out


def full_months_before(snapshot: FinanceSnapshot, month: str) -> list[str]:
    """Statement months before `month` that the statement covers from the first to the last day."""
    if not snapshot.transactions:
        return []
    first = min(dates.parse(t.date) for t in snapshot.transactions)
    last = dates.parse(snapshot.as_of)
    out = []
    for m in statement_months(snapshot):
        start, end = dates.month_bounds(m)
        if m < month and first <= start and end <= last:
            out.append(m)
    return out


def _amount(txs: list[Transaction], category: Category, month: str) -> float:
    return by_category(txs, month).get(category, (0.0, 0))[0]


def category_detail(snapshot: FinanceSnapshot, category: Category, month: str | None = None) -> CategoryDetail:
    from lifeline_engine.money import finance_meta  # the package imports this module

    as_of = dates.parse(snapshot.as_of)
    m = month or dates.month_of(as_of)
    txs = list(snapshot.transactions)
    before = full_months_before(snapshot, m)
    usual = round(sum(_amount(txs, category, b) for b in before) / len(before), 2) if before else 0.0
    mine = [t for t in txs if t.date[:7] == m and categorise(t) == category]
    start, end = dates.month_bounds(m)
    if start <= as_of < end:
        end = as_of
    weeks: list[CategoryWeek] = []
    d = start
    while d <= end:
        w_end = min(d + timedelta(days=6), end)
        spent = -sum(t.amount for t in mine if d <= dates.parse(t.date) <= w_end)
        weeks.append(CategoryWeek(start=dates.iso(d), end=dates.iso(w_end), amount=max(0.0, round(spent, 2))))
        d = w_end + timedelta(days=1)
    return CategoryDetail(
        meta=finance_meta(snapshot),
        category=category,
        label=label(category),
        month=m,
        total=_amount(txs, category, m),
        usual_monthly=usual,
        weeks=weeks,
        transactions=sorted(mine, key=lambda t: (t.date, t.id), reverse=True),
    )
