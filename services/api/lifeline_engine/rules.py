"""Official UK rule numbers for the 2026 to 2027 tax year (ADR 0033). Pure data, no I/O.

Penny may cite only these rule numbers outside tool results. Each entry has its own official page (ADR 0058
domains) and the date the value was checked against that page (`checked`). Income tax bands are "income after
allowances", as gov.uk states them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

Unit = Literal["gbp", "gbp_per_month", "gbp_per_year", "percent", "months", "years", "count", "date_year"]
Topic = Literal[
    "isa", "income_tax", "scotland_income_tax", "national_insurance", "student_loan", "student_finance", "council_tax",
    "travel",
]

TAX_YEAR = "2026/27"
# Each entry was checked against its own official page on this date (ADR 0058, facts_verified.json).
CHECKED_2026_10_17 = "2026-10-17"

URL_INCOME_TAX = (
    "https://www.gov.uk/government/publications/rates-and-allowances-income-tax/"
    "income-tax-rates-and-allowances-current-and-past"
)
URL_EMPLOYERS = "https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2026-to-2027"
URL_ISA = "https://www.gov.uk/individual-savings-accounts"
URL_LISA = "https://www.gov.uk/lifetime-isa"
URL_LISA_WHO = "https://www.gov.uk/lifetime-isa/who-can-open-a-lifetime-isa"
URL_LISA_WITHDRAW = "https://www.gov.uk/lifetime-isa/withdrawing-money-from-your-lifetime-isa"
URL_JISA = "https://www.gov.uk/junior-individual-savings-accounts"
URL_STUDENT_LOAN_PAY = "https://www.gov.uk/repaying-your-student-loan/what-you-pay"
URL_SFE_PAID = (
    "https://www.gov.uk/government/publications/student-finance-how-youre-assessed-and-paid/"
    "student-finance-how-youre-assessed-and-paid-2026-to-2027"
)
URL_SFW = "https://www.studentfinancewales.co.uk/terms-and-conditions/terms-and-conditions-guide-2627/"
URL_SFNI = "https://www.studentfinanceni.co.uk/media/1866/sfni_terms_and_conditions_guide_2627_o.pdf"
URL_SAAS = "https://www.saas.gov.uk/files/270/saas-living-cost-loan-application-form.pdf"
URL_COUNCIL_TAX_STUDENTS = "https://www.gov.uk/council-tax/discounts-for-full-time-students"
URL_COUNCIL_TAX_WHO = "https://www.gov.uk/council-tax/who-has-to-pay"
URL_RAILCARD = "https://www.16-25railcard.co.uk/"
# Official sources that are not on gov.uk (devolved student finance bodies, Rail Delivery Group's Railcard site).
OFFICIAL_NON_GOVUK: frozenset[str] = frozenset({URL_SAAS, URL_SFW, URL_SFNI, URL_RAILCARD})
# ADR 0058: allowed official domains.
OFFICIAL_DOMAINS: tuple[str, ...] = (
    "www.gov.uk", "www.saas.gov.uk", "www.studentfinancewales.co.uk", "www.studentfinanceni.co.uk",
    "www.railcard.co.uk", "www.16-25railcard.co.uk", "www.legislation.gov.uk", "www.bankofengland.co.uk",
)


@dataclass(frozen=True)
class RuleFact:
    id: str
    topic: Topic
    value: float
    unit: Unit
    label: str
    url: str
    checked: str  # ISO date this entry was checked against `url` (ADR 0058)
    tax_year: str = TAX_YEAR


def _f(id_: str, topic: Topic, value: float, unit: Unit, label: str, url: str, checked: str) -> RuleFact:
    return RuleFact(id=f"rule.{id_}", topic=topic, value=value, unit=unit, label=label, url=url, checked=checked)


FACTS: tuple[RuleFact, ...] = (
    _f("isa_allowance", "isa", 20_000, "gbp_per_year", "ISA allowance, all ISAs together", URL_ISA, CHECKED_2026_10_17),
    _f("lisa_allowance", "isa", 4000, "gbp_per_year",
       "Lifetime ISA yearly limit (part of the ISA allowance)", URL_LISA, CHECKED_2026_10_17),
    _f("lisa_bonus_rate", "isa", 25, "percent", "Lifetime ISA government bonus", URL_LISA, CHECKED_2026_10_17),
    _f("lisa_bonus_max", "isa", 1000, "gbp_per_year",
       "Lifetime ISA maximum bonus a year", URL_LISA, CHECKED_2026_10_17),
    _f("lisa_open_age_limit", "isa", 40, "years",
       "Lifetime ISA: first payment before this age", URL_LISA_WHO, CHECKED_2026_10_17),
    _f("lisa_pay_in_age_limit", "isa", 50, "years",
       "Lifetime ISA: payments stop at this age", URL_LISA, CHECKED_2026_10_17),
    _f("jisa_allowance", "isa", 9000, "gbp_per_year", "Junior ISA yearly limit", URL_JISA, CHECKED_2026_10_17),
    _f("personal_allowance", "income_tax", 12_570, "gbp_per_year",
       "Personal Allowance", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("personal_allowance_income_limit", "income_tax", 100_000, "gbp_per_year",
       "Income above which the Personal Allowance goes down", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("savings_starting_rate_band", "income_tax", 5000, "gbp_per_year",
       "Starting rate for savings band (0%)", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("basic_rate", "income_tax", 20, "percent",
       "Basic rate (England, Wales, Northern Ireland)", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("basic_rate_band", "income_tax", 37_700, "gbp_per_year",
       "Basic rate band, income after allowances (England, Wales, Northern Ireland)",
       URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("higher_rate", "income_tax", 40, "percent",
       "Higher rate (England, Wales, Northern Ireland)", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("higher_rate_band_top", "income_tax", 125_140, "gbp_per_year",
       "Top of the higher rate band, income after allowances", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("additional_rate", "income_tax", 45, "percent",
       "Additional rate (England, Wales, Northern Ireland)", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("scot_starter_rate", "scotland_income_tax", 19, "percent",
       "Scottish starter rate", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("scot_starter_band_top", "scotland_income_tax", 3967, "gbp_per_year",
       "Top of the Scottish starter band", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("scot_basic_rate", "scotland_income_tax", 20, "percent",
       "Scottish basic rate", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("scot_basic_band_top", "scotland_income_tax", 16_956, "gbp_per_year",
       "Top of the Scottish basic band", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("scot_intermediate_rate", "scotland_income_tax", 21, "percent",
       "Scottish intermediate rate", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("scot_intermediate_band_top", "scotland_income_tax", 31_092, "gbp_per_year",
       "Top of the Scottish intermediate band", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("scot_higher_rate", "scotland_income_tax", 42, "percent",
       "Scottish higher rate", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("scot_higher_band_top", "scotland_income_tax", 62_430, "gbp_per_year",
       "Top of the Scottish higher band", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("scot_advanced_rate", "scotland_income_tax", 45, "percent",
       "Scottish advanced rate", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("scot_advanced_band_top", "scotland_income_tax", 125_140, "gbp_per_year",
       "Top of the Scottish advanced band", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("scot_top_rate", "scotland_income_tax", 48, "percent", "Scottish top rate", URL_INCOME_TAX, CHECKED_2026_10_17),
    _f("ni_primary_threshold", "national_insurance", 12_570, "gbp_per_year",
       "National Insurance primary threshold (employee)", URL_EMPLOYERS, CHECKED_2026_10_17),
    _f("ni_upper_earnings_limit", "national_insurance", 50_270, "gbp_per_year",
       "National Insurance upper earnings limit", URL_EMPLOYERS, CHECKED_2026_10_17),
    _f("ni_main_rate", "national_insurance", 8, "percent",
       "Employee National Insurance between the primary threshold and the upper earnings limit",
       URL_EMPLOYERS, CHECKED_2026_10_17),
    _f("ni_upper_rate", "national_insurance", 2, "percent",
       "Employee National Insurance above the upper earnings limit", URL_EMPLOYERS, CHECKED_2026_10_17),
    _f("student_loan_plan1_threshold", "student_loan", 26_900, "gbp_per_year",
       "Plan 1 repayment threshold", URL_EMPLOYERS, CHECKED_2026_10_17),
    _f("student_loan_plan2_threshold", "student_loan", 29_385, "gbp_per_year",
       "Plan 2 repayment threshold", URL_EMPLOYERS, CHECKED_2026_10_17),
    _f("student_loan_plan4_threshold", "student_loan", 33_795, "gbp_per_year",
       "Plan 4 (Scotland) repayment threshold", URL_EMPLOYERS, CHECKED_2026_10_17),
    _f("student_loan_plan5_threshold", "student_loan", 25_000, "gbp_per_year",
       "Plan 5 repayment threshold", URL_EMPLOYERS, CHECKED_2026_10_17),
    _f("postgraduate_loan_threshold", "student_loan", 21_000, "gbp_per_year",
       "Postgraduate loan repayment threshold", URL_EMPLOYERS, CHECKED_2026_10_17),
    _f("student_loan_rate", "student_loan", 9, "percent",
       "Student loan repayment rate above the threshold", URL_EMPLOYERS, CHECKED_2026_10_17),
    _f("postgraduate_loan_rate", "student_loan", 6, "percent",
       "Postgraduate loan repayment rate above the threshold", URL_EMPLOYERS, CHECKED_2026_10_17),
    _f("student_loan_rate_plan1", "student_loan", 9, "percent",
       "Plan 1 repayment rate above the threshold", URL_STUDENT_LOAN_PAY, CHECKED_2026_10_17),
    _f("student_loan_rate_plan2", "student_loan", 9, "percent",
       "Plan 2 repayment rate above the threshold", URL_STUDENT_LOAN_PAY, CHECKED_2026_10_17),
    _f("student_loan_rate_plan4", "student_loan", 9, "percent",
       "Plan 4 repayment rate above the threshold", URL_STUDENT_LOAN_PAY, CHECKED_2026_10_17),
    _f("student_loan_rate_plan5", "student_loan", 9, "percent",
       "Plan 5 repayment rate above the threshold", URL_STUDENT_LOAN_PAY, CHECKED_2026_10_17),
    _f("lisa_min_open_age", "isa", 18, "years",
       "Lifetime ISA: you must be at least this age to open one", URL_LISA_WHO, CHECKED_2026_10_17),
    _f("lisa_withdrawal_charge", "isa", 25, "percent",
       "Lifetime ISA: charge on money taken out for anything other than a first home or after age 60",
       URL_LISA_WITHDRAW, CHECKED_2026_10_17),
    _f("lisa_penalty_free_age", "isa", 60, "years",
       "Lifetime ISA: no withdrawal charge from this age", URL_LISA_WITHDRAW, CHECKED_2026_10_17),
    _f("lisa_first_home_price_limit", "isa", 450_000, "gbp",
       "Lifetime ISA: first home must cost this or less", URL_LISA_WITHDRAW, CHECKED_2026_10_17),
    _f("maintenance_instalments_england", "student_finance", 3, "count",
       "England: maintenance loan paid in 3 instalments a year, one at the start of each term",
       URL_SFE_PAID, CHECKED_2026_10_17),
    _f("maintenance_instalments_wales", "student_finance", 3, "count",
       "Wales: maintenance loan paid in 3 instalments a year, one at the start of each term",
       URL_SFW, CHECKED_2026_10_17),
    _f("maintenance_instalments_ni", "student_finance", 3, "count",
       "Northern Ireland: maintenance loan paid in 3 instalments a year, one at the start of each term",
       URL_SFNI, CHECKED_2026_10_17),
    _f("saas_payment_months_term_time", "student_finance", 9, "months",
       "SAAS living-cost loan paid monthly over 9 term-time months or 12 months (you choose)",
       URL_SAAS, CHECKED_2026_10_17),
    _f("saas_payment_months_full_year", "student_finance", 12, "months",
       "SAAS living-cost loan paid monthly over 9 term-time months or 12 months (you choose)",
       URL_SAAS, CHECKED_2026_10_17),
    _f("council_tax_all_students_discount", "council_tax", 100, "percent",
       "No council tax when everyone in the home is a full-time student", URL_COUNCIL_TAX_STUDENTS, CHECKED_2026_10_17),
    _f("council_tax_single_adult_discount", "council_tax", 25, "percent",
       "25% off when everyone but one adult in the home is a full-time student",
       URL_COUNCIL_TAX_WHO, CHECKED_2026_10_17),
    _f("railcard_16_25_price_1y", "travel", 35, "gbp",
       "16-25 Railcard price for 1 year", URL_RAILCARD, CHECKED_2026_10_17),
    _f("railcard_16_25_price_3y", "travel", 80, "gbp",
       "16-25 Railcard price for 3 years", URL_RAILCARD, CHECKED_2026_10_17),
    _f("railcard_16_25_discount", "travel", 33.33, "percent", "16-25 Railcard: a third off most rail fares",
       URL_RAILCARD, CHECKED_2026_10_17),
)

BY_ID: dict[str, RuleFact] = {f.id: f for f in FACTS}
TOPICS: tuple[Topic, ...] = (
    "isa", "income_tax", "scotland_income_tax", "national_insurance", "student_loan", "student_finance", "council_tax",
    "travel",
)


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
