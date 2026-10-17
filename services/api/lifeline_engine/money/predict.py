"""Daily spend prediction and "Guess my spend" scoring (ADR 0017). Pure numpy, no LLM, no clock.

Target: log(1 + daily spend). Daily spend = outflows that day, excluding transfers, savings, income,
housing (rent, mortgage), bills, subscriptions and fees (scheduled payments live in the bills list).

Features, by group (the reasons use the groups):
- weekday: one-hot Monday..Sunday.
- payday: days since the last salary credit / 30, and a flag for the first 3 days after payday
  (payday 0, 1, 2). Paydays come from detected salary credits, projected monthly after the last one.
- bank_holiday: flag (dates from gov.uk, passed in by the caller).
- weather: max temperature (C) and rain (mm) for the user's region (passed in). Missing values take
  the training mean, so they add nothing.
- recent_trend: mean log spend of the 7 days before.
- month_end: flag for the last 3 days of the month.

Model: ridge regression on standardised features, unpenalised intercept. alpha is chosen from
ALPHAS by walk-forward validation over the last VALIDATION_DAYS training days.
Range: the 10th and 90th percentiles of walk-forward residuals (log space), mapped back to GBP.
Reasons: effect of a group in GBP = predicted - prediction with that group at its training mean.
Baseline ("typical day") = prediction with every feature at its training mean = expm1(intercept).
"""

from __future__ import annotations

import calendar
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from lifeline_contracts.finance import (
    BacktestDay,
    Category,
    FinanceSnapshot,
    GuessDay,
    GuessState,
    ModelInfo,
    PredictionEvaluation,
    Reason,
    SpendPrediction,
    Transaction,
    Weather,
)
from lifeline_contracts.observation import Status
from lifeline_engine.money import dates
from lifeline_engine.money.categorise import NOT_SPENDING, categorise
from lifeline_engine.money.recurring import detect_salary

FloatArray = NDArray[np.float64]
WeatherDays = Mapping[dates.date, tuple[float, float]]  # day -> (max temp C, rain mm), same as lifeline_data

EXCLUDED: frozenset[Category] = NOT_SPENDING | {"housing", "bills", "subscriptions", "fees"}
GROUPS: tuple[str, ...] = ("weekday", "payday", "bank_holiday", "weather", "recent_trend", "month_end")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
ALPHAS: tuple[float, ...] = (0.3, 1.0, 3.0, 10.0, 30.0, 100.0)
VALIDATION_DAYS = 28
RESIDUAL_DAYS = 60
MIN_TRAIN_DAYS = 28
BACKTEST_DAYS = 90
PAYDAY_WINDOW = 3
TREND_DAYS = 7
MONTH_END_DAYS = 3
STREAK_POINTS = 70
METHOD = "Ridge regression on log daily spend (weekday, payday, bank holiday, weather, last 7 days, month end)"
BASELINE_TEXT = "Average spend for the same weekday"


# ---------- data ----------


def is_daily_spend(t: Transaction) -> bool:
    return t.amount < 0 and categorise(t) not in EXCLUDED


def daily_spend(txs: Sequence[Transaction], start: dates.date, end: dates.date) -> dict[dates.date, float]:
    """Spend per day from `start` to `end` inclusive. Days without spend are 0."""
    out = {dates.add_days(start, i): 0.0 for i in range((end - start).days + 1)}
    for t in txs:
        d = dates.parse(t.date)
        if d in out and is_daily_spend(t):
            out[d] += -t.amount
    return {d: round(v, 2) for d, v in out.items()}


def paydays(txs: Sequence[Transaction], until: dates.date) -> list[dates.date]:
    """Detected salary dates, projected monthly after the last one up to `until` + 40 days."""
    inc = detect_salary(txs)
    if inc is None:
        return []
    days = list(inc.payday_dates)
    nxt = dates.add_months(days[-1], 1)
    while nxt <= dates.add_days(until, 40):
        days.append(nxt)
        nxt = dates.add_months(nxt, 1)
    return days


# ---------- features ----------


@dataclass(frozen=True)
class DayInputs:
    holidays: frozenset[dates.date]
    weather: Mapping[dates.date, tuple[float, float]]
    paydays: tuple[dates.date, ...]


def days_since_payday(d: dates.date, pays: Sequence[dates.date]) -> int | None:
    past = [p for p in pays if p <= d]
    return (d - past[-1]).days if past else None


def days_to_payday(d: dates.date, pays: Sequence[dates.date]) -> int | None:
    future = [p for p in pays if p >= d]
    return (future[0] - d).days if future else None


def feature_row(d: dates.date, log_hist: Mapping[dates.date, float], inp: DayInputs) -> dict[str, list[float]]:
    """Raw features per group. NaN marks a missing value (filled with the training mean)."""
    since = days_since_payday(d, inp.paydays)
    prev = [log_hist[x] for x in (dates.add_days(d, -k) for k in range(1, TREND_DAYS + 1)) if x in log_hist]
    w = inp.weather.get(d)
    last_day = calendar.monthrange(d.year, d.month)[1]
    return {
        "weekday": [1.0 if d.weekday() == i else 0.0 for i in range(7)],
        "payday": [
            float("nan") if since is None else min(since, 35) / 30,
            float("nan") if since is None else (1.0 if since < PAYDAY_WINDOW else 0.0),
        ],
        "bank_holiday": [1.0 if d in inp.holidays else 0.0],
        "weather": [float("nan"), float("nan")] if w is None else [float(w[0]), float(w[1])],
        "recent_trend": [float(np.mean(prev)) if prev else float("nan")],
        "month_end": [1.0 if d.day > last_day - MONTH_END_DAYS else 0.0],
    }


def _slices() -> dict[str, slice]:
    sizes = {"weekday": 7, "payday": 2, "bank_holiday": 1, "weather": 2, "recent_trend": 1, "month_end": 1}
    out: dict[str, slice] = {}
    i = 0
    for g in GROUPS:
        out[g] = slice(i, i + sizes[g])
        i += sizes[g]
    return out


SLICES = _slices()
N_FEATURES = sum(s.stop - s.start for s in SLICES.values())


def _flat(row: Mapping[str, list[float]]) -> list[float]:
    return [v for g in GROUPS for v in row[g]]


# ---------- ridge ----------


@dataclass(frozen=True)
class Ridge:
    mean: FloatArray
    scale: FloatArray
    beta: FloatArray
    intercept: float
    alpha: float

    def z(self, x: FloatArray) -> FloatArray:
        filled = np.where(np.isnan(x), self.mean, x)
        out: FloatArray = (filled - self.mean) / self.scale
        return out

    def predict_log(self, x: FloatArray) -> float:
        return float(self.intercept + self.z(x) @ self.beta)

    def contributions(self, x: FloatArray) -> dict[str, float]:
        """Log-space contribution of each group: sum of beta * z over its features."""
        zx = self.z(x) * self.beta
        return {g: float(zx[s].sum()) for g, s in SLICES.items()}


def fit_ridge(x: FloatArray, y: FloatArray, alpha: float) -> Ridge:
    """Ridge on standardised columns. NaN takes the column mean. Constant columns get beta 0."""
    col_mean = np.nanmean(np.where(np.isnan(x).all(axis=0), 0.0, x), axis=0) if x.size else np.zeros(x.shape[1])
    col_mean = np.where(np.isnan(col_mean), 0.0, col_mean)
    filled = np.where(np.isnan(x), col_mean, x)
    sd = filled.std(axis=0)
    scale = np.where(sd > 1e-12, sd, 1.0)
    z = (filled - col_mean) / scale
    z[:, sd <= 1e-12] = 0.0
    y_mean = float(y.mean()) if y.size else 0.0
    a = z.T @ z + alpha * np.eye(z.shape[1])
    beta = np.linalg.solve(a, z.T @ (y - y_mean))
    return Ridge(mean=col_mean, scale=scale, beta=beta, intercept=y_mean, alpha=alpha)


# ---------- dataset ----------


@dataclass(frozen=True)
class Dataset:
    days: tuple[dates.date, ...]
    x: FloatArray
    y: FloatArray  # log1p spend
    spend: FloatArray


def build_dataset(spend: Mapping[dates.date, float], inp: DayInputs, extra: Sequence[dates.date] = ()) -> Dataset:
    """Rows for every day in `spend` (with targets) plus `extra` days (targets NaN)."""
    log_hist = {d: float(np.log1p(v)) for d, v in spend.items()}
    days = sorted({*spend, *extra})
    x = np.array([_flat(feature_row(d, log_hist, inp)) for d in days], dtype=np.float64)
    y = np.array([log_hist.get(d, float("nan")) for d in days], dtype=np.float64)
    s = np.array([spend.get(d, float("nan")) for d in days], dtype=np.float64)
    return Dataset(days=tuple(days), x=x, y=y, spend=s)


def _walk_forward_log_errors(ds: Dataset, idx: Sequence[int], alpha: float) -> list[float]:
    """Residuals (actual - predicted, log space) for rows `idx`, each fitted on all rows before it."""
    out: list[float] = []
    for i in idx:
        if i < MIN_TRAIN_DAYS:
            continue
        m = fit_ridge(ds.x[:i], ds.y[:i], alpha)
        out.append(float(ds.y[i] - m.predict_log(ds.x[i])))
    return out


def choose_alpha(ds: Dataset, end: int) -> float:
    """alpha with the lowest walk-forward MAE in GBP over the VALIDATION_DAYS rows before `end`."""
    idx = list(range(max(MIN_TRAIN_DAYS, end - VALIDATION_DAYS), end))
    if not idx:
        return 10.0
    best, best_err = 10.0, float("inf")
    for a in ALPHAS:
        errs = []
        for i in idx:
            m = fit_ridge(ds.x[:i], ds.y[:i], a)
            errs.append(abs(float(np.expm1(m.predict_log(ds.x[i]))) - float(ds.spend[i])))
        err = float(np.mean(errs))
        if err < best_err - 1e-9:
            best, best_err = a, err
    return best


def weekday_baseline(ds: Dataset, end: int, d: dates.date) -> float:
    """Average spend on the same weekday over rows before `end`."""
    vals = [float(ds.spend[i]) for i in range(end) if ds.days[i].weekday() == d.weekday()]
    return float(np.mean(vals)) if vals else (float(np.mean(ds.spend[:end])) if end else 0.0)


# ---------- prediction ----------


@dataclass(frozen=True)
class DayPrediction:
    date: dates.date
    predicted: float
    low: float
    high: float
    baseline: float
    reasons: tuple[Reason, ...]
    is_bank_holiday: bool
    days_to_payday: int | None
    actual: float | None
    trained_on_days: int
    alpha: float


def _inputs(snapshot: FinanceSnapshot, holidays: Collection[dates.date], weather: WeatherDays | None,
            until: dates.date) -> DayInputs:
    return DayInputs(
        holidays=frozenset(holidays),
        weather=dict(weather or {}),
        paydays=tuple(paydays(snapshot.transactions, until)),
    )


def _history(snapshot: FinanceSnapshot) -> dict[dates.date, float]:
    """Daily spend from the first transaction to the day before as_of (as_of itself is not over yet)."""
    as_of = dates.parse(snapshot.as_of)
    if not snapshot.transactions:
        return {}
    start = min(dates.parse(t.date) for t in snapshot.transactions)
    return daily_spend(snapshot.transactions, start, dates.add_days(as_of, -1))


def reason_label(group: str, d: dates.date, inp: DayInputs, x: Mapping[str, list[float]], effect: float) -> str:
    if group == "weekday":
        return f"It is {WEEKDAYS[d.weekday()]}"
    if group == "payday":
        since = days_since_payday(d, inp.paydays)
        if since is None:
            return "Payday is not known"
        if since == 0:
            return "You were paid today"
        if since == 1:
            return "You were paid yesterday"
        if since < PAYDAY_WINDOW + 4:
            return f"You were paid {since} days ago"
        to = days_to_payday(d, inp.paydays)
        return f"Payday is {to} days away" if to is not None else f"It is {since} days since payday"
    if group == "bank_holiday":
        return "It is a bank holiday" if d in inp.holidays else "It is a normal day, not a bank holiday"
    if group == "weather":
        w = inp.weather.get(d)
        if w is None:
            return "No weather data"
        return f"It is {w[0]:.0f}°C and {'rainy' if w[1] >= 1.0 else 'dry'}"
    if group == "recent_trend":
        return "You spent more than usual in the last 7 days" if effect > 0 else (
            "You spent less than usual in the last 7 days"
        )
    return "It is the end of the month" if x["month_end"][0] > 0 else "It is not the end of the month"


def _predict_row(ds: Dataset, i: int, inp: DayInputs, alpha: float, residuals: Sequence[float]) -> DayPrediction:
    d = ds.days[i]
    train = [j for j in range(i) if not np.isnan(ds.y[j])]
    trained = len(train)
    if trained < MIN_TRAIN_DAYS:
        base = weekday_baseline(ds, i, d)
        return DayPrediction(d, round(base, 2), round(base * 0.5, 2), round(base * 1.5, 2), round(base, 2), (),
                             d in inp.holidays, days_to_payday(d, inp.paydays),
                             None if np.isnan(ds.spend[i]) else float(ds.spend[i]), trained, alpha)
    m = fit_ridge(ds.x[train], ds.y[train], alpha)
    xi = ds.x[i]
    pred_log = m.predict_log(xi)
    predicted = max(0.0, float(np.expm1(pred_log)))
    res = np.array(residuals if len(residuals) >= 10 else [0.0], dtype=np.float64)
    lo_q, hi_q = float(np.quantile(res, 0.1)), float(np.quantile(res, 0.9))
    low = max(0.0, float(np.expm1(pred_log + min(0.0, lo_q))))
    high = max(predicted, float(np.expm1(pred_log + max(0.0, hi_q))))
    baseline = max(0.0, float(np.expm1(m.intercept)))
    contrib = m.contributions(xi)
    row = feature_row(d, {ds.days[j]: float(ds.y[j]) for j in train}, inp)
    effects = {g: predicted - max(0.0, float(np.expm1(pred_log - c))) for g, c in contrib.items()}
    top = sorted(GROUPS, key=lambda g: (-abs(effects[g]), GROUPS.index(g)))[:3]
    reasons = tuple(
        Reason(feature=g, label=reason_label(g, d, inp, row, effects[g]), effect=round(effects[g], 2)) for g in top
    )
    return DayPrediction(
        date=d,
        predicted=round(predicted, 2),
        low=round(low, 2),
        high=round(high, 2),
        baseline=round(baseline, 2),
        reasons=reasons,
        is_bank_holiday=d in inp.holidays,
        days_to_payday=days_to_payday(d, inp.paydays),
        actual=None if np.isnan(ds.spend[i]) else round(float(ds.spend[i]), 2),
        trained_on_days=trained,
        alpha=alpha,
    )


def predict_day(
    snapshot: FinanceSnapshot,
    day: dates.date,
    holidays: Collection[dates.date] = (),
    weather: WeatherDays | None = None,
) -> DayPrediction:
    """Prediction for `day`. Trains on every complete day before `day` (and before as_of)."""
    full = _history(snapshot)
    hist = {d: v for d, v in full.items() if d <= day}  # the row for `day` keeps its actual; training uses d < day
    inp = _inputs(snapshot, holidays, weather, max(day, dates.parse(snapshot.as_of)))
    ds = build_dataset(hist, inp, extra=[day])
    i = ds.days.index(day)
    alpha = choose_alpha(ds, i)
    residuals = _walk_forward_log_errors(ds, range(max(MIN_TRAIN_DAYS, i - RESIDUAL_DAYS), i), alpha)
    return _predict_row(ds, i, inp, alpha, residuals)


# ---------- backtest ----------


@dataclass(frozen=True)
class Backtest:
    days: tuple[BacktestDay, ...]
    mae: float
    baseline_mae: float
    coverage: float
    trained_on_days: int


def backtest(
    snapshot: FinanceSnapshot,
    holidays: Collection[dates.date] = (),
    weather: WeatherDays | None = None,
    n_days: int = BACKTEST_DAYS,
) -> Backtest:
    """Walk-forward over the last `n_days` complete days. Each day trains on all days before it.
    alpha is chosen once on the days before the window. The range uses residuals from earlier test days
    (and from the RESIDUAL_DAYS before the window to start)."""
    hist = _history(snapshot)
    if not hist:
        return Backtest((), 0.0, 0.0, 0.0, 0)
    inp = _inputs(snapshot, holidays, weather, dates.parse(snapshot.as_of))
    ds = build_dataset(hist, inp)
    n = len(ds.days)
    first = max(MIN_TRAIN_DAYS, n - n_days)
    alpha = choose_alpha(ds, first)
    residuals = _walk_forward_log_errors(ds, range(max(MIN_TRAIN_DAYS, first - RESIDUAL_DAYS), first), alpha)
    out: list[BacktestDay] = []
    for i in range(first, n):
        p = _predict_row(ds, i, inp, alpha, residuals)
        actual = float(ds.spend[i])
        out.append(
            BacktestDay(
                date=dates.iso(ds.days[i]),
                predicted=p.predicted,
                low=p.low,
                high=p.high,
                actual=round(actual, 2),
                baseline=round(weekday_baseline(ds, i, ds.days[i]), 2),
            )
        )
        if p.trained_on_days >= MIN_TRAIN_DAYS:
            residuals = [*residuals, float(ds.y[i]) - float(np.log1p(p.predicted))]
    if not out:
        return Backtest((), 0.0, 0.0, 0.0, len(hist))
    mae = float(np.mean([abs(b.predicted - b.actual) for b in out]))
    base = float(np.mean([abs(b.baseline - b.actual) for b in out]))
    cov = float(np.mean([b.low <= b.actual <= b.high for b in out]))
    return Backtest(tuple(out), round(mae, 2), round(base, 2), round(cov, 4), len(hist))


def model_info(bt: Backtest) -> ModelInfo:
    return ModelInfo(
        name="ridge regression on log spend",
        trained_on_days=bt.trained_on_days,
        mae=bt.mae,
        baseline_mae=bt.baseline_mae,
        interval_coverage=bt.coverage,
    )


# ---------- responses ----------


def weather_summary(temp_max_c: float, rain_mm: float) -> str:
    feel = "warm" if temp_max_c >= 20 else "mild" if temp_max_c >= 12 else "cold"
    wet = "rain" if rain_mm >= 1.0 else "dry"
    return f"{feel.capitalize()} and {wet}"


def prediction_response(
    snapshot: FinanceSnapshot,
    day: dates.date,
    holidays: Collection[dates.date] = (),
    weather: WeatherDays | None = None,
    weather_status: Status = "mock",
    guess: GuessState | None = None,
    bt: Backtest | None = None,
) -> SpendPrediction:
    """SpendPrediction for `day`. Pass `bt` to reuse a cached backtest for the model info."""
    from lifeline_engine.money import finance_meta

    p = predict_day(snapshot, day, holidays, weather)
    w = (weather or {}).get(day)
    info = model_info(bt if bt is not None else backtest(snapshot, holidays, weather))
    return SpendPrediction(
        meta=finance_meta(snapshot),
        date=dates.iso(day),
        predicted=p.predicted,
        low=p.low,
        high=p.high,
        baseline=p.baseline,
        reasons=list(p.reasons),
        weather=None if w is None else Weather(
            summary=weather_summary(w[0], w[1]), temp_max_c=w[0], rain_mm=w[1], status=weather_status
        ),
        is_bank_holiday=p.is_bank_holiday,
        days_to_payday=p.days_to_payday,
        guess=guess,
        actual=p.actual,
        model=info,
    )


def evaluation_response(
    snapshot: FinanceSnapshot,
    holidays: Collection[dates.date] = (),
    weather: WeatherDays | None = None,
    bt: Backtest | None = None,
) -> PredictionEvaluation:
    from lifeline_engine.money import finance_meta

    b = bt if bt is not None else backtest(snapshot, holidays, weather)
    return PredictionEvaluation(
        meta=finance_meta(snapshot),
        method=METHOD,
        n_days=len(b.days),
        mae=b.mae,
        baseline_mae=b.baseline_mae,
        baseline=BASELINE_TEXT,
        interval_coverage=b.coverage,
        days=list(b.days),
    )


# ---------- Guess my spend ----------


def score_guess(guess: float, actual: float) -> int:
    """points = round(100 * max(0, 1 - |guess - actual| / max(actual, 10))), rounding .5 up (half-up).
    The raw value is first rounded to 9 decimals so float noise (72.4999999) does not change the result."""
    raw = round(100 * max(0.0, 1 - abs(guess - actual) / max(actual, 10.0)), 9)
    return int(math.floor(raw + 0.5))


def beat_model(guess: float, predicted: float, actual: float) -> bool:
    """True when the guess was strictly closer to the actual than the prediction."""
    return abs(guess - actual) < abs(predicted - actual)


def score_day(day: GuessDay) -> GuessDay:
    """Fill points and beat_model when the actual is known."""
    if day.actual is None:
        return day.model_copy(update={"points": None, "beat_model": None})
    return day.model_copy(
        update={"points": score_guess(day.guess, day.actual), "beat_model": beat_model(day.guess, day.predicted,
                                                                                         day.actual)}
    )


@dataclass(frozen=True)
class GuessTotals:
    points_total: int
    streak: int
    best_streak: int


def guess_totals(days: Sequence[GuessDay]) -> GuessTotals:
    """Totals over scored days in date order. A streak counts consecutive scored days with points >= 70.
    Unscored days (actual not known yet) do not break the streak. `streak` is the run ending at the latest
    scored day."""
    scored = sorted((d for d in days if d.points is not None), key=lambda d: d.date)
    total = run = best = 0
    for d in scored:
        assert d.points is not None
        total += d.points
        run = run + 1 if d.points >= STREAK_POINTS else 0
        best = max(best, run)
    return GuessTotals(points_total=total, streak=run, best_streak=best)
