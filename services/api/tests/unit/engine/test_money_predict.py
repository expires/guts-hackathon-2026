from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from lifeline_contracts.finance import GuessDay
from lifeline_engine.money.predict import (
    backtest,
    beat_model,
    daily_spend,
    fit_ridge,
    guess_totals,
    predict_day,
    prediction_response,
    score_day,
    score_guess,
)

from .finance_builders import monthly, snapshot, tx


def test_ridge_hand_case() -> None:
    # x = 0..3, y = 1, 3, 5, 7. Population sd of x = sqrt(1.25), so sum(z^2) = 4 and z'(y - 4) = 8.944.
    x = np.array([[0.0], [1.0], [2.0], [3.0]])
    y = np.array([1.0, 3.0, 5.0, 7.0])
    ols = fit_ridge(x, y, 0.0)
    assert ols.intercept == 4.0
    assert ols.beta[0] == pytest.approx(2 * np.sqrt(1.25))  # slope 2 in raw units
    assert ols.predict_log(np.array([2.0])) == pytest.approx(5.0)
    ridge = fit_ridge(x, y, 4.0)
    assert ridge.beta[0] == pytest.approx(8.944271909999 / 8)  # beta = z'y / (4 + 4)
    assert ridge.predict_log(np.array([2.0])) == pytest.approx(4.5)  # raw slope 1.0: 4 + 1.0 x 0.5


def test_ridge_constant_and_missing_columns() -> None:
    x = np.array([[1.0, np.nan], [1.0, 2.0], [1.0, 4.0]])
    m = fit_ridge(x, np.array([1.0, 2.0, 3.0]), 1.0)
    assert m.beta[0] == 0.0  # constant column
    assert m.predict_log(np.array([1.0, np.nan])) == pytest.approx(2.0)  # missing -> mean -> intercept


@pytest.mark.parametrize(
    ("guess", "actual", "points"),
    [(20, 20, 100), (15, 20, 75), (30, 20, 50), (45, 20, 0), (5, 0, 50), (0, 0, 100), (12, 4, 20), (51, 40, 73)],
)
def test_score_guess(guess: float, actual: float, points: int) -> None:
    assert score_guess(guess, actual) == points


def test_beat_model_and_score_day() -> None:
    assert beat_model(18, 25, 20) and not beat_model(25, 21, 20) and not beat_model(22, 18, 20)
    d = score_day(GuessDay(date="2026-10-10", guess=18, predicted=25, actual=20))
    assert d.points == 90 and d.beat_model is True
    open_day = score_day(GuessDay(date="2026-10-11", guess=18, predicted=25))
    assert open_day.points is None


def test_streaks() -> None:
    days = [
        GuessDay(date="2026-10-01", guess=1, predicted=1, actual=1, points=80),
        GuessDay(date="2026-10-02", guess=1, predicted=1, actual=1, points=90),
        GuessDay(date="2026-10-03", guess=1, predicted=1, actual=1, points=40),
        GuessDay(date="2026-10-04", guess=1, predicted=1, actual=1, points=70),
        GuessDay(date="2026-10-05", guess=1, predicted=1),  # not scored yet
    ]
    t = guess_totals(days)
    assert (t.points_total, t.streak, t.best_streak) == (280, 1, 2)


def test_daily_spend_excludes_bills_and_transfers() -> None:
    txs = [
        tx("2026-10-01", -12.0, "TESCO", "Tesco"),
        tx("2026-10-01", -800.0, "NATIONWIDE MORTGAGE"),
        tx("2026-10-01", -12.99, "NETFLIX.COM"),
        tx("2026-10-01", -100.0, "TO EVERYDAY SAVER"),
        tx("2026-10-02", -5.5, "GREGGS", "Greggs"),
        tx("2026-10-02", 2000.0, "ACME SALARY"),
    ]
    assert daily_spend(txs, date(2026, 10, 1), date(2026, 10, 3)) == {
        date(2026, 10, 1): 12.0,
        date(2026, 10, 2): 5.5,
        date(2026, 10, 3): 0.0,
    }


def _synthetic():  # type: ignore[no-untyped-def]
    """200 days from 2026-03-31: £10 a day, £60 on Saturdays, +£30 on payday (28th) and the 2 days after."""
    start = date(2026, 3, 31)
    txs = monthly("2026-04-28", 6, 2000.0, "ACME SALARY")
    pays = [date(2026, m, 28) for m in range(4, 11)]
    for k in range(200):
        d = start + timedelta(days=k)
        amount = 60.0 if d.weekday() == 5 else 10.0
        if any(0 <= (d - p).days < 3 for p in pays):
            amount += 30.0
        txs.append(tx(d, -amount, "PRET A MANGER", "Pret"))
    return snapshot(txs, as_of=(start + timedelta(days=200)).isoformat())


def test_backtest_beats_weekday_baseline_on_payday_signal() -> None:
    bt = backtest(_synthetic())
    assert len(bt.days) == 90
    assert bt.mae < bt.baseline_mae
    assert 0.0 <= bt.coverage <= 1.0


def test_prediction_reasons_and_range() -> None:
    snap = _synthetic()
    sat = date(2026, 10, 17)
    assert sat.weekday() == 5
    p = predict_day(snap, sat)
    assert p.low <= p.predicted <= p.high
    assert len(p.reasons) == 3
    assert p.reasons[0].feature == "weekday" and p.reasons[0].label == "It is Saturday"
    assert p.reasons[0].effect > 0
    assert p.predicted == pytest.approx(60, rel=0.25)
    resp = prediction_response(snap, sat)
    assert resp.model.trained_on_days > 100 and resp.guess is None and resp.actual is None


def test_past_day_has_actual_and_no_leak() -> None:
    snap = _synthetic()
    day = date(2026, 10, 10)
    p = predict_day(snap, day)
    assert p.actual is not None
    assert p.trained_on_days == (day - date(2026, 3, 31)).days


def test_fixture_personas() -> None:
    finance = pytest.importorskip("lifeline_data.finance")
    snap = finance.fixture_snapshot("persona:homeowner-leeds")
    bt = backtest(snap)
    assert len(bt.days) == 90 and bt.mae > 0
