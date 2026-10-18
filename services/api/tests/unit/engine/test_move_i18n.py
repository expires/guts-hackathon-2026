"""Next-move text in the 8 app languages (ADR 0069 point 8). Fixed tables, no network, numbers unchanged."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

import pytest

from lifeline_contracts.macro import MacroTable
from lifeline_contracts.next_move import Move, NextMoveResponse
from lifeline_engine import move_i18n as i18n
from lifeline_engine.next_move import next_move

TODAY = date(2026, 10, 17)
STUDENTS = ("scholarship", "scottish", "commuter", "loan_england", "working", "mature", "international",
            "final_year", "rich", "graduate")
NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
MONEY = re.compile(r"£\d+(?:,\d{3})*(?:\.\d+)?")
ALL_ROWS = [*i18n.SENTENCES, *(r for rows in i18n.KINDS.values() for r in rows)]


def _names(template: str) -> dict[str, str | None]:
    return {m.group(1): m.group(2) for m in i18n._PH.finditer(template)}


def test_every_template_has_all_8_languages() -> None:
    assert len(i18n.LANGS) == 8
    for row in ALL_ROWS:
        assert len(row) == len(i18n.LANGS), row[0]
        assert all(text.strip() for text in row), row[0]
        english = _names(row[0])
        for text in row[1:]:
            assert set(_names(text)) == set(english), (row[0], text)
            assert all(kind is None for kind in _names(text).values()), (row[0], text)
        assert all(k is None or k == "*" or k in i18n.KINDS for k in english.values()), row[0]
        assert "—" not in "".join(row), row[0]


def _example(template: str, kinds_seen: tuple[str, ...] = ()) -> str:
    """An English text for the template: numbers for copied parts, the first phrase of each kind."""
    def fill(m: re.Match[str]) -> str:
        kind = m.group(2)
        if kind is None:
            return "£1,234"
        if kind == "*":
            return "Based on your own numbers"
        return _example(i18n.KINDS[kind][-1 if kind == "dnames" else 0][0], (*kinds_seen, kind))
    return i18n._PH.sub(fill, template)


@pytest.mark.parametrize("lang", i18n.LANGS[1:])
def test_every_template_translates_itself(lang: str) -> None:
    for row in i18n.SENTENCES:
        text = _example(row[0])
        done = i18n.translate_text(text, lang)
        assert done is not None, (lang, text)
        assert Counter(MONEY.findall(done)) == Counter(MONEY.findall(text)), (lang, text, done)


def test_unknown_language_falls_back_to_english() -> None:
    assert i18n.language_of("xx") == "en" and i18n.language_of(None) == "en"
    text = "Your energy price can go up"
    assert i18n.translate_text(text, "xx") == text
    assert i18n.translate_text(text, "en") == text
    assert i18n.translate_text("Something the engine never says", "fr") is None


def _samples(macro: MacroTable) -> list[NextMoveResponse]:
    statements = pytest.importorskip("lifeline_data.statements")
    return [next_move(statements.load_sample(sid), macro, TODAY) for sid in STUDENTS]


def _texts(m: Move) -> list[str]:
    out = [m.action, m.headline, m.confidence_label, *(o.label for o in m.options), *(e.text for e in m.evidence)]
    out += [t for t in (m.reason, m.confidence_text, m.test_period.label if m.test_period else None) if t]
    if m.trade_off:
        out += [m.trade_off.summary, *(p.text for p in m.trade_off.points)]
    return out


@pytest.mark.parametrize("lang", ["hi", "zh-Hans"])
def test_sample_responses_have_no_english_template_left(macro: MacroTable, lang: str) -> None:
    for resp in _samples(macro):
        done = i18n.translate_response(resp, lang)
        for en_move, tr_move in zip([resp.top, *resp.runners_up], [done.top, *done.runners_up], strict=True):
            assert i18n.untranslated(_texts(en_move), lang) == [], en_move.kind
            for en, tr in zip(_texts(en_move), _texts(tr_move), strict=True):
                assert tr != en, (lang, en)
                assert not re.search(r"\b(?:you|your|the|and|a month|a year|weeks?)\b", tr, re.IGNORECASE), tr
                assert Counter(MONEY.findall(tr)) == Counter(MONEY.findall(en)), (en, tr)
                assert set(NUMBER.findall(en)) <= set(NUMBER.findall(tr)), (en, tr)
            # Everything that is not text stays the same.
            keep = {"action", "headline", "reason", "confidence_text", "confidence_label", "evidence", "options",
                    "test_period", "trade_off"}
            assert tr_move.model_dump(exclude=keep) == en_move.model_dump(exclude=keep)
            assert [e.facts for e in tr_move.evidence] == [e.facts for e in en_move.evidence]


@pytest.mark.parametrize("lang", i18n.LANGS[1:])
def test_sample_translations_fit_the_contract(macro: MacroTable, lang: str) -> None:
    """No translation is too long for its field, so no field falls back to English."""
    for resp in _samples(macro):
        for m in [resp.top, *resp.runners_up]:
            for text, limit in ((m.reason, 140), (m.confidence_text, 140),
                                (m.trade_off.summary if m.trade_off else None, 90)):
                if text:
                    done = i18n.translate_text(text, lang)
                    assert done is not None and len(done) <= limit, (lang, text, done)
        NextMoveResponse.model_validate(i18n.translate_response(resp, lang).model_dump())


def test_english_is_unchanged(macro: MacroTable) -> None:
    resp = _samples(macro)[0]
    assert i18n.translate_response(resp, "en") is resp
    assert i18n.translate_response(resp, "xx") is resp
