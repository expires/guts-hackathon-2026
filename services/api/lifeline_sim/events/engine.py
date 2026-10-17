"""Load templates, draw events for a year, and resolve choices.

Draw rule (per year, per life):
1. For each template in id order, check eligibility and evaluate `probability`.
2. Roll u = uniform(seed, year, "event", template_id). The template fires when u < p.
   Keying the roll by template id (not by list position) means adding templates in a later
   tier does not change the rolls of existing ones.
3. Sort fired templates by `priority` (high first), then u / p (forced events with p >= 1
   first), and keep up to
   `MAX_EVENTS_PER_YEAR`.

Resolve rule: a choice's branch roll is uniform(seed, event_id, template_id, choice_id).
Effects read only the event's facts, so the result does not depend on the order in which
the player answers the year's events.
"""

from __future__ import annotations

import string
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

import yaml

from lifeline_contracts.domain import Choice, Deltas, Event, Relationship, SourceRef
from lifeline_contracts.macro import MacroKey
from lifeline_sim import params as p
from lifeline_sim.events.schema import (
    ASSET_TARGETS,
    COUNT_TARGETS,
    DEBT_TARGETS,
    STAT_TARGETS,
    Branch,
    ChoiceSpec,
    Template,
)
from lifeline_sim.expr import Expr
from lifeline_sim.macroview import PRICE_LEVEL, SOFT_SOURCES, MacroView, macro_names
from lifeline_sim.occupations import occupation, public_pay_cap
from lifeline_sim.paths import stage_at
from lifeline_sim.rng import rng, uniform
from lifeline_sim.state import SimState

TEMPLATE_PACKAGE = "lifeline_sim.events.templates"

# Life-state variables available to `when`, `probability` and `facts` formulas.
STATE_VARS = (
    "age", "year", "income", "net_income", "cash", "savings", "liquid", "investments", "crypto", "pension",
    "property_value", "mortgage_balance", "mortgage_rate", "mortgage_payment", "mortgage_years_left",
    "fixed_until", "rent", "living", "monthly_costs", "other_debt", "student_loan", "net_worth",
    "happiness", "health", "smarts", "employed", "retired", "years_in_role", "has_car", "has_partner",
    "married", "children", "is_renter", "is_owner", "has_mortgage", "on_variable", "bonus", "bonus_net",
    "occ_redundancy_mult", "occ_redundancy_stock", "occ_bonus_share", "public_sector", "pay_cap_active",
    "variable_rate", "on_tracker", "tracker_margin", "tracker_deal_years", "variable_margin",
    "energy_fixed", "on_path", "is_student",
)  # fmt: skip


def state_env(s: SimState) -> dict[str, float]:
    occ = occupation(s.character.occupation)
    env: dict[str, float] = {
        "age": float(s.age),
        "year": float(s.year),
        "income": s.income,
        "net_income": s.last_net_income,
        "cash": s.cash,
        "savings": s.savings,
        "liquid": s.cash + s.savings,
        "investments": s.investments,
        "crypto": s.crypto,
        "pension": s.pension,
        "property_value": s.property_value,
        "mortgage_balance": s.mortgage_balance,
        "mortgage_rate": s.mortgage_rate or 0.0,
        "mortgage_payment": s.mortgage_payment,
        "mortgage_years_left": float(s.mortgage_years_left),
        "fixed_until": float(s.mortgage_fixed_until or 0),
        "rent": s.rent,
        "living": s.living,
        "monthly_costs": s.monthly_costs,
        "other_debt": s.other_debt,
        "student_loan": s.student_loan,
        "net_worth": s.net_worth,
        "happiness": float(s.happiness),
        "health": float(s.health),
        "smarts": float(s.smarts),
        "employed": float(s.employed),
        "retired": float(s.retired),
        "years_in_role": float(s.years_in_role),
        "has_car": float(s.has_car),
        "has_partner": float(s.has_partner),
        "married": float(s.married),
        "children": float(s.children),
        "is_renter": float(s.housing == "rent"),
        "is_owner": float(s.housing in ("own", "mortgage")),
        "has_mortgage": float(s.housing == "mortgage" and s.mortgage_balance > 0),
        "on_variable": float(
            s.housing == "mortgage" and s.mortgage_balance > 0 and (s.mortgage_fixed_until or 0) < s.year
        ),
        "bonus": s.last_bonus,
        "bonus_net": s.last_bonus_net,
        "occ_redundancy_mult": occ.redundancy_mult,
        "occ_redundancy_stock": occ.redundancy_stock,
        "occ_bonus_share": occ.bonus_share,
        "public_sector": float(occ.public_sector),
        "pay_cap_active": float(occ.public_sector and public_pay_cap(s.year) is not None),
        "variable_rate": (s.mortgage_rate or 0.0),
        "on_tracker": float(
            s.mortgage_tracker
            and s.housing == "mortgage"
            and s.mortgage_balance > 0
            and (s.mortgage_fixed_until or 0) >= s.year
        ),
        "tracker_margin": p.TRACKER_MARGIN,
        "tracker_deal_years": float(p.TRACKER_DEAL_YEARS),
        "variable_margin": p.VARIABLE_MARGIN,
        "energy_fixed": float(s.energy_fixed_until >= s.year),
        "on_path": float(s.path_id is not None),
        "is_student": float(s.student),
    }
    return env


# ---------- loading ----------


@dataclass(frozen=True)
class LoadedTemplate:
    t: Template
    macro_keys: tuple[MacroKey, ...]  # every macro series the template reads, for sources and eligibility
    soft_keys: tuple[MacroKey, ...] = ()  # cited when the table has them; never needed for eligibility
    macro_vars: frozenset[str] = frozenset()  # macro formula variables read; each must have a value (ADR 0027)


def _exprs(t: Template) -> Iterable[Expr]:
    yield t.probability
    if t.eligible.when is not None:
        yield t.eligible.when
    yield from t.facts.values()


@lru_cache(maxsize=1)
def load_templates() -> tuple[LoadedTemplate, ...]:
    """All templates from every YAML file in `events/templates/`, sorted by id."""
    names = macro_names()
    out: list[LoadedTemplate] = []
    root = resources.files(TEMPLATE_PACKAGE)
    for entry in sorted(root.iterdir(), key=lambda e: e.name):
        if not entry.name.endswith(".yaml"):
            continue
        raw: Any = yaml.safe_load(entry.read_text(encoding="utf-8"))
        for item in raw or []:
            t = Template.model_validate(item)
            # `price_level` only scales fixed 2024-pound costs to the year. It is not a headline
            # number, so it alone does not add the CPI series to the event's source chips (V5).
            read = {n for e in _exprs(t) for n in e.names if n in names and n != PRICE_LEVEL}
            used = sorted({names[n] for n in read}, key=lambda k: k.value)
            soft = sorted({SOFT_SOURCES[n] for n in read if n in SOFT_SOURCES}, key=lambda k: k.value)
            all_read = frozenset(n for e in _exprs(t) for n in e.names if n in names)
            out.append(LoadedTemplate(t=t, macro_keys=tuple(used), soft_keys=tuple(soft), macro_vars=all_read))
    out.sort(key=lambda lt: lt.t.id)
    ids = [lt.t.id for lt in out]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate template ids")
    return tuple(out)


@lru_cache(maxsize=1)
def templates_by_id() -> dict[str, LoadedTemplate]:
    return {lt.t.id: lt for lt in load_templates()}


# ---------- drawing ----------


class _Fmt(string.Formatter):
    """str.format over facts only. Field names must be plain fact names."""

    def get_field(self, field_name: str, args: Any, kwargs: Any) -> Any:
        if not field_name.isidentifier():
            raise ValueError(f"bad placeholder {field_name!r}")
        return super().get_field(field_name, args, kwargs)


_FMT = _Fmt()


def render(text: str, facts: Mapping[str, float]) -> str:
    return _FMT.vformat(text, (), dict(facts))


def eligible(lt: LoadedTemplate, s: SimState, mv: MacroView, env: Mapping[str, float]) -> bool:
    t = lt.t
    e = t.eligible
    if not (e.age[0] <= s.age <= e.age[1] and e.years[0] <= s.year <= e.years[1]):
        return False
    if e.housing is not None and s.housing not in e.housing:
        return False
    if any(not mv.has(k) for k in lt.macro_keys):
        return False
    # Live mode (ADR 0027): a template that reads a value missing for this year and place does not fire.
    if any(n not in env for n in lt.macro_vars):
        return False
    return e.when is None or bool(e.when.eval(env))


def compute_facts(t: Template, env: Mapping[str, float]) -> dict[str, float]:
    scope = dict(env)
    facts: dict[str, float] = {}
    for name, ex in t.facts.items():
        v = round(ex.eval(scope), 2)
        facts[name] = v
        scope[name] = v
    return facts


def sources_for(lt: LoadedTemplate, s: SimState, mv: MacroView) -> list[SourceRef]:
    out: list[SourceRef] = []
    for key in (*lt.macro_keys, *lt.soft_keys):
        ref = mv.source_ref(key, s.year, s.region)
        if ref is not None:
            out.append(ref)
    return out


def build_event(lt: LoadedTemplate, s: SimState, mv: MacroView, env: Mapping[str, float], event_id: str) -> Event:
    t = lt.t
    facts = compute_facts(t, env)
    choices = [
        Choice(
            id=c.id,
            label=c.label,
            emoji=c.emoji,
            hint=render(c.hint, facts) if c.hint else None,
            is_default=c.default,
        )
        for c in t.choices
    ]
    return Event(
        id=event_id,
        template_id=t.id,
        area=t.area,
        year=s.year,
        age=s.age,
        emoji=t.emoji,
        title=render(t.title, facts),
        text=render(t.text, facts),
        choices=choices,
        facts=facts,
        sources=sources_for(lt, s, mv),
        concept_id=t.concept_id,
    )


QUICK_TAG = "quick"
STAGE_TAGS = {"study": "stage_study", "study_pg": "stage_study", "apprentice": "stage_work", "work": "stage_work"}


def quick_pool(s: SimState, mv: MacroView, env: Mapping[str, float]) -> list[LoadedTemplate]:
    """Quick Life templates that can fire for this year: tag `quick`, the stage tag (or `stage_any`), age and
    year range, and macro data present. `when` is not checked, so earlier choices never change the pool."""
    stage = stage_at(s.path_id, s.age) if s.path_id is not None else None
    stage_tag = STAGE_TAGS.get(stage.kind, "stage_any") if stage is not None else "stage_any"
    out: list[LoadedTemplate] = []
    for lt in load_templates():
        t = lt.t
        if QUICK_TAG not in t.tags or not ({stage_tag, "stage_any"} & set(t.tags)):
            continue
        e = t.eligible
        if not (e.age[0] <= s.age <= e.age[1] and e.years[0] <= s.year <= e.years[1]):
            continue
        if any(not mv.has(k) for k in lt.macro_keys) or any(n not in env for n in lt.macro_vars):
            continue
        out.append(lt)
    return out


def draw_quick_event(s: SimState, mv: MacroView, env: Mapping[str, float]) -> list[Event]:
    """Quick Life (ADR 0052): one event at each planned event year, none in other years.

    The template is a seeded pick from `quick_pool`, never one already used in this life. Same seed, path
    and start year give the same events."""
    if s.year not in s.quick_event_years:
        return []
    pool = [lt for lt in quick_pool(s, mv, env) if lt.t.id not in s.last_fired]
    if not pool:
        return []
    lt = rng(s.seed, "quick", "event", s.year).choice(pool)
    s.last_fired[lt.t.id] = s.year
    return [build_event(lt, s, mv, env, f"ev-{s.year}-1")]


def draw_events(s: SimState, mv: MacroView) -> list[Event]:
    env = {**mv.env(s.year, s.region), **state_env(s)}
    if s.quick:
        return draw_quick_event(s, mv, env)
    fired: list[tuple[int, float, str, LoadedTemplate]] = []
    focus_on = bool(s.focus_tags) and (s.focus_until is None or s.year <= s.focus_until)
    focus_tags = s.focus_tags if focus_on else ()
    related = {r for tag in focus_tags for r in p.FOCUS_RELATED.get(tag, ())}
    for lt in load_templates():
        if not eligible(lt, s, mv, env):
            continue
        prob = max(0.0, min(1.0, lt.t.probability.eval(env)))
        if prob <= 0:
            continue
        priority = lt.t.priority
        is_focus = any(tag in focus_tags for tag in lt.t.tags)
        last = s.last_fired.get(lt.t.id)
        if last is not None and s.year - last < p.EVENT_COOLDOWN_YEARS and not (lt.t.repeatable or is_focus):
            continue
        if is_focus:
            prob = 1.0
        if is_focus or any(tag in related for tag in lt.t.tags):
            priority += p.FOCUS_PRIORITY_BOOST
        u = uniform(s.seed, s.year, "event", lt.t.id)
        if u < prob:
            fired.append((-priority, 0.0 if prob >= 1 else u / prob, lt.t.id, lt))
    fired.sort(key=lambda x: (x[0], x[1], x[2]))
    # Focused events ("Test it") come on top of the yearly cap, so the other events of the year
    # are the same whichever option the scenario tests.
    focused = [f for f in fired if -f[0] >= p.FOCUS_PRIORITY_BOOST]
    others = [f for f in fired if -f[0] < p.FOCUS_PRIORITY_BOOST][: p.MAX_EVENTS_PER_YEAR]
    chosen = focused + others
    for _, _, tid, _ in chosen:
        s.last_fired[tid] = s.year
    return [build_event(lt, s, mv, env, f"ev-{s.year}-{i + 1}") for i, (_, _, _, lt) in enumerate(chosen)]


# ---------- resolving ----------


@dataclass(frozen=True)
class Resolution:
    choice: ChoiceSpec
    branch: Branch
    effects: dict[str, float | str]
    good: bool
    text: str


def resolve(event: Event, choice_id: str, seed: int) -> Resolution:
    lt = templates_by_id().get(event.template_id)
    if lt is None:
        raise KeyError(event.template_id)
    choice = next((c for c in lt.t.choices if c.id == choice_id), None)
    if choice is None:
        raise KeyError(choice_id)
    facts = event.facts
    u = uniform(seed, event.id, event.template_id, choice_id, "branch")
    chosen = choice.branches[-1]
    cum = 0.0
    for b in choice.branches:
        if b.p is None:
            chosen = b
            break
        cum += max(0.0, min(1.0, b.p.eval(facts)))
        if u < cum:
            chosen = b
            break
    effects: dict[str, float | str] = {
        k: (v if isinstance(v, str) else round(v.eval(facts), 2)) for k, v in chosen.effects.items()
    }
    return Resolution(
        choice=choice,
        branch=chosen,
        effects=effects,
        good=bool(chosen.good.eval(facts)),
        text=render(chosen.text, facts),
    )


def apply_effects(s: SimState, effects: Mapping[str, float | str]) -> Deltas:
    """Apply effects to the state in place. Returns the change in net worth and stats."""
    money = 0.0
    stats = {"happiness": 0, "health": 0, "smarts": 0}
    for target, value in effects.items():
        if isinstance(value, str):
            if target == "set_housing" and value in ("parents", "rent", "own", "mortgage"):
                s.housing = value  # type: ignore[assignment]
            continue
        if target in ASSET_TARGETS:
            setattr(s, target, getattr(s, target) + value)
            money += value
        elif target in DEBT_TARGETS:
            setattr(s, target, max(0.0, getattr(s, target) + value))
            money -= value
        elif target == "income":
            s.income = max(0.0, s.income + value)
        elif target == "rent":
            s.rent = max(0.0, s.rent + value)
        elif target == "living":
            s.living = max(0.0, s.living + value)
            s.living_adj += value
        elif target == "want_weekly":
            s.want_adj += value
        elif target in STAT_TARGETS:
            before = getattr(s, target)
            after = int(max(0, min(100, before + round(value))))
            setattr(s, target, after)
            stats[target] += after - before
        elif target in COUNT_TARGETS:
            _add_children(s, int(round(value)))
        elif target == "set_mortgage_rate":
            s.mortgage_rate = value
        elif target == "set_mortgage_fix_years":
            s.mortgage_fixed_until = s.year + int(value) if value > 0 else s.year
            s.mortgage_tracker = False
        elif target == "set_mortgage_years_left":
            s.mortgage_years_left = int(value)
        elif target == "set_has_partner":
            set_partner(s, bool(value))
        elif target == "set_married":
            set_married(s, bool(value))
        elif target == "set_energy_fix_years":
            s.energy_fixed_until = s.year + int(value) if value > 0 else 0
        elif target == "set_has_car":
            s.has_car = bool(value)
        elif target == "set_employed":
            s.employed = bool(value)
            if not s.employed:
                s.income = 0.0
                s.years_in_role = 0
    tracker = effects.get("set_mortgage_tracker")
    if isinstance(tracker, float | int):
        s.mortgage_tracker = bool(tracker)
    if s.housing == "mortgage" and s.mortgage_balance <= 0:
        s.housing = "own"
    return Deltas(money=round(money, 2), **stats)


def _add_children(s: SimState, n: int) -> None:
    for _ in range(max(0, n)):
        s.children += 1
        s.relationships.append(
            Relationship(
                id=f"rl-child-{s.children}", kind="child", name=f"Child {s.children}", emoji="👶", closeness=95
            )
        )


def set_partner(s: SimState, on: bool) -> None:
    if on and not s.has_partner:
        s.has_partner = True
        s.relationships = [r for r in s.relationships if r.id != "rl-partner"]
        s.relationships.append(Relationship(id="rl-partner", kind="partner", name="Partner", emoji="💑", closeness=80))
    elif not on and s.has_partner:
        s.has_partner = False
        s.married = False
        s.relationships = [
            r.model_copy(update={"kind": "ex", "closeness": 20, "emoji": "💔"}) if r.id == "rl-partner" else r
            for r in s.relationships
        ]


def set_married(s: SimState, on: bool) -> None:
    s.married = on and s.has_partner
    if s.married:
        s.relationships = [
            r.model_copy(update={"kind": "spouse", "emoji": "💍"}) if r.id == "rl-partner" else r
            for r in s.relationships
        ]
