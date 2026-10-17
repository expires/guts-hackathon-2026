"""GET /v1/health, GET /v1/sources."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Request

from lifeline_api.state import get_state
from lifeline_contracts.api_models import Health, SourcesResponse
from lifeline_contracts.brand import PRODUCT_NAME

router = APIRouter(tags=["meta"])

Check = Literal["ok", "down", "skipped"]


@router.get("/v1/health", response_model=Health, response_model_exclude_none=True)
async def get_health(request: Request) -> Health:
    state = get_state(request)
    checks: dict[str, Check] = {}
    if state.settings.is_test:
        checks = {"postgres": "skipped", "redis": "skipped"}
    else:
        if state.settings.database_url:
            checks["postgres"] = "ok" if await state.store.ping() else "down"
        else:
            checks["postgres"] = "skipped"
        if state.redis is not None:
            try:
                checks["redis"] = "ok" if await state.redis.ping() else "down"
            except Exception:
                checks["redis"] = "down"
        else:
            checks["redis"] = "skipped"
    status: Literal["ok", "degraded"] = "degraded" if "down" in checks.values() else "ok"
    extra: dict[str, bool] = {}
    if "warming" in Health.model_fields:  # readiness, never a failed health check (V1)
        extra["warming"] = state.warming
    return Health(
        **extra,
        status=status,
        version=state.settings.version,
        product=PRODUCT_NAME,
        time=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        checks=checks,
    )


@router.get("/v1/sources", response_model=SourcesResponse, response_model_exclude_none=True)
async def list_sources(request: Request) -> SourcesResponse:
    state = get_state(request)
    return SourcesResponse(sources=await state.hub.statuses())
