"""Schema for data-driven event templates (YAML files in `events/templates/`).

One template = one kind of life event. A template states:
- `area`, `eligible` (age, years, housing, extra `when` formula),
- `probability`: a formula over macro values (for the person's region and year) and life state,
- `facts`: ordered formulas. Every number in the text is a fact. Choice effects read facts only,
- `choices`: exactly one `default: true`. Each choice has effects, or `branches` with odds,
- `concept_id`: the lesson the event links to.

Formulas use `lifeline_sim.expr`. Variable names: see `lifeline_sim.events.engine.STATE_VARS`
and the MacroKey names (plus `prev_<key>` and `price_level`).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lifeline_contracts.domain import Area, Housing
from lifeline_sim.expr import Expr

# Effect targets. Additive targets add the value. `set_*` targets replace a field.
ASSET_TARGETS = ("cash", "savings", "investments", "crypto", "pension", "property_value")
DEBT_TARGETS = ("other_debt", "student_loan", "mortgage_balance")
FLOW_TARGETS = ("income", "rent", "living")  # income: gross per year; rent, living: per month
STAT_TARGETS = ("happiness", "health", "smarts")
COUNT_TARGETS = ("children",)
SET_TARGETS = (
    "set_mortgage_rate",
    "set_mortgage_fix_years",
    "set_mortgage_years_left",
    "set_mortgage_tracker",
    "set_energy_fix_years",
    "set_has_partner",
    "set_married",
    "set_has_car",
    "set_employed",
)
STR_TARGETS = ("set_housing",)
ALL_TARGETS = ASSET_TARGETS + DEBT_TARGETS + FLOW_TARGETS + STAT_TARGETS + COUNT_TARGETS + SET_TARGETS + STR_TARGETS


class _S(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


def _parse_effects(raw: dict[str, Any]) -> dict[str, Expr | str]:
    out: dict[str, Expr | str] = {}
    for target, value in raw.items():
        if target not in ALL_TARGETS:
            raise ValueError(f"unknown effect target {target!r}")
        if target in STR_TARGETS:
            if value not in ("parents", "rent", "own", "mortgage"):
                raise ValueError(f"bad housing {value!r}")
            out[target] = str(value)
        else:
            out[target] = Expr.parse(value)
    return out


class Branch(_S):
    """One possible result of a choice. `p` is a formula over facts; the last branch takes the rest."""

    p: Expr | None = None
    text: str
    good: Expr
    effects: dict[str, Expr | str] = Field(default_factory=dict)

    @field_validator("p", mode="before")
    @classmethod
    def _p(cls, v: Any) -> Expr | None:
        return None if v is None else Expr.parse(v)

    @field_validator("good", mode="before")
    @classmethod
    def _good(cls, v: Any) -> Expr:
        return v if isinstance(v, Expr) else Expr.parse(v)

    @field_validator("effects", mode="before")
    @classmethod
    def _effects(cls, v: Any) -> dict[str, Expr | str]:
        return _parse_effects(dict(v or {}))


class ChoiceSpec(_S):
    id: str
    label: str
    emoji: str | None = None
    hint: str | None = None
    default: bool = False
    aliases: tuple[str, ...] = Field(
        default=(), description="Other ids a scenario policy may use for this choice, e.g. 'keep' for 'svr'"
    )
    branches: list[Branch]

    @model_validator(mode="before")
    @classmethod
    def _single_branch(cls, data: Any) -> Any:
        """Allow `effects/text/good` directly on a choice as shorthand for one branch."""
        if isinstance(data, dict) and "branches" not in data:
            data = dict(data)
            branch = {k: data.pop(k) for k in ("effects", "text", "good") if k in data}
            data["branches"] = [branch]
        return data

    @field_validator("branches")
    @classmethod
    def _branches(cls, v: list[Branch]) -> list[Branch]:
        if not v:
            raise ValueError("a choice needs at least one branch")
        if any(b.p is None for b in v[:-1]):
            raise ValueError("every branch except the last needs p")
        return v


class Eligibility(_S):
    age: tuple[int, int] = (16, 110)
    years: tuple[int, int] = (1900, 2200)
    housing: tuple[Housing, ...] | None = None
    when: Expr | None = None

    @field_validator("when", mode="before")
    @classmethod
    def _when(cls, v: Any) -> Expr | None:
        return None if v is None else Expr.parse(v)


class Template(_S):
    id: str
    area: Area
    emoji: str
    title: str
    text: str
    concept_id: str
    tags: tuple[str, ...] = Field(
        default=(), description="Scenario policy keys (ADR 0018), e.g. 'mortgage_deal_end', 'energy_bill'"
    )
    priority: int = Field(default=0, description="Higher wins when more than MAX_EVENTS_PER_YEAR fire")
    eligible: Eligibility = Field(default_factory=Eligibility)
    probability: Expr
    facts: dict[str, Expr] = Field(default_factory=dict)
    choices: list[ChoiceSpec] = Field(min_length=2)

    @field_validator("probability", mode="before")
    @classmethod
    def _prob(cls, v: Any) -> Expr:
        return Expr.parse(v)

    @field_validator("facts", mode="before")
    @classmethod
    def _facts(cls, v: Any) -> dict[str, Expr]:
        return {str(k): Expr.parse(x) for k, x in dict(v or {}).items()}

    @model_validator(mode="after")
    def _check(self) -> Template:
        if not self.id.startswith(f"{self.area}."):
            raise ValueError(f"template id {self.id!r} must start with its area")
        defaults = [c for c in self.choices if c.default]
        if len(defaults) != 1:
            raise ValueError(f"{self.id}: exactly one default choice required")
        ids = [c.id for c in self.choices]
        if len(set(ids)) != len(ids):
            raise ValueError(f"{self.id}: duplicate choice ids")
        names = ids + [a for c in self.choices for a in c.aliases]
        if len(set(names)) != len(names):
            raise ValueError(f"{self.id}: a choice alias repeats a choice id or another alias")
        fact_names = set(self.facts)
        for c in self.choices:
            for b in c.branches:
                for e in b.effects.values():
                    if isinstance(e, Expr) and not e.names <= fact_names:
                        raise ValueError(f"{self.id}/{c.id}: effects may only read facts, got {e.names - fact_names}")
                for e2 in (b.p, b.good):
                    if e2 is not None and not e2.names <= fact_names:
                        raise ValueError(f"{self.id}/{c.id}: p and good may only read facts")
        return self

    @property
    def default_choice(self) -> ChoiceSpec:
        return next(c for c in self.choices if c.default)

    def choice_for(self, name: str) -> ChoiceSpec | None:
        """The choice with this id, else the choice with this alias."""
        for c in self.choices:
            if c.id == name:
                return c
        for c in self.choices:
            if name in c.aliases:
                return c
        return None
