"""ADR 0069 onboarding redesign over HTTP: student cards, plain-English next move, and the data the
"Their profile" screen reads. No network: the app factory runs on fixtures and mock sources."""

from __future__ import annotations

import httpx
import pytest

from lifeline_api import samples
from tests.integration.conftest import sign_in

pytestmark = pytest.mark.skipif(not samples.listing().samples, reason="demo/statements not generated")

CARD = ("name", "age", "avatar", "uni", "city", "funding_label", "money_in", "housing", "habit_line")


async def test_sample_cards_over_http(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "onboarding-0069-cards")
    body = (await client.get("/v1/samples", headers=auth)).json()
    for s in body["samples"]:
        missing = [f for f in CARD if f not in s and not (f == "uni" and s["id"] == "graduate")]
        assert not missing, (s["id"], missing)
        assert s["money_in"] and all(m["period"] in ("week", "month", "term", "year") for m in s["money_in"])
        assert all(m["amount"] > 0 and m["dates"] for m in s["money_in"])
    scottish = next(s for s in body["samples"] if s["id"] == "scottish")
    assert scottish["funding_label"].startswith("SAAS")
    assert {"label": "SAAS loan", "amount": 735.0, "period": "month", "dates": "Mid-month (18 Sep, 16 Oct)"} in (
        scottish["money_in"])


@pytest.mark.parametrize("sample_id", ["working", "commuter", "scottish"])
async def test_next_move_reason_confidence_and_count(client: httpx.AsyncClient, sample_id: str) -> None:
    auth = await sign_in(client, f"onboarding-0069-move-{sample_id}")
    assert (await client.post(f"/v1/samples/{sample_id}/import", headers=auth)).status_code == 201
    nm = (await client.get("/v1/next-move", headers=auth)).json()
    moves = [nm["top"], *nm["runners_up"]]
    assert nm["options_compared"] >= len(moves)
    for m in moves:
        assert m["reason"] and m["confidence_text"], m["kind"]
        assert "sample" not in m["confidence_text"].lower() and "·" not in m["confidence_text"]
        assert m["confidence_text"].split(":")[0] in (
            "Low confidence", "Medium confidence", "High confidence", "No rating")
    home = (await client.get("/v1/finance/home", headers=auth)).json()
    if "next_move" in home:
        assert home["next_move"]["options_compared"] == nm["options_compared"]


async def test_profile_screen_data_is_served(client: httpx.AsyncClient) -> None:
    """Every block of "Their profile" has an endpoint today (see the ADR 0069 data map in the W4 report)."""
    auth = await sign_in(client, "onboarding-0069-profile")
    assert (await client.post("/v1/samples/working/import", headers=auth)).status_code == 201
    ov = (await client.get("/v1/finance/overview", headers=auth)).json()
    assert any(a["kind"] == "current" for a in ov["accounts"])  # savings and overdraft live here
    sp = (await client.get("/v1/finance/spending", headers=auth)).json()
    assert sp["categories"] and all(0 <= c["share"] <= 1 for c in sp["categories"])
    bills = (await client.get("/v1/finance/bills", headers=auth)).json()
    subs = (await client.get("/v1/finance/subscriptions", headers=auth)).json()
    assert "items" in bills and subs["count"] >= 1
    habits = (await client.get("/v1/habits", headers=auth)).json()
    assert set(habits["components"]) <= {"savings_rate", "months_of_cover", "spend_stability", "discretionary_share",
                                         "subscription_creep", "debt_pressure"}
    prof = (await client.get("/v1/finance/profile", headers=auth)).json()
    assert prof["profile"]["housing"] == "rent" and prof["personal_facts"]
    assert len(prof["personal_facts"]) >= 3
    for f in prof["personal_facts"]:
        assert f["text"] and isinstance(f["facts"], dict)
    # ADR 0069 fields: the statement's own income lines, the overdraft, 0 months of cover while overdrawn.
    amounts = {(s["kind"], s["amount"]) for s in prof["income_sources"]}
    assert ("maintenance_loan", 1638.0) in amounts and any(k == "part_time_job" for k, _ in amounts)
    assert any(d["kind"] == "overdraft" and d["balance"] > 0 for d in prof["debts"])
    assert prof["months_of_cover"] == 0.0


async def test_profile_rent_and_cover_for_a_saver(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "onboarding-0069-profile-saver")
    assert (await client.post("/v1/samples/scottish/import", headers=auth)).status_code == 201
    prof = (await client.get("/v1/finance/profile", headers=auth)).json()
    assert prof["monthly_rent"] == 540.0
    assert prof["months_of_cover"] > 0 and prof["debts"] == []
    assert {s["amount"] for s in prof["income_sources"]} >= {735.0, 166.0}
