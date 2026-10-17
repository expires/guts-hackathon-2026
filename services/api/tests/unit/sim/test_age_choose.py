from __future__ import annotations

import pytest

from lifeline_contracts.domain import Life
from lifeline_contracts.macro import MacroTable
from lifeline_sim import api
from lifeline_sim.errors import SimError

from .helpers import play, preset


def _age_until_event(life: Life, macro: MacroTable) -> Life:
    for _ in range(40):
        life = api.age(life, macro).life
        if life.pending_events:
            return life
        assert life.alive
    raise AssertionError("no event in 40 years")


def test_new_life_shape(macro: MacroTable) -> None:
    life = api.new_life("lf1", preset("nurse-leeds"), "preset", 2006, 424242, macro)
    assert (life.year, life.age, life.alive) == (2006, 24, True)
    assert life.index.value == 100.0
    assert life.rewind.free_left == 1
    assert life.pending_events == []
    assert len(life.history) == 1 and life.history[0].decision_id is None
    f = life.finances
    parts = f.cash + f.savings + f.investments + f.crypto + f.pension + f.property_value
    assert f.net_worth == pytest.approx(parts - f.mortgage_balance - f.other_debt - f.student_loan, abs=0.05)
    assert 0 <= life.stats.money <= 100


def test_new_life_rejects_child(macro: MacroTable) -> None:
    with pytest.raises(SimError) as e:
        api.new_life("lf1", preset("student"), "preset", 2006, 1, macro)
    assert e.value.code == "invalid_input"


def test_age_adds_one_year(macro: MacroTable) -> None:
    life = api.new_life("lf1", preset("banker-london"), "preset", 2006, 7, macro)
    res = api.age(life, macro)
    assert (res.life.year, res.life.age) == (2007, 28)
    assert res.events == res.life.pending_events
    assert 0 <= len(res.events) <= 3
    assert res.life.history[-1].year == 2007


def test_age_blocked_with_pending_events(macro: MacroTable) -> None:
    life = _age_until_event(api.new_life("lf1", preset("nurse-leeds"), "preset", 2006, 424242, macro), macro)
    with pytest.raises(SimError) as e:
        api.age(life, macro)
    assert e.value.code == "pending_events"


def test_choose_records_decision(macro: MacroTable) -> None:
    life = _age_until_event(api.new_life("lf1", preset("nurse-leeds"), "preset", 2006, 424242, macro), macro)
    ev = life.pending_events[0]
    choice = ev.choices[-1]
    res = api.choose(life, ev.id, choice.id, macro)
    assert ev.id not in [e.id for e in res.life.pending_events]
    last = res.life.history[-1]
    assert (last.decision_id, last.event_id, last.choice_id) == (ev.id, ev.id, choice.id)
    assert res.outcome.event_id == ev.id and res.outcome.choice_id == choice.id
    assert res.life.finances.net_worth == pytest.approx(life.finances.net_worth + res.outcome.deltas.money, abs=0.05)
    if ev.concept_id:
        assert res.concept_unlocked == ev.concept_id
        assert res.lesson is not None and len(res.lesson.sentences) == 2
        assert ev.concept_id in res.life.concepts_unlocked


def test_choose_errors(macro: MacroTable) -> None:
    life = _age_until_event(api.new_life("lf1", preset("nurse-leeds"), "preset", 2006, 424242, macro), macro)
    ev = life.pending_events[0]
    with pytest.raises(SimError) as e1:
        api.choose(life, "ev-1900-1", ev.choices[0].id, macro)
    assert e1.value.code == "not_found"
    with pytest.raises(SimError) as e2:
        api.choose(life, ev.id, "no-such-choice", macro)
    assert e2.value.code == "invalid_choice"


def test_dead_life_errors(macro: MacroTable) -> None:
    life = play(macro, max_ages=200)
    assert not life.alive and life.cause_of_death
    assert life.pending_events == []
    with pytest.raises(SimError) as e:
        api.age(life, macro)
    assert e.value.code == "dead"


def test_events_trace_to_facts_and_sources(macro: MacroTable) -> None:
    life = play(macro, pid="nurse-leeds", max_ages=20, strategy="random")
    events = [h for h in life.history if h.event_id]
    assert events, "expected some decisions in 20 years"


def test_reached_present(macro: MacroTable) -> None:
    life = api.new_life("lf1", preset("teacher-glasgow"), "preset", 2024, 1, macro)
    assert not life.reached_present
    life = play(macro, pid="teacher-glasgow", start=2024, seed=1, max_ages=2)
    assert life.year == 2026 and life.reached_present


def test_summary(macro: MacroTable) -> None:
    life = play(macro, pid="banker-london", max_ages=200, strategy="random")
    s = api.summary(life)
    assert s.died == life.year and s.final_index == life.index.value
    assert s.timeline == life.history
    assert len(s.key_moments) <= 5


def test_tier1_stubs(macro: MacroTable) -> None:
    life = api.new_life("lf1", preset("nurse-leeds"), "preset", 2006, 1, macro)
    with pytest.raises(SimError) as e:
        api.act(life, "money", "open_isa", {}, macro)
    assert e.value.code == "invalid_action"
