"""'Pick your student' card fields on the sample statements (ADR 0069, ADR 0072). Every number traces to the
statement rows or to the funding figure stored with its source."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from lifeline_contracts.account import SampleStatement
from lifeline_data.statements import list_samples, seed
from lifeline_data.statements.samples import sample_hints

REPO = Path(__file__).resolve().parents[5]
SAMPLES = REPO / "services" / "api" / "lifeline_data" / "statements" / "samples"
INDEX = json.loads((SAMPLES / "index.json").read_text())["samples"]
IDS = seed.IDS
CARD_FIELDS = ("name", "age", "avatar", "uni", "city", "funding_label", "money_in", "housing", "habit_line")
# The app's face art ids (apps/ios/Lifeline/DesignSystem/Icons.swift).
FACES = {"face-girl", "face-boy", "face-teen", "face-teen-hijab", "face-woman-puff", "face-man-beard", "face-priya",
         "face-man-glasses", "face-blue-hair", "face-older-woman", "face-older-man"}
NOT_STUDENTS = {"graduate"}  # graduated: no university on the card


def _rows(sample_id: str) -> list[dict[str, str]]:
    text = (SAMPLES / f"{sample_id}.csv").read_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def _entry(sample_id: str) -> dict[str, object]:
    return next(e for e in INDEX if e["id"] == sample_id)


def _card(sample_id: str) -> SampleStatement:
    return SampleStatement.model_validate({k: v for k, v in _entry(sample_id).items() if k != "hints"})


@pytest.mark.parametrize("sample_id", IDS)
def test_card_fields_present_and_valid(sample_id: str) -> None:
    card = _card(sample_id)
    for f in CARD_FIELDS:
        if f == "uni" and sample_id in NOT_STUDENTS:
            assert card.uni is None
            continue
        assert getattr(card, f), f"{sample_id}: {f} is empty"
    hints = sample_hints(sample_id)
    assert card.name == hints["name"] and card.age == hints["age"]
    assert card.city == hints["town"]
    assert card.avatar in FACES
    for text in (card.funding_label, card.housing, card.habit_line, *(m.dates or "" for m in card.money_in)):
        assert text is not None and "—" not in text and "·" not in text
    if hints["housing"] == "parents":
        assert "home" in (card.housing or "")


@pytest.mark.parametrize("sample_id", IDS)
def test_money_in_matches_statement_rows(sample_id: str) -> None:
    """Each card line is a payment in the statement (or, for a payment not made yet, the first one due)."""
    p = seed.profile(sample_id)
    rows = _rows(sample_id)
    card = _card(sample_id)
    assert len(card.money_in) == len(p.card.money_in)
    for line, (label, stream_id, period, _, divisor, varies) in zip(card.money_in, p.card.money_in, strict=True):
        assert line.label == label and line.period == period
        stream = next(s for s in p.streams if s.id == stream_id)
        paid = [float(r["Amount"]) for r in rows if r["Description"] == stream.description and float(r["Amount"]) > 0]
        if period == "year":
            assert line.amount == pytest.approx(sum(stream.amounts), abs=0.01)
        elif varies:
            assert line.amount == pytest.approx(sum(paid[-4:]) / len(paid[-4:]), abs=0.01)
            assert "varies" in (line.dates or "")
        elif paid:
            assert line.amount == pytest.approx(paid[-1] / divisor, abs=0.01)
        else:
            assert line.amount == stream.amounts[0] and "late" in (line.dates or "")


HABIT_WORDS = seed.HABIT_WORDS


@pytest.mark.parametrize("sample_id", IDS)
def test_habit_line_is_true_for_the_statement(sample_id: str) -> None:
    p, rows, _ = seed.statement(sample_id, seed.REF_END)
    line = str(_entry(sample_id)["habit_line"])
    spend: dict[str, float] = {}
    for t in rows:
        if t.amount < 0 and t.kind in (seed.SPEND, seed.ONE_OFF, seed.BNPL):
            spend[t.category] = spend.get(t.category, 0.0) - t.amount
    top = max(spend, key=lambda c: spend[c])
    assert f"spends most on {HABIT_WORDS[top]};" in line, (sample_id, line)
    saved = -sum(t.amount for t in rows if t.kind == seed.SAVINGS)
    if "overdraft" in line:
        assert min(t.balance for t in rows) < 0
    elif saved > 0:
        assert f"saved £{saved:,.0f} since July" in line
    elif "Klarna" in line:
        assert any(t.name == "Klarna" for t in rows)
    else:
        assert line.endswith("no savings yet")


def test_api_listing_carries_the_card() -> None:
    judge = list_samples()
    assert all(s.money_in and s.habit_line and s.avatar for s in judge)
    assert len({s.name for s in judge}) == len(judge)
