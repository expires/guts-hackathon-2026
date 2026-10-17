from __future__ import annotations

from lifeline_contracts.domain import Concept
from lifeline_contracts.macro import MacroTable
from lifeline_sim import api


def test_presets() -> None:
    ids = {c.id for c in api.presets()}
    assert {"nurse-leeds", "banker-london", "student", "plumber", "pensioner", "teacher-glasgow"} <= ids
    nurse = next(c for c in api.presets() if c.id == "nurse-leeds")
    assert (nurse.town, nurse.annual_income, nurse.birth_year) == ("Leeds", 24800.0, 1982)


def test_god_mode_options() -> None:
    opts = api.god_mode_options()
    assert "banker" in opts["occupations"] and "scotland" in opts["regions"]


def _check_concept(c: Concept) -> None:
    assert c.lesson.concept_id == c.id
    assert len(c.lesson.sentences) == 2
    assert all(s.endswith(".") for s in c.lesson.sentences)
    assert 0 <= c.lesson.quiz.answer_index < len(c.lesson.quiz.options)


def test_concepts_without_macro() -> None:
    cs = api.concepts()
    assert len(cs) >= 8
    assert len({c.id for c in cs}) == len(cs)
    for c in cs:
        _check_concept(c)


def test_concepts_with_macro_have_charts(macro: MacroTable) -> None:
    for c in api.concepts(macro):
        _check_concept(c)
        assert c.lesson.chart.points, c.id
        assert c.lesson.chart.source is not None


def test_challenges() -> None:
    cs = api.challenges()
    assert {"home-by-30", "survive-2008"} <= {c.id for c in cs}
    preset_ids = {p.id for p in api.presets()}
    assert all(c.character_id in preset_ids for c in cs)
