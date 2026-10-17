import numpy as np
import pytest
from pydantic import ValidationError

from playyourself.decision import backtest as bt
from playyourself.decision.backtest import (
    BacktestRequest,
    backtest,
    compare,
    max_drawdown,
    twr_index,
    worst_drawdown_across_periods,
)
from playyourself.decision.returns import ASSETS, ReturnSeries, load_returns


def make_series(n, start_year=2020, start_month=1, rows=None):
    months = []
    y, m = start_year, start_month
    for _ in range(n):
        months.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    data = np.zeros((n, 4)) if rows is None else np.asarray(rows, dtype=float)
    return ReturnSeries(months, data, ASSETS)


def req(weights=None, **kw):
    kw.setdefault("monthly_contribution_pence", 10_000)
    return BacktestRequest(weights=weights or {"global_equity": 1.0}, **kw)


def run(r, rs):
    return bt._run(r, rs)


def test_zero_returns():
    res = run(req(), make_series(24))
    assert res.local.final_value_pence == res.local.contributed_pence == 24 * 10_000
    assert res.index == [100.0] * 25
    assert res.months[0] == "2019-12" and len(res.months) == 25
    assert res.metrics.max_drawdown == 0


def test_constant_return_annuity():
    r, n, c = 0.01, 36, 10_000
    rows = np.zeros((n, 4))
    rows[:, 0] = r
    res = run(req(monthly_contribution_pence=c), make_series(n, rows=rows))
    fv = c * ((1 + r) ** n - 1) / r * (1 + r)
    assert abs(res.local.final_value_pence - fv) <= 2
    assert res.index[-1] == pytest.approx(100 * (1 + r) ** n)
    assert res.metrics.cagr == pytest.approx((1 + r) ** 12 - 1)
    assert res.local.money_weighted_return_annual == pytest.approx((1 + r) ** 12 - 1, rel=1e-4)


def test_isa_cap_across_tax_year():
    # 2020-01..2021-06; big contributions; allowance 20k pence-units = 2_000_000
    rs = make_series(18)
    r = req(monthly_contribution_pence=1_500_000)
    sched = bt.contribution_schedule(r, rs.months)
    by_ty: dict[int, int] = {}
    for m, c in zip(rs.months, sched, strict=True):
        by_ty[bt._tax_year(m)] = by_ty.get(bt._tax_year(m), 0) + c
    assert by_ty == {2019: 2_000_000, 2020: 2_000_000, 2021: 2_000_000}
    res = run(r, rs)
    assert res.local.contributed_pence == 6_000_000


def test_lump_sum_respects_cap_and_total():
    rs = make_series(24)
    d = req(monthly_contribution_pence=300_000)
    ls = req(monthly_contribution_pence=300_000, technique="lump_sum")
    sd = bt.contribution_schedule(d, rs.months)
    sl = bt.contribution_schedule(ls, rs.months)
    assert sum(sd) == sum(sl)
    assert sl[0] == 2_000_000  # allowance used up front
    assert sl[1] == 0 and sl[3] > 0


def test_rebalance_annual_restores_weights():
    n = 16  # 2020-01..2021-04
    rows = np.zeros((n, 4))
    rows[:, 0] = 0.03
    rs = make_series(n, rows=rows)
    w = {"global_equity": 0.5, "cash": 0.5}
    r = req(w, rebalance="annual")
    # inspect via value path: with rebalance the equity share stays closer to 50%
    res_a = run(r, rs)
    res_n = run(req(w, rebalance="none"), rs)
    assert res_a.local.final_value_pence < res_n.local.final_value_pence  # sold winners in April
    # right after April rebalance the weights are exactly target: April value check
    assert res_a.index[-1] < res_n.index[-1]


def test_threshold_triggers():
    n = 6
    rows = np.zeros((n, 4))
    rows[:, 0] = 0.10
    rs = make_series(n, rows=rows)
    w = {"global_equity": 0.5, "cash": 0.5}
    tight = run(req(w, rebalance="threshold", threshold_pp=1.0), rs)
    loose = run(req(w, rebalance="threshold", threshold_pp=50.0), rs)
    none = run(req(w, rebalance="none"), rs)
    assert loose.local.final_value_pence == none.local.final_value_pence
    assert tight.local.final_value_pence < none.local.final_value_pence


def test_max_drawdown_known():
    mdd, rec = max_drawdown([100, 120, 90, 100, 130])
    assert mdd == pytest.approx(0.25)
    assert rec == 2
    mdd, rec = max_drawdown([100, 120, 90, 100])
    assert mdd == pytest.approx(0.25) and rec is None
    assert max_drawdown([100, 101, 102]) == (0.0, 0)


def test_twr_excludes_flows():
    # flow of 100 then value 110 -> +10%; then flow 100 value 231 -> +10%
    idx = twr_index([110, 231], [100, 100])
    assert idx == pytest.approx([100, 110, 121])


@pytest.mark.parametrize(
    "w",
    [
        {"global_equity": 0.5},
        {"global_equity": 1.5, "cash": -0.5},
        {"bitcoin": 1.0},
    ],
)
def test_weight_validation(w):
    with pytest.raises(ValidationError):
        BacktestRequest(weights=w, monthly_contribution_pence=100)


def test_contribution_must_be_positive():
    with pytest.raises(ValidationError):
        BacktestRequest(weights={"cash": 1.0}, monthly_contribution_pence=0)


def test_unknown_period():
    with pytest.raises(ValueError):
        backtest(req(period="nope"), make_series(3))


def test_real_data_gfc_and_compare():
    rs = load_returns()
    eq = BacktestRequest(
        weights={"global_equity": 1.0}, period="gfc_2008", monthly_contribution_pence=50_000
    )
    bond = eq.model_copy(update={"weights": {"gilts": 1.0}})
    a, b = compare([eq, bond], rs)
    assert a.metrics.max_drawdown > 0.3 > b.metrics.max_drawdown
    assert worst_drawdown_across_periods({"global_equity": 1.0}, rs) > 0.3
    assert worst_drawdown_across_periods({"cash": 1.0}, rs) < 0.01
