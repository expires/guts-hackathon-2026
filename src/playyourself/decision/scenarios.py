"""Analog-based "future insight": run the user's strategy forward from similar past periods."""

import numpy as np
from pydantic import BaseModel

from playyourself.decision.backtest import BacktestRequest, _run
from playyourself.decision.returns import ReturnSeries

LABEL = "Modelled scenarios from similar past periods. Not a forecast. Not financial advice."
_WINDOW = 12


class Path(BaseModel):
    start_month: str  # the analog month; the strategy runs over the following months
    index: list[float]  # TWR rebased to 100, horizon+1 points


class Fan(BaseModel):
    p10: list[float]
    p50: list[float]
    p90: list[float]


class ScenarioResult(BaseModel):
    paths: list[Path]
    fan: Fan
    label: str = LABEL


def _features(returns: ReturnSeries) -> tuple[np.ndarray, np.ndarray]:
    """Standardised features (T, 3) and a validity mask. Row i uses months i-11..i."""
    eq = returns.column("global_equity")
    gl = returns.column("gilts")
    blend = 0.6 * eq + 0.4 * gl
    t = len(blend)
    feats = np.full((t, 3), np.nan)
    for i in range(_WINDOW - 1, t):
        b = blend[i - _WINDOW + 1 : i + 1]
        g = gl[i - _WINDOW + 1 : i + 1]
        feats[i] = [np.prod(1 + b) - 1, np.std(b, ddof=1) * np.sqrt(12), np.prod(1 + g) - 1]
    valid = ~np.isnan(feats).any(axis=1)
    mu = feats[valid].mean(axis=0)
    sd = feats[valid].std(axis=0)
    sd[sd == 0] = 1.0
    return (feats - mu) / sd, valid


def find_analogs(
    returns: ReturnSeries,
    as_of_month: str,
    k: int = 8,
    horizon_months: int = 36,
    min_gap_months: int = 12,
) -> list[str]:
    if as_of_month not in returns.months:
        raise ValueError(f"unknown as_of_month {as_of_month!r}")
    a = returns.months.index(as_of_month)
    z, valid = _features(returns)
    if not valid[a]:
        raise ValueError("not enough history before as_of_month")
    t = len(returns.months)
    cands = [
        j for j in range(t) if valid[j] and j + horizon_months <= t - 1 and j + horizon_months < a
    ]
    cands.sort(key=lambda j: (float(np.linalg.norm(z[j] - z[a])), j))
    picked: list[int] = []
    for j in cands:
        if all(abs(j - p) >= min_gap_months for p in picked):
            picked.append(j)
            if len(picked) == k:
                break
    return [returns.months[j] for j in picked]


def scenarios(
    req: BacktestRequest,
    returns: ReturnSeries,
    as_of_month: str | None = None,
    k: int = 8,
    horizon_months: int = 36,
) -> ScenarioResult:
    as_of = as_of_month or returns.months[-1]
    analogs = find_analogs(returns, as_of, k=k, horizon_months=horizon_months)
    if len(analogs) < 3:
        raise ValueError("fewer than 3 analog periods available")
    dca = req.model_copy(update={"technique": "dca"})
    paths: list[Path] = []
    for m in analogs:
        j = returns.months.index(m)
        seg = returns.slice(returns.months[j + 1], returns.months[j + horizon_months])
        paths.append(Path(start_month=m, index=_run(dca, seg).index))
    arr = np.array([p.index for p in paths])
    p10, p50, p90 = (np.percentile(arr, q, axis=0).tolist() for q in (10, 50, 90))
    return ScenarioResult(paths=paths, fan=Fan(p10=p10, p50=p50, p90=p90))
