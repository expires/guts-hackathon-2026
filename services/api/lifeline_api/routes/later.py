"""Tier 2 endpoints. Bank connection is built (Monzo OAuth); the rest validate input, then answer 501."""

from __future__ import annotations

import html
import logging
import secrets
import time
from typing import Annotated, Any
from urllib.parse import parse_qs, urlencode, urlparse

from fastapi import APIRouter, Path, Query, Request, Response
from fastapi.responses import HTMLResponse

from lifeline_api import money
from lifeline_api.auth import Subject
from lifeline_api.errors import PROVIDER_STATUS, not_implemented
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import get_state
from lifeline_contracts.api_models import (
    BankAuthLink,
    BankSummary,
    ChallengesResponse,
    CreateRoomRequest,
    PurchaseVerifyRequest,
    PurchaseVerifyResponse,
    Room,
)
from lifeline_data.providers._http import ProviderError

router = APIRouter()

RoomCode = Annotated[str, Path(pattern=r"^[A-Z0-9]{6}$")]


@router.get("/v1/challenges", tags=["learn"], response_model=ChallengesResponse, response_model_exclude_none=True)
async def list_challenges() -> ChallengesResponse:
    raise not_implemented("Challenges")


@router.post("/v1/rooms", tags=["rooms"], status_code=201, response_model=Room, response_model_exclude_none=True)
async def create_room(body: CreateRoomRequest, sub: Subject) -> Room:
    raise not_implemented("Rooms")


@router.get("/v1/rooms/{code}", tags=["rooms"], response_model=Room, response_model_exclude_none=True)
async def get_room(code: RoomCode, sub: Subject) -> Room:
    raise not_implemented("Rooms")


MOCK_STATE_PREFIX = "mock_"
MOCK_STATE_SECONDS = 600.0
APP_SCHEME = "lifeline://connected"
log = logging.getLogger(__name__)

CALLBACK_HTML = (
    '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" '
    'content="width=device-width, initial-scale=1"><title>{title}</title></head>'
    '<body style="font-family: -apple-system, sans-serif; text-align: center; padding: 3rem 1rem">'
    "<h1>{title}</h1><p>{body}</p>"
    '<p><a href="{deep}" style="display:inline-block; padding: 0.9rem 1.6rem; border-radius: 999px; '
    'background:#0071e3; color:#fff; text-decoration:none; font-weight:600">Open Lifeline</a></p>'
    "<script>window.location.href = {deep_js};</script></body></html>"
)
# Plain-English reasons for the browser page; the app gets the same code in the deep link.
CALLBACK_REASONS = {
    "bad_state": "This sign-in link expired or was already used. Go back to Lifeline and tap Connect again.",
    "provider_auth": "Monzo did not accept the sign-in. Check MONZO_CLIENT_ID and MONZO_CLIENT_SECRET on the "
    "server, and that this redirect URL is registered on the Monzo client.",
    "access_denied": "Sign-in was cancelled.",
    "missing_code": "Monzo did not send a sign-in code. Go back to Lifeline and try again.",
}


def _hub(request: Request) -> Any:
    return get_state(request).hub


def _app_redirect(request: Request, query: dict[str, str]) -> Response:
    """302 to the app's custom scheme for API clients. Browsers (Accept: text/html) get a page with an
    "Open Lifeline" button instead: iOS Safari often won't follow a server redirect to a custom scheme
    at the end of a sign-in chain, and the page also shows why a sign-in failed."""
    deep = f"{APP_SCHEME}?{urlencode(query)}"
    if "text/html" not in request.headers.get("accept", ""):
        return Response(status_code=302, headers={"Location": deep})
    ok = query.get("status") == "ok"
    code = query.get("code", "")
    page = CALLBACK_HTML.format(
        title="Monzo connected" if ok else "Could not connect Monzo",
        body="Monzo connected. Approve the request in your Monzo app if it asks, then open Lifeline."
        if ok
        else html.escape(
            CALLBACK_REASONS.get(code, f"Something went wrong ({code}). Go back to Lifeline and try again.")
        ),
        deep=html.escape(deep, quote=True),
        deep_js=html.escape(repr(deep), quote=False),
    )
    return HTMLResponse(page, headers={"X-App-Redirect": deep})


def _safe_code(raw: str) -> str:
    cleaned = "".join(c for c in raw.lower() if c.isalnum() or c == "_")[:40]
    return cleaned or "unknown"


@router.get("/v1/bank/auth-link", tags=["bank"], response_model=BankAuthLink, response_model_exclude_none=True)
async def get_bank_auth_link(request: Request, sub: Subject) -> BankAuthLink:
    """Live Monzo sign-in link when Monzo OAuth is configured, else a labelled mock link (status "mock")."""
    state = get_state(request)
    try:
        url: str = await _hub(request).monzo_start(sub)
    except ProviderError as exc:
        if exc.code != "not_configured":
            raise
        token = MOCK_STATE_PREFIX + secrets.token_urlsafe(16)
        state.memo[("mockbank", token)] = (time.monotonic(), sub)
        base = state.settings.public_base_url.rstrip("/")
        link = f"{base}/v1/bank/callback?{urlencode({'state': token, 'code': 'mock'})}"
        return BankAuthLink(url=link, state=token, provider="monzo", status="mock")
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
    mock = app.memo.pop(("mockbank", state), None) if state.startswith(MOCK_STATE_PREFIX) else None
    if mock is not None:
        if time.monotonic() - mock[0] > MOCK_STATE_SECONDS:
            return _app_redirect(request, {"status": "error", "code": "bad_state"})
        return _app_redirect(request, {"status": "ok", "provider": "monzo", "session": state})
    if not code:
        return _app_redirect(request, {"status": "error", "code": "missing_code"})
    try:
        subject: str = await _hub(request).monzo_callback(state, code)
    except ProviderError as exc:
        log.warning("monzo callback failed: code=%s message=%s", exc.code, exc.message)
        return _app_redirect(
            request, {"status": "error", "code": PROVIDER_STATUS.get(exc.code, (502, "unavailable"))[1]}
        )
    money.invalidate(app, subject)
    return _app_redirect(request, {"status": "ok", "provider": "monzo", "session": state})


@router.get("/v1/bank/summary", tags=["bank"], response_model=BankSummary, response_model_exclude_none=True)
async def get_bank_summary(
    request: Request, session: Annotated[str, Query(min_length=1, max_length=128)], sub: Subject
) -> BankSummary:
    """Profile from the caller's own snapshot (live when connected). The session id only has to be present."""
    app = get_state(request)
    snap = await money.snapshot(app, sub)
    profile, _ = await call_pure(money.engine_profile, sub, snap)
    return BankSummary(
        status=snap.status,
        provider="monzo" if "monzo" in snap.source else snap.source,
        profile=profile,
        accounts=len(snap.accounts),
    )


@router.post(
    "/v1/purchases/verify", tags=["store"], response_model=PurchaseVerifyResponse, response_model_exclude_none=True
)
async def verify_purchase(body: PurchaseVerifyRequest, sub: Subject) -> PurchaseVerifyResponse:
    raise not_implemented("Purchases")
