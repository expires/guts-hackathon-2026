"""Spending insights for the Money tab (Insights screen). Pure: no clock, callers pass `today`. No LLM.

Reuses the money engine: `by_category` / `monthly_totals` for spending (transfers, savings and income are not
spending), `categorise` for income, `fixed_day_subscriptions` for subscriptions (housing excluded, fixed billing day).
The window is adaptive, see `window.py`: with less history than requested, the complete months available are used.

Insight sentences are facts only: every number comes from the response fields next to them.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict

from lifeline_contracts.finance import Category, FinanceMeta, FinanceSnapshot, Transaction
from lifeline_contracts.insights import (
    CategorySeries,
    InsightCategory,
    InsightMerchant,
    InsightMonth,
    InsightSubscription,
    InsightSubscriptions,
    SpendingInsights,
    SpendingPatterns,
    UnusualPayment,
    WeekdaySpend,
)
from lifeline_engine.money import dates
from lifeline_engine.money.categorise import NOT_SPENDING, categorise, display_name, emoji, label, merchant_key
from lifeline_engine.money.habits import DISCRETIONARY, fixed_day_subscriptions
from lifeline_engine.money.spending import by_category, monthly_totals
from lifeline_engine.money.window import MIN_MONTHS, adaptive_months, window_note

UNUSUAL_FACTOR = 3  # more than 3x the category median
UNUSUAL_MIN_TXNS = 5
CHANGE_THRESHOLD = 10.0  # percent; smallest change worth a sentence
CHANGE_MIN_GBP = 20.0
TOP_MERCHANTS = 8
TOP_UNUSUAL = 8
MAX_INSIGHTS = 6
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
NOT_ENOUGH = "We need at least 2 full months of spending to show insights"


def gbp(x: float) -> str:
    return f"£{x:,.0f}" if abs(x) >= 100 else f"£{x:,.2f}"


def _spend_txs(txs: list[Transaction], months: set[str]) -> list[Transaction]:
    return [t for t in txs if t.date[:7] in months and categorise(t) not in NOT_SPENDING and t.amount < 0]


def _empty(meta: FinanceMeta, requested: int) -> SpendingInsights:
    return SpendingInsights(
        meta=meta, window_months=0, requested_months=requested, note=NOT_ENOUGH,
        total_income=0.0, total_spend=0.0, monthly=[], categories=[], category_months=[], category_by_month=[],
        top_merchants=[], subscriptions=InsightSubscriptions(monthly_total=0.0, annual_total=0.0, items=[]),
        unusual=[], patterns=SpendingPatterns(average_daily_spend=0.0, by_weekday=[]), insights=[],
    )


def spending_insights(snapshot: FinanceSnapshot, today: dates.date, months: int = 6) -> SpendingInsights:
    meta = FinanceMeta(
        data_status=snapshot.status, source=snapshot.source, as_of=snapshot.as_of,
        label="Sample data" if snapshot.status == "mock" else None,
    )
    txs = snapshot.transactions
    used = adaptive_months(txs, today, months)
    if len(used) < MIN_MONTHS:
        return _empty(meta, months)
    mset = set(used)
    start, end = used[0], used[-1]

    # monthly
    spend_by_month = monthly_totals(txs, used)
    income_by_month: dict[str, float] = defaultdict(float)
    for t in txs:
        if t.date[:7] in mset and t.amount > 0 and categorise(t) == "income":
            income_by_month[t.date[:7]] += t.amount
    monthly = [
        InsightMonth(
            month=m, income=round(income_by_month[m], 2), spend=spend_by_month[m],
            net=round(income_by_month[m] - spend_by_month[m], 2),
        )
        for m in used
    ]
    total_income = round(sum(x.income for x in monthly), 2)
    total_spend = round(sum(x.spend for x in monthly), 2)

    # categories, now and in the previous window of the same length (only when its history is complete)
    per_month = {m: by_category(txs, m) for m in used}
    cat_total: dict[Category, float] = defaultdict(float)
    for m in used:
        for c, (v, _) in per_month[m].items():
            cat_total[c] += v
    prior_months = [dates.prev_month(start, k) for k in range(len(used), 0, -1)]
    prior_ok = len(adaptive_months(txs, dates.month_bounds(prior_months[-1])[1], len(used))) == len(used)
    prior_total: dict[Category, float] = defaultdict(float)
    if prior_ok:
        for m in prior_months:
            for c, (v, _) in by_category(txs, m).items():
                prior_total[c] += v
    grand = sum(cat_total.values())
    ordered = sorted((c for c in cat_total if cat_total[c] > 0), key=lambda c: (-cat_total[c], c))
    categories = [
        InsightCategory(
            category=c, label=label(c), emoji=emoji(c), amount=round(cat_total[c], 2),
            share=round(cat_total[c] / grand, 4) if grand > 0 else 0.0,
            monthly_average=round(cat_total[c] / len(used), 2),
            change_pct=round((cat_total[c] - prior_total[c]) / prior_total[c] * 100, 1)
            if prior_ok and prior_total[c] > 0 else None,
        )
        for c in ordered
    ]
    series = [
        CategorySeries(
            category=c, label=label(c), emoji=emoji(c), values=[per_month[m].get(c, (0.0, 0))[0] for m in used]
        )
        for c in ordered
    ]

    out = _spend_txs(txs, mset)

    # merchants
    m_total: dict[str, float] = defaultdict(float)
    m_count: Counter[str] = Counter()
    m_name: dict[str, str] = {}
    m_cats: dict[str, Counter[Category]] = defaultdict(Counter)
    for t in sorted(out, key=lambda t: (t.date, t.id)):
        k = merchant_key(t)
        m_total[k] -= t.amount
        m_count[k] += 1
        m_name[k] = display_name(t)
        m_cats[k][categorise(t)] += 1
    top_merchants = []
    for k in sorted(m_total, key=lambda k: (-m_total[k], k))[:TOP_MERCHANTS]:
        cat = sorted(m_cats[k].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        top_merchants.append(
            InsightMerchant(
                merchant=m_name[k], category=cat, emoji=emoji(cat), amount=round(m_total[k], 2), count=m_count[k]
            )
        )

    # subscriptions
    subs = sorted(
        (
            InsightSubscription(
                merchant=r.name, emoji=emoji(r.category), monthly_cost=r.monthly_cost,
                annual_cost=round(r.monthly_cost * 12, 2),
            )
            for r in fixed_day_subscriptions([t for t in txs if t.date <= today.isoformat()], today)
        ),
        key=lambda s: (-s.monthly_cost, s.merchant),
    )
    subscriptions = InsightSubscriptions(
        monthly_total=round(sum(s.monthly_cost for s in subs), 2),
        annual_total=round(sum(s.annual_cost for s in subs), 2),
        items=subs,
    )

    # unusual payments
    by_cat_txs: dict[Category, list[Transaction]] = defaultdict(list)
    for t in out:
        by_cat_txs[categorise(t)].append(t)
    flagged: list[UnusualPayment] = []
    for c, items in by_cat_txs.items():
        if len(items) < UNUSUAL_MIN_TXNS:
            continue
        med = statistics.median(-t.amount for t in items)
        flagged += [
            UnusualPayment(
                id=t.id, date=t.date, merchant=display_name(t), category=c, emoji=emoji(c),
                amount=round(-t.amount, 2), typical=round(med, 2),
            )
            for t in items
            if -t.amount > UNUSUAL_FACTOR * med
        ]
    flagged.sort(key=lambda u: (-u.amount, u.id))
    unusual = flagged[:TOP_UNUSUAL]

    patterns = _patterns(out, used)
    insights = _sentences(
        monthly, categories, subscriptions, len(flagged), patterns, prior_ok, total_income, total_spend, len(used)
    )
    return SpendingInsights(
        meta=meta, window_months=len(used), requested_months=months, start_month=start, end_month=end,
        note=window_note(len(used), months), total_income=total_income, total_spend=total_spend, monthly=monthly,
        categories=categories, category_months=used, category_by_month=series, top_merchants=top_merchants,
        subscriptions=subscriptions, unusual=unusual, patterns=patterns, insights=insights,
    )


def _patterns(out: list[Transaction], used: list[str]) -> SpendingPatterns:
    by_day = [0.0] * 7
    per_date: dict[str, float] = defaultdict(float)
    weekend = weekday = 0.0
    for t in out:
        wd = dates.parse(t.date).weekday()
        by_day[wd] += -t.amount
        per_date[t.date] += -t.amount
        if categorise(t) in DISCRETIONARY:
            if wd >= 5:
                weekend += -t.amount
            else:
                weekday += -t.amount
    days = (dates.month_bounds(used[-1])[1] - dates.month_bounds(used[0])[0]).days + 1
    total = sum(by_day)
    disc = weekend + weekday
    biggest = max(per_date, key=lambda d: (per_date[d], d)) if per_date else None
    return SpendingPatterns(
        weekend_share=round(weekend / disc, 4) if disc > 0 else None,
        weekday_share=round(weekday / disc, 4) if disc > 0 else None,
        average_daily_spend=round(total / days, 2),
        biggest_weekday=WEEKDAYS[by_day.index(max(by_day))] if total > 0 else None,
        biggest_day=biggest,
        biggest_day_amount=round(per_date[biggest], 2) if biggest else None,
        by_weekday=[WeekdaySpend(weekday=WEEKDAYS[i], amount=round(v, 2)) for i, v in enumerate(by_day)],
    )


def _sentences(
    monthly: list[InsightMonth], cats: list[InsightCategory], subs: InsightSubscriptions, n_unusual: int,
    p: SpendingPatterns, has_prior: bool, income: float, spend: float, n: int,
) -> list[str]:
    out: list[str] = []
    if cats:
        top = cats[0]
        out.append(
            f"{top.label} is your biggest spend: {gbp(top.amount)}, "
            f"{top.share * 100:.0f}% of the {gbp(spend)} you spent."
        )
    over = sum(1 for m in monthly if m.net < 0)
    if over:
        out.append(f"You spent more than you earned in {over} of the last {n} months.")
    elif income > 0:
        out.append(f"You earned more than you spent in all of the last {n} months, {gbp(income - spend)} in total.")
    if has_prior:
        moved = [c for c in cats if c.change_pct is not None and abs(c.change_pct) >= CHANGE_THRESHOLD]
        if moved:
            c = max(moved, key=lambda c: (abs(c.change_pct or 0.0), c.category))
            pct = abs(c.change_pct or 0.0)
            word = "up" if (c.change_pct or 0.0) > 0 else "down"
            out.append(f"{c.label} is {word} {pct:.0f}% on the {n} months before.")
    if subs.items:
        k = len(subs.items)
        out.append(
            f"Your {k} subscription{'s' if k != 1 else ''} cost {gbp(subs.monthly_total)} a month, "
            f"{gbp(subs.annual_total)} a year."
        )
    if p.weekend_share is not None and p.weekend_share > 0:
        out.append(f"{p.weekend_share * 100:.0f}% of your treat spending happens at weekends.")
    if n_unusual:
        out.append(
            f"{n_unusual} payment{'s were' if n_unusual != 1 else ' was'} more than {UNUSUAL_FACTOR} times "
            "the usual for its type."
        )
    if p.average_daily_spend > 0:
        out.append(f"You spend {gbp(p.average_daily_spend)} a day on average.")
    return out[:MAX_INSIGHTS]

