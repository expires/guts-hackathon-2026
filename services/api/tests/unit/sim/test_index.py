from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from lifeline_contracts.macro import MacroTable
from lifeline_sim.index import drawdown_fraction, index_value, load_weights, r_value

from .helpers import play

R = st.floats(min_value=-50, max_value=50, allow_nan=False)
MISSED = st.integers(min_value=0, max_value=200)
DD = st.floats(min_value=0, max_value=1, allow_nan=False)


def test_weights_come_from_toml() -> None:
    w = load_weights()
    assert (w.base, w.r_weight, w.missed_payment_penalty, w.drawdown_penalty, w.floor) == (100.0, 0.1, 2.0, 20.0, 0.0)


def test_exact_formula() -> None:
    # 100 * (1 + 0.1 * (0.5 - 0.2)) - 2 * 1 - 20 * 0.1 = 103 - 2 - 2 = 99
    assert index_value(0.5, 0.2, 1, 0.1) == pytest.approx(99.0)


@given(R)
def test_fairness_same_r_is_100(r: float) -> None:
    assert index_value(r, r, 0, 0.0) == pytest.approx(100.0, abs=0.01)


@given(R, R, R, MISSED, DD)
def test_monotone_in_r_player(r1: float, r2: float, ra: float, missed: int, dd: float) -> None:
    lo, hi = sorted((r1, r2))
    assert index_value(lo, ra, missed, dd) <= index_value(hi, ra, missed, dd)


@given(R, R, MISSED, MISSED, DD)
def test_decreasing_in_missed(rp: float, ra: float, m1: int, m2: int, dd: float) -> None:
    lo, hi = sorted((m1, m2))
    assert index_value(rp, ra, hi, dd) <= index_value(rp, ra, lo, dd)


@given(R, R, MISSED, DD, DD)
def test_decreasing_in_drawdown(rp: float, ra: float, missed: int, d1: float, d2: float) -> None:
    lo, hi = sorted((d1, d2))
    assert index_value(rp, ra, missed, hi) <= index_value(rp, ra, missed, lo)


@given(R, R, MISSED, DD)
def test_floor_at_zero(rp: float, ra: float, missed: int, dd: float) -> None:
    assert index_value(rp, ra, missed, dd) >= 0.0


def test_floor_hits() -> None:
    assert index_value(-40, 0, 10, 1.0) == 0.0


def test_r_uses_income_floor() -> None:
    w = load_weights()
    assert r_value(15_000, 5_000, 0, w) == pytest.approx(10_000 / w.min_income0)
    assert r_value(15_000, 5_000, 40_000, w) == pytest.approx(0.25)


def test_drawdown_fraction() -> None:
    assert drawdown_fraction(100_000, 80_000, 30_000) == pytest.approx(0.2)
    assert drawdown_fraction(-5_000, -10_000, 25_000) == pytest.approx(0.2)  # in debt: measured against pay
    assert drawdown_fraction(50_000, 60_000, 25_000) == 0.0
    assert drawdown_fraction(10_000, -1_000_000, 25_000) == 1.0


PRESET_IDS = ["nurse-leeds", "banker-london", "student", "plumber", "pensioner", "teacher-glasgow"]


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(pid=st.sampled_from(PRESET_IDS), seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_copying_autopilot_scores_exactly_100(macro: MacroTable, pid: str, seed: int) -> None:
    """ADR 0013: default choice everywhere gives Index 100 at every settled point, for any seed."""
    start = 2006 if pid != "student" else 2021
    life = play(macro, pid=pid, start=start, seed=seed, max_ages=200)
    last_per_year = {h.year: h for h in life.history}  # entry after the year's last choice
    for h in last_per_year.values():
        assert h.net_worth == pytest.approx(h.autopilot_net_worth, abs=0.01)
        assert h.index == pytest.approx(100.0, abs=0.01)
    assert life.index.value == pytest.approx(100.0, abs=0.01)


def test_relative_penalties() -> None:
    # Twin missed 3 and fell 0.2; player missed 1 and fell 0.1: +4 and +2 over 100.
    assert index_value(0.0, 0.0, 1, 0.1, missed_autopilot=3, drawdown_autopilot=0.2) == pytest.approx(106.0)
    # A penalty-free twin gives the BUILD_SPEC formula.
    assert index_value(0.5, 0.2, 1, 0.1) == pytest.approx(99.0)


def test_docs_worked_example() -> None:
    """docs/index.md worked example."""
    w = load_weights()
    rp = r_value(14_300, -10_500, 24_800, w)
    ra = r_value(9_340, -10_500, 24_800, w)
    dd = drawdown_fraction(20_000, 18_760, 24_800, w)
    assert (rp, ra, dd) == (pytest.approx(1.0), pytest.approx(0.8), pytest.approx(0.05))
    assert index_value(rp, ra, 1, dd, w=w) == pytest.approx(99.0)


@pytest.mark.parametrize("pid,seed", [("banker-london", 5), ("nurse-leeds", 4242), ("plumber", 1)])
def test_index_does_not_jump_before_answers(macro: MacroTable, pid: str, seed: int) -> None:
    """V2 W-A: while events are open the Index compares with a twin that answered the same events."""
    from lifeline_sim import api

    from .helpers import preset

    life = api.new_life("x", preset(pid), "preset", 2006, seed, macro)
    while life.alive:
        before = life.index.value
        life = api.age(life, macro).life
        if life.pending_events:
            # Ageing alone moves both lives the same way, so a default-only player stays at 100.
            assert life.index.value == pytest.approx(before, abs=0.01)
        for ev in list(life.pending_events):
            life = api.choose(life, ev.id, next(c.id for c in ev.choices if c.is_default), macro).life
            assert life.index.value == pytest.approx(100.0, abs=0.01)
