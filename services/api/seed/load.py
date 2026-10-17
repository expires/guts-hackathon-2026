"""Load demo data into a running Lifeline API through its public HTTP contract.

Run:  python -m seed.load            (inside the api container: `make demo-seed`)
      LIFELINE_BASE_URL=http://localhost:8000 uv run python -m seed.load   (from services/api)

What it creates (see docs/DEMO.md):
  opening  Next Move for the presenter (GET /v1/next-move), Test it for the top move (POST /v1/next-move/test),
           and the top move in the plan (POST /v1/plan; skip with --no-plan)
  scene 1  nurse-leeds 2006 and banker-london 2006, fresh (to play live) and pre-aged to 2008 (fallback)
  scene 2  a Same Life room for 2021 (group mode, banker-london, who has a mortgage)
  scene 3  the pre-aged nurse life has past decisions to rewind (first decision_id is printed)
  scene 4  a "Play yourself" life from 2020 for the presenter's own profile (/v1/finance/profile), pre-aged to the
           present, plus one Real-life Decision call with that profile

The loader uses only contract endpoints. It never reads secrets. It prints a JSON manifest of the ids.
An endpoint that answers 501 not_implemented is skipped and listed under "skipped"; the exit code stays 0.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
# One device id for the seed, DEMO.md and the iOS app (`-demoDeviceID`). Lives belong to the token subject,
# so the presenter and the app must sign in with this id to see the seeded lives.
DEFAULT_DEVICE_ID = "demo-presenter-01"
DEMO_SEED = 424242
MAX_AGE_STEPS = 80
# The first Next Move call after a restart waits on LLM rewording (ADR 0019, 0022). Give it room.
SLOW_TIMEOUT_S = 120.0
# How long to wait for the API to come back when another process restarts the container mid-seed.
RESTART_WAIT_S = 90.0
# Total tries for a request that gets 429 (1 first try + 4 retries).
MAX_TRIES_429 = 5
MAX_EVENTS_PER_YEAR = 20

SELF_CHARACTER: dict[str, Any] = {
    "name": "Me",
    "emoji": "🙂",
    "sex": "female",
    "occupation": "teacher",
    "region": "yorkshire-and-the-humber",
    "town": "Leeds",
    "birth_year": 1992,
    "annual_income": 38000,
    "savings": 9000,
    "debt": 0,
    "housing": "mortgage",
    "property_value": 240000,
    "mortgage_balance": 180000,
}

DECISION_PROFILE: dict[str, Any] = {
    "age": 34,
    "region": "yorkshire-and-the-humber",
    "annual_income": 38000,
    "savings": 9000,
    "housing": "mortgage",
    "property_value": 240000,
    "mortgage_balance": 180000,
    "mortgage_years_left": 25,
    "deal_ends_in_months": 3,
}


class SeedError(RuntimeError):
    """A call to the API failed. The message carries the contract error body when there is one."""


class NotBuilt(SeedError):
    """The endpoint answered 501 not_implemented: the feature is not built in this tier."""


@dataclass
class Api:
    client: httpx.Client

    def call(self, method: str, path: str, expect: tuple[int, ...] = (200, 201), **kwargs: Any) -> Any:
        try:
            resp = self.client.request(method, path, **kwargs)
        except httpx.ConnectError:
            # The request was never sent (the api container is restarting). Wait for health, then send it once more.
            print(f"connection refused on {method} {path}; waiting for the API", file=sys.stderr)
            wait_for_health(self.client, RESTART_WAIT_S)
            resp = self.client.request(method, path, **kwargs)
        # 429: the server did not process the request, so a retry is safe. Honour Retry-After; at most 5 tries.
        for attempt in range(1, MAX_TRIES_429):
            if resp.status_code != 429:
                break
            wait = _retry_after(resp, default=2.0 * attempt)
            print(f"rate limited on {method} {path}; retry {attempt} in {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
            resp = self.client.request(method, path, **kwargs)
        if resp.status_code == 501:
            raise NotBuilt(f"{method} {path} -> 501: {_error_text(resp)}")
        if resp.status_code not in expect:
            raise SeedError(f"{method} {path} -> {resp.status_code}: {_error_text(resp)}")
        return resp.json()


def _retry_after(resp: httpx.Response, default: float) -> float:
    """Seconds from a numeric Retry-After header, capped at 60; `default` when missing or not a number."""
    try:
        return min(60.0, max(0.0, float(resp.headers.get("Retry-After", ""))))
    except ValueError:
        return default


def _error_text(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300]
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return f"{err.get('code')} ({err.get('source')}): {err.get('message')}"
    return json.dumps(body)[:300]


def wait_for_health(client: httpx.Client, timeout_s: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    last = "no response"
    while time.monotonic() < deadline:
        try:
            resp = client.get("/v1/health")
            if resp.status_code == 200:
                body: dict[str, Any] = resp.json()
                return body
            last = f"status {resp.status_code}"
        except httpx.HTTPError as exc:
            last = type(exc).__name__
        time.sleep(1.0)
    raise SeedError(f"API not healthy after {timeout_s:.0f}s ({last})")


def sign_in(api: Api, device_id: str) -> str:
    token = api.call("POST", "/v1/auth/demo", json={"device_id": device_id})
    return str(token["access_token"])


def create_life(api: Api, body: dict[str, Any]) -> dict[str, Any]:
    life: dict[str, Any] = api.call("POST", "/v1/lives", json=body)
    return life


def default_choice(event: dict[str, Any]) -> str:
    choices = event["choices"]
    for choice in choices:
        if choice.get("is_default"):
            return str(choice["id"])
    return str(choices[0]["id"])


def answer_pending(api: Api, life: dict[str, Any]) -> dict[str, Any]:
    """Answer every open event with its default choice (the autopilot path)."""
    for _ in range(MAX_EVENTS_PER_YEAR):
        pending = life.get("pending_events") or []
        if not pending:
            return life
        event = pending[0]
        result = api.call(
            "POST",
            f"/v1/lives/{life['id']}/choices",
            json={"event_id": event["id"], "choice_id": default_choice(event)},
        )
        life = result["life"]
    raise SeedError(f"life {life['id']}: too many open events in one year")


def age_until(api: Api, life: dict[str, Any], *, year: int | None = None, present: bool = False) -> dict[str, Any]:
    """Tap AGE and take default choices until the target year, the present, or death."""
    for _ in range(MAX_AGE_STEPS):
        life = answer_pending(api, life)
        if not life.get("alive", True):
            return life
        if year is not None and life["year"] >= year:
            return life
        if present and life.get("reached_present"):
            return life
        result = api.call("POST", f"/v1/lives/{life['id']}/age")
        life = result["life"]
    raise SeedError(f"life {life['id']}: target not reached in {MAX_AGE_STEPS} steps")


def first_decision_id(life: dict[str, Any]) -> str | None:
    for entry in life.get("history", []):
        if entry.get("decision_id"):
            return str(entry["decision_id"])
    return None


def life_row(life: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": life["id"],
        "name": life["character"]["name"],
        "preset_id": life["character"].get("id"),
        "year": life["year"],
        "age": life["age"],
        "net_worth": life["finances"]["net_worth"],
        "index": life["index"]["value"],
        "first_decision_id": first_decision_id(life),
    }


def run(base_url: str, timeout_s: float, skip_ageing: bool, device_id: str, add_plan: bool = True) -> dict[str, Any]:
    with httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=False) as client:
        health = wait_for_health(client, timeout_s)
        api = Api(client)
        client.headers["Authorization"] = f"Bearer {sign_in(api, device_id)}"

        manifest: dict[str, Any] = {
            "base_url": base_url,
            "device_id": device_id,
            "health": health.get("status"),
            "lives": {},
            "rooms": {},
            "skipped": [],
        }
        lives = manifest["lives"]

        def step(name: str, fn: Callable[[], None]) -> None:
            """Run one seed step. A 501 not_implemented skips the step; other errors stop the run."""
            try:
                fn()
            except NotBuilt as exc:
                print(f"skipped {name}: not built in this tier ({exc})", file=sys.stderr)
                manifest["skipped"].append({"step": name, "reason": str(exc)})

        # Opening: the Next Move story. Every value below is engine output for this device's finance snapshot.
        top_ids: list[str] = []

        def next_move() -> None:
            nm = api.call("GET", "/v1/next-move", timeout=SLOW_TIMEOUT_S)
            top = nm["top"]
            top_ids.append(top["id"])
            manifest["next_move"] = {
                "data_status": nm["meta"]["data_status"],
                "move_id": top["id"],
                "action": top["action"],
                "headline": top["headline"],
                "impact_per_year": top["impact_per_year"],
                "worst_case_per_year": top["worst_case_per_year"],
                "confidence_label": top["confidence_label"],
                "days_left": top.get("days_left"),
                "testable": top["testable"],
                "test_period": (top.get("test_period") or {}).get("label"),
                "options": [o["id"] + ("*" if o.get("is_recommended") else "") for o in top["options"]],
                "evidence": [e["text"] for e in top["evidence"]],
                "runners_up": [m["action"] for m in nm["runners_up"]],
            }

        def test_it() -> None:
            if not top_ids or not manifest["next_move"]["testable"]:
                return
            t = api.call("POST", "/v1/next-move/test", json={"move_id": top_ids[0]}, timeout=SLOW_TIMEOUT_S)
            manifest["next_move_test"] = {
                "period": t["period"]["label"],
                "summary": t["summary"],
                "outcomes": [
                    {
                        "option_id": o["option_id"],
                        "recommended": o["is_recommended"],
                        "life_id": o["life_id"],
                        "end_net_worth": o["end_net_worth"],
                        "total_cost": o["total_cost"],
                        "missed_payments": o["missed_payments"],
                    }
                    for o in t["outcomes"]
                ],
            }

        def plan() -> None:
            if not top_ids:
                return
            api.call("POST", "/v1/plan", json={"move_id": top_ids[0]})
            p = api.call("GET", "/v1/plan")
            manifest["plan"] = {
                "items": [i["action"] for i in p["items"]],
                "total_impact_per_year": p["total_impact_per_year"],
            }

        step("opening next move", next_move)
        step("opening test it", test_it)
        if add_plan:
            step("opening plan", plan)

        # Scene 1: same crash, different lives.
        for preset in ("nurse-leeds", "banker-london"):
            body = {"mode": "preset", "preset_id": preset, "start_year": 2006, "seed": DEMO_SEED}

            def fresh(preset: str = preset, body: dict[str, Any] = body) -> None:
                lives[f"{preset}-2006"] = life_row(create_life(api, body))

            def fallback(preset: str = preset, body: dict[str, Any] = body) -> None:
                lives[f"{preset}-2008-fallback"] = life_row(age_until(api, create_life(api, body), year=2008))

            step(f"scene1 {preset} 2006", fresh)
            if not skip_ageing:
                step(f"scene1 {preset} aged to 2008", fallback)

        # Scene 2: Same Life room for the 2021 to 2023 rate shock.
        def room() -> None:
            body = {"mode": "group", "host_name": "Host", "preset_id": "banker-london", "start_year": 2021}
            r = api.call("POST", "/v1/rooms", json=body)
            manifest["rooms"]["rate-shock-2021"] = {
                "code": r["code"],
                "join_url": r["join_url"],
                "seed": r["seed"],
                "status": r["status"],
            }

        step("scene2 room 2021", room)

        # Scene 4: Play yourself to today, then one Real-life Decision.
        # Use the presenter's own profile from the Money tab data (/v1/finance/profile), so the life, the decision and
        # the Next Move describe the same person. Fall back to the fixed values if the endpoint is not built.
        self_ids: list[str] = []
        profile: dict[str, Any] = {"character": SELF_CHARACTER, "profile": DECISION_PROFILE, "from": "fixed values"}

        def finance_profile() -> None:
            fp = api.call("GET", "/v1/finance/profile")
            profile.update(character=fp["character"], profile=fp["profile"], **{"from": "/v1/finance/profile"})

        step("scene4 finance profile", finance_profile)
        manifest["self_profile_from"] = profile["from"]

        def self_life() -> None:
            life = create_life(
                api, {"mode": "self", "start_year": 2020, "seed": DEMO_SEED, "character": profile["character"]}
            )
            self_ids.append(life["id"])
            lives["self-2020"] = life_row(life)
            if not skip_ageing:
                lives["self-2020"] = life_row(age_until(api, life, present=True))

        def decision() -> None:
            body: dict[str, Any] = {"profile": profile["profile"]}
            if self_ids:
                body["life_id"] = self_ids[0]
            d = api.call("POST", "/v1/decisions", json=body)
            manifest["decision"] = {
                "headline": d["headline"],
                "action": d["action"],
                "evidence": d["evidence"]["sentence"],
                "sources": [f"{s['source']}:{s['series_id']}={s['status']}" for s in d["sources"]],
            }

        step("scene4 self life to present", self_life)
        step("scene4 real-life decision", decision)
        return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m seed.load", description="Load Lifeline demo data via the API.")
    parser.add_argument("--base-url", default=os.environ.get("LIFELINE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument(
        "--device-id",
        default=os.environ.get("DEMO_DEVICE_ID", DEFAULT_DEVICE_ID),
        help="demo sign-in device id that owns the seeded lives (env DEMO_DEVICE_ID)",
    )
    parser.add_argument("--wait", type=float, default=60.0, help="seconds to wait for /v1/health")
    parser.add_argument("--no-ageing", action="store_true", help="create lives only; skip the pre-aged fallbacks")
    parser.add_argument("--no-plan", action="store_true", help="do not add the top move to the plan")
    parser.add_argument("--out", type=Path, help="also write the manifest JSON to this file")
    args = parser.parse_args(argv)

    try:
        manifest = run(args.base_url.rstrip("/"), args.wait, args.no_ageing, args.device_id, not args.no_plan)
    except (SeedError, httpx.HTTPError) as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(manifest, indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
