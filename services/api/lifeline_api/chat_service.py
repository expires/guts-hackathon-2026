"""Ask Penny wiring (ADR 0031-0034): builds W5's ChatToolContext for one request, stores threads per user,
and stores any lives the tools created (Test it, life replay) as the caller's lives with a pinned macro table.

Threads are per-user documents `chat:<thread_id>`, so DELETE /v1/me and /v1/me/reset remove them.
"""

from __future__ import annotations

import logging
import math
import secrets
from datetime import UTC, date, datetime
from typing import Any, cast

from lifeline_api import money, prediction
from lifeline_api.errors import ApiError, not_found
from lifeline_api.routes.lives import new_life_id
from lifeline_api.routes.next_move import DOC_NEXT_MOVE, subject_seed
from lifeline_api.state import AppState
from lifeline_api.store import LifeRecord, macro_hash
from lifeline_contracts.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatThread,
    ChatThreadsResponse,
    ChatThreadSummary,
)
from lifeline_contracts.domain import Life
from lifeline_contracts.finance import Account, FinanceSnapshot
from lifeline_contracts.next_move import NextMoveResponse
from lifeline_explain.chat_engine_tools import EngineToolSet
from lifeline_explain.chat_tools import ChatToolContext, ChatTurn

log = logging.getLogger(__name__)

THREAD_PREFIX = "chat:"
HISTORY_TURNS = 12
MAX_MESSAGES_PER_THREAD = 200
TITLE_CHARS = 60


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def rate_limit(state: AppState, sub: str) -> None:
    if state.chat_limiter is None:
        return
    wait = await state.chat_limiter.take(f"chat:{sub}")
    if wait > 0:
        retry = str(max(1, math.ceil(wait)))
        raise ApiError(429, "rate_limited", "Penny needs a moment. Try again shortly.", source="chat",
                       headers={"Retry-After": retry})


# ---------- threads ----------


async def load_thread(state: AppState, sub: str, thread_id: str) -> dict[str, Any] | None:
    doc = await state.store.get_doc(sub, THREAD_PREFIX + thread_id)
    return cast(dict[str, Any] | None, doc)


async def save_thread(state: AppState, sub: str, thread: dict[str, Any]) -> None:
    thread["messages"] = thread["messages"][-MAX_MESSAGES_PER_THREAD:]
    thread["updated_at"] = _now()
    await state.store.put_doc(sub, THREAD_PREFIX + thread["id"], thread)


def _with_reply_counts(messages: list[dict[str, Any]]) -> list[ChatMessage]:
    counts: dict[str, int] = {}
    for m in messages:
        if m["role"] == "user" and m.get("reply_to"):
            counts[m["reply_to"]] = counts.get(m["reply_to"], 0) + 1
    return [ChatMessage.model_validate({**m, "replies": counts.get(m["id"], 0)}) for m in messages]


def thread_view(thread: dict[str, Any]) -> ChatThread:
    return ChatThread(id=thread["id"], title=thread["title"], messages=_with_reply_counts(thread["messages"]))


async def list_threads(state: AppState, sub: str) -> ChatThreadsResponse:
    docs = await state.store.list_docs(sub, THREAD_PREFIX)
    items = [
        ChatThreadSummary(id=d["id"], title=d["title"], updated_at=d["updated_at"], message_count=len(d["messages"]))
        for d in docs.values()
    ]
    return ChatThreadsResponse(threads=sorted(items, key=lambda t: t.updated_at, reverse=True))


async def open_thread(state: AppState, sub: str, req: ChatRequest) -> dict[str, Any]:
    """The request's thread (404 if it is not the caller's), or a new one titled from the first message."""
    if req.thread_id:
        thread = await load_thread(state, sub, req.thread_id)
        if thread is None:
            raise not_found("Chat thread not found")
        if req.reply_to and not any(m["id"] == req.reply_to for m in thread["messages"]):
            raise not_found("Message to reply to not found")
        return thread
    if req.reply_to:
        raise not_found("Message to reply to not found")
    title = " ".join(req.message.split())[:TITLE_CHARS]
    return {"id": f"th_{secrets.token_hex(8)}", "title": title or "Chat", "created_at": _now(),
            "updated_at": _now(), "messages": []}


def add_user_message(thread: dict[str, Any], req: ChatRequest) -> str:
    mid = f"m_{secrets.token_hex(8)}"
    thread["messages"].append({"id": mid, "role": "user", "created_at": _now(), "text": req.message,
                               "reply_to": req.reply_to})
    return mid


def add_penny_message(thread: dict[str, Any], resp: ChatResponse) -> None:
    thread["messages"].append({"id": resp.message_id, "role": "penny", "created_at": _now(),
                               "reply_to": resp.reply_to, "response": resp.model_dump(mode="json")})


def history(thread: dict[str, Any]) -> list[ChatTurn]:
    turns: list[ChatTurn] = []
    for m in thread["messages"][-HISTORY_TURNS:]:
        if m["role"] == "user":
            turns.append(ChatTurn("user", m.get("text") or ""))
        elif m.get("response"):
            r = m["response"]
            text = " ".join(b["text"] for b in r.get("bubbles", []))
            turns.append(ChatTurn("penny", text, tools_used=tuple(t["name"] for t in r.get("tool_calls", []))))
    return turns


# ---------- tool context ----------


def no_data_snapshot(today: date) -> FinanceSnapshot:
    """For a user with no money data (live mode): no accounts, no transactions, status unavailable.
    The tools then report "no data" instead of numbers."""
    return FinanceSnapshot(status="unavailable", source="none", as_of=today.isoformat(), transactions=[],
                           accounts=[Account(id="acc_none", name="No account connected", kind="current",
                                             provider="none", balance=0.0)])


async def _stored_next_move(state: AppState, sub: str) -> NextMoveResponse | None:
    doc = await state.store.get_doc(sub, DOC_NEXT_MOVE)
    if doc is None:
        return None
    return NextMoveResponse.model_validate(doc["response"])


async def context_life(state: AppState, sub: str, req: ChatRequest) -> Life | None:
    """The caller's life named in the request context. 404 if it is not theirs."""
    if req.context is None or not req.context.life_id:
        return None
    rec = await state.store.get(req.context.life_id, sub)
    if rec is None:
        raise not_found("Life not found")
    return rec.life


async def build_context(state: AppState, sub: str, req: ChatRequest, thread: dict[str, Any], user_message_id: str,
                        display_name: str | None, life: Life | None = None) -> tuple[ChatToolContext, str]:
    """W5's ChatToolContext for this caller. Returns the context and the hash of the pinned macro table."""
    snap = await money.maybe_snapshot(state, sub)
    today = money.today(snap) if snap is not None else datetime.now(UTC).date()
    table = await state.hub.macro_table()
    digest = macro_hash(table)
    await state.store.put_macro(digest, table)

    holidays: Any = ()
    weather: Any = None
    if snap is not None:
        try:
            inp = await prediction.inputs(state, sub)
            holidays, weather = inp.holidays, inp.weather
        except Exception as exc:
            log.warning("chat: prediction inputs unavailable (%s)", type(exc).__name__)

    event_id = req.context.event_id if (req.context is not None and life is not None) else None

    hub: Any = state.hub
    tools = EngineToolSet(
        snap if snap is not None else no_data_snapshot(today),
        table,
        today,
        seed=subject_seed(sub),
        next_move_response=await _stored_next_move(state, sub),
        news=hub.news,
        rates=hub.rate_decisions,
        life=life,
        event_id=event_id,
        holidays=holidays,
        weather=weather,
        life_id_prefix="chat",
    )
    ctx = ChatToolContext(
        tools=tools,
        thread_id=thread["id"],
        user_message_id=user_message_id,
        history=history({"messages": thread["messages"][:-1]}),  # earlier turns; the new message is the request
        known={"name": display_name} if display_name else {},
        request_context=req.context,
    )
    return ctx, digest


async def store_tool_lives(state: AppState, sub: str, ctx: ChatToolContext, digest: str) -> list[str]:
    """Lives the tools played (Test it, life replay) become the caller's lives, with the pinned macro table."""
    stored: list[str] = []
    for _, output in ctx.outputs:
        raw = getattr(output, "raw", None)
        for life in getattr(raw, "lives", None) or []:
            if not isinstance(life, Life):
                continue
            life = life.model_copy(update={"id": new_life_id()})
            await state.store.create(LifeRecord(id=life.id, owner=sub, life=life, macro_hash=digest))
            stored.append(life.id)
    return stored
