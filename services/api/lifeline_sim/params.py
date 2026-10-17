"""Fixed game rules. Index weights live in `config/index.toml`, not here.

Every money rule that is not read from the MacroTable is a named constant in this file,
so each number in the game traces to data or to a rule here.
"""

from __future__ import annotations

PRESENT_YEAR = 2026
MAX_AGE = 110
MIN_START_AGE = 16
MAX_EVENTS_PER_YEAR = 3
# Cooldown: a template that fired in year Y cannot fire in Y+1 or Y+2, unless it is marked
# `repeatable` (with a reason) or it is a focused "Test it" event inside the scenario period.
EVENT_COOLDOWN_YEARS = 3

# Income tax and National Insurance, 2025/26 rUK bands. Applied to every year (simplification).
PERSONAL_ALLOWANCE = 12_570.0
ALLOWANCE_TAPER_START = 100_000.0
BASIC_LIMIT = 50_270.0
HIGHER_LIMIT = 125_140.0
BASIC_RATE = 0.20
HIGHER_RATE = 0.40
ADDITIONAL_RATE = 0.45
NI_MAIN_RATE = 0.08
NI_UPPER_RATE = 0.02

# Workplace pension (auto-enrolment minimums).
PENSION_EMPLOYEE = 0.05
PENSION_EMPLOYER = 0.03
PENSION_DRAWDOWN = 0.04  # minimum yearly drawdown in retirement; the gilt yield is used when higher
PENSION_ACCESS_AGE = 57  # UK normal minimum pension age from 2028
PENSION_STOCK_SHARE = 0.6  # rest follows the 10-year gilt yield

# Student loan, Plan 2.
STUDENT_LOAN_RATE = 0.09
STUDENT_LOAN_THRESHOLD = 27_295.0

# Students: maintenance loan while studying, a graduate job at GRADUATION_AGE.
GRADUATION_AGE = 22
MAINTENANCE_LOAN_2024 = 10_000.0  # per year, 2024 pounds, scaled by CPI; adds to the student loan
STUDENT_RENT_SHARE = 0.6  # shared student housing
GRADUATE_PAY_SHARE = 0.85  # graduate pay as share of regional median pay

# Debt relief: card debt above this many years of income (or of the floor) is written off,
# and savings, shares and crypto are taken. Models bankruptcy or an IVA.
BANKRUPTCY_DEBT_TO_INCOME = 3.0
BANKRUPTCY_INCOME_FLOOR_2024 = 10_000.0

# State pension.
STATE_PENSION_AGE = 66
STATE_PENSION_SHARE_OF_MEDIAN_PAY = 0.32

# Spreads over Bank Rate.
# Variable mortgage rate = Bank Rate + margin. Label: "Bank Rate + 2.0 points", an approximate
# average margin of UK variable mortgages over Bank Rate (BoE Bankstats, effective rates, 2000-2024).
VARIABLE_MARGIN = 2.0
CARD_SPREAD = 18.0  # unsecured debt APR = Bank Rate + spread
SAVINGS_SPREAD = -0.5  # easy-access savings = Bank Rate + spread, floor below
SAVINGS_FLOOR = 0.1

# Household budget at the start of a life.
LIVING_SHARE_OF_NET = 0.55  # monthly living costs (no housing) as share of net pay
GROSS_RENT_YIELD = 0.045  # monthly rent = regional house price * yield / 12
MIN_LIVING_MONTHLY_2024 = 650.0  # floor, 2024 pounds, scaled by CPI
STARTING_CASH_MONTHS = 1.0
LIVING_MAX_SHARE_OF_NET = 0.9  # living + housing costs cannot grow above this share of take-home pay
RETIRED_LIVING_SHARE = 0.7  # living costs drop to this share at retirement
BENEFIT_CAP_2024 = 22_020.0  # yearly state top-up limit, 2024 pounds (benefit cap outside London)
OVERDRAFT_2024 = 1_000.0  # arranged overdraft, 2024 pounds; gaps within it are not missed payments
FORCED_SALE_FEES = 0.03
EQUITY_RELEASE_LTV = 0.75  # a shortfall can be borrowed against the home up to this loan-to-value
EQUITY_RELEASE_MIN_YEARS = 5  # agent and legal fees on a forced home sale
CASH_BUFFER_MONTHS = 6.0  # cash above this many months of costs moves to savings
DEBT_BUFFER_MONTHS = 3.0  # cash above this repays card debt
DEFAULT_MORTGAGE_TERM = 25
FIRST_FIX_YEARS = 2
# Tracker mortgage = Bank Rate + margin for the deal length. Approximate typical UK tracker margin
# over Bank Rate (BoE quoted rates, 2-year trackers, 2010-2024).
TRACKER_MARGIN = 1.0
TRACKER_DEAL_YEARS = 2

# "Test it" scenarios (ADR 0018). A focused tag makes its templates fire (probability 1) whenever
# the data gives them any chance. Focused events come first and do not count toward MAX_EVENTS_PER_YEAR.
FOCUS_PRIORITY_BOOST = 100
# Tags whose events follow from a focused tag's choice (for example a tracker meets Bank Rate rises).
# They keep their own odds but, like focused events, sit outside the yearly cap.
FOCUS_RELATED: dict[str, tuple[str, ...]] = {
    "mortgage_deal_end": ("mortgage_rate_change",),
    "mortgage_rate_change": ("mortgage_deal_end",),
    "energy_bill": ("energy_bill",),
}

# Mortality: Gompertz hazard q(age) = A * exp(B * age), scaled by health.
GOMPERTZ_A = 2.5e-5
GOMPERTZ_B = 0.095

# Tab actions (lifeline_sim/actions.py). Money amounts are 2024 pounds, scaled by the CPI price level.
ACTION_DEPOSIT_SHARE = 0.10  # deposit for "Buy a home"
HOME_BUY_FEES_2024 = 1_800.0  # legal, survey and lender fees
HOME_SELL_FEES = 0.025  # agent and legal fees as share of the sale price
USED_CAR_2024 = 3_500.0
CAR_RUNNING_MONTHLY_2024 = 150.0  # insurance, tax, fuel, servicing
DATING_COST_2024 = 300.0
SMALL_WEDDING_2024 = 3_000.0
BREAK_UP_COST_2024 = 2_500.0  # legal and moving costs when married
CHILD_MONTHLY_2024 = 450.0  # extra household costs per child
FAMILY_VISIT_2024 = 200.0
GYM_YEAR_2024 = 300.0
HOLIDAY_2024 = 1_200.0
COURSE_2024 = 800.0
PENSION_TAX_RELIEF = 0.25  # basic-rate relief: £80 paid in becomes £100
ACTION_SPENDING_CUT = 0.05
MAX_PERSONAL_LOAN_2024 = 25_000.0
MAX_ACTION_AMOUNT = 10_000_000.0
CRYPTO_FROM_YEAR = 2013
