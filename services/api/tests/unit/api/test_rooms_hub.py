"""RoomHub storage and fan-out: process memory, and Redis shared by two replicas."""

from __future__ import annotations

import asyncio
import base64

import fakeredis
import pytest

from lifeline_api.rooms import RoomDoc, RoomHub, qr_png_base64


def _doc(code: str = "4321") -> RoomDoc:
    return RoomDoc(code=code, mode="duel", seed=7, preset_id="nurse-leeds", start_year=2006, max_players=2)


@pytest.mark.parametrize("shared", [False, True])
async def test_two_replicas_share_rooms_and_events(shared: bool) -> None:
    if shared:
        server = fakeredis.FakeServer()
        a = RoomHub(fakeredis.FakeAsyncRedis(server=server))
        b = RoomHub(fakeredis.FakeAsyncRedis(server=server))
    else:
        a = b = RoomHub(None)
    doc = _doc()
    doc.add_player("sub-1", "Ana", host=True)
    assert await a.create(doc) and not await b.create(_doc()), "codes are unique across replicas"
    got = await b.get("4321")
    assert got is not None and got.players[0]["name"] == "Ana"
    assert got.public().players[0].model_dump().get("sub") is None, "the account id never leaves the server"
    async with b.subscribe("4321") as queue:
        await asyncio.sleep(0.05)
        await a.publish("4321", {"type": "pong"})
        assert await asyncio.wait_for(queue.get(), 2) == '{"type": "pong"}'


async def test_lock_is_exclusive() -> None:
    hub = RoomHub(fakeredis.FakeAsyncRedis())
    order: list[str] = []

    async def worker(name: str) -> None:
        async with hub.lock("4321"):
            order.append(f"{name}-in")
            await asyncio.sleep(0.02)
            order.append(f"{name}-out")

    await asyncio.gather(worker("a"), worker("b"))
    assert order in (["a-in", "a-out", "b-in", "b-out"], ["b-in", "b-out", "a-in", "a-out"])


def test_qr_is_png() -> None:
    raw = base64.b64decode(qr_png_base64("lifeline://join/4321"))
    assert raw.startswith(b"\x89PNG\r\n\x1a\n") and b"IEND" in raw[-12:]
