"""Real-life Decision: ONE recommended action, with evidence from twins and similar past periods.

Tier 0 scope: two questions.
- "mortgage": the person has a mortgage. Options: fix 2 years, fix 5 years, tracker.
  Outcome = interest paid over HORIZON years (lower is better).
- "savings": everyone else. Options: keep in savings, invest, pay off debt (when debt > 0).
  Outcome = value after HORIZON years (higher is better).

Method:
1. Match past start years whose macro state looks like `as_of_year` (periods.similar_years).
   Only start years with HORIZON years of data after them are candidates.
2. Draw a synthetic population for `as_of_year` and take the K_TWINS nearest twins of the profile.
3. Run every option for every (twin, period) pair on the real rate path of that period.
4. Rank options by mean outcome relative to the amount. The headline is the best option.
   success_rate = share of (twin, period) pairs where the best option beat the runner-up.

Assumptions (labelled, not from a data source): TRACKER_MARGIN, SAVINGS_GAP, FUND_FEE, DEBT_PREMIUM.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from lifeline_contracts.domain import Alternative, Decision, DecisionProfile, Evidence, SourceRef
from lifeline_contracts.macro import MacroKey, MacroTable
from lifeline_engine.finance import monthly_payment, remaining_balance
from lifeline_engine.macro_access import source_ref, value_or
from lifeline_engine.periods import similar_years, table_years
from lifeline_engine.population import Person, build_population, sample_people
from lifeline_engine.twins import TwinIndex, features

Question = Literal["mortgage", "savings"]

HORIZON = 5
K_PERIODS = 5
K_TWINS = 20
POPULATION_SIZE = 600
DEFAULT_YEARS_LEFT = 25
DEFAULT_AMOUNT = 1_000.0

TRACKER_MARGIN = 1.0  # percent over Bank Rate, typical UK tracker
SAVINGS_GAP = 0.5  # percent below Bank Rate, typical easy-access savings
FUND_FEE = 0.2  # percent per year, low-cost index fund
DEBT_PREMIUM = 15.0  # percent over Bank Rate, typical unsecured debt

DISCLAIMER = "Education, not financial advice."

OPTION_TEXT: dict[str, tuple[str, str]] = {
    # id: (headline, short action label)
    "fix_2y": ("Fix for 2 years.", "Fix your mortgage for 2 years"),
    "fix_5y": ("Fix for 5 years.", "Fix your mortgage for 5 years"),
    "tracker": ("Take a tracker deal.", "Take a deal that follows the Bank Rate"),
    "save": ("Keep it in savings.", "Keep your money in an easy-access savings account"),
    "invest": ("Invest it for the long term.", "Invest in a low-cost fund that follows the stock market"),
    "pay_debt": ("Pay off your debt first.", "Use your savings to clear your debt"),
}

QUESTION_TEXT: dict[Question, str] = {
    "mortgage": "Your mortgage deal is ending. Should you fix for 2 years, fix for 5 years, or track the Bank Rate?",
    "savings": "What should you do with your savings over the next 5 years?",
}


# ---------- option outcomes ----------


def _rate(macro: MacroTable, key: MacroKey, year: int) -> float:
    bank = value_or(macro, MacroKey.BANK_RATE, year, None, 4.0)
    fallback = bank + (1.5 if key == MacroKey.MORTGAGE_2Y_FIX else 1.9 if key == MacroKey.MORTGAGE_5Y_FIX else 0.0)
    return value_or(macro, key, year, None, fallback)


def mortgage_rate_path(macro: MacroTable, option: str, start: int, horizon: int = HORIZON) -> list[float]:
    """Annual mortgage rate (percent) for each of `horizon` years from `start`."""
    if option == "fix_2y":
        return [_rate(macro, MacroKey.MORTGAGE_2Y_FIX, start + 2 * (t // 2)) for t in range(horizon)]
    if option == "fix_5y":
        return [_rate(macro, MacroKey.MORTGAGE_5Y_FIX, start + 5 * (t // 5)) for t in range(horizon)]
    if option == "tracker":
        return [_rate(macro, MacroKey.BANK_RATE, start + t) + TRACKER_MARGIN for t in range(horizon)]
    raise ValueError(f"unknown mortgage option {option}")


def mortgage_interest(balance: float, years_left: int, rates: Sequence[float]) -> float:
    """Interest paid over len(rates) years. Each year re-prices a repayment mortgage at that rate."""
    paid = 0.0
    bal = balance
    remaining = years_left
    for rate in rates:
        if remaining <= 0 or bal <= 0:
            break
        paid += monthly_payment(bal, rate, remaining) * 12
        bal = remaining_balance(bal, rate, remaining, 12)
        remaining -= 1
    return paid - (balance - bal)


def savings_growth_path(macro: MacroTable, option: str, start: int, horizon: int = HORIZON) -> list[float]:
    """Annual growth (percent) for each of `horizon` years from `start`."""
    out: list[float] = []
    for t in range(horizon):
        bank = value_or(macro, MacroKey.BANK_RATE, start + t, None, 4.0)
        if option == "save":
            out.append(max(0.0, bank - SAVINGS_GAP))
        elif option == "invest":
            out.append(value_or(macro, MacroKey.STOCK_RETURN, start + t, None, 5.0) - FUND_FEE)
        elif option == "pay_debt":
            out.append(bank + DEBT_PREMIUM)
        else:
            raise ValueError(f"unknown savings option {option}")
    return out


def _grow(amount: float, pcts: Sequence[float]) -> float:
    for p in pcts:
        amount *= 1.0 + p / 100.0
    return amount


# ---------- ranking ----------


@dataclass(frozen=True)
class Scenario:
    """One twin: the amount at stake and, for mortgages, the years left."""

    amount: float
    years_left: int


@dataclass(frozen=True)
class Ranking:
    options: tuple[str, ...]  # best first
    scores: dict[str, float]  # higher is better
    beat_runner_up: float  # share of pairs where the best option beat the runner-up
    win_rate: dict[str, float]  # share of pairs where each option was the best


def options_for(question: Question, profile: DecisionProfile | None = None) -> tuple[str, ...]:
    if question == "mortgage":
        return ("fix_2y", "fix_5y", "tracker")
    if profile is not None and profile.other_debt > 0:
        return ("save", "invest", "pay_debt")
    return ("save", "invest")


def outcome(question: Question, macro: MacroTable, option: str, start: int, s: Scenario) -> float:
    """Score for one (option, period, twin). Higher is better. Relative to the amount."""
    if s.amount <= 0:
        return 0.0
    if question == "mortgage":
        rates = mortgage_rate_path(macro, option, start)
        return -mortgage_interest(s.amount, s.years_left, rates) / s.amount
    return _grow(s.amount, savings_growth_path(macro, option, start)) / s.amount - 1.0


def rank_options(
    question: Question, macro: MacroTable, options: Sequence[str], starts: Sequence[int], scenarios: Sequence[Scenario]
) -> Ranking:
    """Rank options over every (period, scenario) pair. Ties break on option order."""
    if not options:
        raise ValueError("no options")
    grid = np.array(
        [[[outcome(question, macro, o, y, s) for s in scenarios] for y in starts] for o in options], dtype=np.float64
    ).reshape(len(options), -1)
    if grid.shape[1] == 0:
        return Ranking(tuple(options), dict.fromkeys(options, 0.0), 0.0, dict.fromkeys(options, 0.0))
    means = grid.mean(axis=1)
    order = sorted(range(len(options)), key=lambda i: (-float(means[i]), i))
    best = order[0]
    beat = float((grid[best] > grid[order[1]]).mean()) if len(order) > 1 else 1.0
    winners = np.argmax(grid, axis=0)
    win = {o: float((winners == i).mean()) for i, o in enumerate(options)}
    return Ranking(tuple(options[i] for i in order), {o: float(means[i]) for i, o in enumerate(options)}, beat, win)


# ---------- decide ----------


def choose_question(profile: DecisionProfile) -> Question:
    if profile.housing == "mortgage" and (profile.mortgage_balance or 0) > 0:
        return "mortgage"
    return "savings"


def candidate_starts(macro: MacroTable, before: int, horizon: int = HORIZON) -> list[int]:
    """Start years with a full horizon of data that ends before `before`."""
    years = table_years(macro)
    if not years:
        return []
    last = years[-1]
    return [y for y in years if y + horizon - 1 <= last and y + horizon - 1 < before]


def _twins(profile: DecisionProfile, macro: MacroTable, year: int) -> list[Person]:
    pop = build_population(macro, year)
    people = sample_people(pop, POPULATION_SIZE, np.random.default_rng(year % 2**32))
    target = features(
        profile.age, profile.annual_income, profile.savings, profile.other_debt, profile.housing, profile.region
    )
    return [t.person for t in TwinIndex.build(people).nearest(target, K_TWINS)]


def _scenarios(question: Question, profile: DecisionProfile, twins: Sequence[Person]) -> list[Scenario]:
    years_left = profile.mortgage_years_left or DEFAULT_YEARS_LEFT
    out: list[Scenario] = []
    for tw in twins:
        if question == "mortgage":
            amount = tw.mortgage_balance if tw.mortgage_balance > 0 else (profile.mortgage_balance or 0.0)
            out.append(Scenario(amount=amount, years_left=max(1, min(40, years_left))))
        else:
            out.append(
                Scenario(amount=tw.savings if tw.savings > 0 else max(profile.savings, DEFAULT_AMOUNT), years_left=0)
            )
    return out


def _period_label(start: int) -> str:
    return f"{start}-{start + HORIZON - 1}"


def _sources(macro: MacroTable, year: int, question: Question, region: str) -> list[SourceRef]:
    keys = [MacroKey.BANK_RATE, MacroKey.CPI_INFLATION, MacroKey.UNEMPLOYMENT, MacroKey.HOUSE_PRICE_CHANGE]
    keys += [MacroKey.MORTGAGE_2Y_FIX, MacroKey.MORTGAGE_5Y_FIX] if question == "mortgage" else [MacroKey.STOCK_RETURN]
    refs = [source_ref(macro, k, year) for k in keys]
    pay = source_ref(macro, MacroKey.MEDIAN_PAY, year, region)
    return [r for r in [*refs, pay] if r is not None]


def evidence_sentence(rate: float) -> str:
    n = int(round(rate * 10))
    return f"{n} in 10 twins in similar past periods did better."


def decide_with(
    profile: DecisionProfile,
    macro: MacroTable,
    as_of_year: int,
    starts_filter: Callable[[list[int]], list[int]] | None = None,
) -> tuple[Decision, Ranking]:
    """`decide` plus the raw ranking. `starts_filter` lets the backtest drop held-out periods."""
    question = choose_question(profile)
    options = options_for(question, profile)
    pool = candidate_starts(macro, before=as_of_year)
    if starts_filter is not None:
        pool = starts_filter(pool)
    matches = similar_years(macro, as_of_year, K_PERIODS, candidates=pool)
    starts = [m.year for m in matches]
    twins = _twins(profile, macro, as_of_year)
    ranking = rank_options(question, macro, options, starts, _scenarios(question, profile, twins))
    best = ranking.options[0]
    headline, action = OPTION_TEXT[best]

    if starts:
        runner = OPTION_TEXT[ranking.options[1]][1].lower() if len(ranking.options) > 1 else ""
        sentence = evidence_sentence(ranking.beat_runner_up)
        reasons = [
            f"We found {len(twins)} people like you and {len(starts)} past periods that looked like {as_of_year}.",
            f"In those periods this option came out ahead of the next best choice ({runner}) "
            f"{int(round(ranking.beat_runner_up * 100))}% of the time.",
            "Past periods do not predict the future. They show what has happened before.",
        ]
        success = ranking.beat_runner_up
    else:
        sentence = "Not enough past data to compare these options yet."
        reasons = ["The data table has too few years to find similar past periods."]
        success = 0.0

    decision = Decision(
        question=QUESTION_TEXT[question],
        headline=headline,
        action=action,
        reasons=reasons,
        evidence=Evidence(
            twins_count=len(twins),
            periods=[_period_label(y) for y in starts],
            success_rate=min(1.0, max(0.0, success)),
            sentence=sentence,
        ),
        alternatives=[
            Alternative(
                action=OPTION_TEXT[o][1],
                score=round(ranking.scores[o], 6),
                success_rate=min(1.0, max(0.0, ranking.win_rate[o])),
            )
            for o in ranking.options[1:]
        ],
        sources=_sources(macro, as_of_year, question, profile.region),
        disclaimer=DISCLAIMER,
        # Engine is pure: no clock. The API layer replaces this with the server time.
        generated_at=f"{as_of_year}-01-01T00:00:00Z",
    )
    return decision, ranking


def decide(profile: DecisionProfile, macro: MacroTable, as_of_year: int) -> Decision:
    return decide_with(profile, macro, as_of_year)[0]
