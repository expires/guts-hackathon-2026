"""Penny on game screens (Life event, room round). Fake LLM, no network.

Rules: game numbers only; multiplayer never picks an option (prompt AND code, 8 languages); before a reveal no
outcome; an open quiz question never gets its answer.
"""

from __future__ import annotations

import json
import time

import pytest
from pydantic import BaseModel, ConfigDict

from lifeline_contracts.chat import ChatContext, ChatRequest, ChatResponse
from lifeline_explain import game_scene, i18n
from lifeline_explain.chat import Penny
from lifeline_explain.chat_tools import ChatToolContext, FunctionTool, FunctionToolSet, GameScene, ToolOutput
from lifeline_explain.game_scene import Guard, guard_bubbles, recommends_option
from tests.unit.explain.test_chat import BANK, SETTINGS, FakeChatLLM, NoArgs, check_invariants, f, final, make_tools
from tests.unit.explain.test_chat import finance_summary as finance_tool
from tests.unit.explain.test_chat import next_move as next_move_tool


def _decision(revealed: bool) -> GameScene:
    return game_scene.room_decision_scene(_DECISION, revealed)


_DECISION = {
    "prompt": {"id": "sd1", "year": 2008, "context": "Bank Rate was 5% that spring.",
               "text": "You have £1,000 of game money. What do you do?",
               "options": [{"id": "save", "label": "Save it"}, {"id": "spend", "label": "Buy a laptop"}]},
    "outcomes": [{"option_id": "save", "game_money_change": 47.5, "note": "Savings paid well"},
                 {"option_id": "spend", "game_money_change": -1000.0, "note": "The laptop lost value"}],
}  # fmt: skip
_QUIZ = {
    "question": {"id": "q1", "text": "When do Plan 5 student loan repayments start?",
                 "choices": [{"id": "a", "text": "Over £25,000 a year"}, {"id": "b", "text": "From the first pay"}],
                 "source_label": "gov.uk"},
    "correct": "a", "explanation": "Repayments start once you earn over the threshold.",
}  # fmt: skip
ROOM = ChatContext(screen="room_round", room_code="4821", round_id="sd1", multiplayer=True)


async def _ask(message: str, llm: FakeChatLLM, ctx_: ChatContext, scene: GameScene | None,
               language: str = "en") -> tuple[ChatResponse, ChatToolContext]:  # fmt: skip
    ctx = ChatToolContext(tools=make_tools(), thread_id="t1", user_message_id="u1", request_context=ctx_, scene=scene)
    req = ChatRequest(message=message, context=ctx_, language=language)  # type: ignore[arg-type]
    resp = await Penny(llm=llm, settings=SETTINGS).answer(req, ctx)
    check_invariants(resp)
    return resp, ctx


def _text(r: ChatResponse) -> str:
    return " ".join(b.text for b in r.bubbles)


# ---------- multiplayer never picks ----------


async def test_multiplayer_pick_is_dropped_in_code() -> None:
    llm = FakeChatLLM(final("Go with Save it. Saving gained £47.50 of game money while the laptop lost £1,000."))
    r, _ = await _ask("Which option should I pick?", llm, ROOM, _decision(True))
    assert "Go with" not in _text(r)
    assert "£47.50" in _text(r) and r.verified and r.mode == "checked"


async def test_multiplayer_answer_that_only_picks_gets_the_fixed_reply() -> None:
    llm = FakeChatLLM(final("I would pick Save it."))
    r, _ = await _ask("Which option should I pick?", llm, ROOM, _decision(True))
    assert _text(r) == game_scene.NO_PICK_TEXT["en"]


async def test_trade_off_explanation_is_kept() -> None:
    text = ("If you pick Save it, you keep the money and gain £47.50 of game money. "
            "Buy a laptop gives you the laptop now, but you give up £1,000 of game money.")  # fmt: skip
    r, _ = await _ask("Which option should I pick?", FakeChatLLM(final(text)), ROOM, _decision(True))
    assert _text(r) == text


async def test_solo_life_event_may_say_which_fits() -> None:
    solo = ChatContext(screen="life_event", life_id="l1", event_id="e1")
    llm = FakeChatLLM(final("I would pick Save it."))
    r, _ = await _ask("Which option should I pick?", llm, solo, None)
    assert _text(r) == "I would pick Save it."


PICKS = {
    "en": ["You should pick Save it.", "Save it is the better option.", "I'd go with the first one.",
           "Pick option B.", "Choose Buy a laptop."],
    "fr": ["Je choisirais Save it.", "Choisis la première option.", "Tu devrais prendre Save it."],
    "es": ["Te recomiendo Save it.", "Elige la primera opción.", "Yo elegiría Buy a laptop."],
    "pt": ["Eu escolheria Save it.", "Recomendo a primeira opção.", "Escolha Buy a laptop."],
    "it": ["Sceglierei Save it.", "Ti consiglio la prima opzione.", "Scegli Buy a laptop."],
    "zh-Hans": ["我会选Save it。", "推荐第一个选项。", "你应该选Buy a laptop。"],
    "hi": ["मैं Save it चुनूँगी।", "पहला विकल्प चुनें।", "सबसे अच्छा विकल्प Save it है।"],
    "ne": ["Save it छान्नुहोस्।", "पहिलो विकल्पको सिफारिस गर्छु।", "सबैभन्दा राम्रो विकल्प Save it हो।"],
}  # fmt: skip
OPTIONS = ("Save it", "Buy a laptop")


@pytest.mark.parametrize(("lang", "sentence"), [(lang, s) for lang, ss in PICKS.items() for s in ss])
def test_pick_patterns_in_all_8_languages(lang: str, sentence: str) -> None:
    assert recommends_option(sentence, OPTIONS), (lang, sentence)
    out = guard_bubbles([("answer", sentence)], Guard(OPTIONS, no_pick=True), lang)  # type: ignore[arg-type]
    assert out == [("answer", game_scene.NO_PICK_TEXT[lang])]  # type: ignore[index]


@pytest.mark.parametrize(
    "sentence",
    ["Save it keeps your game money safe, but you miss the laptop.", "Each option has a trade-off.",
     "If you choose Buy a laptop, you give up £1,000 of game money.", "The best option depends on your plan.",
     "Si tu choisis Save it, tu gardes ton argent.", "如果选Save it，你会保住钱。", "每个选项都有取舍。"],
)  # fmt: skip
def test_neutral_sentences_are_not_picks(sentence: str) -> None:
    assert not recommends_option(sentence, OPTIONS)


def test_every_language_has_fixed_texts() -> None:
    for table in (game_scene.NO_PICK_TEXT, game_scene.QUIZ_OPEN_TEXT, game_scene.GAME_NUMBERS):
        assert set(table) == set(i18n.LANGS)
        assert all("—" not in t for t in table.values())


# ---------- prompt rules ----------


async def test_prompt_has_game_rules_and_game_data() -> None:
    llm = FakeChatLLM(final("Save it keeps the money, Buy a laptop spends it."))
    r, ctx = await _ask("Which option should I pick?", llm, ROOM, _decision(False), language="fr")
    user = llm.requests[0]["messages"][-1]["content"]
    assert "GAME DATA" in user and "MULTIPLAYER: never recommend" in user and "BEFORE THE REVEAL" in user
    assert "chiffres du jeu" in user, "game numbers named in the answer language"
    assert "1 or 2 bubbles" in user and "trade-off of each option" in user
    assert "Game screens (CONTEXT.screen is life_event or room_round)" in llm.requests[0]["system"]
    tools = {t["name"] for t in llm.requests[0]["tools"]}
    assert not tools & {"finance_summary", "next_move", "user_balance", "habit_score"}, "no real money on game screens"


async def test_before_reveal_no_outcome_reaches_the_model() -> None:
    scene = _decision(False)
    llm = FakeChatLLM(final("Saving gains £47.50 of game money."), final("Save it keeps the money for later."))
    r, _ = await _ask("What happens if I save?", llm, ROOM, scene)
    sent = json.dumps(llm.requests[0]["messages"])
    assert "47.5" not in sent and "Savings paid well" not in sent and "game_money_change" not in sent
    assert "£47.50" not in _text(r), "a number not in GAME DATA is never shown"
    assert "Save it" in sent and "Bank Rate was 5%" in sent


async def test_game_numbers_only_user_money_blocked() -> None:
    llm = FakeChatLLM(final("You spend £1,840.50 a month, so Save it fits."), final("Save it keeps the cash."))
    r, _ = await _ask("Which one?", llm, ChatContext(screen="life_event"), _decision(True))
    assert "1,840.50" not in _text(r)


# ---------- Money Quiz: no answer while the question is open ----------


async def test_open_quiz_answer_is_never_given() -> None:
    scene = game_scene.room_quiz_scene(_QUIZ, revealed=False)
    llm = FakeChatLLM(final("The answer is Over £25,000 a year. Plan 5 loans are paid back from salary."))
    r, _ = await _ask("What is the answer?", llm, ROOM, scene)
    text = _text(r)
    assert "25,000" not in text and "answer is" not in text.lower()
    assert "paid back from salary" in text
    sent = json.dumps(llm.requests[0]["messages"])
    assert "threshold" not in sent and '"correct' not in sent and "QUIZ QUESTION OPEN" in sent


async def test_open_quiz_answer_only_gets_fixed_reply_in_language() -> None:
    scene = game_scene.room_quiz_scene(_QUIZ, revealed=False)
    llm = FakeChatLLM(final("La bonne réponse est Over £25,000 a year."))
    r, _ = await _ask("Quelle est la réponse ?", llm, ROOM, scene, language="fr")
    assert _text(r) == game_scene.QUIZ_OPEN_TEXT["fr"]


def test_revealed_quiz_has_answer_for_explaining() -> None:
    scene = game_scene.room_quiz_scene(_QUIZ, revealed=True)
    assert not scene.quiz_open and scene.output.result["correct_choice"] == "Over £25,000 a year"


# ---------- streaming: a pick is never sent as an early bubble ----------


def test_early_bubble_check() -> None:
    guard = Guard(OPTIONS, no_pick=True)
    assert guard.changes("Pick Save it.") and not guard.changes("Save it keeps the cash.")


# ---------- speed ----------


async def test_scene_adds_no_model_round_trip() -> None:
    llm = FakeChatLLM(final("Save it keeps £1,000 of game money in the bank. Buy a laptop spends it."))
    t0 = time.monotonic()
    r, _ = await _ask("Which option should I pick?", llm, ROOM, _decision(False))
    assert len(llm.requests) == 1 and time.monotonic() - t0 < 1.0
    assert r.verified and r.mode == "checked" and "£1,000" in _text(r)


def test_scene_tool_output_is_plain() -> None:
    assert isinstance(_decision(False).output, ToolOutput)


# ---------- Next Move, Why? and Test it: the move or result on screen is in context ----------


class MoveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    move_id: str = "top"


TESTED: list[str] = []


def _test_move(inp: MoveIn) -> ToolOutput:
    TESTED.append(inp.move_id)
    return ToolOutput(result={"move_id": inp.move_id, "verdict": "better"},
                      facts=[f("test_move.gain", 410, "gbp", "Gain in the replay", BANK)], sources=[BANK])


class _Preloading(FunctionToolSet):
    preload = ("finance_summary", "next_move")


def _tools() -> _Preloading:
    return _Preloading([
        FunctionTool("next_move", "Next move", NoArgs, next_move_tool),
        FunctionTool("finance_summary", "Summary", NoArgs, finance_tool),
        FunctionTool("test_move", "Test", MoveIn, _test_move),
    ])


@pytest.mark.parametrize("screen", ["next_move", "why"])
async def test_next_move_and_why_have_the_move_in_context(screen: str) -> None:
    rc = ChatContext(screen=screen, next_move_id="fix_5y")  # type: ignore[arg-type]
    ctx = ChatToolContext(tools=_tools(), thread_id="t1", user_message_id="u1", request_context=rc)
    llm = FakeChatLLM(final("Fix for 5 years. It is worth £1,240 a year."))
    r = await Penny(llm=llm, settings=SETTINGS).answer(ChatRequest(message="Why this move?", context=rc), ctx)
    user = llm.requests[0]["messages"][-1]["content"]
    assert "APP DATA" in user and '"next_move"' in user and '"next_move_id": "fix_5y"' in user
    assert r.verified and r.mode == "checked"


async def test_test_it_preloads_the_replay_of_the_move() -> None:
    TESTED.clear()
    rc = ChatContext(screen="test_it", next_move_id="fix_5y")
    ctx = ChatToolContext(tools=_tools(), thread_id="t1", user_message_id="u1", request_context=rc)
    llm = FakeChatLLM(final("In the replay, the move came out £410 better."))
    r = await Penny(llm=llm, settings=SETTINGS).answer(ChatRequest(message="What does this result mean?",
                                                                   context=rc), ctx)  # fmt: skip
    assert TESTED == ["fix_5y"]
    user = llm.requests[0]["messages"][-1]["content"]
    assert '"test_move"' in user and len(llm.requests) == 1
    assert r.verified and "test_move" in {c.name for c in r.tool_calls}
