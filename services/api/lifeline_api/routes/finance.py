"""Money tab (ADR 0016) and spend prediction (ADR 0017). Budget limits, goals and guesses are stored per subject."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from datetime import date as date_cls
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from pydantic import AfterValidator

from lifeline_api import money, prediction
from lifeline_api.auth import Subject
from lifeline_api.errors import ApiError
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState, get_state
from lifeline_api.store import StoreUnavailable
from lifeline_contracts.finance import (
    BillsResponse,
    BudgetLimit,
    BudgetsResponse,
    Category,
    CreateGoalRequest,
    FinanceOverview,
    FinanceProfile,
    FinanceSnapshot,
    GoalsResponse,
    GuessDay,
    GuessesResponse,
    GuessRequest,
    GuessState,
    PredictionEvaluation,
    SavingsGoal,
    SpendingResponse,
    SpendPrediction,
    SubscriptionsResponse,
    UpdateBudgetsRequest,
)
from lifeline_engine import money as money_engine
from lifeline_engine.money import predict

router = APIRouter(tags=["finance"])

MAX_GOALS = 20


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

def _real_month(v: str | None) -> str | None:
    if v is not None and not 1 <= int(v[5:7]) <= 12:
        raise ValueError("not a real month")
    return v


def _real_day(v: str | None) -> str | None:
    if v is not None:
        date_cls.fromisoformat(v)  # ValueError for e.g. 2026-02-30 -> 422 validation_error
    return v


Month = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$"), AfterValidator(_real_month)]
Day = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$"), AfterValidator(_real_day)]


DOC_BUDGETS = "budgets"
DOC_GOALS = "goals"


async def _snap(request: Request, sub: str) -> tuple[AppState, FinanceSnapshot]:
    state = get_state(request)
    return state, await money.snapshot(state, sub)


@router.get("/v1/finance/overview", response_model=FinanceOverview, response_model_exclude_none=True)
async def get_finance_overview(request: Request, sub: Subject) -> FinanceOverview:
    _, snap = await _snap(request, sub)
    return await call_pure(money_engine.overview, snap)


@router.get("/v1/finance/spending", response_model=SpendingResponse, response_model_exclude_none=True)
async def get_finance_spending(request: Request, sub: Subject, month: Month = None) -> SpendingResponse:
    _, snap = await _snap(request, sub)
    return await call_pure(money_engine.spending_response, snap, month)


@router.get("/v1/finance/subscriptions", response_model=SubscriptionsResponse, response_model_exclude_none=True)
async def list_subscriptions(request: Request, sub: Subject) -> SubscriptionsResponse:
    _, snap = await _snap(request, sub)
    return await call_pure(money_engine.subscriptions_response, snap, money.today(snap))


@router.get("/v1/finance/bills", response_model=BillsResponse, response_model_exclude_none=True)
async def list_bills(request: Request, sub: Subject) -> BillsResponse:
    _, snap = await _snap(request, sub)
    return await call_pure(money_engine.bills_response, snap, money.today(snap))


async def _limits(state: AppState, sub: str) -> dict[Category, float]:
    doc = await state.store.get_doc(sub, DOC_BUDGETS)
    return {BudgetLimit.model_validate(x).category: BudgetLimit.model_validate(x).limit for x in (doc or [])}


@router.get("/v1/finance/budgets", response_model=BudgetsResponse, response_model_exclude_none=True)
async def list_budgets(request: Request, sub: Subject, month: Month = None) -> BudgetsResponse:
    state, snap = await _snap(request, sub)
    return await call_pure(money_engine.budgets_response, snap, await _limits(state, sub), month)


@router.put("/v1/finance/budgets", response_model=BudgetsResponse, response_model_exclude_none=True)
async def update_budgets(body: UpdateBudgetsRequest, request: Request, sub: Subject) -> BudgetsResponse:
    """Upsert: the listed categories get the new limits, other stored limits stay."""
    state, snap = await _snap(request, sub)
    async with state.subject_locks[f"{sub}:{DOC_BUDGETS}"]:
        limits = await _limits(state, sub)
        for item in body.items:
            limits[item.category] = item.limit
        await state.store.put_doc(sub, DOC_BUDGETS, [{"category": c, "limit": v} for c, v in limits.items()])
    return await call_pure(money_engine.budgets_response, snap, limits, None)


async def _goals(state: AppState, sub: str) -> list[SavingsGoal]:
    doc = await state.store.get_doc(sub, DOC_GOALS)
    return [SavingsGoal.model_validate(x) for x in (doc or [])]


@router.get("/v1/finance/goals", response_model=GoalsResponse, response_model_exclude_none=True)
async def list_goals(request: Request, sub: Subject) -> GoalsResponse:
    state, snap = await _snap(request, sub)
    return await call_pure(money_engine.goals_response, snap, await _goals(state, sub), money.today(snap))


@router.post("/v1/finance/goals", status_code=201, response_model=SavingsGoal, response_model_exclude_none=True)
async def create_goal(body: CreateGoalRequest, request: Request, sub: Subject) -> SavingsGoal:
    state, snap = await _snap(request, sub)
    goal = await call_pure(money_engine.goal_from_request, f"gl_{secrets.token_hex(6)}", body, money.today(snap))
    async with state.subject_locks[f"{sub}:{DOC_GOALS}"]:
        goals = await _goals(state, sub)
        if len(goals) >= MAX_GOALS:
            raise ApiError(422, "validation_error", f"You can keep up to {MAX_GOALS} goals")
        goals.append(goal)
        await state.store.put_doc(sub, DOC_GOALS, [g.model_dump(mode="json") for g in goals])
    return goal


@router.get("/v1/finance/profile", response_model=FinanceProfile, response_model_exclude_none=True)
async def get_finance_profile(request: Request, sub: Subject) -> FinanceProfile:
    _, snap = await _snap(request, sub)
    return await call_pure(money_engine.finance_profile, snap, money.today(snap), money.hints(sub, snap))


# Spend prediction (ADR 0017). The evaluation route is registered before /prediction on purpose.


DOC_GUESSES = "guesses"


async def _guess_docs(state: AppState, sub: str) -> dict[str, dict[str, Any]]:
    doc = await state.store.get_doc(sub, DOC_GUESSES)
    return {g["date"]: g for g in (doc or [])}


def _guess_state(doc: dict[str, Any] | None, actual: float | None) -> GuessState | None:
    if doc is None:
        return None
    if actual is None:
        return GuessState(amount=doc["amount"], made_at=doc["made_at"])
    return GuessState(
        amount=doc["amount"],
        made_at=doc["made_at"],
        points=predict.score_guess(doc["amount"], actual),
        beat_model=predict.beat_model(doc["amount"], doc["predicted"], actual),
    )


def _day(inp: prediction.Inputs, raw: str | None) -> date_cls:
    try:
        day = money.today(inp.snap) if raw is None else date_cls.fromisoformat(raw)
    except ValueError as exc:
        raise ApiError(422, "validation_error", "date: not a real calendar day") from exc
    lo, hi = prediction.earliest_day(inp), inp.last_day
    if not lo <= day <= hi:
        raise ApiError(422, "validation_error", f"date: pick a day from {lo.isoformat()} to {hi.isoformat()}")
    return day


async def _prediction(state: AppState, sub: str, inp: prediction.Inputs, day: date_cls,
                      guess: dict[str, Any] | None) -> SpendPrediction:
    bt = await prediction.backtest(state, sub, inp)
    pred = await call_pure(
        predict.prediction_response, inp.snap, day, inp.holidays, inp.weather,
        inp.weather_status.get(day, "mock"), None, bt,
    )
    if guess is not None:
        pred = pred.model_copy(update={"guess": _guess_state(guess, pred.actual)})
    return pred


@router.get("/v1/finance/prediction/evaluation", response_model=PredictionEvaluation,
            response_model_exclude_none=True)
async def get_prediction_evaluation(request: Request, sub: Subject) -> PredictionEvaluation:
    state = get_state(request)
    inp = await prediction.inputs(state, sub)
    bt = await prediction.backtest(state, sub, inp)
    return await call_pure(predict.evaluation_response, inp.snap, inp.holidays, inp.weather, bt)


@router.get("/v1/finance/prediction", response_model=SpendPrediction, response_model_exclude_none=True)
async def get_spend_prediction(request: Request, sub: Subject, date: Day = None) -> SpendPrediction:  # noqa: A002
    """The full prediction. The client hides predicted, low, high and reasons until `guess` is set."""
    state = get_state(request)
    inp = await prediction.inputs(state, sub)
    day = _day(inp, date)
    try:
        guesses = await _guess_docs(state, sub)
    except StoreUnavailable:
        guesses = {}  # The prediction does not need the store. Show it without a guess.
    return await _prediction(state, sub, inp, day, guesses.get(day.isoformat()))


@router.get("/v1/finance/guesses", response_model=GuessesResponse, response_model_exclude_none=True)
async def list_guesses(request: Request, sub: Subject) -> GuessesResponse:
    state = get_state(request)
    inp = await prediction.inputs(state, sub)
    docs = await _guess_docs(state, sub)
    items = [
        predict.score_day(GuessDay(
            date=d, guess=g["amount"], predicted=g["predicted"],
            actual=prediction.actual_spend(inp, date_cls.fromisoformat(d)),
        ))
        for d, g in sorted(docs.items(), reverse=True)
    ]
    totals = predict.guess_totals(items)
    return GuessesResponse(
        meta=money.meta(inp.snap),
        points_total=totals.points_total,
        streak=totals.streak,
        best_streak=totals.best_streak,
        items=items,
    )


@router.post("/v1/finance/guesses", status_code=201, response_model=SpendPrediction,
             response_model_exclude_none=True)
async def make_guess(body: GuessRequest, request: Request, sub: Subject) -> SpendPrediction:
    """One guess per day. The guess is stored with the model's prediction for that day, for scoring later."""
    state = get_state(request)
    inp = await prediction.inputs(state, sub)
    day = _day(inp, body.date)
    pred = await _prediction(state, sub, inp, day, None)
    async with state.subject_locks[f"{sub}:{DOC_GUESSES}"]:
        docs = await _guess_docs(state, sub)
        if body.date in docs:
            raise ApiError(409, "already_guessed", "You already made a guess for this day")
        doc = {"date": body.date, "amount": body.amount, "made_at": _utc_now(), "predicted": pred.predicted}
        docs[body.date] = doc
        await state.store.put_doc(sub, DOC_GUESSES, list(docs.values()))
    return pred.model_copy(update={"guess": _guess_state(doc, pred.actual)})
