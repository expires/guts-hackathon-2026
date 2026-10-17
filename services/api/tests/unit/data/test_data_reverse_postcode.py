"""Reverse postcode lookup (postcodes.io). Recorded fixture; no network."""

from __future__ import annotations

from pathlib import Path

import fakeredis.aioredis
import httpx
import pytest
import respx

from lifeline_data.adapters.postcodes import POSTCODES_REVERSE_URL
from lifeline_data.hub import DataHub
from lifeline_data.settings import DataSettings
from lifeline_data.sources import SOURCES

FIXTURE = (Path(__file__).resolve().parents[2] / "fixtures" / "data" / "postcodes_reverse_leeds.json").read_text()
LEEDS = (53.8078, -1.5607)


def make(settings, client, clock, no_sleep, **kw) -> DataHub:
    return DataHub(settings, client=client, clock=clock, sleep=no_sleep, env={}, **kw)


@respx.mock
async def test_reverse_live_then_fresh_cache_then_stale(settings, client, clock, no_sleep):
    route = respx.get(POSTCODES_REVERSE_URL).mock(return_value=httpx.Response(200, text=FIXTURE))
    hub = make(settings, client, clock, no_sleep, redis=fakeredis.aioredis.FakeRedis())
    got = await hub.reverse_postcode(*LEEDS)
    assert got == {"postcode": "LS6 1AN", "region": "yorkshire-and-the-humber", "town": "Leeds", "status": "live"}
    params = route.calls.last.request.url.params
    assert params["lat"] == "53.8078" and params["lon"] == "-1.5607" and params["limit"] == "1"
    assert (await hub.reverse_postcode(53.80781, -1.56072))["status"] == "live" and route.call_count == 1
    clock.advance(SOURCES["postcodes"].ttl_seconds + 1)
    route.mock(side_effect=httpx.ConnectTimeout("down"))
    stale = await hub.reverse_postcode(*LEEDS)
    assert stale is not None and stale["status"] == "cached" and stale["postcode"] == "LS6 1AN"


@respx.mock
async def test_reverse_at_sea_is_none(settings, client, clock, no_sleep):
    respx.get(POSTCODES_REVERSE_URL).mock(return_value=httpx.Response(200, json={"status": 200, "result": None}))
    assert await make(settings, client, clock, no_sleep).reverse_postcode(50.0, -4.0) is None


@pytest.mark.parametrize(("lat", "lon"), [(48.9, -1.0), (61.6, -1.0), (53.0, -8.8), (53.0, 2.1), (40.7, -74.0)])
async def test_reverse_outside_uk_box_sends_nothing(settings, client, clock, no_sleep, lat, lon):
    with respx.mock(assert_all_called=False) as router:
        route = router.route().mock(return_value=httpx.Response(200, text=FIXTURE))
        assert await make(settings, client, clock, no_sleep).reverse_postcode(lat, lon) is None
        assert route.call_count == 0


@respx.mock
async def test_reverse_failure_live_mode_is_none_and_breaker_opens(client, clock, no_sleep):
    live = DataSettings(app_env="test", data_mode="live", backoff_base_seconds=0, redis_url="", database_url="")
    route = respx.get(POSTCODES_REVERSE_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    hub = make(live, client, clock, no_sleep)
    for _ in range(3):
        assert await hub.reverse_postcode(*LEEDS) is None
    assert route.call_count == 9  # 3 tries x 3 calls
    assert await hub.reverse_postcode(*LEEDS) is None and route.call_count == 9  # breaker open
    st = next(s for s in await hub.statuses() if s.id == "postcodes")
    assert st.status == "unavailable" and "circuit open" in (st.last_error or "")


@respx.mock
async def test_reverse_bad_payload_rejected(settings, client, clock, no_sleep):
    respx.get(POSTCODES_REVERSE_URL).mock(return_value=httpx.Response(200, json={"result": [{"postcode": "X"}]}))
    assert await make(settings, client, clock, no_sleep).reverse_postcode(*LEEDS) is None


async def test_reverse_offline_is_none(settings):
    assert await DataHub(settings, env={}).reverse_postcode(*LEEDS) is None
