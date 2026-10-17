"""Public sim API. Implements `lifeline_contracts.interfaces.SimAPI` as module functions.

All functions are pure: same inputs give the same outputs. They return new `Life` objects
and never mutate their inputs. Rule violations raise `SimError`.
"""

from __future__ import annotations

from lifeline_contracts.domain import (
    ActionResult,
    AgeResult,
    AvailableAction,
    Challenge,
    CharacterSpec,
    ChoiceResult,
    Concept,
    KeyMoment,
    Life,
    LifeMode,
    LifeSummary,
    Outcome,
    RewindResult,
    RewindState,
    YearLog,
)
from lifeline_contracts.macro import MacroTable
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
from lifeline_sim.errors import SimError
from lifeline_sim.events.engine import templates_by_id
from lifeline_sim.index import IndexWeights, load_weights
from lifeline_sim.macroview import MacroView
from lifeline_sim.occupations import occupation
from lifeline_sim.presets import god_mode_options as _god_mode_options
from lifeline_sim.presets import presets as _presets
from lifeline_sim.project import index_state, to_life
from lifeline_sim.replay import Decision, LifeSpec, apply_choice, event_year, remember, replay, view_for
from lifeline_sim.setup import Setup
from lifeline_sim.state import SimState, initial_state
from lifeline_sim.step import step_year

PRESENT_YEAR = p.PRESENT_YEAR
FREE_REWINDS = 1

__all__ = [
    "PRESENT_YEAR",
    "act",
    "age",
    "challenges",
    "choose",
    "concepts",
    "god_mode_options",
    "new_life",
    "play_scenario",
    "presets",
    "rewind",
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


def age(life: Life, macro: MacroTable) -> AgeResult:
    if not life.alive:
        raise SimError("dead", "This life has ended.")
    if life.pending_events:
        raise SimError("pending_events", "Answer the open events before you age.")
    w = load_weights()
    mv = view_for(macro)
    spec = _spec(life)
    decisions = _decisions(life)
    s = replay(spec, decisions, life.year, mv, w)
    step_year(s, mv, w)
    remember(mv, spec, False, decisions, s)
    full_twin = replay(spec, [], s.year, mv, w, autopilot=True)
    remember(mv, spec, True, [], full_twin)
    twin = _comparable_twin(spec, full_twin, set(), bool(s.pending), mv, w)
    history = [*life.history, _log(s, _year_text(s), twin)]
    new = to_life(
        s,
        life_id=life.id,
        history=history,
        twin=twin,
        actions=_actions(s, mv, history),
        pending=list(s.pending),
        concepts_unlocked=list(life.concepts_unlocked),
        ribbons=list(life.ribbons),
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
        ribbons=list(life.ribbons),
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
        ribbons=list(life.ribbons),
        rewind=life.rewind,
        room_code=life.room_code,
        w=w,
    )
    return ActionResult(life=new, outcome=outcome, lesson=lesson, concept_unlocked=new_concept)


def rewind(life: Life, decision_id: str, macro: MacroTable) -> RewindResult:
    """Tier 1. Plan: replay with the target choice flipped and later choices dropped."""
    if not any(h.decision_id == decision_id for h in life.history):
        raise SimError("not_found", f"No decision {decision_id}.")
    raise SimError("invalid_action", "Rewind is not available yet.")


# ---------- "Test it" scenarios (ADR 0018) ----------

POLICY_DEAL_END = "__deal_end_year"
POLICY_FOCUS = "__focus"


def scenario_setup(character: CharacterSpec, start_year: int, policy: dict[str, str]) -> Setup:
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
    return Setup(deal_end_year=deal_end, focus=tuple(sorted(focus)))


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
    setup = scenario_setup(character, start_year, policy)
    life = _new_life(life_id, character, "self", start_year, seed, macro, setup)
    while life.alive and life.year < end_year:
        life = age(life, macro).life
        for ev in list(life.pending_events):
            cid = policy_choice(ev.template_id, policy) or next(c.id for c in ev.choices if c.is_default)
            life = choose(life, ev.id, cid, macro).life
    return life


# ---------- read-only views ----------


_WARN_MARKERS = ("You missed", "Your debts grew too big")


def _key_moments(life: Life, limit: int = 5) -> list[KeyMoment]:
    """Year warnings first (missed payments, debt relief), then the choices that moved net worth most.

    Tone: a fall in net worth is 📉, a rise is 📈, a warning is ⚠️. Choices with no money effect are skipped.
    """
    warnings: list[KeyMoment] = []
    moves: list[tuple[float, KeyMoment]] = []
    prev_nw = life.history[0].net_worth if life.history else life.finances.net_worth
    for h in life.history:
        change = h.net_worth - prev_nw
        prev_nw = h.net_worth
        if h.decision_id is None:
            if any(mk in h.text for mk in _WARN_MARKERS):
                warnings.append(KeyMoment(year=h.year, age=h.age, emoji="⚠️", text=h.text))
            elif "graduated" in h.text:
                warnings.append(KeyMoment(year=h.year, age=h.age, emoji="🎓", text=h.text))
            continue
        if abs(change) >= 1:
            emoji = "📈" if change > 0 else "📉"
            moves.append((abs(change), KeyMoment(year=h.year, age=h.age, emoji=emoji, text=h.text)))
    chosen = warnings[:2]
    chosen += [m for _, m in sorted(moves, key=lambda x: -x[0])[: max(0, limit - len(chosen))]]
    return sorted(chosen, key=lambda m: (m.year, m.age))


def summary(life: Life) -> LifeSummary:
    key_moments = _key_moments(life)
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
        timeline=list(life.history),
    )


def presets() -> list[CharacterSpec]:
    return _presets()


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
    ]
