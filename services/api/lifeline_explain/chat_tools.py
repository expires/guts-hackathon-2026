"""Tool seam for Ask Penny (ADR 0031, 0033).

W2 builds the engine tools (`lifeline_engine/tools/`). W4 binds them to the signed-in user and passes a
`ToolSet` in `ChatToolContext`. This module defines only the shapes the chat loop needs, plus a small adapter
(`FunctionToolSet`) that turns typed functions into a `ToolSet`.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lifeline_contracts.chat import ChatContext, ChatFact, ToolCall
from lifeline_contracts.domain import SourceRef

ToolName = Literal[
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
]
TOOL_NAMES: frozenset[str] = frozenset(get_args(ToolName))
assert frozenset(get_args(ToolCall.model_fields["name"].annotation)) == TOOL_NAMES


def source_key(ref: SourceRef) -> str:
    """Same as lifeline_engine.tools.source_id: 'source:series_id'. Used as ChatSource.id and ChatFact.source_id."""
    return f"{ref.source}:{ref.series_id}"


class ToolSourceLink(BaseModel):
    """Optional extra data for a source: a public URL (facts table: gov.uk) and an 'as of' date."""

    model_config = ConfigDict(extra="ignore")

    url: str | None = Field(default=None, max_length=500)
    updated_at: str | None = None


class ToolOutput(BaseModel):
    """Every tool returns {result, facts, sources} (ADR 0033), the shape of lifeline_engine.tools.ToolResult.
    `result` must be JSON-serialisable. A fact's `source_id` is `source_key(ref)` of one of `sources`;
    when it is None or unknown, the fact belongs to the tool's first source.
    `raw` keeps the original return value (e.g. ToolResult with `lives`) for the caller; never sent to the model."""

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    result: Any = None
    facts: list[ChatFact] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    links: list[ToolSourceLink | None] = Field(default_factory=list, description="Aligned with `sources`")
    raw: Any = Field(default=None, exclude=True)

    @classmethod
    def of(cls, value: Any) -> ToolOutput:
        """Accept a ToolOutput, a lifeline_engine ToolResult, or a dict with the same fields."""
        if isinstance(value, ToolOutput):
            return value
        if isinstance(value, BaseModel):
            return cls(
                result=getattr(value, "result", None),
                facts=list(getattr(value, "facts", [])),
                sources=list(getattr(value, "sources", [])),
                raw=value,
            )
        out = cls.model_validate(value)
        out.raw = value
        return out


class ToolSpec(BaseModel):
    name: ToolName
    description: str
    input_schema: dict[str, Any]


class ToolInputError(Exception):
    """The arguments failed validation. The message is safe to show to the model."""


class ToolSet(Protocol):
    def specs(self) -> list[ToolSpec]: ...

    async def call(self, name: str, args: dict[str, Any]) -> ToolOutput:
        """Validate `args`, run the tool for the bound user, return its output.
        Raise ToolInputError for bad input; any other exception counts as a tool failure."""
        ...


@dataclass(frozen=True)
class ChatTurn:
    """One earlier message in the thread. Penny turns carry the tools she used, for 'are you sure?'."""

    role: Literal["user", "penny"]
    text: str
    tools_used: tuple[str, ...] = ()


@dataclass
class ChatToolContext:
    """Everything `answer` needs besides the request. W4 builds it per request.

    `tools`: usually `lifeline_explain.chat_engine_tools.EngineToolSet` (snapshot, macro, today, seed, stored
    NextMoveResponse, news and rate callables, life and event for event_choices).
    After `answer` returns, `outputs` holds (tool name, ToolOutput) for every successful call this turn.
    `ToolOutput.raw` is the original engine ToolResult; store its `lives` (test_move, life_replay)."""

    tools: ToolSet
    thread_id: str | None = None
    user_message_id: str | None = None
    history: Sequence[ChatTurn] = ()
    known: dict[str, str] = field(default_factory=dict)  # what the app already knows, e.g. {"name": "Sam"}
    request_context: ChatContext | None = None
    outputs: list[tuple[str, ToolOutput]] = field(default_factory=list)


# ---------- adapter ----------

ToolFn = Callable[[Any], "ToolOutput | Awaitable[ToolOutput]"]


@dataclass(frozen=True)
class FunctionTool:
    name: ToolName
    description: str
    input_model: type[BaseModel]
    fn: ToolFn


class FunctionToolSet:
    """A ToolSet from typed functions. Input is validated with the tool's Pydantic model (ADR 0034)."""

    def __init__(self, tools: Sequence[FunctionTool]) -> None:
        self._tools: dict[str, FunctionTool] = {t.name: t for t in tools}

    def specs(self) -> list[ToolSpec]:
        out = []
        for t in self._tools.values():
            schema = t.input_model.model_json_schema()
            schema.pop("title", None)
            out.append(ToolSpec(name=t.name, description=t.description, input_schema=schema))
        return out

    async def call(self, name: str, args: dict[str, Any]) -> ToolOutput:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolInputError(f"Unknown tool: {name}")
        try:
            parsed = tool.input_model.model_validate(args)
        except ValidationError as exc:
            fields = ", ".join(".".join(str(p) for p in e["loc"]) or "input" for e in exc.errors())
            raise ToolInputError(f"Invalid input: {fields}") from None
        out = tool.fn(parsed)
        if inspect.isawaitable(out):
            out = await out
        return ToolOutput.of(out)
