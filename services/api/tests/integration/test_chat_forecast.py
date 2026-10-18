"""Ask Penny from the forecast (PENNY_V3_BUILD.md B3.7, D4, ADR 0072), W5 side through the HTTP API.

Penny is replaced by a fake that records the tool context. The forecast tool must return the same numbers as
GET /v1/forecast (same engine call, same stored buffer %). The onboarding chat (no own data) has no forecast tool.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from lifeline_api import samples
from lifeline_contracts.chat import ChatBubble, ChatRequest, ChatResponse
from lifeline_explain.chat_tools import ChatToolContext
from tests.integration.conftest import sign_in

needs_samples = pytest.mark.skipif(not samples.listing().samples, reason="demo/statements not generated")
SEEN: list[ChatToolContext] = []


async def fake_answer(req: ChatRequest, ctx: ChatToolContext) -> ChatResponse:
    SEEN.append(ctx)
    return ChatResponse(thread_id=ctx.thread_id or "", message_id="pm_1", reply_to=ctx.user_message_id or "",
                        reaction="brain", bubbles=[ChatBubble(id="b1", kind="answer", text="ok")], confidence=0.9,
                        verified=True)  # fmt: skip


@pytest.fixture(autouse=True)
def fake_penny(monkeypatch: pytest.MonkeyPatch) -> None:
    from lifeline_api.routes import chat as chat_routes

    SEEN.clear()
    monkeypatch.setattr(chat_routes.penny, "answer", fake_answer)


def _body() -> dict[str, Any]:
    return {"message": "Explain my weekly budget", "context": {"screen": "forecast", "title": "Weekly budget"}}


async def test_onboarding_chat_has_no_forecast_tool(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "chat-forecast-none")
    r = await client.post("/v1/chat", json={"message": "Hi", "context": {"screen": "onboarding"}}, headers=auth)
    assert r.status_code == 200, r.text
    assert "forecast" not in {s.name for s in SEEN[-1].tools.specs()}


@needs_samples
async def test_forecast_tool_matches_get_forecast_and_buffer(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "chat-forecast-01")
    sample = samples.listing().samples[0].id
    assert (await client.post(f"/v1/samples/{sample}/import", headers=auth)).status_code == 201
    assert (await client.put("/v1/forecast/settings", json={"buffer_pct": 20}, headers=auth)).status_code == 200
    card = (await client.get("/v1/forecast", headers=auth)).json()

    r = await client.post("/v1/chat", json=_body(), headers=auth)
    assert r.status_code == 200, r.text
    tools = SEEN[-1].tools
    assert "forecast" in {s.name for s in tools.specs()}
    assert getattr(tools, "preload", ()) == ("finance_summary", "forecast")
    out = await tools.call("forecast", {})
    facts = {f.id: f.value for f in out.facts}
    assert facts["forecast.buffer_pct"] == 20 == card["buffer_pct"]
    assert facts["forecast.per_week"] == round(card["per_week"], 2)
    assert facts["forecast.per_day"] == round(card["per_day"], 2)


@needs_samples
async def test_what_if_tool_runs_the_engine(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "chat-forecast-02")
    sample = samples.listing().samples[0].id
    assert (await client.post(f"/v1/samples/{sample}/import", headers=auth)).status_code == 201
    card = (await client.get("/v1/forecast", headers=auth)).json()
    r = await client.post("/v1/chat", json=_body(), headers=auth)
    assert r.status_code == 200, r.text
    tools = SEEN[-1].tools
    assert "forecast_what_if" in {s.name for s in tools.specs()}
    change = {"kind": "one_off_cost", "amount": 60, "date": card["today"], "label": "Concert ticket"}
    out = await tools.call("forecast_what_if", {"changes": [change]})
    facts = {f.id: f.value for f in out.facts}
    assert facts["whatif.before.per_week"] == round(card["per_week"], 2)
    assert facts["whatif.after.per_week"] <= facts["whatif.before.per_week"]
