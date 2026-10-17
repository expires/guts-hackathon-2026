"""Shared plain-English wording for engine evidence. Pure."""

from __future__ import annotations

TWIN_TAIL = "twins in similar past periods did better"


def confidence_label(confidence: float) -> str:
    """'7 in 10 twins in similar past periods did better'. Never '10 in 10' or '0 in 10':
    1.0 gives 'All', a value that rounds to 10 gives 'More than 9 in 10', 0 gives 'No',
    a value that rounds to 0 gives 'Fewer than 1 in 10'."""
    n = int(round(confidence * 10))
    if confidence >= 1.0:
        return f"All {TWIN_TAIL}"
    if n >= 10:
        return f"More than 9 in 10 {TWIN_TAIL}"
    if confidence <= 0.0:
        return f"No {TWIN_TAIL}"
    if n == 0:
        return f"Fewer than 1 in 10 {TWIN_TAIL}"
    return f"{n} in 10 {TWIN_TAIL}"


def best_choice_label(share: float) -> str:
    """ADR 0023: confidence of a multi-option move. 'In 6 of 10 similar cases this was the best choice'.
    Same cap rules as confidence_label."""
    tail = "similar cases this was the best choice"
    n = int(round(share * 10))
    if share >= 1.0:
        return f"In all {tail}"
    if n >= 10:
        return f"In more than 9 of 10 {tail}"
    if share <= 0.0:
        return f"In no {tail}"
    if n == 0:
        return f"In fewer than 1 of 10 {tail}"
    return f"In {n} of 10 {tail}"
