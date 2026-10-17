# ruff: noqa: E501  (prompt table: one option per line reads better than wrapped lambdas)
"""Same Decision prompts (ADR 0052, ADR 0059). Pure: no I/O, no clock, no global RNG.

Each prompt is one student money decision in one real year. The context line and every option's outcome are
computed from the MacroTable for that year (UK values), so every number traces to a data series:
Bank Rate, CPI, the FTSE proxy, crypto returns, GBP/USD, energy prices, median pay (Nomis ASHE), house prices.
Outcomes are GAME money: the change in the player's game money over the period in the note. They never use the
player's real money. Fixed amounts (for example "£1,000 from a summer job") are the prompt's game stakes.

Sim rules used (lifeline_sim.params): easy-access savings = Bank Rate + SAVINGS_SPREAD (floor SAVINGS_FLOOR) when
the table has no quoted savings rate; card APR = Bank Rate + CARD_SPREAD when it has no quoted card rate.
Pay for a path stage: `lifeline_sim.paths` shares of median pay, after tax (`lifeline_sim.tax.net_pay`).
Lifetime ISA bonus: rule.lisa_bonus_rate (lifeline_engine.rules).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from lifeline_contracts.macro import MacroKey, MacroTable
from lifeline_contracts.play import DecisionOption, DecisionOutcome, DecisionPrompt
from lifeline_engine import rules
from lifeline_sim import params as p
from lifeline_sim.macroview import MacroView
from lifeline_sim.paths import MASTERS_FEE_2024, tuition_fee_cap
from lifeline_sim.rng import rng
from lifeline_sim.tax import net_pay

Outcome = tuple[float, str]  # (game money change in GBP, note)


class _Data:
    """UK values for one table. Nearest year is used when a year is missing (the MacroValue note says so)."""

    def __init__(self, table: MacroTable) -> None:
        self.mv = MacroView(table, strict=False)

    def v(self, key: MacroKey, year: int, default: float = 0.0) -> float:
        return self.mv.value(key, year, None, default)

    def bank(self, y: int) -> float:
        return self.v(MacroKey.BANK_RATE, y)

    def cpi(self, y: int) -> float:
        return self.v(MacroKey.CPI_INFLATION, y)

    def stock(self, y: int) -> float:
        return self.v(MacroKey.STOCK_RETURN, y)

    def crypto(self, y: int) -> float:
        return self.v(MacroKey.CRYPTO_RETURN, y)

    def median(self, y: int) -> float:
        return self.v(MacroKey.MEDIAN_PAY, y, 30_000.0)

    def savings(self, y: int) -> float:
        quoted = self.mv.opt(MacroKey.SAVINGS_RATE, y) if self.mv.has(MacroKey.SAVINGS_RATE) else None
        return quoted if quoted is not None else max(p.SAVINGS_FLOOR, self.bank(y) + p.SAVINGS_SPREAD)

    def card(self, y: int) -> float:
        quoted = self.mv.opt(MacroKey.CARD_RATE, y) if self.mv.has(MacroKey.CARD_RATE) else None
        return quoted if quoted is not None else self.bank(y) + p.CARD_SPREAD

    def price(self, y: int) -> float:
        return self.mv.price_level(y)


@dataclass(frozen=True)
class _Option:
    id: str
    label: str
    outcome: Callable[[_Data], Outcome]


@dataclass(frozen=True)
class _Prompt:
    id: str
    year: int
    text: str
    context: Callable[[_Data], str]
    options: tuple[_Option, ...]


def _gbp(x: float) -> str:
    return f"-£{-x:,.0f}" if x < 0 else f"£{x:,.0f}"


def _pct(x: float) -> str:
    return f"{x:.1f}%"


LISA_BONUS = float(rules.get("lisa_bonus_rate").value) / 100


def _three_years(d: _Data, start: int, share: float, tuition: bool) -> float:
    pay = sum(net_pay(share * d.median(y), True) for y in range(start, start + 3))
    debt = sum(tuition_fee_cap(y) for y in range(start, start + 3)) if tuition else 0.0
    return pay - debt


_PROMPTS: tuple[_Prompt, ...] = (
    _Prompt(
        "sd-2007-store-card",
        2007,
        "A store card gives 10% off a £500 laptop if you open it today. You would clear it over the year.",
        lambda d: f"Bank Rate averaged {_pct(d.bank(2007))} in 2007, so card interest was about {_pct(d.card(2007))} a year.",
        (
            _Option("card", "Open the card for the discount",
                    lambda d: (50 - 500 * 0.5 * d.card(2007) / 100,
                               f"£50 off, then about {_pct(d.card(2007))} interest on the balance as you cleared it.")),
            _Option("cash", "Pay with savings",
                    lambda d: (-500 * d.savings(2007) / 100,
                               f"No discount. You lost {_pct(d.savings(2007))} savings interest on £500.")),
            _Option("wait", "Wait for a sale",
                    lambda d: (0.0, "No laptop yet, no cost.")),
        ),
    ),
    _Prompt(
        "sd-2008-crash",
        2008,
        "You have £1,000 from a summer job. Where does it go for the year?",
        lambda d: f"In 2008 shares returned {d.stock(2008):+.0f}% and Bank Rate averaged {_pct(d.bank(2008))}.",
        (
            _Option("savings", "Easy-access savings",
                    lambda d: (1000 * d.savings(2008) / 100, f"Savings paid about {_pct(d.savings(2008))} in 2008.")),
            _Option("shares", "A shares fund",
                    lambda d: (1000 * d.stock(2008) / 100, f"Shares returned {d.stock(2008):+.0f}% in 2008.")),
            _Option("spend", "Spend it on a holiday",
                    lambda d: (-1000.0, "A great trip. The £1,000 is gone.")),
        ),
    ),
    _Prompt(
        "sd-2009-rate-cut",
        2009,
        "You have £2,000 in savings and £2,000 on a credit card. What do you do this year?",
        lambda d: f"Bank Rate was cut from {_pct(d.bank(2008))} to an average of {_pct(d.bank(2009))} in 2009.",
        (
            _Option("keep", "Keep both",
                    lambda d: (2000 * (d.savings(2009) - d.card(2009)) / 100,
                               f"Savings earned {_pct(d.savings(2009))}, the card charged {_pct(d.card(2009))}.")),
            _Option("clear", "Clear the card with savings",
                    lambda d: (0.0, "No interest earned and none paid.")),
            _Option("invest", "Invest the savings, keep the card",
                    lambda d: (2000 * (d.stock(2009) - d.card(2009)) / 100,
                               f"Shares returned {d.stock(2009):+.0f}%, the card charged {_pct(d.card(2009))}.")),
        ),
    ),
    _Prompt(
        "sd-2010-graduate",
        2010,
        "You graduate into a weak job market. What do you do for the next year?",
        lambda d: f"Unemployment averaged {_pct(d.v(MacroKey.UNEMPLOYMENT, 2010))} in 2010. Median full-time pay was {_gbp(d.median(2010))}.",
        (
            _Option("any_job", "Take any job now",
                    lambda d: (net_pay(0.7 * d.median(2010), True),
                               "Take-home pay for a year at 70% of median pay (game assumption).")),
            _Option("intern", "Unpaid internship in your field",
                    lambda d: (0.0, "No pay this year. Some internships lead to better jobs later.")),
            _Option("masters", "Do a master's",
                    lambda d: (-MASTERS_FEE_2024 * d.price(2010),
                               "The master's fee, paid with a loan, scaled to 2010 prices.")),
        ),
    ),
    _Prompt(
        "sd-2012-fees",
        2012,
        "You are 18 in 2012. What do you do for the next 3 years?",
        lambda d: f"From 2012 English universities could charge up to {_gbp(tuition_fee_cap(2012))} a year, up from {_gbp(tuition_fee_cap(2011))}. Median pay was {_gbp(d.median(2012))}.",
        (
            _Option("uni", "Go to university",
                    lambda d: (_three_years(d, 2012, 0.2, True),
                               "Part-time take-home pay over 3 years, minus the tuition fee loan you owe.")),
            _Option("apprentice", "Start an apprenticeship",
                    lambda d: (_three_years(d, 2012, 0.45, False),
                               "Take-home pay over 3 years at 45% of median pay. No fees.")),
            _Option("job", "Get a job",
                    lambda d: (_three_years(d, 2012, 0.55, False),
                               "Take-home pay over 3 years at 55% of median pay.")),
        ),
    ),
    _Prompt(
        "sd-2013-bitcoin",
        2013,
        "Bitcoin is in the news. Do you put £200 in at the end of 2013?",
        lambda d: f"Crypto returned {d.crypto(2013):+,.0f}% in 2013. Bank Rate was {_pct(d.bank(2013))}.",
        (
            _Option("crypto", "Buy £200 of crypto",
                    lambda d: (200 * max(-95.0, d.crypto(2014)) / 100, f"Crypto returned {d.crypto(2014):+,.0f}% in 2014.")),
            _Option("savings", "Keep it in savings",
                    lambda d: (200 * d.savings(2014) / 100, f"Savings paid about {_pct(d.savings(2014))} in 2014.")),
        ),
    ),
    _Prompt(
        "sd-2015-renting",
        2015,
        "You start your first job. Where do you live this year?",
        lambda d: f"The average UK home cost {_gbp(d.v(MacroKey.HOUSE_PRICE, 2015))} in 2015, and rents follow prices.",
        (
            _Option("alone", "Rent a flat alone",
                    lambda d: (-d.v(MacroKey.HOUSE_PRICE, 2015) * p.GROSS_RENT_YIELD,
                               "A year of rent at 4.5% of the average home price (game rule).")),
            _Option("share", "Share a house",
                    lambda d: (-d.v(MacroKey.HOUSE_PRICE, 2015) * p.GROSS_RENT_YIELD * p.STUDENT_RENT_SHARE,
                               "A year of rent for a room, 60% of a flat (game rule).")),
            _Option("parents", "Stay with parents",
                    lambda d: (0.0, "No rent this year.")),
        ),
    ),
    _Prompt(
        "sd-2016-pound",
        2016,
        "Your US summer camp job needs $1,500 for flights and fees. When do you buy the dollars?",
        lambda d: f"The pound averaged ${d.v(MacroKey.GBP_USD, 2015, 1.5):.2f} in 2015 and ${d.v(MacroKey.GBP_USD, 2016, 1.5):.2f} in 2016.",
        (
            _Option("early", "Bought in 2015",
                    lambda d: (-1500 / d.v(MacroKey.GBP_USD, 2015, 1.5), "Dollars at the 2015 average rate.")),
            _Option("now", "Buy in 2016",
                    lambda d: (-1500 / d.v(MacroKey.GBP_USD, 2016, 1.5), "Dollars at the 2016 average rate.")),
            _Option("uk", "Work in the UK instead",
                    lambda d: (0.0, "No flights or fees to pay.")),
        ),
    ),
    _Prompt(
        "sd-2017-lisa",
        2017,
        "The Lifetime ISA has just started. You can put away £1,000 for a first home this year.",
        lambda d: f"Bank Rate averaged {_pct(d.bank(2017))} in 2017. A Lifetime ISA adds a {LISA_BONUS:.0%} bonus.",
        (
            _Option("lisa", "Lifetime ISA",
                    lambda d: (1000 * LISA_BONUS + 1000 * d.savings(2017) / 100,
                               f"{LISA_BONUS:.0%} bonus plus about {_pct(d.savings(2017))} interest. For a first home or age 60.")),
            _Option("savings", "Easy-access savings",
                    lambda d: (1000 * d.savings(2017) / 100, f"About {_pct(d.savings(2017))} interest.")),
            _Option("shares", "A shares fund",
                    lambda d: (1000 * d.stock(2017) / 100, f"Shares returned {d.stock(2017):+.0f}% in 2017.")),
        ),
    ),
    _Prompt(
        "sd-2020-covid",
        2020,
        "Your shifts stop for 3 months. You need £1,200 for rent. How do you cover it?",
        lambda d: f"Unemployment rose to {_pct(d.v(MacroKey.UNEMPLOYMENT, 2020))} in 2020 and Bank Rate fell to {_pct(d.bank(2020))}.",
        (
            _Option("savings", "Use savings",
                    lambda d: (-1200 * d.savings(2020) / 100, f"You lost about {_pct(d.savings(2020))} interest on £1,200.")),
            _Option("card", "Put it on a credit card",
                    lambda d: (-1200 * d.card(2020) / 100, f"A year of card interest at about {_pct(d.card(2020))}.")),
            _Option("family", "Borrow from family",
                    lambda d: (0.0, "No interest, but you owe someone you love.")),
        ),
    ),
    _Prompt(
        "sd-2021-crypto",
        2021,
        "A friend says to buy crypto with your £500 at the end of 2021.",
        lambda d: f"Crypto returned {d.crypto(2021):+,.0f}% in 2021. Shares returned {d.stock(2021):+.0f}%.",
        (
            _Option("crypto", "Buy crypto",
                    lambda d: (500 * max(-95.0, d.crypto(2022)) / 100, f"Crypto returned {d.crypto(2022):+,.0f}% in 2022.")),
            _Option("shares", "A shares fund",
                    lambda d: (500 * d.stock(2022) / 100, f"Shares returned {d.stock(2022):+.0f}% in 2022.")),
            _Option("savings", "Savings",
                    lambda d: (500 * d.savings(2022) / 100, f"Savings paid about {_pct(d.savings(2022))} in 2022.")),
        ),
    ),
    _Prompt(
        "sd-2022-inflation",
        2022,
        "You have £3,000 in a current account that pays nothing. Prices are rising fast.",
        lambda d: f"Prices rose {_pct(d.cpi(2022))} in 2022. Bank Rate averaged {_pct(d.bank(2022))}.",
        (
            _Option("leave", "Leave it",
                    lambda d: (-3000 * d.cpi(2022) / 100, f"No interest, and prices rose {_pct(d.cpi(2022))}. Shown in what it buys.")),
            _Option("savings", "Easy-access savings",
                    lambda d: (3000 * (d.savings(2022) - d.cpi(2022)) / 100,
                               f"About {_pct(d.savings(2022))} interest, less {_pct(d.cpi(2022))} price rises.")),
            _Option("shares", "A shares fund",
                    lambda d: (3000 * (d.stock(2022) - d.cpi(2022)) / 100,
                               f"Shares returned {d.stock(2022):+.0f}%, less {_pct(d.cpi(2022))} price rises.")),
        ),
    ),
    _Prompt(
        "sd-2022-energy",
        2022,
        "Your student house can fix its energy price for a year at 20% above today's price.",
        lambda d: f"Energy prices changed {d.v(MacroKey.ENERGY_PRICE_CHANGE, 2022):+.0f}% in 2022.",
        (
            _Option("fix", "Fix the price",
                    lambda d: (-450 * d.price(2022) * 0.2, "Your £450 share (2024 prices) cost 20% more, fixed.")),
            _Option("variable", "Stay on the variable price",
                    lambda d: (-450 * d.price(2022) * d.v(MacroKey.ENERGY_PRICE_CHANGE, 2022) / 100,
                               f"Your share moved with energy prices: {d.v(MacroKey.ENERGY_PRICE_CHANGE, 2022):+.0f}%.")),
        ),
    ),
    _Prompt(
        "sd-2023-first-home",
        2023,
        "You have £2,000 to put away for a first home.",
        lambda d: f"Bank Rate averaged {_pct(d.bank(2023))} in 2023, the highest in years.",
        (
            _Option("current", "Current account",
                    lambda d: (0.0, "No interest.")),
            _Option("savings", "Easy-access savings",
                    lambda d: (2000 * d.savings(2023) / 100, f"About {_pct(d.savings(2023))} interest.")),
            _Option("lisa", "Lifetime ISA",
                    lambda d: (2000 * LISA_BONUS + 2000 * d.savings(2023) / 100,
                               f"{LISA_BONUS:.0%} bonus plus about {_pct(d.savings(2023))} interest.")),
        ),
    ),
)  # fmt: skip

_BY_ID: dict[str, _Prompt] = {pr.id: pr for pr in _PROMPTS}
PROMPT_IDS: tuple[str, ...] = tuple(pr.id for pr in _PROMPTS)


def _prompt_model(pr: _Prompt, d: _Data) -> DecisionPrompt:
    return DecisionPrompt(
        id=pr.id,
        year=pr.year,
        context=pr.context(d)[:240],
        text=pr.text,
        options=[DecisionOption(id=o.id, label=o.label) for o in pr.options],
    )


def decision_prompts(seed: int, n: int, macro: MacroTable, year: int | None = None) -> list[DecisionPrompt]:
    """`n` prompts for a Same Decision round. Same seed, n, year and table give the same prompts.

    Without `year`: a seeded sample. With `year`: prompts nearest that year first (ties in seeded order)."""
    d = _Data(macro)
    order = list(_PROMPTS)
    rng(seed, "same_decision").shuffle(order)
    if year is not None:
        order.sort(key=lambda pr: abs(pr.year - year))
    return [_prompt_model(pr, d) for pr in order[: max(1, min(n, len(order)))]]


def decision_prompt(prompt_id: str, macro: MacroTable) -> DecisionPrompt | None:
    pr = _BY_ID.get(prompt_id)
    return None if pr is None else _prompt_model(pr, _Data(macro))


def decision_outcomes(prompt_id: str, macro: MacroTable) -> list[DecisionOutcome]:
    """Every option's outcome in game money, in option order. Raises KeyError for an unknown prompt."""
    pr = _BY_ID[prompt_id]
    d = _Data(macro)
    out: list[DecisionOutcome] = []
    for o in pr.options:
        money, note = o.outcome(d)
        out.append(DecisionOutcome(option_id=o.id, game_money_change=round(money), note=note[:160]))
    return out


def decision_outcome(prompt_id: str, option_id: str, macro: MacroTable) -> DecisionOutcome:
    """One option's outcome. Raises KeyError for an unknown prompt or option."""
    hit = next((o for o in decision_outcomes(prompt_id, macro) if o.option_id == option_id), None)
    if hit is None:
        raise KeyError(option_id)
    return hit


def best_option_ids(prompt_id: str, macro: MacroTable) -> list[str]:
    """The option ids with the highest game money outcome (for points). Ties give several ids."""
    outs = decision_outcomes(prompt_id, macro)
    top = max(o.game_money_change for o in outs)
    return [o.option_id for o in outs if o.game_money_change == top]
