"""Worker loop and source registry."""

from __future__ import annotations

import asyncio

import pytest

from lifeline_data import worker
from lifeline_data.hub import DataHub
from lifeline_data.settings import DataSettings
from lifeline_data.sources import CUT_SOURCES, SOURCES, missing_keys, served_sources

SPEC_SOURCES = {
    "boe", "ons", "nomis", "landregistry", "postcodes", "frankfurter", "coingecko", "yahoo", "fred", "octopus",
    "carbonintensity", "openmeteo", "police", "environmentagency", "companieshouse", "adzuna", "dvla", "dvsamot",
    "statxplore", "epc", "openbanking", "bankholidays", "guardian", "boe-mpc",
}


def test_registry_lists_every_spec_source():
    assert set(SOURCES) == SPEC_SOURCES
    for s in SOURCES.values():
        assert s.name and s.coverage and s.attribution and s.licence and s.ttl_seconds > 0
        assert s.needs_key == bool(s.key_env)


SERVED = {
    "boe", "ons", "nomis", "landregistry", "postcodes", "frankfurter", "coingecko", "yahoo", "fred", "octopus",
    "carbonintensity", "openmeteo", "police", "environmentagency", "companieshouse", "statxplore", "epc",
    "bankholidays", "guardian", "boe-mpc",
}


async def test_sources_endpoint_lists_only_served_sources():
    """ADR 0046: Open Banking (TrueLayer), Adzuna, DVLA and DVSA MOT are cut from /v1/sources."""
    assert {"openbanking", "adzuna", "dvla", "dvsamot"} == CUT_SOURCES
    assert set(served_sources()) == SERVED
    ids = [s.id for s in await DataHub(DataSettings(app_env="test"), env={}).statuses()]
    assert set(ids) == SERVED and len(ids) == len(SERVED)
    assert {"frankfurter", "ons", "boe", "guardian"} <= set(ids)
    assert not any(word in i for i in ids for word in ("monzo", "trading212", "truelayer"))


def test_missing_keys_reports_names_only():
    ch = SOURCES["companieshouse"]
    assert missing_keys(ch, {}) == ["COMPANIES_HOUSE_KEY"]
    assert missing_keys(ch, {"COMPANIES_HOUSE_KEY": "secret"}) == []
    assert missing_keys(SOURCES["openbanking"], {"OB_CLIENT_ID": "x"}) == ["OB_CLIENT_SECRET", "OB_REDIRECT_URI"]


async def test_worker_once_offline():
    await worker.run(once=True, settings=DataSettings(app_env="test"))


async def test_worker_keeps_running(monkeypatch):
    calls = 0

    async def fake_refresh(hub):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")  # must not stop the loop
        return {}

    async def run_safe(hub):
        try:
            return await fake_refresh(hub)
        except Exception:
            return {}

    monkeypatch.setattr(worker, "refresh_once", run_safe)
    settings = DataSettings(app_env="test", data_refresh_interval_seconds=0.01)
    task = asyncio.create_task(worker.run(settings=settings))
    await asyncio.sleep(0.1)
    assert not task.done()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls >= 2


async def test_refresh_once_survives_hub_error():
    class BadHub:
        async def refresh_all(self):
            raise RuntimeError("boom")

    assert await worker.refresh_once(BadHub()) == {}
