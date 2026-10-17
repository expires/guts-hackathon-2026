"""ISA backtest: replay a mix of assets through a named past period. Pure: no I/O, no clock, no global RNG.

Monthly order: contribution (start of month) -> invest at target weights -> apply returns -> rebalance.
The index is time-weighted (TWR), rebased to 100. Money is GBP floats.
Periods are inclusive month bounds on the (synthetic) return series.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from lifeline_contracts.accounts import Holding
from lifeline_contracts.investing import (
    ASSETS,
    IsaBacktestMetrics,
    IsaBacktestRequest,
    IsaBacktestResult,
    ReturnSeries,
)

FloatArray = NDArray[np.float64]

# Inclusive month bounds. periods.py matches macro years only, so these named replay windows live here.
PERIODS: dict[str, tuple[str, str]] = {
    "gfc_2008": ("2007-10", "2012-12"),
    "covid_2020": ("2020-01", "2021-12"),
    "rates_2022": ("2021-12", "2024-06"),
    "full": ("2000-01", "2026-09"),
}
PERIOD_LABELS: dict[str, str] = {
    "gfc_2008": "the 2008 financial crisis",
    "covid_2020": "the 2020 Covid crash",
    "rates_2022": "the 2022 rate rises",
    "full": "the whole period",
}
NAMED_PERIODS: tuple[str, ...] = tuple(p for p in PERIODS if p != "full")

UK_REGIONS = frozenset({"UK", "GB", "UNITED KINGDOM"})
_ASSET_MAP = {"equity": "global_equity", "bond": "gilts", "cash": "cash"}


def weights_from_holdings(holdings: Sequence[Holding]) -> dict[str, float] | None:
    """Current ISA mix mapped to backtest assets and normalised. None when there is no value held.

    UK-region equity -> uk_equity, bond -> gilts, cash -> cash, anything else -> global_equity.
    """
    total = sum(h.value for h in holdings if h.value > 0)
    if total <= 0:
        return None
    out: dict[str, float] = {}
    for h in holdings:
        if h.value <= 0:
            continue
        if h.asset_class == "equity" and (h.region or "").upper() in UK_REGIONS:
            asset = "uk_equity"
        else:
            asset = _ASSET_MAP.get(h.asset_class, "global_equity")
        out[asset] = out.get(asset, 0.0) + h.value / total
    s = sum(out.values())
    return {k: v / s for k, v in out.items()}


# ---------- series helpers ----------


def slice_series(rs: ReturnSeries, start: str, end: str) -> ReturnSeries:
    """Inclusive month range. Raises ValueError if the bounds are outside the series."""
    if start not in rs.months or end not in rs.months:
        raise ValueError(f"period {start}..{end} outside available data")
    i0, i1 = rs.months.index(start), rs.months.index(end)
    if i1 < i0:
        raise ValueError("end before start")
    return rs.model_copy(update={"months": rs.months[i0 : i1 + 1], "returns": rs.returns[i0 : i1 + 1]})


def matrix(rs: ReturnSeries) -> FloatArray:
    """(T, len(ASSETS)) array with columns in ASSETS order."""
    cols = [rs.assets.index(a) for a in ASSETS]
    arr = np.asarray(rs.returns, dtype=np.float64).reshape(len(rs.months), len(rs.assets))
    out: FloatArray = arr[:, cols]
    return out


def max_drawdown(index: Sequence[float]) -> tuple[float, int | None]:
    """(max drawdown as a positive fraction, months from trough to recovery or None)."""
    x = np.asarray(index, dtype=np.float64)
    if len(x) == 0:
        return 0.0, None
    peaks = np.maximum.accumulate(x)
    dd = 1.0 - x / peaks
    trough = int(np.argmax(dd))
    mdd = float(dd[trough])
    if mdd <= 0:
        return 0.0, 0
    after = np.nonzero(x[trough:] >= peaks[trough])[0]
    return mdd, (int(after[0]) if len(after) else None)


def twr_index(values: Sequence[float], flows: Sequence[float]) -> list[float]:
    """Chain-linked TWR index from end-of-month values and start-of-month flows (starts at 100).

    Return_t = V_t / (V_{t-1} + flow_t) - 1, with V_{-1} = 0.
    """
    out = [100.0]
    prev = 0.0
    for v, f in zip(values, flows, strict=True):
        base = prev + f
        r = v / base - 1.0 if base > 0 else 0.0
        out.append(out[-1] * (1.0 + r))
        prev = v
    return out


def _prev_month(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    y, mo = (y - 1, 12) if mo == 1 else (y, mo - 1)
    return f"{y:04d}-{mo:02d}"


def _tax_year(m: str) -> int:
    y, mo = int(m[:4]), int(m[5:7])
    return y if mo >= 4 else y - 1


def contribution_schedule(req: IsaBacktestRequest, months: Sequence[str]) -> list[float]:
    """Contribution (GBP) at the start of each month, capped per tax year (April to March).

    DCA: the monthly amount, capped by the remaining allowance. Lump sum: the same total DCA would
    contribute, invested as early as possible: at month 0 and each later April, as much as the
    allowance permits, until that total is reached.
    """
    allowance = req.isa_allowance
    dca: list[float] = []
    used: dict[int, float] = {}
    for m in months:
        ty = _tax_year(m)
        c = max(min(req.monthly_contribution, allowance - used.get(ty, 0.0)), 0.0)
        used[ty] = used.get(ty, 0.0) + c
        dca.append(c)
    if req.technique == "dca":
        return dca
    remaining = sum(dca)
    used = {}
    out: list[float] = []
    for i, m in enumerate(months):
        c = 0.0
        if i == 0 or m.endswith("-04"):
            ty = _tax_year(m)
            c = max(min(allowance - used.get(ty, 0.0), remaining), 0.0)
            used[ty] = used.get(ty, 0.0) + c
            remaining -= c
        out.append(c)
    return out


def _irr_annual(flows: Sequence[float], final: float) -> float | None:
    if sum(flows) <= 0:
        return None
    n = len(flows)
    f = np.asarray(flows, dtype=np.float64)
    t = np.arange(n)

    def npv(r: float) -> float:
        return float(-(f * (1 + r) ** (n - t)).sum() + final)

    lo, hi = -0.5, 0.5
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return float((1 + (lo + hi) / 2) ** 12 - 1)


def run_backtest(req: IsaBacktestRequest, rs: ReturnSeries, period: str = "custom") -> IsaBacktestResult:
    """Run the request over every month of `rs` (already sliced to the period)."""
    w = np.array([req.weights.get(a, 0.0) for a in ASSETS], dtype=np.float64)
    data = matrix(rs)
    contribs = contribution_schedule(req, rs.months)
    hold = np.zeros(len(ASSETS))
    values: list[float] = []
    for i, m in enumerate(rs.months):
        hold = (hold + contribs[i] * w) * (1.0 + data[i])
        total = float(hold.sum())
        if total > 0:
            do = False
            if req.rebalance == "annual":
                do = m.endswith("-04")
            elif req.rebalance == "threshold":
                do = bool(np.max(np.abs(hold / total - w)) * 100 > req.threshold_pp)
            if do:
                hold = total * w
        values.append(float(hold.sum()))
    index = twr_index(values, contribs)
    mdd, rec = max_drawdown(index)
    idx = np.asarray(index)
    r = idx[1:] / idx[:-1] - 1
    n = len(r)
    cagr = float((idx[-1] / 100.0) ** (12 / n) - 1) if n else 0.0
    vol = float(np.std(r, ddof=1) * np.sqrt(12)) if n > 1 else 0.0
    worst = float(np.min(idx[12:] / idx[:-12] - 1)) if n >= 12 else float(idx[-1] / 100.0 - 1)
    final = values[-1] if values else 0.0
    return IsaBacktestResult(
        period=period,
        label=PERIOD_LABELS.get(period, period),
        months=[_prev_month(rs.months[0]), *rs.months],
        index=index,
        metrics=IsaBacktestMetrics(
            cagr=cagr, volatility=vol, max_drawdown=mdd, months_to_recover=rec, worst_12m=worst
        ),
        contributed=round(float(sum(contribs)), 2),
        final_value=round(final, 2),
        money_weighted_return=_irr_annual(contribs, final),
        data_status=rs.data_status,
        data_label=rs.label,
    )


def isa_backtest(req: IsaBacktestRequest, returns: ReturnSeries) -> IsaBacktestResult:
    if req.period not in PERIODS:
        raise ValueError(f"unknown period {req.period!r}")
    start, end = PERIODS[req.period]
    return run_backtest(req, slice_series(returns, start, end), req.period)


def isa_compare(reqs: Sequence[IsaBacktestRequest], returns: ReturnSeries) -> list[IsaBacktestResult]:
    return [isa_backtest(r, returns) for r in reqs]


def period_drawdowns(weights: Mapping[str, float], returns: ReturnSeries) -> dict[str, float]:
    """Max drawdown of a lump-sum, no-rebalance mix over each named period."""
    w = np.array([weights.get(a, 0.0) for a in ASSETS], dtype=np.float64)
    out: dict[str, float] = {}
    for name in NAMED_PERIODS:
        start, end = PERIODS[name]
        seg = matrix(slice_series(returns, start, end))
        hold = w.copy()
        path = [1.0]
        for row in seg:
            hold = hold * (1.0 + row)
            path.append(float(hold.sum()))
        out[name] = max_drawdown(path)[0]
    return out


def worst_drawdown_for(weights: Mapping[str, float], returns: ReturnSeries) -> float:
    """Worst drawdown of the mix across the named periods (positive fraction)."""
    return max(period_drawdowns(weights, returns).values(), default=0.0)
