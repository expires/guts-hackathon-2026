"""FastAPI app. `uvicorn lifeline_api.main:app`.

APP_ENV=test: in-memory lives store, fakeredis, data hub offline (mock and fixture data, no network).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from starlette.requests import Request
from starlette.types import Scope

from lifeline_api.auth import bearer_subject
from lifeline_api.bodylimit import BodySizeLimitMiddleware
from lifeline_api.errors import CatchAllMiddleware, install_error_handlers
from lifeline_api.ratelimit import Limiter, MemoryBucket, RateLimitMiddleware, RedisBucket
from lifeline_api.routes import auth, finance, later, learn, lives, meta, next_move
from lifeline_api.settings import Settings
from lifeline_api.state import AppState
from lifeline_api.store import LifeStore, MemoryLifeStore, PostgresLifeStore
from lifeline_contracts.brand import PRODUCT_NAME
from lifeline_contracts.interfaces import DataHub
from lifeline_data.hub import DataHub as DataHubImpl

log = logging.getLogger("lifeline_api")

MAX_BODY_BYTES = 64 * 1024


def _redis_client(settings: Settings) -> Any | None:
    if settings.is_test:
        import fakeredis  # dev dependency; only used in test mode

        return fakeredis.FakeAsyncRedis()
    if not settings.redis_url:
        return None
    import redis.asyncio as aioredis

    return aioredis.from_url(settings.redis_url, socket_timeout=1.0, socket_connect_timeout=1.0)


def _store(settings: Settings) -> LifeStore:
    if settings.is_test or not settings.database_url:
        if not settings.is_test:
            log.warning("DATABASE_URL is not set; lives are kept in memory only")
        return MemoryLifeStore()
    return PostgresLifeStore(settings.database_url)


def _hub(settings: Settings, redis: Any | None) -> DataHub:
    return DataHubImpl(settings, redis=redis)


def build_state(settings: Settings) -> AppState:
    redis = _redis_client(settings)
    fallback = MemoryBucket(settings.rate_limit_per_minute)
    limiter: Limiter = RedisBucket(redis, settings.rate_limit_per_minute, fallback) if redis is not None else fallback
    return AppState(
        settings=settings,
        store=_store(settings),
        hub=_hub(settings, redis),
        limiter=limiter,
        jwt_secret=settings.signing_secret(),
        redis=redis,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state = build_state(Settings())
    try:
        await state.store.start()
    except Exception as exc:
        # Keep serving; /v1/health reports postgres as down and the store retries on first use.
        log.error("lives store did not start: %s", type(exc).__name__)
    app.state.lifeline = state
    try:
        yield
    finally:
        await state.store.close()
        hub_close = getattr(state.hub, "aclose", None) or getattr(state.hub, "close", None)
        if hub_close is not None:
            res = hub_close()
            if hasattr(res, "__await__"):
                await res
        if state.redis is not None:
            await state.redis.aclose()


def _subject_from_scope(scope: Scope) -> str | None:
    return bearer_subject(Request(scope))


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{PRODUCT_NAME} API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )
    install_error_handlers(app)
    for r in (meta.router, auth.router, lives.router, finance.router, next_move.router, learn.router, later.router):
        app.include_router(r)
    # Order: last added runs first. Outermost: catch-all, then body limit, then rate limit.
    app.add_middleware(RateLimitMiddleware, subject_of=_subject_from_scope)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BODY_BYTES)
    app.add_middleware(CatchAllMiddleware)
    return app


app = create_app()
