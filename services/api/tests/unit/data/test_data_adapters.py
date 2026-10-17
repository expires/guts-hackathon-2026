"""Adapter base: retries, timeout, breaker, validation. Network is mocked with respx."""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest
import respx

from lifeline_contracts.observation import Observation
from lifeline_data.adapters.boe import BOE_URL, BoEAdapter
from lifeline_data.adapters.landregistry import LR_LIST_URL, LandRegistryAdapter
from lifeline_data.adapters.nomis import NOMIS_BASE, NomisAdapter
from lifeline_data.adapters.ons import OnsAdapter
from lifeline_data.base import (
    CircuitBreaker,
    CircuitOpenError,
    FetchError,
    PayloadError,
    parse_number,
    validate_observations,
)


def _obs(value: float, day: date = date(2020, 1, 1), unit: str = "percent") -> Observation:
    return Observation(
        series_id="X", source="t", date=day, value=value, unit=unit, fetched_at=datetime.now(UTC), status="live"
    )


@respx.mock
async def test_boe_fetch_live(client, settings, fixture_text, no_sleep):
    respx.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(200, text=fixture_text("boe_iadb.csv")))
    obs = await BoEAdapter(client, settings, sleep=no_sleep).fetch_validated("IUMBV42")
    assert obs and all(o.series_id == "IUMBV42" and o.status == "live" and o.source == "boe" for o in obs)


@respx.mock
async def test_browser_user_agent_sent(client, settings, fixture_text, no_sleep):
    route = respx.get(url__startswith=BOE_URL).mock(
        return_value=httpx.Response(200, text=fixture_text("boe_iadb.csv"))
    )
    await BoEAdapter(client, settings, sleep=no_sleep).fetch("IUMBEDR")
    assert "Mozilla/5.0" in route.calls.last.request.headers["User-Agent"]


@respx.mock
async def test_ons_and_nomis_and_landregistry_fetch(client, settings, fixture_text, no_sleep):
    respx.get(url__startswith="https://www.ons.gov.uk/").mock(
        return_value=httpx.Response(200, text=fixture_text("ons_d7g7.json"))
    )
    respx.get(url__startswith=f"{NOMIS_BASE}/NM_30_1").mock(
        return_value=httpx.Response(200, text=fixture_text("nomis_ashe.csv"))
    )
    respx.get(url__startswith=LR_LIST_URL).mock(
        return_value=httpx.Response(200, text=fixture_text("landregistry_london.json"))
    )
    assert await OnsAdapter(client, settings, sleep=no_sleep).fetch_validated("D7G7")
    ashe = await NomisAdapter(client, settings, sleep=no_sleep).fetch_validated("NM_30_1")
    assert {o.region for o in ashe} >= {"london", "scotland", None}
    hpi = await LandRegistryAdapter(client, settings, sleep=no_sleep).fetch_validated("ukhpi-average-price", "london")
    assert hpi and all(o.region == "london" and o.unit == "gbp" for o in hpi)


@respx.mock
async def test_retry_on_503_then_success(client, settings, fixture_text, no_sleep):
    route = respx.get(url__startswith=BOE_URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(429), httpx.Response(200, text=fixture_text("boe_iadb.csv"))]
    )
    obs = await BoEAdapter(client, settings, sleep=no_sleep).fetch_validated("IUMBEDR")
    assert obs and route.call_count == 3


@respx.mock
async def test_no_retry_on_404(client, settings, no_sleep):
    route = respx.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(404))
    with pytest.raises(FetchError):
        await BoEAdapter(client, settings, sleep=no_sleep).fetch_validated("IUMBEDR")
    assert route.call_count == 1


@respx.mock
async def test_timeout_retries_three_times_then_fails(client, settings, no_sleep):
    route = respx.get(url__startswith=BOE_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(FetchError, match="timeout"):
        await BoEAdapter(client, settings, sleep=no_sleep).fetch_validated("IUMBEDR")
    assert route.call_count == 3


@respx.mock
async def test_breaker_opens_after_three_failures(client, settings, no_sleep):
    route = respx.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(500))
    adapter = BoEAdapter(client, settings, sleep=no_sleep)
    for _ in range(3):
        with pytest.raises(FetchError):
            await adapter.fetch_validated("IUMBEDR")
    calls = route.call_count
    assert adapter.breaker.state == "open"
    with pytest.raises(CircuitOpenError):
        await adapter.fetch_validated("IUMBEDR")
    assert route.call_count == calls  # no request sent while open


def test_breaker_half_open_after_reset():
    now = [0.0]
    breaker = CircuitBreaker(threshold=3, reset_seconds=60, clock=lambda: now[0])
    for _ in range(3):
        breaker.record_failure()
    assert breaker.state == "open" and not breaker.allow()
    now[0] = 61
    assert breaker.state == "half-open" and breaker.allow()
    breaker.record_failure()  # trial failed: open again
    assert breaker.state == "open"
    now[0] = 130
    breaker.record_success()
    assert breaker.state == "closed"


@respx.mock
async def test_bad_payload_counts_as_failure(client, settings, no_sleep):
    respx.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(200, text="DATE,IUMBEDR\n31 Jan 2020,abc\n"))
    adapter = BoEAdapter(client, settings, sleep=no_sleep)
    with pytest.raises(PayloadError):
        await adapter.fetch_validated("IUMBEDR")
    assert adapter.breaker.failures == 1


@respx.mock
async def test_out_of_range_payload_rejected(client, settings, no_sleep):
    respx.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(200, text="DATE,IUMBEDR\n31 Jan 2020,95\n"))
    with pytest.raises(PayloadError, match="out of range"):
        await BoEAdapter(client, settings, sleep=no_sleep).fetch_validated("IUMBEDR")


@respx.mock
async def test_html_block_page_rejected(client, settings, no_sleep):
    respx.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(200, text="<html>Access denied</html>"))
    with pytest.raises(PayloadError):
        await BoEAdapter(client, settings, sleep=no_sleep).fetch_validated("IUMBEDR")


@pytest.mark.parametrize("raw", ["", " ", "n/a", None, "nan", "inf", True])
def test_parse_number_rejects(raw):
    with pytest.raises(PayloadError):
        parse_number(raw)


def test_parse_number_accepts():
    assert parse_number("1,234.5") == 1234.5
    assert parse_number(3) == 3.0


def test_validate_rejects_empty_and_bad_dates():
    with pytest.raises(PayloadError, match="empty"):
        validate_observations([])
    with pytest.raises(PayloadError, match="date"):
        validate_observations([_obs(1.0, date(1850, 1, 1))])
    with pytest.raises(PayloadError, match="date"):
        validate_observations([_obs(1.0, date(2100, 1, 1))])
    with pytest.raises(PayloadError, match="range"):
        validate_observations([_obs(-5.0, unit="gbp")])
    assert validate_observations([_obs(4.5)])
