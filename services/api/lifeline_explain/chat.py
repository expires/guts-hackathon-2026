"""Ask Penny: a chat that answers only through engine tools (ADR 0031, 0033, 0034).

Flow per turn:
1. Build the prompt. Untrusted text (user message, history, merchant names, headlines) is fenced (ADR 0034).
2. Tool-use loop: at most 5 tool calls. Tool results go back as JSON; their string values are fenced.
3. Parse the final JSON answer, clean the bubbles (house style), apply the persona rules.
4. Verify every number against the union of tool facts from this turn (facts_table included).
   On failure: one rewrite. On a second failure: a template summary of the tool facts, verified=false.
5. Map each number to a fact id and a source id (highlights). Group sources.

`answer` never raises. Overall deadline: 2 x LLM_TIMEOUT_SECONDS.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
import unicodedata
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from pydantic_core import to_jsonable_python

from lifeline_contracts.chat import (
    BubbleEvent,
    ChatBubble,
    ChatFact,
    ChatRequest,
    ChatResponse,
    ChatSource,
    ChatStreamEvent,
    Highlight,
    Reaction,
    ToolCall,
    ToolStep,
)
from lifeline_contracts.domain import SourceRef
from lifeline_explain import prompts
from lifeline_explain.chat_llm import AnthropicChatLLM, ChatLLM, LLMStep, ToolUse
from lifeline_explain.chat_tools import (
    TOOL_NAMES,
    ChatToolContext,
    ChatTurn,
    ToolInputError,
    ToolOutput,
    ToolSourceLink,
    source_key,
)
from lifeline_explain.config import ExplainSettings, has_api_key, load_settings
from lifeline_explain.trade_off import TRADE_OFF_TOOLS, find_trade_offs, trade_off_facts, trade_off_sources
from lifeline_explain.verifier import Found, extract_numbers, fact_matches

log = logging.getLogger(__name__)

MAX_TOOL_CALLS = 5
MAX_STEPS = 9
MAX_BUBBLES = 4
MAX_SENTENCES = 3
HISTORY_TURNS = 10
REACTIONS: frozenset[str] = frozenset({"eyes", "brain", "thumbs", "tick", "question", "shrug"})
BubbleKind = Literal["answer", "caveat", "question", "general_knowledge"]
SourceGroup = Literal["your_data", "live_sources", "general_knowledge"]

# ---------- untrusted text (ADR 0034) ----------

_ZERO_WIDTH = frozenset({"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff", "\u00ad", "\u180e"})
# Keys whose string values are machine data (ids, enums, dates). Every other string in a tool result is fenced.
SAFE_KEYS = frozenset(
    {"id", "unit", "kind", "type", "status", "source", "series_id", "date", "start", "end", "deadline", "url",
     "option_id", "move_id", "currency", "period", "group", "category", "updated_at", "as_of", "next_decision"}
)  # fmt: skip


# V6 T2-F1: numbers lifted out of user or bank text are not facts. A `<tool>.text.<path>` fact is dropped when its
# path holds one of these keys, or when its value appears inside an untrusted string of the same tool result.
UNTRUSTED_TEXT_KEYS = frozenset(
    {"merchant", "merchants", "name", "names", "description", "payee", "reference", "counterparty", "subscription",
     "subscriptions", "bill", "bills", "headline", "standfirst", "statement", "note", "memo", "title"}
)  # fmt: skip


def _untrusted_numbers(value: Any, key: str | None = None, inside: bool = False) -> set[float]:
    """Numbers inside strings under untrusted keys (anywhere in a tool result)."""
    inside = inside or (key is not None and key.lower() in UNTRUSTED_TEXT_KEYS)
    if isinstance(value, str):
        return {n.value for n in extract_numbers(value)} if inside else set()
    if isinstance(value, dict):
        return set().union(*(_untrusted_numbers(v, str(k), inside) for k, v in value.items()), set())
    if isinstance(value, list):
        return set().union(*(_untrusted_numbers(v, key, inside) for v in value), set())
    return set()


def is_untrusted_text_fact(fact_id: str, tainted: set[float], value: float) -> bool:
    if ".text." not in fact_id:
        return False
    path = re.split(r"[.\[\]]", fact_id.split(".text.", 1)[1].lower())
    return any(p in UNTRUSTED_TEXT_KEYS for p in path) or abs(value) in tainted or value in tainted


def sanitize_untrusted(text: str, limit: int = 2000) -> str:
    """Make untrusted text safe to fence (V6 T2-F2).

    1. NFKC (fullwidth '＜' becomes '<'). 2. Drop control and format characters (Cc, Cf: zero-width, bidi,
    Unicode tag characters U+E0000-E007F), keeping newline and tab. 3. Replace every '<' with '‹', so no tag
    (spaced, split or otherwise) can open or close a fence."""
    out = unicodedata.normalize("NFKC", text)
    out = "".join(
        ch for ch in out if ch in "\n\t" or (unicodedata.category(ch) not in {"Cc", "Cf"} and ch not in _ZERO_WIDTH)
    )
    return out.replace("<", "\u2039")[:limit]


def fence(text: str, source: str) -> str:
    return f'<untrusted source="{source}">{sanitize_untrusted(text)}</untrusted>'


def fence_strings(value: Any, source: str, key: str | None = None) -> Any:
    """Return a copy of a JSON value with every non-safe string fenced."""
    if isinstance(value, str):
        return value if key in SAFE_KEYS else fence(value, source)
    if isinstance(value, dict):
        return {str(k): fence_strings(v, source, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [fence_strings(v, source, key) for v in value]
    return value


# ---------- house style ----------

_EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿️‍]")
_MD = re.compile(r"(\*\*|__|`|^#+\s*|^\s*[-*]\s+)", re.MULTILINE)
_SENT_SPLIT = re.compile(r"(?<=[.?])\s+(?=[A-Z£\"'(])")
_NFA = re.compile(r"not (financial|regulated|investment) advice", re.IGNORECASE)
_CHALLENGE = re.compile(
    r"\b(are you sure|you sure|really\?|that'?s (wrong|not right|incorrect)|is that (right|correct)|double[- ]check|"
    r"check again|i don'?t think so|that can'?t be right|that doesn'?t (look|seem) right)",
    re.IGNORECASE,
)


def _shingles(text: str, n: int = 6) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


_SYSTEM_SHINGLES = _shingles(prompts.PENNY_SYSTEM)


def leaks_system_prompt(text: str) -> bool:
    """True when a bubble repeats 6 or more consecutive words of the system prompt."""
    return bool(_shingles(text) & _SYSTEM_SHINGLES)


def is_challenge(message: str) -> bool:
    return bool(_CHALLENGE.search(message))


def clean_bubble(text: str) -> str:
    out = _MD.sub("", text)
    out = _EMOJI.sub("", out)
    out = re.sub(r"\s*\u2014\s*", ", ", out).replace("!", ".")
    out = re.sub(r"\s+", " ", out).strip()
    sentences = [s for s in _SENT_SPLIT.split(out) if s and not _NFA.search(s)]
    out = " ".join(sentences[:MAX_SENTENCES]).strip()
    if len(out) > 600:
        cut = out[:600]
        out = cut[: max(cut.rfind(". "), cut.rfind("? ")) + 1] or cut[:597] + "..."
    if out and out[0].islower():
        out = out[0].upper() + out[1:]
    return out


# ---------- per-turn state ----------

Emit = Callable[[str, dict[str, Any]], None]  # (event type, ChatStreamEvent fields)

STEP_LABELS: dict[str, str] = {
    "next_move": "Checking your next move\u2026",
    "test_move": "Replaying the test period\u2026",
    "finance_summary": "Reading your accounts\u2026",
    "spend_prediction": "Predicting your spending\u2026",
    "cash_flow_projection": "Projecting your cash\u2026",
    "life_replay": "Replaying your life\u2026",
    "event_choices": "Playing each choice forward\u2026",
    "news_search": "Checking the news\u2026",
    "rate_decision_dates": "Checking Bank of England\u2026",
    "facts_table": "Checking the official rules\u2026",
}


def step_label(ctx: ChatToolContext, name: str, args: Any) -> str:
    """Plain label for a real tool call. A ToolSet may refine it with `step_label(name, args)`."""
    custom = getattr(ctx.tools, "step_label", None)
    if callable(custom):
        try:
            label = custom(name, args if isinstance(args, dict) else {})
            if isinstance(label, str) and label:
                return label[:80]
        except Exception:  # noqa: S110 - a label is cosmetic
            pass
    return STEP_LABELS.get(name, "Working\u2026")


def _emit(state: TurnState, type_: str, **fields: Any) -> None:
    if state.emit is not None:
        with contextlib.suppress(Exception):  # streaming must never break the answer
            state.emit(type_, fields)


@dataclass
class TurnState:
    emit: Emit | None = None
    verifying_sent: bool = False
    tainted: set[float] = field(default_factory=set)  # numbers seen inside untrusted strings this turn
    calls: list[ToolCall] = field(default_factory=list)
    attempted: int = 0
    facts: list[ChatFact] = field(default_factory=list)
    sources: dict[str, ChatSource] = field(default_factory=dict)

    def add_source(self, tool: str, ref: SourceRef, link: ToolSourceLink | None) -> str:
        sid = source_key(ref)
        if sid in self.sources:
            return sid
        url = link.url if link else None
        if url is None and ref.series_id.startswith("https://"):
            url = ref.series_id[:500]  # facts table: series_id is the gov.uk URL
        self.sources[sid] = ChatSource(
            id=sid,
            group=source_group(tool, ref),
            label=source_label(ref)[:120],
            ref=ref,
            url=url,
            updated_at=link.updated_at if link else None,
        )
        return sid

    def add_fact(self, f: ChatFact, source_id: str | None, call_no: int) -> str:
        """Fact ids stay as the tool gave them. A rerun with a different value gets a '~N' suffix."""
        for existing in self.facts:
            if existing.id == f.id:
                if existing.value == f.value:
                    return existing.id
                fid = f"{f.id}~{call_no}"
                break
        else:
            fid = f.id
        self.facts.append(f.model_copy(update={"id": fid, "source_id": source_id}))
        return fid


def source_group(tool: str, ref: SourceRef) -> SourceGroup:
    src = ref.source.lower()
    if tool == "facts_table" or src in {"facts_table", "gov.uk", "govuk"}:
        return "general_knowledge"
    if src.startswith(("bank", "user", "statement", "profile", "finance", "sim", "store")):
        return "your_data"
    return "live_sources"


def source_label(ref: SourceRef) -> str:
    src = ref.source.lower()
    if src.startswith("bank"):
        return "Your bank data" + (" (sample)" if ref.status == "mock" else "")
    if src in {"govuk", "gov.uk", "facts_table"}:
        return "GOV.UK" + (f", {ref.note}" if ref.note else "")
    if src == "guardian":
        return "The Guardian"
    return f"{ref.source}: {ref.series_id}" + (f" ({ref.note})" if ref.note else "")


# ---------- formatting for the template summary ----------


def format_fact(f: ChatFact) -> str:
    v = f.value
    if f.unit in {"gbp", "gbp_per_month", "gbp_per_year"}:
        money = f"£{abs(v):,.2f}" if v != int(v) else f"£{abs(int(v)):,}"
        sign = "minus " if v < 0 else ""
        tail = {"gbp": "", "gbp_per_month": " a month", "gbp_per_year": " a year"}[f.unit]
        return f"{sign}{money}{tail}"
    if f.unit == "percent":
        return f"{round(v, 2):g}%"
    if f.unit == "date_year":
        return str(int(v))
    num = f"{round(v, 1):g}"
    return {"months": f"{num} months", "years": f"{num} years"}.get(f.unit, num)


# ---------- service ----------


@dataclass
class Draft:
    reaction: Reaction
    bubbles: list[tuple[BubbleKind, str]]
    summary_available: bool = False
    out_of_scope: bool = False


class Penny:
    def __init__(self, llm: ChatLLM | None = None, settings: ExplainSettings | None = None) -> None:
        self.settings = settings or load_settings()
        self.llm = llm

    @classmethod
    def from_env(cls) -> Penny:
        settings = load_settings()
        llm: ChatLLM | None = None
        if settings.enabled and has_api_key():
            try:
                llm = AnthropicChatLLM(settings)
            except Exception as exc:
                log.warning("penny: LLM client unavailable (%s)", type(exc).__name__)
        return cls(llm=llm, settings=settings)

    async def answer(self, request: ChatRequest, ctx: ChatToolContext, *, emit: Emit | None = None) -> ChatResponse:
        """One answer. `emit(type, fields)` receives progress events (tool_step, verifying, error) for streaming."""
        ids = self._ids(request, ctx)
        state = TurnState(emit=emit)
        reason = "llm_error"
        if out_of_scope_rule(request.message):
            # Deterministic, before any LLM call (works with the LLM off).
            return self._build(ids, Draft("shrug", [], out_of_scope=True), state, verified=True)
        try:
            async with asyncio.timeout(2 * self.settings.timeout_seconds):
                if self.llm is None:
                    return await self._template(ids, state, ctx, reason="llm_unavailable")
                return await self._loop(request, ctx, state, ids)
        except TimeoutError:
            log.info("penny: overall timeout; template")
            reason = "timeout"
        except Exception as exc:
            log.warning("penny: error (%s); template", type(exc).__name__)
        try:
            return await asyncio.wait_for(self._template(ids, state, ctx, reason=reason), timeout=5)
        except Exception:
            _emit(state, "error", error_code=reason)
            return self._build(ids, Draft("question", [("answer", NO_ANSWER_TEXT)]), state, verified=False)

    async def answer_stream(self, request: ChatRequest, ctx: ChatToolContext) -> AsyncIterator[ChatStreamEvent]:
        """Server-Sent Events for POST /v1/chat/stream (ADR 0031 amendment).

        Order: reaction (before any LLM call), tool_step per real tool call, verifying, bubble per verified
        bubble with its highlights, done with the same ChatResponse as `answer`.
        The template summary (LLM off, timeout, verifier failure) streams the same way: its bubbles are built from
        tool facts and checked before they are sent. `error` is sent only when not even the template can be
        built; then `done` follows with no bubble events."""
        t0 = time.monotonic()
        seq = 0

        def event(type_: str, **fields: Any) -> ChatStreamEvent:
            nonlocal seq
            e = ChatStreamEvent(type=cast(Any, type_), seq=seq, elapsed_ms=int((time.monotonic() - t0) * 1000),
                                **fields)  # fmt: skip
            seq += 1
            return e

        yield event("reaction", reaction=quick_reaction(request))
        queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()
        task = asyncio.create_task(self.answer(request, ctx, emit=lambda t, f: queue.put_nowait((t, f))))
        task.add_done_callback(lambda _: queue.put_nowait(None))
        saw_error = saw_verifying = False
        try:
            while (item := await queue.get()) is not None:
                type_, fields = item
                if type_ == "tool_step":
                    yield event("tool_step", step=ToolStep(tool=fields["tool"], label=fields["label"]))
                elif type_ == "verifying":
                    saw_verifying = True
                    yield event("verifying")
                elif type_ == "error":
                    saw_error = True
                    yield event("error", error_code=str(fields.get("error_code") or "error")[:40])
            resp = task.result()
        finally:
            if not task.done():
                task.cancel()
        if not saw_error:
            if not saw_verifying and resp.highlights:
                yield event("verifying")
            sent = 0
            for b in resp.bubbles:
                if not bubble_verified(b, resp):
                    continue  # never emit an unverified bubble
                hl = [h for h in resp.highlights if h.bubble_id == b.id]
                yield event("bubble", bubble=BubbleEvent(bubble=b, highlights=hl))
                sent += 1
            if sent == 0:
                yield event("error", error_code="unverified")
        yield event("done", response=resp)

    # ----- loop -----

    async def _loop(
        self, request: ChatRequest, ctx: ChatToolContext, state: TurnState, ids: dict[str, str]
    ) -> ChatResponse:
        assert self.llm is not None
        tool_specs = ctx.tools.specs()
        tools = [{"name": s.name, "description": s.description, "input_schema": s.input_schema} for s in tool_specs]
        messages = build_messages(request, ctx)
        challenged = is_challenge(request.message)
        nudged = rewritten = False
        reason = "max_steps"
        for _ in range(MAX_STEPS):
            step = await self.llm.step(prompts.PENNY_SYSTEM, messages, tools, prompts.PENNY_ANSWER_SCHEMA)
            if step.tool_uses:
                messages.append({"role": "assistant", "content": _content(step)})
                results = [await self._run_tool(tu, ctx, state) for tu in step.tool_uses]
                messages.append({"role": "user", "content": results})
                continue
            if step.stop_reason in {"refusal", "max_tokens"}:
                log.info("penny: stop_reason %s; template", step.stop_reason)
                reason = str(step.stop_reason)
                break
            draft = parse_draft(step.text)
            if draft is None:
                log.info("penny: unparseable final answer; template")
                reason = "unparseable"
                break
            if challenged and not state.calls and tools and not nudged and not draft.out_of_scope:
                nudged = True
                messages.append({"role": "assistant", "content": _content(step)})
                messages.append({"role": "user", "content": prompts.PENNY_CHALLENGE_NUDGE})
                continue
            if not draft.out_of_scope and any(leaks_system_prompt(t) for _, t in draft.bubbles):
                log.info("penny: answer repeated the system prompt; fixed reply")
                draft = Draft("shrug", [("answer", prompts.NO_INSTRUCTIONS_TEXT)], out_of_scope=True)
                return self._build(ids, draft, state, verified=True, fixed_text=prompts.NO_INSTRUCTIONS_TEXT)
            if draft.out_of_scope:
                return self._build(ids, draft, state, verified=True)  # fixed reply, no numbers
            draft = apply_rules(draft, challenged)
            if not state.verifying_sent:
                state.verifying_sent = True
                _emit(state, "verifying")
            bad = unverified_numbers(draft, state.facts)
            if not bad:
                return self._build(ids, draft, state, verified=True)
            log.info("penny: verifier rejected %s", bad)
            if rewritten:
                reason = "unverified"
                break
            rewritten = True
            messages.append({"role": "assistant", "content": _content(step)})
            messages.append({"role": "user", "content": prompts.PENNY_REWRITE.format(bad=", ".join(bad))})
        return await self._template(ids, state, ctx, reason=reason)

    async def _run_tool(self, tu: ToolUse, ctx: ChatToolContext, state: TurnState) -> dict[str, Any]:
        def err(msg: str) -> dict[str, Any]:
            return {"type": "tool_result", "tool_use_id": tu.id, "content": msg, "is_error": True}

        if state.attempted >= MAX_TOOL_CALLS:
            return err("Tool limit reached. Answer now with the facts you have.")
        if tu.name not in TOOL_NAMES:
            return err(f"Unknown tool: {tu.name[:40]}")
        state.attempted += 1
        _emit(state, "tool_step", tool=tu.name, label=step_label(ctx, tu.name, tu.input))
        out, ok, msg, ms = await self._call_tool(ctx, tu.name, tu.input)
        state.calls.append(ToolCall(name=cast(Any, tu.name), ok=ok, duration_ms=ms))
        if out is None:
            return err(msg)
        ctx.outputs.append((tu.name, out))
        payload = self._register(tu.name, out, state)
        return {"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(payload, ensure_ascii=False)}

    async def _call_tool(self, ctx: ChatToolContext, name: str, args: Any) -> tuple[ToolOutput | None, bool, str, int]:
        start = time.monotonic()
        try:
            if not isinstance(args, dict) or len(json.dumps(args, default=str)) > 2000:
                raise ToolInputError("Invalid input")
            out = ToolOutput.of(await ctx.tools.call(name, args))
            return out, True, "", int((time.monotonic() - start) * 1000)
        except ToolInputError as exc:
            return None, False, str(exc)[:200], int((time.monotonic() - start) * 1000)
        except Exception as exc:
            log.info("penny: tool %s failed (%s)", name, type(exc).__name__)
            return None, False, "Tool failed. Say you could not check this.", int((time.monotonic() - start) * 1000)

    def _register(self, tool: str, out: ToolOutput, state: TurnState) -> dict[str, Any]:
        result = to_jsonable_python(out.result)
        out_facts = list(out.facts)
        out_sources = list(out.sources)
        if tool in TRADE_OFF_TOOLS:
            # ADR 0042: the engine's trade-off numbers become facts (tf_<move_id>_<key>) Penny may quote.
            for move_id, tf in find_trade_offs(result):
                out_facts += trade_off_facts(move_id, tf)
                out_sources += trade_off_sources(tf)
        source_ids = [
            state.add_source(tool, ref, out.links[i] if i < len(out.links) else None)
            for i, ref in enumerate(out_sources)
        ]
        call_no = len(state.calls)
        facts = []
        state.tainted |= {abs(v) for v in _untrusted_numbers(result)}
        # Drop earlier text facts that a later result shows came from untrusted text.
        state.facts = [x for x in state.facts if not is_untrusted_text_fact(x.id, state.tainted, x.value)]
        for f in out_facts:
            if is_untrusted_text_fact(f.id, state.tainted, f.value):
                log.info("penny: dropped fact %s (number from untrusted text)", f.id[:80])
                continue
            sid = f.source_id if f.source_id in source_ids else (source_ids[0] if source_ids else None)
            fid = state.add_fact(f, sid, call_no)
            facts.append({"id": fid, "value": f.value, "unit": f.unit, "label": fence(f.label, tool)})
        return {
            "result": fence_strings(result, tool),
            "facts": facts,
            "sources": [{"id": sid, "label": state.sources[sid].label} for sid in source_ids],
        }

    # ----- template (verified=false) -----

    async def _template(self, ids: dict[str, str], state: TurnState, ctx: ChatToolContext, reason: str) -> ChatResponse:
        if not state.facts and state.attempted < MAX_TOOL_CALLS:
            # LLM down or no usable answer before any tool ran: show the engine's one answer.
            state.attempted += 1
            _emit(state, "tool_step", tool="next_move", label=step_label(ctx, "next_move", {}))
            out, ok, _, ms = await self._call_tool(ctx, "next_move", {})
            state.calls.append(ToolCall(name="next_move", ok=ok, duration_ms=ms))
            if out is not None:
                ctx.outputs.append(("next_move", out))
                self._register("next_move", out, state)
        lines: list[str] = []
        for f in state.facts:
            if ".text." in f.id:
                continue  # numbers W2 lifted out of text fields; the template lists the main facts only
            label = sanitize_untrusted(f.label, 100).rstrip(".")
            line = f"{label[:1].upper()}{label[1:]}: {format_fact(f)}."
            if not unverified_numbers(Draft("eyes", [("answer", line)]), state.facts):
                lines.append(line)
        if not lines:
            _emit(state, "error", error_code=reason)  # not even a template summary
            return self._build(ids, Draft("question", [("answer", NO_ANSWER_TEXT)]), state, verified=False)
        first = [TEMPLATE_INTRO, *lines[:2]]
        bubbles: list[tuple[BubbleKind, str]] = [("answer", " ".join(first))]
        if lines[2:]:
            bubbles.append(("answer", " ".join(lines[2:5])))
        log.info("penny: template summary (%s)", reason)
        return self._build(ids, Draft("question", bubbles, summary_available=len(lines) > 5), state, verified=False)

    # ----- response -----

    def _ids(self, request: ChatRequest, ctx: ChatToolContext) -> dict[str, str]:
        return {
            "thread_id": ctx.thread_id or request.thread_id or f"t_{uuid.uuid4().hex[:16]}",
            "message_id": f"m_{uuid.uuid4().hex[:16]}",
            "reply_to": ctx.user_message_id or request.reply_to or f"u_{uuid.uuid4().hex[:16]}",
        }

    def _build(
        self, ids: dict[str, str], draft: Draft, state: TurnState, verified: bool, fixed_text: str | None = None
    ) -> ChatResponse:
        if draft.out_of_scope:
            draft = Draft("shrug", [("answer", fixed_text or prompts.OUT_OF_SCOPE_TEXT)], out_of_scope=True)
        bubbles = [
            ChatBubble(id=f"{ids['message_id']}-b{i + 1}", kind=kind, text=text)
            for i, (kind, text) in enumerate(draft.bubbles[:MAX_BUBBLES])
        ]
        highlights = make_highlights(bubbles, state)
        used = {h.fact_id for h in highlights}
        sources = [] if draft.out_of_scope else list(state.sources.values())
        if any(b.kind == "general_knowledge" for b in bubbles):
            sources.append(ChatSource(id="gk", group="general_knowledge", label="General knowledge, no numbers"))
        question = next((b.text for b in bubbles if b.kind == "question"), None)
        reaction: Reaction = draft.reaction
        if draft.out_of_scope:
            reaction = "shrug"
        elif not verified:
            reaction = "question"
        return ChatResponse(
            thread_id=ids["thread_id"],
            message_id=ids["message_id"],
            reply_to=ids["reply_to"],
            reaction=reaction,
            bubbles=bubbles,
            highlights=highlights,
            facts=[f for f in state.facts if f.id in used],
            sources=sources,
            follow_up_question=question[:300] if question else None,
            confidence=confidence(draft, state, verified, bubbles),
            tool_calls=state.calls[:MAX_TOOL_CALLS],
            verified=verified,
            summary_available=draft.summary_available,
            links=links_for(draft, state, verified),
        )


NO_ANSWER_TEXT = "I cannot check that right now. Your Next Move on the Money tab has the latest answer."
TEMPLATE_INTRO = "Here are the numbers I found."


def _content(step: LLMStep) -> Any:
    return step.content if step.content is not None else [{"type": "text", "text": step.text}]


# ---------- prompt building ----------


def build_messages(request: ChatRequest, ctx: ChatToolContext) -> list[dict[str, Any]]:
    turns: list[tuple[str, str]] = []
    for t in list(ctx.history)[-HISTORY_TURNS:]:
        turns.append(_turn(t))
    parts = []
    if ctx.known:
        parts.append("KNOWN (from the app): " + fence(json.dumps(ctx.known, ensure_ascii=False), "profile"))
    rc = ctx.request_context or request.context
    if rc is not None:
        parts.append("CONTEXT: " + json.dumps(rc.model_dump(exclude_none=True)))
    parts.append("USER MESSAGE: " + fence(request.message, "user"))
    turns.append(("user", "\n".join(parts)))
    merged: list[dict[str, Any]] = []
    for role, text in turns:
        if not merged and role != "user":
            continue
        if merged and merged[-1]["role"] == role:
            merged[-1]["content"] += "\n\n" + text
        else:
            merged.append({"role": role, "content": text})
    return merged


def _turn(t: ChatTurn) -> tuple[str, str]:
    if t.role == "user":
        return "user", "EARLIER USER MESSAGE: " + fence(t.text, "user")
    tools = f" (tools used: {', '.join(n for n in t.tools_used if n in TOOL_NAMES)})" if t.tools_used else ""
    return "assistant", sanitize_untrusted(t.text) + tools


# ---------- parsing and rules ----------


def parse_draft(text: str) -> Draft | None:
    try:
        data = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
        except ValueError:
            return None
    if not isinstance(data, dict):
        return None
    reaction = data.get("reaction")
    bubbles: list[tuple[BubbleKind, str]] = []
    for b in data.get("bubbles") or []:
        if not isinstance(b, dict):
            continue
        kind = b.get("kind")
        if kind not in {"answer", "caveat", "question", "general_knowledge"}:
            kind = "answer"
        text_ = clean_bubble(str(b.get("text") or ""))
        if text_:
            bubbles.append((cast(BubbleKind, kind), text_))
    out_of_scope = bool(data.get("out_of_scope"))
    if not bubbles and not out_of_scope:
        return None
    return Draft(
        reaction=cast(Reaction, reaction if reaction in REACTIONS else "eyes"),
        bubbles=bubbles,
        summary_available=bool(data.get("summary_available")),
        out_of_scope=out_of_scope,
    )


def apply_rules(draft: Draft, challenged: bool) -> Draft:
    if draft.out_of_scope:
        return draft
    bubbles: list[tuple[BubbleKind, str]] = []
    seen_question = False
    for kind, text in draft.bubbles:
        if kind == "question":
            if seen_question:
                continue  # at most one follow-up question
            seen_question = True
        bubbles.append((kind, text))
    summary = draft.summary_available or len(bubbles) > MAX_BUBBLES
    if len(bubbles) > MAX_BUBBLES:
        # Keep the question (if any) as the last bubble.
        q = [b for b in bubbles if b[0] == "question"]
        rest = [b for b in bubbles if b[0] != "question"]
        bubbles = rest[: MAX_BUBBLES - len(q)] + q
    if challenged and bubbles and bubbles[0][0] == "answer" and not bubbles[0][1].lower().startswith("fair"):
        bubbles[0] = ("answer", "Fair question. " + bubbles[0][1])
        bubbles[0] = ("answer", clean_bubble(bubbles[0][1]))
    reaction = draft.reaction
    if reaction == "shrug":
        reaction = "question"
    return Draft(reaction, bubbles, summary, False)


def unverified_numbers(draft: Draft, facts: list[ChatFact]) -> list[str]:
    """Every number must match a fact value in a compatible unit. General-knowledge bubbles hold no number."""
    bad: list[str] = []
    for kind, text in draft.bubbles:
        for found in extract_numbers(text):
            if kind == "general_knowledge" or not any(fact_matches(found, f.value, f.unit) for f in facts):
                bad.append(found.raw)
    return bad


def bubble_verified(b: ChatBubble, resp: ChatResponse) -> bool:
    """Final per-bubble check before a stream emits it: every number matches a fact in the response."""
    nums = extract_numbers(b.text)
    if b.kind == "general_knowledge":
        return not nums
    return all(any(fact_matches(n, f.value, f.unit) for f in resp.facts) for n in nums)


def _match(found: Found, facts: list[ChatFact]) -> ChatFact | None:
    ok = [f for f in facts if fact_matches(found, f.value, f.unit)]
    exact = [f for f in ok if abs(f.value) == found.value]
    return exact[0] if exact else (ok[0] if ok else None)


def make_highlights(bubbles: list[ChatBubble], state: TurnState) -> list[Highlight]:
    out: list[Highlight] = []
    for b in bubbles:
        for found in extract_numbers(b.text):
            fact = _match(found, state.facts)
            if fact is None:
                continue
            start = found.start
            while start > 0 and b.text[start - 1] in "£-":
                start -= 1
            out.append(
                Highlight(
                    bubble_id=b.id,
                    start=start,
                    length=found.end - start,
                    fact_id=fact.id,
                    source_id=fact.source_id,
                )
            )
    return out


def links_for(draft: Draft, state: TurnState, verified: bool) -> list[Any]:
    """In-app destinations: out of scope and unverified answers point to the Next Move; a next_move answer
    offers Test it; a test_move answer offers Do this (plan)."""
    if draft.out_of_scope or not verified:
        return ["next_move"]
    ok = {c.name for c in state.calls if c.ok}
    links: list[Any] = []
    if "next_move" in ok:
        links.append("test_it")
    if "test_move" in ok:
        links.append("plan")
    return links[:3]


def confidence(draft: Draft, state: TurnState, verified: bool, bubbles: list[ChatBubble]) -> float:
    if draft.out_of_scope:
        return 1.0
    if not verified:
        return 0.3
    conf = [
        f.value / 100 if f.unit == "percent" else f.value
        for f in state.facts
        if "confidence" in f.id and (0 <= f.value <= 1 or (f.unit == "percent" and 0 <= f.value <= 100))
    ]
    if conf:
        return round(conf[0], 2)
    if any(c.ok for c in state.calls):
        return 0.9
    if any(b.kind == "question" for b in bubbles) and len(bubbles) == 1:
        return 0.5
    return 0.6


_OOS_RULES = [
    # Stock, fund and crypto picks.
    re.compile(
        r"\b(which|what|best|top|good|hot)\b[^.?]*\b(shares?|stocks?|equit(y|ies)|crypto(currency|currencies)?|"
        r"bitcoin|ethereum|dogecoin|coins?|tokens?|etfs?|penny stocks?|meme stocks?)\b[^.?]*"
        r"\b(buy|invest|pick|go up|moon|own)\b"
    ),
    re.compile(
        r"\bshould i (buy|sell|short|invest in)\b[^.?]*\b(shares?|stocks?|crypto|bitcoin|ethereum|dogecoin|coins?|"
        r"tesla|apple|nvidia|amazon|options|etfs?)\b"
    ),
    re.compile(r"\b(stock tips?|share tips?|price target|day trad(e|ing)|which crypto|to the moon)\b"),
    # Regulated advice.
    re.compile(
        r"\b(pension transfer|transfer my pension|defined benefit transfer|tax return|self[- ]assessment return|"
        r"legal advice|lawyer|solicitor|sue (my|the|him|her|them)|probate|power of attorney)\b"
    ),
    # Unrelated topics.
    re.compile(
        r"\b(tell me a joke|a joke|write (me )?a (poem|song|story)|recipe|capital of|football|homework|"
        r"write (me )?(some )?code|medical advice|diagnos(e|is))\b"
    ),
]


def out_of_scope_rule(message: str) -> bool:
    """Deterministic out-of-scope check (stock picks, regulated advice, unrelated topics), before any LLM call."""
    msg = unicodedata.normalize("NFKC", message).lower()
    return any(r.search(msg) for r in _OOS_RULES)


def quick_reaction(request: ChatRequest) -> Reaction:
    """A cheap first reaction for the UI before the answer arrives (ADR 0031: within 1 s). Heuristic only."""
    if out_of_scope_rule(request.message):
        return "shrug"
    msg = request.message.lower()
    if re.search(r"\b(what if|replay|test|project|forecast|lose my job|next move|should i)\b", msg):
        return "brain"
    return "eyes"


# ---------- module API ----------

_penny: Penny | None = None


def get_penny() -> Penny:
    global _penny
    if _penny is None:
        _penny = Penny.from_env()
    return _penny


def set_penny(penny: Penny | None) -> None:
    global _penny
    _penny = penny


async def answer(request: ChatRequest, ctx: ChatToolContext) -> ChatResponse:
    """Answer one chat message. Never raises. See module docstring."""
    return await get_penny().answer(request, ctx)


def answer_stream(request: ChatRequest, ctx: ChatToolContext) -> AsyncIterator[ChatStreamEvent]:
    """Stream one answer as ChatStreamEvents (ADR 0031 amendment). The last event is always 'done'."""
    return get_penny().answer_stream(request, ctx)
