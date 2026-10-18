"""Live trace mode for the judges' demo: the last 50 Penny answers and their steps, pushed to SSE subscribers.

On only when PENNY_TRACE_ENABLED is set. The routes in `routes/chat.py` give each real chat request a `Recorder`
and call `publish` when the answer is done. `GET /v1/chat/trace/live` streams each new trace.

One process (the Dockerfile runs uvicorn without --workers), so the buffer lives in memory.
Never stored: tokens, account ids, headers, keys, the system prompt or raw model messages.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import os
from collections import deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from lifeline_contracts.chat import ChatRequest, ChatResponse, ChatTrace
from lifeline_explain.trace import Recorder

MAX_TRACES = 50
QUEUE_SIZE = 100
KEEPALIVE_SECONDS = 15.0
TOKEN_ENV = "PENNY_TRACE_TOKEN"  # noqa: S105 (the env var name, not a value)

_buffer: deque[dict[str, Any]] = deque(maxlen=MAX_TRACES)
_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()


def token() -> str:
    return os.environ.get(TOKEN_ENV, "").strip()


def token_ok(authorization: str | None) -> bool:
    """True when the header is exactly `Bearer <PENNY_TRACE_TOKEN>`. Constant-time compare."""
    expected = token()
    if not expected or not authorization:
        return False
    scheme, _, given = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return False
    return hmac.compare_digest(given.strip().encode(), expected.encode())


def screen_of(body: ChatRequest) -> str:
    """The screen the question came from. No context means the Penny tab."""
    ctx = body.context
    if ctx is None or ctx.screen is None:
        return "penny_tab"
    return str(ctx.screen)


def build(rec: Recorder, body: ChatRequest, resp: ChatResponse, student: str | None, total_ms: int,
          screen: str | None = None) -> dict[str, Any]:  # fmt: skip
    """One live trace: the ChatTrace JSON plus screen, student and time."""
    trace = ChatTrace(question=body.message, student=student, steps=rec.steps, answer=resp, total_ms=total_ms)
    item: dict[str, Any] = trace.model_dump(mode="json", exclude_none=True)
    item["screen"] = screen or screen_of(body)
    item["student"] = student or "a student"
    item["time"] = datetime.now(UTC).isoformat(timespec="seconds")
    return item


def publish(item: dict[str, Any]) -> None:
    """Keep the trace and send it to every subscriber. A full subscriber queue drops the trace for that one."""
    _buffer.append(item)
    for q in list(_subscribers):
        with contextlib.suppress(asyncio.QueueFull):
            q.put_nowait(item)


def recent(n: int) -> list[dict[str, Any]]:
    if n <= 0:
        return []
    return list(_buffer)[-n:]


def subscribe() -> asyncio.Queue[dict[str, Any]]:
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_SIZE)
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue[dict[str, Any]]) -> None:
    _subscribers.discard(q)


def clear() -> None:
    """Tests only."""
    _buffer.clear()
    _subscribers.clear()


def sse(item: dict[str, Any]) -> str:
    return f"event: trace\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"


async def events(last: int = 0, keepalive: float = KEEPALIVE_SECONDS,
                 q: asyncio.Queue[dict[str, Any]] | None = None) -> AsyncIterator[str]:  # fmt: skip
    """SSE text: the last `last` traces, then each new one; a comment line every `keepalive` seconds.
    Subscribes on the first read and unsubscribes when the client goes away."""
    if q is None:
        q = subscribe()
    try:
        yield ": connected\n\n"
        for item in recent(last):
            yield sse(item)
        while True:
            try:
                item = await asyncio.wait_for(q.get(), timeout=keepalive)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            yield sse(item)
    finally:
        unsubscribe(q)
