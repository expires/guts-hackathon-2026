"""Investment concentration for the `spread_investments` move (ADR 0042). Pure: no I/O, no clock, no RNG.

FinanceSnapshot has no holdings field yet (Trading212 ISA data lands later), so the engine takes a small typed
input: `Holding` (name, value). The caller passes holdings to `next_move(..., holdings=...)`.

Model (labelled assumptions in trade_offs.TYPICAL):
- One company's shares swing about S = 35% a year (standard deviation), a broad fund about B = 15%.
- Treat a share as the market plus its own risk: own-risk variance D^2 = S^2 - B^2.
- With the same average return, more swing lowers the typical (median) result by about half the variance each
  year ("volatility drag"). Moving `moved` GBP from the share to a broad fund adds about moved * D^2 / 2 a year.
- Over T years, the log return of the fund minus the share has mean D^2 T / 2 and standard deviation D sqrt(T).
  confidence = P(fund beats share) = Phi(D sqrt(T) / 2).
- Worst case: a good year for the share (about 1 in 10, z = 1.28): the move gives up moved * 1.28 * D.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from lifeline_engine.trade_offs import TYPICAL

CONCENTRATION_LIMIT_PCT = 40.0  # a holding above this share of the ISA triggers the move
MIN_ISA_VALUE = 1_000.0  # ignore very small portfolios
SPREAD_HORIZON = 5  # years
GOOD_YEAR_Z = 1.28  # about a 1 in 10 good year


@dataclass(frozen=True)
class Holding:
    name: str
    value: float  # GBP market value today, >= 0


@dataclass(frozen=True)
class Concentration:
    name: str
    largest: float
    total: float
    share_pct: float  # largest / total * 100, rounded to a whole number
    moved: float  # GBP to move so the largest is CONCENTRATION_LIMIT_PCT of the total


@dataclass(frozen=True)
class SpreadScore:
    impact_per_year: float
    worst_case_per_year: float
    confidence: float


def concentration(holdings: Sequence[Holding]) -> Concentration | None:
    """The largest holding, when it is more than CONCENTRATION_LIMIT_PCT of a portfolio worth MIN_ISA_VALUE or more.
    Ties: the first by name."""
    live = [h for h in holdings if h.value > 0]
    total = sum(h.value for h in live)
    if total < MIN_ISA_VALUE or len(live) == 0:
        return None
    top = sorted(live, key=lambda h: (-h.value, h.name))[0]
    share = top.value / total * 100
    if share <= CONCENTRATION_LIMIT_PCT:
        return None
    moved = top.value - CONCENTRATION_LIMIT_PCT / 100 * total
    return Concentration(top.name, top.value, total, float(round(share)), moved)


def own_risk() -> float:
    """D = sqrt(S^2 - B^2) as a fraction a year."""
    s = TYPICAL["single_share_swing_pct"].low / 100
    b = TYPICAL["broad_fund_swing_pct"].low / 100
    return math.sqrt(max(0.0, s * s - b * b))


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def spread_score(moved: float, horizon: int = SPREAD_HORIZON) -> SpreadScore:
    d = own_risk()
    return SpreadScore(
        impact_per_year=moved * d * d / 2,
        worst_case_per_year=-moved * GOOD_YEAR_Z * d,
        confidence=_phi(d * math.sqrt(horizon) / 2),
    )
