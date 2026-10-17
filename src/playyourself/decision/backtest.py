"""Pure-numpy monthly backtest.

Monthly order: contribution (start of month) -> invest at target weights -> apply returns
-> rebalance. Index/metrics are time-weighted (TWR) and safe to share; `LocalResult`
holds pound values and money-weighted return and must NEVER leave the device.
"""

from typing import Literal

import numpy as np
from pydantic import BaseModel, Field, field_validator

from playyourself.decision.returns import ASSETS, PERIODS, ReturnSeries


class BacktestRequest(BaseModel):
    weights: dict[str, float]
    technique: Literal["dca", "lump_sum"] = "dca"
    rebalance: Literal["none", "annual", "threshold"] = "annual"
    threshold_pp: float = 5.0
    period: str = "gfc_2008"
    monthly_contribution_pence: int = Field(gt=0)
    isa_allowance_pence: int = 2_000_000

    @field_validator("weights")
    @classmethod
    def _valid_weights(cls, w: dict[str, float]) -> dict[str, float]:
        bad = set(w) - set(ASSETS)
        if bad:
            raise ValueError(f"unknown assets: {sorted(bad)}")
        if any(v < 0 for v in w.values()):
            raise ValueError("weights must be non-negative")
        if abs(sum(w.values()) - 1.0) > 1e-6:
            raise ValueError("weights must sum to 1")
        return w


class Metrics(BaseModel):
    """All computed on the TWR index; safe to share."""

    cagr: float
    volatility_annual: float
    max_drawdown: float  # positive fraction
    months_to_recover: int | None  # trough -> new peak; None if never recovered
    worst_12m: float


class LocalResult(BaseModel):
    """LOCAL ONLY: pound values derived from the user's own contributions.

    Must never be sent to the backend, friends or the explainer.
    """

    contributed_pence: int
    final_value_pence: int
    value_pence: list[int]  # end-of-month portfolio value, aligned with months[1:]
    money_weighted_return_annual: float | None


class BacktestResult(BaseModel):
    months: list[str]  # months[0] = month before start (index base 100); then each month end
    index: list[float]
    metrics: Metrics
    local: LocalResult


def max_drawdown(index) -> tuple[float, int | None]:
    """(max drawdown as positive fraction, months from trough to recovery or None)."""
    x = np.asarray(index, dtype=float)
    if len(x) == 0:
        return 0.0, None
    peaks = np.maximum.accumulate(x)
    dd = 1.0 - x / peaks
    trough = int(np.argmax(dd))
    mdd = float(dd[trough])
    if mdd <= 0:
        return 0.0, 0
    peak_val = peaks[trough]
    after = np.nonzero(x[trough:] >= peak_val)[0]
    return mdd, (int(after[0]) if len(after) else None)


def twr_index(values, flows) -> list[float]:
    """Chain-linked TWR index from end-of-month `values` and start-of-month `flows`.

    Return_t = V_t / (V_{t-1} + flow_t) - 1, with V_{-1} = 0. Returns len(values)+1 points
    starting at 100.
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


def contribution_schedule(req: BacktestRequest, months: list[str]) -> list[int]:
    """Contribution (pence) at the start of each month, capped per tax year (Apr..Mar).

    DCA: monthly amount, capped by remaining allowance. Lump sum: the same total DCA would
    contribute is invested as early as possible: at month 0 and at the start of each later
    tax year (April), as much as the allowance permits, until that total is reached.
    """
    allowance = req.isa_allowance_pence
    dca: list[int] = []
    used: dict[int, int] = {}
    for m in months:
        ty = _tax_year(m)
        c = min(req.monthly_contribution_pence, allowance - used.get(ty, 0))
        c = max(c, 0)
        used[ty] = used.get(ty, 0) + c
        dca.append(c)
    if req.technique == "dca":
        return dca
    remaining = sum(dca)
    used = {}
    out: list[int] = []
    for i, m in enumerate(months):
        c = 0
        if i == 0 or m.endswith("-04"):
            ty = _tax_year(m)
            c = max(min(allowance - used.get(ty, 0), remaining), 0)
            used[ty] = used.get(ty, 0) + c
            remaining -= c
        out.append(c)
    return out


def _irr_annual(flows: list[int], final: float) -> float | None:
    if sum(flows) <= 0:
        return None
    n = len(flows)
    f = np.asarray(flows, dtype=float)
    t = np.arange(n)

    def npv(r: float) -> float:
        return float(-(f * (1 + r) ** (n - t)).sum() + final)  # compounded to the end

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


def _run(req: BacktestRequest, rs: ReturnSeries) -> BacktestResult:
    cols = [rs.assets.index(a) for a in ASSETS]
    w = np.array([req.weights.get(a, 0.0) for a in ASSETS])
    data = rs.data[:, cols]
    contribs = contribution_schedule(req, rs.months)
    hold = np.zeros(len(ASSETS))
    values: list[float] = []
    for i, m in enumerate(rs.months):
        hold = hold + contribs[i] * w
        hold = hold * (1.0 + data[i])
        total = hold.sum()
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
    return BacktestResult(
        months=[_prev_month(rs.months[0]), *rs.months],
        index=index,
        metrics=Metrics(
            cagr=cagr,
            volatility_annual=vol,
            max_drawdown=mdd,
            months_to_recover=rec,
            worst_12m=worst,
        ),
        local=LocalResult(
            contributed_pence=int(sum(contribs)),
            final_value_pence=int(round(final)),
            value_pence=[int(round(v)) for v in values],
            money_weighted_return_annual=_irr_annual(contribs, final),
        ),
    )


def backtest(req: BacktestRequest, returns: ReturnSeries) -> BacktestResult:
    if req.period not in PERIODS:
        raise ValueError(f"unknown period {req.period!r}")
    start, end = PERIODS[req.period]
    return _run(req, returns.slice(start, end))


def compare(reqs: list[BacktestRequest], returns: ReturnSeries) -> list[BacktestResult]:
    return [backtest(r, returns) for r in reqs]


def worst_drawdown_across_periods(weights: dict[str, float], returns: ReturnSeries) -> float:
    """Max drawdown of a lump-sum, no-rebalance portfolio over each named period (not 'full')."""
    w = np.array([weights.get(a, 0.0) for a in ASSETS])
    worst = 0.0
    for name, (start, end) in PERIODS.items():
        if name == "full":
            continue
        seg = returns.slice(start, end)
        cols = [seg.assets.index(a) for a in ASSETS]
        hold = w.copy()
        path = [1.0]
        for row in seg.data[:, cols]:
            hold = hold * (1.0 + row)
            path.append(float(hold.sum()))
        worst = max(worst, max_drawdown(path)[0])
    return worst
