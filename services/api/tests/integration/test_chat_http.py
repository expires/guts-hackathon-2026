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
from tests.integration.personas import seed_persona

SEEN: list[ChatToolContext] = []
REQUESTS: list[ChatRequest] = []


def _resp(req: ChatRequest, ctx: ChatToolContext, text: str) -> ChatResponse:
    return ChatResponse(
        thread_id=ctx.thread_id or "", message_id=f"pm_{len(SEEN)}", reply_to=ctx.user_message_id or "",
        reaction="brain", bubbles=[ChatBubble(id="b1", kind="answer", text=text)], confidence=0.9, verified=True,
    )


async def fake_answer(req: ChatRequest, ctx: ChatToolContext) -> ChatResponse:
    SEEN.append(ctx)
    REQUESTS.append(req)
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
    # Threads are per user: someone else's id is unknown to them, so they get a NEW thread of their own...
    assert r.status_code == 200 and r.json()["thread_id"] != tid, "threads are per user"
    # ...and the owner's thread is untouched.
    mine = (await client.get(f"/v1/chat/threads/{tid}", headers=auth)).json()
    assert len(mine["messages"]) == 4
    r = await client.post("/v1/chat", json={"message": "hi", "thread_id": tid, "reply_to": "m_nope"}, headers=auth)
    assert r.status_code == 404


async def test_tool_lives_are_stored_for_the_caller(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "demo-presenter-01")
    await seed_persona("demo-presenter-01")
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


async def _stream(client: httpx.AsyncClient, auth: dict[str, str], message: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async with client.stream("POST", "/v1/chat/stream", json={"message": message}, headers=auth) as r:
        assert r.status_code == 200
        async for line in r.aiter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


async def test_stream_keepalive_while_context_builds(client: httpx.AsyncClient,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from lifeline_api import chat_service

    real = chat_service.build_context

    async def slow(*args: Any, **kw: Any) -> Any:
        await asyncio.sleep(2.3)
        return await real(*args, **kw)

    monkeypatch.setattr(chat_service, "build_context", slow)
    events = await _stream(client, await sign_in(client, "chat-device-0010"), "Why?")
    types = [e["type"] for e in events]
    assert types[0] == "reaction" and types[1] == "keepalive" and types[-1] == "done"
    assert [e["seq"] for e in events] == list(range(len(events)))


async def test_context_failure_is_unavailable_then_done(client: httpx.AsyncClient,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    from lifeline_api import chat_service
    from lifeline_explain.prompts import UNAVAILABLE_TEXT

    async def broken(*args: Any, **kw: Any) -> Any:
        raise RuntimeError("macro table down")

    monkeypatch.setattr(chat_service, "build_context", broken)
    auth = await sign_in(client, "chat-device-0011")
    events = await _stream(client, auth, "Why?")
    assert [e["type"] for e in events] == ["reaction", "error", "done"]
    assert events[1]["error_code"] == "unavailable"
    assert events[2]["response"]["bubbles"][0]["text"] == UNAVAILABLE_TEXT
    r = await client.post("/v1/chat", json={"message": "Why?"}, headers=auth)
    assert r.status_code == 200 and r.json()["bubbles"][0]["text"] == UNAVAILABLE_TEXT
    threads = (await client.get("/v1/chat/threads", headers=auth)).json()["threads"]
    assert len(threads) == 2, "the unavailable answer is stored like any other"


async def test_tools_get_boe_series(client: httpx.AsyncClient) -> None:
    await client.post("/v1/chat", json={"message": "What is the bank rate?"},
                      headers=await sign_in(client, "chat-device-0012"))
    assert SEEN[-1].tools.series is not None, "boe_rates needs hub.series"


async def test_penny_down_uses_no_next_move_and_max_two_bubbles(client: httpx.AsyncClient,
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """Real Penny with the LLM off (test mode): template answer, contract-sized, no next_move tool call."""
    from lifeline_api.routes import chat as chat_routes
    from lifeline_explain import chat as real_penny

    monkeypatch.setattr(chat_routes.penny, "answer", real_penny.Penny.answer.__get__(real_penny.get_penny()))
    monkeypatch.setattr(chat_routes.penny, "answer_stream",
                        real_penny.Penny.answer_stream.__get__(real_penny.get_penny()))
    auth = await sign_in(client, "chat-device-0013")
    body = (await client.post("/v1/chat", json={"message": "Can I afford a night out?"}, headers=auth)).json()
    assert 1 <= len(body["bubbles"]) <= 2
    names = {t["name"] for t in body.get("tool_calls", [])}
    assert "next_move" not in names
    allowed = {"next_move", "test_move", "finance_summary", "spend_prediction", "cash_flow_projection",
               "life_replay", "event_choices", "news_search", "rate_decision_dates", "facts_table",
               "boe_rates", "web_search"}
    assert names <= allowed
    events = await _stream(client, auth, "What is the bank rate?")
    done = events[-1]["response"]
    assert len(done["bubbles"]) <= 2 and "next_move" not in {t["name"] for t in done.get("tool_calls", [])}


async def test_million_yuan_uses_fx_convert(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR 0060: the chat tools get hub.fx_rate and hub.cpi; a currency question calls fx_convert."""
    from datetime import date

    from lifeline_api.main import app
    from lifeline_api.routes import chat as chat_routes
    from lifeline_explain import chat as real_penny
    from lifeline_explain.chat_llm import LLMStep, ToolUse

    class Scripted:
        def __init__(self) -> None:
            self.steps = [
                LLMStep(stop_reason="tool_use", tool_uses=[ToolUse(id="tu1", name="fx_convert", input={
                    "amount": 1_000_000, "from_currency": "CNY", "to_currency": "GBP"})]),
                LLMStep(stop_reason="end_turn", text=json.dumps({
                    "reaction": "brain", "out_of_scope": False, "summary_available": False,
                    "bubbles": [{"kind": "answer", "text": "I converted it at today's reference rate."}]})),
            ]

        async def step(self, system: str, messages: Any, tools: Any, schema: Any) -> LLMStep:
            return self.steps.pop(0)

    async def fx_rate(base: str, quote: str) -> tuple[float, date] | None:
        return (0.1052, date(2026, 10, 16)) if (base, quote) == ("CNY", "GBP") else None

    async def cpi() -> tuple[float, date] | None:
        return (3.8, date(2026, 9, 1))

    hub = app.state.lifeline.hub
    monkeypatch.setattr(hub, "fx_rate", fx_rate)
    monkeypatch.setattr(hub, "cpi", cpi)
    penny_obj = real_penny.Penny(llm=Scripted())
    monkeypatch.setattr(chat_routes.penny, "answer", penny_obj.answer)
    auth = await sign_in(client, "chat-device-0020")
    r = await client.post("/v1/chat", json={"message": "How much is 1 million yuan in pounds?"}, headers=auth)
    assert r.status_code == 200, r.text
    names = [t["name"] for t in r.json()["tool_calls"]]
    assert "fx_convert" in names, r.json()



async def test_language_reaches_penny(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "chat-device-0030")
    r = await client.post("/v1/chat", json={"message": "Bonjour", "language": "fr"}, headers=auth)
    assert r.status_code == 200 and REQUESTS[-1].language == "fr"
    bad = await client.post("/v1/chat", json={"message": "Hi", "language": "de"}, headers=auth)
    assert bad.status_code == 422


async def test_stream_finishes_when_saving_is_down(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """V3 F1: Postgres down at the end of a turn still ends the stream with `done`."""
    from lifeline_api import chat_service
    from lifeline_api.store import StoreUnavailable

    auth = await sign_in(client, "chat-device-0040")

    async def down(*a: Any, **k: Any) -> None:
        raise StoreUnavailable()

    monkeypatch.setattr(chat_service, "save_thread", down)
    events = await _stream(client, auth, "Why?")
    assert events[-1]["type"] == "done" and events[-1]["response"]["bubbles"]
    r = await client.post("/v1/chat", json={"message": "Why?"}, headers=auth)
    assert r.status_code == 200 and r.json()["bubbles"]
