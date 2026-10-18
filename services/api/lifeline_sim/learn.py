"""Learn course logic (ADR 0068). Pure: no I/O, no clock, no RNG.

The path is one ordered list of lessons across six units. A lesson is `passed` when the user passed its quiz,
`open` when it is the first lesson or the lesson before it is passed, else `locked`. A Life game bonus
(`life_bonus`) never opens a lesson. The quiz is graded here, so answers never reach the client before an attempt.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from functools import cache

from lifeline_contracts.learn import (
    LearnLesson,
    LearnPath,
    LessonAnswerResult,
    LessonAttemptResult,
    LessonCard,
    LessonChoice,
    LessonFact,
    LessonQuestion,
    LessonStatus,
    LessonSummary,
    Unit,
)
from lifeline_engine import rules
from lifeline_sim.learn_content import LOCKED_REASON, UNIT_TEXT, UNITS, LessonSpec, UnitSpec

LANGUAGES: tuple[str, ...] = ("en", "fr", "es", "pt", "it", "zh-Hans", "hi", "ne")
PASS_MARK = 2
CHOICE_IDS = ("a", "b", "c", "d")
SAMPLE_PASSED = 4  # lessons a sample student starts with (ADR 0068)

SOURCE_LABELS: dict[str, str] = {
    rules.URL_INCOME_TAX: "gov.uk · Income Tax rates and allowances",
    rules.URL_EMPLOYERS: "gov.uk · Rates and thresholds for employers 2026 to 2027",
    rules.URL_ISA: "gov.uk · Individual Savings Accounts",
    rules.URL_LISA: "gov.uk · Lifetime ISA",
    rules.URL_LISA_WHO: "gov.uk · Who can open a Lifetime ISA",
    rules.URL_LISA_WITHDRAW: "gov.uk · Withdrawing from your Lifetime ISA",
    rules.URL_JISA: "gov.uk · Junior Individual Savings Accounts",
    rules.URL_STUDENT_LOAN_PAY: "gov.uk · Repaying your student loan",
    rules.URL_SFE_PAID: "gov.uk · Student finance: how you're assessed and paid",
    rules.URL_SFW: "Student Finance Wales · Terms and conditions 2026/27",
    rules.URL_SFNI: "Student Finance NI · Terms and conditions 2026/27",
    rules.URL_SAAS: "SAAS · Living-cost loan",
    rules.URL_COUNCIL_TAX_STUDENTS: "gov.uk · Council Tax discounts for students",
    rules.URL_COUNCIL_TAX_WHO: "gov.uk · Who has to pay Council Tax",
    rules.URL_RAILCARD: "16-25 Railcard",
    rules.URL_HESA_SB273_FIG7: "HESA · Where students come from",
    rules.URL_BOE_INFLATION: "Bank of England · Inflation and the 2% target",
    rules.URL_BOE_BANK_RATE: "Bank of England · Interest rates and Bank Rate",
    rules.URL_FSCS: "FSCS · Check your money is protected",
    rules.URL_SSP: "gov.uk · Statutory Sick Pay",
    rules.URL_STATE_PENSION: "gov.uk · The new State Pension: what you'll get",
    rules.URL_WORKPLACE_PENSION: "gov.uk · Workplace pensions: what you and your employer pay",
    rules.URL_MIN_WAGE: "gov.uk · National Minimum Wage and National Living Wage rates",
    rules.URL_UNIVERSAL_CREDIT: "gov.uk · Universal Credit: what you'll get",
    rules.URL_REDUNDANCY: "gov.uk · Redundancy pay",
    rules.URL_TAX_FREE_CHILDCARE: "gov.uk · Tax-Free Childcare",
    rules.URL_FREE_CHILDCARE: "gov.uk · 30 hours free childcare",
    rules.URL_OFGEM_CAP_OCT_2026: "Ofgem · Energy price cap from 1 October 2026",
    rules.URL_SFE_NEW_FULLTIME: "gov.uk · Student finance for new full-time students",
    rules.URL_INHERITANCE_TAX: "gov.uk · Inheritance Tax",
    rules.URL_SDLT_RATES: "gov.uk · Stamp Duty Land Tax: residential rates",
    rules.URL_DISTANCE_SELLING: "gov.uk · Online and distance selling",
    rules.URL_FCA_OVERDRAFT_CHARGES: "FCA · Changes to overdraft charges",
    rules.URL_FCA_BNPL: "FCA · Buy Now Pay Later",
    rules.URL_FSCS_INSURANCE: "FSCS · Insurance protection",
}


@dataclass(frozen=True)
class _Entry:
    unit: UnitSpec
    index: int  # position in the unit
    spec: LessonSpec


@cache
def _flat() -> tuple[_Entry, ...]:
    return tuple(_Entry(u, i, lesson) for u in UNITS for i, lesson in enumerate(u.lessons))


@cache
def _by_id() -> dict[str, int]:
    return {e.spec.id: n for n, e in enumerate(_flat())}


def lesson_ids() -> list[str]:
    """Every lesson id in path order."""
    return [e.spec.id for e in _flat()]


def sample_passed() -> list[str]:
    """The lessons a sample student starts with."""
    return lesson_ids()[:SAMPLE_PASSED]


def concept_lessons() -> dict[str, str]:
    """Life concept id -> lesson id."""
    return {e.spec.concept: e.spec.id for e in _flat() if e.spec.concept is not None}


def language_of(language: str | None) -> str:
    """A supported language, else English."""
    return language if language in LANGUAGES else "en"


def format_value(fact: rules.RuleFact) -> str:
    """The rule value as it must appear in a fact text."""
    if fact.unit in ("gbp", "gbp_per_month", "gbp_per_year"):
        return f"£{fact.value:,.0f}" if float(fact.value).is_integer() else f"£{fact.value:,.2f}"
    if fact.unit == "percent":
        return f"{fact.value:g}%"
    return f"{fact.value:g}"


def _status(n: int, passed: Collection[str]) -> LessonStatus:
    flat = _flat()
    if flat[n].spec.id in passed:
        return "passed"
    if n == 0 or flat[n - 1].spec.id in passed:
        return "open"
    return "locked"


def _summary(n: int, passed: Collection[str], bonus: Collection[str], language: str) -> LessonSummary:
    e = _flat()[n]
    status = _status(n, passed)
    reason = None
    if status == "locked":
        reason = LOCKED_REASON[language].format(title=_flat()[n - 1].spec.title)[:120]
    return LessonSummary(
        id=e.spec.id, unit_id=e.unit.id, index=e.index, title=e.spec.title, icon=e.spec.icon, status=status,
        locked_reason=reason, life_bonus=e.spec.concept is not None and e.spec.concept in bonus,
        concept_id=e.spec.concept,
    )


def _unit_text(unit: UnitSpec, language: str) -> tuple[str, str]:
    return UNIT_TEXT.get(language, {}).get(unit.id, (unit.title, unit.description))


def build_path(passed: Collection[str], bonus: Collection[str] = (), language: str = "en") -> LearnPath:
    """The course path for a user. `passed`: passed lesson ids (unknown ids are ignored). `bonus`: Life concept
    ids the user earned in a game."""
    lang = language_of(language)
    known = set(passed) & set(_by_id())
    units: list[Unit] = []
    next_id: str | None = None
    n = 0
    for ui, u in enumerate(UNITS):
        lessons: list[LessonSummary] = []
        for _ in u.lessons:
            s = _summary(n, known, bonus, lang)
            if next_id is None and s.status == "open":
                next_id = s.id
            lessons.append(s)
            n += 1
        title, description = _unit_text(u, lang)
        units.append(Unit(id=u.id, index=ui, title=title, description=description, lessons=lessons,
                          done=sum(1 for s in lessons if s.status == "passed"), total=len(lessons)))
    return LearnPath(units=units, next_lesson_id=next_id, done=len(known), total=n)


@cache
def _fact(rule_id: str, text: str) -> LessonFact:
    f = rules.get(rule_id)
    return LessonFact(text=text, source_label=SOURCE_LABELS[f.url], source_url=f.url, checked=f.checked)


@cache
def _content(lesson_id: str) -> tuple[list[LessonCard], list[LessonFact], list[LessonQuestion]]:
    spec = _flat()[_by_id()[lesson_id]].spec
    cards = [LessonCard(title=t, text=x) for t, x in spec.cards]
    facts = [_fact(f.rule, f.text) for f in spec.facts]
    quiz = [
        LessonQuestion(id=f"q{i}", text=q.text,
                       choices=[LessonChoice(id=CHOICE_IDS[j], text=c) for j, c in enumerate(q.choices)])
        for i, q in enumerate(spec.quiz)
    ]
    return cards, facts, quiz


def has_lesson(lesson_id: str) -> bool:
    return lesson_id in _by_id()


def status_of(lesson_id: str, passed: Collection[str]) -> LessonStatus:
    """Raises KeyError for an unknown lesson."""
    return _status(_by_id()[lesson_id], set(passed))


def build_lesson(lesson_id: str, passed: Collection[str], bonus: Collection[str] = (),
                 language: str = "en") -> LearnLesson:
    """The full lesson, whatever its status (the caller refuses locked lessons). Raises KeyError when unknown.
    Lesson text has no translations yet, so every language gets English."""
    n = _by_id()[lesson_id]
    cards, facts, quiz = _content(lesson_id)
    return LearnLesson(summary=_summary(n, set(passed), bonus, language_of(language)), cards=list(cards),
                       facts=list(facts), quiz=list(quiz), pass_mark=PASS_MARK)


def grade(lesson_id: str, answers: Mapping[str, str], passed: Collection[str], bonus: Collection[str] = (),
          language: str = "en") -> tuple[LessonAttemptResult, list[str]]:
    """Grade one attempt. Returns the result and the new passed list (path order). A missing or unknown answer
    counts as wrong. `unlocked_lesson_id` is the next lesson when this attempt passed the lesson for the first
    time. Raises KeyError when the lesson is unknown."""
    n = _by_id()[lesson_id]
    spec = _flat()[n].spec
    results: list[LessonAnswerResult] = []
    for i, q in enumerate(spec.quiz):
        qid = f"q{i}"
        right = CHOICE_IDS[q.answer]
        results.append(LessonAnswerResult(question_id=qid, correct=answers.get(qid) == right,
                                          correct_choice_id=right, explanation=q.why))
    correct = sum(1 for r in results if r.correct)
    ok = correct >= PASS_MARK
    before = set(passed) & set(_by_id())
    after = before | {lesson_id} if ok else before
    unlocked = None
    flat = _flat()
    if ok and lesson_id not in before and n + 1 < len(flat):
        unlocked = flat[n + 1].spec.id
    order = [i for i in lesson_ids() if i in after]
    return LessonAttemptResult(passed=ok, correct=correct, pass_mark=PASS_MARK, results=results,
                               unlocked_lesson_id=unlocked, path=build_path(order, bonus, language)), order
