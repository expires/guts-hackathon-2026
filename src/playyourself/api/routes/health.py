import asyncio
import time

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from playyourself.adapters.aggregator import effective_modes
from playyourself.adapters.base import FinanceAdapter, SourceHealth
from playyourself.adapters.credentials import CredentialStore
from playyourself.api.deps import get_adapters, get_credential_store
from playyourself.api.envelope import Envelope, ok
from playyourself.settings import Settings, get_settings

router = APIRouter(tags=["health"])


class HealthData(BaseModel):
    mode: dict[str, str]
    sources: list[SourceHealth]


async def check_health(adapter: FinanceAdapter, timeout_s: float) -> SourceHealth:
    start = time.perf_counter()
    try:
        return await asyncio.wait_for(adapter.health(), timeout_s)
    except Exception as exc:
        return SourceHealth(
            name=adapter.name,
            ok=False,
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
            detail=type(exc).__name__,
        )


@router.get("/health", response_model=Envelope[HealthData])
async def health(
    request: Request,
    settings: Settings = Depends(get_settings),
    adapters: list[FinanceAdapter] = Depends(get_adapters),
    store: CredentialStore = Depends(get_credential_store),
):
    """Per-source health and whether each source runs in mock or live mode."""
    checks = await asyncio.gather(
        *(check_health(a, settings.source_timeout_seconds) for a in adapters)
    )
    mode = {
        k: "live" if v == "live" else "mock" for k, v in effective_modes(settings, store).items()
    }
    return ok(HealthData(mode=mode, sources=list(checks)), request=request)
