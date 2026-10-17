"""Fixed, documented bands mapping raw habit factors to 0-100 scores.

Bands are (raw, score) knots; scores are piecewise-linear between knots and
clamped to the first/last knot outside the range. No population data is used,
so scoring is deterministic and can run on-device.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playyourself.decision.habits import HabitVector

_RUNWAY: list[tuple[float, int]] = [(0, 0), (1, 20), (3, 50), (6, 80), (12, 100)]

BANDS: dict[str, list[tuple[float, int]]] = {
    "savings_rate": [(-0.1, 0), (0.0, 20), (0.1, 50), (0.2, 75), (0.35, 100)],
    "runway_months": _RUNWAY,
    "spend_stability": [(0.0, 0), (1.0, 100)],
    # lower is better
    "discretionary_share": [(0.1, 100), (0.25, 70), (0.4, 40), (0.6, 0)],
    "subscription_creep": [(0.0, 100), (0.1, 70), (0.25, 40), (0.5, 0)],
    "isa_diversification": [(0.1, 100), (0.2, 80), (0.35, 50), (0.6, 20), (1.0, 0)],
    "shock_resilience": _RUNWAY,
}


def _interp(knots: list[tuple[float, int]], x: float) -> float:
    if x <= knots[0][0]:
        return float(knots[0][1])
    if x >= knots[-1][0]:
        return float(knots[-1][1])
    for (x0, y0), (x1, y1) in zip(knots, knots[1:], strict=False):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return float(knots[-1][1])  # pragma: no cover


def score_factor(name: str, raw: float | None) -> int | None:
    """Map a raw factor value to a 0-100 int; None passes through."""
    if raw is None:
        return None
    return round(_interp(BANDS[name], raw))


def overall_score(hv: HabitVector) -> int | None:
    """Rounded mean of the non-null factor scores (None if there are none)."""
    scores = [f.score for f in hv.factors.values() if f.score is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores))


def rebase_to_100(values: Sequence[float]) -> list[float]:
    """Rebase a series so the first non-zero value becomes 100.

    Entries before the first non-zero value stay 0.0. All-zero/empty input
    returns zeros/empty.
    """
    base = next((v for v in values if v != 0), None)
    if base is None:
        return [0.0 for _ in values]
    return [v / base * 100 for v in values]
