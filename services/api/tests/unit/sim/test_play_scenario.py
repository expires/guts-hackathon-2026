"""'Test it' scenarios (ADR 0018): play_scenario."""

from __future__ import annotations

import pytest

from lifeline_contracts.domain import CharacterSpec, Life
from lifeline_contracts.macro import MacroTable
from lifeline_sim import api
from lifeline_sim.errors import SimError
from lifeline_sim.events.engine import load_templates

OWNER = CharacterSpec(
    name="Demo",
    occupation="software developer",
    region="south-east",
    town="Reading",
    birth_year=1988,
    annual_income=52000,
    savings=12000,
    debt=800,
    housing="mortgage",
    property_value=320000,
    mortgage_balance=210000,
)

REQUIRED_TAGS = {
    "mortgage_deal_end",
    "mortgage_rate_change",
    "savings_rate_change",
    "energy_bill",
    "card_debt",
    "subscription",
    "budget_overspend",
}


def test_required_tags_exist() -> None:
    tags = {tag for lt in load_templates() for tag in lt.t.tags}
    assert tags >= REQUIRED_TAGS


@pytest.mark.parametrize("option", ["fix_2y", "fix_5y", "tracker", "svr"])
def test_deal_end_fires_in_test_period(macro: MacroTable, option: str) -> None:
    life = api.play_scenario("s1", OWNER, 2021, 2023, {"mortgage_deal_end": option}, 7, macro)
    assert life.year == 2023 and not life.pending_events
    picks = [(h.year, h.choice_id) for h in life.history if h.event_id and h.year == 2022]
    assert (2022, option) in picks


def test_alias_and_template_id_keys(macro: MacroTable) -> None:
    by_alias = api.play_scenario("s", OWNER, 2021, 2023, {"mortgage_deal_end": "keep"}, 7, macro)
    by_id = api.play_scenario(
        "s", OWNER, 2021, 2023, {"home.deal_ends": "svr", "mortgage_deal_end": "fix_5y"}, 7, macro
    )
    first = [h.choice_id for h in by_alias.history if h.year == 2022 and h.event_id][0]
    assert first == "svr"
    assert [h.choice_id for h in by_id.history if h.year == 2022 and h.event_id][0] == "svr"


def test_options_differ_and_are_deterministic(macro: MacroTable) -> None:
    a = api.play_scenario("s", OWNER, 2021, 2024, {"mortgage_deal_end": "fix_5y"}, 7, macro)
    b = api.play_scenario("s", OWNER, 2021, 2024, {"mortgage_deal_end": "fix_5y"}, 7, macro)
    c = api.play_scenario("s", OWNER, 2021, 2024, {"mortgage_deal_end": "svr"}, 7, macro)
    assert a.model_dump_json() == b.model_dump_json()
    assert a.finances.net_worth != c.finances.net_worth
    assert a.finances.mortgage_fixed_until == 2027


def test_default_policy_scores_100(macro: MacroTable) -> None:
    life = api.play_scenario("s", OWNER, 2021, 2025, {"mortgage_deal_end": "fix_2y"}, 11, macro)
    assert life.index.value == 100.0


def test_deal_end_year_override(macro: MacroTable) -> None:
    life = api.play_scenario(
        "s", OWNER, 2020, 2023, {"__deal_end_year": "2022", "mortgage_deal_end": "fix_5y"}, 7, macro
    )
    years = [h.year for h in life.history if h.choice_id == "fix_5y"]
    assert years == [2022]
    with pytest.raises(SimError):
        api.play_scenario("s", OWNER, 2020, 2023, {"__deal_end_year": "soon"}, 7, macro)


def test_stored_life_replays_and_continues(macro: MacroTable) -> None:
    life = api.play_scenario("s", OWNER, 2021, 2023, {"mortgage_deal_end": "tracker"}, 7, macro)
    stored = Life.model_validate_json(life.model_dump_json())
    from lifeline_sim import replay

    replay._STATES.clear()
    nxt = api.age(stored, macro).life
    replay._STATES.clear()
    again = api.age(Life.model_validate_json(life.model_dump_json()), macro).life
    assert nxt.model_dump_json() == again.model_dump_json()
    assert nxt.year == 2024
    for ev in nxt.pending_events:
        nxt = api.choose(nxt, ev.id, ev.choices[-1].id, macro).life
    assert not nxt.pending_events


def test_focus_makes_tagged_event_fire(macro: MacroTable) -> None:
    renter = next(c for c in api.presets() if c.id == "nurse-leeds")
    life = api.play_scenario("s", renter, 2021, 2023, {"energy_bill": "fix"}, 3, macro)
    tids = [h.choice_id for h in life.history if h.event_id]
    assert "fix" in tids


def test_bad_period(macro: MacroTable) -> None:
    with pytest.raises(SimError):
        api.play_scenario("s", OWNER, 2023, 2021, {}, 7, macro)
