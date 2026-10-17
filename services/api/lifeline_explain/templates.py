"""Deterministic fallback. The sim and engine write the template text; this layer only guarantees it is served
as-is with `text_source="template"` when the LLM is off, slow, failing, or rejected by the verifier."""

from __future__ import annotations

import re

from lifeline_contracts.domain import Event, Outcome

_WS = re.compile(r"\s+")


def template_event(event: Event) -> Event:
    text = event.text.strip() or f"{event.title}."
    return event.model_copy(update={"text": text, "text_source": "template"})


def template_outcome(outcome: Outcome) -> Outcome:
    text = outcome.text.strip() or ("That went well." if outcome.good else "That did not go well.")
    return outcome.model_copy(update={"text": text, "text_source": "template"})


def clean(text: str, source: str, max_len: int | None = None) -> str | None:
    """Normalise LLM text. Return None when it is unusable (empty or far longer than the source)."""
    out = _WS.sub(" ", text).strip().strip('"').strip()
    out = out.replace(" — ", ", ").replace("—", ", ")
    if not out:
        return None
    limit = max_len if max_len is not None else max(2 * len(source), len(source) + 160)
    if len(out) > limit:
        return None
    return out
