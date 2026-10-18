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


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9£%]+", " ", (text or "").lower()).strip()


def current_card(cards: list[tuple[str, str]], message: str, card_index: int | None = None) -> int | None:
    """D4: the card the user asks about. ChatContext.card_index when sent; else the card whose text (or heading)
    the question quotes (the app sends the card text with the question). None when no card matches."""
    if card_index is not None and 0 <= card_index < len(cards):
        return card_index
    msg = _norm(message)
    if not msg:
        return None
    best: tuple[int, int] | None = None
    for i, (heading, text) in enumerate(cards):
        body = _norm(text)
        score = 0
        if body and (body in msg or (len(body) > 60 and body[:60] in msg)):
            score = 2
        elif _norm(heading) and len(_norm(heading)) > 3 and _norm(heading) in msg:
            score = 1
        if score and (best is None or score > best[1]):
            best = (i, score)
    return best[0] if best else None


def question_only(message: str, scene: GameScene | None) -> str:
    """The user's words without the quoted card text (so card wording never looks like a question about their own
    money)."""
    if scene is None or not isinstance(scene.output.result, dict):
        return message
    out = message
    for card in scene.output.result.get("cards", []):
        text = str(card.get("text") or "")
        if text and text in out:
            out = out.replace(text, " ")
    return out


def lesson_scene(lesson_id: str | None, message: str = "", card_index: int | None = None) -> GameScene | None:
    """The lesson's title, cards and facts (with values and official sources). Never its quiz.
    `current_card` marks the card the user asks about (D4). None for a missing or unknown lesson id."""
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
    idx = current_card(list(spec.cards), message, card_index)
    if idx is not None:
        heading, text = spec.cards[idx]
        result["current_card"] = {"index": idx, "heading": heading, "text": text}
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
    if scene is not None and isinstance(scene.output.result, dict) and scene.output.result.get("current_card"):
        parts.append(
            "The user is on the card in LESSON DATA current_card. Answer their question about that card first; use "
            "the rest of the lesson only if it helps."
        )
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
