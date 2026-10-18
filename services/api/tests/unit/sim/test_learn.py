"""Learn course content and logic (ADR 0068)."""

from __future__ import annotations

from collections import Counter
from urllib.parse import urlparse

import pytest

from lifeline_contracts.learn import LessonCard, LessonChoice, LessonQuestion
from lifeline_engine import rules
from lifeline_sim import learn
from lifeline_sim.concepts import concept_ids
from lifeline_sim.learn_content import LOCKED_REASON, NEW_LESSONS, UNIT_TEXT, UNITS, LessonSpec

ALL = [lesson for u in UNITS for lesson in u.lessons]
DASHES = ("—", "–")


def test_six_units_in_lifecycle_order() -> None:
    assert [u.title for u in UNITS] == [
        "Money basics", "Student money", "Staying safe", "Making money grow", "After uni", "The bigger picture",
    ]
    assert all(u.lessons for u in UNITS)


def test_ids_unique() -> None:
    ids = [lesson.id for lesson in ALL] + [u.id for u in UNITS]
    assert len(ids) == len(set(ids))


# Lessons removed from the path because they do not fit students (homeowner or later-life topics). Their Life game
# concepts stay in the game but are no longer taught on the path.
REMOVED_LESSONS = (
    "depreciation", "fuel-costs", "house-prices", "remortgaging", "negative-equity", "flood-risk", "home-security",
    "divorce-costs", "inheritance",
)
OFF_PATH_CONCEPTS = frozenset(REMOVED_LESSONS)


def test_every_path_concept_exists_and_is_placed_once() -> None:
    placed = Counter(lesson.concept for lesson in ALL if lesson.concept is not None)
    assert set(placed) <= set(concept_ids())
    assert all(n == 1 for n in placed.values())
    assert len(concept_ids()) == 50
    assert set(concept_ids()) - set(placed) == OFF_PATH_CONCEPTS


def test_lesson_counts_per_unit() -> None:
    assert [len(u.lessons) for u in UNITS] == [6, 7, 9, 8, 10, 8]
    assert len(learn.lesson_ids()) == 48
    assert not set(REMOVED_LESSONS) & set(learn.lesson_ids())


def test_stored_progress_with_removed_lessons_is_ignored() -> None:
    ids = learn.lesson_ids()
    stored = [*ids[:3], *REMOVED_LESSONS]
    path = learn.build_path(stored)
    assert path.done == 3 and path.total == len(ids) and path.next_lesson_id == ids[3]
    assert sum(u.done for u in path.units) == 3
    assert [s.index for s in path.units[-1].lessons] == list(range(len(path.units[-1].lessons)))
    res, after = learn.grade(ids[3], {}, stored)
    assert not res.passed and after == ids[:3]
    for gone in REMOVED_LESSONS:
        assert not learn.has_lesson(gone)
        with pytest.raises(KeyError):
            learn.build_lesson(gone, stored)


def test_new_student_lessons_exist() -> None:
    ids = {lesson.id for lesson in ALL}
    assert set(NEW_LESSONS) <= ids and len(NEW_LESSONS) == 9


@pytest.mark.parametrize("lesson", ALL, ids=[lesson.id for lesson in ALL])
def test_lesson_rules(lesson: LessonSpec) -> None:
    assert 2 <= len(lesson.cards) <= 3
    for title, text in lesson.cards:
        LessonCard(title=title, text=text)  # length limits
    assert 1 <= len(lesson.facts) <= 3
    assert len(lesson.quiz) == 3
    for q in lesson.quiz:
        assert 2 <= len(q.choices) <= 4 and 0 <= q.answer < len(q.choices)
        assert len(set(q.choices)) == len(q.choices), "one correct answer needs distinct choices"
        assert 0 < len(q.why) <= 200
        LessonQuestion(id="q0", text=q.text, choices=[LessonChoice(id="a", text=c) for c in q.choices])
    texts = [lesson.title, *(t for c in lesson.cards for t in c), *(f.text for f in lesson.facts),
             *(q.text for q in lesson.quiz), *(c for q in lesson.quiz for c in q.choices),
             *(q.why for q in lesson.quiz)]
    assert not any(d in t for t in texts for d in DASHES), "no em or en dashes"
    assert lesson.icon and " " not in lesson.icon


@pytest.mark.parametrize("lesson", ALL, ids=[lesson.id for lesson in ALL])
def test_facts_trace_to_the_facts_table(lesson: LessonSpec) -> None:
    for f in lesson.facts:
        rule = rules.get(f.rule)
        assert urlparse(rule.url).hostname in rules.OFFICIAL_DOMAINS
        assert learn.format_value(rule) in f.text, f"{f.rule}: the text must show the rule value"
    full = learn.build_lesson(lesson.id, learn.lesson_ids())
    assert full.facts and all(urlparse(f.source_url).hostname in rules.OFFICIAL_DOMAINS for f in full.facts)
    assert all(f.checked for f in full.facts)


def test_translations_cover_every_unit() -> None:
    assert set(LOCKED_REASON) == set(learn.LANGUAGES)
    for lang, units in UNIT_TEXT.items():
        assert lang in learn.LANGUAGES
        assert set(units) == {u.id for u in UNITS}


def test_no_locks_but_order_kept() -> None:
    """PENNY_V3_BUILD.md E1: every lesson is open; the path keeps the order and next_lesson_id."""
    ids = learn.lesson_ids()
    path = learn.build_path([])
    flat = [s for u in path.units for s in u.lessons]
    assert all(s.status == "open" and s.locked_reason is None for s in flat)
    assert path.next_lesson_id == ids[0] and path.done == 0 and path.total == len(ids)
    # The first lesson of unit 2 opens when the last lesson of unit 1 is passed.
    unit1 = [s.id for s in path.units[0].lessons]
    path = learn.build_path(unit1)
    assert path.units[0].done == path.units[0].total
    assert path.units[1].lessons[0].status == "open" and path.next_lesson_id == path.units[1].lessons[0].id


def test_life_bonus_does_not_pass_a_lesson() -> None:
    path = learn.build_path([], bonus={"pensions"})
    pensions = next(s for u in path.units for s in u.lessons if s.concept_id == "pensions")
    assert pensions.life_bonus and pensions.status == "open"


def test_grade() -> None:
    first = learn.lesson_ids()[0]
    spec = ALL[0]
    right = {f"q{i}": "abcd"[q.answer] for i, q in enumerate(spec.quiz)}
    wrong = {k: ("b" if v == "a" else "a") for k, v in right.items()}
    res, after = learn.grade(first, wrong, [])
    assert not res.passed and res.correct == 0 and after == []
    one = {"q0": right["q0"], "q1": wrong["q1"], "q2": wrong["q2"]}
    res, after = learn.grade(first, one, [])
    assert not res.passed and res.correct == 1 and res.unlocked_lesson_id is None
    two = {"q0": right["q0"], "q1": right["q1"], "q2": wrong["q2"]}
    res, after = learn.grade(first, two, [])
    assert res.passed and res.correct == 2 and after == [first]
    assert res.unlocked_lesson_id == learn.lesson_ids()[1]
    res, _ = learn.grade(first, right, after)
    assert res.passed and res.unlocked_lesson_id is None  # already passed


def test_language_fallback() -> None:
    assert learn.language_of("xx") == "en"
    fr = learn.build_path([], language="fr")
    assert fr.units[0].title == "Les bases de l'argent"
    assert learn.build_path([], language="xx").units[0].title == "Money basics"
    assert learn.build_lesson(learn.lesson_ids()[0], [], language="fr").cards[0].title == ALL[0].cards[0][0]


# ADR 0068: each lesson cites a fact on its own topic. Lessons with no matching fact in the facts table yet use the
# closest general fact and are listed here, so a new fact can replace them later.
LOOSE_FACT_LESSONS: set[str] = set()
RELEVANT = {
    "inflation": "rule.boe_inflation_target", "emergency-fund": "rule.fscs_deposit_limit",
    "price-cap": "rule.ofgem_price_cap_typical_bill", "energy-bills": "rule.ofgem_price_cap_typical_bill",
    "crypto-risk": "rule.fscs_deposit_limit", "health-cost": "rule.ssp_weekly",
    "income-protection": "rule.ssp_weekly", "pensions": "rule.auto_enrolment_total_min",
    "pay-growth": "rule.national_living_wage", "job-security": "rule.uc_standard_single_25_plus",
    "interest-rates": "rule.boe_bank_rate", "fixed-vs-variable": "rule.boe_bank_rate",
    "benefits": "rule.uc_standard_single_25_plus",
    "state-pension": "rule.state_pension_full_weekly", "redundancy": "rule.redundancy_pay_max",
    "childcare": "rule.tax_free_childcare_max", "subscriptions": "rule.distance_cancel_days",
    "overdrafts": "rule.fca_overdraft_simple_rate_year", "buy-now-pay-later": "rule.fca_bnpl_regulated_year",
    "insurance": "rule.fscs_general_insurance_share",
    "deposit": "rule.sdlt_first_time_buyer_threshold", "student-loans": "rule.maintenance_loan_max_away_england",
}


def test_lessons_cite_a_fact_on_their_topic() -> None:
    by_id = {lesson.id: lesson for lesson in ALL}
    assert not LOOSE_FACT_LESSONS and set(by_id) >= set(RELEVANT)
    for lesson_id, rule_id in RELEVANT.items():
        assert rule_id in {rules.get(f.rule).id for f in by_id[lesson_id].facts}, lesson_id


def test_format_value_keeps_pence() -> None:
    assert learn.format_value(rules.get("national_living_wage")) == "£12.71"
    assert learn.format_value(rules.get("state_pension_full_weekly")) == "£241.30"
    assert learn.format_value(rules.get("isa_allowance")) == "£20,000"
