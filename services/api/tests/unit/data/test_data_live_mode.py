"""ADR 0027 live mode: no mock data anywhere in lifeline_data. Demo mode keeps the fallback."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import fakeredis.aioredis
import httpx
import pytest
import respx

from lifeline_contracts.macro import MacroKey
from lifeline_data.adapters.boe import BOE_URL
from lifeline_data.finance import DEMO_SUBJECT
from lifeline_data.hub import DataHub
from lifeline_data.settings import DataSettings
from lifeline_data.sources import CUT_SOURCES, DISABLED_IN_LIVE, SOURCES

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "data"


def fx(name: str) -> str:
    return (FIXTURES / name).read_text()


@pytest.fixture
def live_settings() -> DataSettings:
    return DataSettings(app_env="test", data_mode="live", backoff_base_seconds=0, redis_url="", database_url="")


def live_hub(live_settings, client, clock, no_sleep, **kw) -> DataHub:
    return DataHub(live_settings, client=client, clock=clock, sleep=no_sleep, env=kw.pop("env", {}), **kw)


def test_default_mode_is_demo(monkeypatch):
    monkeypatch.delenv("DATA_MODE", raising=False)
    assert DataSettings().data_mode == "demo"
    monkeypatch.setenv("DATA_MODE", "live")
    assert DataSettings().live_mode


async def test_statuses_offline_live_mode_are_unavailable_never_mock(live_settings):
    hub = DataHub(live_settings, env={})
    statuses = {s.id: s for s in await hub.statuses()}
    assert all(s.status == "unavailable" for s in statuses.values())
    for sid, reason in DISABLED_IN_LIVE.items():
        if sid in statuses:
            assert statuses[sid].last_error == f"Disabled: {reason}"
    assert not CUT_SOURCES & set(statuses)
    assert statuses["companieshouse"].last_error.startswith("COMPANIES_HOUSE_KEY not set")
    assert statuses["yahoo"].last_error.startswith("Disabled: Blocked or timing out")


async def test_disabled_source_sends_no_request_even_with_key(live_settings, client, clock, no_sleep):
    with respx.mock(assert_all_called=False) as router:
        route = router.route().mock(return_value=httpx.Response(200, json={}))
        hub = live_hub(live_settings, client, clock, no_sleep, env={"ADZUNA_APP_ID": "a", "ADZUNA_APP_KEY": "b"})
        assert await hub.series("adzuna", "advertised-salary") == []
        assert route.call_count == 0


async def test_series_failure_gives_empty_not_mock(live_settings, client, clock, no_sleep):
    with respx.mock(assert_all_called=False) as router:
        router.route().mock(side_effect=httpx.ConnectError("down"))
        hub = live_hub(live_settings, client, clock, no_sleep)
        assert await hub.series("boe", "IUMBEDR") == []
        st = next(s for s in await hub.statuses() if s.id == "boe")
        assert st.status == "unavailable" and st.last_error


async def test_series_failure_after_good_fetch_serves_cached(live_settings, client, clock, no_sleep):
    with respx.mock(assert_all_called=False) as router:
        route = router.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(200, text=fx("boe_iadb.csv")))
        hub = live_hub(live_settings, client, clock, no_sleep, redis=fakeredis.aioredis.FakeRedis())
        assert all(o.status == "live" for o in await hub.series("boe", "IUMBEDR"))
        clock.advance(SOURCES["boe"].ttl_seconds + 1)
        route.mock(side_effect=httpx.ConnectTimeout("down"))
        got = await hub.series("boe", "IUMBEDR")
        assert got and all(o.status == "cached" for o in got)


async def test_macro_table_live_mode_has_only_real_values(live_settings, client, clock, no_sleep):
    with respx.mock(assert_all_called=False) as router:
        router.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(200, text=fx("boe_iadb.csv")))
        router.route().mock(side_effect=httpx.ConnectError("down"))
        table = await live_hub(live_settings, client, clock, no_sleep).macro_table()
    assert table.values and all(v.status in ("live", "cached") for v in table.values.values())
    assert {v.source for v in table.values.values()} == {"boe"}
    assert table.get(MacroKey.BANK_RATE, 2008).value == 2.0
    with pytest.raises(KeyError):
        table.get(MacroKey.CPI_INFLATION, 2008)  # gap stays a gap
    assert not table.years(MacroKey.HOUSE_PRICE)


async def test_macro_table_live_mode_offline_is_empty(live_settings):
    table = await DataHub(live_settings, env={}).macro_table()
    assert table.values == {}


async def test_demo_mode_still_fills_with_mock(settings, client, clock, no_sleep):
    with respx.mock(assert_all_called=False) as router:
        router.route().mock(side_effect=httpx.ConnectError("down"))
        hub = DataHub(settings, client=client, clock=clock, sleep=no_sleep, env={})
        obs = await hub.series("boe", "IUMBEDR")
        table = await hub.macro_table()
    assert obs and all(o.status == "mock" for o in obs)
    assert table.get(MacroKey.CPI_INFLATION, 2008).status == "mock"


async def test_finance_snapshot_none_in_live_mode(live_settings, settings):
    assert await DataHub(live_settings, env={}).finance_snapshot(DEMO_SUBJECT) is None
    assert await DataHub(settings, env={}).finance_snapshot(DEMO_SUBJECT) is None  # demo mode: no persona


async def test_postcode_lookup_live_mode_no_mock(live_settings, client, clock, no_sleep):
    assert await DataHub(live_settings, env={}).lookup_postcode("LS6 1AN") is None
    with respx.mock(assert_all_called=False) as router:
        router.get(url__startswith="https://api.postcodes.io/").mock(
            return_value=httpx.Response(200, text=fx("postcodes_sw1a1aa.json"))
        )
        hit = await live_hub(live_settings, client, clock, no_sleep).lookup_postcode("SW1A 1AA")
    assert hit is not None and hit["region"] == "london"


async def test_weather_live_mode_only_real_days(live_settings, client, clock, no_sleep):
    assert await DataHub(live_settings, env={}).daily_weather("london", date(2026, 10, 1), date(2026, 10, 5)) == []
    with respx.mock(assert_all_called=False) as router:
        router.get(url__startswith="https://archive-api.open-meteo.com/").mock(
            return_value=httpx.Response(200, text=fx("openmeteo_archive_leeds.json"))
        )
        router.get(url__startswith="https://api.open-meteo.com/").mock(
            return_value=httpx.Response(200, text=fx("openmeteo_forecast_leeds.json"))
        )
        rows = await live_hub(live_settings, client, clock, no_sleep).daily_weather(
            "yorkshire-and-the-humber", date(2026, 8, 30), date(2026, 9, 2), today=date(2026, 10, 17)
        )
    assert [r["date"] for r in rows] == [date(2026, 9, 1), date(2026, 9, 2)]  # 30-31 Aug not recorded
    assert all(r["status"] == "live" for r in rows)


async def test_bank_holidays_live_mode_recorded_copy_is_cached(live_settings):
    hub = DataHub(live_settings, env={})
    assert date(2026, 8, 31) in await hub.bank_holidays("london")
    st = next(s for s in await hub.statuses() if s.id == "bankholidays")
    assert st.status == "cached" and "recorded gov.uk copy" in (st.last_error or "")
