"""Student start paths (ADR 0052, ADR 0059): university, apprenticeship, job at 18, gap year, master's.

A path is a list of stages by age. Each stage says what the person does from that age:
- `study`: a full-time student with a part-time job. Each study year adds the tuition fee loan and the
  maintenance loan to the student loan (undergraduate) or the postgraduate loan (master's).
- `apprentice` or `work`: employed. Pay is set when the stage starts, then grows with regional median pay.

Pay rule: stage pay = `pay_share` x regional median full-time pay for that year (MacroTable MEDIAN_PAY,
Nomis ASHE NM_30_1). The shares are game assumptions that approximate how young workers' pay compares
with the all-ages median in ASHE. They are labelled as assumptions (`PAY_SHARE_NOTE`).

Student loan repayment (rules from `lifeline_engine.rules`, ADR 0058): 9% of gross pay above the plan
threshold, every year the pay is above it. Postgraduate loan: 6% above its threshold. The rule values are for
2026/27; an earlier year uses the same threshold in that year's prices (scaled by CPI).
Plan by the year the course starts (England): before 2012 Plan 1, 2012 to 2022 Plan 2, from 2023 Plan 5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from lifeline_contracts.domain import CharacterSpec, Housing
from lifeline_contracts.macro import MacroKey
from lifeline_contracts.play import StudentPath
from lifeline_engine import rules
from lifeline_sim import params as p
from lifeline_sim.macroview import MacroView

if TYPE_CHECKING:
    from lifeline_sim.state import SimState

StageKind = Literal["study", "study_pg", "apprentice", "work"]
LoanPlan = Literal["plan1", "plan2", "plan5"]

PAY_SHARE_NOTE = "Game assumption: share of regional median full-time pay (Nomis ASHE)."
RULES_YEAR = 2026  # the rules in lifeline_engine.rules are for the 2026/27 tax year

CHECKED = "2026-10-17"  # ADR 0058: every official number below was checked against its URL on this date


@dataclass(frozen=True)
class OfficialAmount:
    """One official yearly amount: from academic year `year` (starting in autumn) until the next row."""

    year: int
    value: float
    url: str
    checked: str = CHECKED


_LEG = "https://www.legislation.gov.uk/uksi/"
TUITION_URL = "https://www.gov.uk/student-finance/new-fulltime-students"
TUITION_URL_2027 = (
    "https://www.gov.uk/government/publications/tuition-fees-and-student-support-2026-to-2027-academic-year/"
    "changes-to-tuition-fees-2026-to-2027-academic-year-and-2027-to-2028-academic-year"
)
# Tuition fee cap for a full-time undergraduate in England, by the academic year the course year starts.
# Paid with the tuition fee loan from 2006. Before 2006 fees were paid up front: no loan here.
# 2027: the cap for providers with a TEF award and an access and participation plan.
TUITION_FEE_CAP: tuple[OfficialAmount, ...] = (
    OfficialAmount(2006, 3000.0, _LEG + "2004/1932/made"),
    OfficialAmount(2007, 3070.0, _LEG + "2006/2382/made"),
    OfficialAmount(2008, 3145.0, _LEG + "2007/1865/made"),
    OfficialAmount(2009, 3225.0, _LEG + "2008/2507/made"),
    OfficialAmount(2010, 3290.0, _LEG + "2009/3113/made"),
    OfficialAmount(2011, 3375.0, _LEG + "2011/432/made"),
    OfficialAmount(2012, 9000.0, _LEG + "2010/3020/made"),
    OfficialAmount(2017, 9250.0, _LEG + "2016/1206/made"),
    OfficialAmount(2025, 9535.0, _LEG + "2025/263/made"),
    OfficialAmount(2026, 9790.0, TUITION_URL),
    OfficialAmount(2027, 10050.0, TUITION_URL_2027),
)
PLAN_URL = "https://www.gov.uk/repaying-your-student-loan/which-repayment-plan-you-are-on"
PG_LOAN_URL = "https://www.gov.uk/masters-loan/what-youll-get"
# Postgraduate Master's Loan maximum, by the academic year the course starts. Years before the first row use
# the first row scaled back by CPI (a game estimate); years after the last row use the last row.
PG_LOAN_MAX: tuple[OfficialAmount, ...] = (
    OfficialAmount(2024, 12_471.0, PG_LOAN_URL),
    OfficialAmount(2025, 12_858.0, PG_LOAN_URL),
    OfficialAmount(2026, 13_206.0, PG_LOAN_URL),
)
MASTERS_FEE_2024 = 11_000.0  # same figure as the study.masters event template


@dataclass(frozen=True)
class Stage:
    from_age: int
    kind: StageKind
    pay_share: float
    job_title: str
    move_out: bool = False  # a work stage that moves from the parents' home into a shared rented room


@dataclass(frozen=True)
class PathDef:
    id: str
    title: str
    description: str
    start_age: int
    quick: bool
    stages: tuple[Stage, ...]
    name: str
    emoji: str
    sex: Literal["female", "male"]
    region: str
    town: str
    housing: Housing  # housing at the start; a study stage moves the person into student rent
    prior_study_years: int = 0  # undergraduate years already done (master's path)


_PATHS: tuple[PathDef, ...] = (
    PathDef(
        id="uni",
        title="University",
        description="Three years of study with student loans, then a graduate job.",
        start_age=18,
        quick=True,
        stages=(
            Stage(18, "study", 0.12, "Student (part-time job)"),
            Stage(21, "work", p.GRADUATE_PAY_SHARE, "Graduate"),
        ),
        name="Priya",
        emoji="🧑🏽‍🎓",
        sex="female",
        region="west-midlands",
        town="Birmingham",
        housing="rent",
    ),
    PathDef(
        id="apprentice",
        title="Apprenticeship",
        description="Earn while you train for three years. No fees, no student loan.",
        start_age=18,
        quick=True,
        stages=(
            Stage(18, "apprentice", 0.45, "Apprentice electrician"),
            Stage(21, "work", 0.75, "Electrician", move_out=True),
        ),
        name="Jordan",
        emoji="👷🏾",
        sex="male",
        region="north-west",
        town="Manchester",
        housing="parents",
    ),
    PathDef(
        id="job18",
        title="Job at 18",
        description="Start work straight after school and live at home.",
        start_age=18,
        quick=True,
        stages=(
            Stage(18, "work", 0.55, "Retail assistant"),
            Stage(21, "work", 0.65, "Shift supervisor", move_out=True),
        ),
        name="Kai",
        emoji="🧑🏻‍💼",
        sex="male",
        region="yorkshire-and-the-humber",
        town="Leeds",
        housing="parents",
    ),
    PathDef(
        id="gap_year",
        title="Gap year",
        description="Work for a year, then three years at university.",
        start_age=18,
        quick=True,
        stages=(
            Stage(18, "work", 0.5, "Café worker"),
            Stage(19, "study", 0.12, "Student (part-time job)"),
            Stage(22, "work", p.GRADUATE_PAY_SHARE, "Graduate"),
        ),
        name="Maya",
        emoji="🎒",
        sex="female",
        region="south-west",
        town="Bristol",
        housing="parents",
    ),
    PathDef(
        id="masters",
        title="Master's degree",
        description="A one-year master's after your degree, paid with a postgraduate loan.",
        start_age=21,
        quick=False,
        stages=(
            Stage(21, "study_pg", 0.12, "Master's student"),
            Stage(22, "work", 0.95, "Graduate"),
        ),
        name="Sam",
        emoji="📚",
        sex="male",
        region="london",
        town="London",
        housing="rent",
        prior_study_years=3,
    ),
)

PATH_IDS: tuple[str, ...] = tuple(d.id for d in _PATHS)
_BY_ID: dict[str, PathDef] = {d.id: d for d in _PATHS}
PATH_CHARACTER_PREFIX = "path-"

# Quick Life (ADR 0052): ages 18 to 25.
QUICK_START_AGE = 18
QUICK_END_AGE = 25
QUICK_DEFAULT_START_YEAR = 2018  # ends at 25 in 2025


def path_def(path_id: str) -> PathDef | None:
    return _BY_ID.get(path_id)


def paths() -> list[StudentPath]:
    """The student start paths, in display order."""
    return [
        StudentPath(id=d.id, title=d.title, description=d.description, start_age=d.start_age, quick=d.quick)
        for d in _PATHS
    ]


def stage_at(path_id: str, age: int) -> Stage | None:
    """The stage the person is in at `age`, or None before the path starts."""
    d = _BY_ID.get(path_id)
    if d is None:
        return None
    current: Stage | None = None
    for st in d.stages:
        if st.from_age <= age:
            current = st
    return current


def stage_starts(path_id: str, age: int) -> Stage | None:
    """The stage that starts exactly at `age`, or None."""
    d = _BY_ID.get(path_id)
    if d is None:
        return None
    return next((st for st in d.stages if st.from_age == age), None)


def _row(table: tuple[OfficialAmount, ...], year: int) -> OfficialAmount | None:
    hit: OfficialAmount | None = None
    for row in table:
        if year >= row.year:
            hit = row
    return hit


def tuition_fee_cap(year: int) -> float:
    """England tuition fee cap for a course year starting in `year`; 0 before 2006 (no tuition fee loan)."""
    row = _row(TUITION_FEE_CAP, year)
    return row.value if row is not None else 0.0


def pg_loan_max(year: int, mv: MacroView) -> float:
    """Master's loan maximum for a course starting in `year` (official table; CPI estimate before 2024)."""
    row = _row(PG_LOAN_MAX, year)
    if row is not None:
        return row.value
    first = PG_LOAN_MAX[0]
    return first.value * mv.price_level(year) / mv.price_level(first.year)


def loan_plan_for(course_start_year: int) -> LoanPlan:
    if course_start_year < 2012:
        return "plan1"
    if course_start_year < 2023:
        return "plan2"
    return "plan5"


def _rule(fact_id: str) -> float:
    return float(rules.get(fact_id).value)


def repayment_threshold(plan: LoanPlan, year: int, mv: MacroView) -> float:
    """Plan threshold (2026/27 rule) in the prices of `year`."""
    base = _rule(f"student_loan_{plan}_threshold")
    return base * mv.price_level(year) / mv.price_level(RULES_YEAR)


def repayment(plan: LoanPlan, gross: float, year: int, mv: MacroView) -> float:
    """Yearly student loan repayment: rate x pay above the threshold, 0 at or below it."""
    rate = _rule(f"student_loan_rate_{plan}") / 100
    return rate * max(0.0, gross - repayment_threshold(plan, year, mv))


def pg_repayment(gross: float, year: int, mv: MacroView) -> float:
    rate = _rule("postgraduate_loan_rate") / 100
    threshold = _rule("postgraduate_loan_threshold") * mv.price_level(year) / mv.price_level(RULES_YEAR)
    return rate * max(0.0, gross - threshold)


def stage_pay(stage: Stage, year: int, region: str, mv: MacroView) -> float | None:
    """Gross yearly pay for the stage, or None when the table has no median pay (live gap)."""
    median = (
        mv.opt(MacroKey.MEDIAN_PAY, year, region)
        if mv.strict
        else mv.value(MacroKey.MEDIAN_PAY, year, region, 30_000.0)
    )
    if median is None:
        return None
    return round(stage.pay_share * median)


def study_loans(year: int, mv: MacroView) -> tuple[float, float]:
    """(tuition fee loan, maintenance loan) for one undergraduate year starting in `year`."""
    return tuition_fee_cap(year), p.MAINTENANCE_LOAN_2024 * mv.price_level(year)


# Offered characters are students or recent graduates only (user rule). Occupation by path: a gap year
# student holds a university place; job at 18 is a school leaver.
PATH_OCCUPATION: dict[str, str] = {
    "uni": "student",
    "apprentice": "apprentice",
    "job18": "school leaver",
    "gap_year": "student",
    "masters": "student",
}


@dataclass(frozen=True)
class QuickStudentDef:
    """A premade Quick Life student (ADR 0064): a path, a place and a way of paying for it."""

    id: str
    name: str
    path_id: str
    description: str
    emoji: str
    sex: Literal["female", "male"]
    region: str
    town: str
    bursary_2024: float = 0.0  # university bursary a study year, 2024 pounds (game amount, not a loan)


QUICK_STUDENTS: tuple[QuickStudentDef, ...] = (
    QuickStudentDef("qs-priya", "Priya", "uni", "University in Birmingham, paid with the full student loan.",
                    "🧑🏽‍🎓", "female", "west-midlands", "Birmingham"),
    QuickStudentDef("qs-amara", "Amara", "uni", "University in London with a £2,000 a year bursary.",
                    "👩🏿‍🎓", "female", "london", "London", bursary_2024=2000.0),
    QuickStudentDef("qs-jordan", "Jordan", "apprentice", "Electrician apprentice in Manchester. Paid to train.",
                    "👷🏾", "male", "north-west", "Manchester"),
    QuickStudentDef("qs-kai", "Kai", "job18", "Starts work at 18 in Leeds and lives at home.",
                    "🧑🏻‍💼", "male", "yorkshire-and-the-humber", "Leeds"),
    QuickStudentDef("qs-maya", "Maya", "gap_year", "Works a gap year in Bristol, then goes to university.",
                    "🎒", "female", "south-west", "Bristol"),
)  # fmt: skip
_QUICK_BY_ID: dict[str, QuickStudentDef] = {q.id: q for q in QUICK_STUDENTS}


def quick_student_def(student_id: str) -> QuickStudentDef | None:
    return _QUICK_BY_ID.get(student_id)


def path_character(
    path_id: str, start_year: int, mv: MacroView | None = None, student_id: str | None = None
) -> CharacterSpec:
    """The character for a path (or a premade Quick Life student), `start_age` in `start_year`.
    With `mv`, the starting pay is the stage pay."""
    d = _BY_ID[path_id]
    qs = _QUICK_BY_ID.get(student_id) if student_id is not None else None
    first = d.stages[0]
    region = qs.region if qs is not None else d.region
    income = 0.0
    if mv is not None:
        income = stage_pay(first, start_year, region, mv) or 0.0
    return CharacterSpec(
        id=qs.id if qs is not None else f"{PATH_CHARACTER_PREFIX}{d.id}",
        name=qs.name if qs is not None else d.name,
        emoji=qs.emoji if qs is not None else d.emoji,
        sex=qs.sex if qs is not None else d.sex,
        occupation=PATH_OCCUPATION[d.id],
        region=region,
        town=qs.town if qs is not None else d.town,
        birth_year=start_year - d.start_age,
        annual_income=income,
        savings=0.0,
        debt=0.0,
        housing=d.housing,
        blurb=(qs.description if qs is not None else f"{d.title}: {d.description}")[:200],
    )


# ---------- applying stages to a state ----------


def _student_rent(s: SimState, mv: MacroView) -> float:
    house_price = mv.value(MacroKey.HOUSE_PRICE, s.year, s.region, 200_000.0)
    return round(house_price * p.GROSS_RENT_YIELD / 12 * p.STUDENT_RENT_SHARE)


def _shared_rent(s: SimState, mv: MacroView) -> float:
    house_price = mv.value(MacroKey.HOUSE_PRICE, s.year, s.region, 200_000.0)
    return round(house_price * p.GROSS_RENT_YIELD / 12 * p.SHARED_RENT_SHARE)


def region_factor(region: str, year: int, mv: MacroView) -> float:
    """Regional cost factor: regional / UK median pay (Nomis ASHE), clamped to PATH_REGION_FACTOR_RANGE."""
    uk = mv.value(MacroKey.MEDIAN_PAY, year, None, 0.0)
    here = mv.value(MacroKey.MEDIAN_PAY, year, region, uk)
    lo, hi = p.PATH_REGION_FACTOR_RANGE
    return max(lo, min(hi, here / uk)) if uk > 0 else 1.0


def wants_weekly_2024(s: SimState) -> float:
    """Weekly wants spending in 2024 pounds: the stage baseline plus what choices added, at least the minimum."""
    base = p.PATH_WANTS_WEEKLY_STUDENT_2024 if s.student else p.PATH_WANTS_WEEKLY_WORKER_2024
    return max(p.PATH_WANTS_MIN_WEEKLY_2024, base + s.want_adj)


def path_living(s: SimState, mv: MacroView) -> tuple[float, float]:
    """(monthly living costs without housing, monthly wants part of it) for a path life in `s.year`.

    Living = essentials for the housing (at home, student, worker) x CPI price level x regional cost factor
    + weekly wants x 52 / 12 x CPI price level + monthly changes from choices (for example a subscription)."""
    price = mv.price_level(s.year)
    if s.housing == "parents":
        essentials = p.PATH_ESSENTIALS_AT_HOME_2024
    elif s.student:
        essentials = p.PATH_ESSENTIALS_STUDENT_2024
    else:
        essentials = p.PATH_ESSENTIALS_WORKER_2024
    wants = wants_weekly_2024(s) * 52 / 12 * price
    living = essentials * price * region_factor(s.region, s.year, mv) + wants + s.living_adj
    return max(0.0, living), wants


def apply_stage(s: SimState, stage: Stage, mv: MacroView) -> None:
    """Enter `stage` at the state's current year and age. Sets pay, job, student flags and housing."""
    was_student = s.student
    pay = stage_pay(stage, s.year, s.region, mv)
    if pay is None:
        s.data_gaps.setdefault(s.year, []).append(MacroKey.MEDIAN_PAY.value)
        pay = s.income
    s.income = pay
    s.job_title = stage.job_title
    s.years_in_role = 0
    s.retired = False
    if stage.kind in ("study", "study_pg"):
        s.student = True
        s.employed = pay > 0
        s.study_kind = "pg" if stage.kind == "study_pg" else "ug"
        if stage.kind == "study" and s.loan_plan is None:
            s.loan_plan = loan_plan_for(s.year)
        if s.housing != "rent":
            s.housing = "rent"
            s.rent = _student_rent(s, mv)
            s.living = max(s.living, p.MIN_LIVING_MONTHLY_2024 * mv.price_level(s.year))
    else:
        s.student = False
        s.study_kind = None
        s.employed = True
        if was_student:
            s.last_graduated = True
            if s.housing == "rent":
                s.rent = _shared_rent(s, mv)  # graduates stay in a shared rented room
        if stage.move_out and s.housing == "parents":
            s.housing = "rent"
            s.rent = _shared_rent(s, mv)


def add_study_year_loans(s: SimState, mv: MacroView) -> float:
    """Add one study year of loans. Returns the money paid to the student (counts as income this year)."""
    if s.study_kind == "pg":
        loan = pg_loan_max(s.year, mv)
        s.pg_loan += loan
        return max(0.0, loan - MASTERS_FEE_2024 * mv.price_level(s.year))
    tuition, maintenance = study_loans(s.year, mv)
    s.student_loan += tuition + maintenance
    return maintenance + s.bursary_2024 * mv.price_level(s.year)


def start_path(s: SimState, path_id: str, mv: MacroView, student_id: str | None = None) -> None:
    """Set the start state for a path life. Called from `initial_state` before costs are set."""
    d = _BY_ID[path_id]
    s.path_id = path_id
    qs = _QUICK_BY_ID.get(student_id) if student_id is not None else None
    s.bursary_2024 = qs.bursary_2024 if qs is not None else 0.0
    if d.prior_study_years:
        # A degree before the master's: loans for each earlier year, Plan by the first year.
        first = s.year - d.prior_study_years
        s.loan_plan = loan_plan_for(first)
        for y in range(first, s.year):
            tuition, maintenance = study_loans(y, mv)
            s.student_loan += tuition + maintenance
    stage = stage_at(path_id, s.age) or d.stages[0]
    apply_stage(s, stage, mv)
    s.last_graduated = False
    if s.student:
        add_study_year_loans(s, mv)  # the first study year's loans are taken at the start
