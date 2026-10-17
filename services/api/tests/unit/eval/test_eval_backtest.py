from __future__ import annotations

from lifeline_contracts.domain import Evaluation
from lifeline_contracts.macro import MacroTable
from lifeline_engine import api
from lifeline_eval.backtest import BASELINE_TEXT
from tests.unit.engine.conftest import build_fixture_macro


def test_evaluate_valid_and_deterministic() -> None:
    macro = build_fixture_macro()
    a = api.evaluate(macro)
    assert a == api.evaluate(macro)
    Evaluation.model_validate(a.model_dump())
    assert a.n == len(a.periods) > 0
    assert a.baseline.startswith(BASELINE_TEXT)
    assert a.hit_rate == sum(p.hit for p in a.periods) / a.n
    for p in a.periods:
        assert p.end - p.start == 4


def test_evaluate_empty_table() -> None:
    e = api.evaluate(MacroTable(values={}))
    assert e.n == 0 and e.hit_rate == 0.0 and e.periods == []


def test_evaluation_reports_best_constant_rule() -> None:
    from lifeline_eval.backtest import evaluate
    from tests.unit.engine.conftest import build_fixture_macro

    ev = evaluate(build_fixture_macro())
    assert "Best constant rule: always" in ev.method
    assert "best constant rule" in ev.baseline
