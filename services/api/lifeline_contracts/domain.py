"""Domain models shared by sim (W3), engine (W2), explain (W5) and api (W4).

These mirror the schemas in contracts/openapi.yaml one to one. Field names are the wire names.
If you need a change, ask BOSS: the contract and this file change together.
"""

from __future__ import annotations

from datetime import date as _date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from lifeline_contracts.observation import Status

LifeMode = Literal["self", "random", "god", "preset"]
Area = Literal["work", "home", "money", "bills", "car", "health", "family", "place", "employer", "study", "state"]
Tab = Literal["job", "assets", "relationships", "activities", "money"]
Housing = Literal["parents", "rent", "own", "mortgage"]
Sex = Literal["female", "male"]


# Bounded identifier types for request inputs (V6).
ShortId = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")]
RegionSlug = Annotated[str, StringConstraints(min_length=2, max_length=40, pattern=r"^[a-z-]+$")]
ParamKey = Annotated[str, StringConstraints(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_]+$")]
ParamText = Annotated[str, StringConstraints(max_length=64)]


def _real_date(v: str) -> str:
    _date.fromisoformat(v)  # raises ValueError -> 422 for impossible dates such as 2026-02-30
    return v


def _real_month(v: str) -> str:
    _date.fromisoformat(v + "-01")
    return v


# Calendar-checked date strings (V1 Tier 1): the pattern documents the format, the validator rejects 2026-02-30.
IsoDate = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$"), AfterValidator(_real_date)]
IsoMonth = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}$"), AfterValidator(_real_month)]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- character ----------


class CharacterSpec(_M):
    """Input for a new life. Presets and random characters are also CharacterSpec."""

    id: ShortId | None = None
    name: str = Field(min_length=1, max_length=40)
    emoji: str = Field(default="🙂", max_length=8)
    sex: Sex = "female"
    occupation: str = Field(min_length=1, max_length=60, description="e.g. nurse, plumber, banker")
    region: RegionSlug = Field(description="Canonical region slug, see observation.REGIONS")
    town: str = Field(max_length=60)
    postcode: str | None = Field(default=None, max_length=10)
    birth_year: int = Field(ge=1930, le=2026)
    annual_income: float = Field(ge=0, le=10_000_000, description="gbp gross per year at start")
    savings: float = Field(default=0, ge=0, le=100_000_000)
    debt: float = Field(default=0, ge=0, le=100_000_000)
    housing: Housing = "rent"
    property_value: float = Field(default=0, ge=0, le=100_000_000)
    mortgage_balance: float = Field(default=0, ge=0, le=100_000_000)
    blurb: str | None = Field(default=None, max_length=200)


# ---------- stats and money ----------


class Stats(_M):
    happiness: int = Field(ge=0, le=100)
    health: int = Field(ge=0, le=100)
    smarts: int = Field(ge=0, le=100)
    money: int = Field(ge=0, le=100, description="0-100 bar derived from net worth vs income")


class Finances(_M):
    cash: float
    savings: float
    investments: float
    crypto: float
    pension: float
    property_value: float
    mortgage_balance: float
    mortgage_rate: float | None = Field(default=None, description="percent")
    mortgage_fixed_until: int | None = Field(default=None, description="year the fix ends")
    other_debt: float
    student_loan: float
    annual_income: float
    monthly_costs: float
    net_worth: float


class IndexState(_M):
    value: float = Field(ge=0)
    r_player: float
    r_autopilot: float
    missed_payments: int = Field(ge=0)
    max_drawdown: float = Field(ge=0, le=1)


class SourceRef(_M):
    source: str
    series_id: str
    status: Status
    note: str | None = None


# ---------- events ----------


class Choice(_M):
    id: str
    label: str
    emoji: str | None = None
    hint: str | None = Field(default=None, description="Plain English cost or effect hint")
    is_default: bool = False


class Event(_M):
    id: str = Field(description="Instance id, unique within a life")
    template_id: str
    area: Area
    year: int
    age: int
    emoji: str
    title: str
    text: str
    text_source: Literal["template", "llm"] = "template"
    choices: list[Choice] = Field(min_length=1)
    facts: dict[str, float] = Field(default_factory=dict, description="Engine numbers behind the text")
    sources: list[SourceRef] = Field(default_factory=list)
    concept_id: str | None = None


class Deltas(_M):
    money: float = 0
    happiness: int = 0
    health: int = 0
    smarts: int = 0


class Outcome(_M):
    event_id: str
    choice_id: str
    text: str
    text_source: Literal["template", "llm"] = "template"
    deltas: Deltas
    facts: dict[str, float] = Field(default_factory=dict)
    good: bool


class ChartPoint(_M):
    x: float
    y: float
    label: str | None = None


class Chart(_M):
    kind: Literal["line", "bar"]
    title: str
    x_label: str
    y_label: str
    points: list[ChartPoint]
    source: SourceRef | None = None


class Quiz(_M):
    question: str
    options: list[str] = Field(min_length=2, max_length=4)
    answer_index: int = Field(ge=0)


class Lesson(_M):
    concept_id: str
    title: str
    chart: Chart
    sentences: list[str] = Field(min_length=2, max_length=2)
    quiz: Quiz
    personal: str | None = Field(
        default=None,
        description="Bridge to the Money tab: one sentence with the user's real numbers, e.g. "
        "'You spend £47 a month on 6 subscriptions.' Omitted when no finance data exists.",
    )


class Concept(_M):
    id: str
    title: str
    emoji: str
    area: Area
    summary: str
    lesson: Lesson


# ---------- life ----------


class Job(_M):
    title: str
    employer: str | None = None
    annual_income: float
    years_in_role: int = 0
    employer_status: Literal["active", "insolvent", "unknown"] = "unknown"


class Asset(_M):
    id: str
    kind: Literal["home", "car", "investment", "crypto", "pension", "business", "other"]
    name: str
    value: float


class Relationship(_M):
    id: str
    kind: Literal["partner", "spouse", "child", "parent", "friend", "ex"]
    name: str
    emoji: str
    closeness: int = Field(ge=0, le=100)


class AvailableAction(_M):
    tab: Tab
    id: str
    label: str
    emoji: str | None = None
    hint: str | None = None
    enabled: bool = True
    paid: bool = False


class Ribbon(_M):
    id: str
    title: str
    emoji: str
    reason: str


class YearLog(_M):
    """One entry per year and per decision. Rewind targets entries with decision_id."""

    year: int
    age: int
    text: str
    decision_id: str | None = None
    event_id: str | None = None
    choice_id: str | None = None
    net_worth: float
    autopilot_net_worth: float
    index: float


class RewindState(_M):
    free_left: int = Field(ge=0)
    has_pass: bool = False


class Life(_M):
    id: str
    seed: int
    mode: LifeMode
    character: CharacterSpec
    start_year: int
    year: int
    age: int
    alive: bool
    cause_of_death: str | None = None
    stats: Stats
    finances: Finances
    index: IndexState
    job: Job | None = None
    assets: list[Asset]
    relationships: list[Relationship]
    pending_events: list[Event] = Field(description="Events awaiting a choice. AGE is blocked while non-empty.")
    available_actions: list[AvailableAction]
    history: list[YearLog]
    ribbons: list[Ribbon]
    concepts_unlocked: list[str]
    rewind: RewindState
    room_code: str | None = None
    reached_present: bool = False
    next_age: int | None = Field(
        default=None, description="Age after the next AGE tap (Quick Life taps move 1 or 2 years); None when over"
    )


class AgeResult(_M):
    life: Life
    events: list[Event]
    lesson: Lesson | None = None


class ChoiceResult(_M):
    life: Life
    outcome: Outcome
    lesson: Lesson | None = None
    concept_unlocked: str | None = None


class ActionResult(_M):
    life: Life
    outcome: Outcome
    lesson: Lesson | None = None
    concept_unlocked: str | None = None


class RewindResult(_M):
    life: Life
    abandoned_index: float
    abandoned_net_worth: float


class KeyMoment(_M):
    year: int
    age: int
    emoji: str
    text: str


class HabitComponents(_M):
    """Ratios of the user's own amounts, 0-100. No amounts, so they may be shared (ADR 0052 privacy rule)."""

    savings_rate: int | None = Field(default=None, ge=0, le=100)
    months_of_cover: int | None = Field(default=None, ge=0, le=100)
    spend_stability: int | None = Field(default=None, ge=0, le=100)
    discretionary_share: int | None = Field(default=None, ge=0, le=100)
    subscription_creep: int | None = Field(default=None, ge=0, le=100)
    debt_pressure: int | None = Field(default=None, ge=0, le=100)


class HabitScore(_M):
    components: HabitComponents
    overall: int | None = Field(default=None, ge=0, le=100)


class LifeSummary(_M):
    life_id: str
    name: str
    born: int
    died: int | None = None
    age: int
    cause_of_death: str | None = None
    final_index: float
    net_worth: float
    autopilot_net_worth: float
    ribbons: list[Ribbon]
    key_moments: list[KeyMoment]
    concepts_unlocked: int
    habit_score: HabitScore | None = Field(default=None, description="Quick Life: from the game ledger (ADR 0059)")
    timeline: list[YearLog]


class Challenge(_M):
    id: str
    title: str
    emoji: str
    description: str
    character_id: str
    start_year: int
    goal: dict[str, float | str]
    scope: Literal["you", "life"] = Field(
        default="life", description="'you' = scored on the user's own data (ratios, no £); 'life' = a game life"
    )


# ---------- decision and evaluation ----------


class DecisionProfile(_M):
    age: int = Field(ge=16, le=100)
    region: RegionSlug
    postcode: str | None = Field(default=None, max_length=10)
    annual_income: float = Field(ge=0, le=10_000_000)
    savings: float = Field(ge=0, le=100_000_000)
    other_debt: float = Field(default=0, ge=0, le=100_000_000)
    housing: Housing
    monthly_rent: float | None = Field(default=None, ge=0, le=100_000)
    property_value: float | None = Field(default=None, ge=0, le=100_000_000)
    mortgage_balance: float | None = Field(default=None, ge=0, le=100_000_000)
    mortgage_years_left: int | None = Field(default=None, ge=0, le=40)
    deal_ends_in_months: int | None = Field(default=None, ge=0, le=120)


class Evidence(_M):
    twins_count: int
    periods: list[str] = Field(description="Matched past periods, e.g. '1989-1991'")
    success_rate: float = Field(ge=0, le=1)
    sentence: str = Field(description="e.g. '7 in 10 twins in similar past periods did better.'")


class Alternative(_M):
    action: str
    score: float
    success_rate: float = Field(ge=0, le=1)


class Decision(_M):
    question: str
    headline: str
    action: str
    reasons: list[str]
    evidence: Evidence
    alternatives: list[Alternative]
    sources: list[SourceRef]
    disclaimer: str
    generated_at: str


class BacktestPeriod(_M):
    start: int
    end: int
    recommended: str
    realised_best: str
    hit: bool


class Evaluation(_M):
    method: str
    n: int
    hit_rate: float = Field(ge=0, le=1)
    baseline_hit_rate: float = Field(ge=0, le=1)
    baseline: str
    periods: list[BacktestPeriod]
    generated_at: str
