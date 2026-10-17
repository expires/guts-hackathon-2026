from datetime import date, timedelta

import pytest

from playyourself.adapters.aggregator import fetch_snapshot
from playyourself.adapters.base import Capability
from playyourself.adapters.mock import MockAdapter


@pytest.fixture
def fixed_today() -> date:
    return date(2026, 9, 30)


@pytest.fixture
def snapshot_for(fixed_today, tmp_path):
    """Async factory: `snap = await snapshot_for("steady_saver")` -> Snapshot."""

    async def factory(persona: str, **kwargs):
        adapters = [
            MockAdapter(
                "monzo",
                persona,
                frozenset({Capability.BALANCES, Capability.TRANSACTIONS}),
                today=fixed_today,
                **kwargs,
            ),
            MockAdapter(
                "trading212",
                persona,
                frozenset({Capability.HOLDINGS, Capability.BALANCES}),
                today=fixed_today,
                **kwargs,
            ),
        ]
        return await fetch_snapshot(
            adapters, fixed_today - timedelta(days=400), 5.0, 0, tmp_path / "cache"
        )

    return factory
