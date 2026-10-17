"""Money tab (ADR 0016, Tier 1). Auth and input validation now; 501 not_implemented until Tier 1."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from lifeline_api.auth import Subject
from lifeline_api.errors import not_implemented
from lifeline_contracts.finance import (
    BillsResponse,
    BudgetsResponse,
    CreateGoalRequest,
    FinanceOverview,
    FinanceProfile,
    GoalsResponse,
    GuessesResponse,
    GuessRequest,
    PredictionEvaluation,
    SavingsGoal,
    SpendingResponse,
    SpendPrediction,
    SubscriptionsResponse,
    UpdateBudgetsRequest,
)

router = APIRouter(tags=["finance"])

Month = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")]
Day = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")]


@router.get("/v1/finance/overview", response_model=FinanceOverview, response_model_exclude_none=True)
async def get_finance_overview(sub: Subject) -> FinanceOverview:
    raise not_implemented("Finance overview")


@router.get("/v1/finance/spending", response_model=SpendingResponse, response_model_exclude_none=True)
async def get_finance_spending(sub: Subject, month: Month = None) -> SpendingResponse:
    raise not_implemented("Spending")


@router.get("/v1/finance/subscriptions", response_model=SubscriptionsResponse, response_model_exclude_none=True)
async def list_subscriptions(sub: Subject) -> SubscriptionsResponse:
    raise not_implemented("Subscriptions")


@router.get("/v1/finance/bills", response_model=BillsResponse, response_model_exclude_none=True)
async def list_bills(sub: Subject) -> BillsResponse:
    raise not_implemented("Bills")


@router.get("/v1/finance/budgets", response_model=BudgetsResponse, response_model_exclude_none=True)
async def list_budgets(sub: Subject, month: Month = None) -> BudgetsResponse:
    raise not_implemented("Budgets")


@router.put("/v1/finance/budgets", response_model=BudgetsResponse, response_model_exclude_none=True)
async def update_budgets(body: UpdateBudgetsRequest, sub: Subject) -> BudgetsResponse:
    raise not_implemented("Budgets")


@router.get("/v1/finance/goals", response_model=GoalsResponse, response_model_exclude_none=True)
async def list_goals(sub: Subject) -> GoalsResponse:
    raise not_implemented("Savings goals")


@router.post("/v1/finance/goals", status_code=201, response_model=SavingsGoal, response_model_exclude_none=True)
async def create_goal(body: CreateGoalRequest, sub: Subject) -> SavingsGoal:
    raise not_implemented("Savings goals")


@router.get("/v1/finance/profile", response_model=FinanceProfile, response_model_exclude_none=True)
async def get_finance_profile(sub: Subject) -> FinanceProfile:
    raise not_implemented("Finance profile")


# Spend prediction (ADR 0017). The evaluation route is registered before /prediction on purpose.


@router.get("/v1/finance/prediction/evaluation", response_model=PredictionEvaluation,
            response_model_exclude_none=True)
async def get_prediction_evaluation(sub: Subject) -> PredictionEvaluation:
    raise not_implemented("Prediction evaluation")


@router.get("/v1/finance/prediction", response_model=SpendPrediction, response_model_exclude_none=True)
async def get_spend_prediction(sub: Subject, date: Day = None) -> SpendPrediction:
    raise not_implemented("Spend prediction")


@router.get("/v1/finance/guesses", response_model=GuessesResponse, response_model_exclude_none=True)
async def list_guesses(sub: Subject) -> GuessesResponse:
    raise not_implemented("Guesses")


@router.post("/v1/finance/guesses", status_code=201, response_model=SpendPrediction,
             response_model_exclude_none=True)
async def make_guess(body: GuessRequest, sub: Subject) -> SpendPrediction:
    raise not_implemented("Guesses")
