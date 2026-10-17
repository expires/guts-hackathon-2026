"""Daily spend prediction and "Guess my spend" scoring (ADR 0017). Pure: no clock, no I/O, no global RNG.

Model: ridge regression (L2, closed form, numpy) on log(1 + daily spend), refit for every test day
(walk-forward: a day is only ever predicted from days before it).

Daily spend is the money that left on a day, excluding transfers, savings, income, rent, mortgage and other
scheduled bills. Features are grouped so that the reasons are exact in the model: with centred inputs the
prediction in log space is `mean(y) + sum over groups of (group contribution)`, and the baseline ("a typical
day") is the prediction with every feature at its training mean.

Reasons are converted to GBP by adding the groups to the baseline one at a time, largest first, so the effects
telescope: the effects of ALL groups sum to `predicted - baseline` (the API shows the top 3).

Weather and bank holidays are passed in (the data layer owns them). The penalty `ALPHA` is fixed rather than
tuned (history is only months long); this is a simplification of ADR 0017 and is stated in the model name.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from numpy.typing import NDArray

from lifeline_contracts.finance import BacktestDay, Reason, Transaction
from lifeline_engine.money import dates
from lifeline_engine.money.categorise import NOT_SPENDING, categorise
from lifeline_engine.money.recurring import detect_salary

FloatArray = NDArray[np.float64]

ALPHA = 10.0
MIN_TRAIN_DAYS = 45
BACKTEST_DAYS = 90
INTERVAL_DAYS = 60
MIN_RESIDUALS = 10
DEFAULT_LOG_SPREAD = 0.6
MODEL_NAME = "ridge regression on log spend"
EXCLUDED = NOT_SPENDING | {"housing", "bills"}
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# (group id, number of columns). Column order in the matrix follows this list.
GROUPS: tuple[tuple[str, int], ...] = (
    ("weekday", 7),
    ("payday", 2),
    ("bank_holiday", 1),
    ("weather", 2),
    ("recent_trend", 1),
    ("month_end", 1),
)

Weather = Callable[[date], tuple[float, float]]  # day -> (max temperature C, rain mm)


@dataclass(frozen=True)
class DayPrediction:
    predicted: float
    low: float
    high: float
    baseline: float
    reasons: list[Reason]
    days_to_payday: int | None
    trained_on_days: int


@dataclass(frozen=True)
class Evaluation:
    days: list[BacktestDay]
    mae: float
    baseline_mae: float
    coverage: float


def daily_spend(txs: Sequence[Transaction]) -> dict[date, float]:
    """Money out per day (GBP, positive). Days without spending are absent."""
    out: dict[date, float] = {}
    for t in txs:
        if t.amount >= 0 or categorise(t) in EXCLUDED:
            continue
        d = dates.parse(t.date)
        out[d] = out.get(d, 0.0) - t.amount
    return out


def _payday_day(txs: Sequence[Transaction]) -> int | None:
    inc = detect_salary(txs)
    if inc is None:
        return None
    days = sorted(d.day for d in inc.payday_dates)
    return days[len(days) // 2]


def _days_since_payday(d: date, payday: int) -> int:
    if d.day >= payday:
        return d.day - payday
    prev_last = (d.replace(day=1) - timedelta(days=1)).day
    return d.day + min(prev_last, 31) - payday


def _days_to_payday(d: date, payday: int) -> int:
    since = _days_since_payday(d, payday)
    return 0 if since == 0 else max(0, 30 - since)


@dataclass(frozen=True)
class _Table:
    days: list[date]
    x: FloatArray
    y: FloatArray  # log1p of daily spend
    spend: FloatArray
    index: dict[date, int]
    payday: int | None


def _features(
    d: date, log_hist: Mapping[date, float], payday: int | None, holidays: frozenset[date], weather: Weather
) -> list[float]:
    row = [1.0 if d.weekday() == k else 0.0 for k in range(7)]
    if payday is None:
        row += [0.0, 0.0]
    else:
        since = _days_since_payday(d, payday)
        row += [1.0 if since <= 2 else 0.0, since / 30.0]
    row.append(1.0 if d in holidays else 0.0)
    temp, rain = weather(d)
    row += [temp, rain]
    prior = [log_hist.get(d - timedelta(days=k), 0.0) for k in range(1, 8)]
    row.append(sum(prior) / 7.0)
    last = (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    row.append(1.0 if (last - d).days <= 2 else 0.0)
    return row


def _table(txs: Sequence[Transaction], end: date, holidays: frozenset[date], weather: Weather) -> _Table | None:
    """One row per day from the first transaction to `end` inclusive."""
    spend = daily_spend(txs)
    if not txs:
        return None
    start = min(dates.parse(t.date) for t in txs)
    if end < start:
        return None
    payday = _payday_day(txs)
    days = [start + timedelta(days=k) for k in range((end - start).days + 1)]
    log_hist = {d: math.log1p(spend.get(d, 0.0)) for d in days}
    x = np.array([_features(d, log_hist, payday, holidays, weather) for d in days], dtype=np.float64)
    y = np.array([log_hist[d] for d in days], dtype=np.float64)
    s = np.array([spend.get(d, 0.0) for d in days], dtype=np.float64)
    return _Table(days, x, y, s, {d: i for i, d in enumerate(days)}, payday)


@dataclass(frozen=True)
class _Fit:
    ybar: float
    xbar: FloatArray
    scale: FloatArray
    w: FloatArray

    def contributions(self, row: FloatArray) -> FloatArray:
        return ((row - self.xbar) / self.scale) * self.w

    def predict(self, row: FloatArray) -> float:
        return self.ybar + float(self.contributions(row).sum())


def _fit(x: FloatArray, y: FloatArray) -> _Fit:
    xbar = x.mean(axis=0)
    scale = x.std(axis=0)
    scale = np.where(scale < 1e-9, 1.0, scale)
    z = (x - xbar) / scale
    ybar = float(y.mean())
    a = z.T @ z + ALPHA * np.eye(z.shape[1])
    w = np.linalg.solve(a, z.T @ (y - ybar))
    return _Fit(ybar, xbar, scale, w)


def _walk_forward(t: _Table, first: int, last: int) -> list[tuple[int, float]]:
    """(row index, predicted log spend) for rows first..last, each fitted on the rows before it."""
    out: list[tuple[int, float]] = []
    for i in range(first, last + 1):
        if i < MIN_TRAIN_DAYS:
            continue
        out.append((i, _fit(t.x[:i], t.y[:i]).predict(t.x[i])))
    return out


def _spread(residuals: Sequence[float]) -> tuple[float, float]:
    """(q10, q90) of log residuals, forced to straddle zero. A wide default until there are enough."""
    if len(residuals) < MIN_RESIDUALS:
        return -DEFAULT_LOG_SPREAD, DEFAULT_LOG_SPREAD
    q10, q90 = (float(q) for q in np.percentile(np.array(residuals), [10, 90]))
    return min(q10, 0.0), max(q90, 0.0)


def _money(z: float) -> float:
    return round(max(0.0, math.expm1(z)), 2)


def _weekday_means(t: _Table, upto: int) -> dict[int, float]:
    out: dict[int, float] = {}
    for wd in range(7):
        vals = [t.spend[i] for i in range(upto) if t.days[i].weekday() == wd]
        out[wd] = float(np.mean(vals)) if vals else 0.0
    return out


def _label(group: str, d: date, row: FloatArray, payday: int | None, holiday: bool, temp: float, rain: float,
           effect: float) -> str:
    if group == "weekday":
        return f"It is a {WEEKDAYS[d.weekday()]}"
    if group == "payday" and payday is not None:
        since = _days_since_payday(d, payday)
        if since == 0:
            return "It is payday"
        return f"You were paid {since} day{'s' if since != 1 else ''} ago"
    if group == "bank_holiday":
        return "It is a bank holiday" if holiday else "It is a normal working day"
    if group == "weather":
        if rain >= 1.0:
            return f"It is wet, {temp:.0f} degrees"
        return f"It is dry, {temp:.0f} degrees"
    if group == "recent_trend":
        return "Your last week was busier than usual" if effect >= 0 else "Your last week was quieter than usual"
    return "It is near the end of the month" if row[-1] >= 1.0 else "It is not near the end of the month"


def predict_day(
    txs: Sequence[Transaction], target: date, holidays: frozenset[date], weather: Weather
) -> DayPrediction:
    """Prediction for `target` from all days before it. Raises ValueError with fewer than MIN_TRAIN_DAYS."""
    t = _table(txs, target, holidays, weather)
    if t is None or len(t.days) - 1 < MIN_TRAIN_DAYS:
        raise ValueError("not enough history to predict")
    n = len(t.days) - 1  # index of target
    fit = _fit(t.x[:n], t.y[:n])
    row = t.x[n]
    contrib = fit.contributions(row)
    z = fit.ybar + float(contrib.sum())

    residuals = [float(t.y[i]) - p for i, p in _walk_forward(t, max(MIN_TRAIN_DAYS, n - INTERVAL_DAYS), n - 1)]
    q10, q90 = _spread(residuals)

    groups: list[tuple[str, float, slice]] = []
    col = 0
    for name, width in GROUPS:
        sl = slice(col, col + width)
        groups.append((name, float(contrib[sl].sum()), sl))
        col += width
    ordered = sorted(groups, key=lambda g: (-abs(g[1]), g[0]))
    cum = fit.ybar
    reasons: list[Reason] = []
    temp, rain = weather(target)
    for name, c, _ in ordered:
        before = _money(cum)
        cum += c
        effect = round(_money(cum) - before, 2)
        reasons.append(
            Reason(
                feature=name,
                label=_label(name, target, row, t.payday, target in holidays, temp, rain, effect),
                effect=effect,
            )
        )
    predicted = _money(z)
    return DayPrediction(
        predicted=predicted,
        low=min(_money(z + q10), predicted),
        high=max(_money(z + q90), predicted),
        baseline=_money(fit.ybar),
        reasons=reasons[:3],
        days_to_payday=None if t.payday is None else _days_to_payday(target, t.payday),
        trained_on_days=n,
    )


def evaluate(
    txs: Sequence[Transaction], as_of: date, holidays: frozenset[date], weather: Weather, n_days: int = BACKTEST_DAYS
) -> Evaluation:
    """Walk-forward backtest over the last `n_days` days before `as_of`. Raises ValueError without enough history."""
    t = _table(txs, as_of - timedelta(days=1), holidays, weather)
    if t is None or len(t.days) <= MIN_TRAIN_DAYS:
        raise ValueError("not enough history to evaluate")
    last = len(t.days) - 1
    first = max(MIN_TRAIN_DAYS, last - n_days + 1)
    preds = _walk_forward(t, first, last)
    days: list[BacktestDay] = []
    residuals: list[float] = []
    covered = 0
    abs_err = 0.0
    base_err = 0.0
    for i, z in preds:
        q10, q90 = _spread(residuals[-INTERVAL_DAYS:])
        predicted = _money(z)
        actual = round(float(t.spend[i]), 2)
        baseline = round(_weekday_means(t, i)[t.days[i].weekday()], 2)
        low, high = min(_money(z + q10), predicted), max(_money(z + q90), predicted)
        residuals.append(float(t.y[i]) - z)
        covered += 1 if low <= actual <= high else 0
        abs_err += abs(predicted - actual)
        base_err += abs(baseline - actual)
        days.append(
            BacktestDay(
                date=dates.iso(t.days[i]), predicted=predicted, low=low, high=high, actual=actual, baseline=baseline
            )
        )
    n = len(days)
    return Evaluation(
        days=days,
        mae=round(abs_err / n, 2),
        baseline_mae=round(base_err / n, 2),
        coverage=round(covered / n, 3),
    )


def actual_spend(txs: Sequence[Transaction], day: date) -> float:
    return round(daily_spend(txs).get(day, 0.0), 2)


def guess_points(guess: float, actual: float) -> int:
    """100 x max(0, 1 - |guess - actual| / max(actual, 10)), rounded."""
    return round(100 * max(0.0, 1 - abs(guess - actual) / max(actual, 10.0)))


def beat_model(guess: float, predicted: float, actual: float) -> bool:
    return abs(guess - actual) < abs(predicted - actual)


def streaks(points_by_day: Mapping[str, int | None], threshold: int = 70) -> tuple[int, int]:
    """(current streak, best streak) of consecutive scored days with points >= threshold, by date order."""
    scored = [p for _, p in sorted(points_by_day.items()) if p is not None]
    best = run = 0
    for p in scored:
        run = run + 1 if p >= threshold else 0
        best = max(best, run)
    return run, best
