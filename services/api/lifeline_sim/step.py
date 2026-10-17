"""One AGE: one year of money, stats, death and events.

Order inside a year (year t, region r):
1.  Age +1. Retire at state pension age (living costs drop to RETIRED_LIVING_SHARE).
2.  Pay: employed pay grows with regional median pay (ASHE). Pension income grows with CPI.
3.  Tax, NI, workplace pension, student loan repayment. Retirees draw the pension
    (gilt yield, at least PENSION_DRAWDOWN). A state top-up covers essential costs.
4.  Costs: living costs grow with CPI, capped at a share of take-home pay after housing.
    Rent, or mortgage payments at the deal rate (variable rate once a fix lapses).
5.  Cash flow. A shortfall draws savings, shares, crypto, pension (from PENSION_ACCESS_AGE),
    then borrows against home equity. Only a gap above the arranged overdraft is a missed
    payment (months short, max 12). The gap moves to card debt.
6.  Card debt interest and repayment from any accessible pot. If debt still exceeds the limit,
    the home is sold; only then are debts written off.
7.  Returns: savings (Bank Rate), investments (stock return), crypto, pension, house price change.
8.  Stats drift. Drawdown tracking. Death roll. Then 0-3 events.
"""

from __future__ import annotations

import math

from lifeline_contracts.macro import MacroKey
from lifeline_sim import params as p
from lifeline_sim.events.engine import draw_events
from lifeline_sim.index import IndexWeights
from lifeline_sim.macroview import PAY_GROWTH, MacroView
from lifeline_sim.mortgage import monthly_payment, remaining_balance
from lifeline_sim.occupations import occupation, public_pay_cap
from lifeline_sim.rng import uniform
from lifeline_sim.state import SimState
from lifeline_sim.tax import income_tax, national_insurance


def _clamp_stat(x: int) -> int:
    return max(0, min(100, x))


def _draw(s: SimState, amount: float) -> float:
    """Pay `amount` from savings, shares, crypto, then pension (if of age). Returns the unpaid rest."""
    pots = ["savings", "investments", "crypto"]
    if s.age >= p.PENSION_ACCESS_AGE:
        pots.append("pension")
    for pot in pots:
        if amount <= 0:
            break
        have = max(0.0, float(getattr(s, pot)))
        take = min(have, amount)
        setattr(s, pot, have - take)
        amount -= take
    return max(0.0, amount)


def _borrow_on_home(s: SimState, amount: float, bank_rate: float) -> float:
    """Secured borrowing against home equity, up to EQUITY_RELEASE_LTV. Returns the unpaid rest."""
    room = s.property_value * p.EQUITY_RELEASE_LTV - s.mortgage_balance
    take = min(max(0.0, room), amount)
    if take <= 0:
        return amount
    if s.mortgage_balance <= 0:
        s.housing = "mortgage"
        s.mortgage_years_left = max(p.EQUITY_RELEASE_MIN_YEARS, min(p.DEFAULT_MORTGAGE_TERM, 75 - s.age))
        s.mortgage_rate = round(bank_rate + p.VARIABLE_MARGIN, 2)
        s.mortgage_fixed_until = None
        s.mortgage_tracker = False
    s.mortgage_balance += take
    return amount - take


def _forced_sale(s: SimState, house_price: float) -> None:
    """Sell the home to clear debts. Equity after fees goes to savings; the household rents."""
    equity = s.property_value * (1 - p.FORCED_SALE_FEES) - s.mortgage_balance
    s.property_value = 0.0
    s.mortgage_balance = 0.0
    s.mortgage_rate = None
    s.mortgage_fixed_until = None
    s.mortgage_tracker = False
    s.mortgage_years_left = 0
    s.housing = "rent"
    s.rent = round(house_price * p.GROSS_RENT_YIELD / 12)
    if equity >= 0:
        s.savings += equity
    else:
        s.other_debt += -equity


def step_year(s: SimState, mv: MacroView, w: IndexWeights) -> None:
    """Advance the state by one year, in place. Sets `s.pending` to the new events."""
    if not s.alive:
        return
    s.year += 1
    s.age += 1
    s.last_graduated = False
    y, r = s.year, s.region
    occ = occupation(s.character.occupation)
    m = mv.env(y, r)
    cpi = m[MacroKey.CPI_INFLATION.value]
    bank = m[MacroKey.BANK_RATE.value]

    # 1-2. Work, retirement, pay growth
    if s.age >= p.STATE_PENSION_AGE and (s.employed or (s.income <= 0 and not s.student)):
        # State pension starts. Living costs drop only for people who stop work now.
        if s.employed:
            s.living *= p.RETIRED_LIVING_SHARE
        s.employed = False
        s.retired = True
        s.years_in_role = 0
        s.income = round(p.STATE_PENSION_SHARE_OF_MEDIAN_PAY * mv.value(MacroKey.MEDIAN_PAY, y, None, 35_000.0))
    elif s.student and s.age >= p.GRADUATION_AGE:
        s.student = False
        s.employed = True
        s.last_graduated = True
        s.years_in_role = 0
        s.job_title = "Graduate"
        s.income = round(p.GRADUATE_PAY_SHARE * mv.value(MacroKey.MEDIAN_PAY, y, r, 30_000.0))
        s.rent = round(s.rent / p.STUDENT_RENT_SHARE)
    elif s.employed:
        growth = m[PAY_GROWTH] / 100
        cap = public_pay_cap(y) if occ.public_sector else None
        if cap is not None:
            growth = min(growth, cap / 100)
        s.income *= 1 + max(-0.1, min(0.2, growth))
        s.years_in_role += 1
    elif s.retired:
        s.income *= 1 + max(0.0, cpi) / 100

    # 3. Take-home pay. Bonus follows the stock market for occupations that have one.
    bonus = s.income * occ.bonus_rate(m[MacroKey.STOCK_RETURN.value]) if s.employed else 0.0
    gross = s.income + bonus
    drawdown = 0.0
    if s.retired and s.pension > 0:
        # Drawdown rate: the 10-year gilt yield (an annuity proxy), at least PENSION_DRAWDOWN.
        rate = max(p.PENSION_DRAWDOWN, m[MacroKey.GILT_10Y.value] / 100)
        drawdown = s.pension * rate
        s.pension -= drawdown
    tax = income_tax(gross + drawdown)
    ni = national_insurance(gross) if s.employed else 0.0
    pension_in = s.income * p.PENSION_EMPLOYEE if s.employed else 0.0
    employer_in = s.income * p.PENSION_EMPLOYER if s.employed else 0.0
    sl_repay = 0.0
    if s.student_loan > 0 and s.employed:
        sl_repay = min(s.student_loan, p.STUDENT_LOAN_RATE * max(0.0, gross - p.STUDENT_LOAN_THRESHOLD))
    maintenance = p.MAINTENANCE_LOAN_2024 * m["price_level"] if s.student else 0.0
    s.student_loan += maintenance
    net = gross + drawdown + maintenance - tax - ni - pension_in - sl_repay
    s.pension += pension_in + employer_in
    s.student_loan = (s.student_loan - sl_repay) * (1 + max(0.0, cpi) / 100)

    # 4. Costs
    housing = 0.0
    if s.housing == "rent":
        housing = 12 * s.rent
    elif s.housing == "mortgage" and s.mortgage_balance > 0:
        if s.mortgage_fixed_until is None or y > s.mortgage_fixed_until:
            s.mortgage_tracker = False
            s.mortgage_rate = round(bank + p.VARIABLE_MARGIN, 2)
        elif s.mortgage_tracker:
            s.mortgage_rate = round(bank + p.TRACKER_MARGIN, 2)
        rate = max(0.0, s.mortgage_rate or 0.0)
        years_left = max(1, s.mortgage_years_left)
        housing = 12 * monthly_payment(s.mortgage_balance, rate, years_left)
        s.mortgage_balance = remaining_balance(s.mortgage_balance, rate, years_left, 12)
        s.mortgage_years_left = years_left - 1
        if s.mortgage_years_left <= 0 or s.mortgage_balance < 1:
            s.mortgage_balance = 0.0
            s.housing = "own"
            s.mortgage_rate = None
            s.mortgage_fixed_until = None
    # Living costs follow prices, but a household cannot keep spending more than it earns:
    # they are capped at a share of take-home pay left after housing, with a floor.
    floor = p.MIN_LIVING_MONTHLY_2024 * m["price_level"]
    # State top-up (Universal Credit / Pension Credit proxy): covers the gap between take-home
    # pay and essential costs (floor living costs + housing), up to the benefit cap.
    benefits = 0.0
    if not s.student:
        benefits = min(max(0.0, 12 * floor + housing - net), p.BENEFIT_CAP_2024 * m["price_level"])
    net += benefits
    cap = max(floor, (p.LIVING_MAX_SHARE_OF_NET * net - housing) / 12)
    s.living = max(floor, min(s.living * (1 + cpi / 100), cap))
    costs = housing + 12 * s.living

    # 5. Cash flow and missed payments. A shortfall draws on savings, shares, crypto and
    # (from PENSION_ACCESS_AGE) the pension before any payment is missed.
    s.cash += net - costs
    if s.cash < 0:
        s.cash = -_draw(s, -s.cash)
    if s.cash < 0:
        s.cash = -_borrow_on_home(s, -s.cash, bank)
    missed = 0
    if s.cash < 0:
        short = -s.cash
        # An arranged overdraft absorbs small gaps. Only the part above it is a missed payment.
        headroom = max(0.0, p.OVERDRAFT_2024 * m["price_level"] - s.other_debt)
        unpaid = short - min(short, headroom)
        if unpaid > 0:
            missed = min(12, math.ceil(unpaid / max(costs / 12, 1.0)))
        s.other_debt += short
        s.cash = 0.0
    s.missed += missed

    # 6. Debt interest, repayment, debt relief, savings sweep
    s.other_debt *= 1 + max(0.0, bank + p.CARD_SPREAD) / 100
    monthly = costs / 12
    spare = s.cash - p.DEBT_BUFFER_MONTHS * monthly
    if s.other_debt > 0 and spare > 0:
        pay = min(s.other_debt, spare)
        s.other_debt -= pay
        s.cash -= pay
    if s.other_debt > 0:
        # Card debt costs more than any asset earns: repay it from savings, shares, crypto, pension.
        s.other_debt = _draw(s, s.other_debt)
    s.last_bankrupt = False
    s.last_forced_sale = False
    limit = p.BANKRUPTCY_DEBT_TO_INCOME * max(s.income, p.BANKRUPTCY_INCOME_FLOOR_2024 * m["price_level"])
    if s.other_debt > limit and s.property_value > 0:
        _forced_sale(s, mv.value(MacroKey.HOUSE_PRICE, y, r, s.property_value))
        s.other_debt = _draw(s, s.other_debt)
        s.last_forced_sale = True
    if s.other_debt > limit:
        s.other_debt = 0.0
        s.last_bankrupt = True
        s.happiness = _clamp_stat(s.happiness - 15)
    excess = s.cash - p.CASH_BUFFER_MONTHS * monthly
    if excess > 0:
        s.cash -= excess
        s.savings += excess

    # 7. Returns
    s.savings *= 1 + max(p.SAVINGS_FLOOR, bank + p.SAVINGS_SPREAD) / 100
    stock = m[MacroKey.STOCK_RETURN.value]
    gilt = m[MacroKey.GILT_10Y.value]
    s.investments *= 1 + stock / 100
    if mv.has(MacroKey.CRYPTO_RETURN):
        s.crypto *= 1 + max(-95.0, m[MacroKey.CRYPTO_RETURN.value]) / 100
    s.pension *= 1 + (p.PENSION_STOCK_SHARE * stock + (1 - p.PENSION_STOCK_SHARE) * gilt) / 100
    s.property_value *= 1 + m[MacroKey.HOUSE_PRICE_CHANGE.value] / 100

    # 8. Stats
    if s.age >= 75:
        s.health = _clamp_stat(s.health - 2)
    elif s.age >= 45 or (s.age >= 30 and s.age % 2 == 0):
        s.health = _clamp_stat(s.health - 1)
    if s.age < 25:
        s.smarts = _clamp_stat(s.smarts + 1)
    elif s.age > 75:
        s.smarts = _clamp_stat(s.smarts - 1)
    mood = (65 - s.happiness) // 5
    if missed:
        mood -= 6
    if net - costs > 0:
        mood += 1
    s.happiness = _clamp_stat(s.happiness + mood)

    s.last_bonus = bonus
    s.last_bonus_net = bonus * (net / gross) if gross > 0 else 0.0
    s.last_net_income = net
    s.last_costs = costs
    s.last_missed = missed
    s.track_drawdown(w)

    # Death
    hazard = p.GOMPERTZ_A * math.exp(p.GOMPERTZ_B * s.age) * (0.6 + (100 - s.health) / 100)
    if s.age >= p.MAX_AGE or s.health <= 0 or uniform(s.seed, y, "death") < hazard:
        s.alive = False
        s.cause_of_death = "Old age" if s.age >= 75 else ("Poor health" if s.health <= 20 else "Illness")
        s.pending = []
        return

    s.pending = draw_events(s, mv)
