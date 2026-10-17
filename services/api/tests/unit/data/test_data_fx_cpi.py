"""ADR 0060: Frankfurter FX for any supported pair, and the latest ONS CPI rate. No network."""

from __future__ import annotations

import json
from datetime import date

import fakeredis.aioredis
import httpx
import pytest
import respx

from lifeline_data.adapters.market import FX_CURRENCIES, FX_UNIT, fx_pair, parse_frankfurter_latest
from lifeline_data.base import PayloadError
from lifeline_data.hub import DataHub
from lifeline_data.sources import SOURCES

FX_LATEST = "https://api.frankfurter.dev/v1/latest"


def make_hub(settings, client, clock, no_sleep, **kw) -> DataHub:
    return DataHub(settings, client=client, clock=clock, sleep=no_sleep, env={}, **kw)


def test_currency_list_matches_recorded_frankfurter_list(fixture_text):
    assert set(json.loads(fixture_text("frankfurter_currencies.json"))) == FX_CURRENCIES


def test_fx_pair_rules():
    assert fx_pair("cny", " gbp ") == "CNYGBP"
    assert fx_pair("GBP", "GBP") is None
    assert fx_pair("XXX", "GBP") is None and fx_pair("GBP", "BTC") is None


def test_parse_latest(fixture_text):
    assert parse_frankfurter_latest(fixture_text("frankfurter_latest_cnygbp.json"), "CNY", "GBP") == (
        date(2026, 10, 16), 0.11215)
    with pytest.raises(PayloadError):
        parse_frankfurter_latest(fixture_text("frankfurter_latest_cnygbp.json"), "USD", "GBP")
    with pytest.raises(PayloadError):
        parse_frankfurter_latest({"base": "CNY", "date": "2026-10-16", "rates": {"GBP": 0}}, "CNY", "GBP")
    with pytest.raises(PayloadError):
        parse_frankfurter_latest(fixture_text("frankfurter_404.json"), "CNY", "GBP")


def test_ttl_is_six_hours():
    assert SOURCES["frankfurter"].ttl_seconds == 6 * 3600
    assert "European Central Bank" in SOURCES["frankfurter"].attribution


@respx.mock
async def test_fx_rate_live_then_cached(settings, client, clock, no_sleep, fixture_text):
    route = respx.get(url__startswith=FX_LATEST).mock(
        return_value=httpx.Response(200, text=fixture_text("frankfurter_latest_cnygbp.json")))
    hub = make_hub(settings, client, clock, no_sleep, redis=fakeredis.aioredis.FakeRedis())
    assert await hub.fx_rate("CNY", "GBP") == (0.11215, date(2026, 10, 16))
    assert dict(route.calls.last.request.url.params) == {"from": "CNY", "to": "GBP"}
    assert await hub.fx_rate("cny", "gbp") == (0.11215, date(2026, 10, 16))
    assert route.call_count == 1  # fresh cache inside 6 h
    obs = await hub.series("frankfurter", "CNYGBP")
    assert obs[0].unit == FX_UNIT and obs[0].status == "live"
    # After the TTL the source fails: the stale value is served as cached, not invented.
    clock.advance(6 * 3600 + 1)
    route.mock(return_value=httpx.Response(503))
    assert await hub.fx_rate("CNY", "GBP") == (0.11215, date(2026, 10, 16))
    states = {s.id: s for s in await hub.statuses()}
    assert states["frankfurter"].status == "cached"


@respx.mock
async def test_fx_rate_large_values_and_unknown_codes(settings, client, clock, no_sleep, fixture_text):
    respx.get(url__startswith=FX_LATEST).mock(
        return_value=httpx.Response(200, text=fixture_text("frankfurter_latest_gbpjpy.json")))
    hub = make_hub(settings, client, clock, no_sleep)
    assert await hub.fx_rate("GBP", "JPY") == (210.72, date(2026, 10, 16))
    assert await hub.fx_rate("GBP", "XXX") is None  # never fetched
    assert await hub.fx_rate("GBP", "GBP") is None
    assert respx.calls.call_count == 1


@respx.mock
async def test_fx_rate_unavailable_is_none(settings, client, clock, no_sleep):
    respx.get(url__startswith=FX_LATEST).mock(side_effect=httpx.ConnectError("down"))
    hub = make_hub(settings, client, clock, no_sleep)
    assert await hub.fx_rate("CNY", "GBP") is None


async def test_gbpusd_mock_is_never_returned(settings):
    hub = DataHub(settings, env={})  # offline: GBPUSD has a labelled mock series, which must not count
    assert await hub.series("frankfurter", "GBPUSD")
    assert await hub.fx_rate("GBP", "USD") is None
    assert await hub.cpi() is None


@respx.mock
async def test_gbpusd_uses_history_latest(settings, client, clock, no_sleep, fixture_text):
    respx.get(url__startswith="https://api.frankfurter.dev/v1/1999").mock(
        return_value=httpx.Response(200, text=fixture_text("frankfurter_gbpusd.json")))
    hub = make_hub(settings, client, clock, no_sleep)
    rate, day = await hub.fx_rate("GBP", "USD")
    history = json.loads(fixture_text("frankfurter_gbpusd.json"))["rates"]
    last = max(history)
    assert day == date.fromisoformat(last) and rate == history[last]["USD"]


@respx.mock
async def test_cpi_latest(settings, client, clock, no_sleep, fixture_text):
    respx.get(url__startswith="https://www.ons.gov.uk/").mock(
        return_value=httpx.Response(200, text=fixture_text("ons_d7g7.json")))
    hub = make_hub(settings, client, clock, no_sleep)
    assert await hub.cpi() == (3.1, date(2026, 8, 1))


def test_frankfurter_uses_current_host():
    from lifeline_data.adapters import market

    for url in (market.FRANKFURTER_URL, market.FRANKFURTER_LATEST_URL):
        assert url.startswith("https://api.frankfurter.dev/v1/")
    assert SOURCES["frankfurter"].url == "https://frankfurter.dev/"
