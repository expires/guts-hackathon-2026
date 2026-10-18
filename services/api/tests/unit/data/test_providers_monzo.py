"""Monzo adapter, store and OAuth (offline, respx)."""

from __future__ import annotations

import json
import stat
from datetime import UTC, datetime
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from lifeline_contracts.finance import Transaction
from lifeline_data.crypto import Sealer
from lifeline_data.providers import monzo_oauth
from lifeline_data.providers._http import ProviderError
from lifeline_data.providers.monzo import PAGE_LIMIT, MonzoAdapter, map_transaction
from lifeline_data.providers.store import ProviderStore
from lifeline_data.settings import DataSettings

BASE = "https://api.monzo.com"
ACC = "acc_1"
SECRET_TOKEN = "tok_SECRET_value_123456"


def raw_tx(i: int, **kw) -> dict:
    return {
        "id": f"tx_{i:04d}",
        "created": "2026-09-01T10:00:00.000Z",
        "amount": -250,
        "currency": "GBP",
        "description": "TESCO",
        "category": "groceries",
        "merchant": {"name": "Tesco"},
        "decline_reason": None,
        **kw,
    }


@pytest.fixture
def store(tmp_path):
    return ProviderStore(tmp_path)


def adapter(client, store=None, refresher=None, token=SECRET_TOKEN):
    return MonzoAdapter(
        BASE,
        client,
        token,
        refresher=refresher,
        store=store,
        subject="user-a",
        clock=lambda: datetime(2026, 10, 17, 12, tzinfo=UTC),
    )


def mock_accounts():
    respx.get(f"{BASE}/accounts").mock(
        return_value=httpx.Response(
            200, json={"accounts": [{"id": "rw", "type": "uk_rewards"}, {"id": ACC, "type": "uk_retail"}]}
        )
    )


@respx.mock
async def test_pagination_uses_last_id_and_stops_on_short_page(client, store):
    mock_accounts()
    pages = {
        None: [raw_tx(i) for i in range(100)],
        "tx_0099": [raw_tx(i) for i in range(100, 200)],
        "tx_0199": [raw_tx(i) for i in range(200, 237)],
    }
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        q = dict(request.url.params)
        seen.append(q)
        assert q["limit"] == str(PAGE_LIMIT) and q["expand[]"] == "merchant"
        assert request.headers["Authorization"] == f"Bearer {SECRET_TOKEN}"
        return httpx.Response(200, json={"transactions": pages[q.get("since")]})

    respx.get(f"{BASE}/transactions").mock(side_effect=handler)
    assert await adapter(client, store).full_sync() is True
    assert [s.get("since") for s in seen] == [None, "tx_0099", "tx_0199"]
    assert len(store.history_transactions("user-a")) == 237
    status = store.history_status("user-a")
    assert status == {"synced": True, "oldest": "2026-09-01", "count": 237, "last_error": None}


@respx.mock
async def test_403_before_approval_then_sync_success(client, store):
    mock_accounts()
    route = respx.get(f"{BASE}/transactions").mock(
        side_effect=[httpx.Response(403, json={}), httpx.Response(200, json={"transactions": [raw_tx(1)]})]
    )
    a = adapter(client, store)
    assert await a.full_sync() is False
    st = store.history_status("user-a")
    assert st["synced"] is False and st["last_error"] == "auth"
    assert await a.full_sync() is True
    assert store.history_status("user-a")["last_error"] is None and route.call_count == 2


@respx.mock
async def test_full_sync_never_raises_on_500_and_timeout(client, store):
    mock_accounts()
    respx.get(f"{BASE}/transactions").mock(return_value=httpx.Response(500))
    assert await adapter(client, store).full_sync() is False
    assert store.history_status("user-a")["last_error"] == "unavailable"
    respx.get(f"{BASE}/transactions").mock(side_effect=httpx.ReadTimeout("t"))
    assert await adapter(client, store).full_sync() is False
    assert store.history_status("user-a")["last_error"] == "timeout"


@respx.mock
async def test_recent_sync_window_and_upsert(client, store):
    mock_accounts()
    store.merge_history(
        "user-a",
        ACC,
        [Transaction(id="old", account_id=ACC, date="2025-01-01", amount=-1, description="x").model_dump()],
        full=True,
    )
    seen = []

    def handler(request):
        seen.append(request.url.params["since"])
        return httpx.Response(200, json={"transactions": [raw_tx(1, amount=-300)]})

    respx.get(f"{BASE}/transactions").mock(side_effect=handler)
    txs = await adapter(client, store).sync_recent()
    assert seen == ["2026-07-20T00:00:00Z"]  # 89 days before 2026-10-17
    assert {t.id for t in txs} == {"old", "tx_0001"}
    respx.get(f"{BASE}/transactions").mock(
        return_value=httpx.Response(200, json={"transactions": [raw_tx(1, amount=-999)]})
    )
    txs = await adapter(client, store).sync_recent()
    assert next(t for t in txs if t.id == "tx_0001").amount == -9.99
    assert len(txs) == 2
    assert store.history_is_full("user-a")  # full_sync_at survives a recent merge


def test_history_account_switch_starts_fresh(store):
    t = Transaction(id="a", account_id="x", date="2026-01-01", amount=-1, description="d").model_dump()
    store.merge_history("s", "acc_old", [t], full=True)
    store.merge_history("s", "acc_new", [{**t, "id": "b"}], full=False)
    assert [x["id"] for x in store.history_transactions("s")] == ["b"]
    assert not store.history_is_full("s")


def test_private_files_are_0600_and_hashed_dir(store, tmp_path):
    store.set("demo_abc/../../x", "monzo", {"access_token": SECRET_TOKEN})
    store.merge_history("demo_abc/../../x", ACC, [], full=True)
    d = store.dir_for("demo_abc/../../x")
    assert d.parent == tmp_path and ".." not in d.name
    for name in ("credentials.json", "monzo_history.json"):
        assert stat.S_IMODE((d / name).stat().st_mode) == 0o600
    assert store.hint("demo_abc/../../x", "monzo") == "…3456"


def test_disconnect_deletes_creds_and_history(store):
    store.set("s", "monzo", {"access_token": SECRET_TOKEN})
    store.merge_history("s", ACC, [], full=True)
    store.forget("s", "monzo")
    assert store.get("s", "monzo") is None and store.history_transactions("s") == []
    assert not store.dir_for("s").exists()


@respx.mock
async def test_refresh_once_on_auth_failure_replaces_refresh_token(client, store):
    mock_accounts()
    settings = DataSettings(app_env="test", monzo_client_id="cid", monzo_client_secret="csec")
    store.set("user-a", "monzo", {"access_token": "old", "refresh_token": "r1"})
    token_route = respx.post(settings.monzo_token_url).mock(
        return_value=httpx.Response(200, json={"access_token": "new_at", "refresh_token": "r2", "expires_in": 3600})
    )

    async def refresher():
        new = await monzo_oauth.refresh(settings, "r1", client)
        store.set("user-a", "monzo", new)
        return new["access_token"]

    def handler(request):
        ok = request.headers["Authorization"] == "Bearer new_at"
        return httpx.Response(200, json={"transactions": []}) if ok else httpx.Response(401)

    respx.get(f"{BASE}/transactions").mock(side_effect=handler)
    assert await adapter(client, store, refresher, token="old").full_sync() is True
    form = parse_qs(token_route.calls[0].request.content.decode())
    assert form["grant_type"] == ["refresh_token"] and form["refresh_token"] == ["r1"]
    assert store.get("user-a", "monzo")["refresh_token"] == "r2"
    assert token_route.call_count == 1


@respx.mock
async def test_accounts_and_pots_mapping(client):
    mock_accounts()
    respx.get(f"{BASE}/balance").mock(return_value=httpx.Response(200, json={"balance": 12345, "total_balance": 99999}))
    respx.get(f"{BASE}/pots").mock(
        return_value=httpx.Response(
            200,
            json={
                "pots": [
                    {"id": "pot_1", "name": "Holiday", "balance": 5000, "deleted": False},
                    {"id": "pot_2", "name": "Gone", "balance": 1, "deleted": True},
                ]
            },
        )
    )
    accs = await adapter(client).accounts()
    assert [(a.id, a.kind, a.balance) for a in accs] == [(ACC, "current", 123.45), ("pot_1", "savings", 50.0)]


def test_transaction_mapping_pot_moves_and_declined():
    out = map_transaction(raw_tx(1, scheme="uk_retail_pot", description="pot_0000abc", merchant=None), ACC)
    assert out is not None and out.description == "Transfer to savings pot" and out.amount == -2.5
    back = map_transaction(raw_tx(2, scheme="uk_retail_pot", amount=500, merchant=None), ACC)
    assert back is not None and back.description == "Transfer from savings pot" and back.amount == 5.0
    assert map_transaction(raw_tx(3, decline_reason="INSUFFICIENT_FUNDS"), ACC) is None
    tx = map_transaction(raw_tx(4), ACC)
    assert tx is not None and tx.merchant == "Tesco" and tx.provider_category == "groceries" and tx.date == "2026-09-01"
    assert map_transaction({"id": "x"}, ACC) is None


def test_oauth_state_single_use_and_expiry(clock):
    states = monzo_oauth.OAuthStateStore(clock=clock)
    s = states.issue("user-a")
    p = states.consume(s)
    assert p is not None and p.subject == "user-a"
    assert states.consume(s) is None
    s2 = states.issue("user-b")
    clock.advance(601)
    assert states.consume(s2) is None
    assert states.consume(None) is None and states.consume("bogus") is None


def test_authorize_url_params():
    st = DataSettings(app_env="test", monzo_client_id="cid", monzo_client_secret="x")
    url = monzo_oauth.authorize_url(st, "st1")
    q = parse_qs(url.split("?", 1)[1])
    assert url.startswith("https://auth.monzo.com/?")
    assert q == {
        "client_id": ["cid"],
        "redirect_uri": [st.monzo_redirect_uri],
        "response_type": ["code"],
        "state": ["st1"],
    }


@respx.mock
async def test_exchange_code_form_and_secret_not_in_error(client):
    st = DataSettings(app_env="test", monzo_client_id="cid", monzo_client_secret="THE_CLIENT_SECRET")
    route = respx.post(st.monzo_token_url).mock(
        return_value=httpx.Response(200, json={"access_token": "a", "refresh_token": "r"})
    )
    creds = await monzo_oauth.exchange_code(st, "code1", client)
    assert creds["refresh_token"] == "r"
    form = parse_qs(route.calls[0].request.content.decode())
    assert form["grant_type"] == ["authorization_code"] and form["code"] == ["code1"]
    route.mock(return_value=httpx.Response(400, text="THE_CLIENT_SECRET leaked?"))
    with pytest.raises(ProviderError) as ei:
        await monzo_oauth.exchange_code(st, "code1", client)
    assert "THE_CLIENT_SECRET" not in str(ei.value) and ei.value.code == "bad_data"
    assert "THE_CLIENT_SECRET" not in repr(st)
    json.dumps(ei.value.to_error_body())


def test_oauth_states_survive_restart(tmp_path):
    path = tmp_path / "oauth_states.json"
    sealer = Sealer({"TOKEN_ENCRYPTION_KEY": "restart-test-key"}, strict=True)
    first = monzo_oauth.OAuthStateStore(clock=lambda: 1000.0, path=path, sealer=sealer)
    state = first.issue("demo_subject")
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert state not in path.read_text(), "pending sign-ins are encrypted at rest"
    restarted = monzo_oauth.OAuthStateStore(clock=lambda: 1001.0, path=path, sealer=sealer)
    pending = restarted.consume(state)
    assert pending is not None and pending.subject == "demo_subject"
    third = monzo_oauth.OAuthStateStore(clock=lambda: 1002.0, path=path, sealer=sealer)
    assert third.consume(state) is None  # single use
