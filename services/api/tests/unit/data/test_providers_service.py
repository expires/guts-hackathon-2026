"""ProviderService and DataHub.finance_snapshot: live vs cached vs mock, isolation, connect flows."""

from __future__ import annotations

import httpx
import pytest
import respx

from lifeline_data.hub import DataHub
from lifeline_data.providers._http import ProviderError
from lifeline_data.providers.trading212 import reset_cache
from lifeline_data.settings import DataSettings

MONZO = "https://api.monzo.com"
T212 = "https://live.trading212.com/api/v0"
A, B = "demo_aaaa", "demo_bbbb"

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
def _clear():
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def cfg(tmp_path) -> DataSettings:
    return DataSettings(
        app_env="test",
        backoff_base_seconds=0,
        redis_url="",
        database_url="",
        credentials_dir=str(tmp_path),
        monzo_client_id="cid",
        monzo_client_secret="csec",
    )


@pytest.fixture
def hub(cfg, client, clock, no_sleep) -> DataHub:
    return DataHub(cfg, client=client, clock=clock, sleep=no_sleep, env={})


def mock_monzo(token_ok="Bearer mtok"):
    def guard(request, payload):
        return (
            httpx.Response(200, json=payload) if request.headers["Authorization"] == token_ok else httpx.Response(401)
        )

    respx.get(f"{MONZO}/ping/whoami").mock(side_effect=lambda r: guard(r, {"authenticated": True}))
    respx.get(f"{MONZO}/accounts").mock(
        side_effect=lambda r: guard(r, {"accounts": [{"id": "acc_1", "type": "uk_retail"}]})
    )
    respx.get(f"{MONZO}/balance").mock(side_effect=lambda r: guard(r, {"balance": 10000}))
    respx.get(f"{MONZO}/pots").mock(side_effect=lambda r: guard(r, {"pots": []}))
    respx.get(f"{MONZO}/transactions").mock(
        side_effect=lambda r: guard(
            r,
            {
                "transactions": [
                    {
                        "id": "tx_1",
                        "created": "2026-10-01T09:00:00Z",
                        "amount": -450,
                        "description": "COSTA",
                        "category": "eating_out",
                        "merchant": {"name": "Costa"},
                    }
                ]
            },
        )
    )


def mock_t212():
    respx.get(T212 + "/equity/positions").mock(return_value=httpx.Response(200, json=POSITIONS))
    respx.get(T212 + "/equity/account/summary").mock(return_value=httpx.Response(200, json=SUMMARY))


async def test_no_credentials_gives_no_live_data(hub):
    assert await hub.live_snapshot(A) is None  # never sample data in its place
    conns = (await hub.connections(A)).providers
    assert [(c.provider, c.connected, c.data_status, c.hint) for c in conns] == [
        ("monzo", False, "mock", None),
        ("trading212", False, "mock", None),
    ]
    assert conns[0].oauth_available


@respx.mock
async def test_connect_t212_validates_before_storing(hub):
    respx.get(T212 + "/equity/account/summary").mock(return_value=httpx.Response(401))
    with pytest.raises(ProviderError) as ei:
        await hub.connect_trading212(A, " kkkkkkkkkkkk1234 ", "s")
    assert ei.value.code == "auth"
    assert hub.providers.store.get(A, "trading212") is None
    reset_cache()
    respx.get(T212 + "/equity/account/summary").mock(return_value=httpx.Response(200, json=SUMMARY))
    conn = await hub.connect_trading212(A, " kkkkkkkkkkkk1234 ", " s ")
    assert conn.connected and conn.hint == "…1234"
    assert hub.providers.store.get(A, "trading212") == {"api_key": "kkkkkkkkkkkk1234", "api_secret": "s"}
    assert "kkkkkkkkkkkk1234" not in (await hub.connections(A)).model_dump_json()


@respx.mock
async def test_live_snapshot_both_providers_then_cached_then_isolation(hub, clock):
    mock_monzo()
    mock_t212()
    await hub.connect_monzo_token(A, "mtok")
    await hub.connect_trading212(A, "kkkkkkkkkkkk1234", "ssss")
    snap = await hub.live_snapshot(A)
    assert snap.status == "live" and snap.source == "monzo+trading212"
    assert {a.id for a in snap.accounts} == {"acc_1", "t212-42"}
    assert [t.id for t in snap.transactions] == ["tx_1"] and snap.transactions[0].amount == -4.5
    assert snap.mortgage is None and snap.energy is None
    assert next(a for a in snap.accounts if a.id == "t212-42").balance == 2000.0
    # another subject never sees A's data and never uses A's credentials
    other = await hub.live_snapshot(B)
    assert other is None
    # provider failure -> last good snapshot, labelled cached
    clock.advance(120)
    respx.get(f"{MONZO}/balance").mock(return_value=httpx.Response(500))
    cached = await hub.live_snapshot(A)
    assert cached.status == "cached" and cached.accounts == snap.accounts
    assert (await hub.connections(A)).providers[0].last_error == "unavailable"
    # disconnect everything -> fixture again, files gone
    await hub.disconnect(A, "monzo")
    await hub.disconnect(A, "trading212")
    assert await hub.live_snapshot(A) is None
    assert not hub.providers.store.dir_for(A).exists()


@respx.mock
async def test_failure_without_cache_gives_nothing(hub):
    mock_t212()
    await hub.connect_trading212(A, "kkkkkkkkkkkk1234", "ssss")
    respx.get(T212 + "/equity/account/summary").mock(return_value=httpx.Response(500))
    reset_cache()
    assert await hub.live_snapshot(A) is None  # never sample data in its place


@respx.mock
async def test_t212_only_leaves_monzo_part_empty(hub):
    mock_t212()
    await hub.connect_trading212(A, "kkkkkkkkkkkk1234", "ssss")
    snap = await hub.live_snapshot(A)
    assert snap.source == "trading212" and snap.transactions == [] and [a.kind for a in snap.accounts] == ["isa"]
    assert "stocks" in snap.accounts[0].name.lower(), "an investment account is never counted as cash savings"


@respx.mock
async def test_snapshot_memo_protects_rate_limits(hub, clock):
    mock_monzo()
    await hub.connect_monzo_token(A, "mtok")
    await hub.live_snapshot(A)
    calls = respx.calls.call_count
    await hub.live_snapshot(A)
    assert respx.calls.call_count == calls
    clock.advance(61)
    await hub.live_snapshot(A)
    assert respx.calls.call_count > calls


@respx.mock
async def test_monzo_oauth_flow_and_sync_retry(hub):
    url = await hub.monzo_start(A)
    state = url.split("state=")[1].split("&")[0]
    respx.post("https://api.monzo.com/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "mtok", "refresh_token": "r1", "expires_in": 100})
    )
    respx.get(f"{MONZO}/accounts").mock(return_value=httpx.Response(403))  # not approved in the app yet
    assert await hub.monzo_callback(state, "code") == A
    conn = (await hub.connections(A)).providers[0]
    assert conn.connected and conn.history is not None and conn.history.synced is False
    assert conn.history.last_error == "auth"
    with pytest.raises(ProviderError) as ei:  # state is single use
        await hub.monzo_callback(state, "code")
    assert ei.value.code == "bad_state"
    mock_monzo()
    status = await hub.monzo_sync(A)
    assert status.synced and status.count == 1 and status.last_error is None
    await hub.disconnect(A, "monzo")
    assert hub.providers.store.history_transactions(A) == []


async def test_monzo_start_unconfigured(client, clock, no_sleep, tmp_path):
    h = DataHub(
        DataSettings(app_env="test", credentials_dir=str(tmp_path)), client=client, clock=clock, sleep=no_sleep, env={}
    )
    with pytest.raises(ProviderError) as ei:
        await h.monzo_start(A)
    assert ei.value.code == "not_configured"


async def test_offline_hub_connect_refused_and_snapshot_never_raises(cfg, clock, no_sleep):
    h = DataHub(cfg, clock=clock, sleep=no_sleep, env={})  # no client in test env -> offline
    h.providers.store.set(A, "trading212", {"api_key": "kkkkkkkkkkkk1234", "api_secret": "s"})
    with pytest.raises(ProviderError) as ei:
        await h.connect_trading212(A, "k", "s")
    assert ei.value.code == "offline"
    assert await h.finance_snapshot(A) is None  # no data of their own: None, never sample data
