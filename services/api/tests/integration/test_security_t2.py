"""V6 / V3 Tier 2 findings: token revocation on delete, 503 paths, rate-limit keys (T2-F3, T2-F4, T2-G1)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from lifeline_api.ratelimit import client_ip
from tests.integration.conftest import sign_in

FIXTURES = __import__("pathlib").Path(__file__).resolve().parents[1] / "fixtures" / "data"


async def test_delete_revokes_every_token_of_the_subject(client: httpx.AsyncClient) -> None:
    from lifeline_api.main import app

    a = await sign_in(client, "revoke-device-01")
    b = await sign_in(client, "revoke-device-01")  # a second phone or an old session
    sub = (await client.get("/v1/me", headers=a)).json()["id"]
    assert (await client.delete("/v1/me", headers=a)).status_code == 204
    for token in (a, b):
        r = await client.get("/v1/me", headers=token)
        assert r.status_code == 401
    assert await app.state.lifeline.store.get_doc(sub, "account") is None, "old tokens cannot recreate the account"
    fresh = await sign_in(client, "revoke-device-01")
    assert (await client.get("/v1/me", headers=fresh)).status_code == 200


async def test_delete_answers_503_when_money_data_cannot_be_deleted(client: httpx.AsyncClient,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    from lifeline_api.main import app
    from lifeline_data.crypto import StoreUnavailable as DataStoreUnavailable

    auth = await sign_in(client, "revoke-device-02")
    life = await client.post("/v1/lives", json={"mode": "preset", "preset_id": "nurse-leeds", "start_year": 2006},
                             headers=auth)

    async def boom(subject: str) -> None:
        raise DataStoreUnavailable("down")

    monkeypatch.setattr(app.state.lifeline.hub, "delete_user_snapshot", boom)
    r = await client.delete("/v1/me", headers=auth)
    assert r.status_code == 503 and r.json()["error"]["code"] == "store_unavailable"
    assert (await client.get(f"/v1/lives/{life.json()['id']}", headers=auth)).status_code == 200, "nothing deleted"
    assert (await client.post("/v1/me/reset", headers=auth)).status_code == 503


async def test_failed_money_write_is_503_and_not_used(client: httpx.AsyncClient,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    from lifeline_api.main import app

    auth = await sign_in(client, "write-fail-01")

    async def boom(subject: str, snap: Any) -> bool:
        from lifeline_data.crypto import EncryptionKeyMissing

        raise EncryptionKeyMissing("no key")

    monkeypatch.setattr(app.state.lifeline.hub, "set_user_snapshot", boom)
    r = await client.post("/v1/finance/transactions", json={"amount": 3, "merchant": "Pret"}, headers=auth)
    assert r.status_code == 503 and r.json()["error"]["code"] == "store_unavailable"
    manual = {"postcode": "LS6 1AN", "housing": "rent", "monthly_rent": 900, "monthly_take_home": 2000}
    r = await client.put("/v1/finance/manual", json=manual, headers=auth)
    assert r.status_code == 503
    csv = (FIXTURES / "statement_monzo_sample.csv").read_bytes()
    r = await client.post("/v1/finance/statements", files={"file": ("m.csv", csv, "text/csv")}, headers=auth)
    assert r.status_code == 503, "no import result is reported when the data was not saved"
    me = (await client.get("/v1/me", headers=auth)).json()
    assert me["has_finance_data"] is False and me["finance_inputs"] == []


def test_client_ip_trusts_only_the_proxy_hop() -> None:
    from types import SimpleNamespace

    def scope(xff: str | None, hops: int | None, env: str = "dev") -> dict[str, Any]:
        settings = SimpleNamespace(trusted_proxy_hops=hops, app_env=env)
        app = SimpleNamespace(state=SimpleNamespace(lifeline=SimpleNamespace(settings=settings)))
        headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
        return {"client": ("10.0.0.9", 1234), "headers": headers, "app": app}

    # Behind Railway (1 trusted hop): the rightmost entry is the client; entries to its left are client-written.
    assert client_ip(scope("6.6.6.6, 203.0.113.7", 1)) == "203.0.113.7"
    assert client_ip(scope("6.6.6.6, 203.0.113.7", None, env="prod")) == "203.0.113.7", "prod default: 1 hop"
    # No trusted proxy (local, tests): X-Forwarded-For is ignored entirely, so it cannot be faked.
    assert client_ip(scope("6.6.6.6, 203.0.113.7", 0)) == "10.0.0.9"
    assert client_ip(scope("203.0.113.7", None)) == "10.0.0.9"
    assert client_ip(scope(None, 1)) == "10.0.0.9"


@pytest.fixture
async def strict_auth(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_RATE_LIMIT_PER_MINUTE", "3")
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")  # as on Railway
    from lifeline_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_demo_sign_in_is_limited_per_ip(strict_auth: httpx.AsyncClient) -> None:
    def hdr(left: str) -> dict[str, str]:
        return {"x-forwarded-for": f"{left}, 198.51.100.1"}

    codes = [(await strict_auth.post("/v1/auth/demo", json={"device_id": f"rotating-device-{i:03d}"},
                                     headers=hdr(f"1.1.1.{i}"))).status_code for i in range(4)]
    assert codes == [200, 200, 200, 429], "rotating device ids and spoofed left entries do not help"
    r = await strict_auth.post("/v1/auth/demo", json={"device_id": "other-ip-device-01"},
                               headers={"x-forwarded-for": "198.51.100.2"})
    assert r.status_code == 200
