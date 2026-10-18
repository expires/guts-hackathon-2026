"""ADR 0069: Move.reason, Move.confidence_text and NextMoveResponse.options_compared. Pure, no network."""

from __future__ import annotations

from datetime import date

import pytest

from lifeline_contracts.finance import FinanceSnapshot
from lifeline_contracts.macro import MacroTable
from lifeline_contracts.next_move import Move, NextMoveResponse
from lifeline_engine.money.text import unsupported_numbers
from lifeline_engine.next_move import BUILDERS, build_context, built, next_move
from lifeline_engine.wording import LEVEL_WORDS, confidence_sentence

from .finance_builders import homeowner

TODAY = date(2026, 10, 17)


@pytest.mark.parametrize(
    ("args", "text"),
    [
        (("medium", 4, "weeks of your spending"), "Medium confidence: based on your last 4 weeks of spending"),
        (("low", 2, "weeks of your spending"), "Low confidence: only 2 weeks of spending so far"),
        (("high", 9, "past years"), "High confidence: based on 9 similar past years in UK data"),
        (("low", 3, "past periods"), "Low confidence: only 3 similar past periods in UK data to compare"),
        (("low", 6, "past years"), "Low confidence: mixed results in 6 similar past years in UK data"),
        (("low", 1, "months"), "Low confidence: only 1 month of spending so far"),
        (("medium", 6, "months"), "Medium confidence: based on your last 6 months of spending"),
        (("high", None, "", "the price is on your own statement"),
         "High confidence: the price is on your own statement"),
        (("low", None, ""), "Low confidence: little data to compare yet"),
        ((None, None, ""), "No rating: nothing in your data needs action now"),
    ],
)
def test_confidence_sentence(args: tuple, text: str) -> None:  # type: ignore[type-arg]
    assert confidence_sentence(*args) == text


def _snapshots() -> list[FinanceSnapshot]:
    snaps = [homeowner()]
    statements = pytest.importorskip("lifeline_data.statements")
    snaps += [statements.load_sample(s.id) for s in statements.list_samples()]
    return snaps


def _check_move(m: Move) -> None:
    assert m.reason and m.confidence_text, m.kind
    for text in (m.reason, m.confidence_text):
        assert len(text) <= 140
        assert "\u2014" not in text and "\u00b7" not in text and "sample" not in text.lower()
    if m.confidence_level is not None:
        assert m.confidence_text.startswith(LEVEL_WORDS[m.confidence_level] + ":")
    facts = {k: v for e in m.evidence for k, v in e.facts.items()}
    facts["move_impact"] = m.impact_per_year
    if m.days_left is not None:
        facts["days_left"] = float(m.days_left)
    assert unsupported_numbers(m.reason, facts) == [], m.reason
    if m.sample_size is not None and m.confidence_level is not None and m.kind not in ("cancel_subscription",
                                                                                         "lifetime_isa"):
        assert str(m.sample_size) in m.confidence_text


def test_every_move_has_reason_and_plain_confidence(macro: MacroTable) -> None:
    seen: set[str] = set()
    for snap in _snapshots():
        r: NextMoveResponse = next_move(snap, macro, TODAY)
        for m in [r.top, *r.runners_up]:
            _check_move(m)
            seen.add(m.kind)
    assert {"weekly_budget", "build_emergency_fund", "fix_mortgage"} <= seen


def test_options_compared_counts_every_built_candidate(macro: MacroTable) -> None:
    for snap in _snapshots():
        r = next_move(snap, macro, TODAY)
        evaluated = built(build_context(snap, macro, TODAY))
        assert r.options_compared == max(len(evaluated), 1 + len(r.runners_up))
        assert 1 + len(r.runners_up) <= r.options_compared <= len(BUILDERS)


def test_homeowner_compares_more_than_it_shows(macro: MacroTable) -> None:
    r = next_move(homeowner(), macro, TODAY)
    assert r.options_compared >= 1 + len(r.runners_up)
    assert r.top.reason is not None and "165 days" in r.top.reason
