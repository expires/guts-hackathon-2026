"""Monzo pagination, local history store and sync strategy (httpx.MockTransport fakes)."""

import json
import stat
from datetime import UTC, datetime, timedelta

import httpx

from playyourself.adapters.credentials import CredentialStore
from playyourself.adapters.monzo import PAGE_LIMIT, RECENT_SYNC_DAYS, MonzoAdapter
from playyourself.adapters.monzo_history import MonzoHistory
from playyourself.adapters.monzo_oauth import refresh_access_token
from playyourself.settings import Settings

NOW = datetime.now(UTC)


def tx(i: int, days_ago: float = 1.0, amount: int = -100) -> dict:
    ts = (NOW - timedelta(days=days_ago, minutes=-i)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": f"tx_{i:04d}",
        "created": ts,
        "amount": amount,
        "description": f"shop {i}",
        "category": "general",
    }


class Fake:
    """Serves /transactions from an ordered list honouring since (timestamp or id) and limit."""

    def __init__(self, txs: list[dict]):
        self.txs = txs
        self.calls: list[dict] = []
        self.fail = False

    def handler(self, req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if p == "/accounts":
            return httpx.Response(200, json={"accounts": [{"id": "acc_1", "type": "uk_retail"}]})
        if p == "/transactions":
            if self.fail:
                return httpx.Response(500)
            q = dict(req.url.params)
            self.calls.append(q)
            items = self.txs
            since = q.get("since")
            if since and since.startswith("tx_"):
                ids = [t["id"] for t in items]
                items = items[ids.index(since) + 1 :]
            elif since:
                items = [t for t in items if t["created"] >= since]
            return httpx.Response(200, json={"transactions": items[: int(q["limit"])]})
        return httpx.Response(404)


def make(tmp_path, fake: Fake, history: bool = True, timeout: float = 60) -> MonzoAdapter:
    s = Settings(
        _env_file=None,
        monzo_base_url="https://monzo.test",
        credentials_dir=tmp_path,
        monzo_initial_sync_timeout_seconds=timeout,
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(fake.handler))
    return MonzoAdapter(s, client, token="tok", history=MonzoHistory(tmp_path) if history else None)


async def test_pagination_three_pages(tmp_path):
    fake = Fake([tx(i) for i in range(237)])
    out = await make(tmp_path, fake).get_transactions((NOW - timedelta(days=30)).date())
    assert len(out) == 237
    assert [c["limit"] for c in fake.calls] == ["100"] * 3
    assert "since" in fake.calls[0] and fake.calls[0]["since"].endswith("Z")
    assert fake.calls[1]["since"] == "tx_0099" and fake.calls[2]["since"] == "tx_0199"


async def test_dedupe_by_id(tmp_path):
    fake = Fake([tx(1), tx(1, amount=-999), tx(2)])
    out = await make(tmp_path, fake, history=False).get_transactions(
        (NOW - timedelta(days=30)).date()
    )
    assert sorted(t.id for t in out) == ["tx_0001", "tx_0002"]
    assert {t.id: t.amount_pence for t in out}["tx_0001"] == -999


async def test_full_sync_stores_everything_0600(tmp_path):
    fake = Fake([tx(i, days_ago=400 - i) for i in range(PAGE_LIMIT + 5)])
    a = make(tmp_path, fake)
    assert await a.full_sync()
    assert "since" not in fake.calls[0] and fake.calls[1]["since"] == "tx_0099"
    path = tmp_path / "monzo_history.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    meta = json.loads(path.read_text())["meta"]
    assert meta["count"] == PAGE_LIMIT + 5 and meta["account_id"] == "acc_1"
    assert meta["full_sync_at"] and meta["oldest_ts"]
    st = MonzoHistory(tmp_path).status()
    assert st["synced"] and st["count"] == PAGE_LIMIT + 5 and st["last_error"] is None
    assert st["oldest"] == (NOW - timedelta(days=400)).date().isoformat()


async def test_recent_sync_after_full_merges_and_filters(tmp_path):
    old = [tx(i, days_ago=300 - i) for i in range(3)]
    recent = tx(10, days_ago=2, amount=-500)
    fake = Fake([*old, recent])
    a = make(tmp_path, fake)
    assert await a.full_sync()
    fake.calls.clear()
    fake.txs = [*old, tx(10, days_ago=2, amount=-777), tx(11, days_ago=1)]  # 10 changed
    out = await a.get_transactions((NOW - timedelta(days=100)).date())
    floor = NOW - timedelta(days=RECENT_SYNC_DAYS)
    got = datetime.strptime(fake.calls[0]["since"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    assert abs(got - floor) < timedelta(days=1, seconds=1)
    assert {t.id: t.amount_pence for t in out} == {"tx_0010": -777, "tx_0011": -100}
    # old data stays in the store, and a wider since returns it from the store
    wide = await a.get_transactions((NOW - timedelta(days=365)).date())
    assert len(wide) == 5 and MonzoHistory(tmp_path).status()["count"] == 5


async def test_no_history_never_asks_for_old_data(tmp_path):
    fake = Fake([tx(1)])
    a = make(tmp_path, fake)
    await a.get_transactions((NOW - timedelta(days=500)).date())
    got = datetime.strptime(fake.calls[0]["since"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    assert NOW - got < timedelta(days=RECENT_SYNC_DAYS + 1)
    assert not MonzoHistory(tmp_path).status()["synced"]


async def test_full_sync_failure_is_recorded(tmp_path):
    fake = Fake([tx(1)])
    fake.fail = True
    a = make(tmp_path, fake)
    assert not await a.full_sync()
    st = MonzoHistory(tmp_path).status()
    assert not st["synced"] and st["last_error"] == "unavailable"
    fake.fail = False
    assert await a.full_sync() and MonzoHistory(tmp_path).status()["last_error"] is None


def test_forget_deletes_history(tmp_path):
    h = MonzoHistory(tmp_path)
    h.merge("acc_1", [tx(1) | {"ts": "2026-01-01T00:00:00Z"}], full=True)
    assert h.path.exists()
    s = CredentialStore(tmp_path)
    s.set("monzo", {"access_token": "t"})
    s.forget("monzo")
    assert not h.path.exists()


async def test_refresh_replaces_refresh_token(tmp_path):
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req.content.decode())
        return httpx.Response(
            200, json={"access_token": "a2", "refresh_token": "r2", "expires_in": 60}
        )

    s = Settings(_env_file=None, monzo_client_id="c", monzo_client_secret="s")
    store = CredentialStore(tmp_path, s)
    store.set("monzo", {"access_token": "a1", "refresh_token": "r1"}, remember=True)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert await refresh_access_token(s, store, client) == "a2"
    assert "refresh_token=r1" in seen[0]
    assert store.get("monzo")["refresh_token"] == "r2"
    assert "r2" in (tmp_path / "credentials.json").read_text()
