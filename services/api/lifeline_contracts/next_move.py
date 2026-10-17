"""Next Move: the product's one question, "What is my next money move?" (ADR 0018). BOSS-owned.

Flow: FinanceSnapshot (W1) + MacroTable (W1) -> lifeline_engine.next_move (W2: candidates, £/year impact,
worst-case risk, twins + similar past periods, confidence) -> GET /v1/next-move (W4)
-> "Test it": lifeline_sim.api.play_scenario (W3) per option through the most relevant past period
-> POST /v1/next-move/test (W4) -> side-by-side outcomes.
No LLM decides anything here. Explain (W5) may only reword text; the verifier checks every number.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.domain import CharacterSpec, IsoDate, ShortId, SourceRef
from lifeline_contracts.finance import Bill, FinanceMeta, Point, SpendPrediction

MoveKind = Literal[
    "fix_mortgage",
    "remortgage",
    "move_savings",
    "cancel_subscription",
    "switch_subscription",
    "switch_energy",
    "pay_off_debt",
    "build_emergency_fund",
    "cut_budget",
    "spread_investments",
]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidencePoint(_M):
    text: str = Field(description="Plain English. Every number in it appears in facts.")
    facts: dict[str, float] = Field(default_factory=dict)
    source: SourceRef | None = None


class MoveOption(_M):
    id: str = Field(description="e.g. fix_5y, fix_2y, tracker, keep, switch, cancel")
    label: str
    is_recommended: bool = False


class TradeOff(_M):
    """What the user gives up with this move. Engine-defined per move kind (ADR 0042), never LLM-written."""

    summary: str = Field(
        max_length=90, description="One line for the card, e.g. 'Less flexibility: a fee if you leave early'"
    )
    points: list[EvidencePoint] = Field(
        min_length=1, max_length=4, description="Full trade-off for Why?. Every number in a point appears in its facts."
    )


class TestPeriod(_M):
    start: int
    end: int
    label: str = Field(description="e.g. '2021-2023 rate shock'")


class Move(_M):
    id: str
    kind: MoveKind
    action: str = Field(description="The move in a few words, e.g. 'Fix for 5 years'")
    headline: str = Field(description="e.g. 'Your deal ends in 165 days'")
    impact_per_year: float = Field(description="Expected GBP per year vs doing nothing; positive is better")
    worst_case_per_year: float = Field(description="GBP per year in the worst matched period; can be negative")
    confidence: float = Field(ge=0, le=1)
    confidence_label: str = Field(description="e.g. '7 in 10 twins in similar past periods did better'")
    evidence: list[EvidencePoint] = Field(min_length=3, max_length=3)
    sources: list[SourceRef]
    options: list[MoveOption] = Field(min_length=1)
    deadline: IsoDate | None = None
    days_left: int | None = Field(default=None, ge=0)
    testable: bool
    test_period: TestPeriod | None = None
    concept_id: str | None = Field(default=None, description="Lesson for the 'Why?' button")
    gain_kind: Literal["gbp_per_year", "months_of_cover"] = Field(
        default="gbp_per_year", description="Gain as £ a year (impact_per_year) or months of cover (cover_months)"
    )
    cover_months: float | None = Field(default=None, ge=0, description="Months of costs covered after the move")
    trade_off: TradeOff | None = Field(
        default=None, description="What you give up. Always set by the engine (ADR 0042)"
    )


class NextMoveBacktest(_M):
    method: str
    n: int = Field(ge=0)
    hit_rate: float = Field(ge=0, le=1)
    baseline: str
    baseline_hit_rate: float = Field(ge=0, le=1)


class NextMoveResponse(_M):
    meta: FinanceMeta
    question: Literal["What is my next money move?"] = "What is my next money move?"
    top: Move
    runners_up: list[Move] = Field(max_length=2)
    backtest: NextMoveBacktest | None = None
    decision_sources: list[SourceRef] = Field(
        default_factory=list,
        description="Decision inputs only (user data, BoE, ONS, Nomis, Land Registry, Companies House, Octopus, FX, "
        "CoinGecko) with status. Game-only and context sources (news, rate dates) are not counted (ADR 0032).",
    )
    decision_source_count: int = Field(default=0, ge=0, description="'Based on N sources'")
    context_lines: list[str] = Field(
        default_factory=list, max_length=3, description="Context only, never a decision input (e.g. next MPC date)"
    )
    generated_at: str


class TestMoveRequest(_M):
    move_id: str = Field(min_length=1, max_length=64)
    option_ids: list[ShortId] | None = Field(default=None, max_length=4, description="Default: all options of the move")


class OptionOutcome(_M):
    option_id: str
    label: str
    is_recommended: bool
    life_id: str = Field(description="A stored life the client can open in the Life tab")
    net_worth_path: list[Point]
    end_net_worth: float
    total_cost: float = Field(description="GBP paid for this option over the period (e.g. mortgage payments)")
    missed_payments: int = Field(ge=0)
    worst_year: int
    worst_year_change: float
    index: float = Field(ge=0)


class TestMoveResult(_M):
    move_id: str
    period: TestPeriod
    character: CharacterSpec
    outcomes: list[OptionOutcome] = Field(min_length=1, max_length=4)
    summary: str = Field(description="e.g. 'Fixing for 5 years left you £4,180 better off by 2023.'")
    evidence_sentence: str = Field(description="e.g. '7 in 10 twins in similar past periods did better.'")
    sources: list[SourceRef]


class PlanItem(_M):
    id: str
    move_id: str
    kind: MoveKind
    action: str
    impact_per_year: float
    added_at: str
    status: Literal["todo", "done"] = "todo"


class AddPlanItemRequest(_M):
    move_id: str = Field(min_length=1, max_length=64)


class PlanResponse(_M):
    items: list[PlanItem]
    total_impact_per_year: float


# ---------- Money home in one request (user UX fix) ----------


class FinanceHome(_M):
    """Everything Money home needs in ONE request. No data is a normal state (has_data=false), not an error."""

    has_data: bool
    meta: FinanceMeta | None = None
    balance: float | None = Field(default=None, description="'In your account' tile")
    net_worth: float | None = Field(default=None, description="'Net worth' tile")
    next_move: NextMoveResponse | None = Field(default=None, description="Compact card uses top only")
    prediction: SpendPrediction | None = Field(default=None, description="Guess my spend")
    coming_up: list[Bill] = Field(default_factory=list, max_length=3)
    coming_up_more: bool = False
    connect_prompt: str | None = Field(
        default=None, description="Shown when has_data is false: 'Connect your money to see your next move'"
    )
