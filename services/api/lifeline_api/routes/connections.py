"""Connected accounts (Monzo, Trading212). Everything is per subject (the JWT `sub`).

Tokens, keys and secrets are stored server-side by the data layer and are never returned: clients only see
a masked hint such as "...a1b2". ProviderError is mapped to HTTP by `errors.provider_error_to_api`.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Request

from lifeline_api import money, onboarding
from lifeline_api.auth import Subject
from lifeline_api.state import AppState, get_state
from lifeline_contracts.accounts import (
    ConnectionsResponse,
    HistoryStatus,
    MonzoTokenRequest,
    ProviderConnection,
    Trading212ConnectRequest,
)
from lifeline_data.providers._http import ProviderError

log = logging.getLogger(__name__)
router = APIRouter(tags=["connections"])


async def adopt_live(state: AppState, sub: str) -> None:
    """Make the connected accounts the user's own data, the same way a statement upload does: the live Monzo
    and Trading212 snapshot is merged with what the user entered (age, student, loan, mortgage, logged payments)
    and saved encrypted as their snapshot. Next Move, Money, Circles and the rest then read it with data_status
    live. Sample data is never mixed in: only what the providers returned plus the user's own entries."""
    hub: Any = state.hub
    async with state.subject_locks[f"{sub}:money"]:
        live = await hub.live_snapshot(sub)
        if live is None:
            money.forget(state, sub)
            return
        prev = await money.stored_snapshot(state, sub)
        # Keeps what the user entered; replaces the old statement or sample rows with the live ones.
        await money.save_snapshot(state, sub, onboarding.merge_statement(prev, live))


async def _drop_live(state: AppState, sub: str) -> None:
    """After a disconnect: rebuild from what is still connected, or remove data that came only from the banks."""
    hub: Any = state.hub
    async with state.subject_locks[f"{sub}:money"]:
        live = await hub.live_snapshot(sub)
        prev = await money.stored_snapshot(state, sub)
        if live is not None:
            await money.save_snapshot(state, sub, onboarding.merge_statement(prev, live))
        elif prev is not None and prev.source in ("monzo", "trading212", "monzo+trading212"):
            await money.delete_snapshot(state, sub)
        elif prev is not None and (prev.holdings or any(a.provider == "trading212" for a in prev.accounts)):
            await money.save_snapshot(state, sub, onboarding.without_trading212(prev))
        else:
            money.forget(state, sub)


def _hub(request: Request) -> Any:
    return get_state(request).hub


@router.get("/v1/connections", response_model=ConnectionsResponse, response_model_exclude_none=True)
async def list_connections(request: Request, sub: Subject) -> ConnectionsResponse:
    result: ConnectionsResponse = await _hub(request).connections(sub)
    return result


@router.post("/v1/connections/trading212", response_model=ProviderConnection, response_model_exclude_none=True)
async def connect_trading212(body: Trading212ConnectRequest, request: Request, sub: Subject) -> ProviderConnection:
    """Checks the key with Trading212 first. Nothing is stored when the check fails."""
    conn: ProviderConnection = await _hub(request).connect_trading212(sub, body.api_key, body.api_secret)
    await adopt_live(get_state(request), sub)
    return conn


@router.post("/v1/connections/monzo/token", response_model=ProviderConnection, response_model_exclude_none=True)
async def connect_monzo_token(body: MonzoTokenRequest, request: Request, sub: Subject) -> ProviderConnection:
    """Dev convenience: a Monzo playground access token instead of the sign-in flow."""
    conn: ProviderConnection = await _hub(request).connect_monzo_token(sub, body.access_token)
    await adopt_live(get_state(request), sub)
    return conn


@router.post("/v1/connections/monzo/sync", response_model=HistoryStatus, response_model_exclude_none=True)
async def sync_monzo(request: Request, sub: Subject) -> HistoryStatus:
    """Retry the history import. Monzo refuses until the user approves access in the Monzo app."""
    status: HistoryStatus = await _hub(request).monzo_sync(sub)
    try:
        await adopt_live(get_state(request), sub)
    except ProviderError:
        log.info("live data not adopted yet")
    return status


@router.delete("/v1/connections/{provider}", response_model=ConnectionsResponse, response_model_exclude_none=True)
async def disconnect(provider: Literal["monzo", "trading212"], request: Request, sub: Subject) -> ConnectionsResponse:
    hub = _hub(request)
    await hub.disconnect(sub, provider)
    await _drop_live(get_state(request), sub)
    result: ConnectionsResponse = await hub.connections(sub)
    return result
