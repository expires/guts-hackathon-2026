"""Bank (Monzo OAuth; TrueLayer disabled) and the demo store."""

from __future__ import annotations

import html
import logging
from typing import Annotated, Any, Literal
from urllib.parse import parse_qs, urlencode, urlparse

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import HTMLResponse

from lifeline_api import money
from lifeline_api.auth import Subject
from lifeline_api.errors import PROVIDER_STATUS, ApiError, not_implemented
from lifeline_api.routes import connections
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import AppState, get_state
from lifeline_contracts.api_models import (
    BankAuthLink,
    BankSummary,
    PurchaseVerifyRequest,
    PurchaseVerifyResponse,
)
from lifeline_contracts.brand import PRODUCT_NAME
from lifeline_data.providers._http import ProviderError

router = APIRouter()



APP_SCHEME = "lifeline://connected"  # the URL scheme in apps/ios/project.yml
log = logging.getLogger(__name__)

CALLBACK_HTML = (
    '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" '
    'content="width=device-width, initial-scale=1"><title>{title}</title></head>'
    '<body style="font-family: -apple-system, sans-serif; text-align: center; padding: 3rem 1rem">'
    "<h1>{title}</h1><p>{body}</p>"
    '<p><a href="{deep}" style="display:inline-block; padding: 0.9rem 1.6rem; border-radius: 999px; '
    'background:#0071e3; color:#fff; text-decoration:none; font-weight:600">Open {product}</a></p>'
    "<script>window.location.href = {deep_js};</script></body></html>"
)
# Plain-English reasons for the browser page; the app gets the same code in the deep link.
CALLBACK_REASONS = {
    "bad_state": "This sign-in link expired or was already used. Go back to {product} and tap Connect again.",
    "provider_auth": "Monzo did not accept the sign-in. Go back to {product} and try again.",
    "not_configured": "Monzo sign-in is not set up on this server yet.",
    "access_denied": "Sign-in was cancelled.",
    "missing_code": "Monzo did not send a sign-in code. Go back to {product} and try again.",
}


def _hub(request: Request) -> Any:
    return get_state(request).hub


def _app_redirect(request: Request, query: dict[str, str]) -> Response:
    """302 to the app's custom scheme for API clients. Browsers (Accept: text/html) get a page with an
    "Open Penny" button instead: iOS Safari often won't follow a server redirect to a custom scheme
    at the end of a sign-in chain, and the page also shows why a sign-in failed. The deep link is also
    sent in the X-App-Redirect header."""
    deep = f"{APP_SCHEME}?{urlencode(query)}"
    if "text/html" not in request.headers.get("accept", ""):
        return Response(status_code=302, headers={"Location": deep})
    ok = query.get("status") == "ok"
    code = query.get("code", "")
    reason = CALLBACK_REASONS.get(code, f"Something went wrong ({code}). Go back to {{product}} and try again.")
    page = CALLBACK_HTML.format(
        title="Monzo connected" if ok else "Could not connect Monzo",
        body=f"Monzo connected. Approve the request in your Monzo app if it asks, then open {PRODUCT_NAME}."
        if ok
        else html.escape(reason.format(product=PRODUCT_NAME)),
        product=PRODUCT_NAME,
        deep=html.escape(deep, quote=True),
        deep_js=html.escape(repr(deep), quote=False),
    )
    return HTMLResponse(page, headers={"X-App-Redirect": deep})


def _safe_code(raw: str) -> str:
    cleaned = "".join(c for c in raw.lower() if c.isalnum() or c == "_")[:40]
    return cleaned or "unknown"


@router.get("/v1/bank/auth-link", tags=["bank"], response_model=BankAuthLink, response_model_exclude_none=True)
async def get_bank_auth_link(
    request: Request,
    sub: Subject,
    provider: Annotated[Literal["monzo", "truelayer"], Query()] = "monzo",
) -> BankAuthLink:
    """Live Monzo sign-in link. Never a mock link (ADR 0027): without Monzo OAuth set up the error says so."""
    if provider == "truelayer":
        raise _bank_disabled()
    url: str = await _hub(request).monzo_start(sub)  # ProviderError(not_configured) becomes 503
    values = parse_qs(urlparse(url).query).get("state", [""])
    return BankAuthLink(url=url, state=values[0], provider="monzo", status="live")


@router.get("/v1/bank/callback", tags=["bank"], response_class=Response, status_code=302)
async def bank_callback(
    request: Request,
    state: Annotated[str, Query(max_length=256)],
    code: Annotated[str | None, Query(max_length=2048)] = None,
    error: Annotated[str | None, Query(max_length=256)] = None,
) -> Response:
    """Browser redirect target. No app auth: the single-use `state` identifies who started the flow."""
    app = get_state(request)
    if error:
        return _app_redirect(request, {"status": "error", "code": _safe_code(error)})
    if not code:
        return _app_redirect(request, {"status": "error", "code": "missing_code"})
    try:
        subject: str = await _hub(request).monzo_callback(state, code)
        await connections.adopt_live(app, subject)
    except ProviderError as exc:
        log.warning("monzo callback failed: code=%s", exc.code)
        return _app_redirect(
            request, {"status": "error", "code": PROVIDER_STATUS.get(exc.code, (502, "unavailable"))[1]}
        )
    return _app_redirect(request, {"status": "ok", "provider": "monzo", "session": state})


@router.get("/v1/bank/summary", tags=["bank"], response_model=BankSummary, response_model_exclude_none=True)
async def get_bank_summary(
    request: Request, session: Annotated[str, Query(min_length=1, max_length=128)], sub: Subject
) -> BankSummary:
    """Profile from the caller's own snapshot (live when connected). The session id only has to be present."""
    app = get_state(request)
    snap = await money.snapshot(app, sub)
    profile, _ = await call_pure(money.engine_profile, snap, None)
    return BankSummary(
        status=snap.status,
        provider="monzo" if "monzo" in snap.source else snap.source,
        profile=profile,
        accounts=len(snap.accounts),
    )


def _bank_disabled() -> ApiError:
    """The TrueLayer provider is disabled (ADR 0027): its sandbox only has test banks."""
    return ApiError(409, "source_disabled", "Bank connection is not available.", source="truelayer")


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
