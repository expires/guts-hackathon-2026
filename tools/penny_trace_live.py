"""Live trace of every Penny answer on the server, for the judges' demo. Run from services/api:

    uv run python ../../tools/penny_trace_live.py --base https://<server>

Connects to GET /v1/chat/trace/live (Server-Sent Events) and prints each finished answer in the same format as
tools/penny_trace.py, with the local time, the screen and the student first. Reconnects when the stream drops.
Ctrl-C exits.

The server must run with PENNY_TRACE_ENABLED=1 and PENNY_TRACE_TOKEN set. This tool reads the token from the
environment variable PENNY_TRACE_TOKEN, or else from that one key in the repo-root .env. It never prints the token,
keys, headers or prompts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from penny_trace import render, scrub  # noqa: E402

TOKEN_KEY = "PENNY_TRACE_TOKEN"  # noqa: S105 (the env var name, not a value)
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
RULE = "─" * 72
_MOCK = re.compile(r"\bmock\b", re.IGNORECASE)
SCREENS = {"penny_tab": "Penny tab", "trace_tool": "trace tool", "money": "Money", "next_move": "next move",
           "why": "why sheet", "life_event": "life event", "life": "Life", "onboarding": "onboarding",
           "room_round": "room round", "test_it": "Try Penny", "learn_lesson": "lesson", "forecast": "what-if",
           "other": "other"}  # fmt: skip


class Stop(Exception):
    """The server said no (404 or 401). Reconnecting will not help."""


def read_token(env_file: Path = ENV_FILE) -> str:
    """PENNY_TRACE_TOKEN from the environment, or only that key from .env. Never printed."""
    value = os.environ.get(TOKEN_KEY, "").strip()
    if value or not env_file.is_file():
        return value
    for raw in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, val = line.partition("=")
        if sep and key.strip() == TOKEN_KEY:
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            return val.strip()
    return ""


def sample_words(text: str) -> str:
    """Demo output says "sample", never "mock"."""
    return _MOCK.sub(lambda m: "Sample" if m.group(0)[0].isupper() else "sample", text)


def local_time(iso: Any) -> str:
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone().strftime("%H:%M:%S")
    except ValueError:
        return datetime.now().strftime("%H:%M:%S")


def header(item: dict[str, Any]) -> str:
    screen = str(item.get("screen") or "?")
    return f"{local_time(item.get('time'))} · {SCREENS.get(screen, screen)} · {item.get('student') or 'a student'}"


def show(item: dict[str, Any], colour: bool = False) -> str:
    """One trace as terminal text: separator, time · screen · student, then the penny_trace format."""
    body = render(item, str(item.get("student") or "a student"), colour=colour)
    return sample_words(scrub("\n".join([RULE, header(item), RULE, body, ""])))


def parse_sse(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """Each `event: trace` JSON from SSE lines. Comments (keepalive) and other events are skipped."""
    event, data = "", []
    for line in lines:
        if line == "":
            if event == "trace" and data:
                try:
                    item = json.loads("\n".join(data))
                except ValueError:
                    item = None
                if isinstance(item, dict):
                    yield item
            event, data = "", []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())


def stream(base: str, token: str, last: int, colour: bool) -> None:
    import httpx

    auth = {"Authorization": "Bearer " + token}  # kept in memory only, never printed
    timeout = httpx.Timeout(10.0, read=45.0)  # the server sends a keepalive every 15 s
    with httpx.Client(base_url=base.rstrip("/"), timeout=timeout) as client, \
            client.stream("GET", "/v1/chat/trace/live", headers=auth, params={"last": last}) as r:  # fmt: skip
        if r.status_code == 404:
            raise Stop("Live trace is off. Start the server with PENNY_TRACE_ENABLED=1 and PENNY_TRACE_TOKEN set.")
        if r.status_code == 401:
            raise Stop("The server did not accept the trace token. Check PENNY_TRACE_TOKEN.")
        if r.status_code != 200:
            raise ConnectionError(f"status {r.status_code}")
        print(f"Connected to {base}. Waiting for Penny answers. Ctrl-C to stop.", file=sys.stderr)
        for item in parse_sse(r.iter_lines()):
            print(show(item, colour), flush=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Live trace of every Penny answer (judges' demo)")
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--last", type=int, default=0, help="old traces to show first (0 to 50)")
    p.add_argument("--no-colour", action="store_true")
    a = p.parse_args(argv)
    token = read_token()
    if not token:
        print(f"Set {TOKEN_KEY} in your environment or in .env.", file=sys.stderr)
        return 1
    colour = not a.no_colour and sys.stdout.isatty()
    last = max(0, min(50, a.last))
    wait = 1.0
    try:
        while True:
            try:
                stream(a.base, token, last, colour)
                wait = 1.0
                print("Stream closed. Reconnecting.", file=sys.stderr)
                time.sleep(1.0)
            except Stop as exc:
                print(str(exc), file=sys.stderr)
                return 1
            except Exception as exc:  # network drop, timeout, server restart
                print(f"Stream dropped ({type(exc).__name__}). Reconnecting in {wait:.0f} s.", file=sys.stderr)
                time.sleep(wait)
                wait = min(wait * 2, 15.0)
            last = 0  # after a reconnect, show only new answers
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
