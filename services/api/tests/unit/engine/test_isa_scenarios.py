from __future__ import annotations

import pytest

from lifeline_contracts.investing import IsaBacktestRequest, IsaScenariosResult, ReturnSeries
from lifeline_data.returns import load_returns
from lifeline_engine.isa_scenarios import find_analogs, isa_scenarios

LABEL = "Modelled scenarios from similar past periods. Not a forecast. Not financial advice."


@pytest.fixture(scope="module")
def rs() -> ReturnSeries:
    return load_returns()


@pytest.fixture
def req() -> IsaBacktestRequest:
    return IsaBacktestRequest(weights={"global_equity": 0.6, "gilts": 0.4}, monthly_contribution=500.0)


def test_label_fan_and_paths(rs: ReturnSeries, req: IsaBacktestRequest) -> None:
    res = isa_scenarios(req, rs)
    assert res.label == LABEL and res.data_status == "mock"
    assert len(res.paths) >= 3
    for p in res.paths:
        assert len(p.index) == 37 and p.index[0] == 100.0
    for lo, mid, hi in zip(res.fan.p10, res.fan.p50, res.fan.p90, strict=True):
        assert lo <= mid <= hi


def test_label_cannot_be_dropped_or_changed(rs: ReturnSeries, req: IsaBacktestRequest) -> None:
    res = isa_scenarios(req, rs)
    assert "label" in IsaScenariosResult.model_json_schema()["properties"]
    assert res.model_dump()["label"] == LABEL
    with pytest.raises(ValueError):
        IsaScenariosResult(**{**res.model_dump(), "label": "Guaranteed returns"})


def test_analogs_constraints(rs: ReturnSeries) -> None:
    as_of = rs.months[-1]
    idx = sorted(rs.months.index(m) for m in find_analogs(rs, as_of, k=8, horizon_months=36, min_gap_months=12))
    assert len(idx) >= 3
    assert all(y - x >= 12 for x, y in zip(idx, idx[1:], strict=False))
    assert all(i + 36 <= len(rs.months) - 1 and i + 36 < rs.months.index(as_of) for i in idx)


def test_deterministic(rs: ReturnSeries, req: IsaBacktestRequest) -> None:
    assert isa_scenarios(req, rs).model_dump() == isa_scenarios(req, rs).model_dump()


def test_too_few_analogs(rs: ReturnSeries, req: IsaBacktestRequest) -> None:
    with pytest.raises(ValueError):
        isa_scenarios(req, rs, as_of_month="2003-06")
