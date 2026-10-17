"""V6 V2-F1: at most 2 statement parses at once; others wait up to 5 s, then 503 with Retry-After.
A burst of hostile uploads must not slow the rest of the API."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import pytest

from tests.integration.conftest import sign_in

HOSTILE = b"%PDF-1.4\n" + b"(x) Tj " * 50_000  # large text-like PDF body


def _slow_parse(seconds: float) -> Any:
    from lifeline_data.statements import parse_statement

    def parse(content: bytes, filename: str | None = None) -> Any:
        time.sleep(seconds)  # stands in for a CPU-heavy hostile file; runs in a worker thread
        return parse_statement(content, filename)

    return parse


async def _upload(client: httpx.AsyncClient, auth: dict[str, str]) -> httpx.Response:
    return await client.post("/v1/finance/statements", files={"file": ("x.pdf", HOSTILE, "application/pdf")},
                             headers=auth)


async def test_parallel_hostile_uploads_do_not_delay_health(client: httpx.AsyncClient,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    from lifeline_api.routes import account

    monkeypatch.setattr(account.statements, "parse_statement", _slow_parse(1.0))
    auths = [await sign_in(client, f"hostile-device-{i:02d}") for i in range(4)]
    uploads = [asyncio.create_task(_upload(client, a)) for a in auths]
    await asyncio.sleep(0.1)
    t0 = time.monotonic()
    r = await client.get("/v1/health")
    assert r.status_code == 200 and time.monotonic() - t0 < 1.0
    results = await asyncio.gather(*uploads)
    assert all(x.status_code == 201 for x in results), [x.status_code for x in results]


async def test_parse_queue_answers_503_after_the_wait(client: httpx.AsyncClient,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    from lifeline_api import sim_bridge
    from lifeline_api.routes import account

    monkeypatch.setattr(account.statements, "parse_statement", _slow_parse(1.0))
    monkeypatch.setattr(sim_bridge, "PARSE_WAIT_SECONDS", 0.2)
    auths = [await sign_in(client, f"queue-device-{i:02d}") for i in range(3)]
    results = await asyncio.gather(*(_upload(client, a) for a in auths))
    codes = sorted(x.status_code for x in results)
    assert codes == [201, 201, 503]
    busy = next(x for x in results if x.status_code == 503)
    assert busy.json()["error"]["code"] == "busy" and busy.headers["retry-after"] == "5"
