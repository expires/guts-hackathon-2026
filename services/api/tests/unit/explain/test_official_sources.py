"""ADR 0058: rules questions use official sources. Facts table first, then official web search, else no number."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest

from lifeline_contracts.chat import ChatRequest
from lifeline_explain import official
from lifeline_explain.chat import Penny
from lifeline_explain.chat_llm import LLMStep, WebResult
from lifeline_explain.chat_tools import ChatToolContext
from tests.unit.explain.test_chat import SETTINGS, FakeChatLLM, ask, call, check_invariants, final

SF_URL = "https://www.gov.uk/student-finance/new-fulltime-students"
SF_TITLE = "Student finance: new full-time students - GOV.UK"
SF_TEXT = "up to £13,762 if you live away from your parents and study in London"
QUESTION = "How much maintenance loan can I get in London?"


@pytest.fixture(autouse=True)
def _today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(official, "today", lambda: date(2026, 10, 17))


def web(step: LLMStep, *results: WebResult) -> LLMStep:
    step.web_searches = 1
    step.web_results = list(results)
    return step


def test_rules_question_detection() -> None:
    assert official.is_rules_question(QUESTION)
    assert official.is_rules_question("When do I start repaying my student loan?")
    assert official.is_rules_question("How much is a 16-25 Railcard?")
    assert not official.is_rules_question("What can I cook tonight?")


def test_official_domains() -> None:
    assert official.is_official_url("https://www.gov.uk/x") and official.is_official_url("https://www.saas.gov.uk/y")
    assert official.is_official_url("https://www.16-25railcard.co.uk")
    assert not official.is_official_url("https://gov.uk.evil.example/x")
    assert not official.is_official_url("http://www.gov.uk/x")  # https only


# ---------- 1. facts table hit ----------


async def test_facts_table_hit_shows_official_url_and_checked_date() -> None:
    from lifeline_data.macro import mock_macro_table
    from lifeline_explain.chat_engine_tools import EngineToolSet
    from tests.unit.engine.finance_builders import homeowner

    ts = EngineToolSet(homeowner(), mock_macro_table(), date(2026, 10, 17))

    def answer(messages: list[dict[str, Any]]) -> LLMStep:
        payload = json.loads(messages[-1]["content"][0]["content"])
        fact = next(x for x in payload["facts"] if x["unit"].startswith("gbp") and "plan2_threshold" in x["id"])
        return final(f"On Plan 2 you repay once you earn over £{fact['value']:,.0f} a year.")

    llm = FakeChatLLM(call("facts_table", topic="student_loan"), answer)
    r = await Penny(llm=llm, settings=SETTINGS).answer(
        ChatRequest(message="When do I start repaying my student loan?"), ChatToolContext(tools=ts)
    )
    check_invariants(r)
    assert r.mode == "checked" and r.verified
    src = next(s for s in r.sources if s.id == r.highlights[0].source_id)
    url = official.rule_url("rule.student_loan_plan2_threshold")
    assert url and src.url == url and official.is_official_url(url)
    assert src.label == official.official_label(url, "checked 17 Oct 2026")
    assert src.label.startswith("gov.uk \u00b7 ") and src.label.endswith(" \u00b7 checked 17 Oct 2026")
    assert src.updated_at == "2026-10-17"


# ---------- 2. official web search ----------


async def test_web_search_restricted_to_official_domains_and_cited() -> None:
    step = web(final("You can get up to £13,762 a year if you study in London."),
               WebResult(url=SF_URL, title=SF_TITLE, text=SF_TEXT))  # fmt: skip
    llm = FakeChatLLM(step)
    r, _ = await ask(QUESTION, llm)
    tool = next(t for t in llm.requests[0]["tools"] if t.get("name") == "web_search")
    assert tool["allowed_domains"] == list(official.OFFICIAL_DOMAINS)
    assert r.mode == "general" and r.verified and "13,762" in r.bubbles[0].text
    assert [s.label for s in r.sources] == ["gov.uk · Student finance: new full-time students · retrieved 17 Oct 2026"]
    assert r.sources[0].url == SF_URL


async def test_general_question_web_search_not_restricted() -> None:
    llm = FakeChatLLM(final("Batch cooking saves time."))
    await ask("How do I batch cook?", llm)
    tool = next(t for t in llm.requests[0]["tools"] if t.get("name") == "web_search")
    assert "allowed_domains" not in tool


async def test_non_official_result_is_ignored() -> None:
    blog = WebResult(url="https://moneyblog.example/loans", title="Loans", text="you get £15,000 in London")
    said = "A blog says you can get up to £15,000 in London."
    llm = FakeChatLLM(web(final(said), blog), final(said))
    r, _ = await ask(QUESTION, llm)
    text = " ".join(b.text for b in r.bubbles)
    assert "15,000" not in text and r.sources == []
    assert text == official.NO_OFFICIAL_SOURCE_TEXT


async def test_number_not_in_official_text_is_blocked_then_fixed() -> None:
    page = WebResult(url=SF_URL, title=SF_TITLE, text=SF_TEXT)
    llm = FakeChatLLM(
        web(final("You can get up to £14,000 a year in London."), page),
        final("You can get up to £13,762 a year in London."),
    )
    r, _ = await ask(QUESTION, llm)
    assert "14,000" in llm.requests[1]["messages"][-1]["content"]
    assert r.verified and "13,762" in r.bubbles[0].text and r.sources[0].url == SF_URL


async def test_number_still_wrong_answers_without_it() -> None:
    page = WebResult(url=SF_URL, title=SF_TITLE, text=SF_TEXT)
    said = "Student finance depends on where you live. In London you can get up to £14,000."
    r, _ = await ask(QUESTION, FakeChatLLM(web(final(said), page), final(said)))
    assert [b.text for b in r.bubbles] == ["Student finance depends on where you live."]
    assert r.sources and r.sources[0].url == SF_URL


# ---------- 3. no official source ----------


async def test_no_official_source_gives_no_number() -> None:
    said = final("The London maintenance loan is £13,000.")
    r, _ = await ask(QUESTION, FakeChatLLM(said, said))
    assert [b.text for b in r.bubbles] == [official.NO_OFFICIAL_SOURCE_TEXT]
    assert r.mode == "general" and not any(ch.isdigit() for ch in r.bubbles[0].text)


def test_citation_text_is_read_from_the_api_response() -> None:
    from types import SimpleNamespace

    from lifeline_explain.chat_llm import _web

    cite = SimpleNamespace(type="web_search_result_location", url=SF_URL, title=SF_TITLE, cited_text=SF_TEXT)
    _, results = _web([SimpleNamespace(type="text", text="x", citations=[cite])])
    assert results == [WebResult(url=SF_URL, title=SF_TITLE, text=SF_TEXT)]
