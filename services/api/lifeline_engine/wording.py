"""Shared plain-English wording for engine evidence. Pure."""

from __future__ import annotations

from typing import Literal

Level = Literal["low", "medium", "high"]

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


# ADR 0053 bug 4: confidence level from the share AND the sample behind it.
# The sample counts INDEPENDENT cases (W-V2-3): matched past periods or years, or months of the user's own data.
# Twins in one period share that period's rates, so they are not independent and are not counted.
HIGH_MIN_SAMPLE = 8  # independent cases needed for "high"
MEDIUM_MIN_SAMPLE = 5  # independent cases needed for "medium"
HIGH_MIN_SHARE = 0.7  # share of cases where the move did better, needed for "high"
MEDIUM_MIN_SHARE = 0.55  # share needed for "medium"


def confidence_level(share: float, sample: int | None, deterministic: bool = False) -> Level:
    """'high' only with sample >= HIGH_MIN_SAMPLE and share >= HIGH_MIN_SHARE; 'medium' with sample >=
    MEDIUM_MIN_SAMPLE and share >= MEDIUM_MIN_SHARE; else 'low'. A deterministic gain (arithmetic on the user's
    own data, not a sampled outcome, e.g. a cancelled subscription) is 'high' with no sample."""
    if deterministic:
        return "high"
    if sample is None:
        return "low"
    if sample >= HIGH_MIN_SAMPLE and share >= HIGH_MIN_SHARE:
        return "high"
    if sample >= MEDIUM_MIN_SAMPLE and share >= MEDIUM_MIN_SHARE:
        return "medium"
    return "low"


def with_sample(label: str, sample: int | None, unit: str = "") -> str:
    """'7 in 10 twins in similar past periods did better (sample: 5 past periods)'."""
    if sample is None:
        return label
    return f"{label} (sample: {sample} {unit})" if unit else f"{label} (sample {sample})"
