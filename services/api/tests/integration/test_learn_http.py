"""Learn course over HTTP (ADR 0068): unlock order, grading, retries, samples, reset, language fallback."""

from __future__ import annotations

import time

import httpx
import pytest

from lifeline_api import learn_progress, samples
from lifeline_sim import learn
from lifeline_sim.learn_content import UNITS
from tests.integration.conftest import sign_in

SPECS = {lesson.id: lesson for u in UNITS for lesson in u.lessons}
IDS = learn.lesson_ids()


def answers(lesson_id: str, n_right: int) -> dict[str, str]:
    out = {}
    for i, q in enumerate(SPECS[lesson_id].quiz):
        right = "abcd"[q.answer]
        out[f"q{i}"] = right if i < n_right else ("b" if right == "a" else "a")
    return out


async def attempt(client: httpx.AsyncClient, auth: dict[str, str], lesson_id: str, n_right: int) -> httpx.Response:
    return await client.post(f"/v1/learn/lessons/{lesson_id}/attempts", json={"answers": answers(lesson_id, n_right)},
                             headers=auth)


async def test_path_needs_auth_and_is_fast(client: httpx.AsyncClient) -> None:
    assert (await client.get("/v1/learn")).status_code == 401
    auth = await sign_in(client, "learn-path-01")
    await client.get("/v1/learn", headers=auth)  # warm the memo
    t0 = time.monotonic()
    r = await client.get("/v1/learn", headers=auth)
    assert time.monotonic() - t0 < 0.3
    body = r.json()
    assert r.status_code == 200 and len(body["units"]) == 6 and body["total"] == len(IDS)
    assert body["next_lesson_id"] == IDS[0] and body["done"] == 0
    assert "quiz" not in r.text and "correct" not in r.text


async def test_locked_unknown_and_open(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "learn-lock-01")
    # No locks (PENNY_V3_BUILD.md E1): a later lesson opens and can be attempted at once.
    assert (await client.get(f"/v1/learn/lessons/{IDS[1]}", headers=auth)).status_code == 200
    assert (await attempt(client, auth, IDS[1], 3)).status_code == 200
    r = await client.get("/v1/learn/lessons/no-such-lesson", headers=auth)
    assert r.status_code == 404 and set(r.json()) == {"error"}
    r = await client.get(f"/v1/learn/lessons/{IDS[0]}", headers=auth)
    lesson = r.json()
    assert r.status_code == 200 and len(lesson["quiz"]) == 3 and lesson["facts"]
    assert "correct" not in r.text and "explanation" not in r.text


async def test_fail_retry_pass_unlocks_next(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "learn-pass-01")
    r = await attempt(client, auth, IDS[0], 1)
    res = r.json()
    assert r.status_code == 200 and not res["passed"] and res["correct"] == 1 and "unlocked_lesson_id" not in res
    res = (await attempt(client, auth, IDS[0], 2)).json()
    assert res["passed"] and res["unlocked_lesson_id"] == IDS[1] and res["path"]["done"] == 1
    assert all(len(x["explanation"]) > 0 for x in res["results"])
    assert (await client.get(f"/v1/learn/lessons/{IDS[1]}", headers=auth)).status_code == 200
    path = (await client.get("/v1/learn", headers=auth)).json()
    assert path["next_lesson_id"] == IDS[1] and path["units"][0]["done"] == 1
    # A retry on a passed lesson is allowed and never takes the pass away.
    res = (await attempt(client, auth, IDS[0], 0)).json()
    assert not res["passed"] and res["path"]["done"] == 1


async def test_bad_stored_document_is_skipped(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "learn-bad-doc-01")
    me = (await client.get("/v1/me", headers=auth)).json()["id"]
    from lifeline_api.main import app

    state = app.state.lifeline
    await state.store.put_doc(me, learn_progress.DOC_LEARN, {"passed": "not-a-list"})
    r = await client.get("/v1/learn", headers=auth)
    assert r.status_code == 200 and r.json()["done"] == 0
    await state.store.put_doc(me, learn_progress.DOC_LEARN, {"passed": [IDS[0], "gone-lesson"]})
    assert (await client.get("/v1/learn", headers=auth)).json()["done"] == 1


async def test_language_fallback(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "learn-lang-01")
    fr = (await client.get("/v1/learn", params={"language": "fr"}, headers=auth)).json()
    assert fr["units"][0]["title"] == "Les bases de l'argent"
    xx = await client.get("/v1/learn", params={"language": "xx"}, headers=auth)
    assert xx.status_code == 200 and xx.json()["units"][0]["title"] == "Money basics"
    lesson = (await client.get(f"/v1/learn/lessons/{IDS[0]}", params={"language": "hi"}, headers=auth)).json()
    assert lesson["cards"][0]["title"] == SPECS[IDS[0]].cards[0][0]  # English lesson text


@pytest.mark.skipif(not samples.listing().samples, reason="demo/statements not generated")
async def test_sample_import_gives_progress_and_reset_clears(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "learn-sample-01")
    sample_id = samples.listing().samples[0].id
    assert (await client.post(f"/v1/samples/{sample_id}/import", headers=auth)).status_code == 201
    path = (await client.get("/v1/learn", headers=auth)).json()
    assert path["done"] == 4 and path["next_lesson_id"] == IDS[4]
    assert [s["status"] for s in path["units"][0]["lessons"][:5]] == ["passed"] * 4 + ["open"]
    assert (await client.post("/v1/me/reset", headers=auth)).status_code == 200
    path = (await client.get("/v1/learn", headers=auth)).json()
    assert path["done"] == 0 and path["next_lesson_id"] == IDS[0]
