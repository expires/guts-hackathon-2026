"""Friends feature: what a user shares. Scores, a rebased index and opt-in percentages only.

FriendCard must never gain a pence/amount/balance field (enforced by tests).
"""

from pydantic import BaseModel

from playyourself.decision.backtest import BacktestRequest, backtest
from playyourself.decision.habits import habit_vector
from playyourself.decision.portfolio import allocation_pct, isa_weights, isa_worst_drawdown
from playyourself.decision.returns import ReturnSeries, load_returns
from playyourself.decision.scoring import overall_score
from playyourself.domain.models import Snapshot

# Used only when someone has no ISA holdings yet.
DEFAULT_WEIGHTS = {"global_equity": 0.8, "gilts": 0.2}
# Arbitrary fixed amount: the TWR index does not depend on it, so no user amount is involved.
_REFERENCE_CONTRIBUTION_PENCE = 10_000


class FriendCard(BaseModel):
    display_name: str
    overall_score: int | None
    factor_scores: dict[str, int | None]
    twr_index_final: float  # own ISA mix, DCA over "full", rebased to 100
    pie: dict[str, float] | None = None  # asset-class percentages, only when opted in


def twr_final(weights: dict[str, float], returns: ReturnSeries) -> float:
    """Final TWR index of a DCA backtest over "full". Depends on the mix only, not on amounts."""
    req = BacktestRequest(
        weights=weights,
        technique="dca",
        rebalance="annual",
        period="full",
        monthly_contribution_pence=_REFERENCE_CONTRIBUTION_PENCE,
    )
    return round(backtest(req, returns).index[-1], 1)


def share_card(
    name: str, snapshot: Snapshot, share_pie: bool, returns: ReturnSeries | None = None
) -> FriendCard:
    returns = returns or load_returns()
    hv = habit_vector(snapshot, worst_drawdown=isa_worst_drawdown(snapshot, returns))
    return FriendCard(
        display_name=name,
        overall_score=overall_score(hv),
        factor_scores={k: f.score for k, f in hv.factors.items()},
        twr_index_final=twr_final(isa_weights(snapshot) or DEFAULT_WEIGHTS, returns),
        pie=(allocation_pct(snapshot) or None) if share_pie else None,
    )
