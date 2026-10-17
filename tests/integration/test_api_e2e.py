"""End to end: HTTP -> aggregator -> mock adapters -> decision layer -> envelope."""

import pytest
from fastapi.testclient import TestClient

from playyourself.adapters.aggregator import build_adapters
from playyourself.adapters.base import Capability
from playyourself.adapters.credentials import CredentialStore
from playyourself.adapters.mock import MockAdapter
from playyourself.api.app import app
from playyourself.api.deps import get_adapters, get_credential_store
from playyourself.settings import Settings, get_settings


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        _env_file=None,
        monzo_mode="mock",
        t212_mode="mock",
        cache_dir=tmp_path / "cache",
        source_max_retries=0,
        anthropic_api_key="",
    )
    store = CredentialStore(None, settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_credential_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def data(r):
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["error"] is None
    assert body["meta"]["request_id"] == r.headers["X-Request-ID"]
    return body


def test_full_flow(client):
    body = data(client.get("/v1/health"))
    assert body["data"]["mode"] == {"monzo": "mock", "trading212": "mock"}
    assert all(s["ok"] for s in body["data"]["sources"])

    body = data(client.get("/v1/dashboard"))
    d = body["data"]
    assert d["net_worth_pence"] > 0 and d["allocation_pct"]
    assert len(d["monthly_spend"]) == 6 and len(d["recent_transactions"]) == 10
    assert set(body["meta"]["sources"]) == {"monzo", "trading212"}

    d = data(client.get("/v1/habit-vector"))["data"]
    assert len(d["factors"]) == 7
    for f in d["factors"].values():
        assert 0 <= f["score"] <= 100
    assert 0 <= d["overall_score"] <= 100

    strategies = [
        {"name": "eq", "weights": {"global_equity": 1.0}, "period": "gfc_2008"},
        {"name": "6040", "weights": {"global_equity": 0.6, "gilts": 0.4}, "period": "gfc_2008"},
    ]
    d = data(client.post("/v1/backtest", json={"strategies": strategies}))["data"]
    assert len(d["results"]) == 2
    assert all(r["index"][0] == 100.0 and r["local"] for r in d["results"])
    assert d["contribution_source"] == "derived" and d["monthly_contribution_pence"] > 0

    d = data(client.post("/v1/backtest", json={"strategies": strategies, "include_local": False}))[
        "data"
    ]
    assert all(r["local"] is None for r in d["results"])
    assert d["monthly_contribution_pence"] is None

    sc = data(client.post("/v1/scenarios", json={"strategy": strategies[1]}))["data"]
    assert "Not a forecast" in sc["label"] and sc["fan"]["p50"]

    ex = data(client.post("/v1/explain", json={"kind": "scenarios", "result": sc["fan"]}))["data"]
    assert ex["source"] == "template" and ex["text"]

    lb = data(client.get("/v1/friends/leaderboard"))["data"]
    assert [e["rank"] for e in lb] == [1, 2, 3, 4, 5]
    assert sum(e["is_me"] for e in lb) == 1
    assert sum(e["pie"] is not None for e in lb if not e["is_me"]) == 2
    assert next(e for e in lb if e["is_me"])["pie"] is None

    assert data(client.put("/v1/friends/share", json={"share_pie": True}))["data"] == {
        "share_pie": True
    }
    card = data(client.get("/v1/friends/me/card"))["data"]
    assert card["pie"] and abs(sum(card["pie"].values()) - 100) < 0.5
    assert "pence" not in str(card).lower()


def test_validation_and_unknown_period(client):
    r = client.post("/v1/backtest", json={"strategies": []})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    bad = {"strategies": [{"weights": {"global_equity": 1.0}, "period": "nope"}]}
    r = client.post("/v1/backtest", json=bad)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_degraded_source_still_200(client, tmp_path):
    def failing():
        adapters = build_adapters(get_settings_value(), CredentialStore())
        adapters[1] = MockAdapter(
            "trading212",
            "steady_saver",
            frozenset({Capability.HOLDINGS, Capability.BALANCES}),
            fail_rate=1.0,
        )
        return adapters

    def get_settings_value():
        return app.dependency_overrides[get_settings]()

    app.dependency_overrides[get_adapters] = failing
    body = data(client.get("/v1/dashboard"))
    sources = body["meta"]["sources"]
    assert sources["monzo"]["ok"] is True
    assert sources["trading212"]["ok"] is False
    assert sources["trading212"]["error_code"]
    assert body["data"]["allocation_pct"] == {}


def test_openapi(client):
    spec = client.get("/openapi.json").json()
    assert "/v1/backtest" in spec["paths"]
    assert "/v1/friends/leaderboard" in spec["paths"]


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Play Yourself" in r.text
    assert client.get("/static/app.js").status_code == 200


def test_connect_status_demo_and_no_secrets(client):
    d = data(client.get("/v1/connect/status"))["data"]["sources"]
    assert d["monzo"]["mode"] == "demo" and d["trading212"]["mode"] == "demo"
    assert not d["monzo"]["connected"] and d["monzo"]["hint"] is None
    assert d["monzo"]["oauth_available"] is False
    sources = data(client.get("/v1/dashboard"))["meta"]["sources"]
    assert {s["mode"] for s in sources.values()} == {"demo"}


def test_spending_endpoint_and_explain(client):
    d = data(client.get("/v1/spending?months=6"))["data"]
    assert set(d) >= {
        "window", "monthly", "by_category", "category_by_month", "top_merchants",
        "subscriptions", "unusual", "patterns", "insights",
    }  # fmt: skip
    assert len(d["monthly"]) == 6 and d["by_category"] and d["insights"]
    assert client.get("/v1/spending?months=13").status_code == 422
    assert client.get("/v1/spending?months=0").status_code == 422
    result = {
        "insights": d["insights"][:3],
        "top_categories": [
            {"category": c["category"], "share_pct": round(c["share"] * 100, 1)}
            for c in d["by_category"][:3]
        ],
    }
    ex = data(client.post("/v1/explain", json={"kind": "spending", "result": result}))["data"]
    assert ex["source"] == "template" and d["insights"][0].split(" ")[0] in ex["text"]
