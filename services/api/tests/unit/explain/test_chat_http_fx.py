"""V4 F3-2 through the HTTP route: the "1 million yuan" answer states the rate and its date (V6 S5-F1)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import httpx
import pytest

from lifeline_explain.chat_llm import LLMStep, ToolUse
from tests.integration.conftest import client, sign_in  # noqa: F401  (client is a fixture)


class Scripted:
    """Converts with fx_convert, then answers twice without the rate or its date."""

    def __init__(self) -> None:
        self.steps: list[LLMStep] = [
            LLMStep(stop_reason="tool_use", tool_uses=[ToolUse(id="tu1", name="fx_convert", input={
                "amount": 1_000_000, "from_currency": "CNY", "to_currency": "GBP"})]),
        ]  # fmt: skip
        self.converted: float | None = None

    async def step(self, system: str, messages: list[dict[str, Any]], tools: Any, schema: Any) -> LLMStep:
        if self.steps:
            return self.steps.pop(0)
        if self.converted is None:
            for block in messages[-1]["content"]:
                for fact in json.loads(block["content"])["facts"]:
                    if fact["id"] == "fx.converted":
                        self.converted = fact["value"]
        text = f"1,000,000 yuan is about £{self.converted:,.0f}."
        body = {"reaction": "brain", "out_of_scope": False, "bubbles": [{"kind": "answer", "text": text}]}
        return LLMStep(stop_reason="end_turn", text=json.dumps(body))


async def test_million_yuan_answer_states_rate_and_date_over_http(
    client: httpx.AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lifeline_api.main import app
    from lifeline_api.routes import chat as chat_routes
    from lifeline_explain import chat as real_penny

    async def fx_rate(base: str, quote: str) -> tuple[float, date] | None:
        return (0.11215, date(2026, 10, 16)) if (base, quote) == ("CNY", "GBP") else None

    monkeypatch.setattr(app.state.lifeline.hub, "fx_rate", fx_rate)
    monkeypatch.setattr(chat_routes.penny, "answer", real_penny.Penny(llm=Scripted()).answer)
    auth = await sign_in(client, "w5-fx-device-0001")
    r = await client.post("/v1/chat", json={"message": "Can I afford a holiday that costs 1 million yuan?"},
                          headers=auth)  # fmt: skip
    assert r.status_code == 200, r.text
    body = r.json()
    text = " ".join(b["text"] for b in body["bubbles"])
    assert body["verified"] and "fx_convert" in {t["name"] for t in body["tool_calls"]}
    assert "Rate: 1 CNY = £0.11215 (ECB, 16 Oct 2026)." in text
