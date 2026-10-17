from __future__ import annotations

import json
import math
import re
from datetime import date

import pytest

from lifeline_contracts.accounts import Holding
from lifeline_contracts.finance import Account, FinanceSnapshot, Transaction
from lifeline_contracts.habits import HabitFactors
from lifeline_engine.money.categorise import categorise
from lifeline_engine.money.habits import BANDS, FACTOR_IDS, habit_factors, overall_score, score_factor
from lifeline_engine.money.recurring import detect_recurring

TODAY = date(2026, 6, 30)
_n = 0


def tx(month: int, day: int, amount: float, description: str, merchant: str | None = None) -> Transaction:
    global _n
    _n += 1
    return Transaction(
        id=f"t{_n}", account_id="cur", date=f"2026-{month:02d}-{day:02d}", amount=amount,
        description=description, merchant=merchant,
    )


def holding(value: float, asset_class: str = "equity", name: str = "A") -> Holding:
    return Holding(instrument_id=name, name=name, quantity=1, value=value, asset_class=asset_class)  # type: ignore[arg-type]


def snap(txs: list[Transaction], holdings: list[Holding] | None = None) -> FinanceSnapshot:
    return FinanceSnapshot(
        status="mock", source="fixtures", as_of="2026-06-30",
        accounts=[
            Account(id="cur", name="Current", kind="current", provider="Monzo", balance=2000),
            Account(id="sav", name="Pot", kind="savings", provider="Monzo", balance=1000),
            Account(id="isa", name="Cash ISA", kind="isa", provider="Bank", balance=500),
        ],
        transactions=txs,
        holdings=[holding(3000, name="A"), holding(1000, "bond", "B")] if holdings is None else holdings,
    )


def main_txs() -> list[Transaction]:
    out: list[Transaction] = []
    for m in range(1, 7):
        out.append(tx(m, 1, 3000, "Salary"))
        out.append(tx(m, 2, -1000, "Rent to landlord", "Landlord"))
        out.append(tx(m, 5, -10, "NETFLIX.COM", "Netflix"))
        out.append(tx(m, 20, -500, "Transfer to savings pot"))
    for m in (4, 5, 6):
        out.append(tx(m, 8, -5, "SPOTIFY", "Spotify"))
    out.append(tx(3, 10, -100, "ZARA", "Zara"))
    return out


# Spend per month: 1010, 1010, 1110, 1015, 1015, 1015 = 6175. Income 18000.
MONTHLY = [1010, 1010, 1110, 1015, 1015, 1015]
MEAN = 6175 / 6


def by_id(hf: HabitFactors) -> dict[str, object]:
    return {f.id: f for f in hf.factors}


def test_categories_assumed() -> None:
    cats = {t.description: categorise(t) for t in main_txs()}
    assert cats["Rent to landlord"] == "housing" and cats["NETFLIX.COM"] == "subscriptions"
    assert cats["ZARA"] == "shopping" and cats["Transfer to savings pot"] == "savings"


def test_all_factors_hand_computed() -> None:
    hf = habit_factors(snap(main_txs()), TODAY)
    f = {x.id: x for x in hf.factors}
    assert hf.version == "hf-1" and hf.window.months == 6 and hf.window.end == "2026-06-30"
    assert [x.id for x in hf.factors] == list(FACTOR_IDS)
    assert f["savings_rate"].raw == pytest.approx((18000 - 6175) / 18000, abs=1e-3)
    assert f["runway_months"].raw == pytest.approx(3500 / MEAN, abs=1e-3)  # 2000 + 1000 + cash ISA 500
    sd = math.sqrt(sum((x - MEAN) ** 2 for x in MONTHLY) / 6)
    assert f["spend_stability"].raw == pytest.approx(1 - sd / MEAN, abs=1e-3)
    assert f["discretionary_share"].raw == pytest.approx(175 / 6175, abs=1e-3)  # netflix 60, spotify 15, zara 100
    assert f["subscription_creep"].raw == pytest.approx((15 - 10) / 10, abs=1e-3)  # rent is not a subscription
    assert f["isa_concentration"].raw == pytest.approx(0.75**2 + 0.25**2, abs=1e-3)
    assert f["shock_resilience"].raw == pytest.approx((3500 + 4000 * 0.65) / MEAN, abs=1e-3)
    for x in hf.factors:
        assert x.score == score_factor(x.id, x.raw)
    assert hf.overall == overall_score([x.score for x in hf.factors])


def test_plain_english_labels() -> None:
    for x in habit_factors(snap(main_txs()), TODAY).factors:
        text = f"{x.label} {x.explainer}".lower()
        for banned in ("hhi", "runway", "shock resilience", "—"):
            assert banned not in text
        assert x.label and x.explainer


def test_worst_drawdown_param() -> None:
    f = {x.id: x for x in habit_factors(snap(main_txs()), TODAY, worst_drawdown=0.5).factors}
    assert f["shock_resilience"].raw == pytest.approx((3500 + 2000) / MEAN, abs=1e-3)


def test_mid_month_today_excludes_incomplete_month() -> None:
    hf = habit_factors(snap(main_txs()), date(2026, 7, 15))
    assert hf.window.end == "2026-06-30"
    early = habit_factors(snap(main_txs()), date(2026, 6, 15))  # window Dec..May
    assert early.window.end == "2026-05-31"
    assert early.factors[0].reason == "Not enough history yet"


def test_transfers_and_savings_not_spending() -> None:
    base = habit_factors(snap(main_txs()), TODAY)
    extra = main_txs() + [tx(5, 3, -900, "Transfer to Jo"), tx(5, 4, 900, "Transfer from Jo")]
    assert habit_factors(snap(extra), TODAY) == base


def test_zero_income() -> None:
    txs = [tx(m, 3, -500, "Rent landlord", "Landlord") for m in range(1, 7)]
    f = {x.id: x for x in habit_factors(snap(txs), TODAY).factors}
    assert f["savings_rate"].raw is None and f["savings_rate"].score is None
    assert f["savings_rate"].reason == "No income in this period"
    assert f["runway_months"].raw == pytest.approx(3500 / 500)
    assert f["spend_stability"].raw == pytest.approx(1.0)


def test_zero_spend() -> None:
    f = {x.id: x for x in habit_factors(snap([tx(m, 1, 3000, "Salary") for m in range(1, 7)]), TODAY).factors}
    assert f["savings_rate"].raw == pytest.approx(1.0)
    for n in ("runway_months", "spend_stability", "discretionary_share", "shock_resilience"):
        assert f[n].raw is None and f[n].reason == "No spending in this period"
    assert f["subscription_creep"].raw == 0.0
    assert f["isa_concentration"].raw is not None


def test_insufficient_history_and_shorter_window() -> None:
    txs = [t for t in main_txs() if int(t.date[5:7]) >= 3]
    f = {x.id: x for x in habit_factors(snap(txs), TODAY).factors}
    for n in FACTOR_IDS:
        if n == "isa_concentration":
            assert f[n].raw is not None
        else:
            assert f[n].raw is None and f[n].score is None and f[n].reason == "Not enough history yet"
    ok = {x.id: x for x in habit_factors(snap(txs), TODAY, window_months=4).factors}
    assert ok["savings_rate"].raw is not None


def test_no_holdings() -> None:
    f = {x.id: x for x in habit_factors(snap(main_txs(), holdings=[]), TODAY).factors}
    assert f["isa_concentration"].raw is None and f["isa_concentration"].score is None
    assert f["isa_concentration"].reason == "No investments found"
    assert f["shock_resilience"].raw == pytest.approx(3500 / MEAN, abs=1e-3)


def test_subscription_creep_edges() -> None:
    sal = [tx(m, 1, 3000, "Salary") for m in range(1, 7)]
    new = sal + [tx(m, 5, -10, "NETFLIX.COM", "Netflix") for m in (4, 5, 6)]
    assert {x.id: x for x in habit_factors(snap(new), TODAY).factors}["subscription_creep"].raw == 1.0
    steady = sal + [tx(m, 5, -10, "NETFLIX.COM", "Netflix") for m in range(1, 7)]
    assert {x.id: x for x in habit_factors(snap(steady), TODAY).factors}["subscription_creep"].raw == 0.0


def test_scattered_billing_days_are_not_subscriptions() -> None:
    sal = [tx(m, 1, 3000, "Salary") for m in range(1, 7)]
    days = (1, 5, 8, 12, 15, 18)  # gaps stay 25-35 days, so detect_recurring alone would accept it
    scattered = sal + [tx(m, d, -10, "NETFLIX.COM", "Netflix") for m, d in zip(range(1, 7), days, strict=True)]
    assert detect_recurring(scattered, TODAY)
    f = {x.id: x for x in habit_factors(snap(scattered), TODAY).factors}
    assert f["subscription_creep"].raw == 0.0


def test_housing_is_not_a_subscription() -> None:
    sal = [tx(m, 1, 3000, "Salary") for m in range(1, 7)]
    rent = [tx(m, 2, -500 if m < 4 else 900, "Rent to landlord", "Landlord") for m in range(1, 7)]
    assert {x.id: x for x in habit_factors(snap(sal + rent), TODAY).factors}["subscription_creep"].raw == 0.0


@pytest.mark.parametrize("name", list(BANDS))
def test_band_endpoints(name: str) -> None:
    for raw, score in BANDS[name]:  # type: ignore[index]
        assert score_factor(name, raw) == score  # type: ignore[arg-type]


def test_interpolation_clamping_and_overall() -> None:
    assert score_factor("savings_rate", 0.05) == 35
    assert score_factor("runway_months", 4.5) == 65
    assert score_factor("discretionary_share", 0.325) == 55
    assert score_factor("savings_rate", -5) == 0 and score_factor("savings_rate", 5) == 100
    assert score_factor("subscription_creep", 9) == 0 and score_factor("isa_concentration", 0.01) == 100
    assert score_factor("savings_rate", None) is None
    assert BANDS["shock_resilience"] == BANDS["runway_months"]
    assert overall_score([50, 75, None]) == 62 and overall_score([None, None]) is None


def test_schema_and_output_have_no_money_amounts() -> None:
    def names(node: object, acc: set[str]) -> set[str]:
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "properties":
                    acc.update(v)
                names(v, acc)
        elif isinstance(node, list):
            for v in node:
                names(v, acc)
        return acc

    for p in names(HabitFactors.model_json_schema(), set()):
        for banned in ("amount", "balance", "value", "gbp", "pence"):
            assert banned not in p.lower()
    s = snap(main_txs())
    blob = json.dumps(habit_factors(s, TODAY).model_dump(mode="json"))
    amounts = {abs(t.amount) for t in s.transactions} | {abs(a.balance) for a in s.accounts}
    amounts |= {h.value for h in s.holdings}
    big = {str(int(a)) for a in amounts if a >= 500}
    assert big
    for a in big:
        assert not re.search(rf"(?<![\d.]){a}(?![\d.])", blob)
