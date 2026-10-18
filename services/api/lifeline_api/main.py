"""FastAPI app. `uvicorn lifeline_api.main:app`.

APP_ENV=test: in-memory lives store, fakeredis, data hub offline (mock and fixture data, no network).
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.types import Scope

from lifeline_api import logsafe, macro
from lifeline_api.apple import AppleVerifier
from lifeline_api.auth import bearer_subject
from lifeline_api.bodylimit import BodySizeLimitMiddleware
from lifeline_api.errors import CatchAllMiddleware, error_response, install_error_handlers
from lifeline_api.ratelimit import Limiter, MemoryBucket, RateLimitMiddleware, RedisBucket
from lifeline_api.rooms import RoomHub, RoomsUnavailable
from lifeline_api.routes import (
    account,
    auth,
    chat,
    circles,
    course,
    finance,
    later,
    learn,
    lives,
    meta,
    next_move,
    rooms,
)
from lifeline_api.settings import Settings
from lifeline_api.state import AppState
from lifeline_api.store import LifeStore, MemoryLifeStore, PostgresLifeStore
from lifeline_contracts.brand import PRODUCT_NAME
from lifeline_contracts.interfaces import DataHub
from lifeline_data.hub import DataHub as DataHubImpl
from lifeline_explain import api as explain_api

log = logging.getLogger("lifeline_api")

MAX_BODY_BYTES = 64 * 1024
MAX_STATEMENT_BYTES = 5 * 1024 * 1024


def _redis_client(settings: Settings) -> Any | None:
    if settings.is_test:
        import fakeredis  # dev dependency; only used in test mode

        # A fresh server per app start: no limiter or room state leaks between tests (fakeredis instances
        # created with default arguments share one server).
        return fakeredis.FakeAsyncRedis(server=fakeredis.FakeServer())
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


def _bucket(per_minute: int, redis: Any | None) -> Limiter:
    fallback = MemoryBucket(per_minute)
    return fallback if redis is None else RedisBucket(redis, per_minute, fallback)


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
        apple=AppleVerifier(settings.apple_bundle_id, offline=settings.is_test),
        rooms=RoomHub(redis),
        chat_limiter=_bucket(settings.chat_rate_limit_per_minute, redis),  # keys "chat:<subject>"
        read_limiter=_bucket(settings.read_rate_limit_per_minute, redis),  # keys "read:<subject>"
        ip_limiter=_bucket(settings.ip_rate_limit_per_minute, redis),  # keys "ip:<addr>"
        auth_limiter=_bucket(settings.auth_rate_limit_per_minute, redis),  # keys "auth:<ip>"
    )


async def _warm_up(state: AppState) -> None:
    """After a deploy, make the first requests fast: build the MacroTable, then import and build the chat
    stack (LLM client, Penny, engine tools) once. Never fails startup."""
    state.warming = True
    try:
        table = await macro.table(state)
        await asyncio.to_thread(_warm_chat, table)
        log.info("warm-up done")
    except Exception as exc:
        log.warning("warm-up skipped: %s", type(exc).__name__)
    finally:
        state.warming = False


def _warm_chat(table: Any) -> None:
    from datetime import UTC, datetime

    from lifeline_api.chat_service import no_data_snapshot
    from lifeline_explain import chat as penny
    from lifeline_explain.chat_engine_tools import EngineToolSet

    penny.get_penny()  # imports the Anthropic SDK and builds the client once
    tools = EngineToolSet(no_data_snapshot(datetime.now(UTC).date()), table, datetime.now(UTC).date())
    tools.specs()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state = build_state(Settings())
    try:
        await state.store.start()
    except Exception as exc:
        # Keep serving; /v1/health reports postgres as down and the store retries on first use.
        log.error("lives store did not start: %s", type(exc).__name__)
    app.state.lifeline = state
    watchdog = rooms.start_watchdog(state)
    warm: asyncio.Task[Any] | None = None
    if not state.settings.is_test:
        # Build the MacroTable in the background so the first life or room start does not wait for it.
        warm = asyncio.create_task(_warm_up(state))
    try:
        yield
    finally:
        if warm is not None and not warm.done():
            warm.cancel()
        watchdog.cancel()
        for task in list(state.games):
            task.cancel()
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


async def _rooms_unavailable(_: Request, exc: Exception) -> JSONResponse:
    """Redis down for rooms (V3 F2): 503 in the shared error format."""
    return error_response(503, "rooms_unavailable", "Play with friends is unavailable right now. Try again shortly.",
                          "rooms", {"Retry-After": "10"})


def create_app() -> FastAPI:
    logsafe.install()
    app = FastAPI(
        title=f"{PRODUCT_NAME} API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )
    install_error_handlers(app)
    app.add_exception_handler(RoomsUnavailable, _rooms_unavailable)
    for r in (meta.router, auth.router, lives.router, finance.router, next_move.router, learn.router, account.router,
              chat.router, rooms.router, circles.router, course.router,
              later.router):
        app.include_router(r)
    # Order: last added runs first. Outermost: catch-all, then body limit, then rate limit.
    app.add_middleware(RateLimitMiddleware, subject_of=_subject_from_scope)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BODY_BYTES,
                       path_limits={"/v1/finance/statements": MAX_STATEMENT_BYTES})
    app.add_middleware(CatchAllMiddleware)
    return app


app = create_app()
