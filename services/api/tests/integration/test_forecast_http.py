"""Forecast Next Move, forecast settings and the Category screen through the HTTP API (ADR 0072)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from lifeline_api import samples
from lifeline_contracts.finance import SpendingResponse
from lifeline_contracts.forecast import CategoryDetail, Forecast
from tests.integration.conftest import sign_in

needs_samples = pytest.mark.skipif(not samples.listing().samples, reason="demo/statements not generated")


async def _with_sample(client: httpx.AsyncClient, device: str, sample_id: str = "scottish") -> dict[str, str]:
    auth = await sign_in(client, device)
    r = await client.post(f"/v1/samples/{sample_id}/import", headers=auth)
    assert r.status_code == 201, r.text
    return auth


async def _forecast(client: httpx.AsyncClient, auth: dict[str, str], **params: Any) -> dict[str, Any]:
    r = await client.get("/v1/forecast", headers=auth, params=params)
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    Forecast.model_validate(body)
    return body


async def test_forecast_needs_auth_and_data(client: httpx.AsyncClient) -> None:
    assert (await client.get("/v1/forecast")).status_code == 401
    auth = await sign_in(client, "forecast-no-data")
    r = await client.get("/v1/forecast", headers=auth)
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_finance_data"
    r = await client.get("/v1/finance/spending/groceries", headers=auth)
    assert r.status_code == 409


@needs_samples
async def test_forecast_adds_up_and_settings_persist(client: httpx.AsyncClient) -> None:
    auth = await _with_sample(client, "forecast-sample-1")
    f = await _forecast(client, auth)
    assert f["buffer_pct"] == 10 and len(f["steps"]) == 4
    assert [s["id"] for s in f["steps"]] == ["money_now", "bills", "buffer", "result"]
    available = f["money_now"] + f.get("expected_income_total", 0)
    assert abs(available - f["bills_total"] - f["buffer_amount"] - f["per_day"] * f["days"]) < 0.01
    assert f["per_week"] == round(f["per_day"] * 7, 2)
    assert "stress" not in f

    r = await client.put("/v1/forecast/settings", json={"buffer_pct": 20}, headers=auth)
    assert r.status_code == 200 and r.json() == {"buffer_pct": 20}
    f20 = await _forecast(client, auth)
    assert f20["buffer_pct"] == 20 and f20["buffer_amount"] >= f["buffer_amount"]
    # a preview does not change the stored setting
    f0 = await _forecast(client, auth, buffer_pct=0)
    assert f0["buffer_pct"] == 0 and f0["per_week"] >= f20["per_week"]
    assert (await _forecast(client, auth))["buffer_pct"] == 20


@needs_samples
async def test_forecast_stress_and_language(client: httpx.AsyncClient) -> None:
    auth = await _with_sample(client, "forecast-sample-2")
    f = await _forecast(client, auth, stress=2022, language="fr")
    assert f["stress"]["year"] == 2022 and f["stress"]["inflation_pct"] > 0
    assert f["stress"]["per_week"] == f["per_week"]
    assert any(s["label"].startswith("ONS CPI") for s in f["sources"])


async def test_forecast_rejects_bad_values(client: httpx.AsyncClient) -> None:
    auth = await sign_in(client, "forecast-bad-values")
    assert (await client.put("/v1/forecast/settings", json={"buffer_pct": 7}, headers=auth)).status_code == 422
    assert (await client.put("/v1/forecast/settings", json={"buffer_pct": 10, "x": 1},
                             headers=auth)).status_code == 422
    assert (await client.get("/v1/forecast", params={"buffer_pct": 7}, headers=auth)).status_code == 422
    assert (await client.get("/v1/forecast", params={"stress": 2008}, headers=auth)).status_code == 422


@needs_samples
async def test_spending_months_and_category_detail(client: httpx.AsyncClient) -> None:
    auth = await _with_sample(client, "forecast-sample-3")
    sp = SpendingResponse.model_validate((await client.get("/v1/finance/spending", headers=auth)).json())
    assert sp.months == sorted(sp.months) and sp.months[-1] == sp.month and len(sp.months) >= 3

    top = sp.categories[0]
    r = await client.get(f"/v1/finance/spending/{top.category}", headers=auth)
    assert r.status_code == 200, r.text
    cd = CategoryDetail.model_validate(r.json())
    assert cd.month == sp.month and cd.total == top.amount
    assert round(sum(w.amount for w in cd.weeks), 2) == pytest.approx(cd.total, abs=0.01)
    assert len(cd.transactions) == top.transactions
    assert all(t.date[:7] == cd.month for t in cd.transactions)

    earlier = sp.months[-2]
    r = await client.get(f"/v1/finance/spending/{top.category}", params={"month": earlier}, headers=auth)
    assert r.status_code == 200 and r.json()["month"] == earlier

    r = await client.get("/v1/finance/spending/not-a-category", headers=auth)
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = await client.get("/v1/finance/spending/groceries", params={"month": "2026-13"}, headers=auth)
    assert r.status_code == 422
