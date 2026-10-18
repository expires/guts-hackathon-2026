"""POST /v1/chat/trace and tools/penny_trace.py (ADR 0075). Fake LLM, offline app, no network."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest

from lifeline_api import samples
from lifeline_explain import chat as penny_mod
from lifeline_explain import prompts
from lifeline_explain.chat import Penny
from tests.integration.conftest import sign_in
from tests.unit.explain.test_chat import SETTINGS, FakeChatLLM, call, final

needs_samples = pytest.mark.skipif(not samples.listing().samples, reason="demo/statements not generated")
TOOL_PATH = Path(__file__).resolve().parents[4] / "tools" / "penny_trace.py"
LIBRARY_A = ("The Main Library is open 24 hours a day during term time. A late coffee there adds up, so keep it "
             "inside your weekly budget.")  # fmt: skip


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("penny_trace", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["penny_trace"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def trace_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("PENNY_TRACE_ENABLED", "1")
    yield
    penny_mod.set_penny(None)


def _use(*script: Any) -> FakeChatLLM:
    llm = FakeChatLLM(*script)
    penny_mod.set_penny(Penny(llm=llm, settings=SETTINGS))
    return llm


async def _trace(client: httpx.AsyncClient, auth: dict[str, str], message: str) -> dict[str, Any]:
    r = await client.post("/v1/chat/trace", json={"message": message}, headers=auth)
    assert r.status_code == 200, r.text
    data: dict[str, Any] = r.json()
    return data


def _kinds(trace: dict[str, Any]) -> list[str]:
    return [s["kind"] for s in trace["steps"]]


def _scope(trace: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = trace["steps"][0]["data"]
    assert trace["steps"][0]["kind"] == "scope"
    return data


async def test_trace_is_404_without_the_flag(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PENNY_TRACE_ENABLED", raising=False)
    auth = await sign_in(client, "trace-off")
    r = await client.post("/v1/chat/trace", json={"message": "Hi"}, headers=auth)
    assert r.status_code == 404
    assert "error" in r.json()


async def test_declined_path(client: httpx.AsyncClient, trace_on: None) -> None:
    llm = _use()
    t = await _trace(client, await sign_in(client, "trace-declined"), "Write my Python essay")
    assert llm.requests == []
    assert _kinds(t) == ["scope", "final"]
    assert _scope(t)["decision"] == "declined" and "sources" in _scope(t)
    assert len(t["answer"]["suggestions"]) == 2
    out = _tool().render(t, "Eilidh", colour=False)
    assert "SCOPE     declined" in out and "TOOL" not in out


async def test_student_life_path(client: httpx.AsyncClient, trace_on: None) -> None:
    _use(final(("general_knowledge", LIBRARY_A)))
    t = await _trace(client, await sign_in(client, "trace-life"), "How long is Edinburgh uni library open?")
    assert _scope(t)["decision"] == "student_life" and _scope(t)["check"] == "relaxed"
    assert _kinds(t) == ["scope", "draft", "verify", "final"]
    verify = next(s for s in t["steps"] if s["kind"] == "verify")
    assert verify["data"]["result"] == "pass"
    assert any(n["where"] == "general" for n in verify["data"]["numbers"])


@needs_samples
async def test_money_path_and_render_has_no_secrets(client: httpx.AsyncClient, trace_on: None) -> None:
    auth = await sign_in(client, "trace-money")
    assert (await client.post("/v1/samples/scottish/import", headers=auth)).status_code == 201
    _use(call("forecast"), final("You are on track until your next money."))
    t = await _trace(client, auth, "Will my money last?")
    assert _scope(t)["decision"] == "money" and _scope(t)["check"] == "strict"
    kinds = _kinds(t)
    for k in ("tool_call", "tool_result", "draft", "verify", "final"):
        assert k in kinds
    result = next(s for s in t["steps"] if s["kind"] == "tool_result" and s["data"]["tool"] == "forecast")
    inputs = result["data"]["inputs"]
    assert inputs["money_now"]["source"] == "statement" and inputs["buffer"]["source"] == "user setting"
    assert len(inputs["usual_spending"]["weeks"]) <= 4
    hub_ids = [s["id"] for s in _scope(t)["sources"]["sources"]]
    assert hub_ids[:2] == ["statement", "official_facts"] and "boe-mpc" in hub_ids

    token = auth["Authorization"].split()[1]
    raw = json.dumps(t)
    out = _tool().render(t, "Eilidh", colour=False)
    for text in (raw, out):
        assert token not in text and "Bearer" not in text and "sk-" not in text
        assert prompts.PENNY_SYSTEM[:60] not in text and "You are Penny" not in text
    assert "mock" not in out.lower()  # judges see "sample", never "mock"
    for label in ("SOURCES", "QUESTION", "SCOPE", "TOOL", "ENGINE", "DRAFT", "VERIFY", "ANSWER", "SOURCES USED"):
        assert any(line.startswith(label) for line in out.splitlines()), label
    assert "money now" in out and "buffer" in out


def test_render_scrubs_anything_that_looks_like_a_secret() -> None:
    tool = _tool()
    t = {"question": "my key is sk-ant-abcdef123456 and Bearer eyJhbGciOiJIUzI1NiJ9.e30.abc", "steps": [],
         "answer": {"bubbles": []}}  # fmt: skip
    out = tool.render(t, "Sam", colour=False)
    assert "sk-ant" not in out and "Bearer" not in out and "eyJ" not in out


def test_student_names_map_to_samples() -> None:
    tool = _tool()
    assert tool.sample_id("Eilidh") == "scottish" and tool.sample_id("yutong") == "international"
    assert tool.sample_id("loan_england") == "loan_england" and tool.display_name("scottish") == "Eilidh"
    assert len(tool.STUDENTS) == 10


def test_trace_shows_sample_never_mock() -> None:
    hub = {"sources": [{"name": "Your statement", "status": "mock", "updated_at": "2026-10-17T09:00:00Z"}]}
    trace = {"question": "Hi", "steps": [{"kind": "scope", "elapsed_ms": 1, "label": "scope",
                                          "data": {"decision": "money", "check": "strict", "sources": hub}}]}
    out = _tool().render(trace, "Eilidh", colour=False)
    assert "mock" not in out.lower() and "sample" in out
