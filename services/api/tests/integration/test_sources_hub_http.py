"""GET /v1/sources/hub (ADR 0073): order, no homeowner sources, live count, values, language. Offline test app."""

from __future__ import annotations

import httpx

from lifeline_api.routes.sources_hub import HOMEOWNER_SOURCES
from lifeline_contracts.sources_hub import SourcesHub
from lifeline_explain import hub_text
from tests.integration.conftest import sign_in

ORDER = ["statement", "official_facts", "boe", "ons", "nomis", "octopus", "frankfurter", "boe-mpc"]


async def _hub(client: httpx.AsyncClient, language: str = "en", headers: dict[str, str] | None = None) -> SourcesHub:
    r = await client.get("/v1/sources/hub", params={"language": language}, headers=headers or {})
    assert r.status_code == 200, r.text
    return SourcesHub.model_validate(r.json())


async def test_order_kinds_and_no_homeowner_sources(client: httpx.AsyncClient) -> None:
    hub = await _hub(client)
    assert [s.id for s in hub.sources] == ORDER
    assert [s.kind for s in hub.sources[:2]] == ["statement", "official_facts"]
    assert all(s.kind == "live" for s in hub.sources[2:])
    assert not {s.id for s in hub.sources} & HOMEOWNER_SOURCES
    names = " ".join(s.name for s in hub.sources).lower()
    for word in ("land registry", "epc", "police", "flood", "companies house", "carbon", "coingecko", "yahoo"):
        assert word not in names


async def test_live_count_matches_summary(client: httpx.AsyncClient) -> None:
    hub = await _hub(client)
    assert hub.live_count == len([s for s in hub.sources if s.kind != "statement"]) == 7
    assert hub.summary == hub_text.SUMMARY["en"].format(n=7)
    assert hub.summary.startswith("Penny uses your statement plus 7 live UK sources.")


async def test_values_present_in_mock_data(client: httpx.AsyncClient) -> None:
    hub = await _hub(client)
    by_id = {s.id: s for s in hub.sources}
    labels = {v.label for s in hub.sources for v in s.latest}
    for label in ("Bank Rate", "Easy-access savings rate", "CPI annual rate", "Median full-time pay",
                  "Typical energy bill", "Pounds to US dollars", "Student loan threshold (Plan 2)"):
        assert label in labels, label
    assert by_id["official_facts"].url and "gov.uk" in by_id["official_facts"].url
    assert all(s.url for s in hub.sources if s.kind != "statement")
    assert all(s.used_in and s.gives for s in hub.sources)
    assert "One thing that helps" in by_id["boe"].used_in and "The maths" in by_id["boe"].used_in
    assert all(v.as_of for s in hub.sources for v in s.latest)


async def test_statement_card_without_and_with_sign_in(client: httpx.AsyncClient) -> None:
    anon = await _hub(client)
    assert anon.sources[0].status == "unavailable" and anon.sources[0].latest == []
    signed = await _hub(client, headers=await sign_in(client, "hub-device"))
    assert signed.sources[0].latest == []  # never the user's own numbers
    assert "£" not in signed.sources[0].gives


async def test_language(client: httpx.AsyncClient) -> None:
    hub = await _hub(client, "fr")
    assert hub.summary == hub_text.SUMMARY["fr"].format(n=7)
    assert hub.sources[0].name == "Votre relevé"
    assert hub.sources[2].gives == hub_text.GIVES["boe"]["fr"]
    assert "Une chose qui aide" in hub.sources[2].used_in
    assert (await client.get("/v1/sources/hub", params={"language": "xx"})).status_code in {400, 422}


async def test_no_text_says_mock(client: httpx.AsyncClient) -> None:
    """Users and judges see "sample", never "mock". The `status` enum is a machine field, not shown as text."""
    for headers in ({}, await sign_in(client, "hub-mock-words")):
        hub = await _hub(client, headers=headers)
        text = hub.model_dump(mode="json", exclude={"sources": {"__all__": {"status"}}})
        assert "mock" not in str(text).lower()
