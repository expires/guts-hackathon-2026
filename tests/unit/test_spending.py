from datetime import UTC, date, datetime, timedelta

import pytest

from playyourself.adapters.aggregator import fetch_snapshot
from playyourself.adapters.base import Capability
from playyourself.adapters.mock import MockAdapter
from playyourself.decision.spending import analyse_spending
from playyourself.domain.models import Snapshot, Transaction

AS_OF = date(2026, 6, 30)
_n = 0


def tx(y, m, d, amount, merchant, category, transfer=False) -> Transaction:
    global _n
    _n += 1
    return Transaction(
        id=f"t{_n}",
        ts=datetime(y, m, d, 12, 0, tzinfo=UTC),
        amount_pence=amount,
        merchant=merchant,
        category=category,
        is_transfer=transfer,
    )


def build() -> Snapshot:
    txs = []
    for m in (1, 2, 3):  # previous window
        txs.append(tx(2026, m, 3, -3000, "TESCO", "groceries"))
    for m in (4, 5, 6):
        txs.append(tx(2026, m, 25, 200000, "SALARY", "income"))
        txs.append(tx(2026, m, 20, -30000, "ISA", "savings", transfer=True))
        txs.append(tx(2026, m, 3, -(1000 * m + 1000), "TESCO", "groceries"))
        txs.append(tx(2026, m, 5, -1000, "NETFLIX", "entertainment"))
    txs += [
        tx(2026, 4, 10, -1000, "PRET", "eating_out"),
        tx(2026, 5, 10, -1500, "PRET", "eating_out"),
        tx(2026, 6, 10, -800, "PRET", "eating_out"),
        tx(2026, 6, 20, -3000, "NANDOS", "eating_out"),
        tx(2026, 4, 1, -1000, "AMAZON", "shopping"),
        tx(2026, 4, 2, -1000, "AMAZON", "shopping"),
        tx(2026, 5, 2, -1000, "AMAZON", "shopping"),
        tx(2026, 5, 3, -1000, "AMAZON", "shopping"),
        tx(2026, 6, 12, -5000, "ASOS", "shopping"),
    ]
    return Snapshot(transactions=txs, as_of=datetime(2026, 7, 5, tzinfo=UTC))


@pytest.fixture(scope="module")
def a():
    return analyse_spending(build(), months=3, as_of=AS_OF)


def test_window_and_monthly(a):
    assert (a.window.months, str(a.window.start), str(a.window.end)) == (
        3,
        "2026-04-01",
        "2026-06-30",
    )
    assert [(m.month, m.income_pence, m.spend_pence, m.net_pence) for m in a.monthly] == [
        ("2026-04", 200000, 9000, 191000),
        ("2026-05", 200000, 10500, 189500),
        ("2026-06", 200000, 16800, 183200),
    ]


def test_categories(a):
    cats = {c.category: c for c in a.by_category}
    assert [c.category for c in a.by_category] == [
        "groceries",
        "shopping",
        "eating_out",
        "entertainment",
    ]
    assert cats["groceries"].total_pence == 18000
    assert cats["groceries"].share == pytest.approx(18000 / 36300, abs=1e-4)
    assert cats["groceries"].monthly_avg_pence == 6000
    assert cats["groceries"].change_vs_prev_period == 1.0  # 18000 vs 9000 before
    assert cats["eating_out"].total_pence == 6300
    assert cats["eating_out"].change_vs_prev_period is None  # no prior spend
    assert "income" not in cats and "savings" not in cats  # no inflows, no transfers


def test_category_matrix(a):
    m = a.category_by_month
    assert m.months == ["2026-04", "2026-05", "2026-06"]
    assert m.values["groceries"] == [5000, 6000, 7000]
    assert m.values["eating_out"] == [1000, 1500, 3800]
    assert m.values["shopping"] == [2000, 2000, 5000]


def test_top_merchants(a):
    got = [(x.merchant, x.total_pence, x.count, x.category) for x in a.top_merchants]
    assert got[:3] == [
        ("TESCO", 18000, 3, "groceries"),
        ("ASOS", 5000, 1, "shopping"),
        ("AMAZON", 4000, 4, "shopping"),
    ]
    assert len(got) <= 10


def test_subscriptions(a):
    s = a.subscriptions
    assert [(i.merchant, i.monthly_pence, str(i.first_seen), i.months_active) for i in s.items] == [
        ("NETFLIX", 1000, "2026-04-05", 3)
    ]
    assert (s.total_monthly_pence, s.annualised_pence, s.by_month) == (1000, 12000, [1000] * 3)


def test_unusual(a):
    assert [(u.merchant, u.amount_pence, u.category_median_pence) for u in a.unusual] == [
        ("ASOS", 5000, 1000)
    ]


def test_patterns(a):
    p = a.patterns
    assert p.average_daily_spend_pence == round(36300 / 91)
    assert sum(p.spend_by_weekday_pence) == 36300
    assert p.spend_by_weekday_pence == [0, 1000, 8800, 1000, 12000, 4000, 9500]
    assert p.biggest_spending_weekday == "Friday"
    assert p.weekend_share_of_discretionary == pytest.approx(7500 / 18300, abs=1e-4)
    assert p.weekday_share_of_discretionary == pytest.approx(10800 / 18300, abs=1e-4)


def test_insights(a):
    assert "Groceries is the largest category at 50% of spending" in a.insights
    assert "Groceries is up 100% vs the previous 3 months" in a.insights
    assert "Subscriptions cost £10.00/month (£120.00/year) across 1 services" in a.insights
    assert "1 unusual transaction this period" in a.insights
    assert "41% of discretionary spending is on weekends" in a.insights
    assert "Average daily spend is £3.99" in a.insights
    assert "Income exceeded spending in all 3 months" in a.insights
    assert not any("should" in i.lower() for i in a.insights)


def test_empty_snapshot():
    r = analyse_spending(Snapshot(as_of=datetime(2026, 7, 5, tzinfo=UTC)), months=3)
    assert r.by_category == [] and r.unusual == [] and r.subscriptions.items == []
    assert r.patterns.biggest_spending_weekday is None


def test_month_end_includes_current_month():
    snap = build()
    assert analyse_spending(snap, 3, as_of=date(2026, 6, 15)).window.end == date(2026, 5, 31)


async def _persona(name, tmp_path):
    today = date(2026, 9, 30)
    adapters = [
        MockAdapter(
            "monzo",
            name,
            frozenset({Capability.BALANCES, Capability.TRANSACTIONS}),
            today=today,
        )
    ]
    snap = await fetch_snapshot(adapters, today - timedelta(days=400), 5.0, 0, None)
    return analyse_spending(snap, 6)


async def test_subscription_creep_persona_rises(tmp_path):
    r = await _persona("subscription_creep", tmp_path)
    by_month = r.subscriptions.by_month
    assert by_month[-1] > by_month[0]
    assert len(r.subscriptions.items) >= 5


async def test_volatile_persona_has_unusual(tmp_path):
    r = await _persona("volatile_spender", tmp_path)
    assert r.unusual and all(u.amount_pence > 3 * u.category_median_pence for u in r.unusual)
