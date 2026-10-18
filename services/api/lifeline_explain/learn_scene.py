"""Penny on a Learn lesson (screen "learn_lesson", ADR 0068): "Ask Penny about this lesson".

The lesson the user looks at is loaded server-side from the Learn course (lifeline_sim.learn_content) and goes to
the model as LESSON DATA: title, cards and facts. Each fact carries its facts-table value, its official page and
the date it was checked, so Penny may quote it as a checked fact with that source.

Rules (prompt AND code):
- The quiz is never loaded: no question, no choice, no answer reaches the model.
- 1 or 2 bubbles, simple English (or the request language).
- No personal money tools, unless the user asks about their own money.
- Unknown lesson id: no scene, a general answer, no error.
"""

from __future__ import annotations

import re
from functools import cache
from typing import Any

from lifeline_contracts.chat import ChatContext, ChatFact
from lifeline_explain.chat_tools import GameScene, ToolOutput
from lifeline_explain.game_scene import text_facts
from lifeline_explain.official import with_official_sources

LEARN_SCREEN = "learn_lesson"
LESSON_TOOL = "learn_lesson"

# "my money", "can I afford", "my balance": the user asks about their own money, so personal tools stay on.
_OWN_MONEY = re.compile(
    r"\b(my|mine|i have|i've got|i earn|i spend|i owe|can i afford|should i|for me|i get paid)\b",
    re.IGNORECASE,
)


def is_learn_screen(rc: ChatContext | None) -> bool:
    return rc is not None and rc.screen == LEARN_SCREEN


def asks_own_money(message: str) -> bool:
    return bool(_OWN_MONEY.search(message or ""))


@cache
def _spec(lesson_id: str) -> Any:
    from lifeline_sim.learn_content import UNITS

    for unit in UNITS:
        for spec in unit.lessons:
            if spec.id == lesson_id:
                return spec
    return None


def lesson_scene(lesson_id: str | None) -> GameScene | None:
    """The lesson's title, cards and facts (with values and official sources). Never its quiz.
    None for a missing or unknown lesson id."""
    if not lesson_id:
        return None
    try:
        spec = _spec(lesson_id)
    except Exception:  # pragma: no cover - content module missing or broken: Penny answers in general
        return None
    if spec is None:
        return None
    from lifeline_engine import rules

    facts: list[ChatFact] = []
    rows: list[dict[str, Any]] = []
    for fs in spec.facts:
        try:
            rf = rules.get(fs.rule)
        except KeyError:
            continue
        if not any(f.id == rf.id for f in facts):
            facts.append(ChatFact(id=rf.id, value=rf.value, unit=rf.unit,
                                  label=f"{rf.label} ({rf.tax_year})"[:120]))  # fmt: skip
        rows.append({"fact_id": rf.id, "text": fs.text, "source_url": rf.url, "checked": rf.checked})
    result: dict[str, Any] = {
        "lesson_id": spec.id,
        "lesson_title": spec.title,
        "cards": [{"heading": t, "text": x} for t, x in spec.cards],
        "facts": rows,
    }
    out = with_official_sources(ToolOutput(result=result, facts=facts))
    first = out.facts[0].source_id if out.facts else None
    # Numbers written in the cards are lesson content; they may be repeated, under the lesson's first source.
    card_texts = {f"cards.{i}.text": x for i, (_, x) in enumerate(spec.cards)}
    if first is not None:
        out = out.model_copy(update={"facts": [*out.facts, *text_facts("lesson", card_texts, first)]})
    return GameScene(tool=LESSON_TOOL, output=out)


def rules_line(rc: ChatContext, scene: GameScene | None, own_money: bool) -> str:
    """Per-turn rules for the lesson screen (in the user turn, so the cached system prompt stays the same)."""
    parts = [
        "LEARN LESSON SCREEN: the user asks about a Learn lesson. Answer in 1 or 2 short bubbles, in simple words "
        "a 15-year-old understands.",
    ]
    if scene is not None:
        parts.append(
            "Explain the lesson from LESSON DATA. Its facts are checked official numbers: quote them exactly, and "
            "they are cited with their official source (the page and the date it was checked). Use no other "
            "numbers. Never talk about the lesson quiz, its questions or its answers."
        )
    else:
        parts.append("The lesson could not be loaded: explain the idea in general words. Use a number only from a "
                     "tool result.")
    if not own_money:
        parts.append("Do not use or mention the user's own money.")
    return " ".join(parts)
