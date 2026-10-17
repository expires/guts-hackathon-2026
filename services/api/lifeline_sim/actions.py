"""Tab actions: Job, Assets, Relationships, Activities, Money (BUILD_SPEC core loop step 3).

Rules (ADR 0012):
- An action is a decision. Its id is `act-<year>-<n>` and its choice id is
  `<tab>/<action>` plus `?k=v&...` with the parameters in key order. Replay applies it in the
  recorded order with the events of that year. The autopilot twin takes no actions.
- Outcomes are deterministic. A random action rolls `uniform(seed, decision_id, "action", id)`.
- Prices come from the MacroTable for the person's region and year (house prices, pay, rates)
  or from named rules in `params`, scaled by the CPI price level.
- An action with a random outcome can run once per year. Money moves can run any number of times.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import parse_qsl

from lifeline_contracts.domain import AvailableAction, Deltas, Relationship, Tab
from lifeline_contracts.macro import MacroKey
from lifeline_sim import params as p
from lifeline_sim.events.engine import set_married, set_partner
from lifeline_sim.macroview import MacroView
from lifeline_sim.mortgage import monthly_payment
from lifeline_sim.rng import uniform
from lifeline_sim.state import SimState

ACTION_PREFIX = "act"
TABS: tuple[Tab, ...] = ("job", "assets", "relationships", "activities", "money")


@dataclass(frozen=True)
class ActionCtx:
    s: SimState
    mv: MacroView
    params: Mapping[str, float]
    roll: float  # uniform in [0, 1), keyed by the decision id

    @property
    def pl(self) -> float:
        return self.mv.price_level(self.s.year)

    def macro(self, key: MacroKey, default: float, regional: bool = True) -> float:
        return self.mv.value(key, self.s.year, self.s.region if regional else None, default)


@dataclass(frozen=True)
class ActionResultText:
    text: str
    good: bool
    facts: dict[str, float]


Apply = Callable[[ActionCtx], ActionResultText]
Avail = Callable[[SimState, MacroView], bool]


@dataclass(frozen=True)
class ActionSpec:
    tab: Tab
    id: str
    label: str
    emoji: str
    hint: str
    available: Avail
    apply: Apply
    concept_id: str | None = None
    once_per_year: bool = True
    amount: bool = False  # takes an `amount` parameter in pounds


# ---------- helpers ----------


def _liquid(s: SimState) -> float:
    return max(0.0, s.cash) + max(0.0, s.savings)


def _spend(s: SimState, amount: float) -> None:
    """Pay from cash, then savings. Any rest goes on the card."""
    take = min(max(0.0, s.cash), amount)
    s.cash -= take
    amount -= take
    take = min(max(0.0, s.savings), amount)
    s.savings -= take
    amount -= take
    if amount > 0:
        s.other_debt += amount


def _take(s: SimState, amount: float) -> float:
    """Take up to `amount` from cash, then savings, without borrowing. Returns what was taken."""
    amount = max(0.0, min(amount, _liquid(s)))
    _spend(s, amount)
    return amount


def _stat(s: SimState, name: str, delta: int) -> None:
    setattr(s, name, int(max(0, min(100, getattr(s, name) + delta))))


def _amount(c: ActionCtx, default: float) -> float:
    v = c.params.get("amount", default)
    return max(0.0, round(float(v), 2))


def _r(x: float) -> float:
    return float(round(x))


# ---------- job ----------


def _ask_raise(c: ActionCtx) -> ActionResultText:
    s = c.s
    growth = max(0.0, c.mv.growth(MacroKey.MEDIAN_PAY, s.year, s.region) * 100)
    rise_pct = round(min(8.0, growth + 2.0), 1)
    chance = max(0.1, min(0.7, 0.25 + s.smarts / 400 + min(s.years_in_role, 10) * 0.02))
    rise = _r(s.income * rise_pct / 100)
    facts = {"rise_pct": rise_pct, "rise_amount": rise, "chance_pct": round(chance * 100)}
    if c.roll < chance:
        s.income += rise
        _stat(s, "happiness", 3)
        return ActionResultText(
            f"Your boss said yes. Your pay rises {rise_pct:.1f}%, £{rise:,.0f} a year.", True, facts
        )
    _stat(s, "happiness", -3)
    return ActionResultText("Your boss said not this year.", False, facts)


def _new_job(c: ActionCtx) -> ActionResultText:
    s = c.s
    median = c.macro(MacroKey.MEDIAN_PAY, 30_000.0)
    unemp = c.macro(MacroKey.UNEMPLOYMENT, 5.0)
    chance = max(0.1, min(0.8, 0.75 - unemp / 20 + (s.smarts - 50) / 200))
    offer = _r(max(s.income * 1.05, median * (0.9 + s.smarts / 250)))
    facts = {"offer": offer, "unemployment_pct": round(unemp, 1), "chance_pct": round(chance * 100)}
    if c.roll < chance:
        s.income = offer
        s.years_in_role = 0
        s.job_title = f"New {s.character.occupation}".strip()
        _stat(s, "happiness", 4)
        return ActionResultText(f"You got a new job on £{offer:,.0f} a year.", True, facts)
    _stat(s, "happiness", -2)
    return ActionResultText(
        f"No offer this year. Unemployment in your area is {unemp:.1f}%, so jobs are hard to get.", False, facts
    )


def _quit(c: ActionCtx) -> ActionResultText:
    s = c.s
    lost = _r(s.income)
    s.employed = False
    s.income = 0.0
    s.years_in_role = 0
    _stat(s, "happiness", 4)
    return ActionResultText(f"You quit. You give up £{lost:,.0f} a year of pay.", False, {"lost_pay": lost})


def _find_work(c: ActionCtx) -> ActionResultText:
    s = c.s
    median = c.macro(MacroKey.MEDIAN_PAY, 30_000.0)
    unemp = c.macro(MacroKey.UNEMPLOYMENT, 5.0)
    chance = max(0.15, min(0.85, 0.85 - unemp / 15))
    pay = _r(median * p.GRADUATE_PAY_SHARE)
    facts = {"pay": pay, "unemployment_pct": round(unemp, 1), "chance_pct": round(chance * 100)}
    if c.roll < chance:
        s.employed = True
        s.income = pay
        s.years_in_role = 0
        s.job_title = s.character.occupation.capitalize()
        _stat(s, "happiness", 5)
        return ActionResultText(f"You found work on £{pay:,.0f} a year.", True, facts)
    _stat(s, "happiness", -3)
    return ActionResultText(f"No luck yet. Unemployment in your area is {unemp:.1f}%.", False, facts)


def _retire(c: ActionCtx) -> ActionResultText:
    s = c.s
    lost = _r(s.income)
    s.employed = False
    s.retired = True
    s.income = 0.0
    s.years_in_role = 0
    s.living *= p.RETIRED_LIVING_SHARE
    _stat(s, "happiness", 6)
    return ActionResultText(
        f"You retired early. Your pension pot of £{s.pension:,.0f} now pays your way. State pension starts at "
        f"{p.STATE_PENSION_AGE}.",
        True,
        {"lost_pay": lost, "pension_pot": _r(s.pension), "state_pension_age": float(p.STATE_PENSION_AGE)},
    )


# ---------- assets ----------


def _home_price(c: ActionCtx) -> float:
    return _r(c.macro(MacroKey.HOUSE_PRICE, 200_000.0) * 0.8)


def _deposit(c: ActionCtx) -> float:
    return _r(_home_price(c) * p.ACTION_DEPOSIT_SHARE)


def _can_buy_home(s: SimState, mv: MacroView) -> bool:
    if s.housing != "rent" or not s.employed:
        return False
    if not _has_data(mv, s, MacroKey.HOUSE_PRICE, MacroKey.MORTGAGE_2Y_FIX):
        return False
    price = mv.value(MacroKey.HOUSE_PRICE, s.year, s.region, 200_000.0) * 0.8
    return _liquid(s) >= price * p.ACTION_DEPOSIT_SHARE + p.HOME_BUY_FEES_2024 * mv.price_level(s.year)


def _buy_home(c: ActionCtx) -> ActionResultText:
    s = c.s
    price = _home_price(c)
    deposit = _deposit(c)
    fees = _r(p.HOME_BUY_FEES_2024 * c.pl)
    rate = round(c.mv.value(MacroKey.MORTGAGE_2Y_FIX, s.year, None, 4.5), 2)
    loan = price - deposit
    years = max(10, min(p.DEFAULT_MORTGAGE_TERM, 70 - s.age))
    payment = _r(monthly_payment(loan, rate, years))
    _spend(s, deposit + fees)
    s.property_value += price
    s.mortgage_balance += loan
    s.housing = "mortgage"
    s.rent = 0.0
    s.mortgage_rate = rate
    s.mortgage_fixed_until = s.year + p.FIRST_FIX_YEARS
    s.mortgage_tracker = False
    s.mortgage_years_left = years
    _stat(s, "happiness", 8)
    return ActionResultText(
        f"You bought a home for £{price:,.0f} with a £{deposit:,.0f} deposit. A 2-year fix at {rate:.2f}% costs "
        f"about £{payment:,.0f} a month.",
        True,
        {"price": price, "deposit": deposit, "fees": fees, "rate": rate, "payment": payment},
    )


def _sell_home(c: ActionCtx) -> ActionResultText:
    s = c.s
    value = _r(s.property_value)
    fees = _r(value * p.HOME_SELL_FEES)
    owed = _r(s.mortgage_balance)
    equity = value - fees - owed
    rent = _r(c.macro(MacroKey.HOUSE_PRICE, 200_000.0) * p.GROSS_RENT_YIELD / 12)
    s.property_value = 0.0
    s.mortgage_balance = 0.0
    s.mortgage_rate = None
    s.mortgage_fixed_until = None
    s.mortgage_tracker = False
    s.mortgage_years_left = 0
    s.housing = "rent"
    s.rent = rent
    if equity >= 0:
        s.savings += equity
    else:
        s.other_debt += -equity
    _stat(s, "happiness", -4)
    return ActionResultText(
        f"You sold your home for £{value:,.0f}. After £{fees:,.0f} fees and the £{owed:,.0f} mortgage, "
        f"£{equity:,.0f} is left. You now rent for £{rent:,.0f} a month.",
        equity > 0,
        {"value": value, "fees": fees, "owed": owed, "equity": equity, "rent": rent},
    )


def _overpay(c: ActionCtx) -> ActionResultText:
    s = c.s
    amount = min(_amount(c, s.savings * 0.25), s.mortgage_balance)
    paid = _take(s, amount)
    s.mortgage_balance -= paid
    rate = s.mortgage_rate or 0.0
    saved = _r(paid * rate / 100)
    if s.mortgage_balance < 1:
        s.mortgage_balance = 0.0
        s.housing = "own"
        s.mortgage_rate = None
        s.mortgage_fixed_until = None
        s.mortgage_years_left = 0
    return ActionResultText(
        f"You paid £{paid:,.0f} off your mortgage. At {rate:.2f}% that saves about £{saved:,.0f} of interest a year.",
        paid > 0,
        {"amount": _r(paid), "rate": rate, "interest_saved": saved},
    )


def _move_in(c: ActionCtx, pot: str, label: str, default_share: float) -> ActionResultText:
    s = c.s
    amount = _take(s, _amount(c, _liquid(s) * default_share))
    setattr(s, pot, getattr(s, pot) + amount)
    return ActionResultText(f"You put £{amount:,.0f} into {label}.", amount > 0, {"amount": _r(amount)})


def _move_out(c: ActionCtx, pot: str, label: str) -> ActionResultText:
    s = c.s
    have = max(0.0, float(getattr(s, pot)))
    amount = min(_amount(c, have), have)
    setattr(s, pot, have - amount)
    s.savings += amount
    return ActionResultText(
        f"You sold £{amount:,.0f} of {label} and moved it to savings.", True, {"amount": _r(amount)}
    )


def _buy_shares(c: ActionCtx) -> ActionResultText:
    return _move_in(c, "investments", "a shares fund", 0.2)


def _sell_shares(c: ActionCtx) -> ActionResultText:
    return _move_out(c, "investments", "shares")


def _buy_crypto(c: ActionCtx) -> ActionResultText:
    return _move_in(c, "crypto", "crypto", 0.05)


def _sell_crypto(c: ActionCtx) -> ActionResultText:
    return _move_out(c, "crypto", "crypto")


def _buy_car(c: ActionCtx) -> ActionResultText:
    s = c.s
    cost = _r(p.USED_CAR_2024 * c.pl)
    running = _r(p.CAR_RUNNING_MONTHLY_2024 * c.pl)
    _spend(s, cost)
    s.has_car = True
    s.living += running
    _stat(s, "happiness", 4)
    return ActionResultText(
        f"You bought a used car for £{cost:,.0f}. It costs about £{running:,.0f} a month to run.",
        False,
        {"cost": cost, "running_monthly": running},
    )


def _sell_car(c: ActionCtx) -> ActionResultText:
    s = c.s
    value = _r(p.USED_CAR_2024 * c.pl * 0.5)
    running = _r(p.CAR_RUNNING_MONTHLY_2024 * c.pl)
    s.cash += value
    s.has_car = False
    s.living = max(0.0, s.living - running)
    _stat(s, "happiness", -3)
    return ActionResultText(
        f"You sold the car for £{value:,.0f} and save about £{running:,.0f} a month.",
        True,
        {"value": value, "running_monthly": running},
    )


# ---------- relationships ----------


def _date(c: ActionCtx) -> ActionResultText:
    s = c.s
    cost = _r(p.DATING_COST_2024 * c.pl)
    _spend(s, cost)
    if c.roll < 0.4:
        set_partner(s, True)
        _stat(s, "happiness", 8)
        return ActionResultText(f"You met someone special. Dates cost £{cost:,.0f}.", True, {"cost": cost})
    _stat(s, "happiness", -1)
    return ActionResultText(f"No spark this year. Dates cost £{cost:,.0f}.", False, {"cost": cost})


def _propose(c: ActionCtx) -> ActionResultText:
    s = c.s
    cost = _r(p.SMALL_WEDDING_2024 * c.pl)
    if c.roll < 0.8:
        _spend(s, cost)
        set_married(s, True)
        _stat(s, "happiness", 10)
        return ActionResultText(f"They said yes. A small wedding cost £{cost:,.0f}.", True, {"cost": cost})
    _stat(s, "happiness", -8)
    return ActionResultText("They said they are not ready.", False, {"cost": cost})


def _break_up(c: ActionCtx) -> ActionResultText:
    s = c.s
    cost = _r(p.BREAK_UP_COST_2024 * c.pl) if s.married else 0.0
    _spend(s, cost)
    set_partner(s, False)
    _stat(s, "happiness", -10)
    return ActionResultText(
        f"You split up. Legal and moving costs were £{cost:,.0f}." if cost else "You split up.", False, {"cost": cost}
    )


def _baby(c: ActionCtx) -> ActionResultText:
    s = c.s
    monthly = _r(p.CHILD_MONTHLY_2024 * c.pl)
    if c.roll < 0.5:
        s.children += 1
        s.relationships.append(
            Relationship(
                id=f"rl-child-{s.children}", kind="child", name=f"Child {s.children}", emoji="👶", closeness=95
            )
        )
        s.living += monthly
        _stat(s, "happiness", 10)
        _stat(s, "health", -2)
        return ActionResultText(
            f"A baby arrives. Costs go up about £{monthly:,.0f} a month.", True, {"child_monthly": monthly}
        )
    return ActionResultText("No baby this year.", False, {"child_monthly": monthly})


def _family_time(c: ActionCtx) -> ActionResultText:
    s = c.s
    cost = _r(p.FAMILY_VISIT_2024 * c.pl)
    _spend(s, cost)
    s.relationships = [
        r.model_copy(update={"closeness": min(100, r.closeness + 5)}) if r.kind != "ex" else r for r in s.relationships
    ]
    _stat(s, "happiness", 4)
    return ActionResultText(f"You spent time with family. Travel cost £{cost:,.0f}.", True, {"cost": cost})


# ---------- activities ----------


def _paid_activity(
    c: ActionCtx, cost_2024: float, stats: dict[str, int], text: str, good: bool = True
) -> ActionResultText:
    cost = _r(cost_2024 * c.pl)
    _spend(c.s, cost)
    for k, v in stats.items():
        _stat(c.s, k, v)
    return ActionResultText(text.format(cost=cost), good, {"cost": cost})


def _gym(c: ActionCtx) -> ActionResultText:
    return _paid_activity(
        c, p.GYM_YEAR_2024, {"health": 4, "happiness": 1}, "A year of gym sessions cost £{cost:,.0f}."
    )


def _holiday(c: ActionCtx) -> ActionResultText:
    return _paid_activity(c, p.HOLIDAY_2024, {"happiness": 8}, "A week away cost £{cost:,.0f}.", good=False)


def _course(c: ActionCtx) -> ActionResultText:
    return _paid_activity(c, p.COURSE_2024, {"smarts": 5}, "An evening course cost £{cost:,.0f}.")


def _doctor(c: ActionCtx) -> ActionResultText:
    return _paid_activity(c, 0.0, {"health": 3}, "A check-up on the NHS. It cost nothing.")


def _volunteer(c: ActionCtx) -> ActionResultText:
    return _paid_activity(c, 0.0, {"happiness": 3, "smarts": 1}, "You volunteered at a food bank.")


def _walks(c: ActionCtx) -> ActionResultText:
    return _paid_activity(c, 0.0, {"health": 2, "happiness": 1}, "You walked every weekend. It cost nothing.")


# ---------- money ----------


def _save(c: ActionCtx) -> ActionResultText:
    s = c.s
    amount = min(_amount(c, max(0.0, s.cash) * 0.5), max(0.0, s.cash))
    s.cash -= amount
    s.savings += amount
    return ActionResultText(f"You moved £{amount:,.0f} to savings.", True, {"amount": _r(amount)})


def _withdraw(c: ActionCtx) -> ActionResultText:
    s = c.s
    amount = min(_amount(c, s.savings * 0.25), max(0.0, s.savings))
    s.savings -= amount
    s.cash += amount
    return ActionResultText(f"You took £{amount:,.0f} out of savings.", False, {"amount": _r(amount)})


def _pay_debt(c: ActionCtx) -> ActionResultText:
    s = c.s
    paid = _take(s, min(_amount(c, s.other_debt), s.other_debt))
    s.other_debt -= paid
    apr = (
        _card_apr(c)
        if c.mv.strict
        else (c.mv.value(MacroKey.CARD_RATE, s.year, None, 20.0) if c.mv.has(MacroKey.CARD_RATE) else 20.0)
    )
    saved = _r(paid * apr / 100)
    _stat(s, "happiness", 2)
    return ActionResultText(
        f"You paid off £{paid:,.0f} of card debt. At {apr:.1f}% that saves about £{saved:,.0f} a year.",
        True,
        {"amount": _r(paid), "apr": round(apr, 2), "interest_saved": saved},
    )


def _pension_topup(c: ActionCtx) -> ActionResultText:
    s = c.s
    paid = _take(s, _amount(c, _liquid(s) * 0.1))
    relief = _r(paid * p.PENSION_TAX_RELIEF)
    s.pension += paid + relief
    return ActionResultText(
        f"You paid £{paid:,.0f} into your pension. Tax relief added £{relief:,.0f}.",
        True,
        {"amount": _r(paid), "tax_relief": relief},
    )


def _cut_spending(c: ActionCtx) -> ActionResultText:
    s = c.s
    cut = _r(s.living * p.ACTION_SPENDING_CUT)
    s.living -= cut
    _stat(s, "happiness", -2)
    return ActionResultText(f"You cut your spending by £{cut:,.0f} a month.", True, {"monthly_cut": cut})


def _borrow(c: ActionCtx) -> ActionResultText:
    s = c.s
    amount = min(_amount(c, 1000.0 * c.pl), p.MAX_PERSONAL_LOAN_2024 * c.pl)
    s.cash += amount
    s.other_debt += amount
    apr = (
        _card_apr(c)
        if c.mv.strict
        else (c.mv.value(MacroKey.CARD_RATE, s.year, None, 20.0) if c.mv.has(MacroKey.CARD_RATE) else 20.0)
    )
    return ActionResultText(
        f"You borrowed £{amount:,.0f} at about {apr:.1f}% a year.", False, {"amount": _r(amount), "apr": round(apr, 2)}
    )


# ---------- catalogue ----------


def _has_data(mv: MacroView, s: SimState, *keys: MacroKey) -> bool:
    """Live mode (ADR 0027): an action priced from data needs real values for this year."""
    return not mv.strict or all(mv.opt(k, s.year, s.region) is not None for k in keys)


def _card_apr(c: ActionCtx) -> float:
    v = c.mv.opt(MacroKey.CARD_RATE, c.s.year)
    if v is not None:
        return v
    bank = c.mv.opt(MacroKey.BANK_RATE, c.s.year)
    return (bank if bank is not None else 0.0) + p.CARD_SPREAD


def _always(s: SimState, mv: MacroView) -> bool:
    return s.alive


def _working_age(s: SimState) -> bool:
    return s.alive and not s.retired and s.age < p.STATE_PENSION_AGE


ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec(
        "job", "ask_raise", "Ask for a raise", "💷", "A chance of more pay",
        lambda s, mv: s.employed, _ask_raise, "job-security",
    ),
    ActionSpec(
        "job", "new_job", "Look for a better job", "🔎", "Odds follow local unemployment",
        lambda s, mv: s.employed and _has_data(mv, s, MacroKey.MEDIAN_PAY, MacroKey.UNEMPLOYMENT),
        _new_job, "job-security",
    ),
    ActionSpec(
        "job", "find_work", "Find work", "📋", "Odds follow local unemployment",
        lambda s, mv: not s.employed and not s.student and _working_age(s)
        and _has_data(mv, s, MacroKey.MEDIAN_PAY, MacroKey.UNEMPLOYMENT),
        _find_work, "job-security",
    ),
    ActionSpec("job", "quit", "Quit your job", "🚪", "No pay until you find work", lambda s, mv: s.employed, _quit),
    ActionSpec(
        "job", "retire", "Retire early", "🏖️", "Live on your pension pot",
        lambda s, mv: s.employed and s.age >= p.PENSION_ACCESS_AGE, _retire, "pensions",
    ),
    ActionSpec(
        "assets", "buy_home", "Buy a home", "🏡", "Deposit, fees and a 2-year fix",
        _can_buy_home, _buy_home, "house-prices",
    ),
    ActionSpec(
        "assets", "sell_home", "Sell your home", "🪧", "Fees, then you rent",
        lambda s, mv: s.property_value > 0 and _has_data(mv, s, MacroKey.HOUSE_PRICE), _sell_home, "house-prices",
    ),
    ActionSpec(
        "assets", "overpay_mortgage", "Overpay the mortgage", "🏦", "Less interest from now on",
        lambda s, mv: s.mortgage_balance > 0 and _liquid(s) > 0, _overpay, "interest-rates", False, True,
    ),
    ActionSpec(
        "assets", "buy_shares", "Buy shares", "📈", "Can rise or fall",
        lambda s, mv: _liquid(s) > 0, _buy_shares, "diversification", False, True,
    ),
    ActionSpec(
        "assets", "sell_shares", "Sell shares", "📉", "Move shares to savings",
        lambda s, mv: s.investments > 0, _sell_shares, "diversification", False, True,
    ),
    ActionSpec(
        "assets", "buy_crypto", "Buy crypto", "🪙", "Can double or halve",
        lambda s, mv: _liquid(s) > 0 and mv.has(MacroKey.CRYPTO_RETURN) and s.year >= p.CRYPTO_FROM_YEAR
        and _has_data(mv, s, MacroKey.CRYPTO_RETURN),
        _buy_crypto, "crypto-risk", False, True,
    ),
    ActionSpec(
        "assets", "sell_crypto", "Sell crypto", "💱", "Move crypto to savings",
        lambda s, mv: s.crypto > 0, _sell_crypto, "crypto-risk", False, True,
    ),
    ActionSpec(
        "assets", "buy_car", "Buy a used car", "🚙", "Upfront cost and running costs",
        lambda s, mv: not s.has_car and s.age >= 17, _buy_car, "depreciation",
    ),
    ActionSpec(
        "assets", "sell_car", "Sell the car", "🚲", "Cash now, lower costs",
        lambda s, mv: s.has_car, _sell_car, "depreciation",
    ),
    ActionSpec(
        "relationships", "date", "Go on dates", "💘", "Meet someone",
        lambda s, mv: not s.has_partner and s.age >= 18, _date,
    ),
    ActionSpec(
        "relationships", "propose", "Propose", "💍", "A small wedding",
        lambda s, mv: s.has_partner and not s.married, _propose, "household-costs",
    ),
    ActionSpec(
        "relationships", "break_up", "Break up", "💔", "Costs more if married",
        lambda s, mv: s.has_partner, _break_up, "household-costs",
    ),
    ActionSpec(
        "relationships", "try_for_baby", "Try for a baby", "👶", "Costs rise every month",
        lambda s, mv: s.has_partner and 18 <= s.age <= 45, _baby, "household-costs",
    ),
    ActionSpec(
        "relationships", "family_time", "Spend time with family", "👨‍👩‍👧", "Closer ties",
        lambda s, mv: any(r.kind != "ex" for r in s.relationships), _family_time,
    ),
    ActionSpec("activities", "gym", "Join a gym", "🏋️", "Health up, small cost", _always, _gym, "health-cost"),
    ActionSpec("activities", "holiday", "Go on holiday", "🏝️", "Happiness up", _always, _holiday, "budgeting"),
    ActionSpec("activities", "course", "Take a course", "📚", "Smarts up", _always, _course, "human-capital"),
    ActionSpec("activities", "doctor", "See a doctor", "🩺", "Free on the NHS", _always, _doctor, "health-cost"),
    ActionSpec("activities", "volunteer", "Volunteer", "🤝", "Happiness up", _always, _volunteer),
    ActionSpec("activities", "walks", "Walk more", "🚶", "Free exercise", _always, _walks),
    ActionSpec(
        "money", "save", "Move cash to savings", "🐖", "Earn interest",
        lambda s, mv: s.cash > 0, _save, "emergency-fund", False, True,
    ),
    ActionSpec(
        "money", "withdraw", "Take money out of savings", "💸", "Cash in hand",
        lambda s, mv: s.savings > 0, _withdraw, "emergency-fund", False, True,
    ),
    ActionSpec(
        "money", "pay_debt", "Pay off card debt", "🧹", "Stop the interest",
        lambda s, mv: s.other_debt > 0 and _liquid(s) > 0, _pay_debt, "debt", False, True,
    ),
    ActionSpec(
        "money", "pension_topup", "Top up your pension", "👵", "Tax relief adds 25%",
        lambda s, mv: _liquid(s) > 0 and not s.retired, _pension_topup, "pensions", False, True,
    ),
    ActionSpec(
        "money", "cut_spending", "Cut your spending", "✂️", "Spend 5% less each month",
        lambda s, mv: s.living > 0, _cut_spending, "budgeting",
    ),
    ActionSpec(
        "money", "borrow", "Take a loan", "🏧", "Cash now, interest later",
        lambda s, mv: s.age >= 18, _borrow, "debt", False, True,
    ),
)  # fmt: skip

_BY_KEY: dict[tuple[str, str], ActionSpec] = {(a.tab, a.id): a for a in ACTIONS}


def action_spec(tab: str, action_id: str) -> ActionSpec | None:
    return _BY_KEY.get((tab, action_id))


# ---------- encoding ----------


def _fmt(v: float) -> str:
    text = f"{v:.2f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def encode_choice(tab: str, action_id: str, params: Mapping[str, float]) -> str:
    base = f"{tab}/{action_id}"
    if not params:
        return base
    return base + "?" + "&".join(f"{k}={_fmt(params[k])}" for k in sorted(params))


def decode_choice(choice_id: str) -> tuple[str, str, dict[str, float]] | None:
    head, _, query = choice_id.partition("?")
    tab, _, action_id = head.partition("/")
    if not tab or not action_id:
        return None
    params: dict[str, float] = {}
    for k, v in parse_qsl(query, keep_blank_values=False):
        try:
            params[k] = float(v)
        except ValueError:
            return None
    return tab, action_id, params


def is_action_id(decision_id: str) -> bool:
    return decision_id.startswith(f"{ACTION_PREFIX}-")


def action_decision_id(year: int, n: int) -> str:
    return f"{ACTION_PREFIX}-{year}-{n}"


def clean_params(spec: ActionSpec, params: Mapping[str, float | str]) -> dict[str, float]:
    """Only `amount` is allowed, and only on actions that take one. Raises ValueError."""
    out: dict[str, float] = {}
    for k, v in params.items():
        if k != "amount" or not spec.amount:
            raise ValueError(f"unknown parameter {k!r}")
        try:
            f = float(v)
        except (TypeError, ValueError) as exc:
            raise ValueError("amount must be a number") from exc
        if not (f > 0 and f <= p.MAX_ACTION_AMOUNT):
            raise ValueError(f"amount must be above 0 and at most {p.MAX_ACTION_AMOUNT:,.0f}")
        out[k] = round(f, 2)
    return out


# ---------- running ----------


@dataclass(frozen=True)
class ActionRun:
    spec: ActionSpec
    text: str
    good: bool
    facts: dict[str, float]
    deltas: Deltas


def run_action(s: SimState, mv: MacroView, decision_id: str, choice_id: str) -> ActionRun | None:
    """Apply a recorded action in place. Returns None when the record is not a valid action now."""
    decoded = decode_choice(choice_id)
    if decoded is None:
        return None
    tab, action_id, params = decoded
    spec = action_spec(tab, action_id)
    if spec is None or not s.alive or not spec.available(s, mv):
        return None
    before = (s.net_worth, s.happiness, s.health, s.smarts)
    roll = uniform(s.seed, decision_id, "action", action_id)
    res = spec.apply(ActionCtx(s=s, mv=mv, params=params, roll=roll))
    deltas = Deltas(
        money=round(s.net_worth - before[0], 2),
        happiness=s.happiness - before[1],
        health=s.health - before[2],
        smarts=s.smarts - before[3],
    )
    return ActionRun(spec=spec, text=res.text, good=res.good, facts=res.facts, deltas=deltas)


def available_actions(s: SimState, mv: MacroView, done_this_year: set[str]) -> list[AvailableAction]:
    """Every action, in tab order. `enabled` is False when it is not possible now."""
    if not s.alive:
        return []
    out: list[AvailableAction] = []
    for a in ACTIONS:
        ok = a.available(s, mv) and not (a.once_per_year and f"{a.tab}/{a.id}" in done_this_year)
        out.append(AvailableAction(tab=a.tab, id=a.id, label=a.label, emoji=a.emoji, hint=a.hint, enabled=ok))
    return out
