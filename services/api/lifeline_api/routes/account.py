"""Accounts, onboarding and on-device connectors (ADR 0029)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from starlette.datastructures import UploadFile as StarletteUploadFile

from lifeline_api import account, money, onboarding
from lifeline_api.auth import Subject, _bearer, revoke
from lifeline_api.errors import ApiError, not_found
from lifeline_api.routes.next_move import _compute as compute_next_move
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import get_state
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
)
from lifeline_contracts.finance import FinanceProfile
from lifeline_data import statements
from lifeline_engine import money as money_engine

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
    parsed = await call_pure(statements.parse_statement, content, upload.filename)

    state = get_state(request)
    stages = {name: False for name in STAGE_LABELS}
    stages["read"] = parsed.status != "failed"
    if parsed.status == "failed":
        return _import_result(parsed, stages)

    async with state.subject_locks[f"{sub}:money"]:
        previous = await money.stored_snapshot(state, sub)
        stmt = await call_pure(statements.to_snapshot, parsed, region=None, postcode=None, holder=None)
        snap = onboarding.merge_statement(previous, stmt)
        await money.save_snapshot(state, sub, snap)
    stages["categorise"] = True
    stages["find_bills"] = True
    try:
        await call_pure(money_engine.finance_profile, snap, money.today(snap), None)
        stages["build_profile"] = True
        await compute_next_move(state, sub)
        stages["next_move"] = True
    except ApiError as exc:
        parsed.warnings.append(f"{STAGE_LABELS['next_move'] if stages['build_profile'] else 'Profile'}: "
                               f"{exc.message}")
    return _import_result(parsed, stages)


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
    return await call_pure(money_engine.finance_profile, snap, money.today(snap), None)


@router.post("/v1/finance/transactions", tags=["finance"], status_code=201, response_model=LoggedPayment,
             response_model_exclude_none=True)
async def log_payment(body: LogPaymentRequest, request: Request, sub: Subject) -> LoggedPayment:
    """App Intent "Log a payment". Appends to the user's own data (demo mode: to a copy of their sample data)."""
    state = get_state(request)
    today = _today()
    tx = onboarding.logged_transaction(body, today)
    async with state.subject_locks[f"{sub}:money"]:
        base = await money.maybe_snapshot(state, sub)  # own data, else (demo mode) the sample persona
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
