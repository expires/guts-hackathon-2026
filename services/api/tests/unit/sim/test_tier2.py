"""Tier 2: compare_event_choices ("Not sure? Ask Penny") and the phone health signal."""

from __future__ import annotations

import pytest

from lifeline_contracts.domain import Life
from lifeline_contracts.macro import MacroTable
from lifeline_sim import api, replay
from lifeline_sim.errors import SimError
from lifeline_sim.health import HealthInput, health_effect

from .helpers import preset


def _first_event(macro: MacroTable, pid: str = "banker-london", seed: int = 424242) -> Life:
    life = api.new_life("t2", preset(pid), "preset", 2006, seed, macro)
    for _ in range(30):
        life = api.age(life, macro).life
        if life.pending_events:
            return life
    raise AssertionError("no event")


def test_projection_per_choice(macro: MacroTable) -> None:
    life = _first_event(macro)
    before = life.model_dump_json()
    ev = life.pending_events[0]
    out = api.compare_event_choices(life, ev.id, macro, years=3)
    assert life.model_dump_json() == before  # no mutation
    assert [p.choice_id for p in out] == [c.id for c in ev.choices]
    for p in out:
        assert p.years[0] == life.year and p.end_year == life.year + 3
        assert len(p.net_worth_path) == len(p.years) == 4
        assert p.end_net_worth == p.net_worth_path[-1]
        ids = {f.id for f in p.facts}
        assert f"{ev.id}.{p.choice_id}.end_net_worth" in ids
        assert next(f for f in p.facts if f.id.endswith(".cost")).value == p.cost
        assert p.sources
    again = api.compare_event_choices(life, ev.id, macro, years=3)
    assert [p.model_dump() for p in again] == [p.model_dump() for p in out]


def test_default_projection_matches_real_play(macro: MacroTable) -> None:
    """The default choice's projection equals answering defaults and ageing 3 times."""
    life = _first_event(macro)
    ev = life.pending_events[0]
    proj = next(p for p in api.compare_event_choices(life, ev.id, macro, years=3) if p.is_default)
    played = life
    nw = []
    for _ in range(4):
        for e in list(played.pending_events):
            played = api.choose(played, e.id, next(c.id for c in e.choices if c.is_default), macro).life
        nw.append(played.finances.net_worth)
        if played.year < life.year + 3:
            played = api.age(played, macro).life
    assert proj.net_worth_path == nw
    assert proj.index == played.index.value == 100.0


def test_projection_errors(macro: MacroTable) -> None:
    life = _first_event(macro)
    with pytest.raises(SimError):
        api.compare_event_choices(life, "ev-1900-1", macro)
    with pytest.raises(SimError):
        api.compare_event_choices(life, life.pending_events[0].id, macro, years=0)


def test_mortgage_projection_cost(macro: MacroTable) -> None:
    from .test_play_scenario import OWNER

    life = api.new_life("m", OWNER, "self", 2021, 7, macro)
    while not any(e.template_id == "home.deal_ends" for e in life.pending_events):
        for e in list(life.pending_events):
            life = api.choose(life, e.id, next(c.id for c in e.choices if c.is_default), macro).life
        life = api.age(life, macro).life
    ev = next(e for e in life.pending_events if e.template_id == "home.deal_ends")
    by = {p.choice_id: p for p in api.compare_event_choices(life, ev.id, macro, years=2)}
    assert set(by) == {"fix_2y", "fix_5y", "tracker", "svr"}
    assert all(p.cost > 0 for p in by.values())  # mortgage payments
    assert len({p.cost for p in by.values()}) > 1


def test_health_effect_rule() -> None:
    assert health_effect(HealthInput(steps_per_day=11000, sleep_hours=8)) == 10
    assert health_effect(HealthInput(steps_per_day=8500, sleep_hours=6.5)) == 3
    assert health_effect(HealthInput(steps_per_day=2000, sleep_hours=5)) == -10
    assert health_effect(HealthInput(sleep_hours=11)) == -2
    assert health_effect(HealthInput()) == 0
    with pytest.raises(ValueError):
        HealthInput(steps_per_day=-1)
    h = HealthInput(steps_per_day=8200, sleep_hours=7.5)
    assert HealthInput.decode(h.encode()) == h


def test_health_on_age_is_recorded_and_replayed(macro: MacroTable) -> None:
    life = api.new_life("h", preset("nurse-leeds"), "preset", 2006, 11, macro)
    plain = api.age(life, macro).life
    healthy = api.age(life, macro, HealthInput(steps_per_day=12000, sleep_hours=8)).life
    assert healthy.stats.health == min(100, plain.stats.health + 10) or healthy.stats.health > plain.stats.health
    entry = healthy.history[-1]
    assert entry.decision_id is None and entry.event_id == "hl-2007-1"
    assert entry.choice_id == "health?sleep=8&steps=12000"
    # replay from a stored copy gives the same life
    replay._STATES.clear()
    for e in list(healthy.pending_events):
        healthy = api.choose(healthy, e.id, next(c.id for c in e.choices if c.is_default), macro).life
    stored = Life.model_validate_json(healthy.model_dump_json())
    replay._STATES.clear()
    a = api.age(stored, macro).life
    b = api.age(healthy, macro).life
    assert a.model_dump_json() == b.model_dump_json()
    assert a.stats.health <= 100


def test_all_default_without_health_still_100(macro: MacroTable) -> None:
    from .helpers import play

    assert play(macro, "banker-london", 2006, seed=5, max_ages=25).index.value == 100.0
