import numpy as np
import pytest

from playyourself.decision.returns import ASSETS, PERIODS, ReturnSeries, load_returns


@pytest.fixture(scope="module")
def rs():
    return load_returns()


def test_load_shape(rs):
    assert rs.assets == ASSETS
    assert rs.months[0] == "2000-01" and rs.months[-1] == "2026-09"
    assert rs.data.shape == (321, 4)
    assert np.isfinite(rs.data).all()


def test_gfc_equity_strongly_negative(rs):
    seg = rs.slice("2007-10", "2009-02")
    cum = np.prod(1 + seg.column("global_equity")) - 1
    assert -0.5 < cum < -0.4
    assert np.prod(1 + seg.column("gilts")) - 1 > 0


def test_2022_gilts_negative(rs):
    seg = rs.slice("2022-01", "2022-10")
    assert np.prod(1 + seg.column("gilts")) - 1 < -0.2
    assert np.prod(1 + seg.column("global_equity")) - 1 < -0.15


def test_covid_recovers(rs):
    seg = rs.slice("2020-02", "2020-11")
    assert np.prod(1 + seg.column("global_equity")) - 1 > -0.05


def test_periods_inside_data(rs):
    for s, e in PERIODS.values():
        assert rs.slice(s, e).data.shape[0] > 0


def test_slice_errors(rs):
    with pytest.raises(ValueError):
        rs.slice("1990-01", "2000-01")
    with pytest.raises(ValueError):
        rs.slice("2001-01", "2000-01")


def test_bad_shape():
    with pytest.raises(ValueError):
        ReturnSeries(["2000-01"], np.zeros((2, 4)))
