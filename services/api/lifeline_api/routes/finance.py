"""Money tab (ADR 0016, 0017). Every handler reads the caller's own snapshot (`money.snapshot`): live or cached
Monzo and Trading212 data when connected, else the labelled sample persona (`meta.data_status` says which).

Per-subject documents in the store: `budgets` (limits by category), `goals` (savings goals), `guesses`
(Guess my spend, one per day).
"""

from __future__ import annotations

import secrets
from datetime import UTC, date, datetime
from typing import Annotated, Any, cast

from fastapi import APIRouter, Query, Request

from lifeline_api import money
from lifeline_api.auth import Subject
from lifeline_api.errors import ApiError
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState, get_state
from lifeline_contracts.finance import (
    BillsResponse,
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
    InvestmentsResponse,
    ModelInfo,
    PredictionEvaluation,
    SavingsGoal,
    SpendingResponse,
    SpendPrediction,
    SubscriptionsResponse,
    UpdateBudgetsRequest,
    Weather,
)
from lifeline_data.prediction_inputs import fixture_holidays_for, mock_weather_day
from lifeline_engine import money as money_engine
from lifeline_engine.money import dates, predict
from lifeline_engine.money.profile import is_cash_savings

router = APIRouter(tags=["finance"])

Month = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")]
Day = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")]

DOC_BUDGETS = "budgets"
DOC_GOALS = "goals"
DOC_GUESSES = "guesses"
MAX_GUESS_ITEMS = 60
NOT_ENOUGH = (
    "We need about seven weeks of spending history before we can predict a day. "
    "Connect your bank, or check back soon."
)


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


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


# ---------- budgets ----------


async def _limits(state: AppState, sub: str, snap: FinanceSnapshot) -> dict[Category, float]:
    doc = await state.store.get_doc(sub, DOC_BUDGETS)
    if isinstance(doc, dict) and doc:
        return {cast(Category, c): float(v) for c, v in doc.items()}
    return money.default_limits(snap)


@router.get("/v1/finance/budgets", response_model=BudgetsResponse, response_model_exclude_none=True)
async def list_budgets(request: Request, sub: Subject, month: Month = None) -> BudgetsResponse:
    state, snap = await _snap(request, sub)
    return await call_pure(money_engine.budgets_response, snap, await _limits(state, sub, snap), month)


@router.put("/v1/finance/budgets", response_model=BudgetsResponse, response_model_exclude_none=True)
async def update_budgets(body: UpdateBudgetsRequest, request: Request, sub: Subject) -> BudgetsResponse:
    state, snap = await _snap(request, sub)
    async with state.subject_locks[f"{sub}:{DOC_BUDGETS}"]:
        limits = await _limits(state, sub, snap)
        for item in body.items:
            limits[item.category] = item.limit
        await state.store.put_doc(sub, DOC_BUDGETS, dict(limits))
    return await call_pure(money_engine.budgets_response, snap, limits, None)


# ---------- goals ----------


async def _goals(state: AppState, sub: str) -> list[SavingsGoal]:
    doc = await state.store.get_doc(sub, DOC_GOALS)
    return [SavingsGoal.model_validate(g) for g in (doc or [])]


@router.get("/v1/finance/goals", response_model=GoalsResponse, response_model_exclude_none=True)
async def list_goals(request: Request, sub: Subject) -> GoalsResponse:
    state, snap = await _snap(request, sub)
    return await call_pure(money_engine.goals_response, snap, await _goals(state, sub), money.today(snap))


@router.post("/v1/finance/goals", status_code=201, response_model=SavingsGoal, response_model_exclude_none=True)
async def create_goal(body: CreateGoalRequest, request: Request, sub: Subject) -> SavingsGoal:
    state, snap = await _snap(request, sub)
    goal = money_engine.goal_from_request(f"gl_{secrets.token_hex(5)}", body, money.today(snap))
    async with state.subject_locks[f"{sub}:{DOC_GOALS}"]:
        goals = [*await _goals(state, sub), goal]
        await state.store.put_doc(sub, DOC_GOALS, [g.model_dump(mode="json") for g in goals])
    return goal


@router.get("/v1/finance/profile", response_model=FinanceProfile, response_model_exclude_none=True)
async def get_finance_profile(request: Request, sub: Subject) -> FinanceProfile:
    _, snap = await _snap(request, sub)
    return await call_pure(money_engine.finance_profile, snap, money.today(snap), money.hints(sub, snap))


# ---------- investments ----------


@router.get("/v1/finance/investments", response_model=InvestmentsResponse, response_model_exclude_none=True)
async def get_investments(request: Request, sub: Subject) -> InvestmentsResponse:
    _, snap = await _snap(request, sub)
    total = round(sum(h.value for h in snap.holdings), 2)
    allocation: dict[str, float] = {}
    for h in snap.holdings:
        allocation[h.asset_class] = allocation.get(h.asset_class, 0.0) + h.value
    shares = {k: round(v / total * 100, 2) for k, v in sorted(allocation.items())} if total > 0 else {}
    invest_accounts = sum(
        a.balance for a in snap.accounts if a.kind == "isa" and (a.provider == "trading212" or not is_cash_savings(a))
    )
    return InvestmentsResponse(
        meta=money.meta(snap),
        holdings=snap.holdings,
        total_value=total,
        cash=round(max(0.0, invest_accounts - total), 2) if snap.holdings else 0.0,
        allocation=shares,
    )


# ---------- spend prediction and Guess my spend (ADR 0017) ----------


def _weather_fn(sub: str, snap: FinanceSnapshot) -> predict.Weather:
    hints = money.hints(sub, snap)
    region = hints.region if hints else None

    def weather(day: date) -> tuple[float, float]:
        w = mock_weather_day(region, day)
        return float(w["temp_max_c"]), float(w["rain_mm"])

    return weather


def _holidays(sub: str, snap: FinanceSnapshot) -> frozenset[date]:
    hints = money.hints(sub, snap)
    return frozenset(fixture_holidays_for(hints.region if hints else None))


def _not_enough() -> ApiError:
    return ApiError(409, "not_enough_data", NOT_ENOUGH)


async def _evaluation(state: AppState, sub: str, snap: FinanceSnapshot) -> predict.Evaluation:
    key = ("prediction", sub)
    hit = state.memo.get(key)
    if hit is not None and hit[0] is snap:
        return cast(predict.Evaluation, hit[1])
    try:
        ev = await call_pure(
            predict.evaluate, snap.transactions, money.today(snap), _holidays(sub, snap), _weather_fn(sub, snap)
        )
    except ValueError:
        raise _not_enough() from None
    state.memo[key] = (snap, ev)
    return ev


def _parse_day(text: str | None, snap: FinanceSnapshot) -> date:
    today = money.today(snap)
    if text is None:
        return today
    try:
        day = date.fromisoformat(text)
    except ValueError:
        raise ApiError(422, "validation_error", "date: not a real calendar day") from None
    if day > today:
        raise ApiError(422, "validation_error", "date: that day has not happened yet")
    return day


async def _guesses(state: AppState, sub: str) -> dict[str, dict[str, Any]]:
    doc = await state.store.get_doc(sub, DOC_GUESSES)
    return cast(dict[str, dict[str, Any]], doc) if isinstance(doc, dict) else {}


async def _predict(
    state: AppState, sub: str, snap: FinanceSnapshot, day: date
) -> tuple[predict.DayPrediction, predict.Evaluation]:
    ev = await _evaluation(state, sub, snap)
    try:
        pred = await call_pure(
            predict.predict_day, snap.transactions, day, _holidays(sub, snap), _weather_fn(sub, snap)
        )
    except ValueError:
        raise _not_enough() from None
    return pred, ev


def _guess_state(guess: dict[str, Any], pred: float, actual: float | None) -> GuessState:
    amount = float(guess["amount"])
    points = predict.guess_points(amount, actual) if actual is not None else None
    return GuessState(
        amount=amount,
        made_at=str(guess["made_at"]),
        points=points,
        beat_model=predict.beat_model(amount, pred, actual) if actual is not None else None,
    )


def _weather_info(sub: str, snap: FinanceSnapshot, day: date) -> Weather:
    w = mock_weather_day(money.hints(sub, snap).region if money.hints(sub, snap) else None, day)
    wet = float(w["rain_mm"]) >= 1.0
    return Weather(
        summary=f"{'Wet' if wet else 'Dry'}, {float(w['temp_max_c']):.0f} degrees",
        temp_max_c=float(w["temp_max_c"]),
        rain_mm=float(w["rain_mm"]),
        status="mock",
    )


async def _build_prediction(state: AppState, sub: str, snap: FinanceSnapshot, day: date) -> SpendPrediction:
    pred, ev = await _predict(state, sub, snap, day)
    today = money.today(snap)
    actual = predict.actual_spend(snap.transactions, day) if day < today else None
    guess = (await _guesses(state, sub)).get(day.isoformat())
    return SpendPrediction(
        meta=money.meta(snap),
        date=day.isoformat(),
        predicted=pred.predicted,
        low=pred.low,
        high=pred.high,
        baseline=pred.baseline,
        reasons=pred.reasons,
        weather=_weather_info(sub, snap, day),
        is_bank_holiday=day in _holidays(sub, snap),
        days_to_payday=pred.days_to_payday,
        guess=_guess_state(guess, pred.predicted, actual) if guess else None,
        actual=actual,
        model=ModelInfo(
            name=predict.MODEL_NAME,
            trained_on_days=pred.trained_on_days,
            mae=ev.mae,
            baseline_mae=ev.baseline_mae,
            interval_coverage=ev.coverage,
        ),
    )


# The evaluation route is registered before /prediction on purpose.


@router.get("/v1/finance/prediction/evaluation", response_model=PredictionEvaluation,
            response_model_exclude_none=True)
async def get_prediction_evaluation(request: Request, sub: Subject) -> PredictionEvaluation:
    state, snap = await _snap(request, sub)
    ev = await _evaluation(state, sub, snap)
    return PredictionEvaluation(
        meta=money.meta(snap),
        method=predict.MODEL_NAME,
        n_days=len(ev.days),
        mae=ev.mae,
        baseline_mae=ev.baseline_mae,
        baseline="Average spend on the same weekday over the days before",
        interval_coverage=ev.coverage,
        days=ev.days,
    )


@router.get("/v1/finance/prediction", response_model=SpendPrediction, response_model_exclude_none=True)
async def get_spend_prediction(request: Request, sub: Subject, date: Day = None) -> SpendPrediction:
    state, snap = await _snap(request, sub)
    return await _build_prediction(state, sub, snap, _parse_day(date, snap))


@router.get("/v1/finance/guesses", response_model=GuessesResponse, response_model_exclude_none=True)
async def list_guesses(request: Request, sub: Subject) -> GuessesResponse:
    state, snap = await _snap(request, sub)
    guesses = await _guesses(state, sub)
    today = money.today(snap)
    items: list[GuessDay] = []
    points_by_day: dict[str, int | None] = {}
    for key in sorted(guesses, reverse=True)[:MAX_GUESS_ITEMS]:
        day = dates.parse(key)
        pred, _ = await _predict(state, sub, snap, day)
        actual = predict.actual_spend(snap.transactions, day) if day < today else None
        gs = _guess_state(guesses[key], pred.predicted, actual)
        points_by_day[key] = gs.points
        items.append(GuessDay(date=key, guess=gs.amount, predicted=pred.predicted, actual=actual, points=gs.points,
                              beat_model=gs.beat_model))
    current, best = predict.streaks(points_by_day)
    return GuessesResponse(meta=money.meta(snap), points_total=sum(p or 0 for p in points_by_day.values()),
                           streak=current, best_streak=best, items=items)


@router.post("/v1/finance/guesses", status_code=201, response_model=SpendPrediction,
             response_model_exclude_none=True)
async def make_guess(body: GuessRequest, request: Request, sub: Subject) -> SpendPrediction:
    state, snap = await _snap(request, sub)
    day = _parse_day(body.date, snap)
    async with state.subject_locks[f"{sub}:{DOC_GUESSES}"]:
        guesses = await _guesses(state, sub)
        if day.isoformat() in guesses:
            raise ApiError(409, "already_guessed", "You already guessed that day")
        await _predict(state, sub, snap, day)  # fails early (409) when there is not enough history
        guesses[day.isoformat()] = {"amount": body.amount, "made_at": _utc_now()}
        await state.store.put_doc(sub, DOC_GUESSES, guesses)
    return await _build_prediction(state, sub, snap, day)

