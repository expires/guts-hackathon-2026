"""Build the card a friend may see. Pure: snapshot and return series in, FriendCard out.

Privacy: the card holds scores (0-100), a growth index rebased to 100 and, only when asked, asset-class
percentages. The growth index replays the user's current ISA mix with a FIXED reference contribution,
so it depends on the mix only, never on how much the user saves or holds.
"""

from __future__ import annotations

from datetime import date

from lifeline_contracts.finance import FinanceSnapshot
from lifeline_contracts.friends import FriendCard
from lifeline_contracts.investing import IsaBacktestRequest, ReturnSeries
from lifeline_engine.money.habits import DEFAULT_WORST_DRAWDOWN, habit_factors
from lifeline_eval.isa_backtest import isa_backtest, weights_from_holdings, worst_drawdown_for

REFERENCE_CONTRIBUTION = 100.0
GROWTH_PERIOD = "full"


def growth_index(weights: dict[str, float], returns: ReturnSeries) -> float:
    req = IsaBacktestRequest(
        weights=weights, technique="dca", rebalance="annual", period=GROWTH_PERIOD,
        monthly_contribution=REFERENCE_CONTRIBUTION,
    )
    return round(isa_backtest(req, returns).index[-1], 1)


def mix_percentages(snap: FinanceSnapshot) -> dict[str, float] | None:
    total = sum(h.value for h in snap.holdings if h.value > 0)
    if total <= 0:
        return None
    out: dict[str, float] = {}
    for h in snap.holdings:
        if h.value > 0:
            out[h.asset_class] = out.get(h.asset_class, 0.0) + h.value / total * 100
    return {k: round(v, 1) for k, v in sorted(out.items())}


def build_card(
    snap: FinanceSnapshot, returns: ReturnSeries, *, friend_id: str, display_name: str, share_mix: bool
) -> FriendCard:
    weights = weights_from_holdings(snap.holdings)
    worst = worst_drawdown_for(weights, returns) if weights else DEFAULT_WORST_DRAWDOWN
    habits = habit_factors(snap, date.fromisoformat(snap.as_of), worst_drawdown=worst)
    return FriendCard(
        friend_id=friend_id,
        display_name=display_name,
        overall_score=habits.overall,
        factor_scores={f.id: f.score for f in habits.factors if f.score is not None},
        growth_index=growth_index(weights, returns) if weights else None,
        mix=mix_percentages(snap) if share_mix else None,
        data_status="mock" if snap.status == "mock" else "live",
        updated_at=f"{snap.as_of}T00:00:00Z",
    )


def rebased_score(theirs: int | None, mine: int | None) -> float | None:
    """Their overall score with mine as 100. None when either is missing or mine is 0."""
    if theirs is None or not mine:
        return None
    return round(theirs / mine * 100, 1)
