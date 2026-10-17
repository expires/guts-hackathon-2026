"""Spending by category, budgets and savings goals (ADR 0016). Pure.

Spending in a category = minus the sum of that category's transaction amounts in the month, so
refunds reduce it. Transfers, savings and income are not spending. Card repayments are transfers;
the purchases on the card account are the spending.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence

from lifeline_contracts.finance import (
    Budget,
    Category,
    CategorySpend,
    CreateGoalRequest,
    SavingsGoal,
    Transaction,
)
from lifeline_engine.money import dates
from lifeline_engine.money.categorise import NOT_SPENDING, categorise, emoji, label

NEAR_SHARE = 0.8


def by_category(txs: Iterable[Transaction], month: str) -> dict[Category, tuple[float, int]]:
    """(net spend, transaction count) per spending category in `month`. Negative nets clamp to 0."""
    total: dict[Category, float] = defaultdict(float)
    count: dict[Category, int] = defaultdict(int)
    for t in txs:
        if t.date[:7] != month:
            continue
        c = categorise(t)
        if c in NOT_SPENDING:
            continue
        total[c] -= t.amount
        count[c] += 1
    return {c: (max(0.0, round(total[c], 2)), count[c]) for c in total}


def monthly_totals(txs: Iterable[Transaction], months: Sequence[str]) -> dict[str, float]:
    items = list(txs)
    return {m: round(sum(v for v, _ in by_category(items, m).values()), 2) for m in months}


def spending(txs: Iterable[Transaction], month: str) -> list[CategorySpend]:
    """Categories for `month`, largest first. change_pct compares with the month before."""
    items = list(txs)
    cur = by_category(items, month)
    prev = by_category(items, dates.prev_month(month))
    total = sum(v for v, _ in cur.values())
    out: list[CategorySpend] = []
    for c, (amount, n) in cur.items():
        if amount <= 0 and n == 0:
            continue
        before = prev.get(c, (0.0, 0))[0]
        out.append(
            CategorySpend(
                category=c,
                label=label(c),
                emoji=emoji(c),
                amount=amount,
                share=round(amount / total, 4) if total > 0 else 0.0,
                transactions=n,
                change_pct=round((amount - before) / before * 100, 1) if before > 0 else None,
            )
        )
    out.sort(key=lambda x: (-x.amount, x.category))
    return out


def budgets(txs: Iterable[Transaction], month: str, limits: Mapping[Category, float]) -> list[Budget]:
    """Progress per budget limit. Status: over when spent > limit, near at 80% or more, else ok.
    A zero limit with any spend counts as over with progress 1."""
    cur = by_category(txs, month)
    out: list[Budget] = []
    for c, limit in limits.items():
        spent = cur.get(c, (0.0, 0))[0]
        if limit > 0:
            progress = spent / limit
        else:
            progress = 1.0 if spent > 0 else 0.0
        over = spent > limit
        status = "over" if over else "near" if progress >= NEAR_SHARE else "ok"
        out.append(
            Budget(
                category=c,
                label=label(c),
                emoji=emoji(c),
                limit=round(limit, 2),
                spent=spent,
                progress=round(progress, 4),
                status=status,
            )
        )
    out.sort(key=lambda b: (-b.progress, b.category))
    return out


def months_between(start: dates.date, end: dates.date) -> int:
    """Whole months from `start` to `end`, counting a part month as a full one. 0 when end <= start."""
    if end <= start:
        return 0
    n = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day > start.day:
        n += 1
    return max(1, n)


def goal_progress(goal: SavingsGoal, today: dates.date) -> SavingsGoal:
    """Recompute progress and monthly_needed. monthly_needed = what is left / months to the target date
    (a part month counts as one). No target date gives None. A target date in the past needs all that is left now."""
    left = max(0.0, goal.target - goal.saved)
    needed: float | None = None
    if goal.target_date is not None:
        months = months_between(today, dates.parse(goal.target_date))
        needed = round(left / months, 2) if months > 0 else round(left, 2)
    return goal.model_copy(update={"progress": round(goal.saved / goal.target, 4), "monthly_needed": needed})


def goals_progress(goals: Iterable[SavingsGoal], today: dates.date) -> list[SavingsGoal]:
    return [goal_progress(g, today) for g in goals]


def goal_from_request(goal_id: str, req: CreateGoalRequest, today: dates.date) -> SavingsGoal:
    goal = SavingsGoal(
        id=goal_id,
        name=req.name,
        emoji=req.emoji,
        target=req.target,
        saved=req.saved,
        progress=0.0,
        target_date=req.target_date,
    )
    return goal_progress(goal, today)
