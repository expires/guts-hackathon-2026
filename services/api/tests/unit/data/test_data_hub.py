"""DataHub fallback chain: live -> Redis (cached) -> Postgres (cached) -> mock. Never raises."""

from __future__ import annotations

from pathlib import Path

import fakeredis.aioredis
import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import create_async_engine

from lifeline_contracts.macro import MacroKey, MacroTable
from lifeline_contracts.observation import SourceStatus
from lifeline_data.adapters.boe import BOE_URL
from lifeline_data.adapters.ons import ONS_BASE, PIPR_PAGE
from lifeline_data.hub import DataHub
from lifeline_data.sources import SOURCES, served_sources

EMPTY_ENV: dict[str, str] = {}
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "data"


def make_hub(settings, client, clock, no_sleep, **kw) -> DataHub:
    return DataHub(settings, client=client, clock=clock, sleep=no_sleep, env=kw.pop("env", EMPTY_ENV), **kw)


def status_of(statuses: list[SourceStatus], sid: str) -> SourceStatus:
    return next(s for s in statuses if s.id == sid)


@respx.mock
async def test_live_then_fresh_cache_hit(settings, client, clock, no_sleep, fixture_text):
    route = respx.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(200, text=fixture_text("boe_iadb.csv")))
    hub = make_hub(settings, client, clock, no_sleep, redis=fakeredis.aioredis.FakeRedis())
    first = await hub.series("boe", "IUMBEDR")
    assert first and all(o.status == "live" for o in first)
    again = await hub.series("boe", "IUMBEDR")
    assert again == first and route.call_count == 1  # served from fresh Redis entry
    assert status_of(await hub.statuses(), "boe").status == "live"


@respx.mock
async def test_timeout_falls_back_to_cached(settings, client, clock, no_sleep, fixture_text):
    route = respx.get(url__startswith=BOE_URL)
    route.mock(return_value=httpx.Response(200, text=fixture_text("boe_iadb.csv")))
    hub = make_hub(settings, client, clock, no_sleep, redis=fakeredis.aioredis.FakeRedis())
    live = await hub.series("boe", "IUMBEDR")
    clock.advance(SOURCES["boe"].ttl_seconds + 1)  # entry is now stale
    route.mock(side_effect=httpx.ConnectTimeout("down"))
    got = await hub.series("boe", "IUMBEDR")
    assert [o.value for o in got] == [o.value for o in live]
    assert all(o.status == "cached" for o in got)
    st = status_of(await hub.statuses(), "boe")
    assert st.status == "cached" and "timeout" in (st.last_error or "")


@respx.mock
async def test_redis_down_uses_memory_cache(settings, client, clock, no_sleep, fixture_text):
    class BrokenRedis:
        async def get(self, *_a, **_k):
            raise ConnectionError("redis down")

        async def set(self, *_a, **_k):
            raise ConnectionError("redis down")

        async def aclose(self):
            return None

    route = respx.get(url__startswith=BOE_URL)
    route.mock(return_value=httpx.Response(200, text=fixture_text("boe_iadb.csv")))
    hub = make_hub(settings, client, clock, no_sleep, redis=BrokenRedis())
    assert await hub.series("boe", "IUMBEDR")
    clock.advance(SOURCES["boe"].ttl_seconds + 1)
    route.mock(return_value=httpx.Response(503))
    got = await hub.series("boe", "IUMBEDR")
    assert got and all(o.status == "cached" for o in got)


@respx.mock
async def test_postgres_snapshot_fallback(settings, client, clock, no_sleep, fixture_text):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    route = respx.get(url__startswith=BOE_URL)
    route.mock(return_value=httpx.Response(200, text=fixture_text("boe_iadb.csv")))
    writer = make_hub(settings, client, clock, no_sleep, db=engine)
    live = await writer.series("boe", "IUMBV34")
    # New hub: empty Redis/memory cache, same database.
    route.mock(side_effect=httpx.ReadTimeout("down"))
    reader = make_hub(settings, client, clock, no_sleep, db=engine)
    got = await reader.series("boe", "IUMBV34")
    assert [o.value for o in got] == [o.value for o in live]
    assert all(o.status == "cached" for o in got)
    await engine.dispose()


@respx.mock
async def test_everything_down_gives_mock(settings, client, clock, no_sleep):
    respx.get(url__startswith=BOE_URL).mock(side_effect=httpx.ConnectError("no network"))
    hub = make_hub(settings, client, clock, no_sleep)
    got = await hub.series("boe", "IUMBEDR")
    assert got and all(o.status == "mock" for o in got)
    assert {o.date.year for o in got} == set(range(1990, 2027))
    assert status_of(await hub.statuses(), "boe").status == "mock"


@respx.mock
async def test_breaker_open_serves_cached_without_network(settings, client, clock, no_sleep, fixture_text):
    route = respx.get(url__startswith=BOE_URL)
    route.mock(return_value=httpx.Response(200, text=fixture_text("boe_iadb.csv")))
    hub = make_hub(settings, client, clock, no_sleep)
    await hub.series("boe", "IUMBEDR")
    clock.advance(300)  # past the adapter GET memo
    route.mock(return_value=httpx.Response(500))
    for _ in range(3):
        await hub.series("boe", "IUMBEDR", force=True)
    calls = route.call_count
    got = await hub.series("boe", "IUMBEDR", force=True)
    assert route.call_count == calls
    assert all(o.status == "cached" for o in got)
    assert "circuit open" in (status_of(await hub.statuses(), "boe").last_error or "")


async def test_missing_key_gives_mock_status(settings):
    hub = DataHub(settings, env={})
    st = status_of(await hub.statuses(), "companieshouse")
    assert st.status == "mock" and st.needs_key
    assert st.last_error == "COMPANIES_HOUSE_KEY not set (or COMPANIES_HOUSE_API_KEY)"
    assert await hub.series("companieshouse", "anything") == []


async def test_key_present_is_not_reported_missing(settings):
    hub = DataHub(settings, env={"COMPANIES_HOUSE_KEY": "x"})
    st = status_of(await hub.statuses(), "companieshouse")
    assert not (st.last_error or "").startswith("COMPANIES_HOUSE_KEY not set")


async def test_offline_hub_sends_no_requests(settings):
    with respx.mock(assert_all_called=False) as router:
        catch_all = router.route().mock(return_value=httpx.Response(500))
        await _offline_checks(settings)
    assert catch_all.call_count == 0


async def _offline_checks(settings):
    hub = DataHub(settings)  # APP_ENV=test, no client injected
    table = await hub.macro_table()
    assert isinstance(table, MacroTable)
    assert table.get(MacroKey.BANK_RATE, 2009).status == "mock"
    assert await hub.series("nomis", "NM_30_1", "london")
    assert await hub.lookup_postcode("SW1A 1AA") == {"region": "london", "town": "London", "postcode": "SW1A 1AA"}
    statuses = await hub.statuses()
    assert {s.id for s in statuses} == set(served_sources())
    assert all(s.status == "mock" for s in statuses)
    await hub.aclose()


async def test_unknown_source_returns_empty(settings):
    assert await DataHub(settings).series("nope", "x") == []


@respx.mock
async def test_macro_table_from_live_sources(settings, client, clock, no_sleep, fixture_text):
    respx.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(200, text=fixture_text("boe_iadb.csv")))
    respx.get(url__startswith="https://www.ons.gov.uk/").mock(
        return_value=httpx.Response(200, text=fixture_text("ons_d7g7.json"))
    )
    respx.get(url__regex=r".*nomisweb.*NM_30_1.*").mock(
        return_value=httpx.Response(200, text=fixture_text("nomis_ashe.csv"))
    )
    respx.get(url__regex=r".*nomisweb.*NM_17_5.*").mock(
        return_value=httpx.Response(200, text=fixture_text("nomis_aps.csv"))
    )
    respx.get(url__regex=r".*nomisweb.*NM_2072_1.*").mock(
        return_value=httpx.Response(200, text=fixture_text("nomis_census.csv"))
    )
    respx.get(url__startswith="https://landregistry.data.gov.uk/").mock(side_effect=httpx.ConnectError("down"))
    hub = make_hub(settings, client, clock, no_sleep)
    table = await hub.macro_table()
    assert table.get(MacroKey.BANK_RATE, 2009).status == "live"
    assert table.get(MacroKey.CPI_INFLATION, 2022).status == "live"
    assert table.get(MacroKey.MEDIAN_PAY, 2025, "london").value == pytest.approx(46414)
    assert table.get(MacroKey.HOUSE_PRICE, 2008, "london").status == "mock"  # Land Registry down
    scot = table.get(MacroKey.OWNER_OCCUPIED_SHARE, 2021, "scotland")
    assert scot.note == "UK average used" and scot.status == "live"
    for key in MacroKey:
        assert table.years(key) == list(range(1990, 2027))
    assert status_of(await hub.statuses(), "landregistry").status == "mock"


@respx.mock
async def test_postcode_live_404_and_fallback(settings, client, clock, no_sleep, fixture_text):
    respx.get("https://api.postcodes.io/postcodes/SW1A1AA").mock(
        return_value=httpx.Response(200, text=fixture_text("postcodes_sw1a1aa.json"))
    )
    respx.get("https://api.postcodes.io/postcodes/ZZ99ZZ").mock(
        return_value=httpx.Response(404, text=fixture_text("postcodes_404.json"))
    )
    respx.get("https://api.postcodes.io/postcodes/EH11YZ").mock(side_effect=httpx.ConnectError("down"))
    hub = make_hub(settings, client, clock, no_sleep)
    assert await hub.lookup_postcode("sw1a 1aa") == {"region": "london", "town": "Westminster", "postcode": "SW1A 1AA"}
    assert await hub.lookup_postcode("ZZ9 9ZZ") is None
    assert await hub.lookup_postcode("not a postcode") is None
    edin = await hub.lookup_postcode("EH1 1YZ")
    assert edin == {"region": "scotland", "town": "Edinburgh", "postcode": "EH1 1YZ"}
    assert status_of(await hub.statuses(), "postcodes").status == "mock"


async def test_hub_accepts_foreign_settings_object():
    class ApiSettings:
        app_env = "test"
        redis_url = "redis://never-used:6379/0"
        database_url = ""

    hub = DataHub(ApiSettings())
    assert hub.settings.offline and not hub.live_enabled
    assert (await hub.macro_table()).get(MacroKey.GBP_USD, 2016).value < 1.5


IPHRP_META = "https://api.beta.ons.gov.uk/v1/datasets/index-private-housing-rental-prices"
IPHRP_VERSION = IPHRP_META + "/editions/time-series/versions/41"
IPHRP_CSV = "https://download.ons.gov.uk/downloads/datasets/iphrp/41.csv"


def _mock_iphrp(fixture_text, router=respx):
    router.get(IPHRP_META).mock(
        return_value=httpx.Response(200, json={"links": {"latest_version": {"href": IPHRP_VERSION}}})
    )
    router.get(IPHRP_VERSION).mock(
        return_value=httpx.Response(200, json={"downloads": {"csv": {"href": IPHRP_CSV}}})
    )
    router.get(IPHRP_CSV).mock(return_value=httpx.Response(200, text=fixture_text("ons_iphrp.csv")))


PIPR_PAGE_URL = f"{ONS_BASE}/{PIPR_PAGE}/data"
PIPR_RELEASE = f"/{PIPR_PAGE}/16september2026"


def _mock_pipr(router=respx):
    router.get(PIPR_PAGE_URL).mock(return_value=httpx.Response(200, json={"datasets": [{"uri": PIPR_RELEASE}]}))
    router.get(f"{ONS_BASE}{PIPR_RELEASE}/data").mock(
        return_value=httpx.Response(200, json={"downloads": [{"file": "pipr.xlsx"}]})
    )
    router.get(url__startswith=f"{ONS_BASE}/file").mock(
        return_value=httpx.Response(200, content=(FIXTURES / "ons_pipr_sample.xlsx").read_bytes())
    )


def _mock_tier1_sources(fixture_text, router=respx):
    """Every no-key Tier 1 source, from recorded fixtures (Yahoo and FRED: shape samples)."""
    fx = fixture_text
    router.get(url__startswith="https://www.gov.uk/bank-holidays.json").mock(
        return_value=httpx.Response(200, text=fx("bankholidays.json"))
    )
    router.get(url__startswith="https://api.open-meteo.com/").mock(
        return_value=httpx.Response(200, text=fx("openmeteo_forecast_leeds.json"))
    )
    router.get(url__startswith="https://archive-api.open-meteo.com/").mock(
        return_value=httpx.Response(200, text=fx("openmeteo_archive_leeds.json"))
    )
    router.get(url__startswith="https://api.frankfurter.dev/v1/").mock(
        return_value=httpx.Response(200, text=fx("frankfurter_gbpusd.json"))
    )
    router.get(url__startswith="https://api.coingecko.com/").mock(
        return_value=httpx.Response(200, text=fx("coingecko_bitcoin.json"))
    )
    router.get(url__startswith="https://query1.finance.yahoo.com/").mock(
        return_value=httpx.Response(200, text=fx("yahoo_ftas_sample.json"))
    )
    router.get(url__startswith="https://fred.stlouisfed.org/").mock(
        return_value=httpx.Response(200, text=fx("fred_gilt_sample.csv"))
    )
    router.get("https://api.octopus.energy/v1/products/").mock(
        return_value=httpx.Response(200, text=fx("octopus_products.json"))
    )
    router.get(url__startswith="https://api.octopus.energy/v1/products/VAR-").mock(
        return_value=httpx.Response(200, text=fx("octopus_flexible.json"))
    )
    router.get(url__startswith="https://api.carbonintensity.org.uk/").mock(
        return_value=httpx.Response(200, text=fx("carbonintensity_regional.json"))
    )
    router.get(url__startswith="https://data.police.uk/api/crimes-street-dates").mock(
        return_value=httpx.Response(200, text=fx("police_dates.json"))
    )
    router.get(url__startswith="https://data.police.uk/api/crimes-street/").mock(
        return_value=httpx.Response(200, text=fx("police_burglary_leeds.json"))
    )
    router.get(url__startswith="https://environment.data.gov.uk/").mock(
        return_value=httpx.Response(200, text=fx("environmentagency_floods.json"))
    )


def _mock_all_sources(fixture_text, router=respx):
    _mock_pipr(router)
    _mock_tier1_sources(fixture_text, router)
    router.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(200, text=fixture_text("boe_iadb.csv")))
    router.get(url__startswith="https://www.ons.gov.uk/").mock(
        return_value=httpx.Response(200, text=fixture_text("ons_d7g7.json"))
    )
    for sid, name in (("NM_30_1", "nomis_ashe.csv"), ("NM_17_5", "nomis_aps.csv"), ("NM_2072_1", "nomis_census.csv")):
        router.get(url__regex=rf".*nomisweb.*{sid}.*").mock(return_value=httpx.Response(200, text=fixture_text(name)))
    router.get(url__startswith="https://landregistry.data.gov.uk/").mock(
        return_value=httpx.Response(200, text=fixture_text("landregistry_london.json"))
    )
    _mock_iphrp(fixture_text, router)
    router.get(url__startswith="https://api.postcodes.io/").mock(
        return_value=httpx.Response(200, text=fixture_text("postcodes_sw1a1aa.json"))
    )


async def test_two_processes_share_state_through_redis(settings, clock, no_sleep, fixture_text):
    """Worker hub refreshes; a separate API hub sharing the same Redis reports the result."""
    redis = fakeredis.aioredis.FakeRedis()
    with respx.mock(assert_all_called=False) as router:
        _mock_all_sources(fixture_text, router)
        async with httpx.AsyncClient() as wc:
            worker_hub = make_hub(settings, wc, clock, no_sleep, redis=redis)
            await worker_hub.refresh_all()
        fetches = router.calls.call_count

        # API hub: live-capable, same Redis, but its network is down.
        router.clear()
        down = router.route().mock(side_effect=httpx.ConnectError("api has no network"))
        async with httpx.AsyncClient() as ac:
            api_hub = make_hub(settings, ac, clock, no_sleep, redis=redis)
            statuses = await api_hub.statuses()
            for sid in ("boe", "ons", "nomis", "landregistry", "postcodes"):
                st = status_of(statuses, sid)
                assert st.status == "live", (sid, st)
                assert st.fetched_at is not None
            table = await api_hub.macro_table()
        assert fetches > 0 and down.call_count == 0  # API served everything from the shared cache
    assert table.get(MacroKey.BANK_RATE, 2009).status == "live"
    assert table.get(MacroKey.MEDIAN_PAY, 2025, "london").value == pytest.approx(46414)
    assert table.get(MacroKey.HOUSE_PRICE, 2025, "london").status == "live"


async def test_shared_state_stale_data_reports_cached(settings, clock, no_sleep, fixture_text):
    redis = fakeredis.aioredis.FakeRedis()
    with respx.mock(assert_all_called=False) as router:
        _mock_all_sources(fixture_text, router)
        async with httpx.AsyncClient() as wc:
            await make_hub(settings, wc, clock, no_sleep, redis=redis).refresh_all()
        clock.advance(SOURCES["boe"].ttl_seconds + 1)
        router.clear()
        router.route().mock(side_effect=httpx.ConnectError("down"))
        async with httpx.AsyncClient() as ac:
            api_hub = make_hub(settings, ac, clock, no_sleep, redis=redis)
            got = await api_hub.series("boe", "IUMBEDR")
            assert got and all(o.status == "cached" for o in got)
            assert status_of(await api_hub.statuses(), "boe").status == "cached"


async def test_postcodes_before_any_lookup_is_mock_not_fetched(settings, client, clock, no_sleep):
    """V3 F5: no lookup and no worker probe yet: report mock, like the other sources."""
    hub = make_hub(settings, client, clock, no_sleep)
    st = status_of(await hub.statuses(), "postcodes")
    assert st.status == "mock" and st.last_error == "not fetched yet"


async def test_postcodes_status_from_worker_probe(settings, clock, no_sleep, fixture_text):
    """V3 F5: the API reports the status of the last worker probe, live or failed."""
    redis = fakeredis.aioredis.FakeRedis()
    with respx.mock(assert_all_called=False) as router:
        router.get(url__startswith="https://api.postcodes.io/").mock(side_effect=httpx.ConnectError("down"))
        async with httpx.AsyncClient() as wc:
            await make_hub(settings, wc, clock, no_sleep, redis=redis).probe_postcodes()
        async with httpx.AsyncClient() as ac:
            st = status_of(await make_hub(settings, ac, clock, no_sleep, redis=redis).statuses(), "postcodes")
    assert st.status == "mock" and st.last_error


@respx.mock
async def test_postcode_200_without_result_is_bad_payload(settings, client, clock, no_sleep):
    """V3 F4: HTTP 200 with no result is not "not found" and must not mark the source live."""
    respx.get(url__startswith="https://api.postcodes.io/").mock(return_value=httpx.Response(200, json={"status": 200}))
    hub = make_hub(settings, client, clock, no_sleep)
    got = await hub.lookup_postcode("SW1A 1AA")
    assert got == {"region": "london", "town": "London", "postcode": "SW1A 1AA"}  # mock fallback
    st = status_of(await hub.statuses(), "postcodes")
    assert st.status == "mock" and "no result" in (st.last_error or "")


@respx.mock
async def test_postcode_stale_entry_served_as_cached(settings, client, clock, no_sleep, fixture_text):
    """V3 F3: postcode entries outlive their TTL, so a stale entry is the fallback."""
    route = respx.get(url__startswith="https://api.postcodes.io/")
    route.mock(return_value=httpx.Response(200, text=fixture_text("postcodes_sw1a1aa.json")))
    hub = make_hub(settings, client, clock, no_sleep, redis=fakeredis.aioredis.FakeRedis())
    assert (await hub.lookup_postcode("SW1A 1AA"))["town"] == "Westminster"
    clock.advance(SOURCES["postcodes"].ttl_seconds + 3600)
    route.mock(side_effect=httpx.ConnectError("down"))
    assert (await hub.lookup_postcode("SW1A 1AA"))["town"] == "Westminster"
    assert status_of(await hub.statuses(), "postcodes").status == "cached"


async def test_redis_outage_keeps_last_known_status(settings, clock, no_sleep, fixture_text):
    """V3 F2: the API process saw live state in Redis; Redis then fails; status stays live."""

    class FlakyRedis(fakeredis.aioredis.FakeRedis):
        down = False

        async def get(self, *a, **k):
            if FlakyRedis.down:
                raise ConnectionError("redis down")
            return await super().get(*a, **k)

    redis = FlakyRedis()
    with respx.mock(assert_all_called=False) as router:
        _mock_all_sources(fixture_text, router)
        async with httpx.AsyncClient() as wc:
            await make_hub(settings, wc, clock, no_sleep, redis=redis).refresh_all()
        router.clear()
        router.route().mock(side_effect=httpx.ConnectError("down"))
        async with httpx.AsyncClient() as ac:
            api_hub = make_hub(settings, ac, clock, no_sleep, redis=redis)
            await api_hub.macro_table()  # served from fresh Redis entries
            await api_hub.statuses()  # reads shared state once while Redis is up
            FlakyRedis.down = True
            statuses = await api_hub.statuses()
    for sid in ("boe", "ons", "nomis", "landregistry", "postcodes"):
        assert status_of(statuses, sid).status == "live", sid


async def test_fresh_cache_hit_records_local_state(settings, clock, no_sleep, fixture_text):
    """V3 F2: a fresh-cache hit alone gives the process a status, even if shared state is lost."""
    redis = fakeredis.aioredis.FakeRedis()
    with respx.mock(assert_all_called=False) as router:
        _mock_all_sources(fixture_text, router)
        async with httpx.AsyncClient() as wc:
            await make_hub(settings, wc, clock, no_sleep, redis=redis).series("boe", "IUMBEDR")
    await redis.delete("lifeline:source_state:boe")
    api_hub = make_hub(settings, httpx.AsyncClient(), clock, no_sleep, redis=redis)
    assert await api_hub.series("boe", "IUMBEDR")
    assert status_of(await api_hub.statuses(), "boe").status == "live"


@respx.mock
async def test_breaker_uses_hub_clock(settings, client, clock, no_sleep):
    """V3 F6: half-open timing follows the clock injected into DataHub."""
    route = respx.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(500))
    hub = make_hub(settings, client, clock, no_sleep)
    for _ in range(3):
        await hub.series("boe", "IUMBEDR", force=True)
    breaker = hub.adapter("boe").breaker
    assert breaker.state == "open"
    clock.advance(settings.breaker_reset_seconds + 1)
    assert breaker.state == "half-open"
    calls = route.call_count
    await hub.series("boe", "IUMBEDR", force=True)
    assert route.call_count > calls  # trial request sent


@respx.mock
async def test_adr_0014_year_end_values_from_fixtures(settings, client, clock, no_sleep, fixture_text):
    """ADR 0014: 2008 shows the crash. Recorded BoE and UK HPI fixtures."""
    respx.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(200, text=fixture_text("boe_iadb.csv")))
    respx.get(url__startswith="https://www.ons.gov.uk/").mock(
        return_value=httpx.Response(200, text=fixture_text("ons_d7g7.json"))
    )
    _mock_iphrp(fixture_text)
    respx.get(url__regex=r".*nomisweb.*").mock(side_effect=httpx.ConnectError("down"))
    respx.get(url__startswith="https://landregistry.data.gov.uk/").mock(
        return_value=httpx.Response(200, text=fixture_text("landregistry_uk_2007_2009.json"))
    )
    table = await make_hub(settings, client, clock, no_sleep).macro_table()
    hpc = table.get(MacroKey.HOUSE_PRICE_CHANGE, 2008)
    assert hpc.status == "live" and hpc.value < -10
    rate = table.get(MacroKey.BANK_RATE, 2008)
    assert rate.status == "live" and rate.value == 2.0
    assert table.value(MacroKey.BANK_RATE, 2009) == 0.5
    assert table.value(MacroKey.CPI_INFLATION, 2022) == pytest.approx(10.5)  # Dec 2022 y/y
    leeds = table.get(MacroKey.RENT_CHANGE, 2008, "yorkshire-and-the-humber")
    assert leeds.status == "live" and leeds.value == pytest.approx(1.9) and leeds.note is None


@respx.mock
async def test_adr_0018_boe_household_rates_live(settings, client, clock, no_sleep, fixture_text):
    respx.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(200, text=fixture_text("boe_iadb.csv")))
    respx.route().mock(side_effect=httpx.ConnectError("down"))
    table = await make_hub(settings, client, clock, no_sleep).macro_table()
    card = table.get(MacroKey.CARD_RATE, 2023)
    assert card.status == "live" and card.value == pytest.approx(24.02) and card.series_id == "IUMCCTL"
    assert table.get(MacroKey.SAVINGS_RATE, 2023).value == pytest.approx(2.81)
    assert table.get(MacroKey.ENERGY_TARIFF, 2023).status == "mock"
