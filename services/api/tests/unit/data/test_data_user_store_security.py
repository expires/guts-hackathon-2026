"""V6 Tier 2: per-user snapshot encrypted at rest (T2-F5), failed delete raises (T2-F4), formula cells."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from lifeline_data.cache import user_snapshot_table
from lifeline_data.crypto import EncryptionKeyMissing, Sealer, StoreUnavailable
from lifeline_data.hub import DataHub
from lifeline_data.settings import DataSettings
from lifeline_data.statements import parse_statement, to_snapshot
from lifeline_data.statements.parse import text_cell

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "data"


def snap():
    return to_snapshot(parse_statement((FIXTURES / "statement_monzo_sample.csv").read_bytes()))


def key_env(tag: str = "a") -> dict[str, str]:
    return {"TOKEN_ENCRYPTION_KEY": "-".join(("unit", tag, "k" * 16))}  # built at run time


@pytest.fixture
def live_settings() -> DataSettings:
    return DataSettings(app_env="test", data_mode="live", backoff_base_seconds=0, redis_url="", database_url="")


async def test_ciphertext_at_rest_and_round_trip(settings, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'enc.db'}")
    s = snap()
    assert await DataHub(settings, env=key_env(), db=engine).set_user_snapshot("u1", s) is True
    async with engine.connect() as conn:
        stored = (await conn.execute(select(user_snapshot_table.c.payload))).scalar_one()
    assert "Nationwide" not in stored and "statement" not in stored and not stored.lstrip().startswith("{")
    assert await DataHub(settings, env=key_env(), db=engine).get_user_snapshot("u1") == s
    # A different key cannot read it (returns None, never raises).
    assert await DataHub(settings, env=key_env("b"), db=engine).get_user_snapshot("u1") is None
    await engine.dispose()


async def test_live_mode_without_key_refuses_to_store(live_settings):
    hub = DataHub(live_settings, env={})
    with pytest.raises(EncryptionKeyMissing):
        await hub.set_user_snapshot("u2", snap())
    assert await hub.get_user_snapshot("u2") is None


async def test_prod_without_key_refuses(settings):
    prod = DataSettings(app_env="production", backoff_base_seconds=0, redis_url="", database_url="", data_offline=True)
    with pytest.raises(EncryptionKeyMissing):
        await DataHub(prod, env={}).set_user_snapshot("u3", snap())


async def test_demo_without_key_uses_ephemeral_key(settings):
    hub = DataHub(settings, env={})
    assert await hub.set_user_snapshot("u4", snap()) is False
    assert await hub.get_user_snapshot("u4") == snap()


def test_sealer_accepts_fernet_key_and_passphrase():
    fernet_key = Fernet.generate_key().decode()
    for env in ({"TOKEN_ENCRYPTION_KEY": fernet_key}, key_env()):
        sealer = Sealer(env, strict=True)
        token = sealer.seal("secret data")
        assert token != "secret data" and sealer.open(token) == "secret data"
    with pytest.raises(EncryptionKeyMissing):
        Sealer({}, strict=True).seal("x")


async def test_failed_delete_raises(settings, tmp_path):
    broken = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'missing-dir' / 'x.db'}")
    hub = DataHub(settings, env=key_env(), db=broken)
    with pytest.raises(StoreUnavailable):
        await hub.delete_user_snapshot("u5")
    await broken.dispose()


async def test_delete_without_database_is_fine(settings):
    hub = DataHub(settings, env=key_env())
    await hub.set_user_snapshot("u6", snap())
    await hub.delete_user_snapshot("u6")
    assert await hub.get_user_snapshot("u6") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("=SUM(A1)", "'=SUM(A1)"), ("+44 7700", "'+44 7700"), ("-12", "'-12"), ("@cmd", "'@cmd"), ("Tesco", "Tesco")],
)
def test_formula_cells_defused(raw, expected):
    assert text_cell(raw, 80) == expected


async def test_two_processes_postgres_is_source_of_truth(settings, tmp_path, clock):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'two.db'}")
    a = DataHub(settings, env=key_env(), db=engine, clock=clock)
    b = DataHub(settings, env=key_env(), db=engine, clock=clock)
    s = snap()
    assert await a.set_user_snapshot("u7", s) is True
    assert await b.get_user_snapshot("u7") == s
    await b.delete_user_snapshot("u7")
    assert await a.get_user_snapshot("u7") is None  # a's memory copy is not served after b deleted
    await engine.dispose()


async def test_failed_write_raises_and_leaves_memory_unchanged(settings, tmp_path):
    broken = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nope' / 'x.db'}")
    hub = DataHub(settings, env=key_env(), db=broken)
    with pytest.raises(StoreUnavailable):
        await hub.set_user_snapshot("u8", snap())
    assert hub.user_snapshots._memory == {}
    assert await hub.get_user_snapshot("u8") is None
    await broken.dispose()


async def test_read_failure_serves_memory_only_briefly(settings, tmp_path, clock):
    from sqlalchemy import text

    from lifeline_data.cache import MEMORY_TTL_SECONDS

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ttl.db'}")
    hub = DataHub(settings, env=key_env(), db=engine, clock=clock)
    s = snap()
    await hub.set_user_snapshot("u9", s)
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE user_finance_snapshot"))  # reads now fail
    assert await hub.get_user_snapshot("u9") == s
    clock.advance(MEMORY_TTL_SECONDS + 1)
    assert await hub.get_user_snapshot("u9") is None
    await engine.dispose()
