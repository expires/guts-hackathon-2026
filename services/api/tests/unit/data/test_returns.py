from __future__ import annotations

import math

import pytest

from lifeline_contracts.investing import ASSETS, ReturnSeries
from lifeline_data.returns import DEFAULT_PATH, load_returns
from lifeline_eval.isa_backtest import PERIODS, slice_series


@pytest.fixture(scope="module")
def rs() -> ReturnSeries:
    return load_returns()


def cum(rs: ReturnSeries, start: str, end: str, asset: str) -> float:
    seg = slice_series(rs, start, end)
    j = seg.assets.index(asset)
    return math.prod(1 + row[j] for row in seg.returns) - 1


def test_fixture_is_labelled_synthetic() -> None:
    assert DEFAULT_PATH.read_text(encoding="utf-8").startswith("# SYNTHETIC")


def test_load_shape_and_label(rs: ReturnSeries) -> None:
    assert rs.assets == list(ASSETS)
    assert rs.months[0] == "2000-01" and rs.months[-1] == "2026-09"
    assert len(rs.returns) == 321 and all(len(r) == 4 for r in rs.returns)
    assert rs.data_status == "mock"
    assert rs.label == "Synthetic illustrative returns"


def test_2008_equities_strongly_negative(rs: ReturnSeries) -> None:
    assert -0.5 < cum(rs, "2007-10", "2009-02", "global_equity") < -0.4
    assert cum(rs, "2007-10", "2009-02", "gilts") > 0


def test_2022_gilts_negative(rs: ReturnSeries) -> None:
    assert cum(rs, "2022-01", "2022-10", "gilts") < -0.2
    assert cum(rs, "2022-01", "2022-10", "global_equity") < -0.15


def test_covid_recovers(rs: ReturnSeries) -> None:
    assert cum(rs, "2020-02", "2020-11", "global_equity") > -0.05


def test_long_run_equity_about_6_5_percent(rs: ReturnSeries) -> None:
    total = cum(rs, rs.months[0], rs.months[-1], "global_equity")
    annual = (1 + total) ** (12 / len(rs.months)) - 1
    assert annual == pytest.approx(0.065, abs=0.005)


def test_periods_inside_data(rs: ReturnSeries) -> None:
    for s, e in PERIODS.values():
        assert len(slice_series(rs, s, e).months) > 0


def test_slice_errors(rs: ReturnSeries) -> None:
    with pytest.raises(ValueError):
        slice_series(rs, "1990-01", "2000-01")
    with pytest.raises(ValueError):
        slice_series(rs, "2001-01", "2000-01")


def test_bad_shape() -> None:
    with pytest.raises(ValueError):
        ReturnSeries(months=["2000-01"], assets=list(ASSETS), returns=[[0.0, 0.0]])
