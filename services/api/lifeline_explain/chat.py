"""Ask Penny (ADR 0031, 0033, 0034, 0051): one chat, two answer modes.

Flow per turn:
0. Fixed replies before any LLM call: distress (kind reply and support contacts), stock picks and regulated
   advice (polite refusal).
1. Build the prompt. Untrusted text (user message, history, statement text, headlines) is fenced (ADR 0034).
   The system prompt is static, so the API caches it.
2. Tool-use loop: at most 5 app tool calls, run in parallel within one model step, plus Anthropic's server
   web search. Tool results go back as JSON; their string values are fenced.
3. Parse the final JSON answer, clean the bubbles (house style, at most 2), keep at most 2 suggestion chips.
4. Mode:
   - "checked": an app tool ran. Every number must match a tool fact from this turn. On failure: one rewrite,
     then a template summary of the tool facts (verified=false).
   - "general": no app tool ran. The answer must not state the user's own numbers (personal facts). If it does,
     Penny retries once with an app tool; a second failure gives the template.
5. Highlights map money and rate numbers to a fact id and a source id. Sources use human names.

`answer` never raises. Overall deadline: 2 x LLM_TIMEOUT_SECONDS. With the LLM down: "Penny is unavailable".
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import logging
import re
import time
import unicodedata
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field, replace
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
from lifeline_explain import official, prompts
from lifeline_explain.chat_llm import WEB_SEARCH_TOOL, AnthropicChatLLM, ChatLLM, LLMStep, ToolUse
from lifeline_explain.chat_tools import (
    CLIENT_TOOL_NAMES,
    CONTRACT_TOOL_NAMES,
    TOOL_NAMES,
    ChatToolContext,
    ChatTurn,
    ToolInputError,
    ToolOutput,
    ToolSourceLink,
    source_key,
)
from lifeline_explain.config import ExplainSettings, has_api_key, load_settings
from lifeline_explain.source_names import source_label
from lifeline_explain.trade_off import TRADE_OFF_TOOLS, find_trade_offs, trade_off_facts, trade_off_sources
from lifeline_explain.verifier import Found, extract_numbers, fact_matches

log = logging.getLogger(__name__)

MAX_TOOL_CALLS = 5
MAX_STEPS = 9
MAX_BUBBLES = 2  # ADR 0051: usually one bubble, two at most
MAX_SENTENCES = 3
MAX_SUGGESTIONS = 2
HISTORY_TURNS = 10
KEEPALIVE_SECONDS = 2.0
PRELOAD_SECONDS = 1.0
HIGHLIGHT_UNITS = frozenset({"gbp", "gbp_per_month", "gbp_per_year", "percent"})  # money and rates only
PERSONAL_UNITS = frozenset({"gbp", "gbp_per_month", "gbp_per_year"})
ChatMode = Literal["checked", "general"]
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


_TRAILING_ZERO_PCT = re.compile(r"(?<![\d.])(\d+)\.0+(?=\s*(%|per ?cent))")


def tidy_numbers(text: str) -> str:
    """'25.0%' -> '25%', '9.00 per cent' -> '9 per cent'. '4.5%' stays (V4 advisory)."""
    return _TRAILING_ZERO_PCT.sub(r"\1", text)


def clean_bubble(text: str) -> str:
    out = tidy_numbers(_MD.sub("", text))
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
    "boe_rates": "Checking Bank of England rates\u2026",
    "user_balance": "Checking your balance\u2026",
    "habit_score": "Checking your habits\u2026",
    "inflation": "Checking inflation\u2026",
    "fx_convert": "Checking exchange rates\u2026",
    "web_search": "Searching the web\u2026",
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
    web_sources: dict[str, ChatSource] = field(default_factory=dict)
    rules: bool = False  # ADR 0058: a rules question; only official sources count
    preloaded: list[tuple[str, ToolOutput, ToolCall]] = field(default_factory=list)  # speed: facts in request 1
    preloaded_ids: set[str] = field(default_factory=set)
    personal: list[ChatFact] = field(default_factory=list)  # the user's own money facts (general-mode block)
    committed: tuple[BubbleKind, str, ChatMode] | None = None  # bubble 1 already streamed (speed, V1)
    testable: bool = False  # the user's top move can be replayed (Test it)
    source_tools: dict[str, set[str]] = field(default_factory=dict)  # source id -> tools that returned it
    fact_tool: dict[str, str] = field(default_factory=dict)  # fact id -> tool that returned it

    def app_tool_used(self) -> bool:
        return any(c.ok and c.name in CLIENT_TOOL_NAMES for c in self.calls)

    def add_web(self, url: str, title: str, text: str = "") -> None:
        """A web page the model saw. Rules questions (ADR 0058): only official pages count, and numbers in their
        cited text become facts ('web.N') that Penny may quote."""
        if self.rules and not official.is_official_url(url):
            return  # a non-official result is ignored
        if url not in self.web_sources:
            if len(self.web_sources) >= 5:
                return
            clean_title = sanitize_untrusted(title, 100).strip()
            if self.rules:
                label = official.official_label(url, f"retrieved {official.nice_date(official.today())}", clean_title)
            else:
                label = f"{clean_title or url.split('/')[2]} \u00b7 web"
            when = official.today().isoformat() if self.rules else None
            self.web_sources[url] = ChatSource(
                id=f"web:{len(self.web_sources) + 1}", group="general_knowledge", label=label[:120], url=url,
                updated_at=when,
            )  # fmt: skip
        if self.rules and text:
            start = sum(1 for f in self.facts if f.id.startswith("web.")) + 1
            sid = self.web_sources[url].id
            self.facts += official.web_facts(url, sanitize_untrusted(text, 1000), sid, start)

    def has_official_source(self) -> bool:
        return (
            bool(self.web_sources)
            or any(f.id.startswith("rule.") for f in self.facts)
            or any(s.url and official.is_official_url(s.url) for s in self.sources.values())
        )

    def add_source(self, tool: str, ref: SourceRef, link: ToolSourceLink | None) -> str:
        sid = source_key(ref)
        self.source_tools.setdefault(sid, set()).add(tool)
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
    suggestions: list[str] = field(default_factory=list)


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
        if distress_rule(request.message):
            # Deterministic, before any LLM call: a kind reply with support contacts (ADR 0051).
            return self._build(ids, distress_draft(), state, verified=True, mode="general")
        if out_of_scope_rule(request.message):
            return self._build(ids, Draft("shrug", [], out_of_scope=True), state, verified=True, mode="general")
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
            return self._unavailable(ids, state)

    async def answer_stream(self, request: ChatRequest, ctx: ChatToolContext) -> AsyncIterator[ChatStreamEvent]:
        """Server-Sent Events for POST /v1/chat/stream (ADR 0031 amendment, ADR 0051 guards).

        Order: reaction (before any LLM call), tool_step per real tool call, keepalive every KEEPALIVE_SECONDS
        while waiting, verifying, bubble per checked bubble with its highlights, done with the same ChatResponse
        as `answer`. `error` is sent when Penny is unavailable; then `done` follows with the fixed reply and no
        bubble events."""
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
        sent_ids: set[str] = set()
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                except TimeoutError:
                    yield event("keepalive")
                    continue
                if item is None:
                    break
                type_, fields = item
                if type_ == "early_bubble":
                    sent_ids.add(fields["bubble"].id)
                    yield event("bubble", bubble=BubbleEvent(bubble=fields["bubble"], highlights=fields["highlights"]))
                elif type_ == "tool_step":
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
            sent = len(sent_ids)
            for b in resp.bubbles:
                if b.id in sent_ids:
                    continue  # already streamed early
                if not bubble_verified(b, resp):
                    continue  # never emit an unchecked bubble
                hl = [h for h in resp.highlights if h.bubble_id == b.id]
                yield event("bubble", bubble=BubbleEvent(bubble=b, highlights=hl))
                sent += 1
            if sent == 0:
                yield event("error", error_code="unverified")
        yield event("done", response=resp)

    # ----- loop -----

    async def _personal_facts(self, ctx: ChatToolContext) -> list[ChatFact]:
        """The user's own money numbers. A general answer must not state them (ADR 0051)."""
        if ctx.personal_facts is not None:
            facts = list(ctx.personal_facts)
        else:
            fn = getattr(ctx.tools, "personal_facts", None)
            if not callable(fn):
                return []
            try:
                got = await asyncio.to_thread(fn)
                if inspect.isawaitable(got):
                    got = await got
                facts = list(got)
            except Exception as exc:
                log.info("penny: personal facts unavailable (%s)", type(exc).__name__)
                return []
        return [f for f in facts if f.unit in PERSONAL_UNITS and abs(f.value) >= 1]

    async def _preload(self, ctx: ChatToolContext, state: TurnState) -> str | None:
        """Speed (V1, first bubble < 3 s): run the ToolSet's cheap personal tools (`preload`, e.g. finance_summary
        and next_move) before the first model call and send their facts with the question. A personal question
        then needs one model call. The results are real tool outputs; they count as tool calls only when the
        answer uses them."""
        names = [n for n in (getattr(ctx.tools, "preload", ()) or ()) if n in CLIENT_TOOL_NAMES][:2]
        if state.rules and names and "facts_table" in {s.name for s in ctx.tools.specs()}:
            names.append("facts_table")  # ADR 0058: official rules first, without a tool round trip
        if not names:
            return None
        try:
            got = await asyncio.wait_for(
                asyncio.gather(*(self._call_tool(ctx, n, {}) for n in names)), timeout=PRELOAD_SECONDS
            )
        except TimeoutError:
            log.info("penny: preload timed out")
            return None
        payload: dict[str, Any] = {}
        before = {f.id for f in state.facts}
        for name, (out, ok, _, ms) in zip(names, got, strict=True):
            if out is None or not ok:
                continue
            payload[name] = self._register(name, out, state)
            state.preloaded.append((name, out, ToolCall.model_construct(name=cast(Any, name), ok=True, duration_ms=ms)))
        state.preloaded_ids = {f.id for f in state.facts} - before
        if not payload:
            return None
        intro = (
            "APP DATA (tool results already fetched for this user this turn; use these facts for numbers about "
            "the user's money, and call a tool only for anything else): "
        )
        return intro + json.dumps(payload, ensure_ascii=False)

    async def _loop(
        self, request: ChatRequest, ctx: ChatToolContext, state: TurnState, ids: dict[str, str]
    ) -> ChatResponse:
        assert self.llm is not None
        state.rules = official.is_rules_question(request.message)
        challenged = is_challenge(request.message)
        app_data, state.personal = await asyncio.gather(self._preload(ctx, state), self._personal_facts(ctx))
        # Speed (V1): a preloaded tool is not offered again (its result is in APP DATA), except after a challenge.
        skip = set() if challenged else {name for name, _, _ in state.preloaded}
        tools = [{"name": s.name, "description": s.description, "input_schema": s.input_schema}
                 for s in ctx.tools.specs() if s.name not in skip]  # fmt: skip
        tools.append(web_search_tool(state.rules))
        messages = build_messages(request, ctx, app_data)
        nudged = rewritten = personal_retried = official_retried = fx_retried = False
        reason = "max_steps"
        streams = bool(getattr(self.llm, "supports_stream", False)) and state.emit is not None and not challenged
        for _ in range(MAX_STEPS):
            t_step = time.monotonic()
            if streams and state.committed is None:
                on_text = self._early_bubble_hook(ids, state, ctx)
                step = await cast(Any, self.llm).step(prompts.PENNY_SYSTEM, messages, tools,
                                                      prompts.PENNY_ANSWER_SCHEMA, on_text=on_text)  # fmt: skip
            else:
                step = await self.llm.step(prompts.PENNY_SYSTEM, messages, tools, prompts.PENNY_ANSWER_SCHEMA)
            self._record_web(step, state, int((time.monotonic() - t_step) * 1000))
            if state.committed is not None:
                # The first bubble already went out (stream). Finish with it; later bubbles only if they pass.
                return self._finish_committed(ids, parse_draft(step.text), state)
            if step.tool_uses:
                messages.append({"role": "assistant", "content": _content(step)})
                # Parallel tool calls (ADR 0051): all results go back in one user message.
                results = await asyncio.gather(*(self._run_tool(tu, ctx, state) for tu in step.tool_uses))
                messages.append({"role": "user", "content": list(results)})
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
            if challenged and not state.app_tool_used() and len(tools) > 1 and not nudged and not draft.out_of_scope:
                nudged = True
                messages.append({"role": "assistant", "content": _content(step)})
                messages.append({"role": "user", "content": prompts.PENNY_CHALLENGE_NUDGE})
                continue
            fixed = fixed_reply(draft)
            if fixed is not None:
                return self._build(ids, fixed[0], state, verified=True, fixed_text=fixed[1], mode="general")
            draft = apply_rules(draft, challenged)
            chk = check_draft(draft, state)
            if chk.kind is not None and len(draft.bubbles) > 1:
                # Speed (V1): keep a good first bubble and drop a failing second one instead of a rewrite.
                first = replace(draft, bubbles=draft.bubbles[:1])
                first_chk = check_draft(first, state)
                if first_chk.kind is None:
                    log.info("penny: dropped bubble 2 (%s %s)", chk.kind, chk.bad)
                    draft, chk = first, first_chk
            if chk.kind is None:
                if chk.mode == "checked":
                    self._promote(ctx, state, draft)
                    if not state.verifying_sent:
                        state.verifying_sent = True
                        _emit(state, "verifying")
                return self._build(ids, draft, state, verified=True, mode=chk.mode)
            log.info("penny: answer blocked (%s %s)", chk.kind, chk.bad)
            if chk.kind == "unverified":
                self._promote(ctx, state, draft)
                if rewritten:
                    reason = "unverified"
                    break
                rewritten = True
                retry = prompts.PENNY_REWRITE.format(bad=", ".join(chk.bad))
            elif chk.kind == "fx_rate":
                self._promote(ctx, state, draft)
                if fx_retried:
                    # V6 S5-F1: state the rate and its date from the tool facts.
                    return self._build(ids, with_fx_rate(draft, state), state, verified=True)
                fx_retried = True
                retry = prompts.PENNY_FX_RETRY.format(missing=", ".join(chk.bad))
            elif chk.kind == "official":
                if official_retried:
                    # ADR 0058: answer without the number; with no official source, say so.
                    return self._build(ids, without_numbers(draft, list(chk.bad), state), state, verified=True,
                                       mode="general")  # fmt: skip
                official_retried = True
                if not state.rules:  # V6 V2-R2: retry on official sites only
                    state.rules = True
                    tools[-1] = web_search_tool(True)
                retry = prompts.PENNY_OFFICIAL_RETRY.format(bad=", ".join(chk.bad))
            else:
                if personal_retried:
                    reason = {"personal": "personal_numbers", "asks_public": "asked_public_fact"}.get(
                        chk.kind or "", "no_live_data_claim"
                    )
                    break
                personal_retried = True
                if chk.kind == "personal":
                    retry = prompts.PENNY_PERSONAL_RETRY.format(bad=", ".join(chk.bad))
                elif chk.kind == "asks_public":
                    retry = prompts.PENNY_LOOKUP_RETRY.format(bad="; ".join(chk.bad))
                else:
                    retry = prompts.PENNY_LIVE_DATA_RETRY
            messages.append({"role": "assistant", "content": _content(step)})
            messages.append({"role": "user", "content": retry})
        return await self._template(ids, state, ctx, reason=reason)

    def _promote(self, ctx: ChatToolContext, state: TurnState, draft: Draft | None = None) -> None:
        """The answer uses the app data sent with the question: the tool calls whose facts it quotes count
        (checked mode). With no quoted fact (a claim in words), every preloaded call counts."""
        if not state.preloaded:
            return
        used = {state.fact_tool.get(i) for i in used_fact_ids(draft, state.facts)} if draft is not None else set()
        take = [p for p in state.preloaded if p[0] in used] or list(state.preloaded)
        for name, out, tc in take:
            state.calls.append(tc)
            ctx.outputs.append((name, out))
        state.preloaded = [p for p in state.preloaded if p not in take]

    def _early_bubble_hook(self, ids: dict[str, str], state: TurnState, ctx: ChatToolContext) -> Callable[[str], None]:
        """Speed (V1): send bubble 1 as soon as its JSON is complete and it passes every check on its own."""

        def hook(text: str) -> None:
            if state.committed is not None or state.emit is None:
                return
            m = _FIRST_BUBBLE.search(text)
            if m is None or re.search(r'"out_of_scope"\s*:\s*true', text):
                return
            try:
                raw = json.loads(f'"{m.group("text")}"')
            except ValueError:
                return
            kind = m.group("kind") if m.group("kind") in {"answer", "caveat", "general_knowledge"} else "answer"
            body = clean_bubble(str(raw))
            if not body:
                return
            draft = Draft("eyes", [(cast(BubbleKind, kind), body)])
            if fixed_reply(draft) is not None:
                return
            chk = check_draft(draft, state)
            if chk.kind is not None:
                return
            state.committed = (cast(BubbleKind, kind), body, chk.mode)
            if chk.mode == "checked":
                self._promote(ctx, state, draft)
            bubble = ChatBubble(id=f"{ids['message_id']}-b1", kind=cast(BubbleKind, kind), text=body)
            hl = make_highlights([bubble], state) if chk.mode == "checked" else []
            _emit(state, "early_bubble", bubble=bubble, highlights=hl)

        return hook

    def _finish_committed(self, ids: dict[str, str], draft: Draft | None, state: TurnState) -> ChatResponse:
        assert state.committed is not None
        kind, text, mode = state.committed
        bubbles: list[tuple[BubbleKind, str]] = [(kind, text)]
        reaction: Reaction = draft.reaction if draft is not None else "eyes"
        suggestions = list(draft.suggestions) if draft is not None else []
        if draft is not None and not draft.out_of_scope:
            for k, t in draft.bubbles[1:MAX_BUBBLES]:
                second = Draft(reaction, [(k, t)])
                if fixed_reply(second) is None and check_draft(second, state, mode=mode).kind is None:
                    bubbles.append((k, t))
                if distress_rule(t):
                    bubbles = [(kind, text), ("answer", prompts.DISTRESS_TEXT[1])]
        if reaction == "shrug":
            reaction = "eyes"
        return self._build(ids, Draft(reaction, bubbles[:MAX_BUBBLES], suggestions=suggestions), state,
                           verified=True, mode=mode)  # fmt: skip

    def _record_web(self, step: LLMStep, state: TurnState, ms: int) -> None:
        """Server web searches ran inside the model call: record them as real tool calls, after the fact."""
        for _ in range(min(step.web_searches, MAX_TOOL_CALLS)):
            _emit(state, "tool_step", tool="web_search", label=STEP_LABELS["web_search"])
            state.calls.append(ToolCall(name="web_search", ok=True, duration_ms=max(0, ms)))
        for r in step.web_results:
            state.add_web(r.url, r.title, r.text)

    async def _run_tool(self, tu: ToolUse, ctx: ChatToolContext, state: TurnState) -> dict[str, Any]:
        def err(msg: str) -> dict[str, Any]:
            return {"type": "tool_result", "tool_use_id": tu.id, "content": msg, "is_error": True}

        if state.attempted >= MAX_TOOL_CALLS:
            return err("Tool limit reached. Answer now with the facts you have.")
        if tu.name not in CLIENT_TOOL_NAMES:
            return err(f"Unknown tool: {tu.name[:40]}")
        state.attempted += 1
        _emit(state, "tool_step", tool=tu.name, label=step_label(ctx, tu.name, tu.input))
        out, ok, msg, ms = await self._call_tool(ctx, tu.name, tu.input)
        state.calls.append(ToolCall.model_construct(name=cast(Any, tu.name), ok=ok, duration_ms=ms))
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
        if tool == "next_move" and isinstance(result, dict) and isinstance(result.get("top"), dict):
            state.testable = bool(result["top"].get("testable"))  # Test it works only for a testable move
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
            state.fact_tool.setdefault(fid, tool)
            value: float | int = int(f.value) if float(f.value).is_integer() else f.value  # 25, never 25.0
            facts.append({"id": fid, "value": value, "unit": f.unit, "label": fence(tidy_numbers(f.label), tool)})
        return {
            "result": fence_strings(result, tool),
            "facts": facts,
            "sources": [{"id": sid, "label": state.sources[sid].label} for sid in source_ids],
        }

    # ----- template (verified=false) and unavailable -----

    async def _template(self, ids: dict[str, str], state: TurnState, ctx: ChatToolContext, reason: str) -> ChatResponse:
        """A summary of this turn's app tool facts (verified=false).

        - LLM down, timeout or error before any app tool ran: "Penny is unavailable".
        - No app tool ran but the answer failed a check: general mode, "I could not confirm that number" (V6 V2-R1).
        - Never lists web citation numbers ('web.' facts) or app data the answer did not use."""
        if not state.app_tool_used():
            if reason in LLM_FAILURES:
                _emit(state, "error", error_code=reason)
                return self._unavailable(ids, state)
            log.info("penny: could not confirm (%s)", reason)
            draft = Draft("question", [("answer", NOT_CONFIRMED_TEXT)], suggestions=["Next move"])
            return self._build(ids, draft, state, verified=False, mode="general")
        lines: list[str] = []
        for f in state.facts:
            unused = {name for name, _, _ in state.preloaded}
            if ".text." in f.id or f.id.startswith("web.") or state.fact_tool.get(f.id) in unused:
                continue  # text numbers, web citation numbers and unused app data are not listed
            label = sanitize_untrusted(f.label, 100).rstrip(".")
            line = f"{label[:1].upper()}{label[1:]}: {format_fact(f)}."
            if not unverified_numbers(Draft("eyes", [("answer", line)]), state.facts):
                lines.append(line)
        if not lines:
            _emit(state, "error", error_code=reason)
            return self._unavailable(ids, state)
        bubbles: list[tuple[BubbleKind, str]] = [("answer", " ".join([TEMPLATE_INTRO, *lines[:2]]))]
        if lines[2:]:
            bubbles.append(("answer", " ".join(lines[2:4])))
        log.info("penny: template summary (%s)", reason)
        draft = Draft("question", bubbles, summary_available=len(lines) > 4, suggestions=["Next move"])
        return self._build(ids, draft, state, verified=False)

    def _unavailable(self, ids: dict[str, str], state: TurnState) -> ChatResponse:
        draft = Draft("question", [("answer", prompts.UNAVAILABLE_TEXT)])
        return self._build(ids, draft, state, verified=False, mode="general")

    # ----- response -----

    def _ids(self, request: ChatRequest, ctx: ChatToolContext) -> dict[str, str]:
        return {
            "thread_id": ctx.thread_id or request.thread_id or f"t_{uuid.uuid4().hex[:16]}",
            "message_id": f"m_{uuid.uuid4().hex[:16]}",
            "reply_to": ctx.user_message_id or request.reply_to or f"u_{uuid.uuid4().hex[:16]}",
        }

    def _build(
        self,
        ids: dict[str, str],
        draft: Draft,
        state: TurnState,
        verified: bool,
        fixed_text: str | None = None,
        mode: ChatMode = "checked",
    ) -> ChatResponse:
        if draft.out_of_scope:
            draft = Draft("shrug", [("answer", fixed_text or prompts.OUT_OF_SCOPE_TEXT)], out_of_scope=True)
        bubbles = [
            ChatBubble(id=f"{ids['message_id']}-b{i + 1}", kind=kind, text=text)
            for i, (kind, text) in enumerate(draft.bubbles[:MAX_BUBBLES])
        ]
        checked = mode == "checked"
        matched = matched_facts(bubbles, state.facts) if checked else []
        highlights = make_highlights(bubbles, state) if checked else []
        used = {f.id for f in matched} | {h.fact_id for h in highlights}
        if draft.out_of_scope:
            sources: list[ChatSource] = []
        elif checked:
            # V4 F3-1: only the sources behind the numbers the answer uses; with no number, the tools that ran.
            pool = list(state.sources.values()) + list(state.web_sources.values())
            used_sources = {f.source_id for f in state.facts if f.id in used and f.source_id}
            if used_sources:
                sources = [s for s in pool if s.id in used_sources]
            else:
                called = {c.name for c in state.calls if c.ok}
                sources = [s for s in state.sources.values() if state.source_tools.get(s.id, set()) & called]
                sources += list(state.web_sources.values()) if state.rules else []
        else:
            sources = list(state.web_sources.values())
        if any(b.kind == "general_knowledge" for b in bubbles) and checked:
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
            mode=mode,
            bubbles=bubbles,
            highlights=highlights,
            facts=[f for f in state.facts if f.id in used],
            sources=sources,
            follow_up_question=question[:300] if question else None,
            suggestions=[
                x
                for x in (clean_suggestions(draft.suggestions) if asks_question(bubbles) else [])
                if state.testable or not _TEST_CHIP.search(x)
            ],  # fmt: skip
            confidence=confidence(draft, state, verified, bubbles),
            tool_calls=[c for c in state.calls if c.name in CONTRACT_TOOL_NAMES][:MAX_TOOL_CALLS],
            verified=verified,
            summary_available=draft.summary_available,
            links=links_for(draft, state, verified, mode, frozenset(used)),
        )


TEMPLATE_INTRO = "Here are the numbers I found."
NOT_CONFIRMED_TEXT = (
    "I could not confirm that number from your data or an official source, so I will not guess it. "
    "Ask me again, or check the Money tab."
)
LLM_FAILURES = frozenset(
    {"llm_unavailable", "llm_error", "timeout", "refusal", "max_tokens", "unparseable", "max_steps"}
)
NO_ANSWER_TEXT = prompts.UNAVAILABLE_TEXT  # kept for callers of the old name


def distress_draft() -> Draft:
    return Draft("eyes", [("answer", prompts.DISTRESS_TEXT[0]), ("answer", prompts.DISTRESS_TEXT[1])],
                 suggestions=["Make a budget"])  # fmt: skip


def _content(step: LLMStep) -> Any:
    return step.content if step.content is not None else [{"type": "text", "text": step.text}]


# ---------- prompt building ----------


def build_messages(request: ChatRequest, ctx: ChatToolContext, app_data: str | None = None) -> list[dict[str, Any]]:
    turns: list[tuple[str, str]] = []
    for t in list(ctx.history)[-HISTORY_TURNS:]:
        turns.append(_turn(t))
    parts = []
    if ctx.known:
        parts.append("KNOWN (from the app): " + fence(json.dumps(ctx.known, ensure_ascii=False), "profile"))
    rc = ctx.request_context or request.context
    if rc is not None:
        parts.append("CONTEXT: " + json.dumps(rc.model_dump(exclude_none=True)))
    if app_data:
        parts.append(app_data)
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
    """The model's JSON answer. Plain text with no JSON object becomes one answer bubble (it is still checked)."""
    data: Any = None
    try:
        data = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except ValueError:
                data = None
        if data is None:
            plain = clean_bubble(text)
            return Draft("eyes", [("answer", plain)]) if plain else None
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
    raw_suggestions = data.get("suggestions")
    return Draft(
        reaction=cast(Reaction, reaction if reaction in REACTIONS else "eyes"),
        bubbles=bubbles,
        summary_available=bool(data.get("summary_available")),
        out_of_scope=out_of_scope,
        suggestions=[str(x) for x in raw_suggestions] if isinstance(raw_suggestions, list) else [],
    )


_LONE_ANSWERS = frozenset({"yes", "no", "ok", "okay", "sure", "yes please", "no thanks", "maybe"})


_TEST_CHIP = re.compile(r"\b(test|replay|play it)\b", re.IGNORECASE)


def asks_question(bubbles: list[ChatBubble]) -> bool:
    """Chips answer Penny's follow-up question (ADR 0060). No question, no chips."""
    return any(b.kind == "question" or b.text.rstrip().endswith("?") for b in bubbles)


_YES_NO_PREFIX = re.compile(r"^(yes|yeah|yep|sure|ok|okay|no|nope|not now)\s*[,:\-\u2013]\s*(please\s*,?\s*)?", re.I)


def clean_suggestions(items: list[str]) -> list[str]:
    """At most 2 short chips. Never a lone 'Yes' (ADR 0051). Same house style as bubbles, no numbers."""
    out: list[str] = []
    for raw in items:
        chip = clean_bubble(sanitize_untrusted(str(raw), 80)).rstrip(".")
        # V4 advisory: chips name the action ("Show me how"), not "Yes, show me how".
        chip = _YES_NO_PREFIX.sub("", chip).strip()
        chip = chip[:1].upper() + chip[1:]
        if not chip or len(chip) > 40 or chip.lower().rstrip("?") in _LONE_ANSWERS or extract_numbers(chip):
            continue
        if chip.lower() not in {c.lower() for c in out}:
            out.append(chip)
    return out[:MAX_SUGGESTIONS]


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
        # Voice (ADR 0051): the answer first; keep a question (if any) as the second bubble.
        q = [b for b in bubbles if b[0] == "question"]
        rest = [b for b in bubbles if b[0] != "question"]
        bubbles = rest[: MAX_BUBBLES - len(q[:1])] + q[:1]
    if challenged and bubbles and bubbles[0][0] == "answer" and not bubbles[0][1].lower().startswith("fair"):
        bubbles[0] = ("answer", "Fair question. " + bubbles[0][1])
        bubbles[0] = ("answer", clean_bubble(bubbles[0][1]))
    reaction = draft.reaction
    if reaction == "shrug":
        reaction = "question"
    return Draft(reaction, bubbles, summary, False, list(draft.suggestions))


def unverified_numbers(draft: Draft, facts: list[ChatFact], *, gk_numbers: bool = False) -> list[str]:
    """Checked mode: every number must match a fact value in a compatible unit. General-knowledge bubbles hold
    no number, except for rules questions (`gk_numbers`), where official facts back them (ADR 0058)."""
    bad: list[str] = []
    for kind, text in draft.bubbles:
        for found in extract_numbers(text):
            gk_blocked = kind == "general_knowledge" and not gk_numbers
            if gk_blocked or not any(fact_matches(found, f.value, f.unit) for f in facts):
                bad.append(found.raw)
    return bad


def without_numbers(draft: Draft, bad: list[str], state: TurnState) -> Draft:
    """ADR 0058: drop sentences with numbers no official text states. With nothing left, or no official source
    at all, Penny says she could not find an official source and gives no number."""
    bubbles: list[tuple[BubbleKind, str]] = []
    for kind, text in draft.bubbles:
        keep = [s for s in _SENT_SPLIT.split(text) if not any(n.raw in bad for n in extract_numbers(s))]
        if keep:
            bubbles.append((kind, " ".join(keep)))
    if not bubbles or not state.has_official_source():
        bubbles = [("answer", official.NO_OFFICIAL_SOURCE_TEXT)]
    return Draft("question", bubbles, suggestions=list(draft.suggestions))


_MONEY_CONTEXT = re.compile(
    r"\b(account|balance|spend|spent|spending|saved|savings|owe|owed|debt|income|earn|paid|pay|cost|budget|left|"
    r"loan|rent|bills?|overdraft|money|cash)\b",
    re.IGNORECASE,
)
_PERSONAL_CLAIM = re.compile(
    r"\b(your (current )?(balance|account|accounts|income|spend|spending|savings|debts?|loan|budget|rent|bills?|"
    r"overdraft|net worth|pay|salary)( \w+)? (is|are|was|comes to|stands at|of)|"
    r"you('ve| have| currently have| now have| still have| spend| spent| owe| earn| get| receive| saved| paid| pay| "
    r"have got|'ve got)\b)",
    re.IGNORECASE,
)
_HYPOTHETICAL = re.compile(r"\b(if|say|imagine|suppose|for example|e\.g\.|example|someone|a student who)\b", re.I)
PERSONAL_TOLERANCE = 0.05


def _money_number(found: Found, sentence: str) -> bool:
    return found.kind == "gbp" or (found.kind is None and not found.is_ratio and bool(_MONEY_CONTEXT.search(sentence)))


def _near(found: Found, value: float) -> bool:
    """Same number after rounding (£140, £0.1k for 138) or within 5% (V6 V2-F4)."""
    v, t = abs(found.value), abs(value)
    if t == 0:
        return v == 0
    return _close_written(v, t, found.decimals) or abs(v - t) <= PERSONAL_TOLERANCE * t


def _close_written(v: float, t: float, decimals: int) -> bool:
    if v == t or round(t, decimals) == v:
        return True
    for step in (10, 100, 1000):  # "about £140" for 138, "£100" for 96
        if v % step == 0 and v >= step and abs(round(t / step) * step - v) < 1e-9 and step <= 0.2 * max(t, v):
            return True
    return False


def personal_numbers(draft: Draft, personal: list[ChatFact]) -> list[str]:
    """General mode: money numbers that state, or round to, one of the user's own money facts (ADR 0051,
    V6 V2-F4). '£138', '138 GBP', '138 in your account', 'about £140' and '£0.1k' all count."""
    bad: list[str] = []
    for _, text in draft.bubbles:
        for sentence in _SENT_SPLIT.split(text):
            for found in extract_numbers(sentence):
                if _money_number(found, sentence) and any(_near(found, f.value) for f in personal):
                    bad.append(found.raw)
    return bad


def personal_claims(draft: Draft) -> list[str]:
    """General mode: 'your balance is £X', 'you have £X' and similar statements about the user's own money.
    With no app tool they cannot be checked, so they are blocked whatever X is (V6 V2-F5)."""
    bad: list[str] = []
    for _, text in draft.bubbles:
        for sentence in _SENT_SPLIT.split(text):
            if not _PERSONAL_CLAIM.search(sentence) or _HYPOTHETICAL.search(sentence):
                continue
            bad += [n.raw for n in extract_numbers(sentence) if _money_number(n, sentence)]
    return bad


_RATE_WORD = re.compile(r"\b(rates?|interest|apr|aer|yield)\b", re.IGNORECASE)
_NO_LIVE = re.compile(
    r"\b(i\s+(do\s*n[o']?t|cannot|can'?t|am\s+not\s+able\s+to|am\s+unable\s+to)\s+(have\s+)?(access(\s+to)?|see|"
    r"get|check|look\s+up|browse)?\s*(any\s+)?(live|current|real[- ]?time|up[- ]to[- ]date|today'?s|latest)\s+"
    r"(data|rates?|information|figures|numbers|prices)|my\s+(knowledge|training|information)\s+(only\s+)?"
    r"(goes|runs|is|was)\s+(up\s+to|until|from)|as\s+of\s+my\s+(last|training))",
    re.IGNORECASE,
)


_FIRST_BUBBLE = re.compile(
    r'"bubbles"\s*:\s*\[\s*\{\s*"kind"\s*:\s*"(?P<kind>\w+)"\s*,\s*"text"\s*:\s*"(?P<text>(?:[^"\\]|\\.)*)"'
)


def web_search_tool(official_only: bool) -> dict[str, Any]:
    tool = dict(WEB_SEARCH_TOOL)
    if official_only:
        tool["allowed_domains"] = list(official.OFFICIAL_DOMAINS)  # ADR 0058: official sites only
    return tool


def fixed_reply(draft: Draft) -> tuple[Draft, str | None] | None:
    """Answers replaced by a fixed reply: out of scope, system prompt leak, distress signal, investment pick."""
    if draft.out_of_scope:
        return draft, None
    text = " ".join(t for _, t in draft.bubbles)
    if any(leaks_system_prompt(t) for _, t in draft.bubbles):
        log.info("penny: answer repeated the system prompt; fixed reply")
        return Draft(
            "shrug", [("answer", prompts.NO_INSTRUCTIONS_TEXT)], out_of_scope=True
        ), prompts.NO_INSTRUCTIONS_TEXT
    if distress_rule(text):
        log.info("penny: distress signal in the answer; fixed support reply")  # V6 V2-F2 second layer
        return distress_draft(), None
    if gives_pick(text):
        log.info("penny: answer named an investment pick; fixed refusal")  # V6 V2-F3
        return Draft("shrug", [], out_of_scope=True), None
    return None


@dataclass(frozen=True)
class Check:
    mode: ChatMode
    kind: str | None = None  # None: ok. "unverified" (checked), "official", "personal", "no_live" (general)
    bad: tuple[str, ...] = ()


def _official_facts(state: TurnState) -> list[ChatFact]:
    return [f for f in state.facts if f.id.startswith(("web.", "rule."))]


def unofficial_web_numbers(draft: Draft, state: TurnState) -> list[str]:
    """V6 V2-R2: a £ or % number in a general answer after a search that reached a non-official site must be
    stated by an official page."""
    if not any(s.url and not official.is_official_url(s.url) for s in state.web_sources.values()):
        return []
    facts = _official_facts(state)
    return [n.raw for _, t in draft.bubbles for n in extract_numbers(t)
            if n.kind in {"gbp", "percent"} and not any(fact_matches(n, f.value, f.unit) for f in facts)]  # fmt: skip


def check_draft(draft: Draft, state: TurnState, mode: ChatMode | None = None) -> Check:
    """Every rule a final answer must pass, without side effects. Used for the whole answer and for an early
    first bubble."""
    checked = mode == "checked" if mode else (state.app_tool_used() or uses_preloaded(draft, state))
    if checked:
        bad = unverified_numbers(draft, state.facts, gk_numbers=state.rules)
        if bad:
            return Check("checked", "unverified", tuple(bad))
        asked = asks_for_public_fact(draft)
        if asked:
            return Check("checked", "asks_public", tuple(asked))
        missing = fx_missing(draft, state)
        return Check("checked", "fx_rate" if missing else None, tuple(missing))
    if state.rules:
        rule_bad = unverified_numbers(draft, _official_facts(state), gk_numbers=True)
    else:
        rule_bad = unofficial_web_numbers(draft, state)
    if rule_bad:
        return Check("general", "official", tuple(rule_bad))
    rate_bad = [] if state.rules else unsourced_rate_numbers(draft, state)
    bad = list(dict.fromkeys(personal_numbers(draft, state.personal) + personal_claims(draft) + rate_bad))
    if bad:
        return Check("general", "personal", tuple(bad))
    if claims_no_live_data(draft):
        return Check("general", "no_live")
    asked = asks_for_public_fact(draft)
    if asked:
        return Check("general", "asks_public", tuple(asked))
    return Check("general")


_CURRENT = re.compile(
    r"\b(current(ly)?|now|today|at the moment|right now|latest|this (week|month|year)|bank rate|base rate)\b",
    re.IGNORECASE,
)


def uses_preloaded(draft: Draft, state: TurnState) -> bool:
    """True when the answer quotes a preloaded app-data fact (any unit) or states the user's own money."""
    if not state.preloaded:
        return False
    # Counts and years match too easily ("2 steps", "in 2026"); worked examples ("if you save £100") are not data.
    pre = [f for f in state.facts if f.id in state.preloaded_ids and f.unit not in {"count", "date_year"}]
    for _, text in draft.bubbles:
        for sentence in _SENT_SPLIT.split(text):
            if _HYPOTHETICAL.search(sentence):
                continue
            if any(fact_matches(n, f.value, f.unit) for n in extract_numbers(sentence) for f in pre):
                return True
    return bool(personal_claims(draft))


def unsourced_rate_numbers(draft: Draft, state: TurnState) -> list[str]:
    """General mode: a claim about a current rate ('savings rates are 5% now') needs a source (boe_rates or a
    web search this turn). Examples ('at 5% interest, £100 grows to £105') are fine."""
    if state.web_sources or any(c.ok and c.name == "web_search" for c in state.calls):
        return []
    bad: list[str] = []
    for _, text in draft.bubbles:
        for sentence in _SENT_SPLIT.split(text):
            if _RATE_WORD.search(sentence) and _CURRENT.search(sentence):
                bad += [n.raw for n in extract_numbers(sentence) if n.is_percent or n.kind == "percent"]
    return bad


_PUBLIC_ASK = re.compile(
    r"\b(what|which|do you know|could you|can you|would you|please)\b[^?]*\b(exchange rate|conversion rate|rate is|"
    r"current rate|interest rate|bank rate|base rate|inflation|cpi|in pounds|in gbp|worth in|yuan|euros?|dollars?|"
    r"yen|price of gold|date of the|when is the (next )?(budget|rate decision|bank holiday))\b[^?]*\?",
    re.IGNORECASE,
)


def _fact(state: TurnState, fid: str) -> ChatFact | None:
    return next((f for f in reversed(state.facts) if f.id == fid), None)


def fx_missing(draft: Draft, state: TurnState) -> list[str]:
    """V6 S5-F1: an answer that converts money with fx_convert must state the rate and its date."""
    rate, day, year = _fact(state, "fx.rate"), _fact(state, "fx.date.day"), _fact(state, "fx.date.year")
    amount, conv = _fact(state, "fx.amount"), _fact(state, "fx.converted")
    if rate is None or day is None or year is None:
        return []
    nums = [n for _, t in draft.bubbles for n in extract_numbers(t)]

    def says(*facts: ChatFact | None) -> bool:
        return any(f is not None and fact_matches(n, f.value, f.unit) for n in nums for f in facts)

    if not says(amount, conv):
        return []  # the answer does not convert anything
    missing = [] if says(rate, _fact(state, "fx.rate_gbp")) else ["the rate"]
    if not (says(day) and says(year)):
        missing.append("the rate date")
    return missing


def with_fx_rate(draft: Draft, state: TurnState) -> Draft:
    """Add 'Rate: 1 CNY = £0.104123 (ECB, 16 Oct 2026).' from the fx_convert facts."""
    rate, day, year = _fact(state, "fx.rate"), _fact(state, "fx.date.day"), _fact(state, "fx.date.year")
    pair = next((s.ref.series_id for s in state.sources.values() if s.ref and s.ref.source == "frankfurter"), "")
    if rate is None or day is None or year is None or len(pair) != 6:
        return draft
    month = next((f.label.rsplit(" ", 2)[-2][:3] for f in state.facts if f.id == "fx.rate"), "")
    money = "\u00a3" if pair[3:] == "GBP" else ""
    tail = "" if money else f" {pair[3:]}"
    line = f"Rate: 1 {pair[:3]} = {money}{rate.value:g}{tail} (ECB, {int(day.value)} {month} {int(year.value)})."
    bubbles = list(draft.bubbles)
    if len(bubbles) < MAX_BUBBLES:
        bubbles.append(("caveat", line))
    else:
        kind, text = bubbles[-1]
        bubbles[-1] = (kind, f"{text} {line}"[:600])
    return replace(draft, bubbles=bubbles)


def asks_for_public_fact(draft: Draft) -> list[str]:
    """ADR 0060: Penny never asks the user for rates, conversions, public dates or public facts."""
    return [m.group(0)[:60] for _, t in draft.bubbles for m in _PUBLIC_ASK.finditer(t)]


def claims_no_live_data(draft: Draft) -> bool:
    """'I do not have live rates' and similar. The app has live data (boe_rates); Penny must not say this."""
    return any(_NO_LIVE.search(text.replace("\u2019", "'")) for _, text in draft.bubbles)


def bubble_verified(b: ChatBubble, resp: ChatResponse) -> bool:
    """Final per-bubble check before a stream emits it. Checked mode: every number matches a fact in the
    response. General mode: `answer` already blocked personal numbers; other numbers (recipes, dates) are fine."""
    if resp.mode == "general":
        return True
    nums = extract_numbers(b.text)
    if b.kind == "general_knowledge":
        return not nums
    return all(any(fact_matches(n, f.value, f.unit) for f in resp.facts) for n in nums)


def _match(found: Found, facts: list[ChatFact]) -> ChatFact | None:
    ok = [f for f in facts if fact_matches(found, f.value, f.unit)]
    exact = [f for f in ok if abs(f.value) == found.value]
    return exact[0] if exact else (ok[0] if ok else None)


def used_fact_ids(draft: Draft, facts: list[ChatFact]) -> set[str]:
    """Ids of the facts behind the numbers in a draft."""
    out: set[str] = set()
    for _, text in draft.bubbles:
        for found in extract_numbers(text):
            fact = _match(found, facts)
            if fact is not None:
                out.add(fact.id)
    return out


def matched_facts(bubbles: list[ChatBubble], facts: list[ChatFact]) -> list[ChatFact]:
    """The fact behind each number in the bubbles (any unit), so a client can re-check every number."""
    out: dict[str, ChatFact] = {}
    for b in bubbles:
        for found in extract_numbers(b.text):
            fact = _match(found, facts)
            if fact is not None:
                out.setdefault(fact.id, fact)
    return list(out.values())


def make_highlights(bubbles: list[ChatBubble], state: TurnState) -> list[Highlight]:
    """Tappable numbers: money and rates only, never years, dates or counts (ADR 0051)."""
    out: list[Highlight] = []
    for b in bubbles:
        for found in extract_numbers(b.text):
            fact = _match(found, state.facts)
            if fact is None or fact.unit not in HIGHLIGHT_UNITS:
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


def links_for(
    draft: Draft, state: TurnState, verified: bool, mode: ChatMode = "checked", used: frozenset[str] = frozenset()
) -> list[Any]:
    """In-app destinations that work for this user. Out of scope and unverified answers point to the Next Move.
    Test it only when the answer quotes the Next Move (`used` holds a next_move fact) and that move is testable.
    A test_move answer offers Do this (plan). General answers link nowhere."""
    if draft.out_of_scope or not verified:
        return ["next_move"]
    if mode == "general":
        return []
    ok = {c.name for c in state.calls if c.ok}
    links: list[Any] = []
    if "next_move" in ok and state.testable and any(u.startswith("next_move.") for u in used):
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
    if state.app_tool_used():
        return 0.9
    if any(b.kind == "question" for b in bubbles) and len(bubbles) == 1:
        return 0.5
    return 0.6


_PICK_ASSETS = (
    r"shares?|stocks?|equit(y|ies)|crypto(currency|currencies)?|bitcoin|btc|ethereum|eth|dogecoin|solana|xrp|"
    r"coins?|tokens?|etfs?|(index |tracker |mutual )?funds?|penny stocks?|meme stocks?|gold|silver|"
    r"s&p( ?500)?|nasdaq|ftse( ?100)?|dow jones|tesla|apple|nvidia|amazon|microsoft|google|alphabet|meta|"
    r"gamestop|options"
)
# Words that are investments only (V6 re-check): a match with these is a pick question on its own. Other asset
# words (apple, options, gold, coins, funds) count only next to investing words ("best apple to buy for baking" is
# fine).
_STRONG_ASSETS = re.compile(
    r"\b(shares?|stocks?|equit(y|ies)|crypto(currency|currencies)?|bitcoin|btc|ethereum|dogecoin|solana|xrp|etfs?|"
    r"(index|tracker|mutual) funds?|penny stocks?|meme stocks?|s&p( ?500)?|nasdaq|ftse( ?100)?|dow jones)\b"
)
_INVEST_CONTEXT = re.compile(
    r"\b(invest\w*|portfolio|ticker|price target|returns?|dividends?|trading|trade|market|isa|pension|grow my money|"
    r"my savings|my loan|stake|hold(ing)?s?)\b"
)


def _pick_context(msg: str) -> bool:
    return bool(_STRONG_ASSETS.search(msg) or _INVEST_CONTEXT.search(msg))


_OOS_RULES = [
    # Stock, fund and crypto picks (V6 V2-F3: widened).
    re.compile(
        rf"\b(which|what|best|top|good|hot)\b[^.?]*\b({_PICK_ASSETS})\b[^.?]*\b(buy|invest|pick|go up|moon|own|put)\b"
    ),
    re.compile(rf"\bshould i (buy|sell|short|invest in|get)\b[^.?]*\b({_PICK_ASSETS})\b"),
    re.compile(rf"\b(should|could|can) i (put|invest|move)\b[^.?]*\b(in|into)\b[^.?]*\b({_PICK_ASSETS})\b"),
    re.compile(rf"\brecommend\b[^.?]*\b({_PICK_ASSETS})\b"),
    re.compile(
        r"\b(which|what|best|top|cheapest) (\w+ )?(stock|share|fund|index fund|tracker|etf|coin|crypto|token)s? "
        r"(should|to|for|do|is|are|will|would|could)\b"
    ),
    re.compile(rf"\b({_PICK_ASSETS})\b[^.?]*\b(a )?good (investment|buy|bet)\b"),
    re.compile(
        r"\b(good investment|stock tips?|share tips?|price target|day trad(e|ing)|which crypto|"
        r"what crypto|to the moon)\b"
    ),
    # Regulated advice (pensions, tax returns, legal and medical).
    re.compile(
        r"\b(pension transfer|transfer my pension|defined benefit transfer|tax return|self[- ]assessment return|"
        r"legal advice|lawyer|solicitor|sue (my|the|him|her|them)|probate|power of attorney|medical advice|"
        r"diagnos(e|is))\b"
    ),
]
# Ticker after a buy or sell verb ("Should I buy NVDA"), checked on the original case. Not ISA-type words.
_TICKER = re.compile(r"\b(buy|sell|short|invest in|get)\s+\$?(?P<t>[A-Z]{2,5})\b")
_NOT_TICKERS = frozenset({"ISA", "ISAS", "LISA", "JISA", "UK", "US", "GBP", "USD", "EUR", "TV", "PC", "NHS", "BNPL",
                          "SIM", "MOT", "CV", "ID", "OK", "IT"})  # fmt: skip

# Output check (V6 V2-F3): an answer that tells the user to buy or sell a named asset is a pick.
# Output check: a pick names a specific asset, index, fund provider or ticker. Generic advice ("a tracker fund
# inside a stocks and shares ISA") is not a pick (V6 step 5).
_NAMED_ASSETS = (
    r"bitcoin|btc|ethereum|eth|dogecoin|solana|xrp|tesla|apple|nvidia|amazon|microsoft|google|alphabet|meta|"
    r"gamestop|gold|silver|s&p( ?500)?|nasdaq|ftse( ?100| ?250)?|dow jones|vanguard|ishares|blackrock|fidelity|"
    r"hargreaves|lansdown|trading ?212|freetrade|etoro|robinhood|invesco|hsbc ftse|l&g|legal (and|&) general"
)
_PICK_OUT = re.compile(
    rf"\b(buy|sell|short|invest in|put (your |the |some )?(money|savings|loan|cash)? ?(in|into)|go for|pick|"
    rf"get some|load up on|back)\b[^.]*\b({_NAMED_ASSETS})\b"
)
_ISA_NAMES = re.compile(r"\bstocks? (and|&) shares? (lifetime )?isas?\b|\bcash isas?\b")

# Distress (ADR 0051, V6 V2-F2): a kind reply with support contacts. Errs on the side of care.
_DISTRESS = re.compile(
    r"\b(kill (my ?self|me)|kms|suicid\w*|end(ing)? (it all|my life)|end(ing)? things(?! (off )?(with|between))|"
    r"(want to|wanna|wanting to|going to) die|"
    r"wish i (was|were) dead|don'?t (want|wanna) to (live|be here|be alive|exist)|not want to be alive|"
    r"self[- ]?harm\w*|hurt(ing)? my ?self|harm(ing)? my ?self|"
    r"can'?t (cope|go on|carry on|take (it|this) anymore)|cannot (cope|go on)|no way out|"
    r"(no|nothing) (point|reason) (in )?(living|going on)|hopeless|in crisis|"
    r"can'?t afford (to eat|food|groceries|my rent|rent)|(no|run out of) money for (food|rent)|"
    r"(haven'?t|have not|'ve not|not) eaten( in| for)? (\w+ )?(days?|two|three)|haven'?t eaten|going hungry|"
    r"bailiffs?|about to be evicted|being evicted|evict(ed|ing) me)\b"
)


def _norm(text: str) -> str:
    """NFKC, drop control and format characters (zero-width, bidi, tags), lower case, straight apostrophes."""
    out = unicodedata.normalize("NFKC", text)
    out = "".join(ch for ch in out if unicodedata.category(ch) not in {"Cc", "Cf"} and ch not in _ZERO_WIDTH)
    return out.lower().replace("’", "'").replace("‘", "'")


def out_of_scope_rule(message: str) -> bool:
    """Deterministic refusal (stock picks, regulated advice), before any LLM call."""
    msg = _norm(message)
    if any(r.search(msg) for r in _OOS_RULES[-1:]):
        return True  # regulated advice
    if any(r.search(msg) for r in _OOS_RULES[:-1]) and _pick_context(msg):
        return True
    clean = unicodedata.normalize("NFKC", message)
    return any(m.group("t") not in _NOT_TICKERS for m in _TICKER.finditer(clean))


def gives_pick(text: str) -> bool:
    """True when an answer tells the user to buy or sell a named share, fund, ETF, coin or ticker."""
    msg = _ISA_NAMES.sub("cash savings", _norm(text))
    if _PICK_OUT.search(msg) and _pick_context(msg):
        return True
    return any(m.group("t") not in _NOT_TICKERS for m in _TICKER.finditer(unicodedata.normalize("NFKC", text)))


def distress_rule(message: str) -> bool:
    """Deterministic distress check (ADR 0051): before the LLM on the user text, after it on the answer."""
    return bool(_DISTRESS.search(_norm(message)))


def quick_reaction(request: ChatRequest) -> Reaction:
    """A cheap first reaction for the UI before the answer arrives (ADR 0031: within 1 s). Heuristic only."""
    if distress_rule(request.message):
        return "eyes"
    if out_of_scope_rule(request.message):
        return "shrug"
    msg = request.message.lower()
    if re.search(r"\b(what if|replay|test|project|forecast|lose my job|next move|should i|budget)\b", msg):
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
