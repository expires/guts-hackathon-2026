"""PENNY_V3_BUILD.md A5.4: after importing each sample, Jordan, Callum and Hugo are running short; the rest on track."""

from __future__ import annotations

import httpx
import pytest

from lifeline_api import samples
from tests.integration.conftest import sign_in

SHORT_WINDOW = {"scottish", "graduate"}  # Eilidh and Lena: next money within 14 days -> total until then
RUNNING_SHORT = {"loan_england", "working", "rich"}  # Jordan Hughes, Callum Reid, Hugo Ashworth
ALL = ["scholarship", "scottish", "commuter", "loan_england", "working", "mature", "international", "final_year",
       "rich", "graduate"]

pytestmark = pytest.mark.skipif(not samples.listing().samples, reason="demo/statements not generated")


@pytest.mark.parametrize("sample_id", ALL)
async def test_sample_forecast_state(client: httpx.AsyncClient, sample_id: str) -> None:
    auth = await sign_in(client, f"forecast-a54-{sample_id.replace('_', '-')}")
    r = await client.post(f"/v1/samples/{sample_id}/import", headers=auth)
    assert r.status_code == 201, r.text
    r = await client.get("/v1/forecast", headers=auth)
    assert r.status_code == 200, r.text
    f = r.json()
    want = "running_short" if sample_id in RUNNING_SHORT else "on_track"
    assert f["state"] == want, (sample_id, f["headline"], f["budget_line"], f["habit_line"])
    available = f["money_now"] + f.get("expected_income_total", 0)
    left = available - f["bills_total"]
    assert f["to_spend"] == round(f["per_day"] * f["days"], 2)
    if left < 0:  # nothing to spend: zeros and the shortfall, never a negative budget
        assert (f["per_day"], f["per_week"], f["to_spend"]) == (0, 0, 0)
        assert f["budget_line"].startswith("You are £") and " short before " in f["budget_line"]
    else:
        assert abs(left - f["buffer_amount"] - f["per_day"] * f["days"]) < 0.01
    if sample_id in SHORT_WINDOW:
        assert f["budget_period"] == "until_next_money" and " until " in f["budget_line"]
    elif sample_id != "working":
        assert f["budget_period"] == "week"
        assert 30 <= f["per_week"] <= 400, (sample_id, f["per_week"])
