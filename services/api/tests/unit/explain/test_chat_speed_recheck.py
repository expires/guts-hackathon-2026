"""V1 speed work and V6 re-check (V2-R1, V2-R2, false positives). Fake LLM, no network."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any

import pytest

from lifeline_contracts.chat import ChatRequest
from lifeline_explain import chat as chat_mod
from lifeline_explain import official
from lifeline_explain.chat import Penny, distress_rule, gives_pick, out_of_scope_rule
from lifeline_explain.chat_llm import LLMStep, WebResult
from lifeline_explain.chat_tools import ChatToolContext
from tests.unit.explain.test_chat import SETTINGS, FakeChatLLM, ask, call, final, make_tools

SF_URL = "https://www.gov.uk/student-finance/new-fulltime-students"


@pytest.fixture(autouse=True)
def _today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(official, "today", lambda: date(2026, 10, 17))


def web(step: LLMStep, *results: WebResult) -> LLMStep:
    step.web_searches = 1
    step.web_results = list(results)
    return step


def engine_tools() -> Any:
    from lifeline_data.macro import mock_macro_table
    from lifeline_explain.chat_engine_tools import EngineToolSet
    from tests.unit.engine.finance_builders import homeowner

    return EngineToolSet(homeowner(), mock_macro_table(), date(2026, 10, 17))


# ---------- speed: early first bubble, preload ----------


class StreamingFake(FakeChatLLM):
    """Streams the answer text: the first bubble is complete PAUSE seconds before the answer ends."""

    supports_stream = True
    PAUSE = 0.3

    async def step(self, system: str, messages: Any, tools: Any, schema: Any, on_text: Any = None) -> LLMStep:
        s = await super().step(system, messages, tools, schema)
        if on_text and s.text:
            cut = s.text.find('"}', s.text.find('"text"')) + 2
            on_text(s.text[:cut])
            await asyncio.sleep(self.PAUSE)
            on_text(s.text)
        return s


async def test_first_bubble_streams_before_the_answer_finishes() -> None:
    llm = StreamingFake(call("finance_summary"), final("You spend £1,840.50 a month.", "That is a steady month."))
    ctx = ChatToolContext(tools=make_tools())
    ev = [e async for e in Penny(llm=llm, settings=SETTINGS).answer_stream(ChatRequest(message="Spend?"), ctx)]
    bubbles = [e for e in ev if e.type == "bubble"]
    assert [b.bubble.bubble.text for b in bubbles] == ["You spend £1,840.50 a month.", "That is a steady month."]
    assert ev[-1].elapsed_ms - bubbles[0].elapsed_ms >= 250  # bubble 1 went out while bubble 2 was still coming
    assert bubbles[0].bubble.highlights and ev[-1].response.verified
    assert [b.id for b in ev[-1].response.bubbles] == [b.bubble.bubble.id for b in bubbles]


async def test_early_bubble_not_sent_when_it_fails_a_check() -> None:
    llm = StreamingFake(call("finance_summary"), final("You spend £9,999 a month."),
                        final("You spend £1,840.50 a month."))  # fmt: skip
    ctx = ChatToolContext(tools=make_tools())
    ev = [e async for e in Penny(llm=llm, settings=SETTINGS).answer_stream(ChatRequest(message="Spend?"), ctx)]
    texts = [e.bubble.bubble.text for e in ev if e.type == "bubble"]
    assert texts == ["You spend £1,840.50 a month."]


async def test_failing_second_bubble_dropped_without_rewrite() -> None:
    llm = FakeChatLLM(call("finance_summary"), final("You spend £1,840.50 a month.", "That is 3 months of rent."))
    r, _ = await ask("Spend?", llm)
    assert r.verified and [b.text for b in r.bubbles] == ["You spend £1,840.50 a month."]
    assert len(llm.requests) == 2  # no rewrite call


async def test_rules_question_preloads_facts_table_one_call() -> None:
    ts = engine_tools()

    def answer(messages: list[dict[str, Any]]) -> LLMStep:
        content = messages[-1]["content"]
        data, _ = json.JSONDecoder().raw_decode(content[content.index("APP DATA") :].split(": ", 1)[1])
        fact = next(x for x in data["facts_table"]["facts"] if x["id"] == "rule.student_loan_plan2_threshold")
        return final(f"On Plan 2 you repay once you earn over £{fact['value']:,.0f} a year.")

    llm = FakeChatLLM(answer)
    r = await Penny(llm=llm, settings=SETTINGS).answer(
        ChatRequest(message="When do I start repaying my student loan?"), ChatToolContext(tools=ts)
    )
    assert len(llm.requests) == 1 and r.mode == "checked" and r.verified
    assert any(s.label.endswith("checked 17 Oct 2026") for s in r.sources)


# ---------- V2-R1: fallback never shows web numbers ----------


async def test_v2_r1_no_app_tool_fallback_is_general_not_confirmed() -> None:
    page = WebResult(url=SF_URL, title="Student finance - GOV.UK", text="up to £13,762 in London")
    said = final("You have £13,762 left this year.")
    r, _ = await ask("How much maintenance loan in London?", FakeChatLLM(web(said, page), said))
    text = " ".join(b.text for b in r.bubbles)
    assert r.mode == "general" and not r.verified and text == chat_mod.NOT_CONFIRMED_TEXT
    assert "13,762" not in text and not any(f.id.startswith("web.") for f in r.facts)


# ---------- V2-R2: official flow beyond keywords ----------


async def test_v2_r2_sfe_question_is_official_only() -> None:
    q = "How much do I need to earn before SFE starts taking money out of my pay?"
    assert official.is_rules_question(q)
    llm = FakeChatLLM(final("I could not find an official source for that."))
    await ask(q, llm)
    tool = next(t for t in llm.requests[0]["tools"] if t.get("name") == "web_search")
    assert tool["allowed_domains"] == list(official.OFFICIAL_DOMAINS)


async def test_v2_r2_number_from_non_official_site_blocked() -> None:
    blog = WebResult(url="https://studentblog.example/food", title="Food", text="students spend £40 a week")
    said = "Students spend about £40 a week on food."
    llm = FakeChatLLM(web(final(said), blog), final(said))
    r, _ = await ask("How much do students spend on food?", llm)
    second_tool = next(t for t in llm.requests[1]["tools"] if t.get("name") == "web_search")
    assert second_tool["allowed_domains"] == list(official.OFFICIAL_DOMAINS)
    assert "40" not in " ".join(b.text for b in r.bubbles)


# ---------- false positives ----------


@pytest.mark.parametrize(
    "message", ["best apple to buy for baking", "good options to buy cheap textbooks", "Buy an apple and some oats"]
)
async def test_everyday_buying_not_refused(message: str) -> None:
    assert not out_of_scope_rule(message)
    r, _ = await ask(message, FakeChatLLM(final("Buy an apple and some oats.")))
    assert r.reaction != "shrug" and r.bubbles[0].text == "Buy an apple and some oats."
    assert not gives_pick("Buy an apple and some oats.")


async def test_ending_things_with_a_provider_is_not_distress() -> None:
    message = "I'm ending things with my overdraft provider"
    assert not distress_rule(message)
    r, _ = await ask(message, FakeChatLLM(final("Moving your overdraft can save money.")))
    assert "Samaritans" not in " ".join(b.text for b in r.bubbles)
    assert distress_rule("I'm thinking of ending things")
