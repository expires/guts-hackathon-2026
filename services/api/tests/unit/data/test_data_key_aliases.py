"""Env name aliases for keys and base-URL overrides. Fake values are built at run time (secrets scan)."""

from __future__ import annotations

import logging

import httpx
import pytest
import respx

from lifeline_data.adapters.keyed import CompaniesHouseAdapter, EpcAdapter, StatXploreAdapter
from lifeline_data.hub import DataHub
from lifeline_data.sources import (
    COMPANIES_HOUSE_API_URL,
    KEY_ALIASES,
    SOURCES,
    STATXPLORE_API_URL,
    base_url,
    missing_key_message,
    missing_keys,
    resolve_key,
)


def fake(tag: str) -> str:
    return "-".join(("fake", tag, "z" * 12))


def test_alias_map_matches_request():
    assert KEY_ALIASES == {
        "COMPANIES_HOUSE_KEY": "COMPANIES_HOUSE_API_KEY",
        "EPC_KEY": "EPC_API_TOKEN",
        "DWP_STATXPLORE_KEY": "STATXPLORE_API_KEY",
        "DVLA_KEY": "DVLA_VES_API_KEY",
        "OB_CLIENT_ID": "TRUELAYER_CLIENT_ID",
        "OB_CLIENT_SECRET": "TRUELAYER_CLIENT_SECRET",
        "OB_REDIRECT_URI": "TRUELAYER_REDIRECT_URI",
    }
    assert "ADZUNA_APP_ID" not in KEY_ALIASES and "ADZUNA_APP_KEY" not in KEY_ALIASES


@pytest.mark.parametrize(("canonical", "alias"), list(KEY_ALIASES.items()))
def test_resolve_key_alias_and_canonical_wins(canonical, alias):
    a, c = fake("alias"), fake("canon")
    assert resolve_key(canonical, {alias: a}) == a
    assert resolve_key(canonical, {canonical: c, alias: a}) == c
    assert resolve_key(canonical, {canonical: "", alias: a}) == a
    assert resolve_key(canonical, {canonical: "  ", alias: ""}) == ""


def test_missing_keys_uses_aliases():
    ob = SOURCES["openbanking"]
    env = {"TRUELAYER_CLIENT_ID": fake("id"), "TRUELAYER_CLIENT_SECRET": fake("s")}
    assert missing_keys(ob, env) == ["OB_REDIRECT_URI"]
    assert missing_keys(SOURCES["epc"], {"EPC_API_TOKEN": fake("epc")}) == []
    assert missing_keys(SOURCES["adzuna"], {"ADZUNA_APP_ID": fake("a")}) == ["ADZUNA_APP_KEY"]


def test_missing_key_message_names_canonical_and_alias():
    assert missing_key_message("COMPANIES_HOUSE_KEY") == "COMPANIES_HOUSE_KEY not set (or COMPANIES_HOUSE_API_KEY)"
    assert missing_key_message("ADZUNA_APP_KEY") == "ADZUNA_APP_KEY not set"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", COMPANIES_HOUSE_API_URL),
        ("https://ch.example.test/api/", "https://ch.example.test/api"),
        ("http://ch.example.test", COMPANIES_HOUSE_API_URL),
        ("https://", COMPANIES_HOUSE_API_URL),
        ("https://ch.example.test/?x=1", COMPANIES_HOUSE_API_URL),
        ("not a url", COMPANIES_HOUSE_API_URL),
        ("ftp://ch.example.test", COMPANIES_HOUSE_API_URL),
    ],
)
def test_base_url_override_only_when_valid_https(raw, expected):
    assert base_url("COMPANIES_HOUSE_API_URL", {"COMPANIES_HOUSE_API_URL": raw}) == expected


def test_truelayer_url_defaults_and_override():
    assert base_url("TRUELAYER_AUTH_URL", {}).startswith("https://")
    assert base_url("TRUELAYER_API_URL", {"TRUELAYER_API_URL": "https://tl.example.test"}) == "https://tl.example.test"


async def test_hub_status_with_alias_is_not_missing_key(settings, client, clock, no_sleep):
    hub = DataHub(settings, client=client, clock=clock, sleep=no_sleep, env={"EPC_API_TOKEN": fake("epc")})
    statuses = {s.id: s for s in await hub.statuses()}
    assert statuses["epc"].last_error != missing_key_message("EPC_KEY")
    assert statuses["companieshouse"].last_error == "COMPANIES_HOUSE_KEY not set (or COMPANIES_HOUSE_API_KEY)"


@respx.mock
async def test_adapters_use_alias_keys_and_url_overrides(client, settings, no_sleep, caplog):
    caplog.set_level(logging.DEBUG)
    key = fake("ch")
    ch_route = respx.get("https://ch.example.test/advanced-search/companies").mock(
        return_value=httpx.Response(200, json={"hits": 7})
    )
    ch = CompaniesHouseAdapter(client, settings, sleep=no_sleep)
    ch.env = {"COMPANIES_HOUSE_API_KEY": key, "COMPANIES_HOUSE_API_URL": "https://ch.example.test/"}
    assert (await ch.fetch_validated("companies-liquidation"))[0].value == 7
    assert ch_route.calls.last.request.headers["Authorization"] == httpx.BasicAuth(key, "")._auth_header

    epc_key = fake("epc")
    epc_route = respx.get(url__startswith="https://api.get-energy-performance-data").mock(
        return_value=httpx.Response(200, json={"data": [], "pagination": {"totalRecords": 10}})
    )
    epc = EpcAdapter(client, settings, sleep=no_sleep)
    epc.env = {"EPC_API_TOKEN": epc_key}
    await epc.fetch_validated("epc-abc-share", "london")
    assert epc_route.calls.last.request.headers["Authorization"] == f"Bearer {epc_key}"

    sx_key = fake("sx")
    table = {"cubes": {"m": {"values": [1.0]}}, "fields": [{"items": [{"labels": ["August 2026"]}]}]}
    sx_default = respx.post(STATXPLORE_API_URL + "/table").mock(return_value=httpx.Response(200, json=table))
    sx = StatXploreAdapter(client, settings, sleep=no_sleep)
    sx.env = {"STATXPLORE_API_KEY": sx_key, "STATXPLORE_API_URL": "http://insecure.example.test"}
    await sx.fetch_validated("uc-caseload")
    assert sx_default.called and sx_default.calls.last.request.headers["APIKey"] == sx_key

    for value in (key, epc_key, sx_key):
        assert value not in caplog.text
