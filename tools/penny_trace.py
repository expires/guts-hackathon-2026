"""Demo trace of one real Penny answer (ADR 0075). Run from services/api:

    uv run python ../../tools/penny_trace.py --student eilidh --question "Can I afford a £60 concert on the 30th?"

Steps: sign in with a fresh demo device id, import the student's sample statement, call POST /v1/chat/trace, print
the steps. The server must run with PENNY_TRACE_ENABLED=1. The output never contains keys, tokens, headers or
prompts: the token stays in memory, and `render` scrubs anything that looks like a secret.
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

STUDENTS: dict[str, str] = {
    "eilidh": "scottish", "callum": "working", "amara": "scholarship", "priya": "commuter",
    "jordan": "loan_england", "grace": "mature", "yutong": "international", "sam": "final_year",
    "hugo": "rich", "lena": "graduate",
}  # fmt: skip
SAMPLE_IDS = frozenset(STUDENTS.values())
LONDON = ZoneInfo("Europe/London")
WIDTH = 10  # label column

COLOURS = {"label": "\033[1;36m", "ok": "\033[32m", "bad": "\033[31m", "dim": "\033[2m", "warn": "\033[33m",
           "reset": "\033[0m"}  # fmt: skip
_SECRET = re.compile(r"(?i)(bearer\s+\S+|sk-[A-Za-z0-9_-]{6,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9._-]+|"
                     r"(api[_-]?key|token|authorization|secret|password)\s*[:=]\s*\S+)")  # fmt: skip


def sample_id(student: str) -> str:
    key = student.strip().lower()
    if key in STUDENTS:
        return STUDENTS[key]
    if key in SAMPLE_IDS:
        return key
    raise SystemExit(f"Unknown student {student!r}. Use one of: {', '.join(sorted(STUDENTS))}")


def display_name(student: str) -> str:
    key = student.strip().lower()
    if key in STUDENTS:
        return key.capitalize()
    return next((n.capitalize() for n, s in STUDENTS.items() if s == key), student)


def scrub(text: str) -> str:
    return _SECRET.sub("[hidden]", text)


# ---------- formatting ----------


def money(v: Any) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    sign = "-" if x < 0 else ""
    x = abs(x)
    return f"{sign}£{x:,.0f}" if abs(x - round(x)) < 0.005 else f"{sign}£{x:,.2f}"


def day(iso: Any) -> str:
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso)
    return f"{d.day} {d.strftime('%b')}"


def hhmm(iso: Any) -> str:
    if not iso:
        return "--:--"
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return "--:--"
    if t.hour == t.minute == t.second == 0 and t.utcoffset() is not None and not t.utcoffset():
        return day(iso)  # a date only (statement date, facts checked date)
    return t.astimezone(LONDON).strftime("%H:%M")


def secs(ms: Any) -> str:
    return "?" if ms is None else f"{int(ms) / 1000:.1f} s"


def _arg(key: str, value: Any) -> str:
    if key in {"amount", "one_off_cost"} or key.endswith("_amount"):
        return f"{key}={money(value)}"
    if key == "date" or key.endswith("_date"):
        return f"{key}={day(value)}"
    return f"{key}={value}"


def tool_args(args: dict[str, Any]) -> str:
    """forecast_what_if changes print as 'one_off_cost=£60, date=30 Oct'; other tools as key=value."""
    parts: list[str] = []
    for ch in args.get("changes") or []:
        if not isinstance(ch, dict):
            continue
        kind = str(ch.get("kind") or "change")
        bits = [f"{kind}={money(ch['amount'])}" if ch.get("amount") is not None else kind]
        if ch.get("date"):
            bits.append(f"date={day(ch['date'])}")
        if ch.get("target"):
            bits.append(f"target={ch['target']}")
        parts.append(", ".join(bits))
    parts += [_arg(k, v) for k, v in args.items() if k != "changes" and not isinstance(v, (dict, list))]
    return "; ".join(parts)


def state_line(s: dict[str, Any]) -> str:
    status = {"on_track": "on track", "running_short": "running short"}.get(str(s.get("state")), str(s.get("state")))
    line = f"{money(s.get('per_week'))}/week, {status}"
    if s.get("run_out_date"):
        line += f", runs out {day(s['run_out_date'])}"
    return line


class Out:
    def __init__(self, colour: bool) -> None:
        self.colour = colour
        self.lines: list[str] = []

    def c(self, name: str, text: str) -> str:
        return f"{COLOURS[name]}{text}{COLOURS['reset']}" if self.colour else text

    def line(self, label: str, text: str) -> None:
        pad = WIDTH if len(label) < WIDTH else len(label) + 2
        self.lines.append(self.c("label", label.ljust(pad)) + scrub(text))

    def more(self, text: str) -> None:
        self.lines.append(" " * WIDTH + scrub(text))


def _sources_block(out: Out, hub: dict[str, Any]) -> None:
    first = True
    for s in hub.get("sources") or []:
        latest = s.get("latest") or []
        values = ", ".join(f"{v.get('label')} {v.get('value')}" for v in latest) or "no number shown"
        status = str(s.get("status"))
        tone = "ok" if status == "live" else "warn" if status in {"cached", "mock"} else "dim"
        text = f"{s.get('name')} · {out.c(tone, status)} · {hhmm(s.get('updated_at'))} · {values}"
        if first:
            out.line("SOURCES", text)
            first = False
        else:
            out.more(text)


def _engine_inputs(out: Out, inp: dict[str, Any]) -> None:
    mn = inp.get("money_now") or {}
    accounts = ", ".join(f"{a.get('name')} {money(a.get('balance'))}" for a in mn.get("accounts") or [])
    when = day(mn.get("balance_date"))
    out.more(f"money now   {money(mn.get('amount'))} · statement · {accounts} · balance on {when}")
    for b in inp.get("bills") or []:
        out.more(f"bill        {money(b.get('amount'))} · statement · {b.get('name')} · due {day(b.get('due_date'))}")
    nm = inp.get("next_money")
    if nm:
        out.more(f"next money  {money(nm.get('amount'))} on {day(nm.get('date'))} · statement + {nm.get('schedule')}")
    us = inp.get("usual_spending") or {}
    weeks = ", ".join(f"{day(w.get('start'))}-{day(w.get('end'))}" for w in us.get("weeks") or [])
    out.more(f"usual       {money(us.get('weekly'))}/week · statement · weeks {weeks}")
    buf = inp.get("buffer") or {}
    out.more(f"buffer      {buf.get('pct')}% ({money(buf.get('amount'))}) · user setting")


def _where(n: dict[str, Any]) -> str:
    w = n.get("where")
    if w == "statement":
        return f"statement {n.get('date')} · {n.get('merchant')} · {money(n.get('amount'))}"
    if w == "official":
        bits = [str(n.get("name") or "official fact")]
        if n.get("url"):
            bits.append(str(n["url"]))
        if n.get("checked"):
            bits.append(f"checked {n['checked']}")
        return "official · " + " · ".join(bits)
    if w == "engine":
        return f"engine {n.get('field')}"
    if w == "input":
        return f"input ({n.get('field') or 'your question'})"
    if w == "live":
        return f"live · {n.get('name')}"
    if w == "general":
        return "general number (relaxed check)"
    return "no match"


def render(trace: dict[str, Any], student: str | None = None, colour: bool = True) -> str:
    """The terminal view of a ChatTrace JSON. Pure: no network, no secrets."""
    out = Out(colour)
    steps = list(trace.get("steps") or [])
    scope = next((s.get("data") or {} for s in steps if s.get("kind") == "scope"), {})
    if scope.get("sources"):
        _sources_block(out, scope["sources"])
    who = student or trace.get("student") or "?"
    out.line("QUESTION", f"\"{trace.get('question', '')}\"   student: {who}")
    answer = trace.get("answer") or {}
    for s in steps:
        kind, data = s.get("kind"), s.get("data") or {}
        if kind == "scope":
            decision = str(data.get("decision", "?")).replace("_", " ")
            if decision == "declined":
                chips = " · ".join(answer.get("suggestions") or [])
                out.line("SCOPE", f"declined → the friendly line + 2 chips ({data.get('reason', '')})")
                if chips:
                    out.more(f"chips: {chips}")
            else:
                check = {"strict": "strict number check", "relaxed": "relaxed check"}.get(str(data.get("check")),
                                                                                         str(data.get("check")))
                out.line("SCOPE", f"{decision} → {check}")
        elif kind == "tool_call":
            note = "   (preloaded with the question)" if data.get("preload") else ""
            out.line("TOOL", f"{data.get('tool')}({tool_args(data.get('args') or {})}){note}")
        elif kind == "tool_result":
            if "before" in data:
                out.line("ENGINE", f"before: {state_line(data['before'])}   after: {state_line(data['after'])}")
            elif "after" in data:
                out.line("ENGINE", f"{data.get('tool')}: {state_line(data['after'])}")
            else:
                n = len(data.get("facts") or [])
                ok = "ok" if data.get("ok") else "failed"
                out.line("ENGINE", f"{data.get('tool')}: {ok}, {n} facts in {data.get('duration_ms')} ms")
            if data.get("inputs"):
                out.more("inputs the engine used:")
                _engine_inputs(out, data["inputs"])
        elif kind == "draft":
            for i, b in enumerate(data.get("bubbles") or []):
                text = str(b.get("text", ""))
                text = text if len(text) <= 90 else text[:87] + "..."
                if i == 0:
                    out.line("DRAFT", f"\"{text}\"")
                else:
                    out.more(f"\"{text}\"")
            if not data.get("bubbles"):
                out.line("DRAFT", f"({s.get('label')})")
        elif kind == "verify":
            nums = data.get("numbers") or []
            result = str(data.get("result", "")).upper()
            if not nums:
                out.line("VERIFY", f"no numbers → {out.c('ok' if result == 'PASS' else 'bad', result)}")
                continue
            for i, n in enumerate(nums):
                mark = out.c("ok", "✓") if n.get("pass") else out.c("bad", "✗")
                text = f"{n.get('number')} {mark} {_where(n)}"
                if i == 0:
                    out.line("VERIFY", text)
                else:
                    out.more(text)
            out.more(f"→ {out.c('ok' if result == 'PASS' else 'bad', result)}")
        elif kind == "rewrite":
            what = "fallback" if data.get("fallback") else "rewrite"
            bad = ", ".join(map(str, data.get("bad") or []))
            out.line("REWRITE", out.c("warn", f"{what}: {data.get('reason')}" + (f" ({bad})" if bad else "")))
        elif kind == "final":
            first_ms = secs(data.get("first_bubble_ms"))
            out.line("ANSWER", f"sent in {secs(data.get('total_ms'))} (first bubble {first_ms})")
            for b in answer.get("bubbles") or []:
                out.more(f"\"{b.get('text', '')}\"")
            used = data.get("sources_used") or []
            used = used or ["none (no number needed a source)"]
            out.line("SOURCES USED", used[0])
            for u in used[1:]:
                out.more(u)
    return "\n".join(out.lines)


# ---------- network ----------


def main(argv: list[str] | None = None) -> int:
    import httpx

    p = argparse.ArgumentParser(description="Demo trace of one Penny answer (ADR 0075)")
    p.add_argument("--student", required=True, help="first name (eilidh, callum, ...) or sample id")
    p.add_argument("--question", required=True)
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--language", default="en")
    p.add_argument("--no-colour", action="store_true")
    a = p.parse_args(argv)
    sid = sample_id(a.student)
    with httpx.Client(base_url=a.base.rstrip("/"), timeout=60) as client:
        r = client.post("/v1/auth/demo", json={"device_id": f"trace-{uuid.uuid4().hex[:16]}"})
        if r.status_code != 200:
            print(f"Sign-in failed ({r.status_code}).", file=sys.stderr)
            return 1
        auth = {"Authorization": "Bearer " + r.json()["access_token"]}  # kept in memory only, never printed
        r = client.post(f"/v1/samples/{sid}/import", headers=auth)
        if r.status_code not in {200, 201}:
            print(f"Sample import failed ({r.status_code}).", file=sys.stderr)
            return 1
        r = client.post("/v1/chat/trace", headers=auth, json={"message": a.question, "language": a.language})
        if r.status_code == 404:
            print("The trace route is off. Start the server with PENNY_TRACE_ENABLED=1.", file=sys.stderr)
            return 1
        if r.status_code != 200:
            print(f"Trace failed ({r.status_code}).", file=sys.stderr)
            return 1
        print(render(r.json(), display_name(a.student), colour=not a.no_colour and sys.stdout.isatty()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
