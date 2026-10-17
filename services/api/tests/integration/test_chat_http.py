"""Ask Penny wiring: context, threads, stored tool lives, streaming, rate limit (ADR 0031-0034).

Penny herself (W5) is replaced by a fake that calls a real engine tool, so these tests check W4's side only.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from lifeline_contracts.chat import BubbleEvent, ChatBubble, ChatRequest, ChatResponse, ChatStreamEvent
from lifeline_explain.chat_tools import ChatToolContext
from tests.integration.conftest import sign_in

SEEN: list[ChatToolContext] = []


def _resp(req: ChatRequest, ctx: ChatToolContext, text: str) -> ChatResponse:
    return ChatResponse(
        thread_id=ctx.thread_id or "", message_id=f"pm_{len(SEEN)}", reply_to=ctx.user_message_id or "",
        reaction="brain", bubbles=[ChatBubble(id="b1", kind="answer", text=text)], confidence=0.9, verified=True,
    )


async def fake_answer(req: ChatRequest, ctx: ChatToolContext) -> ChatResponse:
    SEEN.append(ctx)
    if "test" in req.message.lower():
        out = await ctx.tools.call("test_move", {"move_id": "top"})
        ctx.outputs.append(("test_move", out))
    return _resp(req, ctx, f"Answer to: {req.message}")


async def fake_stream(req: ChatRequest, ctx: ChatToolContext) -> AsyncIterator[ChatStreamEvent]:
    resp = await fake_answer(req, ctx)
    yield ChatStreamEvent(type="reaction", seq=0, elapsed_ms=1, reaction="brain")
    yield ChatStreamEvent(type="bubble", seq=1, elapsed_ms=2, bubble=BubbleEvent(bubble=resp.bubbles[0]))
    yield ChatStreamEvent(type="done", seq=2, elapsed_ms=3, response=resp)


@pytest.fixture(autouse=True)
def fake_penny(monkeypatch: pytest.MonkeyPatch) -> None:
    from lifeline_api.routes import chat as chat_routes

    SEEN.clear()
    monkeypatch.setattr(chat_routes.penny, "answer", fake_answer)
    monkeypatch.setattr(chat_routes.penny, "answer_stream", fake_stream)


async def test_chat_thread_and_history(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "chat-device-0001")
    r = await client.post("/v1/chat", json={"message": "Why this move?"}, headers=auth)
    assert r.status_code == 200, r.text
    first = r.json()
    tid = first["thread_id"]
    r = await client.post("/v1/chat", json={"message": "Are you sure?", "thread_id": tid,
                                            "reply_to": first["message_id"]}, headers=auth)
    assert r.status_code == 200
    ctx = SEEN[-1]
    assert [t.role for t in ctx.history] == ["user", "penny"] and ctx.history[1].text.startswith("Answer to")
    thread = (await client.get(f"/v1/chat/threads/{tid}", headers=auth)).json()
    assert [m["role"] for m in thread["messages"]] == ["user", "penny", "user", "penny"]
    assert thread["title"] == "Why this move?"
    assert thread["messages"][1]["replies"] == 1, "one question replied to Penny's first answer"
    threads = (await client.get("/v1/chat/threads", headers=auth)).json()["threads"]
    assert [t["id"] for t in threads] == [tid] and threads[0]["message_count"] == 4

    other = await sign_in(client, "chat-device-0002")
    assert (await client.get(f"/v1/chat/threads/{tid}", headers=other)).status_code == 404
    r = await client.post("/v1/chat", json={"message": "hi", "thread_id": tid}, headers=other)
    assert r.status_code == 404, "threads are per user"
    r = await client.post("/v1/chat", json={"message": "hi", "thread_id": tid, "reply_to": "m_nope"}, headers=auth)
    assert r.status_code == 404


async def test_tool_lives_are_stored_for_the_caller(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "demo-presenter-01")
    await client.get("/v1/next-move", headers=auth)
    r = await client.post("/v1/chat", json={"message": "Test the top move"}, headers=auth)
    assert r.status_code == 200
    lives = (await client.get("/v1/lives", headers=auth)).json()["lives"]
    assert len(lives) >= 2, "each Test it option is a life the user can open"
    for item in lives:
        assert item["id"].startswith("lf_")
        assert (await client.get(f"/v1/lives/{item['id']}", headers=auth)).status_code == 200
    assert SEEN[-1].tools.response is not None, "the stored next move is passed to the tools"


async def test_chat_stream_is_sse_and_stores_thread(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "chat-device-0003")
    events: list[dict[str, Any]] = []
    async with client.stream("POST", "/v1/chat/stream", json={"message": "Why?"}, headers=auth) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        assert r.headers["x-accel-buffering"] == "no" and r.headers["cache-control"] == "no-cache"
        async for line in r.aiter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    assert [e["type"] for e in events] == ["reaction", "bubble", "done"], "Penny's own reaction is not repeated"
    assert [e["seq"] for e in events] == [0, 1, 2]
    tid = events[-1]["response"]["thread_id"]
    thread = (await client.get(f"/v1/chat/threads/{tid}", headers=auth)).json()
    assert [m["role"] for m in thread["messages"]] == ["user", "penny"]


async def test_chat_rate_limit_per_user(client: httpx.AsyncClient) -> None:
    from lifeline_api.main import app

    limit = app.state.lifeline.settings.chat_rate_limit_per_minute
    auth = await sign_in(client, "chat-device-0004")
    codes = [(await client.post("/v1/chat", json={"message": "hi"}, headers=auth)).status_code
             for _ in range(limit + 1)]
    assert codes[:limit] == [200] * limit and codes[-1] == 429
    r = await client.post("/v1/chat/stream", json={"message": "hi"}, headers=auth)
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited" and "retry-after" in r.headers
    other = await sign_in(client, "chat-device-0005")
    assert (await client.post("/v1/chat", json={"message": "hi"}, headers=other)).status_code == 200


async def test_threads_are_deleted_with_the_account(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "chat-device-0006")
    await client.post("/v1/chat", json={"message": "hello"}, headers=auth)
    assert (await client.post("/v1/me/reset", headers=auth)).status_code == 200
    assert (await client.get("/v1/chat/threads", headers=auth)).json()["threads"] == []


async def test_news_and_rate_decisions(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "chat-device-0007")
    r = await client.get("/v1/news", params={"from": "2026-10-01", "to": "2026-10-17", "topic": "rates"}, headers=auth)
    assert r.status_code == 200 and r.json()["status"] in ("live", "cached", "unavailable")
    assert r.json()["status"] != "mock"
    r = await client.get("/v1/news", params={"from": "2026-10-17", "to": "2026-10-01"}, headers=auth)
    assert r.status_code == 422
    r = await client.get("/v1/rate-decisions", headers=auth)
    assert r.status_code == 200 and r.json()["status"] != "mock"
