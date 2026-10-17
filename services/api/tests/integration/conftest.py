"""In-process app with APP_ENV=test (in-memory store, fakeredis, offline data hub)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx
import pytest


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    os.environ.setdefault("APP_ENV", "test")
    from lifeline_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def sign_in(client: httpx.AsyncClient, device_id: str = "integration-device-1") -> dict[str, str]:
    r = await client.post("/v1/auth/demo", json={"device_id": device_id})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
