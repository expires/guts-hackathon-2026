"""Demo story (V5 F2): nurse in Leeds vs banker in London, 2006 to 2010, all default choices."""

from __future__ import annotations

import re

from lifeline_contracts.domain import Life
from lifeline_contracts.macro import MacroTable
from lifeline_sim import api

from .helpers import preset


def _play_to(macro: MacroTable, pid: str, end: int) -> tuple[Life, dict[int, float], set[str]]:
    life = api.new_life("demo", preset(pid), "preset", 2006, 424242, macro)
    nw = {2006: life.finances.net_worth}
    sources: set[str] = set()
    while life.year < end:
        res = api.age(life, macro)
        life = res.life
        sources |= {s.source for e in res.events for s in e.sources}
        for ev in list(life.pending_events):
            cid = next(c.id for c in ev.choices if c.is_default)
            life = api.choose(life, ev.id, cid, macro).life
        nw[life.year] = life.finances.net_worth
    return life, nw, sources


def _bonus(life: Life, year: int) -> float:
    text = next(h.text for h in life.history if h.year == year and h.decision_id is None)
    if "No bonus this year." in text:
        return 0.0
    m = re.search(r"Your bonus was £([\d,]+)", text)
    assert m, text
    return float(m.group(1).replace(",", ""))


def test_banker_feels_the_crash(macro: MacroTable) -> None:
    life, nw, sources = _play_to(macro, "banker-london", 2010)
    assert min(nw[2008], nw[2009]) < nw[2007]
    assert _bonus(life, 2008) < _bonus(life, 2007)
    assert sources & {"landregistry", "boe"}


def test_nurse_keeps_her_job(macro: MacroTable) -> None:
    life, _, sources = _play_to(macro, "nurse-leeds", 2010)
    assert not any(h.event_id and h.event_id.startswith("ev-") and "redundan" in h.text for h in life.history)
    assert life.job is not None and life.job.title == "Staff nurse"
    assert sources & {"landregistry", "boe"}


def test_uk_only_series_have_no_uk_average_note(macro: MacroTable) -> None:
    _, _, _ = _play_to(macro, "nurse-leeds", 2009)
    from lifeline_contracts.macro import MacroKey
    from lifeline_sim.replay import view_for

    mv = view_for(macro)
    for key in (MacroKey.BANK_RATE, MacroKey.CPI_INFLATION, MacroKey.STOCK_RETURN, MacroKey.MORTGAGE_2Y_FIX):
        ref = mv.source_ref(key, 2008, "yorkshire-and-the-humber")
        assert ref is not None and (ref.note or "").find("UK average used") < 0


def test_market_crash_cites_stock_series_only(macro: MacroTable) -> None:
    from lifeline_contracts.macro import MacroKey
    from lifeline_sim.events.engine import templates_by_id

    assert templates_by_id()["money.market_crash"].macro_keys == (MacroKey.STOCK_RETURN,)
