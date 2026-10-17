"""Public sim API. Implements `lifeline_contracts.interfaces.SimAPI` as module functions.

All functions are pure: same inputs give the same outputs. They return new `Life` objects
and never mutate their inputs. Rule violations raise `SimError`.
"""

from __future__ import annotations

from collections.abc import Sequence

from lifeline_contracts.chat import ChatFact
from lifeline_contracts.domain import (
    ActionResult,
    AgeResult,
    AvailableAction,
    Challenge,
    CharacterSpec,
    ChoiceResult,
    Concept,
    HabitScore,
    KeyMoment,
    Life,
    LifeMode,
    LifeSummary,
    Outcome,
    RewindResult,
    RewindState,
    Ribbon,
    SourceRef,
    YearLog,
)
from lifeline_contracts.macro import MacroKey, MacroTable
from lifeline_contracts.play import DecisionOutcome, DecisionPrompt, StudentPath
from lifeline_sim import params as p
from lifeline_sim.actions import (
    action_decision_id,
    action_spec,
    available_actions,
    clean_params,
    encode_choice,
    is_action_id,
    run_action,
)
from lifeline_sim.concepts import CONCEPTS, build_concept, build_lesson, concept_ids
from lifeline_sim.decisions import best_option_ids, decision_prompt
from lifeline_sim.decisions import decision_outcome as _decision_outcome
from lifeline_sim.decisions import decision_outcomes as _decision_outcomes
from lifeline_sim.decisions import decision_prompts as _decision_prompts
from lifeline_sim.errors import SimError
from lifeline_sim.events.engine import templates_by_id
from lifeline_sim.habits import game_habit_score
from lifeline_sim.health import HealthInput, health_id
from lifeline_sim.index import IndexWeights, load_weights
from lifeline_sim.macroview import MacroView
from lifeline_sim.occupations import occupation
from lifeline_sim.paths import (
    PATH_IDS,
    QUICK_DEFAULT_START_YEAR,
    QUICK_END_AGE,
    QUICK_START_AGE,
    path_character,
    path_def,
    stage_starts,
)
from lifeline_sim.paths import paths as _paths
from lifeline_sim.presets import LEGACY_PRESET_IDS
from lifeline_sim.presets import god_mode_options as _god_mode_options
from lifeline_sim.presets import presets as _presets
from lifeline_sim.project import index_state, to_life
from lifeline_sim.projection import ChoiceProjection
from lifeline_sim.quick import QuickPlan, next_stop
from lifeline_sim.quick import plan as quick_plan
from lifeline_sim.quiz import QuizItem, QuizTopic, quiz_item
from lifeline_sim.quiz import quiz_questions as _quiz_questions
from lifeline_sim.replay import (
    TEMPLATE_COST_PREFIX,
    Decision,
    LifeSpec,
    apply_choice,
    apply_health,
    event_year,
    last_view,
    remember,
    replay,
    view_for,
)
from lifeline_sim.ribbons import ribbons_before, update_ribbons
from lifeline_sim.setup import Setup
from lifeline_sim.state import SimState, initial_state
from lifeline_sim.step import step_year

PRESENT_YEAR = p.PRESENT_YEAR
FREE_REWINDS = 1

__all__ = [
    "PRESENT_YEAR",
    "decision_outcome",
    "decision_outcomes",
    "decision_prompts",
    "habit_score",
    "is_quick",
    "new_path_life",
    "offered_presets",
    "paths",
    "quick_finished",
    "quick_life",
    "quick_life_plan",
    "quiz_questions",
    "best_option_ids",
    "decision_prompt",
    "quiz_item",
    "QuizItem",
    "life_path",
    "act",
    "age",
    "challenges",
    "choose",
    "compare_event_choices",
    "concepts",
    "data_gaps",
    "god_mode_options",
    "new_life",
    "play_scenario",
    "presets",
    "rewind",
    "scenario_cost",
    "summary",
]


def _setup(life: Life) -> Setup:
    first = life.history[0] if life.history else None
    if first is None or first.event_id is not None:
        return Setup()
    return Setup.decode(first.choice_id)


def _spec(life: Life) -> LifeSpec:
    return LifeSpec(
        character=life.character, mode=life.mode, start_year=life.start_year, seed=life.seed, setup=_setup(life)
    )


def _decisions(life: Life) -> list[Decision]:
    return [(h.event_id, h.choice_id) for h in life.history if h.event_id is not None and h.choice_id is not None]


def _comparable_twin(
    spec: LifeSpec, full_twin: SimState, answered: set[str], player_open: bool, mv: MacroView, w: IndexWeights
) -> SimState:
    """The twin to compare against while the player's year is open.

    While the player still has open events, the twin has answered (with defaults) only the events
    of this year whose ids the player has answered. So the Index does not move before the player
    answers. Once the player has no open events, the twin has answered all of its events.
    """
    if not player_open or full_twin.year <= spec.start_year:
        return full_twin
    twin = replay(spec, [], full_twin.year - 1, mv, w, autopilot=True)
    if not twin.alive:
        return twin
    step_year(twin, mv, w)
    for ev in list(twin.pending):
        if ev.id in answered:
            apply_choice(twin, ev, next(c.id for c in ev.choices if c.is_default), w)
    return twin


def _actions(s: SimState, mv: MacroView, history: list[YearLog]) -> list[AvailableAction]:
    done = {
        (h.choice_id or "").partition("?")[0]
        for h in history
        if h.year == s.year and h.event_id is not None and is_action_id(h.event_id)
    }
    return available_actions(s, mv, done)


def _ribbons(prev: list[Ribbon], s: SimState, history: list[YearLog], twin: SimState, concepts: int) -> list[Ribbon]:
    return update_ribbons(list(prev), s, history, index_state(s, twin, load_weights()).value, concepts)


def _log(
    s: SimState, text: str, twin: SimState, *, event_id: str | None = None, choice_id: str | None = None
) -> YearLog:
    w = load_weights()
    return YearLog(
        year=s.year,
        age=s.age,
        text=text,
        decision_id=event_id,
        event_id=event_id,
        choice_id=choice_id,
        net_worth=round(s.net_worth, 2),
        autopilot_net_worth=round(twin.net_worth, 2),
        index=index_state(s, twin, w).value,
    )


# ---------- lifecycle ----------


def new_life(
    life_id: str, character: CharacterSpec, mode: LifeMode, start_year: int, seed: int, macro: MacroTable
) -> Life:
    return _new_life(life_id, character, mode, start_year, seed, macro, Setup())


SIMULATED_LABEL = "Simulated from ONS and Nomis data."


def label_simulated(character: CharacterSpec) -> CharacterSpec:
    """ADR 0027: a character drawn from the synthetic population says so in its blurb.

    Apply it where the character is drawn (engine `random_character` or the API), so the life and
    `GET /v1/characters` show the same person. `new_life` does not change the character."""
    blurb = character.blurb or ""
    if SIMULATED_LABEL in blurb:
        return character
    room = 200 - len(SIMULATED_LABEL) - 1
    text = f"{blurb[:room].rstrip()} {SIMULATED_LABEL}".strip()
    return character.model_copy(update={"blurb": text})


def _new_life(
    life_id: str,
    character: CharacterSpec,
    mode: LifeMode,
    start_year: int,
    seed: int,
    macro: MacroTable,
    setup: Setup,
) -> Life:
    start_age = start_year - character.birth_year
    if start_age < p.MIN_START_AGE:
        raise SimError(
            "invalid_input", f"{character.name} is {start_age} in {start_year}. Start at {p.MIN_START_AGE} or older."
        )
    if start_age >= p.MAX_AGE:
        raise SimError("invalid_input", f"{character.name} would be {start_age} in {start_year}.")
    w = load_weights()
    mv = view_for(macro)
    s = initial_state(character, mode, start_year, seed, mv, w, setup)
    spec = LifeSpec(character=character, mode=mode, start_year=start_year, seed=seed, setup=setup)
    remember(mv, spec, False, [], s)
    remember(mv, spec, True, [], s)
    where = f"in {character.town}" if character.town else ""
    job = f"a {character.occupation}" if s.employed else "retired" if s.retired else character.occupation
    if setup.path is not None:
        title = s.job_title.lower()
        job = "a student" if s.student else f"{'an' if title[:1] in 'aeiou' else 'a'} {title}"
    first = _log(s, f"You start life at {s.age} as {job} {where}.".replace("  ", " ").replace(" .", "."), s)
    if not setup.empty:
        first = first.model_copy(update={"choice_id": setup.encode()})
    return to_life(
        s,
        life_id=life_id,
        history=[first],
        twin=s,
        actions=_actions(s, mv, [first]),
        pending=[],
        concepts_unlocked=[],
        ribbons=[],
        rewind=RewindState(free_left=FREE_REWINDS, has_pass=False),
        room_code=None,
        w=w,
    )


# ---------- student paths and Quick Life (ADR 0052, ADR 0059) ----------

QUICK_LAST_START_YEAR = PRESENT_YEAR - (QUICK_END_AGE - QUICK_START_AGE)


def new_path_life(
    life_id: str,
    path_id: str,
    start_year: int | None,
    seed: int,
    macro: MacroTable,
    *,
    quick: bool = False,
    mode: LifeMode = "random",
    name: str | None = None,
) -> Life:
    """A life on a student path. `quick=True` gives a Quick Life: ages 18 to 25 in 5 or 6 AGE taps with 2 or
    3 events, then `summary` with the habit score. Same path, start year and seed give the same life.

    - `start_year`: the year the path starts (the person is `start_age`). None: QUICK_DEFAULT_START_YEAR for
      Quick Life, else the year the person reaches `start_age` with the default Quick Life year of birth.
    - Quick Life needs a path with `quick=True` and a start year of QUICK_LAST_START_YEAR or earlier.
    - `name`: the player's display name for the character (optional).
    """
    d = path_def(path_id)
    if d is None:
        raise SimError("not_found", f"No student path {path_id}.")
    if quick and not d.quick:
        raise SimError("invalid_input", f"{d.title} is not offered in Quick Life.")
    if start_year is None:
        start_year = QUICK_DEFAULT_START_YEAR + (d.start_age - QUICK_START_AGE)
    if quick and start_year > QUICK_LAST_START_YEAR:
        raise SimError("invalid_input", f"Quick Life runs 7 years. Start in {QUICK_LAST_START_YEAR} or earlier.")
    if start_year > PRESENT_YEAR:
        raise SimError("invalid_input", f"Start in {PRESENT_YEAR} or earlier.")
    character = path_character(path_id, start_year, view_for(macro))
    if name:
        character = character.model_copy(update={"name": name[:40]})
    return _new_life(life_id, character, mode, start_year, seed, macro, Setup(path=path_id, quick=quick))


def life_path(life: Life) -> str | None:
    """The student path id of a life, or None."""
    return _setup(life).path


def is_quick(life: Life) -> bool:
    return _setup(life).quick


def quick_life_plan(life: Life) -> QuickPlan | None:
    """The Quick Life plan (tap stop years, event years, end year), or None for other lives."""
    return quick_plan(life.seed, life.start_year) if is_quick(life) else None


def quick_finished(life: Life) -> bool:
    """True when a Quick Life has reached its last tap (age 25). Show the summary then."""
    qp = quick_life_plan(life)
    return qp is not None and life.year >= qp.end_year and not life.pending_events


def habit_score(life: Life, macro: MacroTable | None = None) -> HabitScore | None:
    """Habit score of a student path life from its game ledger (lifeline_sim.habits). None for other lives,
    or when no MacroTable is known (no `macro` and no table used yet in this process)."""
    if _setup(life).path is None:
        return None
    mv = view_for(macro) if macro is not None else last_view()
    if mv is None:
        return None
    s = replay(_spec(life), _decisions(life), life.year, mv, load_weights())
    return game_habit_score(s)


def _year_text(s: SimState) -> str:
    parts = [f"Age {s.age}."]
    if s.last_net_income > 0:
        parts.append(f"You took home £{s.last_net_income:,.0f} and spent £{s.last_costs:,.0f}.")
    if s.employed and occupation(s.character.occupation).bonus_cap > 0:
        if s.last_bonus > 0:
            parts.append(f"Your bonus was £{s.last_bonus:,.0f} before tax.")
        else:
            parts.append("No bonus this year.")
    if s.last_graduated:
        parts.append(f"You graduated and started work on £{s.income:,.0f} a year.")
    if s.last_forced_sale:
        parts.append("Your debts grew too big, so your home was sold to pay them.")
    if s.last_bankrupt:
        parts.append("Your debts grew too big. They were written off, and your savings were taken.")
    if s.last_missed:
        word = "payment" if s.last_missed == 1 else "payments"
        parts.append(f"You missed {s.last_missed} {word}.")
    if not s.alive:
        parts.append(f"You died at {s.age}. Cause: {s.cause_of_death}.")
    return " ".join(parts)


class _QuickFlows:
    """Money flows over the years of one Quick Life tap, for the history text."""

    def __init__(self) -> None:
        self.net = 0.0
        self.costs = 0.0
        self.missed = 0
        self.repaid = 0.0
        self.graduated = False
        self.started_study = False

    def add(self, s: SimState) -> None:
        self.net += s.last_net_income
        self.costs += s.last_costs
        self.missed += s.last_missed
        self.repaid += s.last_loan_repaid
        self.graduated = self.graduated or s.last_graduated
        stage = stage_starts(s.path_id, s.age) if s.path_id is not None else None
        self.started_study = self.started_study or (stage is not None and stage.kind in ("study", "study_pg"))


def _quick_text(s: SimState, f: _QuickFlows, from_age: int) -> str:
    span = f"Age {s.age}." if s.age - from_age == 1 else f"Ages {from_age + 1} to {s.age}."
    parts = [span]
    if f.net > 0:
        parts.append(f"You took home £{f.net:,.0f} and spent £{f.costs:,.0f}.")
    if f.started_study:
        parts.append("You started university.")
    if f.graduated:
        parts.append(f"You graduated and started work on £{s.income:,.0f} a year.")
    if f.repaid > 0:
        parts.append(f"You repaid £{f.repaid:,.0f} of student loan.")
    if f.missed:
        word = "payment" if f.missed == 1 else "payments"
        parts.append(f"You missed {f.missed} {word}.")
    if s.quick_end_year is not None and s.year >= s.quick_end_year:
        parts.append("Quick Life complete.")
    return " ".join(parts)


def age(life: Life, macro: MacroTable, health: HealthInput | None = None) -> AgeResult:
    """One year passes. `health` (optional, ADR 0029): the phone's average steps and sleep give a
    Health change of -10 to +10 this year (rule in `lifeline_sim.health`). It is stored in this
    year's history entry, so replay gives the same life."""
    if not life.alive:
        raise SimError("dead", "This life has ended.")
    if life.pending_events:
        raise SimError("pending_events", "Answer the open events before you age.")
    w = load_weights()
    mv = view_for(macro)
    spec = _spec(life)
    decisions = _decisions(life)
    s = replay(spec, decisions, life.year, mv, w)
    flows = _QuickFlows()
    if s.quick:
        stop = next_stop(quick_plan(spec.seed, spec.start_year), s.year)
        if stop is None:
            raise SimError("finished", "This Quick Life is over. See the summary.")
        while s.alive and s.year < stop:
            step_year(s, mv, w)
            flows.add(s)
    else:
        step_year(s, mv, w)
    health_text = ""
    health_choice: str | None = None
    if health is not None and not health.empty and s.alive:
        change = apply_health(s, health)
        health_choice = health.encode()
        decisions.append((health_id(s.year), health_choice))
        health_text = f" Your steps and sleep changed your health by {change:+d}."
        s.track_drawdown(w)
    remember(mv, spec, False, decisions, s)
    full_twin = replay(spec, [], s.year, mv, w, autopilot=True)
    remember(mv, spec, True, [], full_twin)
    twin = _comparable_twin(spec, full_twin, set(), bool(s.pending), mv, w)
    text = _quick_text(s, flows, life.age) if s.quick else _year_text(s)
    entry = _log(s, text + health_text, twin)
    if health_choice is not None:
        entry = entry.model_copy(update={"event_id": health_id(s.year), "choice_id": health_choice})
    history = [*life.history, entry]
    new = to_life(
        s,
        life_id=life.id,
        history=history,
        twin=twin,
        actions=_actions(s, mv, history),
        pending=list(s.pending),
        concepts_unlocked=list(life.concepts_unlocked),
        ribbons=_ribbons(life.ribbons, s, history, twin, len(life.concepts_unlocked)),
        rewind=life.rewind,
        room_code=life.room_code,
        w=w,
    )
    return AgeResult(life=new, events=list(new.pending_events), lesson=None)


def choose(life: Life, event_id: str, choice_id: str, macro: MacroTable) -> ChoiceResult:
    if not life.alive:
        raise SimError("dead", "This life has ended.")
    event = next((e for e in life.pending_events if e.id == event_id), None)
    if event is None:
        raise SimError("not_found", f"No open event {event_id}.")
    if not any(c.id == choice_id for c in event.choices):
        raise SimError("invalid_choice", f"Event {event_id} has no choice {choice_id}.")
    w = load_weights()
    mv = view_for(macro)
    spec = _spec(life)
    decisions = _decisions(life)
    s = replay(spec, decisions, life.year, mv, w)
    res, deltas = apply_choice(s, event, choice_id, w)
    decisions.append((event_id, choice_id))
    remember(mv, spec, False, decisions, s)

    answered = {d[0] for d in decisions if event_year(d[0]) == life.year} | {event_id}
    still_open = any(e.id != event_id for e in life.pending_events)
    full_twin = replay(spec, [], life.year, mv, w, autopilot=True)
    twin = _comparable_twin(spec, full_twin, answered, still_open, mv, w)
    facts = dict(event.facts)
    facts.update({f"effect_{k}": v for k, v in res.effects.items() if isinstance(v, float | int)})
    outcome = Outcome(event_id=event_id, choice_id=choice_id, text=res.text, deltas=deltas, facts=facts, good=res.good)
    unlocked = list(life.concepts_unlocked)
    new_concept: str | None = None
    lesson = None
    if event.concept_id and event.concept_id not in unlocked and event.concept_id in concept_ids():
        unlocked.append(event.concept_id)
        new_concept = event.concept_id
        lesson = build_lesson(event.concept_id, mv, s.year, s.region)
    history = [*life.history, _log(s, res.text, twin, event_id=event_id, choice_id=choice_id)]
    pending = [e for e in life.pending_events if e.id != event_id]
    new = to_life(
        s,
        life_id=life.id,
        history=history,
        twin=twin,
        actions=_actions(s, mv, history),
        pending=pending,
        concepts_unlocked=unlocked,
        ribbons=_ribbons(life.ribbons, s, history, twin, len(unlocked)),
        rewind=life.rewind,
        room_code=life.room_code,
        w=w,
    )
    return ChoiceResult(life=new, outcome=outcome, lesson=lesson, concept_unlocked=new_concept)


def act(life: Life, tab: str, action_id: str, params: dict[str, float | str], macro: MacroTable) -> ActionResult:
    """Run one tab action. Recorded as a decision `act-<year>-<n>` with choice id `<tab>/<action>?k=v`."""
    if not life.alive:
        raise SimError("dead", "This life has ended.")
    spec_a = action_spec(tab, action_id)
    if spec_a is None:
        raise SimError("invalid_action", f"No action {tab}/{action_id}.")
    try:
        clean = clean_params(spec_a, params)
    except ValueError as exc:
        raise SimError("invalid_action", f"{tab}/{action_id}: {exc}.") from exc
    current = next((a for a in life.available_actions if a.tab == tab and a.id == action_id), None)
    if current is not None and not current.enabled:
        raise SimError("invalid_action", f"{spec_a.label} is not possible right now.")
    w = load_weights()
    mv = view_for(macro)
    spec = _spec(life)
    decisions = _decisions(life)
    s = replay(spec, decisions, life.year, mv, w)
    n = 1 + sum(1 for d, _ in decisions if is_action_id(d) and event_year(d) == life.year)
    decision_id = action_decision_id(life.year, n)
    choice_id = encode_choice(tab, action_id, clean)
    if action_id in {a.id for a in _actions(s, mv, life.history) if a.tab == tab and not a.enabled}:
        raise SimError("invalid_action", f"{spec_a.label} is not possible right now.")
    run = run_action(s, mv, decision_id, choice_id)
    if run is None:
        raise SimError("invalid_action", f"{spec_a.label} is not possible right now.")
    s.track_drawdown(w)
    decisions.append((decision_id, choice_id))
    remember(mv, spec, False, decisions, s)

    answered = {d[0] for d in decisions if event_year(d[0]) == life.year and not is_action_id(d[0])}
    full_twin = replay(spec, [], life.year, mv, w, autopilot=True)
    twin = _comparable_twin(spec, full_twin, answered, bool(life.pending_events), mv, w)
    outcome = Outcome(
        event_id=decision_id, choice_id=choice_id, text=run.text, deltas=run.deltas, facts=run.facts, good=run.good
    )
    unlocked = list(life.concepts_unlocked)
    new_concept: str | None = None
    lesson = None
    cid = spec_a.concept_id
    if cid and cid not in unlocked and cid in concept_ids():
        unlocked.append(cid)
        new_concept = cid
        lesson = build_lesson(cid, mv, s.year, s.region)
    history = [*life.history, _log(s, run.text, twin, event_id=decision_id, choice_id=choice_id)]
    new = to_life(
        s,
        life_id=life.id,
        history=history,
        twin=twin,
        actions=_actions(s, mv, history),
        pending=list(life.pending_events),
        concepts_unlocked=unlocked,
        ribbons=_ribbons(life.ribbons, s, history, twin, len(unlocked)),
        rewind=life.rewind,
        room_code=life.room_code,
        w=w,
    )
    return ActionResult(life=new, outcome=outcome, lesson=lesson, concept_unlocked=new_concept)


def rewind(life: Life, decision_id: str, macro: MacroTable) -> RewindResult:
    """Go back to a past decision and take another path (ADR 0012).

    - Event choice: replay up to that year with the decisions before it, then take the default
      choice (or, if the default was taken, the first other choice). Later decisions are dropped.
    - Tab action: replay without it. Later decisions are dropped.
    - Free once per life (`rewind.free_left`), unlimited with `rewind.has_pass`. Otherwise
      `payment_required`.
    """
    idx = next((i for i, h in enumerate(life.history) if h.decision_id == decision_id), None)
    if idx is None:
        raise SimError("not_found", f"No decision {decision_id}.")
    if not life.rewind.has_pass and life.rewind.free_left <= 0:
        raise SimError("payment_required", "You have used your free rewind. A Rewind Pass gives unlimited rewinds.")
    target = life.history[idx]
    year = target.year
    w = load_weights()
    mv = view_for(macro)
    spec = _spec(life)
    before = [
        (h.event_id, h.choice_id) for h in life.history[:idx] if h.event_id is not None and h.choice_id is not None
    ]
    s = replay(spec, before, year, mv, w)
    history = list(life.history[:idx])
    decisions = list(before)
    if not is_action_id(decision_id):
        event = next((e for e in s.pending if e.id == decision_id), None)
        if event is None:
            raise SimError("not_found", f"Decision {decision_id} cannot be replayed.")
        default = next(c.id for c in event.choices if c.is_default)
        alt = default if target.choice_id != default else next(c.id for c in event.choices if c.id != default)
        res, _ = apply_choice(s, event, alt, w)
        decisions.append((decision_id, alt))
        remember(mv, spec, False, decisions, s)
        answered = {d[0] for d in decisions if event_year(d[0]) == year and not is_action_id(d[0])}
        full_twin = replay(spec, [], year, mv, w, autopilot=True)
        twin = _comparable_twin(spec, full_twin, answered, bool(s.pending), mv, w)
        history.append(_log(s, res.text, twin, event_id=decision_id, choice_id=alt))
    else:
        remember(mv, spec, False, decisions, s)
        answered = {d[0] for d in decisions if event_year(d[0]) == year and not is_action_id(d[0])}
        full_twin = replay(spec, [], year, mv, w, autopilot=True)
        twin = _comparable_twin(spec, full_twin, answered, bool(s.pending), mv, w)
    rewind_state = (
        life.rewind if life.rewind.has_pass else life.rewind.model_copy(update={"free_left": life.rewind.free_left - 1})
    )
    unlocked = list(life.concepts_unlocked)
    new = to_life(
        s,
        life_id=life.id,
        history=history,
        twin=twin,
        actions=_actions(s, mv, history),
        pending=list(s.pending),
        concepts_unlocked=unlocked,
        ribbons=_ribbons(ribbons_before(life.ribbons, year), s, history, twin, len(unlocked)),
        rewind=rewind_state,
        room_code=life.room_code,
        w=w,
    )
    return RewindResult(life=new, abandoned_index=life.index.value, abandoned_net_worth=life.finances.net_worth)


# ---------- "Test it" scenarios (ADR 0018) ----------

POLICY_DEAL_END = "__deal_end_year"
POLICY_FOCUS = "__focus"


def scenario_setup(
    character: CharacterSpec, start_year: int, policy: dict[str, str], end_year: int | None = None
) -> Setup:
    """The replayable setup for a scenario.

    - Deal end: `policy["__deal_end_year"]` when given, else the first year with events
      (`start_year + 1`). Only used when the character has a mortgage. A year before
      `start_year + 1` moves to `start_year + 1`, because the start year has no events.
    - Focus: every policy key that is a template tag, plus the comma-separated tags in
      `policy["__focus"]`. Focused templates fire whenever the data gives them any chance.
    """
    deal_end: int | None = None
    if character.mortgage_balance > 0 and character.housing in ("mortgage", "own"):
        raw = policy.get(POLICY_DEAL_END, "").strip()
        if raw and not raw.lstrip("-").isdigit():
            raise SimError("invalid_input", f"{POLICY_DEAL_END} must be a year, got {raw!r}.")
        deal_end = max(start_year + 1, int(raw)) if raw else start_year + 1
    tags = known_tags()
    focus = {k for k in policy if k in tags}
    focus |= {t.strip() for t in policy.get(POLICY_FOCUS, "").split(",") if t.strip() in tags}
    return Setup(deal_end_year=deal_end, focus=tuple(sorted(focus)), focus_until=end_year if focus else None)


def known_tags() -> set[str]:
    return {tag for lt in templates_by_id().values() for tag in lt.t.tags}


def policy_choice(template_id: str, policy: dict[str, str]) -> str | None:
    """The choice id the policy picks for an event of this template, or None for the default.

    Lookup order: the template id, then the template's tags in declared order. Values may be a
    choice id or one of its aliases. A value the template does not offer gives the default.
    """
    lt = templates_by_id().get(template_id)
    if lt is None:
        return None
    for key in (template_id, *lt.t.tags):
        if key in policy:
            c = lt.t.choice_for(policy[key])
            if c is not None:
                return c.id
    return None


def play_scenario(
    life_id: str,
    character: CharacterSpec,
    start_year: int,
    end_year: int,
    policy: dict[str, str],
    seed: int,
    macro: MacroTable,
) -> Life:
    """Play a life from `start_year` to `end_year` with a fixed policy (ADR 0018, "Test it").

    The returned `Life` is an ordinary life: the API can store it, AGE it and choose in it.
    Its setup (deal end year, focus tags) is stored in the first history entry, so replay and
    rewind rebuild the same state. Events of `start_year + 1 .. end_year` take the policy choice,
    else the default. Same inputs give the same life.
    """
    if end_year < start_year:
        raise SimError("invalid_input", f"end_year {end_year} is before start_year {start_year}.")
    setup = scenario_setup(character, start_year, policy, end_year)
    life = _new_life(life_id, character, "self", start_year, seed, macro, setup)
    while life.alive and life.year < end_year:
        life = age(life, macro).life
        for ev in list(life.pending_events):
            cid = policy_choice(ev.template_id, policy) or next(c.id for c in ev.choices if c.is_default)
            life = choose(life, ev.id, cid, macro).life
    return life


MORTGAGE_TAGS = ("mortgage_deal_end", "mortgage_rate_change")


def scenario_cost(life: Life, macro: MacroTable | None = None) -> float:
    """GBP the scenario's policy-controlled costs came to, from `start_year` to `life.year`.

    The tags are the life's focus tags (the tag keys of the `play_scenario` policy). The result
    is the sum over those tags (mortgage tags count once), rounded to pence. Per tag:

    - `mortgage_deal_end`, `mortgage_rate_change`: all mortgage payments (interest and capital).
    - `savings_rate_change`: minus the interest earned on savings, plus interest a choice gave up
      (for example staying with a poor rate). Lower is better; it is usually negative.
    - `energy_bill`: the typical yearly energy bill (`ENERGY_TARIFF` for the region and year) for
      each year played, plus the extra bills, fix premiums and fees of energy choices.
    - `card_debt`: interest charged on card debt, plus fees and extra interest from card choices.
    - `subscription`, `budget_overspend`, `emergency_fund` and other tags: the one-off costs of
      the tagged choices, plus 12 x any monthly spending change they made, for every later year.

    A life with no focus tags returns the mortgage payments when it has a mortgage, else 0.
    `macro` should be the life's pinned MacroTable. When it is omitted, the table used by the
    most recent sim call in this process is used; with none, `invalid_input`.
    """
    if macro is not None:
        mv = view_for(macro)
    else:
        mv_last = last_view()
        if mv_last is None:
            raise SimError("invalid_input", "scenario_cost needs the life's MacroTable.")
        mv = mv_last
    spec = _spec(life)
    s = replay(spec, _decisions(life), life.year, mv, load_weights())
    tags = list(spec.setup.focus)
    if not tags:
        return round(s.mortgage_paid, 2)
    total = base_flows(s, tags) + sum(s.tag_cost.get(tag, 0.0) for tag in tags)
    return round(total, 2)


def base_flows(s: SimState, tags: Sequence[str]) -> float:
    """Running cost flows the tags control (see `scenario_cost`), without one-off choice costs."""
    total = 0.0
    if any(t in MORTGAGE_TAGS for t in tags):
        total += s.mortgage_paid
    for tag in tags:
        if tag == "savings_rate_change":
            total -= s.savings_interest
        elif tag == "energy_bill":
            total += s.energy_paid
        elif tag == "card_debt":
            total += s.card_interest_paid
    return total


def data_gaps(life: Life, macro: MacroTable) -> dict[int, list[str]]:
    """Debug view (ADR 0027): for each year, the macro names a yearly step skipped because the
    live table has no value for that year and place (for example `stock_return`). Empty in demo mode."""
    s = replay(_spec(life), _decisions(life), life.year, view_for(macro), load_weights())
    return {y: sorted(set(names)) for y, names in sorted(s.data_gaps.items())}


# ---------- "Not sure? Ask Penny" (ADR 0031) ----------

MAX_PROJECTION_YEARS = 10
_PROJECTION_KEYS = (
    MacroKey.BANK_RATE,
    MacroKey.CPI_INFLATION,
    MacroKey.MEDIAN_PAY,
    MacroKey.HOUSE_PRICE_CHANGE,
    MacroKey.STOCK_RETURN,
    MacroKey.GILT_10Y,
    MacroKey.MORTGAGE_SVR,
    MacroKey.MORTGAGE_TRACKER,
)


def compare_event_choices(life: Life, event_id: str, macro: MacroTable, years: int = 3) -> list[ChoiceProjection]:
    """Project each choice of an open event `years` years ahead (1-10). Pure: stores nothing.

    Per choice: take it, take the default at the other open events of the year that are still
    open, then AGE `years` times with the default at every event and no tab actions. Same seed,
    so the years ahead differ only through the choice. The Index compares with the autopilot twin.
    """
    if not life.alive:
        raise SimError("dead", "This life has ended.")
    event = next((e for e in life.pending_events if e.id == event_id), None)
    if event is None:
        raise SimError("not_found", f"No open event {event_id}.")
    if not 1 <= years <= MAX_PROJECTION_YEARS:
        raise SimError("invalid_input", f"years must be between 1 and {MAX_PROJECTION_YEARS}.")
    w = load_weights()
    mv = view_for(macro)
    spec = _spec(life)
    base = replay(spec, _decisions(life), life.year, mv, w)
    lt = templates_by_id().get(event.template_id)
    tags = lt.t.tags if lt is not None else ()
    tpl_key = f"{TEMPLATE_COST_PREFIX}{event.template_id}"
    end_year = life.year + years
    twin = replay(spec, [], end_year, mv, w, autopilot=True)
    sources = _projection_sources(event.sources, mv, life.year, end_year, base.region)
    out: list[ChoiceProjection] = []
    for choice in event.choices:
        s = base.clone()
        cost0 = base_flows(s, tags) + s.tag_cost.get(tpl_key, 0.0)
        missed0 = s.missed
        apply_choice(s, next(e for e in s.pending if e.id == event_id), choice.id, w)
        for ev in list(s.pending):
            apply_choice(s, ev, next(c.id for c in ev.choices if c.is_default), w)
        path_years = [s.year]
        path = [round(s.net_worth, 2)]
        while s.alive and s.year < end_year:
            step_year(s, mv, w)
            for ev in list(s.pending):
                apply_choice(s, ev, next(c.id for c in ev.choices if c.is_default), w)
            path_years.append(s.year)
            path.append(round(s.net_worth, 2))
        cost = round(base_flows(s, tags) + s.tag_cost.get(tpl_key, 0.0) - cost0, 2)
        missed = s.missed - missed0
        twin_now = twin if twin.year == s.year else replay(spec, [], s.year, mv, w, autopilot=True)
        index = index_state(s, twin_now, w).value
        fid = f"{event_id}.{choice.id}"
        facts = [
            ChatFact(id=f"{fid}.end_net_worth", value=path[-1], unit="gbp", label=f"Net worth in {s.year}"),
            ChatFact(
                id=f"{fid}.net_worth_change",
                value=round(path[-1] - path[0], 2),
                unit="gbp",
                label=f"Change in net worth {path_years[0]} to {s.year}",
            ),
            ChatFact(id=f"{fid}.cost", value=cost, unit="gbp", label=f"Cost of this choice to {s.year}"),
            ChatFact(id=f"{fid}.missed_payments", value=float(missed), unit="count", label="Missed payments"),
            ChatFact(id=f"{fid}.index", value=index, unit="count", label=f"Index in {s.year}"),
            ChatFact(id=f"{fid}.years", value=float(s.year - life.year), unit="years", label="Years projected"),
        ]
        out.append(
            ChoiceProjection(
                event_id=event_id,
                choice_id=choice.id,
                label=choice.label,
                is_default=choice.is_default,
                start_year=life.year,
                end_year=s.year,
                years=path_years,
                net_worth_path=path,
                end_net_worth=path[-1],
                cost=cost,
                missed_payments=missed,
                index=index,
                alive=s.alive,
                facts=facts,
                sources=sources,
            )
        )
    return out


def _projection_sources(
    event_sources: list[SourceRef], mv: MacroView, start: int, end: int, region: str
) -> list[SourceRef]:
    """The event's own sources, then the series the yearly steps read, each once."""
    out: list[SourceRef] = []
    seen: set[tuple[str, str]] = set()
    refs = list(event_sources)
    for key in _PROJECTION_KEYS:
        for y in range(start + 1, end + 1):
            ref = mv.source_ref(key, y, region)
            if ref is not None:
                refs.append(ref)
                break
    for ref in refs:
        k = (ref.source, ref.series_id)
        if k not in seen:
            seen.add(k)
            out.append(ref)
    return out


# ---------- read-only views ----------


_WARN_MARKERS = ("You missed", "Your debts grew too big")


YEAR_FALL_SHARE = 0.05  # a year's fall in net worth of 5% of max(|net worth|, starting pay) is a key moment


def _key_moments(life: Life, limit: int = 5) -> list[KeyMoment]:
    """Year warnings first (missed payments, debt relief), then the biggest money moves.

    Moves are choices and tab actions that changed net worth, plus years where net worth fell
    sharply (for example a house price crash with no decision). Tone: a fall is 📉, a rise
    is 📈, a warning is ⚠️. Entries with no money effect are skipped.
    """
    warnings: list[KeyMoment] = []
    moves: list[tuple[float, KeyMoment]] = []
    prev_nw = life.history[0].net_worth if life.history else life.finances.net_worth
    pay = max(life.character.annual_income, 1.0)
    for h in life.history[1:]:
        change = h.net_worth - prev_nw
        base = max(abs(prev_nw), pay)
        prev_nw = h.net_worth
        if h.decision_id is None:
            if any(mk in h.text for mk in _WARN_MARKERS):
                warnings.append(KeyMoment(year=h.year, age=h.age, emoji="⚠️", text=h.text))
            elif "graduated" in h.text:
                warnings.append(KeyMoment(year=h.year, age=h.age, emoji="🎓", text=h.text))
            elif change <= -YEAR_FALL_SHARE * base:
                text = f"Your net worth fell £{-change:,.0f} in {h.year}."
                moves.append((abs(change), KeyMoment(year=h.year, age=h.age, emoji="📉", text=text)))
            continue
        if abs(change) >= 1:
            emoji = "📈" if change > 0 else "📉"
            moves.append((abs(change), KeyMoment(year=h.year, age=h.age, emoji=emoji, text=h.text)))
    chosen = warnings[:2]
    chosen += [m for _, m in sorted(moves, key=lambda x: -x[0])[: max(0, limit - len(chosen))]]
    return sorted(chosen, key=lambda m: (m.year, m.age))


def summary(life: Life, macro: MacroTable | None = None) -> LifeSummary:
    """The end-of-life card. Quick Life (and every student path life) gets `habit_score` from its game
    ledger. Pass the life's pinned `macro` for that; without it the last table used in this process is used,
    and with none the habit score is left out."""
    key_moments = _key_moments(life)
    habit = habit_score(life, macro) if _setup(life).path is not None else None
    autopilot_nw = life.history[-1].autopilot_net_worth if life.history else life.finances.net_worth
    return LifeSummary(
        life_id=life.id,
        name=life.character.name,
        born=life.character.birth_year,
        died=None if life.alive else life.year,
        age=life.age,
        cause_of_death=life.cause_of_death,
        final_index=life.index.value,
        net_worth=life.finances.net_worth,
        autopilot_net_worth=autopilot_nw,
        ribbons=list(life.ribbons),
        key_moments=key_moments,
        concepts_unlocked=len(life.concepts_unlocked),
        habit_score=habit,
        timeline=list(life.history),
    )


def presets() -> list[CharacterSpec]:
    """Every preset that a stored life may use, offered or not (old lives and old rooms load by id).
    For the list shown to players, use `offered_presets`."""
    return _presets()


def offered_presets(macro: MacroTable | None = None, start_year: int = QUICK_DEFAULT_START_YEAR) -> list[CharacterSpec]:
    """Characters offered in Play solo (ADR 0052): one per student path, then the legacy `student` and
    `teacher-glasgow` presets. Banker, plumber, pensioner and nurse are no longer offered. With `macro`,
    each path character's starting pay is the path's stage pay for `start_year`."""
    mv = view_for(macro) if macro is not None else None
    out = [path_character(pid, start_year, mv) for pid in PATH_IDS]
    out += [c for c in _presets() if c.id not in LEGACY_PRESET_IDS]
    return out


def paths() -> list[StudentPath]:
    """Student start paths for `GET /v1/paths`."""
    return _paths()


def god_mode_options() -> dict[str, list[str]]:
    return _god_mode_options()


def concepts(macro: MacroTable | None = None) -> list[Concept]:
    """All concepts. Pass `macro` to fill each lesson chart with real data (UK, last 10 years)."""
    mv = view_for(macro) if macro is not None else None
    return [build_concept(c.id, mv) for c in CONCEPTS]


def challenges() -> list[Challenge]:
    return [
        Challenge(
            id="home-by-30",
            title="Own a home by 30",
            emoji="🏡",
            description="Buy any home before you turn 30.",
            character_id="nurse-leeds",
            start_year=2006,
            goal={"type": "own_home_by_age", "age": 30.0},
        ),
        Challenge(
            id="survive-2008",
            title="Survive 2008 with no missed payment",
            emoji="🛡️",
            description="Get through the 2008 crash without missing a single payment.",
            character_id="banker-london",
            start_year=2006,
            goal={"type": "no_missed_payments_until", "year": 2010.0},
        ),
        Challenge(
            id="beat-autopilot",
            title="Beat your twin",
            emoji="🏁",
            description="Reach an Index of 110 or more by 2026.",
            character_id="nurse-leeds",
            start_year=2006,
            goal={"type": "index_at_least_by_year", "index": 110.0, "year": 2026.0},
        ),
        Challenge(
            id="rate-shock-2022",
            title="Ride out the 2022 rate shock",
            emoji="📈",
            description="Your fix ends as rates jump. Reach 2024 with no missed payment.",
            character_id="teacher-glasgow",
            start_year=2021,
            goal={"type": "no_missed_payments_until", "year": 2024.0},
        ),
        Challenge(
            id="debt-free-by-35",
            title="Debt free by 35",
            emoji="🧹",
            description="Clear your card debt and student loan before you turn 35.",
            character_id="student",
            start_year=2025,
            goal={"type": "debt_free_by_age", "age": 35.0},
        ),
        Challenge(
            id="millionaire",
            title="Make a million",
            emoji="💎",
            description="Reach a net worth of £1,000,000 at any age.",
            character_id="banker-london",
            start_year=2006,
            goal={"type": "net_worth_at_least", "amount": 1_000_000.0},
        ),
        Challenge(
            id="pension-pot",
            title="Build a £100,000 pension",
            emoji="👵",
            description="Grow your pension to £100,000 before you turn 50.",
            character_id="plumber",
            start_year=2015,
            goal={"type": "pension_at_least_by_age", "amount": 100_000.0, "age": 50.0},
        ),
    ]


# ---------- Play with friends (ADR 0059) ----------


def quick_life(
    life_id: str,
    *,
    path_id: str,
    seed: int,
    macro: MacroTable,
    start_year: int | None = None,
    mode: LifeMode = "random",
    name: str | None = None,
) -> Life:
    """A new Quick Life: `new_path_life(..., quick=True)`. Tap AGE until `quick_finished`, answering the open
    event when a tap stops on one, then call `summary(life, macro)` for the card with the habit score."""
    return new_path_life(life_id, path_id, start_year, seed, macro, quick=True, mode=mode, name=name)


def quiz_questions(seed: int, *, topic: QuizTopic = "mixed", n: int = 8) -> list[QuizItem]:
    """Money Quiz questions with answers (lifeline_sim.quiz). Send `item.question` to players; keep
    `correct_choice_id`, `explanation` and the source for the reveal. Unknown topic raises ValueError."""
    return _quiz_questions(seed, topic, n)


def _table(macro: MacroTable | None) -> MacroTable:
    """The MacroTable to use. Pass the room's table. Without one, the table of the most recent sim call in
    this process is used; with none, `invalid_input`."""
    if macro is not None:
        return macro
    mv = last_view()
    if mv is None:
        raise SimError("invalid_input", "Same Decision needs the MacroTable.")
    return mv.table


def decision_prompts(
    seed: int, *, n: int = 1, macro: MacroTable | None, year: int | None = None
) -> list[DecisionPrompt]:
    """`n` Same Decision prompts (lifeline_sim.decisions). Without `year`: a seeded order. With `year`
    (GameOptions.start_year): prompts nearest that year first, ties in seeded order."""
    return _decision_prompts(seed, n, _table(macro), year)


def decision_outcomes(prompt_id: str, *, macro: MacroTable | None) -> list[DecisionOutcome]:
    """Every option's outcome in game money, in option order. `not_found` for an unknown prompt."""
    try:
        return _decision_outcomes(prompt_id, _table(macro))
    except KeyError as exc:
        raise SimError("not_found", f"No decision prompt {prompt_id}.") from exc


def decision_outcome(prompt_id: str, *, option_id: str, macro: MacroTable | None) -> DecisionOutcome:
    """One option's outcome in game money. `not_found` for an unknown prompt or option."""
    try:
        return _decision_outcome(prompt_id, option_id, _table(macro))
    except KeyError as exc:
        raise SimError("not_found", f"No option {option_id} in decision prompt {prompt_id}.") from exc
