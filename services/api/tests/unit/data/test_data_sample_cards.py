"""'Pick your student' card fields on the sample statements (ADR 0069). Every number traces to the CSV rows."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from lifeline_contracts.account import SampleStatement
from lifeline_data.statements import list_samples
from lifeline_data.statements.samples import sample_hints

REPO = Path(__file__).resolve().parents[5]
SAMPLES = REPO / "services" / "api" / "lifeline_data" / "statements" / "samples"
INDEX = json.loads((SAMPLES / "index.json").read_text())["samples"]
# The 10 sample students (ADR 0070).
IDS = ["scholarship", "scottish", "commuter", "loan_england", "working", "mature", "international", "final_year",
       "rich", "graduate"]
CARD_FIELDS = ("name", "age", "avatar", "uni", "city", "funding_label", "money_in", "housing", "habit_line")
# The app's face art ids (apps/ios/Lifeline/DesignSystem/Icons.swift).
FACES = {"face-girl", "face-boy", "face-teen", "face-teen-hijab", "face-woman-puff", "face-man-beard", "face-priya",
         "face-man-glasses", "face-blue-hair", "face-older-woman", "face-older-man"}
NOT_STUDENTS = {"graduate"}  # graduated: no university on the card
# Rows behind each card line: (label, CSV description text, pay changes week to week).
ROWS: dict[tuple[str, str], tuple[str, bool]] = {
    ("scholarship", "Scholarship"): ("SCHOLARSHIP LIVING ALLOWANCE", False),
    ("scholarship", "University bursary"): ("SHEFFIELD BURSARY MONTHLY", False),
    ("scottish", "SAAS loan"): ("SAAS LOAN INSTALMENT", False),
    ("scottish", "Young Students' Bursary"): ("SAAS YOUNG STUDENTS BURSARY", False),
    ("scottish", "Fringe bar job"): ("WAGES", True),
    ("commuter", "Access grant"): ("ACCESS GRANT TERM 1", False),
    ("commuter", "Mum"): ("Mum - train money", False),
    ("loan_england", "Maintenance loan"): ("SLC MAINTENANCE LOAN", False),
    ("working", "Maintenance loan"): ("SLC MAINTENANCE LOAN", False),
    ("working", "Bar job"): ("JDW WAGES", True),
    ("mature", "Maintenance loan"): ("SLC MAINTENANCE LOAN", False),
    ("mature", "NHS Learning Support Fund"): ("NHS LEARNING SUPPORT FUND GRANT", False),
    ("mature", "NHS bank shifts"): ("NHSP PAYROLL BANK SHIFTS", True),
    ("international", "Parents (by Wise)"): ("FAMILY SUPPORT FROM LI WEI", False),
    ("final_year", "Summer internship"): ("SALARY SUMMER INTERN", False),
    ("final_year", "Maintenance loan"): ("SLC MAINTENANCE LOAN", False),
    ("rich", "Parents"): ("ALLOWANCE FROM DAD", False),
    ("graduate", "Graduate salary"): ("SALARY GRADUATE SCHEME", False),
}


def _rows(sample_id: str) -> list[dict[str, str]]:
    text = (SAMPLES / f"{sample_id}.csv").read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def _entry(sample_id: str) -> dict[str, object]:
    return next(e for e in INDEX if e["id"] == sample_id)


@pytest.mark.parametrize("sample_id", IDS)
def test_card_fields_present_and_valid(sample_id: str) -> None:
    entry = _entry(sample_id)
    card = SampleStatement.model_validate({k: v for k, v in entry.items() if k != "hints"})
    for f in CARD_FIELDS:
        if f == "uni" and sample_id in NOT_STUDENTS:
            assert card.uni is None
            continue
        assert getattr(card, f), f"{sample_id}: {f} is empty"
    hints = sample_hints(sample_id)
    assert card.name == hints["name"] and card.age == hints["age"]
    assert card.avatar in FACES
    for text in (card.funding_label, card.housing, card.habit_line, *(m.dates or "" for m in card.money_in)):
        assert text is not None and "\u2014" not in text and "\u00b7" not in text
    if hints["housing"] == "parents":
        assert "home" in (card.housing or "")


@pytest.mark.parametrize("sample_id", IDS)
def test_money_in_matches_statement_rows(sample_id: str) -> None:
    rows = _rows(sample_id)
    card = SampleStatement.model_validate({k: v for k, v in _entry(sample_id).items() if k != "hints"})
    assert card.money_in, sample_id
    for line in card.money_in:
        match, varies = ROWS[(sample_id, line.label)]
        paid = [float(r["Amount"]) for r in rows
                if float(r["Amount"]) > 0 and match.upper() in r["Description"].upper()]
        assert paid, (sample_id, line.label)
        if varies:
            assert line.amount == pytest.approx(sum(paid[-4:]) / len(paid[-4:]), abs=0.01)
            assert "varies" in (line.dates or "")
        else:
            assert line.amount == paid[-1], (sample_id, line.label)  # exactly as the statement shows it


@pytest.mark.parametrize("sample_id", IDS)
def test_income_amounts_agree_with_hints(sample_id: str) -> None:
    """Fixed income lines on the card are the same payments the engine reads from hints.income_sources."""
    card = SampleStatement.model_validate({k: v for k, v in _entry(sample_id).items() if k != "hints"})
    hinted = {round(float(s["amount"]), 2) for s in sample_hints(sample_id)["income_sources"]}
    for line in card.money_in:
        if not ROWS[(sample_id, line.label)][1]:
            assert round(line.amount, 2) in hinted, (sample_id, line.label)


HABIT_WORDS = {"Eating out": "eating out", "Groceries": "food shopping", "Entertainment": "nights out and fun",
               "Transport": "travel", "Shopping": "shopping", "Holidays": "holidays",
               "Personal care": "the gym and personal care"}


@pytest.mark.parametrize("sample_id", IDS)
def test_habit_line_is_true_for_the_statement(sample_id: str) -> None:
    rows = _rows(sample_id)
    line = str(_entry(sample_id)["habit_line"])
    spend: dict[str, float] = {}
    for r in rows:
        amt = float(r["Amount"])
        if amt < 0 and r["Category"] not in {"Bills", "Income", "Savings"} and r["Type"] != "Pot transfer":
            spend[r["Category"]] = spend.get(r["Category"], 0.0) - amt
    top = max(spend, key=lambda c: spend[c])
    assert f"spends most on {HABIT_WORDS[top]};" in line, (sample_id, line)
    saved = -sum(float(r["Amount"]) for r in rows
                 if float(r["Amount"]) < 0 and (r["Type"] == "Pot transfer" or r["Category"] == "Savings"))
    if "overdraft" in line:
        assert min(_balances(sample_id)) < 0
    elif saved > 0:
        assert f"saved £{saved:,.0f} in 3 months" in line
    elif "Klarna" in line:
        assert any(r["Name"] == "Klarna" for r in rows)
    else:
        assert line.endswith("no savings yet")


def _balances(sample_id: str) -> list[float]:
    """Balance after each CSV row. The CSV has no balance column: walk back from the closing balance hint."""
    rows = _rows(sample_id)
    bal = float(next(a["balance"] for a in sample_hints(sample_id)["accounts"] if a["kind"] == "current"))
    out = []
    for r in reversed(rows):
        out.append(bal)
        bal -= float(r["Amount"])
    return out


def test_api_listing_carries_the_card() -> None:
    judge = list_samples()
    assert all(s.money_in and s.habit_line and s.avatar for s in judge)
    assert len({s.name for s in judge}) == len(judge)
