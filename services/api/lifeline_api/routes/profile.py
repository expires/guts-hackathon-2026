"""Your profile: what is connected and the stats it supports. Per subject (the JWT `sub`)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from lifeline_api import money, profile_stats
from lifeline_api.auth import Subject
from lifeline_api.sim_bridge import call_pure
from lifeline_api.state import get_state
from lifeline_contracts.profile import ProfileStats

router = APIRouter(tags=["profile"])


@router.get("/v1/profile/stats", response_model=ProfileStats, response_model_exclude_none=True)
async def get_profile_stats(request: Request, sub: Subject) -> ProfileStats:
    """Connections per source and the stats sections. Never 409: with nothing connected every section says what
    to connect."""
    state = get_state(request)
    hub: Any = state.hub
    snap = await money.maybe_snapshot(state, sub)
    stored = await money.stored_snapshot(state, sub)
    providers = (await hub.connections(sub)).providers
    return await call_pure(profile_stats.build, snap, stored, providers)
