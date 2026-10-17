"""Analog-based scenarios: run the user's ISA strategy forward from similar past periods.

Pure: no I/O, no clock, no global RNG. Similar means the trailing 12 months looked alike (a 60/40
equity and gilt blend's return and volatility, and the gilt return). Not a forecast.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from lifeline_contracts.investing import (
    ASSETS,
    SCENARIO_LABEL,
    IsaBacktestRequest,
    IsaScenariosResult,
    ReturnSeries,
    ScenarioFan,
    ScenarioPath,
)
from lifeline_eval.isa_backtest import matrix, run_backtest, slice_series

FloatArray = NDArray[np.float64]
_WINDOW = 12
MIN_ANALOGS = 3


def _features(returns: ReturnSeries) -> tuple[FloatArray, NDArray[np.bool_]]:
    """Standardised features (T, 3) and a validity mask. Row i uses months i-11..i."""
    m = matrix(returns)
    eq = m[:, ASSETS.index("global_equity")]
    gl = m[:, ASSETS.index("gilts")]
    blend = 0.6 * eq + 0.4 * gl
    t = len(blend)
    feats = np.full((t, 3), np.nan)
    for i in range(_WINDOW - 1, t):
        b = blend[i - _WINDOW + 1 : i + 1]
        g = gl[i - _WINDOW + 1 : i + 1]
        feats[i] = [np.prod(1 + b) - 1, np.std(b, ddof=1) * np.sqrt(12), np.prod(1 + g) - 1]
    valid: NDArray[np.bool_] = ~np.isnan(feats).any(axis=1)
    mu = feats[valid].mean(axis=0)
    sd = feats[valid].std(axis=0)
    sd[sd == 0] = 1.0
    z: FloatArray = (feats - mu) / sd
    return z, valid


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
    cands = [j for j in range(t) if valid[j] and j + horizon_months <= t - 1 and j + horizon_months < a]
    cands.sort(key=lambda j: (float(np.linalg.norm(z[j] - z[a])), j))
    picked: list[int] = []
    for j in cands:
        if all(abs(j - p) >= min_gap_months for p in picked):
            picked.append(j)
            if len(picked) == k:
                break
    return [returns.months[j] for j in picked]


def isa_scenarios(
    req: IsaBacktestRequest,
    returns: ReturnSeries,
    as_of_month: str | None = None,
    k: int = 8,
    horizon_months: int = 36,
) -> IsaScenariosResult:
    """Paths and a p10/p50/p90 fan. The strategy is always run as DCA over each analog."""
    as_of = as_of_month or returns.months[-1]
    analogs = find_analogs(returns, as_of, k=k, horizon_months=horizon_months)
    if len(analogs) < MIN_ANALOGS:
        raise ValueError("fewer than 3 analog periods available")
    dca = req.model_copy(update={"technique": "dca"})
    paths: list[ScenarioPath] = []
    for m in analogs:
        j = returns.months.index(m)
        seg = slice_series(returns, returns.months[j + 1], returns.months[j + horizon_months])
        paths.append(ScenarioPath(start_month=m, index=run_backtest(dca, seg).index))
    arr = np.array([p.index for p in paths])
    p10, p50, p90 = (np.percentile(arr, q, axis=0).tolist() for q in (10, 50, 90))
    return IsaScenariosResult(
        paths=paths,
        fan=ScenarioFan(p10=p10, p50=p50, p90=p90),
        horizon_months=horizon_months,
        label=SCENARIO_LABEL,
        data_status=returns.data_status,
        data_label=returns.label,
    )
