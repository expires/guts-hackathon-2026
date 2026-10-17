import json
import math
import re
from datetime import UTC, date, datetime

import pytest

from playyourself.decision.habits import (
    FACTOR_NAMES,
    HabitVector,
    detect_subscriptions,
    effective_n,
    habit_vector,
)
from playyourself.decision.scoring import score_factor
from playyourself.domain.models import Balance, Holding, Snapshot, Transaction

AS_OF = date(2026, 6, 30)
_n = 0


def tx(y, m, d, amount, merchant, category="general", transfer=False):
    global _n
    _n += 1
    return Transaction(
        id=f"t{_n}",
        ts=datetime(y, m, d, 12, tzinfo=UTC),
        amount_pence=amount,
        merchant=merchant,
        category=category,
        is_transfer=transfer,
    )


def snap(txs, holdings=None, balances=None):
    if balances is None:
        balances = [
            Balance(account_id="c", kind="current", value_pence=200_000),
            Balance(account_id="p", kind="pot", value_pence=100_000),
            Balance(account_id="i", kind="isa_cash", value_pence=50_000),
        ]
    if holdings is None:
        holdings = [
            Holding(
                instrument_id="A", name="A", quantity=1, value_pence=300_000, asset_class="equity"
            ),
            Holding(
                instrument_id="B", name="B", quantity=1, value_pence=100_000, asset_class="bond"
            ),
        ]
    return Snapshot(
        balances=balances,
        transactions=txs,
        holdings=holdings,
        as_of=datetime(2026, 6, 30, tzinfo=UTC),
    )


def main_txs():
    out = []
    for m in range(1, 7):
        out.append(tx(2026, m, 1, 300_000, "SALARY", "income"))
        out.append(tx(2026, m, 2, -100_000, "LANDLORD", "bills"))
        out.append(tx(2026, m, 5, -1_000, "NETFLIX", "entertainment"))
        out.append(tx(2026, m, 20, -50_000, "SAVINGS POT", "savings", transfer=True))
        out.append(tx(2026, m, 21, 50_000, "SELF", "income", transfer=True))
    for m in (4, 5, 6):
        out.append(tx(2026, m, 8, -500, "SPOTIFY", "entertainment"))
    out.append(tx(2026, 3, 10, -10_000, "ZARA", "shopping"))
    out.append(tx(2026, 6, 30, -5_000, "SELF", "savings", transfer=True))  # latest tx
    return out


# Hand-computed: monthly spend = [101000, 101000, 111000, 101500, 101500, 101500]
# total 617500, mean 102916.666..., income 1_800_000.
MEAN = 617_500 / 6


def test_all_factors_hand_computed():
    hv = habit_vector(snap(main_txs()), as_of=AS_OF)
    f = hv.factors
    assert hv.version == "hv-1"
    assert hv.window.months == 6
    assert hv.window.end == date(2026, 6, 30)
    assert set(f) == set(FACTOR_NAMES)
    assert len(f) == 7

    assert f["savings_rate"].raw == pytest.approx((1_800_000 - 617_500) / 1_800_000, abs=1e-3)
    # liquid = 200k + 100k + 50k
    assert f["runway_months"].raw == pytest.approx(350_000 / MEAN, abs=1e-3)
    var = (2 * 1916.6667**2 + 8083.3333**2 + 3 * 1416.6667**2) / 6
    assert f["spend_stability"].raw == pytest.approx(1 - math.sqrt(var) / MEAN, abs=1e-3)
    # discretionary: netflix 6*1000 + spotify 3*500 + zara 10000
    assert f["discretionary_share"].raw == pytest.approx(17_500 / 617_500, abs=1e-3)
    # recurring: netflix, spotify (landlord is housing, excluded). last3 1500, prior3 1000
    assert f["subscription_creep"].raw == pytest.approx(500 / 1_000, abs=1e-3)
    assert f["isa_diversification"].raw == pytest.approx(0.75**2 + 0.25**2, abs=1e-3)
    # isa value = 400k holdings + 50k cash
    assert f["shock_resilience"].raw == pytest.approx((350_000 + 450_000 * 0.65) / MEAN, abs=1e-3)
    for name, fv in f.items():
        assert fv.score == score_factor(name, fv.raw)


def test_worst_drawdown_param():
    hv = habit_vector(snap(main_txs()), as_of=AS_OF, worst_drawdown=0.5)
    assert hv.factors["shock_resilience"].raw == pytest.approx((350_000 + 225_000) / MEAN, abs=1e-3)


def test_default_as_of_is_latest_transaction():
    hv = habit_vector(snap(main_txs()))
    assert hv.window.end == date(2026, 6, 30)


def test_mid_month_as_of_excludes_incomplete_month():
    hv = habit_vector(snap(main_txs()), as_of=date(2026, 7, 15))
    assert hv.window.end == date(2026, 6, 30)
    assert hv.factors["savings_rate"].raw == pytest.approx(
        (1_800_000 - 617_500) / 1_800_000, abs=1e-3
    )
    hv2 = habit_vector(snap(main_txs()), as_of=date(2026, 6, 15))  # window Dec..May
    assert hv2.window.end == date(2026, 5, 31)
    assert hv2.factors["savings_rate"].reason == "insufficient history"


def test_transfers_excluded():
    base = habit_vector(snap(main_txs()), as_of=AS_OF)
    extra = main_txs() + [
        tx(2026, 5, 3, -900_000, "BIG", "shopping", transfer=True),
        tx(2026, 5, 4, 900_000, "BIG IN", "income", transfer=True),
    ]
    assert habit_vector(snap(extra), as_of=AS_OF) == base


def test_zero_income():
    txs = [tx(2026, m, 3, -50_000, "RENT", "bills") for m in range(1, 7)]
    f = habit_vector(snap(txs), as_of=AS_OF).factors
    assert f["savings_rate"].raw is None
    assert f["savings_rate"].score is None
    assert f["savings_rate"].reason == "no income in window"
    assert f["runway_months"].raw == pytest.approx(350_000 / 50_000, abs=1e-3)
    assert f["spend_stability"].raw == pytest.approx(1.0, abs=1e-3)


def test_zero_spend():
    txs = [tx(2026, m, 1, 300_000, "SALARY", "income") for m in range(1, 7)]
    f = habit_vector(snap(txs), as_of=AS_OF).factors
    assert f["savings_rate"].raw == pytest.approx(1.0, abs=1e-3)
    for n in ("runway_months", "spend_stability", "discretionary_share", "shock_resilience"):
        assert f[n].raw is None
        assert f[n].reason == "no spend in window"
    assert f["subscription_creep"].raw == pytest.approx(0.0, abs=1e-3)
    assert f["isa_diversification"].raw is not None


def test_insufficient_history():
    txs = [t for t in main_txs() if t.ts.month >= 3]
    f = habit_vector(snap(txs), as_of=AS_OF).factors
    for n in FACTOR_NAMES:
        if n == "isa_diversification":
            assert f[n].raw is not None
        else:
            assert f[n].raw is None
            assert f[n].score is None
            assert f[n].reason == "insufficient history"
    # shorter window is fine with the same data
    ok = habit_vector(snap(txs), window_months=4, as_of=AS_OF).factors
    assert ok["savings_rate"].raw is not None


def test_empty_isa():
    f = habit_vector(snap(main_txs(), holdings=[]), as_of=AS_OF).factors
    assert f["isa_diversification"].raw is None
    assert f["isa_diversification"].score is None
    assert f["isa_diversification"].reason
    assert f["shock_resilience"].raw == pytest.approx((350_000 + 50_000 * 0.65) / MEAN, abs=1e-3)


def test_effective_n():
    assert effective_n(0.25) == pytest.approx(4.0)


def test_subscription_creep_edge_cases():
    # new subscription appears only in last 3 months -> prior == 0, last > 0 -> 1.0
    txs = [tx(2026, m, 1, 300_000, "SALARY", "income") for m in range(1, 7)]
    txs += [tx(2026, m, 5, -1_000, "GYM", "personal_care") for m in (4, 5, 6)]
    assert habit_vector(snap(txs), as_of=AS_OF).factors["subscription_creep"].raw == 1.0
    # steady subscription -> 0 change
    txs = [tx(2026, m, 1, 300_000, "SALARY", "income") for m in range(1, 7)]
    txs += [tx(2026, m, 5, -1_000, "GYM", "personal_care") for m in range(1, 7)]
    assert habit_vector(snap(txs), as_of=AS_OF).factors["subscription_creep"].raw == pytest.approx(
        0
    )


def test_detect_subscriptions():
    txs = [tx(2026, m, 5, -1_000, "A") for m in (1, 2, 3)]
    txs += [tx(2026, m, 5, -1_000 - 300 * m, "VARYING") for m in (1, 2, 3)]  # >10% off
    txs += [tx(2026, m, 5, -1_000, "TWO") for m in (1, 2)]  # too few months
    txs += [tx(2026, m, 5, -1_000, "XFER", transfer=True) for m in (1, 2, 3)]
    # three months but irregular cadence: clustered payments
    txs += [
        tx(2026, 1, 1, -700, "BURST"),
        tx(2026, 1, 2, -700, "BURST"),
        tx(2026, 1, 3, -700, "BURST"),
        tx(2026, 2, 1, -700, "BURST"),
        tx(2026, 3, 1, -700, "BURST"),
    ]
    assert detect_subscriptions(txs) == ["A"]


def test_schema_has_no_money_fields():
    def names(node, acc):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "properties":
                    acc.update(v)
                names(v, acc)
        elif isinstance(node, list):
            for v in node:
                names(v, acc)
        return acc

    props = names(HabitVector.model_json_schema(), set())
    assert "factors" in props
    for p in props:
        for banned in ("pence", "amount", "balance", "value_pence"):
            assert banned not in p.lower()


async def test_serialised_output_has_no_amounts(snapshot_for):
    snap_ = await snapshot_for("steady_saver")
    hv = habit_vector(snap_)
    blob = json.dumps(hv.model_dump(mode="json"))
    amounts = {abs(t.amount_pence) for t in snap_.transactions}
    amounts |= {abs(b.value_pence) for b in snap_.balances}
    amounts |= {h.value_pence for h in snap_.holdings}
    big = {str(a) for a in amounts if a >= 1000}
    assert big
    for a in big:
        # whole-number tokens only: digits inside float mantissas are coincidence
        assert not re.search(rf"(?<![\d.]){a}(?![\d.])", blob)


async def test_persona_sanity(snapshot_for):
    steady = habit_vector(await snapshot_for("steady_saver")).factors
    creep = habit_vector(await snapshot_for("subscription_creep")).factors
    conc = habit_vector(await snapshot_for("concentrated_isa")).factors
    vol = habit_vector(await snapshot_for("volatile_spender")).factors
    assert creep["subscription_creep"].raw > 0
    assert creep["subscription_creep"].raw > steady["subscription_creep"].raw
    assert conc["isa_diversification"].raw > steady["isa_diversification"].raw
    assert vol["spend_stability"].raw < steady["spend_stability"].raw


def test_detect_subscriptions_excludes_rent():
    txs = [
        Transaction(
            id=f"{m}-{i}",
            ts=datetime(2026, i, 1, tzinfo=UTC),
            amount_pence=-amt,
            merchant=m,
            category="bills",
        )
        for i in range(1, 6)
        for m, amt in (("LANDLORD RENT", 95_000), ("THREE MOBILE", 2_000))
    ]
    assert detect_subscriptions(txs) == ["THREE MOBILE"]


def test_detect_subscriptions_requires_fixed_billing_day():
    # Same amount roughly monthly, but on scattered days: a habit, not a subscription.
    days = (3, 28, 12, 25, 6)
    txs = [
        Transaction(
            id=f"n{i}",
            ts=datetime(2026, i + 1, d, tzinfo=UTC),
            amount_pence=-1_500,
            merchant="NANDOS",
            category="eating_out",
        )
        for i, d in enumerate(days)
    ]
    assert detect_subscriptions(txs) == []
