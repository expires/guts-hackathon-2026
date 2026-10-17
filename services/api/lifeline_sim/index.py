"""The INDEX score. Formula and weights: `config/index.toml` and `docs/index.md`."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources


@dataclass(frozen=True)
class IndexWeights:
    base: float
    r_weight: float
    missed_payment_penalty: float
    drawdown_penalty: float
    floor: float
    min_income0: float


@lru_cache(maxsize=1)
def load_weights() -> IndexWeights:
    raw = resources.files("lifeline_sim.config").joinpath("index.toml").read_text(encoding="utf-8")
    t = tomllib.loads(raw)["index"]
    return IndexWeights(
        base=float(t["base"]),
        r_weight=float(t["r_weight"]),
        missed_payment_penalty=float(t["missed_payment_penalty"]),
        drawdown_penalty=float(t["drawdown_penalty"]),
        floor=float(t["floor"]),
        min_income0=float(t["min_income0"]),
    )


def income_base(income0: float, w: IndexWeights) -> float:
    return max(income0, w.min_income0)


def r_value(net_worth: float, net_worth0: float, income0: float, w: IndexWeights | None = None) -> float:
    """R(t) = (NW(t) - NW(0)) / Income(0). Income(0) has a floor of `min_income0`."""
    w = w or load_weights()
    return (net_worth - net_worth0) / income_base(income0, w)


def drawdown_fraction(peak: float, net_worth: float, income0: float, w: IndexWeights | None = None) -> float:
    """Fall from the running peak, as a fraction of max(peak, Income(0)). Clamped to [0, 1].

    The denominator uses Income(0) when the peak is small or negative, so a person in debt
    is measured against their pay, and a wealthy person against their wealth.
    """
    w = w or load_weights()
    denom = max(peak, income_base(income0, w))
    return max(0.0, min(1.0, (peak - net_worth) / denom))


def index_value(
    r_player: float,
    r_autopilot: float,
    missed_payments: int,
    max_drawdown: float,
    missed_autopilot: int = 0,
    drawdown_autopilot: float = 0.0,
    w: IndexWeights | None = None,
) -> float:
    """ADR 0013: penalties are relative to the autopilot twin. Copying the twin gives exactly `base`.

    With a twin that has no missed payments and no drawdown, this equals the BUILD_SPEC formula.
    """
    w = w or load_weights()
    raw = (
        w.base * (1 + w.r_weight * (r_player - r_autopilot))
        - w.missed_payment_penalty * (missed_payments - missed_autopilot)
        - w.drawdown_penalty * (max_drawdown - drawdown_autopilot)
    )
    return max(w.floor, raw)
