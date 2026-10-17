"""Small portfolio helpers shared by the API and friends feature. Pure functions."""

from collections import defaultdict

from playyourself.decision.backtest import worst_drawdown_across_periods
from playyourself.decision.returns import ReturnSeries
from playyourself.domain.models import Snapshot

FALLBACK_DRAWDOWN = 0.35
_ASSET_MAP = {"equity": "global_equity", "bond": "gilts", "cash": "cash"}


def allocation_pct(snapshot: Snapshot) -> dict[str, float]:
    """Holdings by asset_class as percentages (sum ~100). Empty if there are no holdings."""
    total = sum(h.value_pence for h in snapshot.holdings)
    if total <= 0:
        return {}
    by: dict[str, int] = defaultdict(int)
    for h in snapshot.holdings:
        by[h.asset_class] += h.value_pence
    return {k: round(v / total * 100, 1) for k, v in sorted(by.items())}


def isa_weights(snapshot: Snapshot) -> dict[str, float] | None:
    """The user's current ISA mix mapped to backtest assets. None if there are no holdings.

    UK-region equities map to uk_equity; other asset classes fall back to global_equity.
    """
    total = sum(h.value_pence for h in snapshot.holdings)
    if total <= 0:
        return None
    weights: dict[str, float] = defaultdict(float)
    for h in snapshot.holdings:
        if h.asset_class == "equity" and (h.region or "").upper() in {"UK", "GB"}:
            asset = "uk_equity"
        else:
            asset = _ASSET_MAP.get(h.asset_class, "global_equity")
        weights[asset] += h.value_pence / total
    # Normalise away float error so BacktestRequest's sum-to-1 check passes.
    s = sum(weights.values())
    return {k: v / s for k, v in weights.items()}


def isa_worst_drawdown(snapshot: Snapshot, returns: ReturnSeries) -> float:
    """Worst replay drawdown of the user's current ISA mix, mapped to backtest assets."""
    weights = isa_weights(snapshot)
    if weights is None:
        return FALLBACK_DRAWDOWN
    return worst_drawdown_across_periods(weights, returns)
