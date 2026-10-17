"""Rebuild a life's internal state by replay.

State(t) = f(character, mode, start_year, seed, recorded choices, MacroTable). Nothing else.

- Player: apply the recorded choices (from `Life.history`) in recorded order, year by year.
- Autopilot twin: same character and seed; the default choice for every event; no tab actions.
- Rewind (Tier 1): replay with the target choice changed and later choices dropped.

A small in-process memo stores states that API calls produced, so a normal game (AGE, choose,
AGE, ...) costs one year of work per call instead of a full replay. The memo never changes a
result: a hit returns a copy of the exact state a replay would build. It keeps a strong
reference to each MacroTable it has seen, so an `id()` is never reused while cached.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass

from lifeline_contracts.domain import CharacterSpec, Deltas, Event, LifeMode
from lifeline_contracts.macro import MacroTable
from lifeline_sim.actions import is_action_id, run_action
from lifeline_sim.events.engine import Resolution, apply_effects, resolve, templates_by_id
from lifeline_sim.index import IndexWeights
from lifeline_sim.macroview import MacroView
from lifeline_sim.setup import Setup
from lifeline_sim.state import SimState, initial_state
from lifeline_sim.step import step_year

Decision = tuple[str, str]  # (event_id, choice_id)

_VIEWS: OrderedDict[int, tuple[MacroTable, MacroView]] = OrderedDict()
_VIEWS_MAX = 4
_STATES: OrderedDict[tuple[object, ...], SimState] = OrderedDict()
_STATES_MAX = 512


def view_for(macro: MacroTable) -> MacroView:
    hit = _VIEWS.get(id(macro))
    if hit is not None and hit[0] is macro:
        _VIEWS.move_to_end(id(macro))
        return hit[1]
    mv = MacroView(macro)
    _VIEWS[id(macro)] = (macro, mv)
    while len(_VIEWS) > _VIEWS_MAX:
        _VIEWS.popitem(last=False)
    return mv


def last_view() -> MacroView | None:
    """The view of the most recently used MacroTable in this process, if any."""
    if not _VIEWS:
        return None
    return next(reversed(_VIEWS.values()))[1]


@dataclass(frozen=True)
class LifeSpec:
    character: CharacterSpec
    mode: LifeMode
    start_year: int
    seed: int
    setup: Setup = Setup()

    def digest(self) -> str:
        raw = f"{self.character.model_dump_json()}|{self.mode}|{self.start_year}|{self.seed}|{self.setup.encode()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def event_year(event_id: str) -> int | None:
    """Event ids are `ev-<year>-<n>`. Tab action ids are `act-<year>-<n>`."""
    parts = event_id.split("-")
    if len(parts) == 3 and parts[0] in ("ev", "act") and parts[1].isdigit():
        return int(parts[1])
    return None


def apply_decisions(s: SimState, decisions: Sequence[Decision], mv: MacroView, w: IndexWeights) -> None:
    """Apply one year's recorded decisions in recorded order: event choices and tab actions."""
    for decision_id, choice_id in decisions:
        if is_action_id(decision_id):
            if run_action(s, mv, decision_id, choice_id) is not None:
                s.track_drawdown(w)
            continue
        found = next((e for e in s.pending if e.id == decision_id), None)
        if found is not None and any(c.id == choice_id for c in found.choices):
            apply_choice(s, found, choice_id, w)


def apply_choice(s: SimState, event: Event, choice_id: str, w: IndexWeights) -> tuple[Resolution, Deltas]:
    res = resolve(event, choice_id, s.seed)
    deltas = apply_effects(s, res.effects)
    lt = templates_by_id().get(event.template_id)
    living = res.effects.get("living", 0.0)
    for tag in lt.t.tags if lt is not None else ():
        s.tag_cost[tag] = s.tag_cost.get(tag, 0.0) - deltas.money
        if isinstance(living, float | int) and living:
            s.tag_living[tag] = s.tag_living.get(tag, 0.0) + float(living)
    s.pending = [e for e in s.pending if e.id != event.id]
    s.track_drawdown(w)
    return res, deltas


def _key(
    mv: MacroView, spec: LifeSpec, autopilot: bool, decisions: Sequence[Decision], year: int
) -> tuple[object, ...]:
    return (id(mv.table), spec.digest(), autopilot, tuple(decisions), year)


def remember(mv: MacroView, spec: LifeSpec, autopilot: bool, decisions: Sequence[Decision], s: SimState) -> None:
    key = _key(mv, spec, autopilot, [d for d in decisions if (event_year(d[0]) or 0) <= s.year], s.year)
    _STATES[key] = s.clone()
    _STATES.move_to_end(key)
    while len(_STATES) > _STATES_MAX:
        _STATES.popitem(last=False)


def replay(
    spec: LifeSpec,
    decisions: Sequence[Decision],
    until_year: int,
    mv: MacroView,
    w: IndexWeights,
    autopilot: bool = False,
) -> SimState:
    """State at the end of `until_year` with the given choices applied.

    For the player, events of `until_year` without a recorded choice stay in `pending`.
    For the autopilot, every event gets its default choice.
    """
    decisions = [] if autopilot else list(decisions)
    by_year: dict[int, list[Decision]] = {}
    for d in decisions:
        by_year.setdefault(event_year(d[0]) or 0, []).append(d)

    s: SimState | None = None
    for y in range(until_year, spec.start_year - 1, -1):
        prefix = [d for d in decisions if (event_year(d[0]) or 0) <= y]
        hit = _STATES.get(_key(mv, spec, autopilot, prefix, y))
        if hit is not None:
            s = hit.clone()
            break
        if y < until_year - 64:
            break
    if s is None:
        s = initial_state(spec.character, spec.mode, spec.start_year, spec.seed, mv, w, spec.setup)
        # Tab actions taken before the first AGE.
        apply_decisions(s, by_year.get(s.year, []), mv, w)

    while s.year < until_year and s.alive:
        step_year(s, mv, w)
        if autopilot:
            for ev in list(s.pending):
                default = next(c.id for c in ev.choices if c.is_default)
                apply_choice(s, ev, default, w)
        else:
            apply_decisions(s, by_year.get(s.year, []), mv, w)
    return s
