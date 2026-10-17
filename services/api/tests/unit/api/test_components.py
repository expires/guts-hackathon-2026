"""Unit tests for API components that do not need sim, engine or data."""

from __future__ import annotations

import httpx
import pytest
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

from lifeline_api.auth import demo_subject, issue_token, verify_token
from lifeline_api.bodylimit import BodySizeLimitMiddleware
from lifeline_api.errors import ApiError, CatchAllMiddleware, install_error_handlers
from lifeline_api.ratelimit import MemoryBucket, RedisBucket
from lifeline_api.settings import Settings
from lifeline_api.state import AppState
from lifeline_api.store import LifeRecord, MemoryLifeStore, macro_hash
from lifeline_contracts.macro import MacroKey, MacroTable, MacroValue


def _is_error(body: object) -> bool:
    return isinstance(body, dict) and set(body) == {"error"} and {"code", "message", "source"} <= set(body["error"])


# ---------- rate limit ----------


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


async def test_memory_bucket_limits_and_refills() -> None:
    clock = Clock()
    b = MemoryBucket(60, clock=clock)
    for _ in range(60):
        assert await b.take("ip:1") == 0
    wait = await b.take("ip:1")
    assert wait == pytest.approx(1.0)
    assert await b.take("ip:2") == 0, "keys are independent"
    clock.t += 1.0
    assert await b.take("ip:1") == 0


async def test_redis_bucket_limits_and_refills() -> None:
    clock = Clock()
    r = FakeAsyncRedis()
    b = RedisBucket(r, 3, clock=clock)
    assert [await b.take("sub:a") for _ in range(3)] == [0, 0, 0]
    assert await b.take("sub:a") > 0
    clock.t += 20.0  # 3/min -> one token per 20 s
    assert await b.take("sub:a") == 0
    assert await r.ttl("rl:sub:a") > 0


async def test_redis_bucket_falls_back_on_error() -> None:
    class Broken:
        def pipeline(self, **_: object) -> object:
            raise ConnectionError("down")

    fb = MemoryBucket(1)
    b = RedisBucket(Broken(), 1, fallback=fb)
    assert await b.take("ip:x") == 0
    assert await b.take("ip:x") > 0


# ---------- auth ----------


def _state(**kw: object) -> AppState:
    s = Settings(app_env="test", **kw)  # type: ignore[arg-type]
    return AppState(settings=s, store=MemoryLifeStore(), hub=None, limiter=MemoryBucket(10),  # type: ignore[arg-type]
                    jwt_secret=s.signing_secret())


def test_jwt_roundtrip_and_rejects() -> None:
    st = _state()
    tok = issue_token(st, "demo_abc")
    assert tok.token_type == "bearer" and tok.expires_in == st.settings.jwt_ttl_seconds
    assert verify_token(st, tok.access_token) == "demo_abc"
    assert verify_token(st, tok.access_token + "x") is None
    assert verify_token(st, "garbage") is None
    expired = issue_token(st, "demo_abc", now=1)
    assert verify_token(st, expired.access_token) is None
    other = _state(jwt_secret="another-secret-value-that-is-long-enough")
    assert verify_token(other, tok.access_token) is None


def test_demo_subject_stable_and_opaque() -> None:
    assert demo_subject("device-1234") == demo_subject("device-1234")
    assert demo_subject("device-1234") != demo_subject("device-5678")
    assert "device" not in demo_subject("device-1234")


def test_prod_requires_jwt_secret() -> None:
    with pytest.raises(RuntimeError):
        Settings(app_env="prod").signing_secret()


# ---------- store ----------


def _table(v: float) -> MacroTable:
    mv = MacroValue(key=MacroKey.BANK_RATE, year=2006, region=None, value=v, source="boe", series_id="IUMBEDR",
                    status="mock")
    return MacroTable(values={MacroTable.make_key(MacroKey.BANK_RATE, 2006, None): mv})


def test_macro_hash_is_stable_and_content_sensitive() -> None:
    assert macro_hash(_table(4.5)) == macro_hash(_table(4.5))
    assert macro_hash(_table(4.5)) != macro_hash(_table(4.75))


async def test_memory_store_owner_isolation() -> None:
    from lifeline_contracts.domain import Life

    store = MemoryLifeStore()
    life = Life.model_construct(id="lf_abcdef12")  # shape is irrelevant for the store
    await store.create(LifeRecord(id="lf_abcdef12", owner="a", life=life, macro_hash="h"))
    assert (await store.get("lf_abcdef12", "a")) is not None
    assert (await store.get("lf_abcdef12", "b")) is None
    with pytest.raises(KeyError):
        await store.create(LifeRecord(id="lf_abcdef12", owner="b", life=life, macro_hash="h"))
    await store.put_macro("h", _table(1.0))
    await store.put_macro("h", _table(2.0))
    t = await store.get_macro("h")
    assert t is not None and t.value(MacroKey.BANK_RATE, 2006) == 1.0, "first snapshot wins"


# ---------- error format, body limit ----------


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int


def _mini_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.post("/echo")
    async def echo(body: Body) -> Body:
        return body

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internals")

    @app.get("/conflict")
    async def conflict() -> None:
        raise ApiError(409, "pending_events", "Answer first", source="sim")

    app.add_middleware(BodySizeLimitMiddleware, max_bytes=100)
    app.add_middleware(CatchAllMiddleware)
    return app


@pytest.fixture
async def mini() -> httpx.AsyncClient:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_mini_app()), base_url="http://t") as c:
        yield c  # type: ignore[misc]


async def test_error_format(mini: httpx.AsyncClient) -> None:
    r = await mini.get("/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = await mini.delete("/echo")
    assert r.status_code == 405 and _is_error(r.json())
    r = await mini.post("/echo", json={"n": "x"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = await mini.post("/echo", json={"n": 1, "extra": 2})
    assert r.status_code == 422 and _is_error(r.json())
    r = await mini.get("/conflict")
    assert r.status_code == 409 and r.json()["error"] == {"code": "pending_events", "message": "Answer first",
                                                           "source": "sim"}


async def test_500_hides_internals(mini: httpx.AsyncClient) -> None:
    r = await mini.get("/boom")
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal"
    assert "secret" not in r.text and "Traceback" not in r.text


async def test_body_limit(mini: httpx.AsyncClient) -> None:
    big = b'{"n": 1, "pad": "' + b"x" * 200 + b'"}'
    r = await mini.post("/echo", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"

    async def chunks():  # no content-length: streamed body
        for _ in range(5):
            yield b"x" * 50

    r = await mini.post("/echo", content=chunks(), headers={"content-type": "application/json"})
    assert r.status_code == 413 and _is_error(r.json())


# ---------- store unavailable ----------


async def test_postgres_store_down_raises_store_unavailable() -> None:
    import time

    from lifeline_api.store import PostgresLifeStore, StoreUnavailable

    # Port 1 on localhost refuses the connection at once. No external network.
    store = PostgresLifeStore("postgresql+asyncpg://u:p@127.0.0.1:1/db")
    t0 = time.monotonic()
    with pytest.raises(StoreUnavailable) as err:
        await store.get("lf_abcdef12", "a")
    assert err.value.status == 503 and err.value.code == "store_unavailable"
    with pytest.raises(StoreUnavailable):
        await store.put_macro("h", _table(1.0))
    assert not await store.ping()
    assert time.monotonic() - t0 < 10
    await store.close()


def test_sim_error_mapping() -> None:
    from lifeline_api.sim_bridge import sim_error_to_api
    from lifeline_sim.errors import SimError

    cases = {"pending_events": 409, "dead": 409, "payment_required": 402, "not_found": 404,
             "invalid_choice": 422, "invalid_action": 422}
    for code, status in cases.items():
        e = sim_error_to_api(SimError(code, "msg"))  # type: ignore[arg-type]
        assert (e.status, e.code, e.source) == (status, code, "sim")
    assert sim_error_to_api(SimError("invalid_input", "too young")).status == 422  # type: ignore[arg-type]
