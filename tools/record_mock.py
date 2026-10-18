"""Record real API responses for the iOS Mock configuration. BOSS-owned.

Usage (stack running):  cd services/api && uv run python ../../tools/record_mock.py
Writes apps/ios/Lifeline/Preview/Recorded/<operationId>.json (one real response per endpoint)
plus manifest.json. MockClient serves these, so the phone shows engine output, not contract examples.
Device id defaults to demo-presenter-03 (pinned to the demo persona; plan stays empty).

--bundled (ADR 0060): instead writes fixed content to apps/ios/Lifeline/Resources/Bundled/bundled-<key>.json
(characters, student paths, concepts and lessons, challenges, sample students). Sources are not bundled:
their live/cached status must come from the server. The app seeds its
disk cache from these files on first launch. Each file holds the value the iOS client method returns
(for list endpoints the inner array), so `DiskCache` decodes it directly.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

BASE = os.environ.get("LIFELINE_BASE_URL", "http://localhost:8000")
DEVICE = os.environ.get("DEMO_DEVICE_ID", "demo-presenter-03")
OUT = Path(__file__).resolve().parents[1] / "apps" / "ios" / "Lifeline" / "Preview" / "Recorded"
BUNDLED = Path(__file__).resolve().parents[1] / "apps" / "ios" / "Lifeline" / "Resources" / "Bundled"

# key (CachedOps.<x>.key in DiskCache.swift) -> (path, field to unwrap or None for the whole body)
BUNDLED_OPS: dict[str, tuple[str, str | None]] = {
    "listCharacters": ("/v1/characters", None),
    "listPathsResponse": ("/v1/paths", None),
    "listConcepts": ("/v1/concepts", "concepts"),
    "listChallenges": ("/v1/challenges", "challenges"),
    "listSamples": ("/v1/samples", "samples"),
}


def call(c: httpx.Client, method: str, path: str, **kw: Any) -> httpx.Response:
    for attempt in range(6):
        r = c.request(method, path, **kw)
        if r.status_code != 429:
            return r
        time.sleep(min(float(r.headers.get("retry-after", 2 * (attempt + 1))), 30))
    return r


def record_bundled() -> int:
    BUNDLED.mkdir(parents=True, exist_ok=True)
    failed = 0
    with httpx.Client(base_url=BASE, timeout=180) as c:
        tok = call(c, "POST", "/v1/auth/demo", json={"device_id": DEVICE}).json()["access_token"]
        c.headers["Authorization"] = f"Bearer {tok}"
        for key, (path, field) in BUNDLED_OPS.items():
            r = call(c, "GET", path)
            if r.status_code >= 400:
                print(f"skip {key}: {r.status_code}", file=sys.stderr)
                failed += 1
                continue
            body = r.json()
            value = body[field] if field else body
            (BUNDLED / f"bundled-{key}.json").write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
            print(f"ok   {key}")
    print(f"wrote {BUNDLED}")
    return 1 if failed else 0


def main() -> int:
    if "--bundled" in sys.argv[1:]:
        return record_bundled()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"base": BASE, "device_id": DEVICE, "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "files": {}}
    with httpx.Client(base_url=BASE, timeout=180) as c:
        tok = call(c, "POST", "/v1/auth/demo", json={"device_id": DEVICE}).json()["access_token"]
        c.headers["Authorization"] = f"Bearer {tok}"

        def save(op: str, r: httpx.Response) -> Any:
            if r.status_code >= 400:
                manifest["files"][op] = {"status": r.status_code, "skipped": True}
                print(f"skip {op}: {r.status_code}", file=sys.stderr)
                return None
            body = r.json()
            (OUT / f"{op}.json").write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n")
            manifest["files"][op] = {"status": r.status_code}
            print(f"ok   {op}")
            return body

        save("listSources", call(c, "GET", "/v1/sources"))
        save("listCharacters", call(c, "GET", "/v1/characters", params={"seed": 424242}))
        save("listConcepts", call(c, "GET", "/v1/concepts"))
        save("getEvaluation", call(c, "GET", "/v1/evaluation"))
        for op, path in [
            ("getFinanceOverview", "/v1/finance/overview"),
            ("getFinanceSpending", "/v1/finance/spending"),
            ("listSubscriptions", "/v1/finance/subscriptions"),
            ("listBills", "/v1/finance/bills"),
            ("listBudgets", "/v1/finance/budgets"),
            ("listGoals", "/v1/finance/goals"),
            ("getFinanceProfile", "/v1/finance/profile"),
            ("getPredictionEvaluation", "/v1/finance/prediction/evaluation"),
            ("listGuesses", "/v1/finance/guesses"),
            ("getPlan", "/v1/plan"),
        ]:
            save(op, call(c, "GET", path))
        save("getSpendPrediction", call(c, "GET", "/v1/finance/prediction"))
        nm = save("getNextMove", call(c, "GET", "/v1/next-move"))
        if nm:
            testable = next((m for m in [nm["top"], *nm["runners_up"]] if m.get("testable")), None)
            if testable:
                save("testNextMove", call(c, "POST", "/v1/next-move/test", json={"move_id": testable["id"]}))
        prof = json.loads((OUT / "getFinanceProfile.json").read_text()) if (OUT / "getFinanceProfile.json").exists() else None
        if prof:
            life = save("createLife", call(c, "POST", "/v1/lives", json={"mode": "self", "start_year": 2026, "character": prof["character"]}))
            if life:
                save("getLifeSummary", call(c, "GET", f"/v1/lives/{life['id']}/summary"))
        save("listLives", call(c, "GET", "/v1/lives"))
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
