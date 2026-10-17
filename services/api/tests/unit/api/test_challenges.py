"""Challenge goal scoring and latching (lifeline_api.challenges)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from lifeline_api.challenges import evaluate, matches
from lifeline_contracts.domain import Challenge, Life
from lifeline_data.macro import mock_macro_table
from lifeline_sim import api as sim_api


def _life(preset: str = "nurse-leeds", start: int = 2006) -> Life:
    char = next(p for p in sim_api.presets() if p.id == preset)
    return sim_api.new_life("lf_test000001", char, "preset", start, 1, mock_macro_table())


def _ch(goal: dict[str, Any], char: str = "nurse-leeds", start: int = 2006) -> Challenge:
    return Challenge(id="c", title="t", emoji="x", description="d", character_id=char, start_year=start, goal=goal)


def _with(life: Life, *, age: int | None = None, year: int | None = None, alive: bool = True,
          missed: int | None = None, index: float | None = None, **fin: float) -> Life:
    upd: dict[str, Any] = {"alive": alive, "finances": life.finances.model_copy(update=fin)}
    if age is not None:
        upd["age"] = age
    if year is not None:
        upd["year"] = year
    ix: dict[str, Any] = {}
    if missed is not None:
        ix["missed_payments"] = missed
    if index is not None:
        ix["value"] = index
    if ix:
        upd["index"] = life.index.model_copy(update=ix)
    return life.model_copy(update=upd)


def test_matches_by_character_and_start() -> None:
    life = _life()
    assert matches(_ch({"type": "x"}), life)
    assert not matches(_ch({"type": "x"}, start=2007), life)
    assert not matches(_ch({"type": "x"}, char="banker-london"), life)


@pytest.mark.parametrize(
    "goal,state,want",
    [
        ({"type": "own_home_by_age", "age": 30.0}, {"age": 29, "property_value": 150_000}, "won"),
        ({"type": "own_home_by_age", "age": 30.0}, {"age": 29, "property_value": 0}, "in_progress"),
        ({"type": "own_home_by_age", "age": 30.0}, {"age": 31, "property_value": 0}, "lost"),
        ({"type": "no_missed_payments_until", "year": 2010.0}, {"year": 2009, "missed": 1}, "lost"),
        ({"type": "no_missed_payments_until", "year": 2010.0}, {"year": 2010, "missed": 0}, "won"),
        ({"type": "index_at_least_by_year", "index": 110.0, "year": 2026.0}, {"year": 2020, "index": 111}, "won"),
        ({"type": "index_at_least_by_year", "index": 110.0, "year": 2026.0}, {"year": 2026, "index": 90}, "lost"),
        ({"type": "debt_free_by_age", "age": 35.0}, {"age": 34, "other_debt": 0, "student_loan": 0}, "won"),
        ({"type": "debt_free_by_age", "age": 35.0}, {"age": 36, "other_debt": 10, "student_loan": 0}, "lost"),
        ({"type": "net_worth_at_least", "amount": 1e6}, {"net_worth": 1_000_001}, "won"),
        ({"type": "net_worth_at_least", "amount": 1e6}, {"net_worth": 5, "alive": False}, "lost"),
        ({"type": "pension_at_least_by_age", "amount": 1e5, "age": 50.0}, {"age": 49, "pension": 100_000}, "won"),
        ({"type": "pension_at_least_by_age", "amount": 1e5, "age": 50.0}, {"age": 51, "pension": 10}, "lost"),
        ({"type": "unknown_kind"}, {}, "in_progress"),
    ],
)
def test_goal_scoring(goal: dict[str, Any], state: dict[str, Any], want: str) -> None:
    status, detail = evaluate(_ch(goal), _with(_life(), **state))
    assert status == want and detail


async def test_challenges_route_and_latching(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    from lifeline_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        listed = (await c.get("/v1/challenges")).json()["challenges"]
        assert len(listed) >= 2
        survive = next(ch for ch in listed if ch["goal"]["type"] == "no_missed_payments_until")
        auth_r = await c.post("/v1/auth/demo", json={"device_id": "challenge-device-01"})
        auth = {"Authorization": f"Bearer {auth_r.json()['access_token']}"}
        life = (await c.post("/v1/lives", json={"mode": "preset", "preset_id": survive["character_id"],
                                                "start_year": survive["start_year"], "seed": 3}, headers=auth)).json()
        state = app.state.lifeline
        sub = (await c.get("/v1/me", headers=auth)).json()["id"]
        doc = await state.store.get_doc(sub, "challenges")
        assert doc[f"{life['id']}:{survive['id']}"]["status"] == "in_progress"
        target = int(survive["goal"]["year"])
        while life["year"] < target and life["alive"]:
            for ev in life["pending_events"]:
                ch = next((x for x in ev["choices"] if x.get("is_default")), ev["choices"][0])
                life = (await c.post(f"/v1/lives/{life['id']}/choices",
                                     json={"event_id": ev["id"], "choice_id": ch["id"]}, headers=auth)).json()["life"]
            life = (await c.post(f"/v1/lives/{life['id']}/age", headers=auth)).json()["life"]
        doc = await state.store.get_doc(sub, "challenges")
        entry = doc[f"{life['id']}:{survive['id']}"]
        assert entry["status"] in ("won", "lost")
        assert entry["status"] == ("won" if life["index"]["missed_payments"] == 0 else "lost")
        body = (await c.get("/v1/challenges", headers=auth)).json()
        mine = [p for p in body["progress"] if p["life_id"] == life["id"]]
        assert any(p["challenge_id"] == survive["id"] and p["status"] == entry["status"] for p in mine)
        assert (await c.get("/v1/challenges")).json().get("progress", []) == [], "no progress without a token"
