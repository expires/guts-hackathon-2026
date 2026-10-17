"""ADR 0027: live mode has only real data, with gaps. The sim must not crash or use missing keys."""

from __future__ import annotations

import random

import pytest

from lifeline_contracts.domain import CharacterSpec
from lifeline_contracts.macro import MacroKey, MacroTable
from lifeline_sim import api
from lifeline_sim.events.engine import templates_by_id
from lifeline_sim.replay import view_for

# Real-data coverage in live mode (BOSS, 2026-10-17). Keys not listed have no data at all.
K = MacroKey
LIVE_RANGES: dict[MacroKey, tuple[int, int]] = {
    K.BANK_RATE: (1990, 2026),
    K.MORTGAGE_2Y_FIX: (1995, 2026),
    K.MORTGAGE_5Y_FIX: (1995, 2026),
    K.MORTGAGE_SVR: (1995, 2026),
    K.CARD_RATE: (1995, 2026),
    K.MORTGAGE_TRACKER: (1998, 2026),
    K.SAVINGS_RATE: (2011, 2026),
    K.CPI_INFLATION: (1990, 2026),
    K.ENERGY_PRICE_CHANGE: (1990, 2026),
    K.FUEL_PRICE_CHANGE: (1990, 2026),
    K.HOUSE_PRICE: (1990, 2026),
    K.HOUSE_PRICE_CHANGE: (1990, 2026),
    K.MEDIAN_PAY: (2002, 2025),
    K.UNEMPLOYMENT: (2004, 2025),
    K.OWNER_OCCUPIED_SHARE: (2021, 2021),
    K.RENT_CHANGE: (2006, 2026),
    K.GBP_USD: (1999, 2026),
    K.CRYPTO_RETURN: (2026, 2026),
    K.ENERGY_TARIFF: (2026, 2026),
}
UK_RENT_FROM = 2012
NEVER = {K.GILT_10Y, K.STOCK_RETURN, K.BURGLARY_RATE, K.FLOOD_RISK}


def _live_table(full: MacroTable) -> MacroTable:
    values = {}
    for key, v in full.values.items():
        rng = LIVE_RANGES.get(v.key)
        if rng is None or not rng[0] <= v.year <= rng[1]:
            continue
        if v.key == K.RENT_CHANGE and v.region is None and v.year < UK_RENT_FROM:
            continue
        values[key] = v.model_copy(update={"status": "live"})
    return MacroTable(values=values)


@pytest.fixture(scope="module")
def live(macro: MacroTable) -> MacroTable:
    return _live_table(macro)


def test_live_table_is_strict(live: MacroTable, macro: MacroTable) -> None:
    assert view_for(live).strict
    assert not view_for(macro).strict


def _characters() -> list[tuple[CharacterSpec, int]]:
    out = [(c, 2024 if c.id == "student" else 2006) for c in api.presets()]
    out += [(c, 1995) for c in api.presets() if c.id in ("banker-london", "pensioner")]
    out += [(c, 2015) for c in api.presets() if c.id in ("plumber", "teacher-glasgow", "nurse-leeds")]
    return out


def test_twenty_lives_no_crash_no_missing_keys(live: MacroTable) -> None:
    mv = view_for(live)
    chars = _characters()
    played = 0
    for i in range(20):
        char, start = chars[i % len(chars)]
        life = api.new_life(f"lv{i}", char, "random" if i % 5 == 0 else "preset", start, 500 + i, live)
        pick = random.Random(i)
        for _ in range(70):
            if not life.alive:
                break
            res = api.age(life, live)
            life = res.life
            env = mv.env(life.year, char.region)
            for ev in res.events:
                lt = templates_by_id()[ev.template_id]
                missing = [n for n in lt.macro_vars if n not in env]
                assert not missing, (ev.template_id, life.year, missing)
                assert not ({k for k in NEVER} & set(lt.macro_keys)), ev.template_id
            for ev in list(life.pending_events):
                life = api.choose(life, ev.id, pick.choice(ev.choices).id, live).life
            enabled = [a for a in life.available_actions if a.enabled]
            if enabled and pick.random() < 0.5:
                a = pick.choice(enabled)
                life = api.act(life, a.tab, a.id, {}, live).life
        played += 1
    assert played == 20


def test_stock_and_place_events_never_fire_live(live: MacroTable) -> None:
    banker = next(c for c in api.presets() if c.id == "banker-london")
    life = api.new_life("lv", banker, "preset", 2006, 1, live)
    seen: set[str] = set()
    for _ in range(25):
        life = api.age(life, live).life
        seen |= {e.template_id for e in life.pending_events}
        for ev in list(life.pending_events):
            life = api.choose(life, ev.id, next(c.id for c in ev.choices if c.is_default), live).life
    assert not seen & {"money.market_crash", "place.burglary", "place.flood", "work.bonus_cut"}
    assert life.index.value == 100.0


def test_simulated_label_helper() -> None:
    c = next(c for c in api.presets() if c.id == "plumber")
    labelled = api.label_simulated(c)
    assert labelled.blurb is not None and labelled.blurb.endswith(api.SIMULATED_LABEL)
    assert api.label_simulated(labelled) == labelled
    long = c.model_copy(update={"blurb": "x" * 200})
    assert len(api.label_simulated(long).blurb or "") <= 200


def test_data_gaps_debug_view(live: MacroTable, macro: MacroTable) -> None:
    banker = next(c for c in api.presets() if c.id == "banker-london")
    life = api.new_life("g", banker, "preset", 2006, 1, live)
    life = api.age(life, live).life
    for ev in list(life.pending_events):
        life = api.choose(life, ev.id, next(c.id for c in ev.choices if c.is_default), live).life
    assert "stock_return" in api.data_gaps(life, live)[2007]
    demo = api.age(api.new_life("g", banker, "preset", 2006, 1, macro), macro).life
    assert api.data_gaps(demo, macro) == {}
