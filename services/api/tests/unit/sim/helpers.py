"""Shared helpers for sim tests."""

from __future__ import annotations

import random

from lifeline_contracts.domain import CharacterSpec, Life
from lifeline_contracts.macro import MacroTable
from lifeline_sim import api


def preset(pid: str) -> CharacterSpec:
    return next(c for c in api.presets() if c.id == pid)


def play(
    macro: MacroTable,
    pid: str = "nurse-leeds",
    start: int = 2006,
    seed: int = 424242,
    max_ages: int = 200,
    strategy: str = "default",
) -> Life:
    """Age up to `max_ages` times (or until death), answering every event."""
    life = api.new_life("lf_test", preset(pid), "preset", start, seed, macro)
    pick = random.Random(seed)
    for _ in range(max_ages):
        if not life.alive:
            break
        life = api.age(life, macro).life
        for ev in list(life.pending_events):
            if strategy == "default":
                cid = next(c.id for c in ev.choices if c.is_default)
            else:
                cid = pick.choice(ev.choices).id
            life = api.choose(life, ev.id, cid, macro).life
    return life
