"""Demo trace of one Penny answer (ADR 0075): a recorder the turn writes steps into.

The route passes a `Recorder` in `ChatToolContext.trace`; `chat.Penny` adds a step at each stage: scope, each tool
call and result, each draft, each number check, each rewrite or fallback. The route adds the final step.

Never recorded: keys, tokens, headers, the system prompt, raw prompts or model messages. Tool arguments and results
are the caller's own data (the route serves the caller only).
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Sequence
from typing import Any

from lifeline_contracts.chat import ChatFact, ChatSource, TraceStep
from lifeline_contracts.forecast import Forecast, WhatIfResult
from lifeline_explain.verifier import Found, extract_numbers, fact_matches

MAX_FACTS = 40
MAX_TEXT = 600


def _short(text: str, limit: int = MAX_TEXT) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _jsonable(value: Any, depth: int = 0) -> Any:
    """Plain JSON (str, number, bool, None, list, dict), cut to a sane size."""
    if depth > 5:
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return _short(value) if isinstance(value, str) else value
    if isinstance(value, dict):
        return {str(k)[:60]: _jsonable(v, depth + 1) for k, v in list(value.items())[:40]}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v, depth + 1) for v in list(value)[:40]]
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return _jsonable(dump(mode="json"), depth + 1)
    return _short(str(value), 200)


def forecast_inputs(fc: Forecast) -> dict[str, Any]:
    """The inputs the engine used for one forecast, each with its source (ADR 0075 addition 1)."""
    return {
        "as_of": fc.meta.as_of,
        "money_now": {"amount": fc.money_now, "source": "statement", "balance_date": fc.meta.as_of,
                      "accounts": [{"name": a.name, "balance": a.balance, "counted": a.counted}
                                   for a in fc.accounts if a.counted]},
        "bills": [{"name": b.name, "amount": b.amount, "due_date": b.due_date, "source": "statement"}
                  for b in fc.bills[:12]],
        "next_money": None if fc.next_money is None else {
            "label": fc.next_money.label, "amount": fc.next_money.amount, "date": fc.next_money.date,
            "source": "statement", "schedule": fc.next_money.source.label, "url": fc.next_money.source.url},
        "usual_spending": {"weekly": fc.usual_weekly, "source": "statement",
                           "weeks": [{"start": w.start, "end": w.end, "amount": w.amount} for w in fc.usual_weeks]},
        "buffer": {"pct": fc.buffer_pct, "amount": fc.buffer_amount, "source": "user setting"},
    }  # fmt: skip


def forecast_state(fc: Forecast) -> dict[str, Any]:
    return {"state": fc.state, "per_week": fc.per_week, "per_day": fc.per_day, "budget_period": fc.budget_period,
            "to_spend": fc.to_spend, "run_out_date": fc.run_out_date,
            "spare": fc.spare, "days": fc.days,
            "next_money_date": None if fc.next_money is None else fc.next_money.date}  # fmt: skip


class Recorder:
    """Collects TraceSteps for one answer. Times are milliseconds since the recorder was made."""

    def __init__(self, t0: float | None = None) -> None:
        self.t0 = time.monotonic() if t0 is None else t0
        self.steps: list[TraceStep] = []
        self.forecasts: dict[str, Forecast] = {}  # fact id prefix -> the Forecast behind it
        self.message = ""

    def ms(self) -> int:
        return max(0, int((time.monotonic() - self.t0) * 1000))

    def add(self, kind: str, label: str, data: dict[str, Any] | None = None, *, first: bool = False) -> None:
        step = TraceStep(kind=kind, elapsed_ms=self.ms(), label=_short(label, 120),  # type: ignore[arg-type]
                         data=_jsonable(data or {}))  # fmt: skip
        if first:
            self.steps.insert(0, step)
        else:
            self.steps.append(step)

    # ----- scope -----

    def scope(self, decision: str, check: str, reason: str = "", **extra: Any) -> None:
        """decision: money, student_life, declined or support. check: strict, relaxed or none."""
        self.steps = [s for s in self.steps if s.kind != "scope"]
        self.add("scope", f"{decision} -> {check}", {"decision": decision, "check": check, "reason": reason, **extra},
                 first=True)  # fmt: skip

    def scope_data(self) -> dict[str, Any]:
        return next((s.data for s in self.steps if s.kind == "scope"), {})

    # ----- tools -----

    def tool_call(self, name: str, args: Any, preload: bool = False) -> None:
        """`preload`: fetched before the first model call (speed); its facts go with the question."""
        self.add("tool_call", name, {"tool": name, "args": args if isinstance(args, dict) else {}, "preload": preload})

    def tool_result(self, name: str, out: Any, ok: bool, ms: int) -> None:
        data: dict[str, Any] = {"tool": name, "ok": ok, "duration_ms": ms}
        if out is not None:
            facts = list(getattr(out, "facts", []) or [])
            data["facts"] = [{"id": f.id, "label": f.label, "value": f.value, "unit": f.unit}
                             for f in facts[:MAX_FACTS]]  # fmt: skip
            raw = getattr(out, "raw", None)
            if isinstance(raw, WhatIfResult):
                self.forecasts["whatif.before"] = raw.before
                self.forecasts["whatif.after"] = raw.after
                data["changes"] = [c.model_dump(mode="json", exclude_none=True) for c in raw.changes]
                data["before"] = forecast_state(raw.before)
                data["after"] = forecast_state(raw.after)
                data["inputs"] = forecast_inputs(raw.before)
            elif isinstance(raw, Forecast):
                self.forecasts["forecast"] = raw
                data["after"] = forecast_state(raw)
                data["inputs"] = forecast_inputs(raw)
        self.add("tool_result", name, data)

    # ----- drafts and checks -----

    def draft(self, bubbles: Sequence[tuple[str, str]], note: str = "") -> None:
        self.add("draft", note or "draft", {"bubbles": [{"kind": k, "text": t} for k, t in bubbles]})

    def verify(self, bubbles: Sequence[tuple[str, str]], facts: Sequence[ChatFact],
               sources: dict[str, ChatSource], mode: str, ok: bool, bad: Iterable[str] = ()) -> None:  # fmt: skip
        numbers = number_checks(bubbles, facts, sources, self.message, self.forecasts, mode, set(bad))
        self.add("verify", "pass" if ok else "fail", {"mode": mode, "result": "pass" if ok else "fail",
                                                      "numbers": numbers})  # fmt: skip

    def rewrite(self, reason: str, bad: Iterable[str] = (), fallback: bool = False) -> None:
        self.add("rewrite", "fallback" if fallback else "rewrite",
                 {"reason": reason, "bad": list(bad)[:12], "fallback": fallback})  # fmt: skip

    def final(self, total_ms: int, first_bubble_ms: int | None, sources_used: list[str]) -> None:
        self.add("final", "answer", {"total_ms": total_ms, "first_bubble_ms": first_bubble_ms,
                                     "sources_used": sources_used})  # fmt: skip


# ---------- where each number came from ----------


def _forecast_detail(fid: str, forecasts: dict[str, Forecast]) -> dict[str, Any]:
    """Statement line or engine field behind a forecast fact id ('forecast.bill.0.amount')."""
    for prefix, fc in forecasts.items():
        if not fid.startswith(prefix + "."):
            continue
        rest = fid[len(prefix) + 1 :]
        parts = rest.split(".")
        if parts[0] == "bill" and len(parts) > 1 and parts[1].isdigit() and int(parts[1]) < len(fc.bills):
            b = fc.bills[int(parts[1])]
            return {"where": "statement", "date": b.due_date, "merchant": b.name, "amount": b.amount}
        if parts[0] == "account" and len(parts) > 1 and parts[1].isdigit() and int(parts[1]) < len(fc.accounts):
            a = fc.accounts[int(parts[1])]
            return {"where": "statement", "date": fc.meta.as_of, "merchant": a.name, "amount": a.balance}
        if parts[0] == "usual_week" and len(parts) > 1 and parts[1].isdigit() and int(parts[1]) < len(fc.usual_weeks):
            w = fc.usual_weeks[int(parts[1])]
            return {"where": "statement", "date": f"{w.start} to {w.end}", "merchant": "spending that week",
                    "amount": w.amount}  # fmt: skip
        if parts[0] == "next_money" and fc.next_money is not None:
            return {"where": "official" if fc.next_money.source.url else "statement",
                    "name": fc.next_money.source.label, "url": fc.next_money.source.url,
                    "field": f"{prefix}.next_money"}  # fmt: skip
        if parts[0] == "buffer_pct":
            return {"where": "input", "field": "buffer_pct", "note": "user setting"}
        return {"where": "engine", "field": f"{prefix}.{parts[0]}"}
    return {}


def _rule_checked(fid: str) -> str | None:
    try:
        from lifeline_engine import rules
    except Exception:
        return None
    hit = next((r for r in rules.FACTS if r.id == fid.split("~")[0]), None)
    return hit.checked if hit is not None else None


def match_detail(fact: ChatFact, sources: dict[str, ChatSource], forecasts: dict[str, Forecast]) -> dict[str, Any]:
    fid = fact.id
    src = sources.get(fact.source_id or "")
    if fid.startswith("whatif.change."):
        return {"where": "input", "field": fid, "label": fact.label}
    if fid.startswith(("forecast.", "whatif.")):
        detail = _forecast_detail(fid, forecasts)
        if detail:
            return {**detail, "label": fact.label}
        return {"where": "engine", "field": fid, "label": fact.label}
    if fid.startswith("rule."):
        return {"where": "official", "name": fact.label, "url": src.url if src else None,
                "checked": _rule_checked(fid)}  # fmt: skip
    if fid.startswith("web."):
        return {"where": "official", "name": src.label if src else fact.label, "url": src.url if src else None}
    if src is not None and src.group == "live_sources":
        return {"where": "live", "name": src.label, "field": fid, "label": fact.label}
    if src is not None and src.group == "your_data":
        return {"where": "engine", "field": fid, "label": fact.label}
    return {"where": "engine", "field": fid, "label": fact.label}


def _input_number(found: Found, message: str) -> bool:
    return any(abs(n.value - found.value) < 1e-9 for n in extract_numbers(message))


def number_checks(
    bubbles: Sequence[tuple[str, str]], facts: Sequence[ChatFact], sources: dict[str, ChatSource], message: str,
    forecasts: dict[str, Forecast], mode: str, bad: set[str],
) -> list[dict[str, Any]]:
    """Each number in the bubbles: where it matched (engine, input, statement, official, live, general) and
    pass or fail."""
    out: list[dict[str, Any]] = []
    for kind, text in bubbles:
        for found in extract_numbers(text):
            fact = next((f for f in facts if fact_matches(found, f.value, f.unit)), None)
            if fact is not None:
                detail = match_detail(fact, sources, forecasts)
            elif _input_number(found, message):
                detail = {"where": "input", "field": "your question"}
            elif kind == "general_knowledge" or mode == "general":
                detail = {"where": "general", "note": "general number (relaxed check)"}
            else:
                detail = {"where": "none"}
            ok = found.raw not in bad and detail["where"] != "none"
            shown = f"£{found.raw}" if found.kind == "gbp" and not found.raw.startswith("£") else found.raw
            out.append({"number": shown, "pass": ok, **detail})
            if len(out) >= MAX_FACTS:
                return out
    return out
