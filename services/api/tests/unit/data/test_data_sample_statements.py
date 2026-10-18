"""Sample statements (ADR 0047): generator output, CSV and PDF import, income and debt detection. No network."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

from lifeline_contracts.account import SampleStatement
from lifeline_contracts.finance import FinanceSnapshot, Transaction
from lifeline_data.statements import list_samples, load_sample, parse_statement, to_snapshot
from lifeline_data.statements.detect import detect_debts, detect_income, detect_is_student
from lifeline_data.statements.parse import PDF_WARNING
from lifeline_data.statements.samples import sample_hints

REPO = Path(__file__).resolve().parents[5]
SAMPLES = REPO / "services" / "api" / "lifeline_data" / "statements" / "samples"
DEMO_COPY = REPO / "demo" / "statements"
INDEX = json.loads((SAMPLES / "index.json").read_text())["samples"]
IDS = [s["id"] for s in INDEX]

JUDGE_IDS = ["scholarship", "scottish", "commuter", "loan_england", "working", "mature", "international",
             "final_year", "rich", "graduate"]
EXPECTED_KINDS = {
    "scholarship": {"scholarship", "bursary"},
    "scottish": {"maintenance_loan", "bursary", "part_time_job"},
    "commuter": {"grant", "family"},
    "loan_england": {"maintenance_loan"},
    "working": {"maintenance_loan", "part_time_job"},
    "mature": {"maintenance_loan", "grant", "part_time_job"},
    "international": {"family"},
    "final_year": {"salary", "maintenance_loan"},
    "rich": {"family"},
    "graduate": {"salary", "family"},
}


def _snap(sample_id: str, fmt: str) -> FinanceSnapshot:
    p = parse_statement((SAMPLES / f"{sample_id}.{fmt}").read_bytes(), f"{sample_id}.{fmt}")
    assert p.status == "done", p.warnings
    assert p.rows_rejected == 0
    return to_snapshot(p)


def test_index_matches_contract():
    assert JUDGE_IDS == IDS  # the 10 student profiles only (ADR 0070); team phone profiles are gone
    for entry in INDEX:
        SampleStatement.model_validate({k: v for k, v in entry.items() if k != "hints"})
        assert set(entry["hints"]) == {"name", "is_student", "age", "housing", "student_loan_plan", "income_sources",
                                       "debts", "monthly_costs", "accounts", "budgets", "goals"}
        assert entry["hints"]["housing"] in {"rent", "own", "mortgage", "parents"}
        assert entry["team"] is False
        assert set(entry["funding"]) == EXPECTED_KINDS[entry["id"]]
    assert [s.id for s in list_samples()] == [s.id for s in list_samples(team=False)] == JUDGE_IDS
    assert list_samples(team=True) == []


@pytest.mark.parametrize("sample_id", IDS)
@pytest.mark.parametrize("fmt", ["csv", "pdf"])
def test_each_sample_imports_fast(sample_id, fmt):
    start = time.perf_counter()
    snap = _snap(sample_id, fmt)
    assert time.perf_counter() - start < 2.0
    assert snap.transactions[0].date >= "2026-07-17" and snap.as_of <= "2026-10-16"
    assert {s.kind for s in snap.income_sources} == EXPECTED_KINDS[sample_id]
    assert snap.is_student is (None if sample_id == "graduate" else True)
    assert snap.age is None and snap.student_loan_plan is None  # not shown on a statement


@pytest.mark.parametrize("sample_id", IDS)
def test_csv_and_pdf_agree(sample_id):
    csv_snap, pdf_snap = _snap(sample_id, "csv"), _snap(sample_id, "pdf")
    assert len(csv_snap.transactions) == len(pdf_snap.transactions)
    total = round(sum(t.amount for t in csv_snap.transactions), 2)
    assert total == round(sum(t.amount for t in pdf_snap.transactions), 2)
    assert csv_snap.income_sources == pdf_snap.income_sources
    assert [d.kind for d in csv_snap.debts] == [d.kind for d in pdf_snap.debts]


def test_rich_klarna_is_bnpl_debt():
    for fmt in ("csv", "pdf"):
        debts = {d.kind: d for d in _snap("rich", fmt).debts}
        assert set(debts) == {"bnpl"}
        # ASOS 1 of 3 paid (2 x 29.00) + ZARA 1 of 3 paid (2 x 40.00); older plans are complete.
        assert debts["bnpl"].balance == 138.0 and debts["bnpl"].due_date == "2026-10-20"
        assert debts["bnpl"].id == "bnpl_klarna"


def test_working_overdraft():
    csv_debt = {d.kind: d for d in _snap("working", "csv").debts}["overdraft"]
    assert csv_debt.rate_pct == 39.0 and csv_debt.balance == 0.0  # Monzo CSV has no balance
    pdf_debt = {d.kind: d for d in _snap("working", "pdf").debts}["overdraft"]
    hint = next(d for d in sample_hints("working")["debts"] if d["kind"] == "overdraft")
    assert pdf_debt.balance == hint["balance"] > 0 and pdf_debt.rate_pct == 39.0


def test_no_debt_for_scholarship_and_commuter():
    for sample_id in ("scholarship", "scottish", "commuter", "loan_england", "mature", "international",
                      "final_year", "graduate"):
        assert _snap(sample_id, "pdf").debts == []


def test_income_does_not_predict_habits():
    def spend(snap: FinanceSnapshot, words: tuple[str, ...]) -> float:
        return -sum(t.amount for t in snap.transactions
                    if t.amount < 0 and any(w in t.description.lower() for w in words))

    sch, rich = _snap("scholarship", "csv"), _snap("rich", "csv")
    sch_in = sum(t.amount for t in sch.transactions if t.amount > 0)
    rich_in = sum(t.amount for t in rich.transactions if t.amount > 0)
    assert rich_in > 4 * sch_in
    takeaway = ("deliveroo", "uber", "pret", "nandos", "starbucks", "revolution", "greggs")
    assert spend(sch, takeaway) / sch_in < spend(rich, takeaway) / rich_in / 3
    assert spend(sch, ("moved to rainy day pot",)) > 0
    assert not any((t.provider_category or "") == "Savings" for t in rich.transactions)
    assert not _snap("scholarship", "pdf").debts and _snap("rich", "pdf").debts


@pytest.mark.parametrize("sample_id", IDS)
def test_load_sample_adds_hints(sample_id):
    snap = load_sample(sample_id)
    hints = sample_hints(sample_id)
    assert snap.status == "mock" and snap.source == "sample" and snap.persona == sample_id
    assert snap.age == hints["age"] and snap.is_student == hints["is_student"]
    assert snap.housing == hints["housing"]
    assert snap.student_loan_plan == hints["student_loan_plan"]
    assert {s.kind for s in snap.income_sources} == EXPECTED_KINDS[sample_id]
    for h in hints["income_sources"]:
        merged = next(s for s in snap.income_sources if s.kind == h["kind"] and set(h["dates"]) <= set(s.dates))
        assert merged.next_date == h["next_date"]
    assert {d.kind for d in snap.debts} == {d["kind"] for d in hints["debts"]}
    expected = sum(t.amount for t in snap.transactions) + _opening(sample_id)
    assert snap.accounts[0].balance == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize("sample_id", IDS)
@pytest.mark.parametrize("fmt", ["csv", "pdf"])
def test_sample_balance_matches_pdf_closing_balance(sample_id, fmt):
    pdf = parse_statement((SAMPLES / f"{sample_id}.pdf").read_bytes(), "x.pdf")
    assert pdf.balance_known
    closing = pdf.accounts[0].balance
    snap = load_sample(sample_id, fmt)
    accounts = {a.id: a for a in snap.accounts}
    assert accounts["monzo_current"].balance == closing != 0
    hint_ids = {a["id"] for a in sample_hints(sample_id)["accounts"]}
    assert set(accounts) == hint_ids
    if "monzo_savings" in accounts:
        assert accounts["monzo_savings"].kind == "savings" and accounts["monzo_savings"].balance > 0


def test_plain_csv_import_still_asks_for_balance():
    p = parse_statement((SAMPLES / "rich.csv").read_bytes(), "rich.csv")
    assert not p.balance_known and p.accounts[0].balance == 0.0
    assert any("Add it on the next screen" in w for w in p.warnings)


def _opening(sample_id: str) -> float:
    gen = _generator()
    return next(make() for make in gen.PROFILES if make().id == sample_id).opening_balance


def _generator():
    spec = importlib.util.spec_from_file_location("gen_statements", REPO / "tools" / "gen_statements.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gen_statements"] = mod  # dataclasses need the module registered
    spec.loader.exec_module(mod)
    return mod


def test_generator_is_deterministic(tmp_path, capsys):
    _generator().build(tmp_path)
    for f in sorted(SAMPLES.iterdir()):
        assert (tmp_path / f.name).read_bytes() == f.read_bytes(), f.name


def test_package_and_demo_copies_identical():
    from lifeline_data.statements.samples import samples_dir

    assert samples_dir() == SAMPLES
    names = sorted(f.name for f in SAMPLES.iterdir() if f.is_file())
    assert names == sorted(f.name for f in DEMO_COPY.iterdir() if f.is_file())
    assert len(names) == 2 * len(IDS) + 1  # CSV + PDF per sample, plus index.json
    for name in names:
        assert (SAMPLES / name).read_bytes() == (DEMO_COPY / name).read_bytes(), name


def test_every_sample_has_a_holder_name():
    """Rooms and circles show the first word of hints.name for a demo account (W4).
    The generator writes the PDF's account holder here, so the names match."""
    names = [sample_hints(i)["name"] for i in IDS]
    for sample_id, name in zip(IDS, names, strict=True):
        assert isinstance(name, str) and name.strip() == name and 0 < len(name) < 24, sample_id
        assert len(name.split(" ")) >= 2, sample_id  # given name first, then family name
    assert len({n.split(" ")[0] for n in names}) == len(names)  # first names are unique across samples


def test_unknown_sample():
    with pytest.raises(KeyError):
        load_sample("nope")


# --- detection rules on small inputs ---------------------------------------------------------


def tx(day: str, amount: float, name: str, desc: str | None = None, cat: str | None = None) -> Transaction:
    return Transaction(id=f"t{day}{amount}{name}", account_id="a", date=day, amount=amount,
                       description=desc or name, merchant=name, provider_category=cat)


def test_job_threshold_and_refunds():
    txs = [tx(f"2026-09-{d:02d}", 300.0, "Acme Ltd", "WAGES") for d in (4, 11, 18, 25)]
    txs += [tx("2026-09-26", 25.0, "Deliveroo", cat="Eating out")]  # refund, not income
    income = detect_income(txs)
    assert [(s.kind, s.schedule, s.next_date) for s in income] == [("salary", "weekly", "2026-10-02")]
    small = detect_income([tx(f"2026-09-{d:02d}", 90.0, "Acme Ltd", "WAGES") for d in (4, 11, 18)])
    assert small[0].kind == "part_time_job"
    assert detect_is_student(txs, income) is None


def test_one_off_and_other_income():
    income = detect_income([tx("2026-09-04", 50.0, "Sam", "pizza money"), tx("2026-09-28", 2000.0, "SLC", "SLC")])
    assert [(s.kind, s.schedule) for s in income] == [("maintenance_loan", "termly")]
    rent_share = [tx(f"2026-{m:02d}-01", 400.0, "Ellie", "rent") for m in (7, 8, 9)]
    assert detect_income(rent_share)[0].kind == "other"


def test_overdraft_from_negative_balance_and_finished_bnpl():
    from datetime import date

    from lifeline_contracts.finance import Account

    acct = [Account(id="c", name="c", kind="current", provider="x", balance=-55.0)]
    debts = detect_debts([], acct, True, date(2026, 10, 16))
    assert debts[0].kind == "overdraft" and debts[0].balance == 55.0 and debts[0].rate_pct is None
    done = [tx(d, -20.0, "Clearpay", "CLEARPAY*BOOHOO") for d in ("2026-06-01", "2026-07-01", "2026-07-31")]
    assert detect_debts(done, [], False, date(2026, 10, 16)) == []


def test_unreadable_pdf_fails_cleanly():
    p = parse_statement(b"%PDF-1.4\n1 0 obj\n<< /Length 5 >>\nstream\nBT ET\nendstream\nendobj\n", "x.pdf")
    assert p.status == "failed" and p.warnings == [PDF_WARNING]
    bomb = b"%PDF-1.4\n<< /Filter /FlateDecode >>\nstream\n" + b"\x78\x9c" + b"\x00" * 50 + b"\nendstream"
    assert parse_statement(bomb, "x.pdf").status == "failed"


# --- PDF reader limits (V6 V2-F1) ------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        b"%PDF-1.4\n" + b"<</FlateDecode>>stream\nXX\nendstream\n" * 200_000,  # each with its own end
        b"%PDF-1.4\n" + b"<</Filter /FlateDecode>>stream\nXX" * 200_000 + b"\nendstream",  # one end for all
        b"%PDF-1.4\n" + b"<</Filter /LZWDecode>>stream\n" * 200_000 + b"\nendstream",
        b"%PDF-1.4\n" + b"<<" * 200_000 + b">>stream\nBT (a) Tj ET\nendstream",
    ],
)
def test_pdf_many_stream_headers_is_linear(content):
    from lifeline_data.statements import pdf as pdf_reader

    start = time.perf_counter()
    rows, _ = pdf_reader.extract_rows(content)
    assert time.perf_counter() - start < 1.0
    assert rows == []


def test_pdf_stream_and_byte_caps():
    from lifeline_data.statements import pdf as pdf_reader

    budget = pdf_reader._Budget(5.0)
    many = b"%PDF-1.4\n" + b"<<>>stream\nBT ET\nendstream\n" * 5_000
    assert len(pdf_reader._streams(many, budget)) == pdf_reader.MAX_STREAM_HEADERS
    big = b"%PDF-1.4\n" + (b"<<>>stream\n" + b"x" * 1_000_000 + b"\nendstream\n") * 12
    assert sum(map(len, pdf_reader._streams(big, budget))) <= pdf_reader.MAX_TOTAL_BYTES


def test_pdf_time_budget_stops_work():
    from lifeline_data.statements import pdf as pdf_reader

    content = b"%PDF-1.4\n<<>>stream\n" + b"BT (01/01/2026) Tj (x) Tj (1.00) Tj ET\n" * 15_000 + b"endstream"
    assert len(pdf_reader.extract_rows(content)[0]) == 15_000
    start = time.perf_counter()
    rows, _ = pdf_reader.extract_rows(content, budget_s=0.0)
    assert time.perf_counter() - start < 0.5 and len(rows) < 15_000


# --- ADR 0062: income does not predict the habit score -------------------------------------------


def _spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    return cov / (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5


def test_habit_score_not_predicted_by_income():
    from datetime import date

    from lifeline_engine.habits import habit_score, monthly_income

    today = date(2026, 10, 17)
    rows = []
    for sample_id in JUDGE_IDS:
        snap = load_sample(sample_id)
        income, score = monthly_income(snap, today), habit_score(snap, today).overall
        assert income is not None and income > 0 and score is not None, sample_id
        rows.append((sample_id, income, score))
    assert len(rows) == 10
    rho = _spearman([r[1] for r in rows], [r[2] for r in rows])
    assert abs(rho) < 0.3, rho
    # At least one lower-income student has a better habit score than a higher-income one.
    assert any(a[1] < b[1] and a[2] > b[2] for a in rows for b in rows)
    by_id = {r[0]: r for r in rows}
    assert by_id["scholarship"][2] > by_id["rich"][2] and by_id["scholarship"][1] < by_id["rich"][1]


def test_international_fx_descriptions():
    snap = _snap("international", "csv")
    wise = [t for t in snap.transactions if t.amount > 0]
    assert len(wise) == 4
    assert all(t.description.startswith("WISE CNY 14,000.00 > GBP AT 0.1") for t in wise)
    for t in wise:
        rate = float(t.description.split(" AT ")[1].split()[0])
        assert t.amount == round(14000 * rate, 2)
