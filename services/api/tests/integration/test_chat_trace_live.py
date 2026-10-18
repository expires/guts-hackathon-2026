"""Live trace mode: GET /v1/chat/trace/live, the in-memory buffer and tools/penny_trace_live.py. No network."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

from lifeline_api import samples, trace_live
from lifeline_explain import chat as penny_mod
from lifeline_explain import prompts
from lifeline_explain.chat import Penny
from tests.integration.conftest import sign_in
from tests.unit.explain.test_chat import SETTINGS, FakeChatLLM, final

TOOLS = Path(__file__).resolve().parents[4] / "tools"
TOKEN = "live-trace-test-token-7f3a9c"
LIBRARY_A = ("The Main Library is open 24 hours a day during term time. A late coffee there adds up, so plan "
             "for it.")  # fmt: skip


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("penny_trace_live", TOOLS / "penny_trace_live.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["penny_trace_live"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def fresh() -> Iterator[None]:
    trace_live.clear()
    yield
    trace_live.clear()
    penny_mod.set_penny(None)


@pytest.fixture
def live_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PENNY_TRACE_ENABLED", "1")
    monkeypatch.setenv("PENNY_TRACE_TOKEN", TOKEN)


def _use(*script: Any) -> None:
    penny_mod.set_penny(Penny(llm=FakeChatLLM(*script), settings=SETTINGS))


async def test_live_is_404_when_the_flag_is_off(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PENNY_TRACE_ENABLED", raising=False)
    monkeypatch.setenv("PENNY_TRACE_TOKEN", TOKEN)
    r = await client.get("/v1/chat/trace/live", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 404 and "error" in r.json()


async def test_live_is_404_when_the_token_env_is_empty(client: httpx.AsyncClient,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    monkeypatch.setenv("PENNY_TRACE_ENABLED", "1")
    monkeypatch.setenv("PENNY_TRACE_TOKEN", "")
    r = await client.get("/v1/chat/trace/live", headers={"Authorization": "Bearer "})
    assert r.status_code == 404


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong-token"}, {"Authorization": TOKEN},
                                     {"Authorization": f"Basic {TOKEN}"}])  # fmt: skip
async def test_live_is_401_without_the_right_token(client: httpx.AsyncClient, live_on: None,
                                                   headers: dict[str, str]) -> None:  # fmt: skip
    r = await client.get("/v1/chat/trace/live", headers=headers)
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"
    assert TOKEN not in r.text


def test_token_check() -> None:
    assert not trace_live.token_ok(f"Bearer {TOKEN}")  # env not set in this test


async def test_live_is_not_in_the_openapi_schema(client: httpx.AsyncClient) -> None:
    r = await client.get("/openapi.json")
    if r.status_code == 200:
        assert "/v1/chat/trace/live" not in r.json().get("paths", {})


async def test_flag_off_records_nothing(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PENNY_TRACE_ENABLED", raising=False)
    _use(final(("general_knowledge", LIBRARY_A)))
    auth = await sign_in(client, "live-off")
    r = await client.post("/v1/chat", json={"message": "How long is the library open?"}, headers=auth)
    assert r.status_code == 200
    assert trace_live.recent(50) == []


async def test_chat_request_lands_one_trace_in_buffer_and_subscriber(client: httpx.AsyncClient,
                                                                     live_on: None) -> None:  # fmt: skip
    _use(final(("general_knowledge", LIBRARY_A)))
    q = trace_live.subscribe()
    auth = await sign_in(client, "live-chat")
    body = {"message": "How long is the library open?", "context": {"screen": "learn_lesson"}}
    r = await client.post("/v1/chat", json=body, headers=auth)
    assert r.status_code == 200
    resp = r.json()
    assert "steps" not in resp and "trace" not in json.dumps(resp)  # the app's answer is unchanged
    items = trace_live.recent(50)
    assert len(items) == 1
    item = items[0]
    assert q.get_nowait() is item and q.empty()
    assert item["screen"] == "learn_lesson" and item["student"] and item["time"]
    assert item["question"] == "How long is the library open?"
    assert [s["kind"] for s in item["steps"]][-1] == "final"
    assert item["answer"]["bubbles"] == resp["bubbles"]
    token = auth["Authorization"].split()[1]
    _no_secrets(json.dumps(item), token)
    out = _tool().show(item)
    _no_secrets(out, token)
    assert "QUESTION" in out and "ANSWER" in out and "learn_lesson" not in out.splitlines()[1]
    assert "lesson" in out.splitlines()[1]


async def test_stream_request_lands_one_trace(client: httpx.AsyncClient, live_on: None) -> None:
    _use(final(("general_knowledge", LIBRARY_A)))
    auth = await sign_in(client, "live-stream")
    r = await client.post("/v1/chat/stream", json={"message": "How long is the library open?"}, headers=auth)
    assert r.status_code == 200 and '"type":"done"' in r.text
    assert "elapsed_ms" in r.text and "tool_result" not in r.text
    items = trace_live.recent(50)
    assert len(items) == 1 and items[0]["screen"] == "penny_tab"
    first = next(s for s in items[0]["steps"] if s["kind"] == "final")["data"]["first_bubble_ms"]
    assert first is not None


async def test_sse_events_send_each_new_trace() -> None:
    q = trace_live.subscribe()
    gen = trace_live.events(last=0, keepalive=0.05, q=q)
    assert await anext(gen) == ": connected\n\n"
    assert await anext(gen) == ": keepalive\n\n"
    item = {"question": "Q", "steps": [], "answer": {"bubbles": []}, "screen": "money", "student": "Eilidh",
            "time": "2026-10-18T12:00:00+00:00", "total_ms": 1}  # fmt: skip
    trace_live.publish(item)
    chunk = await asyncio.wait_for(anext(gen), 1)
    assert chunk.startswith("event: trace\ndata: ") and chunk.endswith("\n\n")
    assert json.loads(chunk.split("data: ", 1)[1]) == item
    parsed = list(_tool().parse_sse(chunk.splitlines() + [""]))
    assert parsed == [item]
    await gen.aclose()
    assert q not in trace_live._subscribers


async def test_sse_events_replay_last() -> None:
    for i in range(3):
        trace_live.publish({"question": f"Q{i}"})
    gen = trace_live.events(last=2, keepalive=1)
    await anext(gen)
    assert '"Q1"' in await anext(gen) and '"Q2"' in await anext(gen)
    await gen.aclose()


def test_buffer_keeps_at_most_50() -> None:
    for i in range(70):
        trace_live.publish({"question": f"Q{i}"})
    items = trace_live.recent(100)
    assert len(items) == trace_live.MAX_TRACES == 50
    assert items[0]["question"] == "Q20" and items[-1]["question"] == "Q69"


def test_cli_says_sample_and_reads_only_its_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _tool()
    item = {"question": "Is this mock data?", "student": "Sam", "screen": "money", "time": "2026-10-18T12:00:00Z",
            "steps": [{"kind": "final", "data": {"total_ms": 900, "sources_used": ["Mock bank statement"]}}],
            "answer": {"bubbles": [{"text": "It is mock data."}]}}  # fmt: skip
    out = tool.show(item)
    assert "mock" not in out.lower() and "sample" in out and "Sample bank statement" in out
    env = tmp_path / ".env"
    env.write_text(f"ANTHROPIC_API_KEY=sk-ant-other\nexport PENNY_TRACE_TOKEN='{TOKEN}'\n", encoding="utf-8")
    monkeypatch.delenv("PENNY_TRACE_TOKEN", raising=False)
    assert tool.read_token(env) == TOKEN
    monkeypatch.setenv("PENNY_TRACE_TOKEN", "from-env")
    assert tool.read_token(env) == "from-env"


def _no_secrets(text: str, user_token: str) -> None:
    assert TOKEN not in text and user_token not in text
    assert "Authorization" not in text and "Bearer" not in text
    assert prompts.PENNY_SYSTEM[:80] not in text
    assert "mock" not in text.lower()


@pytest.mark.skipif(not samples.listing().samples, reason="demo/statements not generated")
async def test_student_is_the_sample_first_name(client: httpx.AsyncClient, live_on: None) -> None:
    _use(final(("general_knowledge", LIBRARY_A)))
    auth = await sign_in(client, "live-sample")
    assert (await client.post("/v1/samples/scottish/import", headers=auth)).status_code == 201
    r = await client.post("/v1/chat", json={"message": "How long is the library open?"}, headers=auth)
    assert r.status_code == 200
    assert trace_live.recent(1)[0]["student"] == "Eilidh (sample)"
