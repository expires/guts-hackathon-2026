"""GET /v1/profile/stats end to end: nothing connected, Trading 212 only, a sample student, disconnect."""

from __future__ import annotations

import httpx
import respx

from tests.contract.spec import validate
from tests.integration.conftest import sign_in
from tests.integration.test_live_data_flow import T212_KEY, T212_SECRET, live, mock_t212, router  # noqa: F401


async def stats(c: httpx.AsyncClient, auth: dict[str, str]) -> dict:
    r = await c.get("/v1/profile/stats", headers=auth)
    assert r.status_code == 200, r.text
    validate("GET", "/v1/profile/stats", r.status_code, r.json())
    return r.json()


def by_id(items: list[dict]) -> dict[str, dict]:
    return {i["id"]: i for i in items}


async def test_requires_sign_in(live: httpx.AsyncClient) -> None:  # noqa: F811
    assert (await live.get("/v1/profile/stats")).status_code == 401


async def test_nothing_connected(live: httpx.AsyncClient) -> None:  # noqa: F811
    auth = await sign_in(live, "profile-none")
    body = await stats(live, auth)
    assert not any(c["connected"] for c in body["connections"])
    assert all(not s["available"] and s["missing_hint"] for s in body["sections"])


async def test_trading212_only_then_disconnect(live: httpx.AsyncClient, router: respx.MockRouter) -> None:  # noqa: F811
    mock_t212(router)
    auth = await sign_in(live, "profile-t212")
    r = await live.post("/v1/connections/trading212", headers=auth,
                        json={"api_key": T212_KEY, "api_secret": T212_SECRET})
    assert r.status_code == 200
    body = await stats(live, auth)
    conn, sec = by_id(body["connections"]), by_id(body["sections"])
    assert conn["trading212"]["connected"] and conn["trading212"]["provides"] == "2 holdings"
    assert not conn["monzo"]["connected"]
    inv = sec["investments"]["investments"]
    assert sec["investments"]["available"] and inv["holdings_count"] == 2
    assert inv["total_value"] == 1500.0 and inv["invested_value"] == 1380.5  # walletImpact.currentValue sums
    assert [h["name"] for h in inv["top_holdings"]] == ["Vanguard S&P 500", "Apple"]
    assert sec["net_worth"]["available"] and sec["net_worth"]["net_worth"]["cash"] == 0
    assert not sec["habits"]["available"] and "Connect Monzo" in sec["habits"]["missing_hint"]
    assert not sec["spending"]["available"]

    ov = (await live.get("/v1/finance/overview", headers=auth)).json()
    assert ov["balance"] == 0, "investments never count as cash"

    await live.delete("/v1/connections/trading212", headers=auth)
    assert not any(c["connected"] for c in (await stats(live, auth))["connections"])


async def test_sample_student_is_labelled(live: httpx.AsyncClient) -> None:  # noqa: F811
    auth = await sign_in(live, "profile-sample")
    sample = (await live.get("/v1/samples", headers=auth)).json()["samples"][0]["id"]
    assert (await live.post(f"/v1/samples/{sample}/import", headers=auth)).status_code == 201
    body = await stats(live, auth)
    c = by_id(body["connections"])["sample"]
    assert c["connected"] and c["data_status"] == "mock" and c["label"] == "Sample data"
    assert c["sample_id"] == sample
    sec = by_id(body["sections"])
    assert sec["habits"]["available"] and sec["habits"]["sources"] == ["sample"]
    assert sec["spending"]["available"] and sec["net_worth"]["available"]
    assert not sec["investments"]["available"]


async def test_statement_then_trading212_keeps_the_statement(live: httpx.AsyncClient, router: respx.MockRouter) -> None:  # noqa: F811
    mock_t212(router)
    auth = await sign_in(live, "profile-both")
    sample = (await live.get("/v1/samples", headers=auth)).json()["samples"][0]["id"]
    await live.post(f"/v1/samples/{sample}/import", headers=auth)
    await live.post("/v1/connections/trading212", headers=auth, json={"api_key": T212_KEY, "api_secret": T212_SECRET})
    sec = by_id((await stats(live, auth))["sections"])
    assert sec["investments"]["available"]
    # the sample is replaced by the live data (sample data is never mixed with live data)
    assert not by_id((await stats(live, auth))["connections"])["sample"]["connected"]
