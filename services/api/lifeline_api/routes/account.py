"""Accounts, onboarding and on-device connectors (ADR 0029)."""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from starlette.datastructures import UploadFile as StarletteUploadFile

from lifeline_api import account, learn_progress, money, onboarding, samples
from lifeline_api.auth import Subject, _bearer, revoke
from lifeline_api.errors import ApiError, not_found
from lifeline_api.routes.finance import DOC_BUDGETS, DOC_GOALS, MAX_GOALS
from lifeline_api.routes.next_move import _compute as compute_next_move
from lifeline_api.routes.next_move import valid_items
from lifeline_api.sim_bridge import call_parse, call_pure
from lifeline_api.state import AppState, get_state
from lifeline_contracts.account import (
    HealthSignal,
    HealthSignalStored,
    ImportResult,
    ImportStage,
    LoggedPayment,
    LogPaymentRequest,
    ManualFinanceInput,
    Me,
    ReversePostcode,
    SamplesResponse,
)
from lifeline_contracts.finance import FinanceProfile, FinanceSnapshot, SavingsGoal
from lifeline_data import statements
from lifeline_engine import money as money_engine

log = logging.getLogger(__name__)

router = APIRouter()


DOC_HEALTH = "health"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> Any:
    return datetime.now(UTC).date()


@router.get("/v1/me", tags=["account"], response_model=Me, response_model_exclude_none=True)
async def get_me(request: Request, sub: Subject) -> Me:
    return await account.me(get_state(request), sub)


@router.delete("/v1/me", tags=["account"], status_code=204)
async def delete_account(request: Request, sub: Subject) -> Response:
    """Removes every record of the user, then revokes the token used for this call."""
    state = get_state(request)
    async with state.subject_locks[f"{sub}:account"]:
        await account.erase(state, sub, keep_account=False)
    await _revoke_current(request)
    return Response(status_code=204)


@router.post("/v1/me/reset", tags=["account"], response_model=Me, response_model_exclude_none=True)
async def reset_demo(request: Request, sub: Subject) -> Me:
    """Back to a fresh start: deletes lives, plan, goals, budgets, guesses, threads and money data.
    The account and the token stay."""
    state = get_state(request)
    async with state.subject_locks[f"{sub}:account"]:
        await account.erase(state, sub, keep_account=True)
    return await account.me(state, sub)


async def _revoke_current(request: Request) -> None:
    creds: HTTPAuthorizationCredentials | None = await _bearer(request)
    if creds is not None:
        await revoke(get_state(request), creds.credentials)


@router.post("/v1/auth/logout", tags=["auth"], status_code=204)
async def sign_out(request: Request, sub: Subject) -> Response:
    await _revoke_current(request)
    return Response(status_code=204)


# ---------- money data the user gives us ----------


@router.post("/v1/finance/statements", tags=["finance"], status_code=201, response_model=ImportResult,
             response_model_exclude_none=True)
async def import_statement(request: Request, sub: Subject) -> ImportResult:
    """Multipart upload (CSV or PDF). The body limit for this path is 5 MB (main.MAX_STATEMENT_BYTES)."""
    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        raise ApiError(422, "validation_error", "file: send the statement as multipart/form-data")
    try:
        form = await request.form(max_files=1, max_fields=4)
    except Exception as exc:
        raise ApiError(400, "bad_request", "The upload could not be read") from exc
    upload = form.get("file")
    if not isinstance(upload, StarletteUploadFile):
        raise ApiError(422, "validation_error", "file: required")
    content = await upload.read(statements.MAX_BYTES + 1)
    state = get_state(request)
    parsed = await call_parse(state.parse_slots, statements.parse_statement, content, upload.filename)

    stages = {name: False for name in STAGE_LABELS}
    stages["read"] = parsed.status != "failed"
    if parsed.status == "failed":
        return _import_result(parsed, stages)

    async with state.subject_locks[f"{sub}:money"]:
        previous = await money.stored_snapshot(state, sub)
        stmt = await call_pure(statements.to_snapshot, parsed, region=None, postcode=None, holder=None)
        snap = onboarding.merge_statement(previous, stmt)
        await money.save_snapshot(state, sub, snap)
    return await _finish_import(state, sub, parsed, snap, stages)


async def _finish_import(state: AppState, sub: str, parsed: Any, snap: FinanceSnapshot,
                         stages: dict[str, bool]) -> ImportResult:
    """The stages after the data is saved: profile and next move, as the import screen shows them."""
    stages["categorise"] = True
    stages["find_bills"] = True
    try:
        await call_pure(money_engine.finance_profile, snap, money.today(snap), None)
        stages["build_profile"] = True
        stages["next_move"] = await _next_move_within_budget(state, sub)
    except ApiError as exc:
        parsed.warnings.append(f"{STAGE_LABELS['next_move'] if stages['build_profile'] else 'Profile'}: "
                               f"{exc.message}")
    return _import_result(parsed, stages)


NEXT_MOVE_BUDGET_SECONDS = 4.0


async def _next_move_within_budget(state: AppState, sub: str) -> bool:
    """The import never waits long for live data (V1): the next move is computed in the background and
    stored; if it is not ready within the budget the stage stays open and GET /v1/next-move finishes it."""
    task = asyncio.ensure_future(compute_next_move(state, sub, reword=False))
    building = state.memo.get(("macro-build",))
    budget = 0.2 if building is not None and not building.done() else NEXT_MOVE_BUDGET_SECONDS  # cold start
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=budget)
        return True
    except TimeoutError:
        state.games.add(task)  # keep a reference; it stores the move when done

        def done(t: asyncio.Future[Any]) -> None:
            state.games.discard(t)
            if not t.cancelled() and t.exception() is not None:
                log.info("background next move failed: %s", type(t.exception()).__name__)

        task.add_done_callback(done)
        return False


STAGE_LABELS = {
    "read": "Reading your statement",
    "categorise": "Sorting your spending",
    "find_bills": "Finding your bills",
    "build_profile": "Building your profile",
    "next_move": "Finding your next move",
}


def _import_result(parsed: Any, stages: dict[str, bool]) -> ImportResult:
    return ImportResult(
        import_id=f"im_{secrets.token_hex(6)}",
        status=parsed.status,
        provider=parsed.provider,
        transactions=len(parsed.transactions),
        first_date=parsed.first_date,
        last_date=parsed.last_date,
        months_covered=parsed.months_covered,
        warnings=list(parsed.warnings)[:20],
        stages=[ImportStage(name=n, label=STAGE_LABELS[n], done=d) for n, d in stages.items()],
    )


@router.put("/v1/finance/manual", tags=["finance"], response_model=FinanceProfile, response_model_exclude_none=True)
async def set_manual_finance(body: ManualFinanceInput, request: Request, sub: Subject) -> FinanceProfile:
    state = get_state(request)
    today = _today()
    snap = onboarding.manual_snapshot(body, today)
    place = await state.hub.lookup_postcode(body.postcode)
    acct = await account.ensure(state, sub)
    snap = onboarding.with_holder(snap, body, place, acct.get("display_name"))
    async with state.subject_locks[f"{sub}:money"]:
        snap = onboarding.merge_manual(await money.stored_snapshot(state, sub), snap)
        await money.save_snapshot(state, sub, snap)
        await money.save_onboarding(state, sub, is_student=body.is_student, housing=body.housing, age=body.age)
    prof = await call_pure(money_engine.finance_profile, snap, money.today(snap), None)
    return await money.with_onboarding(state, sub, prof, snap)


@router.post("/v1/finance/transactions", tags=["finance"], status_code=201, response_model=LoggedPayment,
             response_model_exclude_none=True)
async def log_payment(body: LogPaymentRequest, request: Request, sub: Subject) -> LoggedPayment:
    """App Intent "Log a payment". Appends to the user's own data (a new empty snapshot when they have none)."""
    state = get_state(request)
    today = _today()
    tx = onboarding.logged_transaction(body, today)
    async with state.subject_locks[f"{sub}:money"]:
        base = await money.maybe_snapshot(state, sub)  # own data only; none means a new empty snapshot
        snap = base if base is not None else onboarding.empty_snapshot(today)
        as_of = max(snap.as_of, today.isoformat())
        snap = snap.model_copy(update={"transactions": [*snap.transactions, tx], "as_of": as_of})
        await money.save_snapshot(state, sub, snap)
    category = body.category or await call_pure(money_engine.categorise, tx)
    return LoggedPayment(transaction=tx, category=category)


# ---------- connectors ----------


@router.put("/v1/me/health", tags=["account"], response_model=HealthSignalStored, response_model_exclude_none=True)
async def set_health_signal(body: HealthSignal, request: Request, sub: Subject) -> HealthSignalStored:
    stored = HealthSignalStored(
        steps_per_day=body.steps_per_day,
        sleep_hours=body.sleep_hours,
        measured_days=body.measured_days,
        health_effect=onboarding.health_effect(body),
        updated_at=_now(),
    )
    await get_state(request).store.put_doc(sub, DOC_HEALTH, stored.model_dump(mode="json"))
    return stored


@router.get("/v1/postcodes/reverse", tags=["account"], response_model=ReversePostcode,
            response_model_exclude_none=True)
async def reverse_postcode(
    request: Request,
    sub: Subject,
    lat: Annotated[float, Query(ge=49.0, le=61.5)],
    lon: Annotated[float, Query(ge=-8.7, le=2.0)],
) -> ReversePostcode:
    hub: Any = get_state(request).hub
    hit: dict[str, Any] | None = await hub.reverse_postcode(lat, lon)
    if hit is None:
        raise not_found("No postcode near this location")
    return ReversePostcode.model_validate(hit)


# ---------- sample statements (ADR 0047) ----------


@router.get("/v1/samples", tags=["finance"], response_model=SamplesResponse, response_model_exclude_none=True)
async def list_samples(sub: Subject) -> SamplesResponse:
    """The 10 built-in student statements for the judge picker. `team` is always false."""
    return samples.listing()


@router.post("/v1/samples/{sample_id}/import", tags=["finance"], status_code=201, response_model=ImportResult,
             response_model_exclude_none=True)
async def import_sample(sample_id: str, request: Request, sub: Subject) -> ImportResult:
    """Import a sample through the statement pipeline (W1's parser). It replaces the user's data and is labelled
    "Sample data". Student facts (income dates, loan plan, debts, age, housing) come from the sample's hints."""
    hint = samples.hints(sample_id)  # only ids from the index reach the file system
    state = get_state(request)
    try:
        snap = await call_parse(state.parse_slots, samples.load, sample_id) if hint is not None else None
    except samples.SampleWithoutBalance as exc:
        raise ApiError(503, "sample_unavailable", "This sample cannot be read right now.",
                       source="statements") from exc
    if hint is None or snap is None:
        raise not_found(f"Unknown sample {sample_id}")
    async with state.subject_locks[f"{sub}:money"]:
        await money.save_snapshot(state, sub, snap)
        await money.save_onboarding(state, sub, is_student=hint.get("is_student"),
                                    housing=hint.get("housing") or "rent", age=hint.get("age"))
    await _set_up_sample_plan(state, sub, hint, snap)
    await learn_progress.mark_sample_passed(state, sub)  # ADR 0068: a judge sees Learn progress
    days = [t.date for t in snap.transactions]
    parsed = SimpleNamespace(
        status="done", provider="monzo", transactions=snap.transactions, warnings=[],
        first_date=min(days, default=None), last_date=max(days, default=None),
        months_covered=samples.months_covered(snap),
    )
    stages = {name: name == "read" for name in STAGE_LABELS}
    return await _finish_import(state, sub, parsed, snap, stages)


async def _set_up_sample_plan(state: AppState, sub: str, hint: dict[str, Any], snap: FinanceSnapshot) -> None:
    """ADR 0070: every sample comes with its budgets and savings goals. The sample's budgets replace the stored
    limits (the import replaces the user's money data). Goals from any earlier sample import are replaced; goals
    the user made stay. Stable ids mean a re-import never adds copies. Reset (/v1/me/reset) deletes both docs."""
    budgets, goal_reqs = samples.plan(hint)
    async with state.subject_locks[f"{sub}:{DOC_BUDGETS}"]:
        await state.store.put_doc(sub, DOC_BUDGETS, [b.model_dump(mode="json") for b in budgets])
    today = money.today(snap)
    new = [await call_pure(money_engine.goal_from_request, gid, req, today) for gid, req in goal_reqs]
    async with state.subject_locks[f"{sub}:{DOC_GOALS}"]:
        kept = [g for g in valid_items(SavingsGoal, await state.store.get_doc(sub, DOC_GOALS))
                if not g.id.startswith(samples.SAMPLE_GOAL_PREFIX)]
        goals = [*new, *kept][:MAX_GOALS]
        await state.store.put_doc(sub, DOC_GOALS, [g.model_dump(mode="json") for g in goals])
