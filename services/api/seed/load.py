"""Load demo data into a running Lifeline API through its public HTTP contract.

Run:  python -m seed.load            (inside the api container: `make demo-seed`)
      LIFELINE_BASE_URL=http://localhost:8000 uv run python -m seed.load   (from services/api)

What it creates (see docs/DEMO.md):
  scene 1  nurse-leeds 2006 and banker-london 2006, fresh (to play live) and pre-aged to 2008 (fallback)
  scene 2  a Same Life room for 2021 (group mode, banker-london, who has a mortgage)
  scene 3  the pre-aged nurse life has past decisions to rewind (first decision_id is printed)
  scene 4  a "Play yourself" life from 2020, pre-aged to the present, plus one Real-life Decision call

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
        resp = self.client.request(method, path, **kwargs)
        if resp.status_code == 501:
            raise NotBuilt(f"{method} {path} -> 501: {_error_text(resp)}")
        if resp.status_code not in expect:
            raise SeedError(f"{method} {path} -> {resp.status_code}: {_error_text(resp)}")
        return resp.json()


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


def run(base_url: str, timeout_s: float, skip_ageing: bool, device_id: str) -> dict[str, Any]:
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
        self_ids: list[str] = []

        def self_life() -> None:
            life = create_life(
                api, {"mode": "self", "start_year": 2020, "seed": DEMO_SEED, "character": SELF_CHARACTER}
            )
            self_ids.append(life["id"])
            lives["self-2020"] = life_row(life)
            if not skip_ageing:
                lives["self-2020"] = life_row(age_until(api, life, present=True))

        def decision() -> None:
            body: dict[str, Any] = {"profile": DECISION_PROFILE}
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
    parser.add_argument("--out", type=Path, help="also write the manifest JSON to this file")
    args = parser.parse_args(argv)

    try:
        manifest = run(args.base_url.rstrip("/"), args.wait, args.no_ageing, args.device_id)
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
