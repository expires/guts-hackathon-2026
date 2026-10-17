from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from playyourself.domain.models import Balance, Holding, Snapshot, SourceStatus, Transaction


def tx(**kw):
    base = dict(
        id="1", ts=datetime(2026, 1, 1, tzinfo=UTC), amount_pence=-100, merchant="m", category="x"
    )
    return Transaction(**{**base, **kw})


def test_amount_must_be_int():
    with pytest.raises(ValidationError):
        tx(amount_pence=1.5)
    with pytest.raises(ValidationError):
        tx(amount_pence="abc")
    with pytest.raises(ValidationError):
        tx(amount_pence="100")


def test_naive_datetime_rejected():
    with pytest.raises(ValidationError):
        tx(ts=datetime(2026, 1, 1))


def test_frozen():
    with pytest.raises(ValidationError):
        tx().amount_pence = 5


def test_holding_value_non_negative():
    with pytest.raises(ValidationError):
        Holding(instrument_id="a", name="a", quantity=1, value_pence=-1, asset_class="equity")


def test_snapshot_properties():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    snap = Snapshot(
        balances=[
            Balance(account_id="c", kind="current", value_pence=100),
            Balance(account_id="i", kind="isa_cash", value_pence=50),
        ],
        holdings=[
            Holding(instrument_id="a", name="a", quantity=1, value_pence=1000, asset_class="bond")
        ],
        sources={"a": SourceStatus(name="a", ok=False, stale=True)},
        as_of=now,
    )
    assert snap.liquid_cash_pence == 150
    assert snap.isa_value_pence == 1050
    assert snap.stale
