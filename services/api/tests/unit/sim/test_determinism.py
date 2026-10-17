from __future__ import annotations

from lifeline_contracts.macro import MacroTable
from lifeline_sim import api, replay
from lifeline_sim.index import load_weights

from .helpers import play, preset


def _clear_memo() -> None:
    replay._STATES.clear()
    replay._VIEWS.clear()


def test_same_seed_same_life_200_ages(macro: MacroTable) -> None:
    a = play(macro, seed=11, max_ages=200, strategy="random")
    _clear_memo()
    b = play(macro, seed=11, max_ages=200, strategy="random")
    assert a.model_dump() == b.model_dump()
    assert not a.alive  # 200 ages always ends the life


def test_same_seed_same_life_banker(macro: MacroTable) -> None:
    a = play(macro, pid="banker-london", seed=5, max_ages=200)
    b = play(macro, pid="banker-london", seed=5, max_ages=200)
    assert a.model_dump_json() == b.model_dump_json()


def test_different_seed_different_life(macro: MacroTable) -> None:
    a = play(macro, seed=1, max_ages=20)
    b = play(macro, seed=2, max_ages=20)
    assert [h.text for h in a.history] != [h.text for h in b.history]


def test_replay_from_scratch_matches_incremental(macro: MacroTable) -> None:
    life = play(macro, seed=99, max_ages=25, strategy="random")
    _clear_memo()
    w = load_weights()
    spec = replay.LifeSpec(character=life.character, mode=life.mode, start_year=life.start_year, seed=life.seed)
    decisions = [(h.event_id, h.choice_id) for h in life.history if h.event_id and h.choice_id]
    s = replay.replay(spec, decisions, life.year, replay.view_for(macro), w)
    assert round(s.net_worth, 2) == life.finances.net_worth
    assert s.missed == life.index.missed_payments


def test_functions_do_not_mutate_inputs(macro: MacroTable) -> None:
    life = api.new_life("x", preset("nurse-leeds"), "preset", 2006, 3, macro)
    before = life.model_dump_json()
    aged = api.age(life, macro).life
    assert life.model_dump_json() == before
    if aged.pending_events:
        ev = aged.pending_events[0]
        snap = aged.model_dump_json()
        api.choose(aged, ev.id, ev.choices[-1].id, macro)
        assert aged.model_dump_json() == snap
