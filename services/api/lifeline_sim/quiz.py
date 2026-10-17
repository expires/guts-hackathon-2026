"""Money Quiz bank (ADR 0052, ADR 0058, ADR 0059). Pure: no I/O, no clock, no global RNG.

Questions come only from two places:
1. The facts table, `lifeline_engine.rules`: each question asks for one rule value. The right answer is the
   value in the table. The source is the fact's official URL with its checked date.
2. The lessons, `lifeline_sim.concepts`: each lesson's own quiz. The source is the lesson and the data series
   its chart plots.

Wrong answers for rule questions are fixed per question (no RNG). The order of the choices and the choice of
questions are seeded, so everyone in a room with the same seed gets the same quiz. Choice ids are "a".."d" by
position after the shuffle, so an id never gives the answer away.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

from lifeline_contracts.macro import MacroKey
from lifeline_contracts.play import QuizChoice, QuizQuestion
from lifeline_engine import rules
from lifeline_sim.concepts import CONCEPTS, ConceptSpec
from lifeline_sim.rng import rng

QuizTopic = Literal["mixed", "student_finance", "saving", "debt", "tax"]
TOPICS: tuple[QuizTopic, ...] = ("mixed", "student_finance", "saving", "debt", "tax")
CHOICE_IDS = ("a", "b", "c", "d")


class QuizItem(BaseModel):
    """One question with its answer. Send `question` to players; keep the rest for the reveal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question: QuizQuestion
    correct_choice_id: str
    explanation: str = Field(max_length=200, description="Penny's one line")
    source_label: str = Field(max_length=120)
    source_url: str | None = Field(default=None, max_length=500)
    topics: tuple[str, ...]
    fact_id: str | None = Field(default=None, description="rules fact id, for rule questions")
    concept_id: str | None = Field(default=None, description="lesson id, for lesson questions")


@dataclass(frozen=True)
class _RuleQ:
    fact_id: str
    text: str
    wrong: tuple[float, ...]  # wrong values, in the fact's unit
    topics: tuple[str, ...]
    labels: tuple[str, ...] = ()  # optional choice texts, right answer first (replaces value formatting)


_ST = ("student_finance",)
_SL = ("student_finance", "debt")
_SAVE = ("saving",)
_TAX = ("tax",)

_RULE_QUESTIONS: tuple[_RuleQ, ...] = (
    _RuleQ("isa_allowance", "How much can you pay into all your ISAs together in one tax year?",
           (4000, 9000, 50_000), _SAVE),
    _RuleQ("lisa_allowance", "What is the most you can pay into a Lifetime ISA in one tax year?",
           (1000, 20_000, 10_000), _SAVE),
    _RuleQ("lisa_bonus_rate", "What bonus does the government add to money you pay into a Lifetime ISA?",
           (10, 50, 20), _SAVE),
    _RuleQ("lisa_bonus_max", "What is the biggest Lifetime ISA bonus you can get in one year?",
           (4000, 500, 250), _SAVE),
    _RuleQ("lisa_open_age_limit", "You must pay into a Lifetime ISA for the first time before what age?",
           (30, 50, 25), _SAVE),
    _RuleQ("lisa_pay_in_age_limit", "At what age can you no longer pay into a Lifetime ISA?",
           (60, 40, 67), _SAVE),
    _RuleQ("lisa_min_open_age", "How old must you be to open a Lifetime ISA?", (16, 21, 25), _SAVE),
    _RuleQ("lisa_withdrawal_charge",
           "You take money out of a Lifetime ISA for a holiday at 30. What charge do you pay?",
           (0, 10, 50), _SAVE),
    _RuleQ("lisa_penalty_free_age", "From what age can you take money out of a Lifetime ISA with no charge?",
           (50, 55, 67), _SAVE),
    _RuleQ("lisa_first_home_price_limit", "A Lifetime ISA can help buy a first home that costs up to how much?",
           (250_000, 600_000, 1_000_000), _SAVE),
    _RuleQ("jisa_allowance", "How much can family pay into a Junior ISA for a child in one tax year?",
           (4000, 20_000, 2000), _SAVE),
    _RuleQ("savings_starting_rate_band",
           "How big is the starting rate for savings band, where savings interest can be taxed at 0%?",
           (1000, 500, 12_570), ("saving", "tax")),
    _RuleQ("personal_allowance", "How much can most people earn in a tax year before paying income tax?",
           (10_000, 15_000, 25_000), _TAX),
    _RuleQ("personal_allowance_income_limit", "Above what income does your Personal Allowance start to go down?",
           (50_270, 125_140, 150_000), _TAX),
    _RuleQ("basic_rate", "What is the basic rate of income tax in England, Wales and Northern Ireland?",
           (10, 25, 30), _TAX),
    _RuleQ("basic_rate_band", "How wide is the basic rate band (income after allowances)?",
           (50_270, 25_000, 12_570), _TAX),
    _RuleQ("higher_rate", "What is the higher rate of income tax in England, Wales and Northern Ireland?",
           (30, 45, 50), _TAX),
    _RuleQ("higher_rate_band_top", "Where does the higher rate band stop (income after allowances)?",
           (100_000, 150_000, 80_000), _TAX),
    _RuleQ("additional_rate", "What is the additional rate of income tax in England, Wales and Northern Ireland?",
           (40, 50, 60), _TAX),
    _RuleQ("scot_starter_rate", "What is the Scottish starter rate of income tax?", (10, 20, 15), _TAX),
    _RuleQ("scot_intermediate_rate", "What is the Scottish intermediate rate of income tax?", (20, 25, 30), _TAX),
    _RuleQ("scot_higher_rate", "What is the Scottish higher rate of income tax?", (40, 45, 41), _TAX),
    _RuleQ("scot_top_rate", "What is the Scottish top rate of income tax?", (45, 50, 40), _TAX),
    _RuleQ("ni_primary_threshold", "Employees start paying National Insurance on pay above what amount a year?",
           (10_000, 20_000, 6000), _TAX),
    _RuleQ("ni_upper_earnings_limit", "Above what yearly pay does employee National Insurance drop to a lower rate?",
           (40_000, 100_000, 125_140), _TAX),
    _RuleQ("ni_main_rate",
           "What employee National Insurance rate applies between the primary threshold and the upper limit?",
           (12, 10, 2), _TAX),
    _RuleQ("ni_upper_rate", "What employee National Insurance rate applies above the upper earnings limit?",
           (0, 8, 5), _TAX),
    _RuleQ("student_loan_plan1_threshold", "Plan 1 student loans: you repay on pay above what amount a year?",
           (21_000, 29_385, 18_000), _SL),
    _RuleQ("student_loan_plan2_threshold", "Plan 2 student loans: you repay on pay above what amount a year?",
           (25_000, 21_000, 35_000), _SL),
    _RuleQ("student_loan_plan4_threshold",
           "Plan 4 (Scotland) student loans: you repay on pay above what amount a year?",
           (25_000, 29_385, 40_000), _SL),
    _RuleQ("student_loan_plan5_threshold", "Plan 5 student loans: you repay on pay above what amount a year?",
           (29_385, 21_000, 30_000), _SL),
    _RuleQ("postgraduate_loan_threshold", "A postgraduate loan is repaid on pay above what amount a year?",
           (25_000, 15_000, 29_385), _SL),
    _RuleQ("student_loan_rate", "What share of your pay above the threshold repays an undergraduate student loan?",
           (5, 12, 20), _SL),
    _RuleQ("student_loan_rate_plan5",
           "You started university in 2024 (Plan 5). What share of pay above the threshold do you repay?",
           (6, 12, 3), _SL),
    _RuleQ("postgraduate_loan_rate", "What share of your pay above the threshold repays a postgraduate loan?",
           (9, 3, 12), _SL),
    _RuleQ("maintenance_instalments_england",
           "In England, how many instalments a year is the maintenance loan paid in?", (12, 1, 2), _ST),
    _RuleQ("saas_payment_months_term_time",
           "In Scotland, a SAAS living-cost loan can be paid monthly over the term-time months. How many months?",
           (6, 10, 3), _ST),
    _RuleQ("council_tax_all_students_discount",
           "Everyone in your home is a full-time student. How much council tax does the home pay?",
           (), _ST, ("None", "Half", "A quarter off", "The full bill")),
    _RuleQ("council_tax_single_adult_discount",
           "Everyone in your home but one adult is a full-time student. What discount can the home get?",
           (50, 10, 100), _ST),
    _RuleQ("railcard_16_25_price_1y", "How much does a 16-25 Railcard cost for 1 year?", (20, 50, 75), _ST),
    _RuleQ("railcard_16_25_price_3y", "How much does a 16-25 Railcard cost for 3 years?", (105, 60, 120), _ST),
    _RuleQ("railcard_16_25_discount", "How much does a 16-25 Railcard take off most rail fares?",
           (), _ST, ("A third", "A quarter", "Half", "A tenth")),
)  # fmt: skip

# Lessons used in the quiz, with their topics. Only student and young-adult money lessons are listed (student
# finance, budgeting, saving, debt, tax, housing, bills), and each must have an official source URL for its
# chart series (`_SERIES_URL`). Lessons not listed here are not in the quiz (for example car insurance).
_CONCEPT_TOPICS: dict[str, tuple[str, ...]] = {
    "emergency-fund": ("saving", "debt"),
    "compound-interest": ("saving",),
    "real-returns": ("saving",),
    "shopping-around": ("saving",),
    "inflation": ("saving",),
    "deposit": ("saving",),
    "debt": ("debt",),
    "credit-cards": ("debt",),
    "interest-rates": ("debt",),
    "fixed-vs-variable": ("debt",),
    "remortgaging": ("debt",),
    "tax-bands": ("tax",),
    "student-loans": ("student_finance", "debt"),
    "human-capital": ("student_finance",),
    "budgeting": ("student_finance",),
    "renting": ("student_finance",),
    "subscriptions": ("student_finance",),
}

# Official source domains for quiz questions: the ADR 0058 rule domains, plus the official statistics sites
# that publish the lesson chart series (ONS, and Nomis, which ONS runs).
QUIZ_OFFICIAL_DOMAINS: tuple[str, ...] = (*rules.OFFICIAL_DOMAINS, "www.ons.gov.uk", "www.nomisweb.co.uk")

_TOPIC_LABEL: dict[str, str] = {
    "isa": "ISAs",
    "income_tax": "Income Tax rates",
    "scotland_income_tax": "Scottish Income Tax",
    "national_insurance": "National Insurance",
    "student_loan": "Student loan repayment",
    "student_finance": "Student finance",
    "council_tax": "Council Tax",
    "travel": "16-25 Railcard",
}

# Official pages for the data series that lesson charts plot.
_SERIES_URL: dict[MacroKey, str] = {
    MacroKey.BANK_RATE: "https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp",
    MacroKey.MORTGAGE_2Y_FIX: "https://www.bankofengland.co.uk/boeapps/database/",
    MacroKey.MORTGAGE_5Y_FIX: "https://www.bankofengland.co.uk/boeapps/database/",
    MacroKey.SAVINGS_RATE: "https://www.bankofengland.co.uk/boeapps/database/",
    MacroKey.CARD_RATE: "https://www.bankofengland.co.uk/boeapps/database/",
    MacroKey.CPI_INFLATION: "https://www.ons.gov.uk/economy/inflationandpriceindices",
    MacroKey.ENERGY_PRICE_CHANGE: "https://www.ons.gov.uk/economy/inflationandpriceindices",
    MacroKey.RENT_CHANGE: "https://www.ons.gov.uk/economy/inflationandpriceindices",
    MacroKey.MEDIAN_PAY: "https://www.nomisweb.co.uk/datasets/asher",
    MacroKey.UNEMPLOYMENT: "https://www.nomisweb.co.uk/datasets/apsnew",
    MacroKey.HOUSE_PRICE: "https://www.gov.uk/government/collections/uk-house-price-index-reports",
    MacroKey.HOUSE_PRICE_CHANGE: "https://www.gov.uk/government/collections/uk-house-price-index-reports",
}


def _fmt(value: float, unit: str) -> str:
    if unit in ("gbp", "gbp_per_year", "gbp_per_month"):
        return f"£{value:,.0f}"
    if unit == "percent":
        return f"{value:g}%"
    return f"{value:g}"


def _domain(url: str) -> str:
    host = urlparse(url).netloc
    return host[4:] if host.startswith("www.") else host


def _rule_item(q: _RuleQ) -> tuple[str, list[str], str, str, str, tuple[str, ...]]:
    """(id, choice texts with the right one first, explanation, source label, url, topics)."""
    f = rules.get(q.fact_id)
    texts = list(q.labels) if q.labels else [_fmt(f.value, f.unit)] + [_fmt(v, f.unit) for v in q.wrong]
    right = texts[0]
    explanation = f"{f.label} ({f.tax_year})." if q.labels else f"{f.label}: {right} ({f.tax_year})."
    label = f"{_domain(f.url)} · {_TOPIC_LABEL.get(f.topic, f.topic)} · checked {f.checked}"
    return f"q.{f.id}", texts, explanation[:200], label[:120], f.url, q.topics


def _concept_item(c: ConceptSpec) -> tuple[str, list[str], str, str, str | None, tuple[str, ...]]:
    texts = [c.options[c.answer_index]] + [o for i, o in enumerate(c.options) if i != c.answer_index]
    both = f"{c.sentences[0]} {c.sentences[1]}"
    explanation = both if len(both) <= 200 else c.sentences[0][:200]
    label = f"Penny lesson · {c.title} · chart: {c.chart_title}"
    return (
        f"q.concept.{c.id}",
        texts,
        explanation,
        label[:120],
        _SERIES_URL.get(c.chart_key),
        _CONCEPT_TOPICS.get(c.id, ()),
    )


@dataclass(frozen=True)
class _Raw:
    id: str
    text: str
    choices: tuple[str, ...]  # right answer first
    explanation: str
    source_label: str
    source_url: str | None
    topics: tuple[str, ...]
    fact_id: str | None
    concept_id: str | None


def _bank() -> tuple[_Raw, ...]:
    out: list[_Raw] = []
    for q in _RULE_QUESTIONS:
        qid, texts, expl, label, url, topics = _rule_item(q)
        out.append(_Raw(qid, q.text, tuple(texts), expl, label, url, topics, rules.get(q.fact_id).id, None))
    for c in CONCEPTS:
        if c.id not in _CONCEPT_TOPICS:
            continue
        qid, texts, expl, label, url2, topics = _concept_item(c)
        if url2 is None:
            raise ValueError(f"quiz lesson {c.id} has no official source URL")
        out.append(_Raw(qid, c.question, tuple(texts), expl, label, url2, topics, None, c.id))
    return tuple(out)


BANK: tuple[_Raw, ...] = _bank()


def bank_size(topic: QuizTopic = "mixed") -> int:
    return len(_pool(topic))


def _pool(topic: QuizTopic) -> list[_Raw]:
    if topic == "mixed":
        return list(BANK)
    return [r for r in BANK if topic in r.topics]


def _item(raw: _Raw, seed: int, index: int, total: int, answer_ms: int) -> QuizItem:
    order = list(range(len(raw.choices)))
    rng(seed, "quiz", "order", raw.id).shuffle(order)
    choices = [QuizChoice(id=CHOICE_IDS[pos], text=raw.choices[i]) for pos, i in enumerate(order)]
    correct = CHOICE_IDS[order.index(0)]
    q = QuizQuestion(
        id=raw.id,
        index=index,
        total=total,
        text=raw.text,
        choices=choices,
        answer_ms=answer_ms,
        source_label=raw.source_label,
        source_url=raw.source_url,
    )
    return QuizItem(
        question=q,
        correct_choice_id=correct,
        explanation=raw.explanation,
        source_label=raw.source_label,
        source_url=raw.source_url,
        topics=raw.topics or ("mixed",),
        fact_id=raw.fact_id,
        concept_id=raw.concept_id,
    )


def quiz_questions(seed: int, topic: QuizTopic = "mixed", n: int = 8, answer_ms: int = 15_000) -> list[QuizItem]:
    """`n` questions for a Money Quiz round. Same seed and topic give the same questions in the same order with
    the same choice order. `n` is capped at the pool size. Unknown topic raises ValueError."""
    if topic not in TOPICS:
        raise ValueError(f"unknown quiz topic {topic!r}")
    pool = _pool(topic)
    picked = rng(seed, "quiz", "pick", topic).sample(pool, min(max(1, n), len(pool)))
    return [_item(raw, seed, i, len(picked), answer_ms) for i, raw in enumerate(picked)]


def quiz_item(question_id: str, seed: int) -> QuizItem | None:
    """One question by id with the choice order of `seed` (index 0 of 1). None when the id is unknown."""
    raw = next((r for r in BANK if r.id == question_id), None)
    return None if raw is None else _item(raw, seed, 0, 1, 15_000)
