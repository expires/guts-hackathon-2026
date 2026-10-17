"""Bank (Monzo arrives with the integration merge; TrueLayer disabled) and the demo store."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request

from lifeline_api.auth import Subject
from lifeline_api.errors import ApiError, not_implemented
from lifeline_api.state import AppState, get_state
from lifeline_contracts.api_models import (
    BankAuthLink,
    BankSummary,
    PurchaseVerifyRequest,
    PurchaseVerifyResponse,
)

router = APIRouter()



def _bank_disabled() -> ApiError:
    """The TrueLayer provider is disabled (ADR 0027): its sandbox only has test banks."""
    return ApiError(409, "source_disabled", "Bank connection is not available.", source="truelayer")


@router.get("/v1/bank/auth-link", tags=["bank"], response_model=BankAuthLink, response_model_exclude_none=True)
async def get_bank_auth_link(
    sub: Subject,
    provider: Annotated[Literal["monzo", "truelayer"], Query()] = "monzo",
) -> BankAuthLink:
    if provider == "truelayer":
        raise _bank_disabled()
    raise not_implemented("Bank connection")  # Monzo OAuth arrives with the integration branch merge.


@router.get("/v1/bank/callback", tags=["bank"])
async def bank_callback(
    state: Annotated[str, Query(max_length=256)],
    code: Annotated[str | None, Query(max_length=2048)] = None,
    error: Annotated[str | None, Query(max_length=256)] = None,
) -> None:
    raise not_implemented("Bank connection")


@router.get("/v1/bank/summary", tags=["bank"], response_model=BankSummary, response_model_exclude_none=True)
async def get_bank_summary(session: Annotated[str, Query(max_length=128)], sub: Subject) -> BankSummary:
    raise not_implemented("Bank connection")


ENTITLEMENT = {"lifeline.rewindpass": "rewind_pass", "lifeline.godmode": "god_mode", "lifeline.bossmode": "boss_mode"}
DOC_ENTITLEMENTS = "entitlements"
DEMO_LABEL = "Demo payment"


@router.post("/v1/purchases/verify", tags=["store"], response_model=PurchaseVerifyResponse,
             response_model_exclude_none=True)
async def verify_purchase(body: PurchaseVerifyRequest, request: Request, sub: Subject) -> PurchaseVerifyResponse:
    """Demo store: no money moves. The entitlement is stored per user and always labelled "Demo payment".
    Real StoreKit transactions (JWS verification against Apple's certificate chain) are not enabled."""
    if not body.demo:
        raise not_implemented("Real purchases")
    state = get_state(request)
    entitlement = ENTITLEMENT[body.product_id]
    async with state.subject_locks[f"{sub}:{DOC_ENTITLEMENTS}"]:
        doc = await state.store.get_doc(sub, DOC_ENTITLEMENTS) or {}
        doc[entitlement] = {"product_id": body.product_id, "demo": True}
        await state.store.put_doc(sub, DOC_ENTITLEMENTS, doc)
    return PurchaseVerifyResponse(product_id=body.product_id, entitlement=entitlement,
                                  active=True, demo=True, label=DEMO_LABEL)


async def has_entitlement(state: AppState, sub: str, entitlement: str) -> bool:
    try:
        doc = await state.store.get_doc(sub, DOC_ENTITLEMENTS)
    except Exception:
        return False
    return bool(doc and entitlement in doc)
