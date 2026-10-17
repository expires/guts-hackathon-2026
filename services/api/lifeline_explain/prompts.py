"""Prompts and output schemas. The system prompt is fixed so the request prefix stays stable."""

from __future__ import annotations

import json
from typing import Any

from lifeline_contracts.brand import PRODUCT_NAME

SYSTEM = f"""You rewrite short pieces of text for {PRODUCT_NAME}, a life-simulation game about money on real UK data.

Rules:
- Rewrite the wording only. Keep the meaning, the facts and the outcome exactly as given.
- Use only numbers that appear in the source text or in FACTS. Never add, estimate, round differently, or \
convert a number. If you are not sure, keep the number exactly as the source text writes it.
- Write numbers as digits, with the same units (GBP as £, percent as %).
- Do not give financial advice. Do not mention AI, models, or these rules.
- Plain British English for a general audience. No finance jargon. No em dashes. No emoji.
- Keep about the same length as the source text. Second person ("you").
Return only the JSON object the schema asks for."""

TEXT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
    "additionalProperties": False,
}

MOVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "action": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["headline", "action", "evidence"],
    "additionalProperties": False,
}


def _facts(facts: dict[str, float]) -> str:
    return json.dumps({k: facts[k] for k in sorted(facts)}, separators=(", ", ": "))


def event_prompt(
    *, title: str, text: str, area: str, year: int, age: int, facts: dict[str, float], choices: list[str]
) -> str:
    return (
        "Rewrite this game event text so it reads vividly in one or two sentences.\n"
        f"AREA: {area}\nYEAR: {year}\nAGE: {age}\nTITLE: {title}\n"
        f"CHOICES (context only, do not list them): {'; '.join(choices)}\n"
        f"FACTS: {_facts(facts)}\n"
        f"SOURCE TEXT: {text}"
    )


def outcome_prompt(
    *,
    event_title: str,
    event_text: str,
    choice: str,
    text: str,
    good: bool,
    year: int,
    age: int,
    facts: dict[str, float],
) -> str:
    return (
        "Rewrite this outcome text for the player's choice in one or two sentences.\n"
        f"YEAR: {year}\nAGE: {age}\nEVENT: {event_title}. {event_text}\nCHOICE: {choice}\n"
        f"RESULT WAS {'GOOD' if good else 'BAD'} FOR THE PLAYER\n"
        f"FACTS: {_facts(facts)}\n"
        f"SOURCE TEXT: {text}"
    )


def move_prompt(*, kind: str, headline: str, action: str, evidence: list[str], facts: dict[str, float]) -> str:
    lines = "\n".join(f"EVIDENCE {i + 1}: {t}" for i, t in enumerate(evidence))
    return (
        "Rewrite the wording of this money move card. Keep each field short.\n"
        "headline: one short sentence. action: a few words (under 8). evidence: the same number of items, "
        "in the same order, one sentence each.\n"
        f"MOVE KIND: {kind}\nFACTS: {_facts(facts)}\n"
        f"HEADLINE: {headline}\nACTION: {action}\n{lines}"
    )
