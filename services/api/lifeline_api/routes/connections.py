"""Connected accounts (Monzo, Trading212). Everything is per subject (the JWT `sub`).

Tokens, keys and secrets are stored server-side by the data layer and are never returned: clients only see
a masked hint such as "...a1b2". ProviderError is mapped to HTTP by `errors.provider_error_to_api`.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Request

from lifeline_api import money
from lifeline_api.auth import Subject
from lifeline_api.state import get_state
from lifeline_contracts.accounts import (
    ConnectionsResponse,
    HistoryStatus,
    MonzoTokenRequest,
    ProviderConnection,
    Trading212ConnectRequest,
)

router = APIRouter(tags=["connections"])


def _hub(request: Request) -> Any:
    # The shared DataHub Protocol does not list the connection methods yet (see money.snapshot).
    return get_state(request).hub


@router.get("/v1/connections", response_model=ConnectionsResponse, response_model_exclude_none=True)
async def list_connections(request: Request, sub: Subject) -> ConnectionsResponse:
    result: ConnectionsResponse = await _hub(request).connections(sub)
    return result


@router.post("/v1/connections/trading212", response_model=ProviderConnection, response_model_exclude_none=True)
async def connect_trading212(body: Trading212ConnectRequest, request: Request, sub: Subject) -> ProviderConnection:
    """Checks the key with Trading212 first. Nothing is stored when the check fails."""
    conn: ProviderConnection = await _hub(request).connect_trading212(sub, body.api_key, body.api_secret)
    money.invalidate(get_state(request), sub)
    return conn


@router.post("/v1/connections/monzo/token", response_model=ProviderConnection, response_model_exclude_none=True)
async def connect_monzo_token(body: MonzoTokenRequest, request: Request, sub: Subject) -> ProviderConnection:
    """Dev convenience: a Monzo playground access token instead of the sign-in flow."""
    conn: ProviderConnection = await _hub(request).connect_monzo_token(sub, body.access_token)
    money.invalidate(get_state(request), sub)
    return conn


@router.post("/v1/connections/monzo/sync", response_model=HistoryStatus, response_model_exclude_none=True)
async def sync_monzo(request: Request, sub: Subject) -> HistoryStatus:
    """Retry the history import. Monzo refuses until the user approves access in the Monzo app."""
    status: HistoryStatus = await _hub(request).monzo_sync(sub)
    money.invalidate(get_state(request), sub)
    return status


@router.delete("/v1/connections/{provider}", response_model=ConnectionsResponse, response_model_exclude_none=True)
async def disconnect(provider: Literal["monzo", "trading212"], request: Request, sub: Subject) -> ConnectionsResponse:
    hub = _hub(request)
    await hub.disconnect(sub, provider)
    money.invalidate(get_state(request), sub)
    result: ConnectionsResponse = await hub.connections(sub)
    return result
