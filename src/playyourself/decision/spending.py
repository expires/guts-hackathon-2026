"""Spending analysis: pure function over a snapshot. Pence ints, LOCAL ONLY, never shared.

Window convention (mirrors habits.py): the last ``months`` complete calendar months ending at or
before ``as_of``. If ``as_of`` is the last day of its month that month is included; otherwise the
current (incomplete) month is excluded. Transfers are excluded everywhere. Insights are
deterministic, factual strings only.
"""

from __future__ import annotations

import calendar
import statistics
from collections import Counter, defaultdict
from datetime import date

from pydantic import BaseModel

from playyourself.decision.habits import detect_subscriptions
from playyourself.domain.models import DISCRETIONARY_CATEGORIES, Snapshot, Transaction

UNUSUAL_FACTOR = 3  # outflow > 3x the category median
UNUSUAL_MIN_TXNS = 5
CHANGE_THRESHOLD = 0.10  # smallest change worth an insight
TOP_N = 10
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class SpendingWindow(BaseModel):
    months: int
    start: date
    end: date


class MonthTotals(BaseModel):
    month: str  # YYYY-MM
    income_pence: int
    spend_pence: int
    net_pence: int


class CategorySpend(BaseModel):
    category: str
    total_pence: int
    share: float
    monthly_avg_pence: int
    change_vs_prev_period: float | None  # ratio, 0.34 = +34%; null with no prior spend


class CategoryMatrix(BaseModel):
    months: list[str]
    categories: list[str]
    values: dict[str, list[int]]  # category -> pence per month (aligned with months)


class MerchantSpend(BaseModel):
    merchant: str
    total_pence: int
    count: int
    category: str


class SubscriptionItem(BaseModel):
    merchant: str
    monthly_pence: int
    first_seen: date
    months_active: int


class Subscriptions(BaseModel):
    items: list[SubscriptionItem]
    total_monthly_pence: int
    annualised_pence: int
    by_month: list[int]  # pence per window month across detected subscriptions


class UnusualTransaction(BaseModel):
    id: str
    date: date
    merchant: str
    category: str
    amount_pence: int
    category_median_pence: int


class Patterns(BaseModel):
    weekend_share_of_discretionary: float | None
    weekday_share_of_discretionary: float | None
    average_daily_spend_pence: int
    biggest_spending_weekday: str | None
    spend_by_weekday_pence: list[int]  # Monday first


class SpendingAnalysis(BaseModel):
    """Local UI only: contains pence amounts. Never share this payload."""

    window: SpendingWindow
    monthly: list[MonthTotals]
    by_category: list[CategorySpend]
    category_by_month: CategoryMatrix
    top_merchants: list[MerchantSpend]
    subscriptions: Subscriptions
    unusual: list[UnusualTransaction]
    patterns: Patterns
    insights: list[str]


def _midx(d: date) -> int:
    return d.year * 12 + d.month - 1


def _month_end(idx: int) -> date:
    y, m = divmod(idx, 12)
    return date(y, m + 1, calendar.monthrange(y, m + 1)[1])


def _key(idx: int) -> str:
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def gbp(pence: int) -> str:
    sign = "-" if pence < 0 else ""
    return f"{sign}£{abs(pence) / 100:,.2f}"


def _label(category: str) -> str:
    text = category.replace("_", " ")
    return text[:1].upper() + text[1:]


def _outflow(t: Transaction) -> int:
    return -t.amount_pence


def analyse_spending(
    snapshot: Snapshot, months: int = 6, as_of: date | None = None
) -> SpendingAnalysis:
    txs = [t for t in snapshot.transactions if not t.is_transfer]
    if as_of is None:
        all_dates = [t.ts.date() for t in snapshot.transactions]
        as_of = max(all_dates) if all_dates else snapshot.as_of.date()
    end_idx = _midx(as_of)
    if as_of != _month_end(end_idx):
        end_idx -= 1
    start_idx = end_idx - months + 1
    prev_start = start_idx - months
    window = SpendingWindow(
        months=months, start=date(start_idx // 12, start_idx % 12 + 1, 1), end=_month_end(end_idx)
    )

    cur = [t for t in txs if start_idx <= _midx(t.ts.date()) <= end_idx]
    prev = [t for t in txs if prev_start <= _midx(t.ts.date()) < start_idx]
    idxs = list(range(start_idx, end_idx + 1))
    out_cur = [t for t in cur if t.amount_pence < 0]

    # monthly
    inc = defaultdict(int)
    spend = defaultdict(int)
    for t in cur:
        (inc if t.amount_pence > 0 else spend)[_midx(t.ts.date())] += abs(t.amount_pence)
    monthly = [
        MonthTotals(
            month=_key(i), income_pence=inc[i], spend_pence=spend[i], net_pence=inc[i] - spend[i]
        )
        for i in idxs
    ]

    # categories
    cat_total: dict[str, int] = defaultdict(int)
    cat_month: dict[str, list[int]] = defaultdict(lambda: [0] * months)
    for t in out_cur:
        cat_total[t.category] += _outflow(t)
        cat_month[t.category][_midx(t.ts.date()) - start_idx] += _outflow(t)
    prev_total: dict[str, int] = defaultdict(int)
    for t in prev:
        if t.amount_pence < 0:
            prev_total[t.category] += _outflow(t)
    grand = sum(cat_total.values())
    ordered = sorted(cat_total, key=lambda c: (-cat_total[c], c))
    by_category = [
        CategorySpend(
            category=c,
            total_pence=cat_total[c],
            share=round(cat_total[c] / grand, 4) if grand else 0.0,
            monthly_avg_pence=round(cat_total[c] / months),
            change_vs_prev_period=(
                round((cat_total[c] - prev_total[c]) / prev_total[c], 4) if prev_total[c] else None
            ),
        )
        for c in ordered
    ]
    matrix = CategoryMatrix(
        months=[_key(i) for i in idxs],
        categories=ordered,
        values={c: cat_month[c] for c in ordered},
    )

    # merchants
    m_total: dict[str, int] = defaultdict(int)
    m_count: Counter[str] = Counter()
    m_cats: dict[str, Counter[str]] = defaultdict(Counter)
    for t in out_cur:
        m_total[t.merchant] += _outflow(t)
        m_count[t.merchant] += 1
        m_cats[t.merchant][t.category] += 1
    top_merchants = [
        MerchantSpend(
            merchant=m,
            total_pence=m_total[m],
            count=m_count[m],
            category=sorted(m_cats[m].items(), key=lambda kv: (-kv[1], kv[0]))[0][0],
        )
        for m in sorted(m_total, key=lambda m: (-m_total[m], m))[:TOP_N]
    ]

    subscriptions = _subscriptions(cur, idxs, start_idx)

    # unusual
    by_cat_txs: dict[str, list[Transaction]] = defaultdict(list)
    for t in out_cur:
        by_cat_txs[t.category].append(t)
    flagged: list[UnusualTransaction] = []
    for c, ts in by_cat_txs.items():
        if len(ts) < UNUSUAL_MIN_TXNS:
            continue
        med = statistics.median(_outflow(t) for t in ts)
        flagged += [
            UnusualTransaction(
                id=t.id,
                date=t.ts.date(),
                merchant=t.merchant,
                category=c,
                amount_pence=_outflow(t),
                category_median_pence=round(med),
            )
            for t in ts
            if _outflow(t) > UNUSUAL_FACTOR * med
        ]
    flagged.sort(key=lambda u: (-u.amount_pence, u.id))
    n_unusual = len(flagged)
    unusual = flagged[:TOP_N]

    patterns = _patterns(out_cur, start_idx, end_idx)

    analysis = SpendingAnalysis(
        window=window,
        monthly=monthly,
        by_category=by_category,
        category_by_month=matrix,
        top_merchants=top_merchants,
        subscriptions=subscriptions,
        unusual=unusual,
        patterns=patterns,
        insights=[],
    )
    analysis.insights = _insights(analysis, n_unusual, bool(prev))
    return analysis


def _subscriptions(cur: list[Transaction], idxs: list[int], start_idx: int) -> Subscriptions:
    names = detect_subscriptions(cur)
    items: list[SubscriptionItem] = []
    by_month = [0] * len(idxs)
    for name in names:
        ts = sorted(
            (t for t in cur if t.merchant == name and t.amount_pence < 0), key=lambda t: t.ts
        )
        items.append(
            SubscriptionItem(
                merchant=name,
                monthly_pence=round(statistics.median(_outflow(t) for t in ts)),
                first_seen=ts[0].ts.date(),
                months_active=len({_midx(t.ts.date()) for t in ts}),
            )
        )
        for t in ts:
            by_month[_midx(t.ts.date()) - start_idx] += _outflow(t)
    items.sort(key=lambda s: (-s.monthly_pence, s.merchant))
    total = sum(s.monthly_pence for s in items)
    return Subscriptions(
        items=items, total_monthly_pence=total, annualised_pence=total * 12, by_month=by_month
    )


def _patterns(out_cur: list[Transaction], start_idx: int, end_idx: int) -> Patterns:
    by_day = [0] * 7
    weekend = weekday = 0
    for t in out_cur:
        wd = t.ts.weekday()
        by_day[wd] += _outflow(t)
        if t.category in DISCRETIONARY_CATEGORIES:
            if wd >= 5:
                weekend += _outflow(t)
            else:
                weekday += _outflow(t)
    days = (_month_end(end_idx) - date(start_idx // 12, start_idx % 12 + 1, 1)).days + 1
    disc = weekend + weekday
    total = sum(by_day)
    return Patterns(
        weekend_share_of_discretionary=round(weekend / disc, 4) if disc else None,
        weekday_share_of_discretionary=round(weekday / disc, 4) if disc else None,
        average_daily_spend_pence=round(total / days) if days else 0,
        biggest_spending_weekday=WEEKDAYS[by_day.index(max(by_day))] if total else None,
        spend_by_weekday_pence=by_day,
    )


def _insights(a: SpendingAnalysis, n_unusual: int, has_prior: bool) -> list[str]:
    out: list[str] = []
    n = a.window.months
    if a.by_category:
        top = a.by_category[0]
        out.append(
            f"{_label(top.category)} is the largest category at {top.share * 100:.0f}% of spending"
        )
    changed = [c for c in a.by_category if c.change_vs_prev_period is not None]
    if has_prior and changed:
        up = max(changed, key=lambda c: (c.change_vs_prev_period, c.category))
        if up.change_vs_prev_period >= CHANGE_THRESHOLD:
            out.append(
                f"{_label(up.category)} is up {up.change_vs_prev_period * 100:.0f}% "
                f"vs the previous {n} months"
            )
        down = min(changed, key=lambda c: (c.change_vs_prev_period, c.category))
        if down.change_vs_prev_period <= -CHANGE_THRESHOLD:
            out.append(
                f"{_label(down.category)} is down {abs(down.change_vs_prev_period) * 100:.0f}% "
                f"vs the previous {n} months"
            )
    subs = a.subscriptions
    if subs.items:
        out.append(
            f"Subscriptions cost {gbp(subs.total_monthly_pence)}/month "
            f"({gbp(subs.annualised_pence)}/year) across {len(subs.items)} services"
        )
    if n_unusual:
        noun = "transaction" if n_unusual == 1 else "transactions"
        out.append(f"{n_unusual} unusual {noun} this period")
    p = a.patterns
    if p.weekend_share_of_discretionary is not None:
        out.append(
            f"{p.weekend_share_of_discretionary * 100:.0f}% of discretionary spending "
            "is on weekends"
        )
    if p.biggest_spending_weekday:
        out.append(f"{p.biggest_spending_weekday} is the biggest spending day of the week")
    out.append(f"Average daily spend is {gbp(p.average_daily_spend_pence)}")
    over = sum(1 for m in a.monthly if m.net_pence < 0)
    if over:
        out.append(f"Spending exceeded income in {over} of {n} months")
    elif any(m.income_pence for m in a.monthly):
        out.append(f"Income exceeded spending in all {n} months")
    return out
