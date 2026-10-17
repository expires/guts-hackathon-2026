"""FastAPI app. `uvicorn lifeline_api.main:app`.

APP_ENV=test: in-memory lives store, fakeredis, data hub offline (mock and fixture data, no network).
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from starlette.requests import Request
from starlette.types import Scope

from lifeline_api.auth import bearer_subject
from lifeline_api.bodylimit import BodySizeLimitMiddleware
from lifeline_api.errors import CatchAllMiddleware, install_error_handlers
from lifeline_api.ratelimit import Limiter, MemoryBucket, RateLimitMiddleware, RedisBucket
from lifeline_api.routes import auth, connections, finance, friends, investing, later, learn, lives, meta, next_move
from lifeline_api.settings import ENV_FILES, Settings
from lifeline_api.social import SocialStore
from lifeline_api.state import AppState
from lifeline_api.store import LifeStore, MemoryLifeStore, PostgresLifeStore
from lifeline_contracts.brand import PRODUCT_NAME
from lifeline_contracts.interfaces import DataHub
from lifeline_data.hub import DataHub as DataHubImpl
from lifeline_explain import api as explain_api

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
    # Adapter keys (COMPANIES_HOUSE_KEY, ...) are read from this mapping: real env wins over .env files.
    env: dict[str, str] | None = None
    if ENV_FILES is not None:
        from dotenv import dotenv_values

        merged: dict[str, str] = {}
        for f in ENV_FILES:
            merged.update({k: v for k, v in dotenv_values(f).items() if v is not None})
        env = {**merged, **os.environ}
    return DataHubImpl(settings, redis=redis, env=env)


def build_state(settings: Settings) -> AppState:
    if settings.is_test:
        # Tests never call the network: the explain layer uses template text only.
        os.environ["LLM_ENABLED"] = "0"
        explain_api.set_explainer(None)
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
        social=SocialStore(Path(settings.credentials_dir) / "social.json"),
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
    routers = (meta, auth, lives, finance, investing, connections, friends, next_move, learn, later)
    for r in (m.router for m in routers):
        app.include_router(r)
    # Order: last added runs first. Outermost: catch-all, then body limit, then rate limit.
    app.add_middleware(RateLimitMiddleware, subject_of=_subject_from_scope)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BODY_BYTES)
    app.add_middleware(CatchAllMiddleware)
    return app


app = create_app()
