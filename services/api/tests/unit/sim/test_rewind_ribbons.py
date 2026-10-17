"""Rewind (free once, unlimited with pass, 402 otherwise) and ribbons."""

from __future__ import annotations

import pytest

from lifeline_contracts.domain import Life
from lifeline_contracts.macro import MacroTable
from lifeline_sim import api, replay
from lifeline_sim.errors import SimError
from lifeline_sim.ribbons import RIBBONS

from .helpers import play, preset


def _play_years(macro: MacroTable, years: int, seed: int = 424242, pick: str = "default") -> Life:
    life = api.new_life("lf_rw", preset("nurse-leeds"), "preset", 2006, seed, macro)
    for _ in range(years):
        life = api.age(life, macro).life
        for ev in list(life.pending_events):
            cid = next(c.id for c in ev.choices if c.is_default) if pick == "default" else ev.choices[-1].id
            life = api.choose(life, ev.id, cid, macro).life
    return life


def _first_decision(life: Life) -> str:
    return next(h.decision_id for h in life.history if h.decision_id and h.decision_id.startswith("ev-"))


def test_rewind_flips_choice_and_drops_later(macro: MacroTable) -> None:
    life = _play_years(macro, 6, pick="last")
    target = _first_decision(life)
    old = next(h for h in life.history if h.decision_id == target)
    res = api.rewind(life, target, macro)
    new = res.life
    assert res.abandoned_net_worth == life.finances.net_worth
    assert res.abandoned_index == life.index.value
    assert new.year == old.year
    last = new.history[-1]
    assert last.decision_id == target and last.choice_id != old.choice_id
    assert all(h.year <= old.year for h in new.history)
    assert new.rewind.free_left == 0


def test_rewind_matches_fresh_play(macro: MacroTable) -> None:
    """The rewound life equals a life played the new way from the start."""
    life = _play_years(macro, 4, pick="last")
    target = _first_decision(life)
    new = api.rewind(life, target, macro).life
    replay._STATES.clear()
    fresh = api.new_life("lf_rw", preset("nurse-leeds"), "preset", 2006, 424242, macro)
    flipped = {h.decision_id: h.choice_id for h in new.history if h.decision_id}
    while fresh.year < new.year or any(e.id in flipped for e in fresh.pending_events):
        if not fresh.pending_events:
            fresh = api.age(fresh, macro).life
        for ev in list(fresh.pending_events):
            if ev.id in flipped:
                fresh = api.choose(fresh, ev.id, flipped[ev.id] or "", macro).life
        if fresh.year >= new.year:
            break
    assert fresh.finances == new.finances
    assert [e.id for e in fresh.pending_events] == [e.id for e in new.pending_events]


def test_second_rewind_needs_pass(macro: MacroTable) -> None:
    life = _play_years(macro, 4)
    target = _first_decision(life)
    life = api.rewind(life, target, macro).life
    with pytest.raises(SimError) as e:
        api.rewind(life, target, macro)
    assert e.value.code == "payment_required"
    passed = life.model_copy(update={"rewind": life.rewind.model_copy(update={"has_pass": True})})
    again = api.rewind(passed, target, macro).life
    again = api.rewind(again, target, macro).life
    assert again.rewind.has_pass


def test_rewind_unknown(macro: MacroTable) -> None:
    life = _play_years(macro, 1)
    with pytest.raises(SimError) as e:
        api.rewind(life, "ev-1900-1", macro)
    assert e.value.code == "not_found"


def test_rewind_an_action_removes_it(macro: MacroTable) -> None:
    life = api.new_life("lf", preset("nurse-leeds"), "preset", 2006, 1, macro)
    life = api.act(life, "assets", "buy_shares", {"amount": 1000}, macro).life
    assert life.finances.investments >= 1000
    new = api.rewind(life, "act-2006-1", macro).life
    assert new.finances.investments < 1000
    assert all(h.decision_id != "act-2006-1" for h in new.history)


def test_ribbons_catalogue_and_earned(macro: MacroTable) -> None:
    assert len(RIBBONS) >= 8
    life = play(macro, "banker-london", 2006, seed=3, max_ages=80)
    ids = {r.id for r in life.ribbons}
    assert ids, "a long banker life earns at least one ribbon"
    for r in life.ribbons:
        assert r.reason.endswith(")."), r.reason
