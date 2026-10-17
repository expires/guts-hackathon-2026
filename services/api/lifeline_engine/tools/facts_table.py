"""Official UK rule numbers for the 2026 to 2027 tax year (ADR 0033). Pure data, no I/O.

Penny may cite only these rule numbers outside tool results. Each entry has its gov.uk page and the date
the value was checked against that page. Income tax bands are "income after allowances", as gov.uk states them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

Unit = Literal["gbp", "gbp_per_month", "gbp_per_year", "percent", "months", "years", "count", "date_year"]
Topic = Literal["isa", "income_tax", "scotland_income_tax", "national_insurance", "student_loan"]

TAX_YEAR = "2026/27"
AS_OF = "2026-10-17"  # date each value was checked against its gov.uk page

URL_INCOME_TAX = (
    "https://www.gov.uk/government/publications/rates-and-allowances-income-tax/"
    "income-tax-rates-and-allowances-current-and-past"
)
URL_EMPLOYERS = "https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2026-to-2027"
URL_ISA = "https://www.gov.uk/individual-savings-accounts"
URL_LISA = "https://www.gov.uk/lifetime-isa"
URL_JISA = "https://www.gov.uk/junior-individual-savings-accounts"


@dataclass(frozen=True)
class RuleFact:
    id: str
    topic: Topic
    value: float
    unit: Unit
    label: str
    url: str
    tax_year: str = TAX_YEAR
    as_of: str = AS_OF


def _f(id_: str, topic: Topic, value: float, unit: Unit, label: str, url: str) -> RuleFact:
    return RuleFact(id=f"rule.{id_}", topic=topic, value=value, unit=unit, label=label, url=url)


FACTS: tuple[RuleFact, ...] = (
    # ISAs
    _f("isa_allowance", "isa", 20_000, "gbp_per_year", "ISA allowance, all ISAs together", URL_ISA),
    _f("lisa_allowance", "isa", 4_000, "gbp_per_year", "Lifetime ISA yearly limit (part of the ISA allowance)",
       URL_LISA),
    _f("lisa_bonus_rate", "isa", 25, "percent", "Lifetime ISA government bonus", URL_LISA),
    _f("lisa_bonus_max", "isa", 1_000, "gbp_per_year", "Lifetime ISA maximum bonus a year", URL_LISA),
    _f("lisa_open_age_limit", "isa", 40, "years", "Lifetime ISA: first payment before this age", URL_LISA),
    _f("lisa_pay_in_age_limit", "isa", 50, "years", "Lifetime ISA: payments stop at this age", URL_LISA),
    _f("jisa_allowance", "isa", 9_000, "gbp_per_year", "Junior ISA yearly limit", URL_JISA),
    # Income tax: England, Wales and Northern Ireland
    _f("personal_allowance", "income_tax", 12_570, "gbp_per_year", "Personal Allowance", URL_INCOME_TAX),
    _f("personal_allowance_income_limit", "income_tax", 100_000, "gbp_per_year",
       "Income above which the Personal Allowance goes down", URL_INCOME_TAX),
    _f("savings_starting_rate_band", "income_tax", 5_000, "gbp_per_year", "Starting rate for savings band (0%)",
       URL_INCOME_TAX),
    _f("basic_rate", "income_tax", 20, "percent", "Basic rate (England, Wales, Northern Ireland)", URL_INCOME_TAX),
    _f("basic_rate_band", "income_tax", 37_700, "gbp_per_year",
       "Basic rate band, income after allowances (England, Wales, Northern Ireland)", URL_INCOME_TAX),
    _f("higher_rate", "income_tax", 40, "percent", "Higher rate (England, Wales, Northern Ireland)", URL_INCOME_TAX),
    _f("higher_rate_band_top", "income_tax", 125_140, "gbp_per_year",
       "Top of the higher rate band, income after allowances", URL_INCOME_TAX),
    _f("additional_rate", "income_tax", 45, "percent", "Additional rate (England, Wales, Northern Ireland)",
       URL_INCOME_TAX),
    # Income tax: Scotland (bands are income after allowances)
    _f("scot_starter_rate", "scotland_income_tax", 19, "percent", "Scottish starter rate", URL_INCOME_TAX),
    _f("scot_starter_band_top", "scotland_income_tax", 3_967, "gbp_per_year", "Top of the Scottish starter band",
       URL_INCOME_TAX),
    _f("scot_basic_rate", "scotland_income_tax", 20, "percent", "Scottish basic rate", URL_INCOME_TAX),
    _f("scot_basic_band_top", "scotland_income_tax", 16_956, "gbp_per_year", "Top of the Scottish basic band",
       URL_INCOME_TAX),
    _f("scot_intermediate_rate", "scotland_income_tax", 21, "percent", "Scottish intermediate rate", URL_INCOME_TAX),
    _f("scot_intermediate_band_top", "scotland_income_tax", 31_092, "gbp_per_year",
       "Top of the Scottish intermediate band", URL_INCOME_TAX),
    _f("scot_higher_rate", "scotland_income_tax", 42, "percent", "Scottish higher rate", URL_INCOME_TAX),
    _f("scot_higher_band_top", "scotland_income_tax", 62_430, "gbp_per_year", "Top of the Scottish higher band",
       URL_INCOME_TAX),
    _f("scot_advanced_rate", "scotland_income_tax", 45, "percent", "Scottish advanced rate", URL_INCOME_TAX),
    _f("scot_advanced_band_top", "scotland_income_tax", 125_140, "gbp_per_year",
       "Top of the Scottish advanced band", URL_INCOME_TAX),
    _f("scot_top_rate", "scotland_income_tax", 48, "percent", "Scottish top rate", URL_INCOME_TAX),
    # National Insurance (employee, Class 1, category A)
    _f("ni_primary_threshold", "national_insurance", 12_570, "gbp_per_year",
       "National Insurance primary threshold (employee)", URL_EMPLOYERS),
    _f("ni_upper_earnings_limit", "national_insurance", 50_270, "gbp_per_year",
       "National Insurance upper earnings limit", URL_EMPLOYERS),
    _f("ni_main_rate", "national_insurance", 8, "percent",
       "Employee National Insurance between the primary threshold and the upper earnings limit", URL_EMPLOYERS),
    _f("ni_upper_rate", "national_insurance", 2, "percent",
       "Employee National Insurance above the upper earnings limit", URL_EMPLOYERS),
    # Student loans
    _f("student_loan_plan1_threshold", "student_loan", 26_900, "gbp_per_year", "Plan 1 repayment threshold",
       URL_EMPLOYERS),
    _f("student_loan_plan2_threshold", "student_loan", 29_385, "gbp_per_year", "Plan 2 repayment threshold",
       URL_EMPLOYERS),
    _f("student_loan_plan4_threshold", "student_loan", 33_795, "gbp_per_year", "Plan 4 (Scotland) repayment threshold",
       URL_EMPLOYERS),
    _f("student_loan_plan5_threshold", "student_loan", 25_000, "gbp_per_year", "Plan 5 repayment threshold",
       URL_EMPLOYERS),
    _f("postgraduate_loan_threshold", "student_loan", 21_000, "gbp_per_year", "Postgraduate loan repayment threshold",
       URL_EMPLOYERS),
    _f("student_loan_rate", "student_loan", 9, "percent", "Student loan repayment rate above the threshold",
       URL_EMPLOYERS),
    _f("postgraduate_loan_rate", "student_loan", 6, "percent", "Postgraduate loan repayment rate above the threshold",
       URL_EMPLOYERS),
)

BY_ID: dict[str, RuleFact] = {f.id: f for f in FACTS}
TOPICS: tuple[Topic, ...] = ("isa", "income_tax", "scotland_income_tax", "national_insurance", "student_loan")


def get(fact_id: str) -> RuleFact:
    """One fact by id. Accepts the id with or without the 'rule.' prefix. Raises KeyError when unknown."""
    key = fact_id if fact_id.startswith("rule.") else f"rule.{fact_id}"
    return BY_ID[key]


def lookup(ids: Sequence[str] | None = None, topic: Topic | None = None) -> list[RuleFact]:
    """Facts by ids (unknown ids are skipped), by topic, or all when both are None. Order follows FACTS."""
    out = list(FACTS)
    if topic is not None:
        out = [f for f in out if f.topic == topic]
    if ids is not None:
        wanted = {i if i.startswith("rule.") else f"rule.{i}" for i in ids}
        out = [f for f in out if f.id in wanted]
    return out
