"""Penny on a Learn lesson (screen learn_lesson, ADR 0068). Fake LLM, no network.

Rules: the lesson (title, cards, facts with values and official sources) is loaded; the quiz never is; an unknown
lesson id gives a general answer and no error; facts are cited with their official source.
"""

from __future__ import annotations

import json

from lifeline_contracts.chat import ChatContext, ChatRequest, ChatResponse
from lifeline_explain import learn_scene
from lifeline_explain.chat import Penny
from lifeline_explain.chat_tools import PERSONAL_TOOL_NAMES, ChatToolContext, GameScene
from lifeline_sim.learn_content import UNITS
from tests.unit.explain.test_chat import SETTINGS, FakeChatLLM, check_invariants, final, make_tools

LESSON_ID = "opportunity-cost"  # one fact: Lifetime ISA 25% bonus (gov.uk)
SPEC = next(s for u in UNITS for s in u.lessons if s.id == LESSON_ID)


def _ctx(lesson_id: str | None = LESSON_ID) -> ChatContext:
    return ChatContext(screen="learn_lesson", lesson_id=lesson_id, title=SPEC.title)


async def _ask(message: str, llm: FakeChatLLM, rc: ChatContext, language: str = "en") -> ChatResponse:
    scene = learn_scene.lesson_scene(rc.lesson_id)
    ctx = ChatToolContext(tools=make_tools(), thread_id="t1", user_message_id="u1", request_context=rc, scene=scene)
    req = ChatRequest(message=message, context=rc, language=language)  # type: ignore[arg-type]
    resp = await Penny(llm=llm, settings=SETTINGS).answer(req, ctx)
    check_invariants(resp)
    return resp


def _user_turn(llm: FakeChatLLM) -> str:
    return str(llm.requests[0]["messages"][-1]["content"])


def test_lesson_scene_has_title_cards_and_sourced_facts() -> None:
    scene = learn_scene.lesson_scene(LESSON_ID)
    assert isinstance(scene, GameScene) and scene.tool == "learn_lesson"
    result = scene.output.result
    assert result["lesson_title"] == SPEC.title
    assert [c["heading"] for c in result["cards"]] == [t for t, _ in SPEC.cards]
    fact = result["facts"][0]
    assert fact["source_url"] == "https://www.gov.uk/lifetime-isa" and fact["checked"]
    isa = next(f for f in scene.output.facts if f.id == "rule.lisa_bonus_rate")
    assert isa.value == 25 and isa.unit == "percent"
    src = scene.output.sources[0]
    assert isa.source_id == f"{src.source}:{src.series_id}" and src.series_id == "https://www.gov.uk/lifetime-isa"
    assert scene.output.links[0].url == "https://www.gov.uk/lifetime-isa" and scene.output.links[0].updated_at


def test_quiz_is_never_in_the_scene() -> None:
    for unit in UNITS:
        for spec in unit.lessons:
            scene = learn_scene.lesson_scene(spec.id)
            assert scene is not None
            dumped = json.dumps(scene.output.result) + json.dumps([f.label for f in scene.output.facts])
            assert "quiz" not in scene.output.result
            for q in spec.quiz:
                assert q.text not in dumped and q.why not in dumped


def test_unknown_or_missing_lesson_gives_no_scene() -> None:
    assert learn_scene.lesson_scene("no-such-lesson") is None
    assert learn_scene.lesson_scene(None) is None


async def test_lesson_goes_to_the_model_and_its_fact_is_cited() -> None:
    llm = FakeChatLLM(final("Choosing one thing means giving up the next best thing.",
                            "Spend Lifetime ISA money and you give up the 25% government bonus."))  # fmt: skip
    r = await _ask("Explain this lesson simply", llm, _ctx())
    turn = _user_turn(llm)
    assert "LESSON DATA" in turn and SPEC.cards[0][1] in turn and "LEARN LESSON SCREEN" in turn
    for q in SPEC.quiz:
        assert q.text not in turn
    tools = {t["name"] for t in llm.requests[0]["tools"]}
    assert not tools & PERSONAL_TOOL_NAMES, "no personal money tools for a lesson question"
    assert r.verified and r.mode == "checked" and len(r.bubbles) == 2
    fact = next(f for f in r.facts if f.id == "rule.lisa_bonus_rate")
    src = next(s for s in r.sources if s.id == fact.source_id)
    assert src.url == "https://www.gov.uk/lifetime-isa" and src.updated_at and src.group == "general_knowledge"


async def test_unknown_lesson_gets_a_general_answer() -> None:
    llm = FakeChatLLM(final("A lesson like this explains one money idea in simple steps."))
    r = await _ask("Explain this lesson simply", llm, _ctx("no-such-lesson"))
    assert r.bubbles and "LESSON DATA" not in _user_turn(llm)
    assert "could not be loaded" in _user_turn(llm)


async def test_own_money_question_keeps_personal_tools() -> None:
    llm = FakeChatLLM(final("A Lifetime ISA adds a 25% bonus to what you put in."))
    await _ask("Can I afford to put money in a Lifetime ISA with my budget?", llm, _ctx())
    tools = {t["name"] for t in llm.requests[0]["tools"]}
    assert "finance_summary" in tools
    assert "LESSON DATA" in _user_turn(llm)


async def test_request_language_line_is_sent() -> None:
    llm = FakeChatLLM(final("Choisir une chose, c'est renoncer à une autre."))
    await _ask("Explique cette leçon simplement", llm, _ctx(), language="fr")
    assert "ANSWER LANGUAGE" in _user_turn(llm)
