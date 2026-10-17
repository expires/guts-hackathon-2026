from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from lifeline_data.settings import DataSettings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "data"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


@pytest.fixture
def fixture_text():
    return read_fixture


@pytest.fixture
def settings() -> DataSettings:
    return DataSettings(app_env="test", backoff_base_seconds=0, redis_url="", database_url="")


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c


class FakeClock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def no_sleep():
    async def _sleep(_: float) -> None:
        return None

    return _sleep
