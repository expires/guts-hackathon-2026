import pytest

from playyourself.decision.habits import FactorValue, HabitVector, Window
from playyourself.decision.scoring import (
    BANDS,
    overall_score,
    rebase_to_100,
    score_factor,
)


@pytest.mark.parametrize("name", list(BANDS))
def test_band_endpoints(name):
    for raw, score in BANDS[name]:
        assert score_factor(name, raw) == score


def test_interpolation_midpoint():
    assert score_factor("savings_rate", 0.05) == 35  # midway 20..50
    assert score_factor("runway_months", 4.5) == 65  # midway 50..80
    assert score_factor("spend_stability", 0.5) == 50
    assert score_factor("discretionary_share", 0.325) == 55  # lower is better


def test_clamping():
    assert score_factor("savings_rate", -5) == 0
    assert score_factor("savings_rate", 5) == 100
    assert score_factor("runway_months", 100) == 100
    assert score_factor("subscription_creep", -1) == 100
    assert score_factor("subscription_creep", 9) == 0
    assert score_factor("isa_diversification", 0.01) == 100


def test_none_passthrough():
    assert score_factor("savings_rate", None) is None


def test_shock_uses_runway_bands():
    assert BANDS["shock_resilience"] == BANDS["runway_months"]


def _hv(scores):
    return HabitVector(
        window=Window(months=6, end="2026-09-30"),
        factors={f"f{i}": FactorValue(raw=None, score=s) for i, s in enumerate(scores)},
    )


def test_overall_score():
    assert overall_score(_hv([50, 75, None])) == 62  # round(62.5) banker's -> 62
    assert overall_score(_hv([None, None])) is None


def test_rebase_to_100():
    assert rebase_to_100([50, 75, 100]) == [100, 150, 200]
    assert rebase_to_100([0, 20, 10]) == [0, 100, 50]
    assert rebase_to_100([0, 0]) == [0.0, 0.0]
    assert rebase_to_100([]) == []
