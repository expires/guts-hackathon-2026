"""Ask Penny (POST /v1/chat, POST /v1/chat/stream), chat threads, news and rate-decision dates."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import StreamingResponse

from lifeline_api import account, chat_service
from lifeline_api.auth import Subject
from lifeline_api.errors import ApiError, not_found
from lifeline_api.state import get_state
from lifeline_contracts.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamEvent,
    ChatThread,
    ChatThreadsResponse,
    NewsResponse,
    RateDecisions,
)
from lifeline_explain import chat as penny

log = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

ThreadId = Annotated[str, Path(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")]
Topic = Literal["rates", "mortgages", "housing", "inflation", "energy", "jobs", "markets", "economy"]
MAX_NEWS_DAYS = 366


async def _open(request: Request, sub: str, body: ChatRequest) -> tuple[Any, ...]:
    """Fast checks before any answer: rate limit, thread ownership, the life in the context. Raises 4xx."""
    state = get_state(request)
    await chat_service.rate_limit(state, sub)
    thread = await chat_service.open_thread(state, sub, body)
    life = await chat_service.context_life(state, sub, body)
    user_mid = chat_service.add_user_message(thread, body)
    return state, thread, life, user_mid


async def _context(state: Any, sub: str, body: ChatRequest, thread: dict[str, Any], life: Any,
                   user_mid: str) -> tuple[Any, str]:
    acct = await account.ensure(state, sub)
    return await chat_service.build_context(state, sub, body, thread, user_mid, acct.get("display_name"), life)


@router.post("/v1/chat", response_model=ChatResponse, response_model_exclude_none=True)
async def ask_penny(body: ChatRequest, request: Request, sub: Subject) -> ChatResponse:
    state, thread, life, user_mid = await _open(request, sub, body)
    try:
        ctx, digest = await _context(state, sub, body, thread, life, user_mid)
    except Exception as exc:
        log.warning("chat: context failed (%s)", type(exc).__name__)
        resp = chat_service.unavailable_response(thread, user_mid)
    else:
        resp = await penny.answer(body, ctx)
        await chat_service.store_tool_lives(state, sub, ctx, digest)
    chat_service.add_penny_message(thread, resp)
    await chat_service.save_thread(state, sub, thread)
    return resp


KEEPALIVE_SECONDS = 2.0


@router.post("/v1/chat/stream")
async def ask_penny_stream(body: ChatRequest, request: Request, sub: Subject) -> StreamingResponse:
    """Server-Sent Events: `data: <ChatStreamEvent JSON>` per event. Order: reaction, keepalive*, tool_step*,
    verifying?, bubble+, done (ADR 0051).

    The reaction goes out first, before the tool context is built, so it arrives within a second. While the
    context is built a `keepalive` goes out every 2 s. If the context cannot be built: `error` with code
    "unavailable", then `done` with "Penny is unavailable right now. Try again." The thread is stored on `done`.
    POST /v1/chat is the fallback.
    """
    state, thread, life, user_mid = await _open(request, sub, body)
    t0 = time.monotonic()
    seq = 0

    def own(type_: str, **kw: Any) -> str:
        nonlocal seq
        ev = ChatStreamEvent(type=type_, seq=seq, elapsed_ms=int((time.monotonic() - t0) * 1000), **kw)
        seq += 1
        return f"data: {ev.model_dump_json(exclude_none=True)}\n\n"

    async def finish(resp: ChatResponse) -> None:
        chat_service.add_penny_message(thread, resp)
        await chat_service.save_thread(state, sub, thread)

    async def events() -> AsyncIterator[str]:
        nonlocal seq
        yield own("reaction", reaction=penny.quick_reaction(body))
        task = asyncio.ensure_future(_context(state, sub, body, thread, life, user_mid))
        while True:
            done, _ = await asyncio.wait({task}, timeout=KEEPALIVE_SECONDS)
            if done:
                break
            yield own("keepalive")
        try:
            ctx, digest = task.result()
        except Exception as exc:
            log.warning("chat stream: context failed (%s)", type(exc).__name__)
            resp = chat_service.unavailable_response(thread, user_mid)
            yield own("error", error_code="unavailable")
            await finish(resp)
            yield own("done", response=resp)
            return
        ev: ChatStreamEvent
        async for ev in penny.answer_stream(body, ctx):
            if ev.type == "reaction":
                continue  # already sent
            if ev.type == "done" and ev.response is not None:
                await chat_service.store_tool_lives(state, sub, ctx, digest)
                await finish(ev.response)
            ev = ev.model_copy(update={"seq": seq, "elapsed_ms": int((time.monotonic() - t0) * 1000)})
            seq += 1
            yield f"data: {ev.model_dump_json(exclude_none=True)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/v1/chat/threads", response_model=ChatThreadsResponse, response_model_exclude_none=True)
async def list_chat_threads(request: Request, sub: Subject) -> ChatThreadsResponse:
    return await chat_service.list_threads(get_state(request), sub)


@router.get("/v1/chat/threads/{id}", response_model=ChatThread, response_model_exclude_none=True)
async def get_chat_thread(id: ThreadId, request: Request, sub: Subject) -> ChatThread:  # noqa: A002
    thread = await chat_service.load_thread(get_state(request), sub, id)
    if thread is None:
        raise not_found("Chat thread not found")
    return chat_service.thread_view(thread)


@router.get("/v1/news", tags=["news"], response_model=NewsResponse, response_model_exclude_none=True)
async def list_news(
    request: Request,
    sub: Subject,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
    topic: Annotated[Topic | None, Query()] = None,
) -> NewsResponse:
    """Guardian headlines (W1). Never mock: `status: unavailable` with no items when the source is down."""
    if to < from_:
        raise ApiError(422, "validation_error", "to: must be on or after from")
    if (to - from_).days > MAX_NEWS_DAYS:
        raise ApiError(422, "validation_error", f"Pick a range of at most {MAX_NEWS_DAYS} days")
    hub: Any = get_state(request).hub
    result: NewsResponse = await hub.news(from_, to, topic or "rates")
    return result


@router.get("/v1/rate-decisions", tags=["news"], response_model=RateDecisions, response_model_exclude_none=True)
async def get_rate_decisions(request: Request, sub: Subject) -> RateDecisions:
    """Bank of England rate-decision dates (W1). Never mock."""
    hub: Any = get_state(request).hub
    result: RateDecisions = await hub.rate_decisions()
    return result
