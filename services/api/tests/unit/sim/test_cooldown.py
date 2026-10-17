"""No template fires again within 3 years in the same life, except `repeatable` ones."""

from __future__ import annotations

import random

import pytest

from lifeline_contracts.macro import MacroTable
from lifeline_sim import api
from lifeline_sim.events.engine import load_templates
from lifeline_sim.events.schema import Template
from lifeline_sim.params import EVENT_COOLDOWN_YEARS

PIDS = ("nurse-leeds", "banker-london", "student", "plumber", "pensioner", "teacher-glasgow")


def test_no_template_repeats_within_cooldown(macro: MacroTable) -> None:
    repeatable = {lt.t.id for lt in load_templates() if lt.t.repeatable}
    presets = {c.id: c for c in api.presets()}
    lives = 0
    for i in range(50):
        pid = PIDS[i % len(PIDS)]
        start = 2024 if pid == "student" else 2006
        life = api.new_life(f"cd{i}", presets[pid], "preset", start, 1000 + i, macro)
        pick = random.Random(i)
        last: dict[str, int] = {}
        for _ in range(60):
            if not life.alive:
                break
            res = api.age(life, macro)
            life = res.life
            for ev in res.events:
                if ev.template_id not in repeatable and ev.template_id in last:
                    gap = ev.year - last[ev.template_id]
                    assert gap >= EVENT_COOLDOWN_YEARS, (pid, i, ev.template_id, ev.year, gap)
                last[ev.template_id] = ev.year
            for ev in list(life.pending_events):
                cid = ev.choices[0].id if i % 2 else pick.choice(ev.choices).id
                life = api.choose(life, ev.id, cid, macro).life
        lives += 1
    assert lives == 50


def test_rent_rise_not_every_year(macro: MacroTable) -> None:
    nurse = next(c for c in api.presets() if c.id == "nurse-leeds")
    life = api.new_life("rr", nurse, "preset", 2006, 7, macro)
    years: list[int] = []
    for _ in range(20):
        life = api.age(life, macro).life
        years += [e.year for e in life.pending_events if e.template_id == "home.rent_rise"]
        for ev in list(life.pending_events):
            life = api.choose(life, ev.id, next(c.id for c in ev.choices if c.is_default), macro).life
    assert all(b - a >= EVENT_COOLDOWN_YEARS for a, b in zip(years, years[1:], strict=False))


def test_repeatable_needs_reason() -> None:
    assert all(lt.t.repeat_reason for lt in load_templates() if lt.t.repeatable)
    base = {
        "id": "work.x",
        "area": "work",
        "emoji": "x",
        "title": "t",
        "text": "t",
        "concept_id": "inflation",
        "probability": 0.1,
        "choices": [
            {"id": "a", "label": "A", "default": True, "text": "x", "good": True},
            {"id": "b", "label": "B", "text": "x", "good": False},
        ],
    }
    Template.model_validate({**base, "repeatable": True, "repeat_reason": "Yearly by law."})
    with pytest.raises(ValueError):
        Template.model_validate({**base, "repeatable": True})
