"""Money plausibility over whole lives (V2 F1)."""

from __future__ import annotations

import pytest

from lifeline_contracts.domain import CharacterSpec
from lifeline_contracts.macro import MacroTable
from lifeline_engine.api import random_character
from lifeline_sim import params
from lifeline_sim.index import load_weights
from lifeline_sim.replay import apply_choice, view_for
from lifeline_sim.state import SimState, initial_state
from lifeline_sim.step import step_year

from .helpers import preset


def _characters(macro: MacroTable) -> list[tuple[CharacterSpec, int]]:
    out = [(preset("nurse-leeds"), 2006), (preset("banker-london"), 2006)]
    for seed in (3, 11, 23):
        c = random_character(seed, macro)
        out.append((c, max(1990, min(2026, c.birth_year + 25))))
    return out


def _accessible(s: SimState) -> float:
    pension = s.pension if s.age >= params.PENSION_ACCESS_AGE else 0.0
    equity_room = max(0.0, s.property_value * params.EQUITY_RELEASE_LTV - s.mortgage_balance)
    return s.savings + s.investments + s.crypto + pension + equity_room


@pytest.mark.parametrize("idx", range(5))
@pytest.mark.parametrize("seed", [1, 99, 4242, 424242])
def test_default_lives_do_not_miss_payments_when_wealthy(macro: MacroTable, idx: int, seed: int) -> None:
    character, start = _characters(macro)[idx]
    mv, w = view_for(macro), load_weights()
    s = initial_state(character, "preset", start, seed, mv, w)
    while s.alive:
        nw_before = s.net_worth
        step_year(s, mv, w)
        if s.last_missed:
            # Invariant 1: missed only when net worth was at most 2x income.
            assert nw_before <= 2 * max(s.income, 1.0), (s.year, s.age, nw_before, s.income)
            # Invariant 2: missed only when every accessible pot is empty.
            assert _accessible(s) < 1.0, (s.year, _accessible(s))
        for ev in list(s.pending):
            apply_choice(s, ev, next(c.id for c in ev.choices if c.is_default), w)


def test_presets_all_default_never_miss(macro: MacroTable) -> None:
    for pid in ("nurse-leeds", "banker-london"):
        for seed in (1, 99, 4242, 424242):
            mv, w = view_for(macro), load_weights()
            s = initial_state(preset(pid), "preset", 2006, seed, mv, w)
            while s.alive:
                step_year(s, mv, w)
                for ev in list(s.pending):
                    apply_choice(s, ev, next(c.id for c in ev.choices if c.is_default), w)
            assert s.missed == 0, (pid, seed)


def test_retirement_costs_bounded_by_income(macro: MacroTable) -> None:
    mv, w = view_for(macro), load_weights()
    s = initial_state(preset("banker-london"), "preset", 2006, 1, mv, w)
    while s.alive and s.age < 85:
        step_year(s, mv, w)
        for ev in list(s.pending):
            apply_choice(s, ev, next(c.id for c in ev.choices if c.is_default), w)
        if s.retired:
            assert s.last_costs <= max(s.last_net_income, 12 * params.MIN_LIVING_MONTHLY_2024 * 3) * 1.01


def test_death_year_text_matches_count(macro: MacroTable) -> None:
    from .helpers import play

    life = play(macro, pid="banker-london", seed=99, max_ages=200, strategy="random")
    text_total = sum(int(h.text.split("You missed ")[1].split()[0]) for h in life.history if "You missed " in h.text)
    assert text_total == life.index.missed_payments
    assert "You died at" in life.history[-1].text or any("You died at" in h.text for h in life.history)
