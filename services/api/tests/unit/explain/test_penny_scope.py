"""ADR 0073: Penny answers money and student-life questions. Anything else gets one fixed line and 2 money chips.
Fake LLM and fake tools, no network."""

from __future__ import annotations

import json

import pytest

from lifeline_contracts.chat import ChatContext, ChatRequest, ChatResponse
from lifeline_explain import i18n, prompts, scope
from lifeline_explain.chat import Penny, quick_reaction
from lifeline_explain.chat_llm import LLMStep
from lifeline_explain.chat_tools import ChatToolContext
from tests.unit.explain.test_chat import SETTINGS, FakeChatLLM, ask, check_invariants, final
from tests.unit.explain.test_chat_languages import no_data_tools

ESSAY_Q = "Write my Python essay"
LIBRARY_Q = "How long is Edinburgh library open?"
LIBRARY_A = (
    "The Main Library at the University of Edinburgh is open 24 hours a day during term time. "
    "A late-night coffee nearby adds up, so keep it inside your weekly budget."
)
LOAN_Q = "How does my student loan work?"
LOAN_A = (
    "You borrow for fees and living costs, and you start paying back only once you earn over the threshold. "
    "Repayments come out of your pay automatically, and anything left is written off after a set time."
)


async def _ask(message: str, llm: FakeChatLLM, language: str = "en", context: ChatContext | None = None
               ) -> ChatResponse:  # fmt: skip
    req = ChatRequest(message=message, language=language, context=context)  # type: ignore[arg-type]
    ctx = ChatToolContext(tools=no_data_tools(), thread_id="t1", user_message_id="u1", request_context=context)
    resp = await Penny(llm=llm, settings=SETTINGS).answer(req, ctx)
    check_invariants(resp)
    return resp


def _off_topic_step() -> LLMStep:
    payload = {"reaction": "shrug", "out_of_scope": False, "off_topic": True, "bubbles": []}
    return LLMStep(stop_reason="end_turn", text=json.dumps(payload))


@pytest.mark.parametrize("lang", ["en", "fr"])
async def test_python_essay_gets_the_short_no_and_two_chips(lang: str) -> None:
    llm = FakeChatLLM()  # the rule decides before any model call
    r = await _ask(ESSAY_Q, llm, lang)
    assert llm.requests == []
    assert [b.text for b in r.bubbles] == [i18n.OFF_TOPIC[lang]]  # type: ignore[index]
    assert r.suggestions == list(i18n.OFF_TOPIC_CHIPS["homework"][lang])  # type: ignore[index]
    assert len(r.suggestions) == 2
    assert r.mode == "general" and r.reaction == "shrug" and r.verified
    assert r.sources == [] and r.links == [] and r.tool_calls == []
    assert all(b.kind == "answer" for b in r.bubbles)


async def test_off_topic_in_onboarding_has_no_web_search() -> None:
    llm = FakeChatLLM()
    r = await _ask("Can you debug my code?", llm, context=ChatContext(screen="onboarding"))
    assert llm.requests == [] and r.tool_calls == []
    assert r.suggestions == list(i18n.OFF_TOPIC_CHIPS["code"]["en"])


async def test_model_off_topic_flag_gets_the_short_no_without_retry() -> None:
    llm = FakeChatLLM(_off_topic_step())
    r = await _ask("Who won the darts last night?", llm, "es")
    assert len(llm.requests) == 1
    assert [b.text for b in r.bubbles] == [i18n.OFF_TOPIC["es"]]
    assert r.suggestions == list(i18n.OFF_TOPIC_CHIPS["general"]["es"])


async def test_library_question_gets_a_real_answer() -> None:
    r = await _ask(LIBRARY_Q, FakeChatLLM(final(LIBRARY_A)), context=ChatContext(screen="onboarding"))
    text = " ".join(b.text for b in r.bubbles)
    assert "24 hours" in text and "weekly budget" in text
    assert i18n.OFF_TOPIC["en"] not in text
    assert r.bubbles[0].kind == "general_knowledge" and r.mode == "general"


async def test_student_loan_question_gets_a_real_answer() -> None:
    r, _ = await ask(LOAN_Q, FakeChatLLM(final(LOAN_A)))
    text = " ".join(b.text for b in r.bubbles)
    assert "threshold" in text and i18n.OFF_TOPIC["en"] not in text
    assert r.verified


async def test_safety_replies_are_unchanged() -> None:
    r, _ = await ask("Which crypto should I buy?", FakeChatLLM())
    assert r.bubbles[0].text == i18n.OUT_OF_SCOPE["en"]
    r, _ = await ask("I can't cope anymore, I want to die", FakeChatLLM())
    assert r.bubbles[0].text == i18n.DISTRESS["en"][0]


@pytest.mark.parametrize("message", [
    LIBRARY_Q, LOAN_Q, "How do I make friends at uni?", "Cheap recipes for students?", "When is my essay deadline?",
    "How do I get from Waverley to campus?", "Where is the student wellbeing service?", "Can I afford a laptop?",
    "Is there a coding society at Edinburgh?", "Python course fees", "How much is a gym membership?",
])  # fmt: skip
def test_rule_lets_money_and_student_life_through(message: str) -> None:
    assert not scope.off_topic_rule(message)


@pytest.mark.parametrize("message", [
    ESSAY_Q, "Fix my JavaScript code", "Do my homework for me", "Give me a lasagne recipe",
    "Latest celebrity gossip?", "Écris ma dissertation", "帮我写作业",
])  # fmt: skip
def test_rule_catches_clear_off_topic(message: str) -> None:
    assert scope.off_topic_rule(message)


def test_quick_reaction_for_off_topic() -> None:
    assert quick_reaction(ChatRequest(message=ESSAY_Q)) == "shrug"


def test_fixed_texts_cover_8_languages() -> None:
    assert set(i18n.OFF_TOPIC) == set(i18n.LANGS)
    for topic in ("code", "homework", "celebrity", "food", "general"):
        for lang in i18n.LANGS:
            chips = i18n.OFF_TOPIC_CHIPS[topic][lang]
            assert len(chips) == 2 and all(c and "—" not in c for c in chips)


def test_prompt_has_the_scope_rule() -> None:
    assert "off_topic" in prompts.PENNY_SYSTEM and "student-life" in prompts.PENNY_SYSTEM
    assert "off_topic" in prompts.PENNY_ANSWER_SCHEMA["properties"]
    assert "general_knowledge" in prompts.PENNY_ANSWER_SCHEMA["properties"]["bubbles"]["items"]["properties"][
        "kind"]["enum"]  # fmt: skip
