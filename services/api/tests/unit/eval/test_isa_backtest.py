from __future__ import annotations

import pytest
from pydantic import ValidationError

from lifeline_contracts.accounts import Holding
from lifeline_contracts.investing import ASSETS, IsaBacktestRequest, ReturnSeries
from lifeline_data.returns import load_returns
from lifeline_eval import isa_backtest as bt


def make_series(n: int, rows: list[list[float]] | None = None, start_year: int = 2020) -> ReturnSeries:
    months = []
    y, m = start_year, 1
    for _ in range(n):
        months.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return ReturnSeries(months=months, assets=list(ASSETS), returns=rows or [[0.0] * 4 for _ in range(n)])


def req(weights: dict[str, float] | None = None, **kw: object) -> IsaBacktestRequest:
    kw.setdefault("monthly_contribution", 100.0)
    return IsaBacktestRequest(weights=weights or {"global_equity": 1.0}, **kw)  # type: ignore[arg-type]


def test_zero_returns() -> None:
    res = bt.run_backtest(req(), make_series(24))
    assert res.final_value == res.contributed == 2400.0
    assert res.index == [100.0] * 25
    assert res.months[0] == "2019-12" and len(res.months) == 25
    assert res.metrics.max_drawdown == 0


def test_constant_return_annuity_closed_form() -> None:
    r, n, c = 0.01, 36, 100.0
    rows = [[r, 0.0, 0.0, 0.0] for _ in range(n)]
    res = bt.run_backtest(req(monthly_contribution=c), make_series(n, rows))
    fv = c * ((1 + r) ** n - 1) / r * (1 + r)
    assert res.final_value == pytest.approx(fv, abs=0.01)
    assert res.index[-1] == pytest.approx(100 * (1 + r) ** n)
    assert res.metrics.cagr == pytest.approx((1 + r) ** 12 - 1)
    assert res.money_weighted_return == pytest.approx((1 + r) ** 12 - 1, rel=1e-4)


def test_isa_cap_per_tax_year() -> None:
    rs = make_series(18)  # 2020-01 .. 2021-06 spans tax years 2019, 2020, 2021
    r = req(monthly_contribution=15_000.0)
    sched = bt.contribution_schedule(r, rs.months)
    by_ty: dict[int, float] = {}
    for m, c in zip(rs.months, sched, strict=True):
        by_ty[bt._tax_year(m)] = by_ty.get(bt._tax_year(m), 0.0) + c
    assert by_ty == {2019: 20_000.0, 2020: 20_000.0, 2021: 20_000.0}
    assert bt.run_backtest(r, rs).contributed == 60_000.0


def test_lump_sum_respects_cap_and_total() -> None:
    rs = make_series(24)
    d = req(monthly_contribution=3_000.0)
    ls = req(monthly_contribution=3_000.0, technique="lump_sum")
    sd, sl = bt.contribution_schedule(d, rs.months), bt.contribution_schedule(ls, rs.months)
    assert sum(sd) == pytest.approx(sum(sl))
    assert sl[0] == 20_000.0 and sl[1] == 0 and sl[3] > 0


def test_annual_rebalance_sells_winners() -> None:
    n = 16
    rows = [[0.03, 0.0, 0.0, 0.0] for _ in range(n)]
    rs = make_series(n, rows)
    w = {"global_equity": 0.5, "cash": 0.5}
    a = bt.run_backtest(req(w, rebalance="annual"), rs)
    none = bt.run_backtest(req(w, rebalance="none"), rs)
    assert a.final_value < none.final_value


def test_threshold_triggers() -> None:
    rs = make_series(6, [[0.10, 0.0, 0.0, 0.0] for _ in range(6)])
    w = {"global_equity": 0.5, "cash": 0.5}
    tight = bt.run_backtest(req(w, rebalance="threshold", threshold_pp=1.0), rs)
    loose = bt.run_backtest(req(w, rebalance="threshold", threshold_pp=50.0), rs)
    none = bt.run_backtest(req(w, rebalance="none"), rs)
    assert loose.final_value == none.final_value
    assert tight.final_value < none.final_value


def test_max_drawdown_known() -> None:
    mdd, rec = bt.max_drawdown([100, 120, 90, 100, 130])
    assert mdd == pytest.approx(0.25) and rec == 2
    mdd, rec = bt.max_drawdown([100, 120, 90, 100])
    assert mdd == pytest.approx(0.25) and rec is None
    assert bt.max_drawdown([100, 101, 102]) == (0.0, 0)


def test_twr_excludes_flows() -> None:
    assert bt.twr_index([110, 231], [100, 100]) == pytest.approx([100, 110, 121])


@pytest.mark.parametrize("w", [{"global_equity": 0.5}, {"global_equity": 1.5, "cash": -0.5}, {"bitcoin": 1.0}])
def test_weight_validation(w: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        IsaBacktestRequest(weights=w, monthly_contribution=1.0)


def test_contribution_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        IsaBacktestRequest(weights={"cash": 1.0}, monthly_contribution=0)


def test_unknown_period() -> None:
    with pytest.raises(ValueError):
        bt.isa_backtest(req(period="nope"), make_series(3))


def test_real_data_gfc_and_worst_drawdown() -> None:
    rs = load_returns()
    eq = req(period="gfc_2008", monthly_contribution=500.0)
    bond = eq.model_copy(update={"weights": {"gilts": 1.0}})
    a, b = bt.isa_compare([eq, bond], rs)
    assert a.metrics.max_drawdown > 0.3 > b.metrics.max_drawdown
    assert a.label == "the 2008 financial crisis" and a.data_status == "mock"
    assert bt.worst_drawdown_for({"global_equity": 1.0}, rs) > 0.3
    assert bt.worst_drawdown_for({"cash": 1.0}, rs) < 0.01
    assert set(bt.period_drawdowns({"gilts": 1.0}, rs)) == {"gfc_2008", "covid_2020", "rates_2022"}


def h(value: float, asset_class: str, region: str | None = None) -> Holding:
    return Holding(instrument_id="x", name="x", quantity=1, value=value, asset_class=asset_class, region=region)  # type: ignore[arg-type]


def test_weights_from_holdings() -> None:
    w = bt.weights_from_holdings(
        [h(400, "equity", "UK"), h(300, "equity", "US"), h(200, "bond"), h(50, "cash"), h(50, "commodity")]
    )
    assert w is not None
    assert w == pytest.approx({"uk_equity": 0.4, "global_equity": 0.35, "gilts": 0.2, "cash": 0.05})
    assert sum(w.values()) == pytest.approx(1.0)
    assert bt.weights_from_holdings([]) is None
    assert bt.weights_from_holdings([h(0, "equity")]) is None
