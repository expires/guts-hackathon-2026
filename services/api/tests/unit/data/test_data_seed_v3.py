"""PENNY_V3_BUILD.md A5 checks on the reseeded students (ADR 0072). No network.

1. September non-rent spending within ±15% of the A3/A4 target.
2. No loan above the official maximum; every funding figure has a stored source.
3. Rent once per period; no Monzo anywhere in the sample data; town matches the card.
4. The data supports the A4 forecast states (data-side B2 estimate; the engine worker tests the real forecast).
Plus A1: statements start 1 July 2026 and end the day before the import; spending patterns.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pytest

from lifeline_data.statements import load_sample, seed
from lifeline_data.statements.samples import sample_hints

REPO = Path(__file__).resolve().parents[5]
SAMPLES = REPO / "services" / "api" / "lifeline_data" / "statements" / "samples"
A4_TARGET = {"scholarship": 380, "scottish": 560, "commuter": 330, "loan_england": 620, "working": 650,
             "mature": 520, "international": 520, "final_year": 520, "rich": 1000, "graduate": 700}
A4_STATE = {"loan_england": "running_short", "working": "running_short", "rich": "running_short"}
BANKS = {"scholarship": "Nationwide", "scottish": "Bank of Scotland", "commuter": "Santander", "loan_england": "HSBC",
         "working": "NatWest", "mature": "Lloyds", "international": "Barclays", "final_year": "Starling",
         "rich": "Barclays", "graduate": "Chase"}
LOAN_MAX = {"england_away": seed.SFE_MAX_AWAY, "england_home": seed.SFE_MAX_HOME, "saas": seed.SAAS_LOAN}


def _rows(sample_id: str, end: date = seed.REF_END) -> tuple[seed.Profile, list[seed.Tx]]:
    p, rows, _ = seed.statement(sample_id, end)
    return p, rows


# ---------- A5.1 ----------


@pytest.mark.parametrize("sample_id", seed.IDS)
def test_september_non_rent_within_15_percent_of_target(sample_id: str) -> None:
    p, rows = _rows(sample_id)
    assert p.target == A4_TARGET[sample_id]
    actual = seed.non_rent_spending(rows, "2026-09")
    assert abs(actual / p.target - 1) <= 0.15, (sample_id, actual, p.target)


@pytest.mark.parametrize("sample_id", seed.IDS)
def test_september_check_holds_on_the_imported_statement(sample_id: str) -> None:
    """Same check on what the import gives the engine: September money out except housing and savings."""
    snap = load_sample(sample_id, today=date(2026, 10, 18))
    from lifeline_engine.money.categorise import categorise

    out = -sum(t.amount for t in snap.transactions if t.amount < 0 and t.date[:7] == "2026-09"
               and categorise(t) not in ("housing", "savings", "transfers"))
    assert abs(out / A4_TARGET[sample_id] - 1) <= 0.15, (sample_id, out)


# ---------- A5.2 ----------


def test_no_loan_above_the_official_maximum() -> None:
    assert seed.sfe_loan(0) == seed.SFE_MAX_AWAY and seed.sfe_loan(0, home=True) == seed.SFE_MAX_HOME
    for income in (25_000, 30_000, 35_000, 45_000, 60_000, 200_000):
        assert seed.sfe_loan(income) <= seed.SFE_MAX_AWAY
        assert seed.sfe_loan(income, home=True) <= seed.SFE_MAX_HOME
    for sample_id in seed.IDS:
        p = seed.profile(sample_id)
        for s in p.streams:
            if s.kind != "maintenance_loan":
                continue
            yearly = round(sum(s.amounts), 2)
            top = LOAN_MAX["saas"] if p.plan == "plan_4" else (
                LOAN_MAX["england_home"] if p.housing == "parents" else LOAN_MAX["england_away"])
            assert yearly <= top, (sample_id, yearly, top)
            if p.plan == "plan_4":
                bursary = sum(a for b in p.streams if b.kind == "bursary" for a in b.amounts)
                assert yearly == seed.SAAS_LOAN and round(bursary, 2) == seed.SAAS_YSB


def test_sfe_amounts_follow_household_income() -> None:
    assert seed.sfe_loan(30_000) == pytest.approx(10_830 - 5_000 / 7.08, abs=0.01)  # Jordan
    assert seed.sfe_loan(60_000) == pytest.approx(10_830 - 35_000 / 7.08, abs=0.01)  # Callum
    assert seed.sfe_loan(45_000) == pytest.approx(10_830 - 20_000 / 7.08, abs=0.01)  # Sam
    assert seed.sfe_loan(35_000, home=True) == pytest.approx(9_118 - 10_000 / 7.08, abs=0.01)  # Priya
    assert seed.sfe_loan(30_000) < seed.SFE_MAX_AWAY


def test_wages_and_tax() -> None:
    assert seed.WAGE_21 == 12.71 and seed.WAGE_18_20 == 10.85
    tax, ni, net = seed.net_month(2_000.0)
    assert (tax, ni, net) == (190.5, 76.2, 1_733.3)
    callum = next(s for s in seed.profile("working").streams if s.kind == "part_time_job")
    assert all(round(a / seed.WAGE_21, 6).is_integer() for a in callum.amounts)
    eilidh = next(s for s in seed.profile("scottish").streams if s.kind == "part_time_job")
    assert all(round(a / seed.WAGE_18_20, 6).is_integer() for a in eilidh.amounts)


@pytest.mark.parametrize("sample_id", seed.IDS)
def test_every_funding_figure_has_a_stored_source(sample_id: str) -> None:
    hints = sample_hints(sample_id)
    sources = hints["sources"]
    assert sources
    for s in sources:
        assert s["figure"] and s["value"] and s["source"] and s["checked"] == "2026-10-18"
        assert s["url"] is None or s["url"].startswith("https://")
        assert s["example"] is None or s["example"].startswith(("example", "rule"))
    refs = {s["ref"] for s in sources}
    for income in hints["income_sources"]:
        assert income["id"] in refs, (sample_id, income["id"])
    assert "rent" in refs and "target" in refs
    doc = (REPO / "docs" / "seed_sources.md").read_text(encoding="utf-8")
    for s in sources:
        assert s["value"] in doc, (sample_id, s["figure"])


# ---------- A5.3 ----------


@pytest.mark.parametrize("sample_id", seed.IDS)
def test_rent_once_per_period(sample_id: str) -> None:
    p, rows = _rows(sample_id)
    rent = [t for t in rows if t.kind == seed.RENT and "DEPOSIT" not in t.description]
    per_month = Counter(t.day.isoformat()[:7] for t in rent)
    assert all(n == 1 for n in per_month.values()), (sample_id, per_month)
    snap = load_sample(sample_id, today=date(2026, 10, 18))
    from lifeline_engine.money.categorise import categorise

    housing = Counter(t.date[:7] for t in snap.transactions if t.amount < 0 and categorise(t) == "housing"
                      and "DEPOSIT" not in t.description)
    assert housing == per_month, sample_id


def _all_sample_text() -> str:
    parts = [(SAMPLES / f.name).read_text(encoding="utf-8") for f in sorted(SAMPLES.iterdir())
             if f.suffix in (".csv", ".json")]
    parts += [load_sample(i, today=date(2026, 10, 18)).model_dump_json() for i in seed.IDS]
    parts += [load_sample(i, "pdf").model_dump_json() for i in seed.IDS]
    return "\n".join(parts).lower()


def test_no_monzo_and_no_pots_anywhere_in_sample_data() -> None:
    text = _all_sample_text()
    assert "monzo" not in text
    assert " pots" not in text and " pot " not in text
    for f in SAMPLES.iterdir():
        if f.suffix == ".pdf":
            assert b"Monzo" not in f.read_bytes()


@pytest.mark.parametrize("sample_id", seed.IDS)
def test_bank_town_and_region_match_the_card(sample_id: str) -> None:
    entry = next(e for e in json.loads((SAMPLES / "index.json").read_text())["samples"] if e["id"] == sample_id)
    snap = load_sample(sample_id, today=date(2026, 10, 18))
    assert snap.holder is not None and snap.holder.town == entry["city"] == entry["hints"]["town"]
    assert snap.region == entry["hints"]["region"]
    assert {a.provider for a in snap.accounts if a.kind in ("current", "savings")} == {BANKS[sample_id]}


# ---------- A1.3: dates relative to the import day ----------


@pytest.mark.parametrize("today", [date(2026, 10, 18), date(2026, 10, 25), date(2026, 11, 3)])
def test_statement_runs_from_1_july_to_the_day_before_the_import(today: date) -> None:
    for sample_id in seed.IDS:
        snap = load_sample(sample_id, today=today)
        days = sorted(t.date for t in snap.transactions)
        assert "2026-07-01" <= days[0] <= "2026-07-03"  # first statement day 1 July (first row within 3 days)
        assert days[-1] <= (today - timedelta(days=1)).isoformat() == snap.as_of
        assert days[-1] >= (today - timedelta(days=4)).isoformat(), sample_id


def test_earlier_rows_do_not_change_when_the_import_day_moves() -> None:
    for sample_id in seed.IDS:
        _, a = _rows(sample_id, date(2026, 10, 17))
        _, b = _rows(sample_id, date(2026, 11, 2))
        cut = [(t.day, t.description, t.amount, t.balance) for t in b if t.day <= date(2026, 10, 17)]
        assert cut == [(t.day, t.description, t.amount, t.balance) for t in a], sample_id


# ---------- A1.6: spending patterns ----------


@pytest.mark.parametrize("sample_id", seed.IDS)
def test_spending_patterns(sample_id: str) -> None:
    p, rows = _rows(sample_id)
    groceries = [t for t in rows if t.category == "Groceries" and t.kind == seed.SPEND]
    assert all(6.0 <= -t.amount <= 35.0 for t in groceries), sample_id
    weeks = (seed.REF_END - seed.START).days / 7
    assert 1.2 <= len(groceries) / weeks <= 3.5, (sample_id, len(groceries) / weeks)
    nights = [t for t in rows if t.category == "Entertainment" and t.kind == seed.SPEND]
    assert all(t.day.weekday() in (3, 4, 5) for t in nights), sample_id
    sep = seed.non_rent_spending(rows, "2026-09")
    if p.id != "loan_england":  # Jordan's spending stays high after loan day
        assert sep >= max(seed.non_rent_spending(rows, m) for m in ("2026-07", "2026-08")), sample_id
    for f in p.fixed:  # bills and subscriptions on fixed dates every month
        if f.kind in (seed.BILL, seed.SUB) and len(f.dates) > 2:
            assert len({d.day for d in f.dates if f.type == "Card payment"}) <= 1, (sample_id, f.name)


def test_spike_after_money_arrives() -> None:
    """Discretionary spending in the 7 days after a big payment is higher per day than in the rest of the month."""
    ratios = []
    for sample_id in seed.IDS:
        p, rows = _rows(sample_id)
        money = sorted({t.day for t in rows if t.kind == seed.INCOME and t.amount >= 500})
        spend = [t for t in rows if t.kind == seed.SPEND and t.category in ("Eating out", "Entertainment",
                                                                             "Shopping")]
        near = [t for t in spend if any(0 <= (t.day - m).days < 7 for m in money)]
        near_days = len({m + timedelta(days=i) for m in money for i in range(7)})
        if not money or not near_days or len(spend) == len(near):
            continue
        far_days = (seed.REF_END - seed.START).days + 1 - near_days
        ratios.append((-sum(t.amount for t in near) / near_days) / (-sum(t.amount for t in spend if t not in near)
                                                                    / far_days))
    assert ratios and sum(ratios) / len(ratios) > 1.2


def test_income_does_not_predict_habits() -> None:
    _, sch = _rows("scholarship")
    _, rich = _rows("rich")
    sch_in = sum(t.amount for t in sch if t.amount > 0)
    rich_in = sum(t.amount for t in rich if t.amount > 0)
    takeaway = ("Eating out", "Entertainment")
    sch_out = -sum(t.amount for t in sch if t.amount < 0 and t.category in takeaway)
    rich_out = -sum(t.amount for t in rich if t.amount < 0 and t.category in takeaway)
    assert sch_out / sch_in < rich_out / rich_in / 2
    assert any(t.kind == seed.SAVINGS for t in sch) and not any(t.kind == seed.SAVINGS for t in rich)


# ---------- A5.4: the data supports the forecast states ----------


@pytest.mark.parametrize("sample_id", seed.IDS)
def test_data_supports_the_a4_forecast_state(sample_id: str) -> None:
    p, rows = _rows(sample_id)
    fc = seed.expected_forecast(p, rows, seed.REF_END)
    assert fc["state"] == A4_STATE.get(sample_id, "on_track") == p.expected_state, (sample_id, fc)
    if sample_id == "loan_england":  # runs out in December, before the January payment
        assert fc["next_money"] == "2027-01-11" and str(fc["run_out"]).startswith("2026-12")
    if sample_id == "working":  # short before the next pay, overdraft close to the £500 limit
        assert fc["next_money"] == "2026-10-23" and -500 < float(str(fc["money_now"])) <= -300
    if sample_id == "rich":  # short before 1 November despite the highest income
        assert fc["next_money"] == "2026-11-01" and str(fc["run_out"]) < "2026-11-01"
    if sample_id in ("scholarship", "final_year"):  # on track to January with spare money
        assert fc["next_money"] == "2027-01-11" and float(str(fc["spare"])) > 100


@pytest.mark.parametrize("sample_id", seed.IDS)
def test_balances_stay_realistic(sample_id: str) -> None:
    p, rows = _rows(sample_id)
    low = min(t.balance for t in rows)
    if p.overdraft_limit is None:
        assert low >= 0, (sample_id, low)
    else:
        assert low >= -p.overdraft_limit, (sample_id, low)
    assert seed.opening_balance(p) >= 0
