"""Trading212 adapter and HTTP error mapping (offline, respx)."""

from __future__ import annotations

from base64 import b64encode

import httpx
import pytest
import respx

from lifeline_data.providers._http import ProviderError, request_json
from lifeline_data.providers.trading212 import (
    POSITIONS_PATH,
    SUMMARY_PATH,
    Trading212Adapter,
    reset_cache,
)

BASE = "https://live.trading212.com/api/v0"
KEY, SECRET = "key_SECRETKEY", "sec_SECRETVALUE"

POSITIONS = [
    {
        "instrument": {"ticker": "AAPL_US_EQ", "isin": "US0378331005", "name": "Apple", "currency": "USD"},
        "quantity": 2.5,
        "currentPrice": 250.0,
        "averagePricePaid": 100.0,
        "walletImpact": {"currency": "GBP", "currentValue": 480.5, "totalCost": 200.0},
    },
    {
        "instrument": {"ticker": "VUSAl_EQ", "isin": "IE00B3XXRP09", "name": "Vanguard S&P 500", "currency": "GBX"},
        "quantity": 10,
        "walletImpact": {"currency": "GBP", "currentValue": 900.0},
    },
    {
        "instrument": {"ticker": "SAP_DE_EQ", "isin": "DE0007164600", "name": "SAP", "currency": "EUR"},
        "quantity": 1,
        "walletImpact": {"currency": "EUR", "currentValue": 100.0},
    },
]
SUMMARY = {
    "id": 42,
    "currency": "GBP",
    "totalValue": 2000.0,
    "cash": {"availableToTrade": 100.0, "inPies": 5.0, "reservedForOrders": 0},
    "investments": {"currentValue": 1380.5},
}


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_cache()
    yield
    reset_cache()


def make(client, clock, key=KEY, secret=SECRET):
    return Trading212Adapter(BASE, client, key, secret, clock=clock, wall_clock=clock)


@respx.mock
async def test_basic_header_and_wallet_impact_mapping(client, clock):
    route = respx.get(BASE + POSITIONS_PATH).mock(return_value=httpx.Response(200, json=POSITIONS))
    a = make(client, clock)
    holdings = await a.holdings()
    expected = "Basic " + b64encode(f"{KEY}:{SECRET}".encode()).decode()
    assert route.calls[0].request.headers["Authorization"] == expected
    assert [(h.instrument_id, h.value, h.asset_class, h.region) for h in holdings] == [
        ("US0378331005", 480.5, "equity", "US"),  # USD instrument: value from walletImpact, not price*qty
        ("IE00B3XXRP09", 900.0, "equity", None),
    ]
    assert a.last_dropped == 1  # EUR wallet dropped


@respx.mock
async def test_summary_account_and_non_gbp(client, clock):
    respx.get(BASE + SUMMARY_PATH).mock(return_value=httpx.Response(200, json=SUMMARY))
    acc = await make(client, clock).account()
    assert (acc.id, acc.kind, acc.provider, acc.balance) == ("t212-42", "isa", "trading212", 2000.0)
    reset_cache()
    respx.get(BASE + SUMMARY_PATH).mock(return_value=httpx.Response(200, json={**SUMMARY, "currency": "USD"}))
    with pytest.raises(ProviderError) as ei:
        await make(client, clock).account()
    assert ei.value.code == "bad_data"


@respx.mock
async def test_cache_windows(client, clock):
    pos = respx.get(BASE + POSITIONS_PATH).mock(return_value=httpx.Response(200, json=POSITIONS))
    summ = respx.get(BASE + SUMMARY_PATH).mock(return_value=httpx.Response(200, json=SUMMARY))
    a = make(client, clock)
    await a.holdings()
    await a.account()
    clock.advance(0.5)
    await make(client, clock).holdings()  # new adapter, same credential: shared cache
    await make(client, clock).account()
    assert (pos.call_count, summ.call_count) == (1, 1)
    clock.advance(0.6)  # 1.1 s: positions expired, summary (5 s) not
    await a.holdings()
    await a.account()
    assert (pos.call_count, summ.call_count) == (2, 1)
    clock.advance(5)
    await a.account()
    assert summ.call_count == 2
    await make(client, clock, key="other", secret="creds").account()  # different credential: own cache entry
    assert summ.call_count == 3


@respx.mock
async def test_missing_half_of_credentials(client, clock):
    with pytest.raises(ProviderError) as ei:
        await make(client, clock, secret="").account()
    assert ei.value.code == "auth"


@pytest.mark.parametrize(
    ("resp", "code", "retryable"),
    [
        (httpx.Response(401), "auth", False),
        (httpx.Response(403), "auth", False),
        (httpx.Response(500, text=SECRET), "unavailable", True),
        (httpx.Response(404), "bad_data", False),
        (httpx.Response(200, text="not json " + SECRET), "bad_data", False),
    ],
)
@respx.mock
async def test_error_mapping_never_leaks_secret(client, clock, resp, code, retryable):
    respx.get(BASE + SUMMARY_PATH).mock(return_value=resp)
    with pytest.raises(ProviderError) as ei:
        await make(client, clock).account()
    assert ei.value.code == code and ei.value.retryable is retryable
    assert SECRET not in str(ei.value) and KEY not in str(ei.value)
    assert ei.value.to_error_body()["error"]["source"] == "trading212"


@respx.mock
async def test_timeout_and_connect_errors(client):
    respx.get("https://x.test/a").mock(side_effect=httpx.ReadTimeout("t"))
    with pytest.raises(ProviderError) as ei:
        await request_json(client, "GET", "https://x.test/a", source="x")
    assert ei.value.code == "timeout" and ei.value.retryable
    respx.get("https://x.test/a").mock(side_effect=httpx.ConnectError("c"))
    with pytest.raises(ProviderError) as ei:
        await request_json(client, "GET", "https://x.test/a", source="x")
    assert ei.value.code == "unavailable" and ei.value.retryable


@respx.mock
async def test_429_retry_after_variants(client):
    url = "https://x.test/a"
    respx.get(url).mock(return_value=httpx.Response(429, headers={"Retry-After": "7"}))
    with pytest.raises(ProviderError) as ei:
        await request_json(client, "GET", url, source="x")
    assert ei.value.code == "rate_limited" and ei.value.retry_after == 7.0
    respx.get(url).mock(return_value=httpx.Response(429, headers={"x-ratelimit-reset": "5"}))
    with pytest.raises(ProviderError) as ei:
        await request_json(client, "GET", url, source="x")
    assert ei.value.retry_after == 5.0
    respx.get(url).mock(return_value=httpx.Response(429, headers={"x-ratelimit-reset": "1700000010"}))
    with pytest.raises(ProviderError) as ei:
        await request_json(client, "GET", url, source="x", wall_clock=lambda: 1_700_000_000.0)
    assert ei.value.retry_after == 10.0
    respx.get(url).mock(return_value=httpx.Response(429))
    with pytest.raises(ProviderError) as ei:
        await request_json(client, "GET", url, source="x")
    assert ei.value.retry_after is None
