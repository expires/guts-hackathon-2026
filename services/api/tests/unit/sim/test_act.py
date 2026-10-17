"""Tab actions (Tier 1): act(), available_actions, replay of actions."""

from __future__ import annotations

import pytest

from lifeline_contracts.domain import Life
from lifeline_contracts.macro import MacroTable
from lifeline_sim import api, replay
from lifeline_sim.actions import ACTIONS, TABS, decode_choice, encode_choice
from lifeline_sim.errors import SimError

from .helpers import preset


def _new(macro: MacroTable, pid: str = "nurse-leeds", start: int = 2006, seed: int = 99) -> Life:
    return api.new_life("lf_act", preset(pid), "preset", start, seed, macro)


def _answer_defaults(life: Life, macro: MacroTable) -> Life:
    for ev in list(life.pending_events):
        life = api.choose(life, ev.id, next(c.id for c in ev.choices if c.is_default), macro).life
    return life


def test_every_tab_has_actions(macro: MacroTable) -> None:
    life = _new(macro)
    tabs = {a.tab for a in life.available_actions}
    assert tabs == set(TABS)
    assert all(sum(1 for a in ACTIONS if a.tab == t) >= 4 for t in TABS)


def test_choice_id_encoding() -> None:
    cid = encode_choice("money", "save", {"amount": 1500.0})
    assert cid == "money/save?amount=1500"
    assert decode_choice(cid) == ("money", "save", {"amount": 1500.0})
    assert encode_choice("job", "ask_raise", {}) == "job/ask_raise"


def test_act_records_decision_and_moves_money(macro: MacroTable) -> None:
    life = _new(macro)
    cash = life.finances.cash
    res = api.act(life, "money", "save", {"amount": 500}, macro)
    assert res.outcome.choice_id == "money/save?amount=500"
    assert res.outcome.event_id == "act-2006-1"
    assert res.life.finances.savings == pytest.approx(life.finances.savings + 500)
    assert res.life.finances.cash == pytest.approx(cash - 500)
    h = res.life.history[-1]
    assert h.decision_id == "act-2006-1" and h.choice_id == "money/save?amount=500"
    assert res.concept_unlocked == "emergency-fund" and res.lesson is not None


def test_once_per_year_and_invalid(macro: MacroTable) -> None:
    life = _new(macro)
    life = api.act(life, "activities", "gym", {}, macro).life
    with pytest.raises(SimError) as e:
        api.act(life, "activities", "gym", {}, macro)
    assert e.value.code == "invalid_action"
    with pytest.raises(SimError):
        api.act(life, "job", "fly_to_moon", {}, macro)
    with pytest.raises(SimError):
        api.act(life, "money", "save", {"amount": -5}, macro)
    with pytest.raises(SimError):
        api.act(life, "activities", "holiday", {"amount": 5}, macro)
    life = _answer_defaults(api.age(life, macro).life, macro)
    life = api.act(life, "activities", "gym", {}, macro).life  # allowed again next year


def _play_with_actions(macro: MacroTable, seed: int) -> Life:
    life = _new(macro, seed=seed)
    life = api.act(life, "money", "save", {"amount": 300}, macro).life
    plan = [
        ("job", "ask_raise", {}),
        ("assets", "buy_shares", {"amount": 400}),
        ("activities", "course", {}),
        ("relationships", "date", {}),
        ("money", "pension_topup", {"amount": 200}),
        ("job", "new_job", {}),
    ]
    for tab, aid, params in plan:
        life = api.age(life, macro).life
        life = api.act(life, tab, aid, params, macro).life
        life = _answer_defaults(life, macro)
    return life


def test_actions_replay_exactly(macro: MacroTable) -> None:
    a = _play_with_actions(macro, 5)
    replay._STATES.clear()
    b = _play_with_actions(macro, 5)
    assert a.model_dump_json() == b.model_dump_json()
    replay._STATES.clear()
    stored = Life.model_validate_json(a.model_dump_json())
    nxt = api.age(stored, macro).life
    nxt2 = api.age(a, macro).life
    assert nxt.model_dump_json() == nxt2.model_dump_json()


def test_actions_change_index_not_twin(macro: MacroTable) -> None:
    plain = _new(macro, seed=7)
    acted = api.act(plain, "assets", "buy_shares", {"amount": 1000}, macro).life
    for _ in range(5):
        plain = _answer_defaults(api.age(plain, macro).life, macro)
        acted = _answer_defaults(api.age(acted, macro).life, macro)
    assert plain.index.value == 100.0
    assert acted.history[-1].autopilot_net_worth == plain.history[-1].autopilot_net_worth
    assert acted.finances.investments > plain.finances.investments


def test_buy_and_sell_home(macro: MacroTable) -> None:
    life = api.new_life("lf", preset("banker-london"), "preset", 2012, 3, macro)
    life = api.act(life, "assets", "sell_home", {}, macro).life
    assert life.finances.property_value == 0 and life.finances.mortgage_balance == 0
    life = _answer_defaults(api.age(life, macro).life, macro)
    can = next(a for a in life.available_actions if a.id == "buy_home")
    assert can.enabled
    life = api.act(life, "assets", "buy_home", {}, macro).life
    assert life.finances.property_value > 0 and life.finances.mortgage_balance > 0


def test_dead_life_has_no_actions(macro: MacroTable) -> None:
    from .helpers import play

    life = play(macro, "pensioner", 2006, seed=1, max_ages=200)
    assert not life.alive and life.available_actions == []
    with pytest.raises(SimError):
        api.act(life, "activities", "gym", {}, macro)
