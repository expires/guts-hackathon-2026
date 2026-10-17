from datetime import date

import pytest

from playyourself.adapters.base import SourceError
from playyourself.adapters.mock import MockAdapter
from playyourself.domain.models import Transaction

SINCE = date(2025, 1, 1)


async def test_corrupt_rate_drops_records(fixed_today):
    m = MockAdapter("monzo", "steady_saver", corrupt_rate=0.3, today=fixed_today)
    txs = await m.get_transactions(SINCE)
    assert m.last_dropped > 0
    assert txs and all(isinstance(t, Transaction) for t in txs)
    clean = await MockAdapter("monzo", "steady_saver", today=fixed_today).get_transactions(SINCE)
    assert len(txs) + m.last_dropped >= len(clean) - 0
    assert len(txs) < len(clean)


async def test_no_corruption_no_drops(fixed_today):
    m = MockAdapter("monzo", "steady_saver", today=fixed_today)
    await m.get_transactions(SINCE)
    assert m.last_dropped == 0


async def test_fail_rate_one_raises(fixed_today):
    m = MockAdapter("monzo", "steady_saver", fail_rate=1.0, today=fixed_today)
    with pytest.raises(SourceError) as ei:
        await m.get_balances()
    assert ei.value.code == "unavailable" and ei.value.retryable
