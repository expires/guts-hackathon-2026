import pytest

from playyourself.decision.backtest import BacktestRequest
from playyourself.decision.returns import load_returns
from playyourself.decision.scenarios import LABEL, find_analogs, scenarios


@pytest.fixture(scope="module")
def rs():
    return load_returns()


@pytest.fixture
def req():
    return BacktestRequest(
        weights={"global_equity": 0.6, "gilts": 0.4}, monthly_contribution_pence=50_000
    )


def test_label_fan_and_paths(rs, req):
    res = scenarios(req, rs)
    assert res.label == LABEL
    assert len(res.paths) >= 3
    for p in res.paths:
        assert len(p.index) == 37 and p.index[0] == 100.0
    f = res.fan
    for lo, mid, hi in zip(f.p10, f.p50, f.p90, strict=True):
        assert lo <= mid <= hi


def test_analogs_constraints(rs):
    as_of = rs.months[-1]
    a = find_analogs(rs, as_of, k=8, horizon_months=36, min_gap_months=12)
    idx = sorted(rs.months.index(m) for m in a)
    assert len(idx) >= 3
    assert all(y - x >= 12 for x, y in zip(idx, idx[1:], strict=False))
    t = len(rs.months)
    assert all(i + 36 <= t - 1 for i in idx)
    assert all(i + 36 < rs.months.index(as_of) for i in idx)


def test_deterministic(rs, req):
    assert scenarios(req, rs).model_dump() == scenarios(req, rs).model_dump()


def test_too_few_analogs(rs, req):
    with pytest.raises(ValueError):
        scenarios(req, rs, as_of_month="2003-06")
