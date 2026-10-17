from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from playyourself.adapters.base import FinanceAdapter, SourceError
from playyourself.adapters.monzo import MonzoAdapter
from playyourself.settings import Settings

TOKEN = "tok_SECRET123"


def settings(token: str = TOKEN) -> Settings:
    return Settings(monzo_access_token=token, monzo_base_url="https://monzo.test", _env_file=None)


def make(handler, token: str = TOKEN) -> MonzoAdapter:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return MonzoAdapter(settings(token), client)


def ok_handler(txs=None):
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["Authorization"] == f"Bearer {TOKEN}"
        p = req.url.path
        if p == "/accounts":
            return httpx.Response(
                200,
                json={
                    "accounts": [
                        {"id": "acc_closed", "type": "uk_retail", "closed": True},
                        {"id": "acc_1", "type": "uk_retail", "closed": False},
                    ]
                },
            )
        if p == "/balance":
            assert req.url.params["account_id"] == "acc_1"
            return httpx.Response(200, json={"balance": 12345})
        if p == "/pots":
            return httpx.Response(
                200,
                json={
                    "pots": [
                        {"id": "pot_1", "balance": 5000, "deleted": False},
                        {"id": "pot_2", "balance": 900, "deleted": True},
                    ]
                },
            )
        if p == "/transactions":
            # older history is never requested: since is clamped to today - 89 days
            floor = datetime.now(UTC) - timedelta(days=89)
            assert req.url.params["since"] == floor.strftime("%Y-%m-%dT00:00:00Z")
            return httpx.Response(200, json={"transactions": txs or []})
        if p == "/ping/whoami":
            return httpx.Response(200, json={"authenticated": True})
        return httpx.Response(404)

    return handler


async def test_protocol_and_balances():
    a = make(ok_handler())
    assert isinstance(a, FinanceAdapter)
    bals = await a.get_balances()
    assert [(b.account_id, b.kind, b.value_pence) for b in bals] == [
        ("acc_1", "current", 12345),
        ("pot_1", "pot", 5000),
    ]


async def test_transactions_mapping_and_dropped():
    txs = [
        {
            "id": "tx_1",
            "created": "2026-02-01T10:00:00.000Z",
            "amount": -450,
            "description": "TESCO 123",
            "merchant": {"name": "Tesco"},
            "category": "groceries",
        },
        {
            "id": "tx_2",
            "created": "2026-02-02T10:00:00Z",
            "amount": -10000,
            "description": "pot_abc",
            "merchant": None,
            "category": "savings",
            "scheme": "uk_retail_pot",
        },
        {"id": "tx_3", "created": "2026-02-03T10:00:00Z", "amount": "bad", "category": "general"},
        {
            "id": "tx_4",
            "created": "2026-02-04T10:00:00Z",
            "amount": 250000,
            "description": "ACME LTD",
            "category": "income",
        },
    ]
    a = make(ok_handler(txs))
    out = await a.get_transactions(date(2026, 1, 1))
    assert a.last_dropped == 1
    by_id = {t.id: t for t in out}
    assert set(by_id) == {"tx_1", "tx_2", "tx_4"}
    assert by_id["tx_1"].merchant == "Tesco" and by_id["tx_1"].amount_pence == -450
    assert by_id["tx_1"].ts.tzinfo is not None and not by_id["tx_1"].is_transfer
    assert by_id["tx_2"].is_transfer
    assert by_id["tx_4"].merchant == "ACME LTD" and not by_id["tx_4"].is_transfer


async def test_health():
    h = await make(ok_handler()).health()
    assert h.ok and h.latency_ms is not None


@pytest.mark.parametrize(
    ("resp", "code", "retryable"),
    [
        (httpx.Response(401), "auth", False),
        (httpx.Response(500), "unavailable", True),
        (httpx.Response(200, content=b"not json"), "bad_data", False),
        (httpx.Response(200, json={"nope": 1}), "bad_data", False),
    ],
)
async def test_errors(resp, code, retryable):
    a = make(lambda req: resp)
    with pytest.raises(SourceError) as ei:
        await a.get_balances()
    assert ei.value.code == code and ei.value.retryable is retryable
    assert TOKEN not in str(ei.value)


async def test_rate_limited_retry_after():
    a = make(lambda req: httpx.Response(429, headers={"Retry-After": "7"}))
    with pytest.raises(SourceError) as ei:
        await a.get_balances()
    assert ei.value.code == "rate_limited" and ei.value.retryable
    assert ei.value.retry_after == 7.0


async def test_rate_limited_no_header():
    a = make(lambda req: httpx.Response(429))
    with pytest.raises(SourceError) as ei:
        await a.get_balances()
    assert ei.value.retry_after is None


async def test_timeout():
    def handler(req):
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(SourceError) as ei:
        await make(handler).get_balances()
    assert ei.value.code == "timeout" and ei.value.retryable


async def test_missing_token_raises_on_call_not_construction():
    a = make(ok_handler(), token="")
    with pytest.raises(SourceError) as ei:
        await a.get_balances()
    assert ei.value.code == "auth" and "MONZO_ACCESS_TOKEN" in ei.value.message
    assert not (await a.health()).ok


async def test_explicit_token_overrides_settings():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.headers["Authorization"])
        return httpx.Response(200, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    a = MonzoAdapter(settings(""), client, token="explicit")
    assert (await a.health()).ok and seen == ["Bearer explicit"]


async def test_refresh_once_on_auth_failure_then_retry():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.headers["Authorization"])
        return httpx.Response(401 if req.headers["Authorization"] == "Bearer old" else 200, json={})

    refreshed = []

    async def refresher():
        refreshed.append(1)
        return "new"

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    a = MonzoAdapter(settings(""), client, token="old", refresher=refresher)
    assert (await a.health()).ok
    assert seen == ["Bearer old", "Bearer new"] and refreshed == [1]


async def test_refresh_failure_gives_auth_error():
    async def refresher():
        return None

    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(401)))
    h = await MonzoAdapter(settings(""), client, token="old", refresher=refresher).health()
    assert not h.ok and h.error_code == "auth"
