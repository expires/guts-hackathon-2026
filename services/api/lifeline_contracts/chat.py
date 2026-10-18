"""Ask Penny (chat), news and rate-decision dates. BOSS-owned. ADR 0030-0034.

Principles: chat and news SERVE the one decision ("Where should my money go this month?"); they never make it.
The LLM never produces a number: every number in a bubble maps to a fact (tool result or the facts table).
Untrusted text (news, user messages, merchant names) is data, never instructions.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.domain import IsoDate, ShortId, SourceRef
from lifeline_contracts.observation import Status


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- news and rate decisions (ADR 0030) ----------


class NewsItem(_M):
    """Headline and link only. Never article body text (copyright)."""

    id: str
    headline: str = Field(max_length=300)
    standfirst: str | None = Field(default=None, max_length=300, description="At most one sentence")
    section: str = Field(max_length=60)
    date: IsoDate
    url: str = Field(max_length=500)
    source: Literal["guardian"] = "guardian"


class NewsResponse(_M):
    status: Status
    items: list[NewsItem] = Field(max_length=50)


class RateDecisions(_M):
    status: Status
    next_decision: IsoDate | None = None
    dates: list[IsoDate] = Field(max_length=24)
    source: SourceRef


# ---------- chat (ADR 0031) ----------

Reaction = Literal["eyes", "brain", "thumbs", "tick", "question", "shrug"]
Screen = Literal[
    "money",
    "next_move",
    "why",
    "life_event",
    "life",
    "onboarding",
    "room_round",
    "test_it",
    "learn_lesson",
    "forecast",
    "other",
]


class ChatContext(_M):
    next_move_id: ShortId | None = None
    card_index: int | None = Field(default=None, ge=0, description="Learn lesson card on screen (D4)")
    life_id: ShortId | None = None
    event_id: ShortId | None = None
    screen: Screen | None = None
    title: str | None = Field(
        default=None,
        max_length=80,
        description="Thread title for a NEW thread, e.g. 'Safety fund, age 19'. Used instead of the first message.",
    )
    multiplayer: bool = Field(
        default=False, description="Room round: Penny explains trade-offs and never picks an option."
    )
    room_code: str | None = Field(default=None, max_length=8, description="Room of the round (screen room_round)")
    lesson_id: ShortId | None = Field(default=None, description="Learn lesson (screen learn_lesson, ADR 0068)")
    round_id: str | None = Field(
        default=None, max_length=40, description="Same Decision prompt id; the server loads its options and game money"
    )


class ChatRequest(_M):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: ShortId | None = Field(default=None, description="Omit to start a new thread")
    reply_to: ShortId | None = Field(default=None, description="Message id this question replies to")
    context: ChatContext | None = None
    language: Literal["en", "fr", "es", "pt", "it", "zh-Hans", "hi", "ne"] = Field(
        default="en", description="Answer language (ADR 0063); numbers stay in Western digits with £"
    )


ChatMode = Literal["checked", "general"]
"""checked = an engine tool was used, every personal number verified ("Checked with your data").
general = no engine tool ("General answer"); must not state the user's own numbers (ADR 0051)."""

DISCLAIMER = (
    "Penny is AI and can make mistakes. Guidance only, not regulated financial advice. Check before big decisions."
)


class ChatBubble(_M):
    id: str
    kind: Literal["answer", "caveat", "question", "general_knowledge"]
    text: str = Field(max_length=600)


class ChatFact(_M):
    """A number Penny may say. From a tool result or the official facts table."""

    id: str
    value: float
    unit: Literal["gbp", "gbp_per_month", "gbp_per_year", "percent", "months", "years", "count", "date_year"]
    label: str = Field(max_length=120)
    source_id: str | None = None


class Highlight(_M):
    """A tappable number inside a bubble."""

    bubble_id: str
    start: int = Field(ge=0)
    length: int = Field(ge=1)
    fact_id: str
    source_id: str | None = None


class ChatSource(_M):
    id: str
    group: Literal["your_data", "live_sources", "general_knowledge"]
    label: str = Field(max_length=120)
    ref: SourceRef | None = None
    url: str | None = Field(default=None, max_length=500)
    updated_at: str | None = None


class ToolCall(_M):
    name: Literal[
        "next_move",
        "test_move",
        "finance_summary",
        "spend_prediction",
        "cash_flow_projection",
        "life_replay",
        "event_choices",
        "news_search",
        "rate_decision_dates",
        "facts_table",
        "boe_rates",
        "web_search",
        "user_balance",
        "habit_score",
        "inflation",
        "fx_convert",
        "forecast",
        "forecast_what_if",
    ]
    ok: bool
    duration_ms: int = Field(ge=0)


class ChatResponse(_M):
    thread_id: str
    message_id: str
    reply_to: str = Field(description="The user's message id this answer group attaches to")
    reaction: Reaction
    mode: ChatMode = "checked"
    bubbles: list[ChatBubble] = Field(
        min_length=1, max_length=3, description="1 to 3 short bubbles (PENNY_V3_BUILD.md D6)"
    )
    highlights: list[Highlight] = Field(default_factory=list)
    facts: list[ChatFact] = Field(default_factory=list)
    sources: list[ChatSource] = Field(default_factory=list)
    follow_up_question: str | None = Field(default=None, max_length=300)
    suggestions: list[str] = Field(
        default_factory=list,
        max_length=2,
        description="Follow-up chips, e.g. 'Next move', 'Summary'. Never a lone 'Yes'.",
    )
    confidence: float = Field(ge=0, le=1)
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=5)
    verified: bool = Field(description="True when every number passed the verifier; False means template summary")
    summary_available: bool = False
    links: list[Literal["next_move", "test_it", "why", "plan", "maths", "forecast"]] = Field(
        default_factory=list,
        max_length=3,
        description="In-app destinations, e.g. the out-of-scope reply links to the Next Move",
    )
    disclaimer: Literal[
        "Penny is AI and can make mistakes. Guidance only, not regulated financial advice. Check before big decisions."
    ] = "Penny is AI and can make mistakes. Guidance only, not regulated financial advice. Check before big decisions."


class ChatThreadSummary(_M):
    id: str
    title: str = Field(max_length=120)
    updated_at: str
    message_count: int = Field(ge=0)


class ChatThreadsResponse(_M):
    threads: list[ChatThreadSummary]


class ChatMessage(_M):
    id: str
    role: Literal["user", "penny"]
    created_at: str
    text: str | None = Field(default=None, description="User message text")
    reply_to: str | None = None
    response: ChatResponse | None = Field(default=None, description="Penny's answer group")
    replies: int = Field(default=0, ge=0, description="N Replies under a user bubble")


class ChatThread(_M):
    id: str
    title: str
    messages: list[ChatMessage]


# ---------- streaming (ADR 0031, perceived speed) ----------


class ToolStep(_M):
    """One REAL tool call in progress. Never invented."""

    tool: str
    label: str = Field(max_length=80, description="e.g. 'Checking Bank of England…', 'Replaying 2022…'")


class BubbleEvent(_M):
    bubble: ChatBubble
    highlights: list[Highlight] = Field(default_factory=list)


class ChatStreamEvent(_M):
    """One Server-Sent Event from POST /v1/chat/stream. Order: reaction, tool_step*, verifying?, bubble+, done."""

    type: Literal["reaction", "tool_step", "verifying", "bubble", "done", "error", "keepalive"]
    seq: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)
    reaction: Reaction | None = None
    step: ToolStep | None = None
    bubble: BubbleEvent | None = None
    response: ChatResponse | None = Field(default=None, description="Full verified response on 'done'")
    error_code: str | None = None


# ---------- demo trace (ADR 0075): judges see how Penny answers, step by step ----------


class TraceStep(_M):
    kind: Literal["scope", "tool_call", "tool_result", "draft", "verify", "rewrite", "final"]
    elapsed_ms: int = Field(ge=0)
    label: str = Field(max_length=120)
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Step details (scope decision and check mode, tool name and arguments, engine result before and "
        "after, draft bubbles, each number with where it matched and pass or fail). Never keys, tokens or prompts.",
    )


class ChatTrace(_M):
    question: str
    student: str | None = None
    steps: list[TraceStep]
    answer: ChatResponse
    total_ms: int = Field(ge=0)
