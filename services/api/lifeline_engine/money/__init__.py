"""Money tab insights (ADR 0016). Pure code, no LLM, no clock: callers pass `today`.

Item functions work on transaction lists. Response builders take a FinanceSnapshot and return the
contract models from lifeline_contracts.finance, with `meta` filled from the snapshot.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from lifeline_contracts.finance import (
    BillsResponse,
    BudgetsResponse,
    Category,
    FinanceMeta,
    FinanceOverview,
    FinanceProfile,
    FinanceSnapshot,
    GoalsResponse,
    SavingsGoal,
    SpendingResponse,
    SubscriptionsResponse,
)
from lifeline_engine.money import dates
from lifeline_engine.money.categorise import CATEGORY_INFO, categorise
from lifeline_engine.money.profile import (
    ProfileHints,
    balance,
    balance_history,
    net_worth,
    net_worth_history,
    personal_facts,
    profile,
)
from lifeline_engine.money.recurring import detect_recurring, detect_salary, detect_subscriptions, upcoming_bills
from lifeline_engine.money.spending import budgets, goal_from_request, goals_progress, spending

SAMPLE_LABEL = "Sample data"

__all__ = [
    "CATEGORY_INFO",
    "ProfileHints",
    "bills_response",
    "budgets",
    "budgets_response",
    "categorise",
    "detect_recurring",
    "detect_salary",
    "detect_subscriptions",
    "finance_meta",
    "finance_profile",
    "goal_from_request",
    "goals_progress",
    "goals_response",
    "overview",
    "personal_facts",
    "profile",
    "spending",
    "spending_response",
    "subscriptions_response",
    "upcoming_bills",
]


def finance_meta(snapshot: FinanceSnapshot) -> FinanceMeta:
    return FinanceMeta(
        data_status=snapshot.status,
        source=snapshot.source,
        as_of=snapshot.as_of,
        label=SAMPLE_LABEL if snapshot.status == "mock" else None,
    )


def _today(snapshot: FinanceSnapshot, today: dates.date | None) -> dates.date:
    return today if today is not None else dates.parse(snapshot.as_of)


def overview(snapshot: FinanceSnapshot) -> FinanceOverview:
    return FinanceOverview(
        meta=finance_meta(snapshot),
        balance=balance(snapshot),
        net_worth=net_worth(snapshot),
        accounts=list(snapshot.accounts),
        balance_history=balance_history(snapshot),
        net_worth_history=net_worth_history(snapshot),
    )


def spending_response(snapshot: FinanceSnapshot, month: str | None = None) -> SpendingResponse:
    from lifeline_engine.money.category import statement_months

    m = month or dates.month_of(dates.parse(snapshot.as_of))
    cats = spending(snapshot.transactions, m)
    return SpendingResponse(
        meta=finance_meta(snapshot), month=m, total=round(sum(c.amount for c in cats), 2), categories=cats,
        months=statement_months(snapshot),
    )


def subscriptions_response(snapshot: FinanceSnapshot, today: dates.date | None = None) -> SubscriptionsResponse:
    items = detect_subscriptions(snapshot.transactions, _today(snapshot, today))
    return SubscriptionsResponse(
        meta=finance_meta(snapshot),
        monthly_total=round(sum(s.monthly_cost for s in items), 2),
        count=len(items),
        items=items,
    )


def bills_response(snapshot: FinanceSnapshot, today: dates.date | None = None) -> BillsResponse:
    items = upcoming_bills(snapshot.transactions, _today(snapshot, today))
    return BillsResponse(
        meta=finance_meta(snapshot),
        total_next_30_days=round(sum(b.amount for b in items), 2),
        items=items,
    )


def budgets_response(
    snapshot: FinanceSnapshot, limits: Mapping[Category, float], month: str | None = None
) -> BudgetsResponse:
    m = month or dates.month_of(dates.parse(snapshot.as_of))
    return BudgetsResponse(meta=finance_meta(snapshot), month=m, items=budgets(snapshot.transactions, m, limits))


def goals_response(
    snapshot: FinanceSnapshot, goals: Iterable[SavingsGoal], today: dates.date | None = None
) -> GoalsResponse:
    return GoalsResponse(meta=finance_meta(snapshot), items=goals_progress(goals, _today(snapshot, today)))


def finance_profile(
    snapshot: FinanceSnapshot, today: dates.date | None = None, hints: ProfileHints | None = None
) -> FinanceProfile:
    prof, char = profile(snapshot, _today(snapshot, today), hints)
    return FinanceProfile(
        meta=finance_meta(snapshot), profile=prof, character=char, personal_facts=personal_facts(snapshot)
    )
