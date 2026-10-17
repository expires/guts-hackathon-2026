"""Public API of the explain layer (implements lifeline_contracts.interfaces.ExplainAPI, plus move_text).

All functions are async and never raise. On any failure they return the input text unchanged
(`text_source="template"` for Event and Outcome).

Wiring (W4): call the module functions directly. The default Explainer is built lazily from the environment
(ANTHROPIC_API_KEY, LLM_MODEL, LLM_TIMEOUT_SECONDS, REDIS_URL, LLM_ENABLED). Tests call `set_explainer(...)`.
"""

from __future__ import annotations

from lifeline_contracts.domain import Event, Outcome
from lifeline_contracts.next_move import Move
from lifeline_explain.service import Explainer

_explainer: Explainer | None = None


def get_explainer() -> Explainer:
    global _explainer
    if _explainer is None:
        _explainer = Explainer.from_env()
    return _explainer


def set_explainer(explainer: Explainer | None) -> None:
    """Replace the default Explainer (tests), or pass None to rebuild it from the environment on next use."""
    global _explainer
    _explainer = explainer


async def event_text(event: Event) -> Event:
    """Reword `event.text`. Returns a new Event with text_source 'llm' or 'template'."""
    return await get_explainer().event_text(event)


async def outcome_text(event: Event, outcome: Outcome) -> Outcome:
    """Reword `outcome.text` in the context of `event`. Returns a new Outcome."""
    return await get_explainer().outcome_text(event, outcome)


async def move_text(move: Move) -> Move:
    """Reword `headline` and each evidence `text` only (ADR 0018). `action` is never changed: it must match
    the option label exactly. Numbers, facts, options and confidence_label are never changed.
    A field whose new wording fails the verifier keeps its original text."""
    return await get_explainer().move_text(move)
