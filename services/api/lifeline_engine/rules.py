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
    "travel", "economy", "banking", "work", "pensions", "benefits", "childcare", "energy", "inheritance_tax",
    "property_tax", "consumer",
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
URL_HESA_SB273_FIG7 = "https://www.hesa.ac.uk/data-and-analysis/sb273/figure-7"
CHECKED_2026_10_18 = "2026-10-18"
URL_BOE_INFLATION = "https://www.bankofengland.co.uk/monetary-policy/inflation"
URL_BOE_BANK_RATE = "https://www.bankofengland.co.uk/monetary-policy/the-interest-rate-bank-rate"
URL_FSCS = "https://www.fscs.org.uk/check/check-your-money-is-protected/"
URL_SSP = "https://www.gov.uk/statutory-sick-pay"
URL_STATE_PENSION = "https://www.gov.uk/new-state-pension/what-youll-get"
URL_WORKPLACE_PENSION = "https://www.gov.uk/workplace-pensions/what-you-your-employer-and-the-government-pay"
URL_MIN_WAGE = "https://www.gov.uk/national-minimum-wage-rates"
URL_UNIVERSAL_CREDIT = "https://www.gov.uk/universal-credit/what-youll-get"
URL_REDUNDANCY = "https://www.gov.uk/redundancy-your-rights/redundancy-pay"
URL_TAX_FREE_CHILDCARE = "https://www.gov.uk/tax-free-childcare"
URL_FREE_CHILDCARE = "https://www.gov.uk/free-childcare-if-working"
URL_OFGEM_CAP_OCT_2026 = "https://www.ofgem.gov.uk/press-release/energy-price-cap-will-rise-4-october-2026"
URL_SFE_NEW_FULLTIME = "https://www.gov.uk/student-finance/new-fulltime-students"
URL_INHERITANCE_TAX = "https://www.gov.uk/inheritance-tax"
URL_SDLT_RATES = "https://www.gov.uk/stamp-duty-land-tax/residential-property-rates"
URL_DISTANCE_SELLING = "https://www.gov.uk/online-and-distance-selling-for-businesses"
URL_FCA_OVERDRAFT_CHARGES = "https://www.fca.org.uk/data/changes-overdraft-charges"
URL_FCA_BNPL = "https://www.fca.org.uk/consumers/buy-now-pay-later"
URL_FSCS_INSURANCE = "https://www.fscs.org.uk/what-we-cover/insurance/"
# Official sources that are not on gov.uk (devolved student finance bodies, Rail Delivery Group's Railcard site).
# Bank of England, FSCS and Ofgem are UK public bodies (ADR 0058 domains).
OFFICIAL_NON_GOVUK: frozenset[str] = frozenset({
    URL_SAAS, URL_SFW, URL_SFNI, URL_RAILCARD, URL_HESA_SB273_FIG7, URL_BOE_INFLATION, URL_BOE_BANK_RATE, URL_FSCS,
    URL_OFGEM_CAP_OCT_2026, URL_FCA_OVERDRAFT_CHARGES, URL_FCA_BNPL, URL_FSCS_INSURANCE,
})
# ADR 0058: allowed official domains.
OFFICIAL_DOMAINS: tuple[str, ...] = (
    "www.gov.uk", "www.saas.gov.uk", "www.studentfinancewales.co.uk", "www.studentfinanceni.co.uk",
    "www.railcard.co.uk", "www.16-25railcard.co.uk", "www.legislation.gov.uk", "www.bankofengland.co.uk",
    "www.hesa.ac.uk",  # ADR 0058 amendment: higher education statistics
    "www.fscs.org.uk",  # Financial Services Compensation Scheme (UK public body)
    "www.ofgem.gov.uk",  # Office of Gas and Electricity Markets (UK energy regulator)
    "www.fca.org.uk",  # Financial Conduct Authority (UK financial regulator)
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


def _f(
    id_: str, topic: Topic, value: float, unit: Unit, label: str, url: str, checked: str, tax_year: str = TAX_YEAR
) -> RuleFact:
    return RuleFact(id=f"rule.{id_}", topic=topic, value=value, unit=unit, label=label, url=url, checked=checked,
                    tax_year=tax_year)


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
    # HESA 2024/25 enrolments: 685,565 non-UK of 2,863,180 = 23.94%, shown as 23.9
    _f("hesa_non_uk_share_2024_25", "student_finance", 23.9, "percent",
       "Students at UK universities from outside the UK (HESA 2024/25, enrolments)", URL_HESA_SB273_FIG7,
       CHECKED_2026_10_18, tax_year="2024/25"),
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
    # Learn course facts (ADR 0068). Each value checked against its own official page on 2026-10-18.
    _f("boe_inflation_target", "economy", 2, "percent",
       "Bank of England inflation target (set by the Government)", URL_BOE_INFLATION, CHECKED_2026_10_18),
    _f("boe_bank_rate", "economy", 3.75, "percent",
       "Bank of England Bank Rate (held at the September 2026 meeting)", URL_BOE_BANK_RATE, CHECKED_2026_10_18),
    _f("fscs_deposit_limit", "banking", 120_000, "gbp",
       "FSCS deposit protection per eligible person, per bank, building society or credit union (from 1 December "
       "2025)", URL_FSCS, CHECKED_2026_10_18),
    _f("ssp_weekly", "work", 123.25, "gbp",
       "Statutory Sick Pay: up to this amount a week, for up to 28 weeks", URL_SSP, CHECKED_2026_10_18),
    _f("national_living_wage", "work", 12.71, "gbp",
       "National Living Wage an hour, age 21 and over (from April 2026)", URL_MIN_WAGE, CHECKED_2026_10_18),
    _f("minimum_wage_18_20", "work", 10.85, "gbp",
       "National Minimum Wage an hour, age 18 to 20 (from April 2026)", URL_MIN_WAGE, CHECKED_2026_10_18),
    _f("redundancy_weekly_pay_cap", "work", 751, "gbp",
       "Statutory redundancy pay: weekly pay capped at this amount (redundancy on or after 6 April 2026)",
       URL_REDUNDANCY, CHECKED_2026_10_18),
    _f("redundancy_pay_max", "work", 22_530, "gbp",
       "Maximum statutory redundancy pay (redundancy on or after 6 April 2026)", URL_REDUNDANCY, CHECKED_2026_10_18),
    _f("state_pension_full_weekly", "pensions", 241.30, "gbp",
       "Full rate of the new State Pension a week", URL_STATE_PENSION, CHECKED_2026_10_18),
    _f("state_pension_qualifying_years", "pensions", 35, "years",
       "Qualifying years of National Insurance for the full new State Pension (record started after April 2016)",
       URL_STATE_PENSION, CHECKED_2026_10_18),
    _f("auto_enrolment_total_min", "pensions", 8, "percent",
       "Workplace pension auto-enrolment: total minimum contribution", URL_WORKPLACE_PENSION, CHECKED_2026_10_18),
    _f("auto_enrolment_employer_min", "pensions", 3, "percent",
       "Workplace pension auto-enrolment: minimum the employer pays", URL_WORKPLACE_PENSION, CHECKED_2026_10_18),
    _f("uc_standard_single_25_plus", "benefits", 424.90, "gbp_per_month",
       "Universal Credit standard allowance, single and 25 or over", URL_UNIVERSAL_CREDIT, CHECKED_2026_10_18),
    _f("uc_standard_single_under_25", "benefits", 338.58, "gbp_per_month",
       "Universal Credit standard allowance, single and under 25", URL_UNIVERSAL_CREDIT, CHECKED_2026_10_18),
    _f("tax_free_childcare_max", "childcare", 2000, "gbp_per_year",
       "Tax-Free Childcare: government top-up of up to this a year per child (£2 for every £8 you pay in)",
       URL_TAX_FREE_CHILDCARE, CHECKED_2026_10_18),
    _f("free_childcare_hours_england", "childcare", 30, "count",
       "England: hours of free childcare a week for working parents, child aged 9 months to 4 years",
       URL_FREE_CHILDCARE, CHECKED_2026_10_18),
    _f("ofgem_price_cap_typical_bill", "energy", 1723, "gbp_per_year",
       "Ofgem price cap: typical yearly dual fuel Direct Debit bill, 1 October to 31 December 2026",
       URL_OFGEM_CAP_OCT_2026, CHECKED_2026_10_18),
    _f("maintenance_loan_max_home_england", "student_finance", 9118, "gbp_per_year",
       "England: maximum Maintenance Loan 2026/27, living with parents", URL_SFE_NEW_FULLTIME, CHECKED_2026_10_18),
    _f("maintenance_loan_max_away_england", "student_finance", 10_830, "gbp_per_year",
       "England: maximum Maintenance Loan 2026/27, living away from parents outside London",
       URL_SFE_NEW_FULLTIME, CHECKED_2026_10_18),
    _f("maintenance_loan_max_london_england", "student_finance", 14_135, "gbp_per_year",
       "England: maximum Maintenance Loan 2026/27, living away from parents in London",
       URL_SFE_NEW_FULLTIME, CHECKED_2026_10_18),
    _f("student_loan_interest_plan5", "student_loan", 4.1, "percent",
       "Plan 5 student loan interest rate (current)", URL_STUDENT_LOAN_PAY, CHECKED_2026_10_18),
    _f("student_loan_interest_plan2_max", "student_loan", 6, "percent",
       "Plan 2 student loan interest rate: highest rate (income of £52,885 or more, or while studying)",
       URL_STUDENT_LOAN_PAY, CHECKED_2026_10_18),
    _f("inheritance_tax_threshold", "inheritance_tax", 325_000, "gbp",
       "Inheritance Tax threshold (no tax on the estate below it)", URL_INHERITANCE_TAX, CHECKED_2026_10_18),
    _f("inheritance_tax_rate", "inheritance_tax", 40, "percent",
       "Standard Inheritance Tax rate on the part of the estate above the threshold", URL_INHERITANCE_TAX,
       CHECKED_2026_10_18),
    _f("sdlt_first_time_buyer_threshold", "property_tax", 300_000, "gbp",
       "England and Northern Ireland: first-time buyers pay no Stamp Duty up to this price", URL_SDLT_RATES,
       CHECKED_2026_10_18),
    _f("sdlt_first_time_buyer_max_price", "property_tax", 500_000, "gbp",
       "First-time buyer Stamp Duty relief: not available above this price", URL_SDLT_RATES, CHECKED_2026_10_18),
    _f("distance_cancel_days", "consumer", 14, "count",
       "Days to cancel an order made online, by phone or by post, after delivery (downloads and streaming differ)",
       URL_DISTANCE_SELLING, CHECKED_2026_10_18),
    _f("fca_overdraft_simple_rate_year", "consumer", 2020, "date_year",
       "Since April 2020, banks can charge overdraft users only a simple annual interest rate, with no extra fees",
       URL_FCA_OVERDRAFT_CHARGES, CHECKED_2026_10_18),
    _f("fca_bnpl_regulated_year", "consumer", 2026, "date_year",
       "The FCA regulates Buy Now Pay Later (Deferred Payment Credit) from 15 July 2026: lenders must check you "
       "can afford it", URL_FCA_BNPL, CHECKED_2026_10_18),
    _f("fscs_general_insurance_share", "banking", 90, "percent",
       "FSCS repays this share of valid general insurance claims (home, travel, pet) if the insurer fails; "
       "compulsory insurance in full", URL_FSCS_INSURANCE, CHECKED_2026_10_18),
)

BY_ID: dict[str, RuleFact] = {f.id: f for f in FACTS}
TOPICS: tuple[Topic, ...] = (
    "isa", "income_tax", "scotland_income_tax", "national_insurance", "student_loan", "student_finance", "council_tax",
    "travel", "economy", "banking", "work", "pensions", "benefits", "childcare", "energy", "inheritance_tax",
    "property_tax", "consumer",
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
