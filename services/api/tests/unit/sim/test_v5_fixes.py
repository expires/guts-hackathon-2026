"""V5 leftovers: preset money scales with start year, crash-year key moments, no CPI chip on house events."""

from __future__ import annotations

from lifeline_contracts.macro import MacroKey, MacroTable
from lifeline_sim import api
from lifeline_sim.events.engine import templates_by_id

from .helpers import preset


def test_preset_money_scales_with_start_year(macro: MacroTable) -> None:
    a = api.new_life("a", preset("nurse-leeds"), "preset", 2006, 1, macro).finances
    b = api.new_life("b", preset("nurse-leeds"), "preset", 2021, 1, macro).finances
    assert (a.annual_income, a.student_loan) == (24800.0, 18000.0)
    assert b.annual_income > a.annual_income
    assert b.student_loan > a.student_loan
    assert b.net_worth != a.net_worth


def test_edited_preset_is_not_scaled(macro: MacroTable) -> None:
    edited = preset("nurse-leeds").model_copy(update={"annual_income": 30000.0})
    life = api.new_life("c", edited, "preset", 2021, 1, macro)
    assert life.finances.annual_income == 30000.0


def test_banker_summary_shows_crash_year(macro: MacroTable) -> None:
    life = api.new_life("d", preset("banker-london"), "preset", 2006, 424242, macro)
    while life.year < 2010:
        life = api.age(life, macro).life
        for ev in list(life.pending_events):
            life = api.choose(life, ev.id, next(c.id for c in ev.choices if c.is_default), macro).life
    years = {k.year for k in api.summary(life).key_moments}
    assert 2008 in years or 2009 in years


def test_house_events_do_not_cite_cpi() -> None:
    for tid in ("home.buy_the_dip", "home.price_crash", "home.first_home"):
        assert MacroKey.CPI_INFLATION not in templates_by_id()[tid].macro_keys
