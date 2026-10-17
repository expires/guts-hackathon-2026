"""Connect real accounts: Monzo OAuth, Monzo playground token paste, Trading212 key paste.

Credentials are validated with the live adapter's health() BEFORE they are stored. No response
from this module ever contains a secret; only a masked hint is returned.

CSRF mitigation for state-changing routes (see `require_local_origin`): POST bodies must be
`Content-Type: application/json`, which makes browsers send a CORS preflight for cross-origin
requests, and we configure no CORS, so the preflight fails. Requests carrying an Origin header
that is not this server's own origin are rejected outright. The OAuth callback is protected by
its single-use `state` instead.
"""

import asyncio
from typing import Literal
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field, field_validator

from playyourself.adapters import monzo_oauth
from playyourself.adapters.aggregator import effective_modes
from playyourself.adapters.base import FinanceAdapter, SourceError, SourceHealth
from playyourself.adapters.credentials import SOURCES, CredentialStore
from playyourself.adapters.monzo import MonzoAdapter
from playyourself.adapters.monzo_history import MonzoHistory
from playyourself.adapters.monzo_oauth import OAuthStateStore
from playyourself.adapters.trading212 import Trading212Adapter
from playyourself.api.deps import (
    get_adapters,
    get_credential_store,
    get_http_client,
    get_oauth_states,
)
from playyourself.api.envelope import Envelope, error_response, ok
from playyourself.api.routes.health import check_health
from playyourself.settings import Settings, get_settings

router = APIRouter(prefix="/connect", tags=["connect"])

CONNECTIONS_FRAGMENT = "/#connections"


def require_local_origin(request: Request) -> None:
    """CSRF guard: reject foreign Origin headers; require JSON bodies on POST (see module doc)."""
    origin = request.headers.get("origin")
    if origin is not None and origin != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "Cross-origin request rejected")
    if request.method == "POST":
        ctype = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise HTTPException(415, "Content-Type must be application/json")


class HistoryStatus(BaseModel):
    """Monzo history import state. Counts and dates only, never amounts."""

    synced: bool
    oldest: str | None = None  # YYYY-MM-DD
    count: int = 0
    last_error: str | None = None


class SourceConnection(BaseModel):
    mode: Literal["demo", "live"]
    connected: bool
    hint: str | None = None  # masked, e.g. "…a1b2"
    remembered: bool = False
    oauth_available: bool = False
    health: SourceHealth | None = None
    history: HistoryStatus | None = None  # monzo only


class ConnectStatus(BaseModel):
    sources: dict[str, SourceConnection]


class MonzoTokenIn(BaseModel):
    access_token: str = Field(min_length=1, max_length=4096)
    remember: bool = False

    @field_validator("access_token")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class Trading212In(BaseModel):
    api_key: str = Field(min_length=1, max_length=4096)
    # Trading212 issues keys as a key + secret pair used together for Basic auth
    # (verified against docs.trading212.com, Oct 2026), so both are required.
    api_secret: str = Field(min_length=1, max_length=4096)
    remember: bool = False

    @field_validator("api_key", "api_secret")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


def _connection(
    source: str,
    settings: Settings,
    store: CredentialStore,
    health: SourceHealth | None = None,
) -> SourceConnection:
    st = store.status(source)
    return SourceConnection(
        mode=effective_modes(settings, store)[source],  # type: ignore[arg-type]
        connected=st.connected,
        hint=st.hint,
        remembered=st.remembered,
        oauth_available=source == "monzo" and monzo_oauth.is_configured(settings),
        health=health,
        history=(
            HistoryStatus(**MonzoHistory(settings.credentials_dir).status())
            if source == "monzo"
            else None
        ),
    )


def _clear_live_cache(settings: Settings, source: str) -> None:
    (settings.cache_dir / f"{source}-live.json").unlink(missing_ok=True)


async def _validate(adapter: FinanceAdapter, timeout_s: float) -> None:
    """Raise SourceError (with the real code) if the adapter's health() is not ok."""
    try:
        h = await asyncio.wait_for(adapter.health(), timeout_s)
    except TimeoutError as exc:
        raise SourceError("timeout", "the provider did not respond in time") from exc
    if not h.ok:
        raise SourceError(h.error_code or "unavailable", "the provider rejected the request")


async def _import_history(settings: Settings, client: httpx.AsyncClient | None, token: str) -> None:
    """Full history import inside Monzo's 5-minute window. A failure keeps the connection and is
    recorded in the history status."""
    # No wipe here: a reconnect outside the 5-minute window only gets 90 days, so wiping would
    # lose older history for good. merge() starts a fresh store if the account id differs, so
    # a different user never inherits someone else's history. Disconnect deletes it.
    history = MonzoHistory(settings.credentials_dir)
    await MonzoAdapter(settings, client, token=token, history=history).full_sync()


@router.get("/status", response_model=Envelope[ConnectStatus])
async def status(
    request: Request,
    settings: Settings = Depends(get_settings),
    store: CredentialStore = Depends(get_credential_store),
    adapters: list[FinanceAdapter] = Depends(get_adapters),
):
    """Per source: effective mode, masked credential hint and the latest health result."""
    checks = await asyncio.gather(
        *(check_health(a, settings.source_timeout_seconds) for a in adapters)
    )
    by_name = {c.name: c for c in checks}
    data = ConnectStatus(
        sources={s: _connection(s, settings, store, by_name.get(s)) for s in SOURCES}
    )
    return ok(data, request=request)


@router.post(
    "/monzo/token",
    response_model=Envelope[SourceConnection],
    dependencies=[Depends(require_local_origin)],
)
async def connect_monzo_token(
    body: MonzoTokenIn,
    request: Request,
    settings: Settings = Depends(get_settings),
    store: CredentialStore = Depends(get_credential_store),
    client: httpx.AsyncClient | None = Depends(get_http_client),
):
    """Paste a Monzo playground access token. Validated before it is stored."""
    await _validate(
        MonzoAdapter(settings, client, token=body.access_token), settings.source_timeout_seconds
    )
    store.set("monzo", {"access_token": body.access_token}, remember=body.remember)
    _clear_live_cache(settings, "monzo")
    await _import_history(settings, client, body.access_token)
    return ok(_connection("monzo", settings, store), request=request)


@router.post(
    "/monzo/sync",
    response_model=Envelope[SourceConnection],
    dependencies=[Depends(require_local_origin)],
)
async def sync_monzo_history(
    request: Request,
    settings: Settings = Depends(get_settings),
    store: CredentialStore = Depends(get_credential_store),
    client: httpx.AsyncClient | None = Depends(get_http_client),
):
    """Retry the full history import with the stored token. Monzo returns 403 for data until
    the user approves access in the Monzo app, which usually happens just after connecting, so
    the import run at connect time can fail; the UI retries here once they've approved."""
    creds = store.get("monzo")
    if not creds or not creds.get("access_token"):
        raise HTTPException(409, "Monzo is not connected")
    await _import_history(settings, client, creds["access_token"])
    _clear_live_cache(settings, "monzo")
    return ok(_connection("monzo", settings, store), request=request)


@router.post(
    "/trading212",
    response_model=Envelope[SourceConnection],
    dependencies=[Depends(require_local_origin)],
)
async def connect_trading212(
    body: Trading212In,
    request: Request,
    settings: Settings = Depends(get_settings),
    store: CredentialStore = Depends(get_credential_store),
    client: httpx.AsyncClient | None = Depends(get_http_client),
):
    """Paste a Trading212 API key (and optional secret). Validated before it is stored."""
    await _validate(
        Trading212Adapter(settings, client, api_key=body.api_key, api_secret=body.api_secret),
        settings.source_timeout_seconds,
    )
    store.set(
        "trading212",
        {"api_key": body.api_key, "api_secret": body.api_secret},
        remember=body.remember,
    )
    _clear_live_cache(settings, "trading212")
    return ok(_connection("trading212", settings, store), request=request)


@router.delete(
    "/{source}",
    response_model=Envelope[SourceConnection],
    dependencies=[Depends(require_local_origin)],
)
async def disconnect(
    source: Literal["monzo", "trading212"],
    request: Request,
    settings: Settings = Depends(get_settings),
    store: CredentialStore = Depends(get_credential_store),
):
    """Forget stored credentials (memory and disk) and revert this source to demo data."""
    store.forget(source)
    _clear_live_cache(settings, source)
    return ok(_connection(source, settings, store), request=request)


# ---- Monzo OAuth ------------------------------------------------------------------------
@router.get("/monzo/start", include_in_schema=True)
async def monzo_start(
    request: Request,
    remember: bool = False,
    settings: Settings = Depends(get_settings),
    states: OAuthStateStore = Depends(get_oauth_states),
) -> Response:
    """Redirect to Monzo's authorisation page. Needs MONZO_CLIENT_ID."""
    if not monzo_oauth.is_configured(settings):
        return error_response(
            request, 400, "not_configured", "MONZO_CLIENT_ID is not configured on the server"
        )
    return RedirectResponse(
        monzo_oauth.authorize_url(settings, states.issue(remember)), status_code=302
    )


def _back(**params: str) -> RedirectResponse:
    return RedirectResponse(f"{CONNECTIONS_FRAGMENT}?{urlencode(params)}", status_code=302)


@router.get("/monzo/callback")
async def monzo_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    settings: Settings = Depends(get_settings),
    store: CredentialStore = Depends(get_credential_store),
    states: OAuthStateStore = Depends(get_oauth_states),
    client: httpx.AsyncClient | None = Depends(get_http_client),
) -> Response:
    """Validate the single-use state, exchange the code, store tokens, return to the UI."""
    pending = states.consume(state)
    if pending is None:
        return _back(monzo="error", code="invalid_state")
    if error or not code:
        return _back(monzo="error", code="denied")
    try:
        creds = await monzo_oauth.exchange_code(settings, code, client)
    except SourceError as exc:
        return _back(monzo="error", code=exc.code)
    store.set("monzo", creds, remember=pending.remember)
    _clear_live_cache(settings, "monzo")
    await _import_history(settings, client, creds["access_token"])
    return _back(monzo="connected")
