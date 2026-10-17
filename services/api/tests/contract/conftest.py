"""Contract fixtures. In-process by default; set LIFELINE_BASE_URL to test a running stack."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

import httpx
import pytest

BASE = os.environ.get("LIFELINE_BASE_URL")


class RetryOn429(httpx.AsyncHTTPTransport):
    """Stack mode only: behave like a polite client and honour Retry-After on 429 (rate limit is per IP)."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        for _ in range(6):
            response = await super().handle_async_request(request)
            if response.status_code != 429:
                return response
            await response.aclose()
            await asyncio.sleep(min(float(response.headers.get("retry-after", "5")), 30))
        return await super().handle_async_request(request)


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    if BASE:
        async with httpx.AsyncClient(base_url=BASE, timeout=60, transport=RetryOn429()) as c:
            yield c
        return
    os.environ.setdefault("APP_ENV", "test")
    from lifeline_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth(client: httpx.AsyncClient) -> dict[str, str]:
    from tests.contract.spec import validate

    r = await client.post("/v1/auth/demo", json={"device_id": "contract-test-device"})
    validate("POST", "/v1/auth/demo", r.status_code, r.json())
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
