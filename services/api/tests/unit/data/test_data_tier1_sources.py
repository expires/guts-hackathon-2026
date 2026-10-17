"""Tier 1 sources: parsers on recorded fixtures, adapter V3 behaviour (timeout, retry, breaker,
validation), key handling, prediction inputs and MacroTable mapping. No network: respx only."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import fakeredis.aioredis
import httpx
import pytest
import respx

from lifeline_contracts.macro import MacroKey
from lifeline_data.adapters.calendar_weather import (
    BankHolidaysAdapter,
    OpenMeteoAdapter,
    parse_open_meteo_daily,
)
from lifeline_data.adapters.energy import (
    CarbonIntensityAdapter,
    OctopusAdapter,
    find_flexible_product,
    parse_carbon_regional,
    parse_octopus_quotes,
)
from lifeline_data.adapters.keyed import (
    ADZUNA_HISTORY_URL,
    COMPANIES_HOUSE_SEARCH_URL,
    DVLA_URL,
    EPC_SEARCH_URL,
    STATXPLORE_TABLE_URL,
    AdzunaAdapter,
    CompaniesHouseAdapter,
    DvlaAdapter,
    EpcAdapter,
    StatXploreAdapter,
    parse_statxplore_table,
)
from lifeline_data.adapters.market import (
    CoinGeckoAdapter,
    FrankfurterAdapter,
    FredAdapter,
    YahooAdapter,
    parse_coingecko,
    parse_frankfurter,
    parse_fred_csv,
    parse_yahoo_chart,
)
from lifeline_data.adapters.ons import parse_pipr_xlsx
from lifeline_data.adapters.place import (
    EnvironmentAgencyAdapter,
    PoliceAdapter,
    parse_ea_floods,
    parse_police_crimes,
)
from lifeline_data.base import CircuitOpenError, FetchError, MissingKeyError, PayloadError
from lifeline_data.hub import DataHub
from lifeline_data.prediction_inputs import (
    division_for_region,
    fixture_bank_holidays,
    mock_daily_weather,
    parse_bank_holidays,
)
from lifeline_data.sources import SOURCES

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "data"
FAKE_KEY = "test-key-not-real-123"


def fx(name: str) -> str:
    return (FIXTURES / name).read_text()


def make_hub(settings, client, clock, no_sleep, env=None, **kw) -> DataHub:
    return DataHub(settings, client=client, clock=clock, sleep=no_sleep, env=env or {}, **kw)


# --- parsers on recorded fixtures --------------------------------------------------------------


def test_parse_recorded_market_fixtures():
    fxr = parse_frankfurter(fx("frankfurter_gbpusd.json"))
    assert fxr[0][0] < fxr[-1][0] and all(1.0 < v < 1.5 for _, v in fxr)
    btc = parse_coingecko(fx("coingecko_bitcoin.json"))
    assert len(btc) >= 10 and all(v > 1_000 for _, v in btc)
    ftas = parse_yahoo_chart(fx("yahoo_ftas_sample.json"))
    assert ftas[0][0] == date(2021, 12, 1) and len(ftas) == 26  # trailing null close skipped
    gilt = parse_fred_csv(fx("fred_gilt_sample.csv"), "IRLTLT01GBM156N")
    assert (date(2022, 10, 1), 3.94) in gilt and all(d.year < 2026 for d, _ in gilt)  # "." skipped


def test_parse_recorded_energy_and_place_fixtures():
    assert find_flexible_product(fx("octopus_products.json")).startswith("VAR-")
    day, gb, regional = parse_octopus_quotes(fx("octopus_flexible.json"))
    assert day == date(2026, 10, 17) and 1_000 < gb < 3_000
    assert {"london", "scotland", "yorkshire-and-the-humber"} <= regional.keys()
    _, carbon = parse_carbon_regional(fx("carbonintensity_regional.json"))
    assert None in carbon and "scotland" in carbon and "wales" in carbon
    assert parse_police_crimes(fx("police_burglary_leeds.json")) == 7
    floods = parse_ea_floods(fx("environmentagency_floods.json"))
    assert floods[None] == 0 and "scotland" not in floods  # recorded item is "no longer in force"


def test_parse_ea_counts_active_warnings_by_region():
    payload = json.loads(fx("environmentagency_floods.json"))
    item = dict(payload["items"][0], severityLevel=2, eaAreaName="Yorkshire")
    payload["items"].append(item)
    counts = parse_ea_floods(payload)
    assert counts[None] == 1 and counts["yorkshire-and-the-humber"] == 1 and counts["london"] == 0


def test_parse_pipr_sample_xlsx():
    rows = parse_pipr_xlsx((FIXTURES / "ons_pipr_sample.xlsx").read_bytes())
    regions = {r for _, r, _ in rows}
    assert regions == {None, "yorkshire-and-the-humber", "london", "scotland"}
    assert max(d for d, _, _ in rows) == date(2026, 8, 1)
    assert all(-30 < v < 50 for _, _, v in rows)  # "[x]" cell skipped, local authority row skipped


def test_parse_pipr_rejects_non_xlsx():
    with pytest.raises(PayloadError):
        parse_pipr_xlsx(b"<html>not a workbook</html>")


def test_parse_weather_and_holidays():
    days = parse_open_meteo_daily(fx("openmeteo_archive_leeds.json"))
    assert date(2026, 9, 1) in days and len(days) >= 40
    hol = parse_bank_holidays(fx("bankholidays.json"))
    assert date(2026, 8, 31) in hol["england-and-wales"] and date(2026, 8, 31) not in hol["scotland"]
    assert date(2026, 11, 30) in hol["scotland"]  # St Andrew's Day
    assert division_for_region("london") == "england-and-wales"
    assert division_for_region("northern-ireland") == "northern-ireland"
    assert date(2026, 12, 25) in fixture_bank_holidays()["northern-ireland"]


def test_parse_weather_rejects_out_of_range():
    bad = {"daily": {"time": ["2026-01-01"], "temperature_2m_max": [70.0], "precipitation_sum": [0.0]}}
    with pytest.raises(PayloadError):
        parse_open_meteo_daily(bad)


def test_bad_payloads_rejected():
    with pytest.raises(PayloadError):
        parse_coingecko({"prices": []})
    with pytest.raises(PayloadError):
        parse_frankfurter({"rates": {}})
    with pytest.raises(PayloadError):
        parse_fred_csv("DATE,OTHER\n2020-01-01,1\n", "IRLTLT01GBM156N")
    with pytest.raises(PayloadError):
        parse_bank_holidays({"x": {"division": "elsewhere", "events": []}})
    with pytest.raises(PayloadError):
        parse_statxplore_table({"cubes": {}})


# --- adapters through respx ---------------------------------------------------------------------


@respx.mock
async def test_market_adapters_fetch_validated(client, settings, no_sleep):
    respx.get(url__startswith="https://api.frankfurter.app/").mock(
        return_value=httpx.Response(200, text=fx("frankfurter_gbpusd.json"))
    )
    respx.get(url__startswith="https://api.coingecko.com/").mock(
        return_value=httpx.Response(200, text=fx("coingecko_bitcoin.json"))
    )
    respx.get(url__startswith="https://query1.finance.yahoo.com/").mock(
        return_value=httpx.Response(200, text=fx("yahoo_ftas_sample.json"))
    )
    respx.get(url__startswith="https://fred.stlouisfed.org/").mock(
        return_value=httpx.Response(200, text=fx("fred_gilt_sample.csv"))
    )
    gbp = await FrankfurterAdapter(client, settings, sleep=no_sleep).fetch_validated("GBPUSD")
    assert gbp and all(o.unit == "rate" and o.status == "live" for o in gbp)
    btc = await CoinGeckoAdapter(client, settings, sleep=no_sleep).fetch_validated("bitcoin")
    assert len(btc) == 1 and btc[0].unit == "percent"
    ftas = await YahooAdapter(client, settings, sleep=no_sleep).fetch_validated("^FTAS")
    dec22 = next(o for o in ftas if o.date == date(2022, 12, 1))
    assert dec22.value == pytest.approx((4075.1 / 4208.0 - 1) * 100, abs=0.01)
    gilt = await FredAdapter(client, settings, sleep=no_sleep).fetch_validated("IRLTLT01GBM156N")
    assert gilt[-1].value == pytest.approx(4.53)


@respx.mock
async def test_energy_place_weather_adapters(client, settings, no_sleep):
    respx.get("https://api.octopus.energy/v1/products/").mock(
        return_value=httpx.Response(200, text=fx("octopus_products.json"))
    )
    respx.get(url__startswith="https://api.octopus.energy/v1/products/VAR-").mock(
        return_value=httpx.Response(200, text=fx("octopus_flexible.json"))
    )
    respx.get(url__startswith="https://api.carbonintensity.org.uk/").mock(
        return_value=httpx.Response(200, text=fx("carbonintensity_regional.json"))
    )
    respx.get(url__startswith="https://data.police.uk/api/crimes-street-dates").mock(
        return_value=httpx.Response(200, text=fx("police_dates.json"))
    )
    crimes = respx.get(url__startswith="https://data.police.uk/api/crimes-street/").mock(
        return_value=httpx.Response(200, text=fx("police_burglary_leeds.json"))
    )
    respx.get(url__startswith="https://environment.data.gov.uk/").mock(
        return_value=httpx.Response(200, text=fx("environmentagency_floods.json"))
    )
    respx.get(url__startswith="https://www.gov.uk/").mock(
        return_value=httpx.Response(200, text=fx("bankholidays.json"))
    )
    respx.get(url__startswith="https://api.open-meteo.com/").mock(
        return_value=httpx.Response(200, text=fx("openmeteo_forecast_leeds.json"))
    )
    octo = await OctopusAdapter(client, settings, sleep=no_sleep).fetch_validated("dual-fuel-typical-bill")
    assert any(o.region is None for o in octo) and all(o.unit == "gbp" for o in octo)
    assert await CarbonIntensityAdapter(client, settings, sleep=no_sleep).fetch_validated("intensity")
    police = await PoliceAdapter(client, settings, sleep=no_sleep).fetch_validated("burglary-1mile")
    assert {o.region for o in police} == set(SOURCES_POLICE) and police[0].date == date(2026, 8, 1)
    assert crimes.calls.last.request.url.params["date"] == "2026-08"
    ea = await EnvironmentAgencyAdapter(client, settings, sleep=no_sleep).fetch_validated("flood-warnings")
    assert len(ea) == 10  # 9 England regions + England total
    hol = await BankHolidaysAdapter(client, settings, sleep=no_sleep).fetch_validated("scotland")
    assert all(o.region == "scotland" for o in hol)
    temp = await OpenMeteoAdapter(client, settings, sleep=no_sleep).fetch_validated(
        "temperature_2m_max", "yorkshire-and-the-humber"
    )
    assert temp and all(o.unit == "celsius" for o in temp)


SOURCES_POLICE = (
    "north-east", "north-west", "yorkshire-and-the-humber", "east-midlands", "west-midlands", "east-of-england",
    "london", "south-east", "south-west", "wales", "northern-ireland",
)


@respx.mock
async def test_open_meteo_daily_splits_archive_and_forecast(client, settings, no_sleep):
    archive = respx.get(url__startswith="https://archive-api.open-meteo.com/").mock(
        return_value=httpx.Response(200, text=fx("openmeteo_archive_leeds.json"))
    )
    forecast = respx.get(url__startswith="https://api.open-meteo.com/").mock(
        return_value=httpx.Response(200, text=fx("openmeteo_forecast_leeds.json"))
    )
    om = OpenMeteoAdapter(client, settings, sleep=no_sleep)
    days = await om.daily("yorkshire-and-the-humber", date(2026, 9, 1), date(2026, 10, 18), today=date(2026, 10, 17))
    assert date(2026, 9, 1) in days and date(2026, 10, 18) in days
    assert archive.calls.last.request.url.params["end_date"] == "2026-10-11"
    assert forecast.calls.last.request.url.params["start_date"] == "2026-10-12"
    assert archive.calls.last.request.url.params["latitude"] == "53.8008"


# --- V3: timeout, retries, breaker per new adapter -----------------------------------------------


@respx.mock
async def test_new_adapter_retries_then_breaker_opens(client, settings, no_sleep):
    route = respx.get(url__startswith="https://api.frankfurter.app/").mock(side_effect=httpx.ReadTimeout("slow"))
    adapter = FrankfurterAdapter(client, settings, sleep=no_sleep)
    for _ in range(3):
        with pytest.raises(FetchError, match="timeout"):
            await adapter.fetch_validated("GBPUSD")
    assert route.call_count == 9  # 3 tries per call
    with pytest.raises(CircuitOpenError):
        await adapter.fetch_validated("GBPUSD")
    assert route.call_count == 9


@respx.mock
async def test_yahoo_429_is_retried_then_hub_serves_mock(client, settings, clock, no_sleep):
    route = respx.get(url__startswith="https://query1.finance.yahoo.com/").mock(
        return_value=httpx.Response(429, text="Too Many Requests")
    )
    hub = make_hub(settings, client, clock, no_sleep)
    obs = await hub.series("yahoo", "^FTAS")
    assert route.call_count == 3 and obs and all(o.status == "mock" for o in obs)
    st = next(s for s in await hub.statuses() if s.id == "yahoo")
    assert st.status == "mock" and "429" in (st.last_error or "")


@respx.mock
async def test_timeout_falls_back_to_cached_for_tier1_source(client, settings, clock, no_sleep):
    route = respx.get(url__startswith="https://fred.stlouisfed.org/")
    route.mock(return_value=httpx.Response(200, text=fx("fred_gilt_sample.csv")))
    hub = make_hub(settings, client, clock, no_sleep, redis=fakeredis.aioredis.FakeRedis())
    live = await hub.series("fred", "IRLTLT01GBM156N")
    assert live and all(o.status == "live" for o in live)
    clock.advance(SOURCES["fred"].ttl_seconds + 1)
    route.mock(side_effect=httpx.ConnectTimeout("down"))
    cached = await hub.series("fred", "IRLTLT01GBM156N")
    assert [o.value for o in cached] == [o.value for o in live] and all(o.status == "cached" for o in cached)


@respx.mock
async def test_bad_payload_counts_against_breaker(client, settings, no_sleep):
    respx.get(url__startswith="https://api.carbonintensity.org.uk/").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    adapter = CarbonIntensityAdapter(client, settings, sleep=no_sleep)
    for _ in range(3):
        with pytest.raises(PayloadError):
            await adapter.fetch_validated("intensity")
    assert adapter.breaker.state == "open"


# --- key-needing sources ---------------------------------------------------------------------------


@pytest.mark.parametrize("sid", ["companieshouse", "epc", "statxplore", "adzuna", "dvla", "dvsamot"])
async def test_missing_key_gives_labelled_mock(settings, client, clock, no_sleep, sid):
    hub = make_hub(settings, client, clock, no_sleep)
    st = next(s for s in await hub.statuses() if s.id == sid)
    assert st.status == "mock" and st.last_error == f"{SOURCES[sid].key_env[0]} not set"
    assert st.needs_key


async def test_adapter_key_missing_raises_without_value(client, settings, no_sleep):
    adapter = CompaniesHouseAdapter(client, settings, sleep=no_sleep)
    adapter.env = {}
    with pytest.raises(MissingKeyError, match="COMPANIES_HOUSE_KEY not set"):
        await adapter.fetch("companies-liquidation")


@respx.mock
async def test_companies_house_basic_auth(client, settings, no_sleep):
    route = respx.get(url__startswith=COMPANIES_HOUSE_SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"hits": 12345, "items": []})
    )
    adapter = CompaniesHouseAdapter(client, settings, sleep=no_sleep)
    adapter.env = {"COMPANIES_HOUSE_KEY": FAKE_KEY}
    obs = await adapter.fetch_validated("companies-liquidation")
    assert obs[0].value == 12345
    auth = route.calls.last.request.headers["Authorization"]
    assert auth.startswith("Basic ")
    assert route.calls.last.request.url.params["company_status"] == "liquidation"


@respx.mock
async def test_epc_bearer_and_share(client, settings, no_sleep):
    def answer(request: httpx.Request) -> httpx.Response:
        rated = "efficiency_rating[]" in request.url.params
        total = 400 if rated else 1000
        return httpx.Response(200, json={"data": [], "pagination": {"totalRecords": total}})

    route = respx.get(url__startswith=EPC_SEARCH_URL).mock(side_effect=answer)
    adapter = EpcAdapter(client, settings, sleep=no_sleep)
    adapter.env = {"EPC_KEY": FAKE_KEY}
    obs = await adapter.fetch_validated("epc-abc-share", "yorkshire-and-the-humber")
    assert len(obs) == 1 and obs[0].value == pytest.approx(40.0)
    assert route.calls.last.request.headers["Authorization"] == f"Bearer {FAKE_KEY}"
    assert route.calls.last.request.url.params["council[]"] == "Leeds"


@respx.mock
async def test_statxplore_apikey_header_and_parse(client, settings, no_sleep):
    table = {
        "cubes": {"str:count:UC_Monthly:V_F_UC_CASELOAD_FULL": {"values": [7_900_000, 8_100_000, None]}},
        "fields": [{"items": [{"labels": ["August 2026"]}, {"labels": ["September 2026"]}, {"labels": ["Total"]}]}],
    }
    route = respx.post(STATXPLORE_TABLE_URL).mock(return_value=httpx.Response(200, json=table))
    adapter = StatXploreAdapter(client, settings, sleep=no_sleep)
    adapter.env = {"DWP_STATXPLORE_KEY": FAKE_KEY}
    obs = await adapter.fetch_validated("uc-caseload")
    assert [o.date for o in obs] == [date(2026, 8, 1), date(2026, 9, 1)]
    assert route.calls.last.request.headers["APIKey"] == FAKE_KEY
    assert json.loads(route.calls.last.request.content)["database"] == "str:database:UC_Monthly"


@respx.mock
async def test_key_never_in_error_message(client, settings, no_sleep):
    respx.get(url__startswith=ADZUNA_HISTORY_URL).mock(return_value=httpx.Response(401, text=FAKE_KEY))
    adapter = AdzunaAdapter(client, settings, sleep=no_sleep)
    adapter.env = {"ADZUNA_APP_ID": "id-123", "ADZUNA_APP_KEY": FAKE_KEY}
    with pytest.raises(FetchError) as err:
        await adapter.fetch_validated("advertised-salary")
    assert FAKE_KEY not in str(err.value) and "HTTP 401" in str(err.value)


@respx.mock
async def test_dvla_lookup(client, settings, no_sleep):
    route = respx.post(DVLA_URL).mock(
        return_value=httpx.Response(200, json={"registrationNumber": "AB12CDE", "yearOfManufacture": 2012})
    )
    adapter = DvlaAdapter(client, settings, sleep=no_sleep)
    adapter.env = {"DVLA_KEY": FAKE_KEY}
    data = await adapter.vehicle("ab12 cde")
    assert data is not None and data["yearOfManufacture"] == 2012
    assert route.calls.last.request.headers["x-api-key"] == FAKE_KEY


# --- hub: prediction inputs ----------------------------------------------------------------------


async def test_bank_holidays_offline_uses_fixture(settings):
    hub = DataHub(settings, env={})
    days = await hub.bank_holidays("scotland")
    assert date(2026, 11, 30) in days and date(2026, 8, 31) not in days
    st = next(s for s in await hub.statuses() if s.id == "bankholidays")
    assert st.status == "mock" and st.last_error == "offline mode"


@respx.mock
async def test_bank_holidays_live_then_cached(settings, client, clock, no_sleep):
    route = respx.get("https://www.gov.uk/bank-holidays.json").mock(
        return_value=httpx.Response(200, text=fx("bankholidays.json"))
    )
    hub = make_hub(settings, client, clock, no_sleep, redis=fakeredis.aioredis.FakeRedis())
    assert date(2026, 8, 31) in await hub.bank_holidays("london")
    assert date(2026, 8, 31) in await hub.bank_holidays(None)
    assert route.call_count == 1  # second call served from fresh cache
    clock.advance(SOURCES["bankholidays"].ttl_seconds + 1)
    route.mock(side_effect=httpx.ConnectTimeout("down"))
    assert date(2026, 7, 13) in await hub.bank_holidays("northern-ireland")
    st = next(s for s in await hub.statuses() if s.id == "bankholidays")
    assert st.status == "cached"


async def test_daily_weather_offline_is_labelled_mock(settings):
    hub = DataHub(settings, env={})
    rows = await hub.daily_weather("london", date(2026, 10, 1), date(2026, 10, 18))
    assert len(rows) == 18 and all(r["status"] == "mock" for r in rows)
    assert rows == mock_daily_weather("london", date(2026, 10, 1), date(2026, 10, 18))


@respx.mock
async def test_daily_weather_live_with_gaps_filled(settings, client, clock, no_sleep):
    respx.get(url__startswith="https://archive-api.open-meteo.com/").mock(
        return_value=httpx.Response(200, text=fx("openmeteo_archive_leeds.json"))
    )
    respx.get(url__startswith="https://api.open-meteo.com/").mock(
        return_value=httpx.Response(200, text=fx("openmeteo_forecast_leeds.json"))
    )
    hub = make_hub(settings, client, clock, no_sleep)
    rows = await hub.daily_weather(
        "yorkshire-and-the-humber", date(2026, 8, 30), date(2026, 10, 19), today=date(2026, 10, 17)
    )
    by_day = {r["date"]: r for r in rows}
    assert by_day[date(2026, 9, 1)]["status"] == "live"
    assert by_day[date(2026, 10, 19)]["status"] == "live"
    assert by_day[date(2026, 8, 30)]["status"] == "mock"  # not in the recorded archive slice
    assert by_day[date(2026, 10, 17)]["temp_max_c"] == pytest.approx(12.5)


@respx.mock
async def test_daily_weather_failure_falls_back_to_mock(settings, client, clock, no_sleep):
    respx.route().mock(side_effect=httpx.ConnectError("down"))
    hub = make_hub(settings, client, clock, no_sleep)
    rows = await hub.daily_weather("wales", date(2026, 10, 10), date(2026, 10, 12), today=date(2026, 10, 17))
    assert [r["status"] for r in rows] == ["mock"] * 3
    st = next(s for s in await hub.statuses() if s.id == "openmeteo")
    assert st.status == "mock" and st.last_error


# --- MacroTable mapping --------------------------------------------------------------------------


@respx.mock
async def test_macro_table_uses_tier1_sources(settings, client, clock, no_sleep):
    respx.get(url__startswith="https://api.frankfurter.app/").mock(
        return_value=httpx.Response(200, text=fx("frankfurter_gbpusd.json"))
    )
    respx.get("https://api.octopus.energy/v1/products/").mock(
        return_value=httpx.Response(200, text=fx("octopus_products.json"))
    )
    respx.get(url__startswith="https://api.octopus.energy/v1/products/VAR-").mock(
        return_value=httpx.Response(200, text=fx("octopus_flexible.json"))
    )
    respx.get(url__startswith="https://fred.stlouisfed.org/").mock(
        return_value=httpx.Response(200, text=fx("fred_gilt_sample.csv"))
    )
    respx.route().mock(side_effect=httpx.ConnectError("down"))
    table = await make_hub(settings, client, clock, no_sleep).macro_table()
    assert table.get(MacroKey.GBP_USD, 2024).status == "live"
    tariff = table.get(MacroKey.ENERGY_TARIFF, 2026)
    assert tariff.status == "live" and 1_000 < tariff.value < 3_000
    assert table.get(MacroKey.ENERGY_TARIFF, 2026, "london").status == "live"
    assert table.get(MacroKey.GILT_10Y, 2022).value == pytest.approx(3.43)
    assert table.get(MacroKey.FUEL_PRICE_CHANGE, 2022).series_id == "D7IO"
    assert table.get(MacroKey.BURGLARY_RATE, 2022).status == "mock"  # police gives counts, not rates


async def test_registry_has_bankholidays():
    info = SOURCES["bankholidays"]
    assert not info.needs_key and info.licence.startswith("Open Government")


def test_pipr_beats_iphrp_alias_and_alias_keeps_its_id():
    from datetime import UTC, datetime

    from lifeline_contracts.observation import Observation
    from lifeline_data.macro import build_macro_table

    def o(series: str, year: int, value: float, status: str = "live") -> Observation:
        return Observation(
            series_id=series, source="ons", date=date(year, 12, 1), value=value, unit="percent",
            region="london", fetched_at=datetime.now(UTC), status=status,
        )

    table = build_macro_table([o("IPHRP", 2010, 1.3), o("IPHRP", 2019, 1.0), o("PIPR", 2019, 2.2)])
    old = table.get(MacroKey.RENT_CHANGE, 2010, "london")
    assert old.value == 1.3 and old.series_id == "IPHRP"
    new = table.get(MacroKey.RENT_CHANGE, 2019, "london")
    assert new.value == 2.2 and new.series_id == "PIPR"
    mixed = build_macro_table([o("IPHRP", 2019, 1.0), o("PIPR", 2019, 2.4, "mock")])
    assert mixed.get(MacroKey.RENT_CHANGE, 2019, "london").series_id == "IPHRP"  # live alias beats mock primary


@respx.mock
async def test_bank_holiday_observations_stop_one_year_ahead(client, settings, no_sleep):
    respx.get(url__startswith="https://www.gov.uk/").mock(
        return_value=httpx.Response(200, text=(Path(__file__).resolve().parents[3] / "lifeline_data" / "fixtures"
                                               / "bank-holidays.json").read_text())
    )
    obs = await BankHolidaysAdapter(client, settings, sleep=no_sleep).fetch_validated("england-and-wales")
    assert obs and max(o.date for o in obs) <= date.today().replace(year=date.today().year + 1)


def test_boe_parser_skips_suppressed_and_placeholder_zero():
    from lifeline_data.adapters.boe import parse_boe_csv

    text = "DATE,IUMTLMV,IUMBV24,IUMBV48\n31 Jan 1997,7.2,0,0\n31 Dec 2022,6.42,..,4.14\n"
    rows = parse_boe_csv(text)
    assert ("IUMTLMV", date(1997, 1, 31), 7.2) in rows
    assert not any(code in ("IUMBV24", "IUMBV48") and day.year == 1997 for code, day, _ in rows)
    assert ("IUMBV48", date(2022, 12, 31), 4.14) in rows and not any(c == "IUMBV24" for c, *_ in rows)


@respx.mock
async def test_macro_svr_and_tracker_live_from_boe(settings, client, clock, no_sleep):
    from lifeline_data.adapters.boe import BOE_SERIES, BOE_URL

    route = respx.get(url__startswith=BOE_URL).mock(return_value=httpx.Response(200, text=fx("boe_iadb.csv")))
    respx.route().mock(side_effect=httpx.ConnectError("down"))
    table = await make_hub(settings, client, clock, no_sleep).macro_table()
    svr = table.get(MacroKey.MORTGAGE_SVR, 2022)
    assert svr.status == "live" and svr.value == pytest.approx(6.42) and svr.series_id == "IUMTLMV"
    tracker = table.get(MacroKey.MORTGAGE_TRACKER, 2023)
    assert tracker.status == "live" and tracker.value == pytest.approx(5.69) and tracker.series_id == "IUMBV48"
    assert table.get(MacroKey.MORTGAGE_SVR, 1991).status == "mock"  # before IADB coverage
    assert route.calls.last.request.url.params["SeriesCodes"] == ",".join(BOE_SERIES)
