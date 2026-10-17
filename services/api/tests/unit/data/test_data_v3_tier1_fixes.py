"""V3 Tier 1 fixes: G1 (no keys in logs), N1 (no reuse of invalid bodies), N2 (DVSA shape)."""

from __future__ import annotations

import logging

import httpx
import pytest
import respx

from lifeline_data.adapters.keyed import ADZUNA_HISTORY_URL, DVSA_MOT_URL, DvsaMotAdapter
from lifeline_data.adapters.market import FrankfurterAdapter
from lifeline_data.base import PayloadError
from lifeline_data.hub import DataHub
from lifeline_data.logsafe import quiet_http_loggers, redact_urls
from lifeline_data.worker import main as worker_main

# Fake values built at run time so no key-shaped literal sits in the source (secrets scan).
SECRET = "-".join(("sk", "adzuna", "x" * 16))
APP_ID = "-".join(("app", "id", "y" * 8))
ENV = {"ADZUNA_APP_ID": APP_ID, "ADZUNA_APP_KEY": SECRET}


def _hub(settings, client, clock, no_sleep) -> DataHub:
    return DataHub(settings, client=client, clock=clock, sleep=no_sleep, env=ENV)


def test_redact_urls():
    text = f"GET https://api.adzuna.com/v1/api/jobs/gb/history?app_id=x&app_key={SECRET} failed"
    out = redact_urls(text)
    assert SECRET not in out and out[4:] == "https://api.adzuna.com/v1/api/jobs/gb/history?<redacted> failed"


def test_http_loggers_quiet_and_filtered(caplog):
    quiet_http_loggers()
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
    caplog.set_level(logging.DEBUG)
    logging.getLogger("httpx").info("HTTP Request: GET %s", f"https://x.test/a?app_key={SECRET}")
    logging.getLogger("httpx").warning("HTTP Request: GET %s", f"https://x.test/a?app_key={SECRET}")
    assert SECRET not in caplog.text and "?<redacted>" in caplog.text


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"month": {"2026-08": 39000.0, "2026-09": 39500.0}}),
        httpx.Response(500, text="boom"),
        httpx.Response(401, text=f"bad key {SECRET}"),
        httpx.Response(200, text="not json"),
    ],
)
async def test_adzuna_key_never_in_logs(settings, client, clock, no_sleep, caplog, response):
    caplog.set_level(logging.DEBUG)
    with respx.mock:
        route = respx.get(url__startswith=ADZUNA_HISTORY_URL).mock(return_value=response)
        hub = _hub(settings, client, clock, no_sleep)
        await hub.series("adzuna", "advertised-salary")
        statuses = await hub.statuses()
    assert route.called and SECRET in str(route.calls.last.request.url)  # the key really was in the query
    assert SECRET not in caplog.text and APP_ID not in caplog.text
    assert all(SECRET not in (s.last_error or "") for s in statuses)


async def test_unexpected_error_with_url_is_redacted(settings, client, clock, no_sleep, caplog):
    """An unmocked request makes respx raise an error whose text holds the full URL with the key."""
    caplog.set_level(logging.DEBUG)
    with respx.mock(assert_all_mocked=True):
        hub = _hub(settings, client, clock, no_sleep)
        await hub.series("adzuna", "advertised-salary")
        st = await hub._get_state("adzuna")  # cut from /v1/sources (ADR 0046); internal state still recorded
    assert st.status == "mock" and st.last_error and SECRET not in st.last_error
    assert SECRET not in caplog.text


def test_worker_main_quiets_http_loggers(monkeypatch):
    async def fake_run(once: bool = False, settings=None) -> None:
        return None

    monkeypatch.setattr("lifeline_data.worker.run", fake_run)
    logging.getLogger("httpx").setLevel(logging.DEBUG)
    worker_main(["--once"])
    assert logging.getLogger("httpx").level == logging.WARNING


@respx.mock
async def test_invalid_body_is_not_reused(client, settings, no_sleep):
    good = {"rates": {"2026-10-16": {"USD": 1.33}}}
    route = respx.get(url__startswith="https://api.frankfurter.dev/v1/").mock(
        side_effect=[httpx.Response(200, json={"rates": {"2026-10-16": {"USD": 50.0}}}), httpx.Response(200, json=good)]
    )
    adapter = FrankfurterAdapter(client, settings, sleep=no_sleep)
    with pytest.raises(PayloadError):
        await adapter.fetch_validated("GBPUSD")  # absurd rate fails validation
    assert adapter._memo == {}
    obs = await adapter.fetch_validated("GBPUSD")  # fresh request, not the memoised bad body
    assert route.call_count == 2 and obs[0].value == 1.33


@respx.mock
@pytest.mark.parametrize(
    "payload",
    [
        {"foo": 1},
        {"registration": "AB12CDE"},
        {"registration": "ZZ99ZZZ", "motTests": []},
        {"registration": "AB12CDE", "motTests": "none"},
        {"registration": "AB12CDE", "motTests": [{"odometerValue": "1000"}]},
        [],
    ],
)
async def test_dvsa_wrong_shape_rejected(client, settings, no_sleep, payload):
    respx.get(DVSA_MOT_URL.format(reg="AB12CDE")).mock(return_value=httpx.Response(200, json=payload))
    adapter = DvsaMotAdapter(client, settings, sleep=no_sleep)
    adapter.env = {"DVSA_MOT_KEY": "k"}
    with pytest.raises(PayloadError):
        await adapter.fetch_validated("AB12CDE")


@respx.mock
async def test_dvsa_valid_shapes_accepted(client, settings, no_sleep):
    adapter = DvsaMotAdapter(client, settings, sleep=no_sleep)
    adapter.env = {"DVSA_MOT_KEY": "k"}
    respx.get(DVSA_MOT_URL.format(reg="AB12CDE")).mock(
        return_value=httpx.Response(
            200,
            json={"registration": "AB12CDE", "motTests": [{"testResult": "PASSED"}, {"testResult": "FAILED"}]},
        )
    )
    obs = await adapter.fetch_validated("AB12CDE")
    assert obs[0].value == 1.0
    respx.get(DVSA_MOT_URL.format(reg="NEW1CAR")).mock(
        return_value=httpx.Response(200, json={"registration": "NEW1CAR", "motTestDueDate": "2028-01-01"})
    )
    assert (await adapter.fetch_validated("NEW1CAR"))[0].value == 0.0
