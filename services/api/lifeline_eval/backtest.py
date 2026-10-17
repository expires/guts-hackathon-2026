"""Backtest of the mortgage decision against "always fix 2 years".

Leave-one-period-out, made strict (walk-forward): for each start year Y with a full horizon
of data:
1. Hide every start year whose window overlaps Y's window. `decide_with` also uses only
   windows that ended before Y, so there is no look-ahead.
2. Ask `decide_with` for a recommendation as of Y, using only the remaining periods.
3. Compute the realised best option for Y on the real rate path.
4. hit = recommendation == realised best. The baseline hits when fix 2 years was best.

Pure: no I/O, no clock.
"""

from __future__ import annotations

from lifeline_contracts.domain import BacktestPeriod, DecisionProfile, Evaluation
from lifeline_contracts.macro import MacroTable
from lifeline_engine.decision import HORIZON, Scenario, decide_with, options_for, rank_options
from lifeline_engine.macro_access import latest_year
from lifeline_engine.periods import table_years

BASELINE = "fix_2y"
BASELINE_TEXT = "Always fix for 2 years"
METHOD = "Leave-one-period-out, walk-forward backtest of the mortgage decision over 5-year windows"

REFERENCE_PROFILE = DecisionProfile(
    age=35,
    region="north-west",
    annual_income=35_000,
    savings=5_000,
    housing="mortgage",
    property_value=225_000,
    mortgage_balance=180_000,
    mortgage_years_left=25,
    deal_ends_in_months=3,
)


def evaluate(macro: MacroTable) -> Evaluation:
    years = table_years(macro)
    last = years[-1] if years else latest_year(macro)
    starts = [y for y in years if y + HORIZON - 1 <= last]
    options = options_for("mortgage")
    ref = Scenario(
        amount=REFERENCE_PROFILE.mortgage_balance or 0.0, years_left=REFERENCE_PROFILE.mortgage_years_left or 25
    )

    periods: list[BacktestPeriod] = []
    for y in starts:

        def held_out(pool: list[int], y: int = y) -> list[int]:
            return [s for s in pool if abs(s - y) >= HORIZON]

        decision, ranking = decide_with(REFERENCE_PROFILE, macro, y, starts_filter=held_out)
        if not decision.evidence.periods:
            continue
        realised = rank_options("mortgage", macro, options, [y], [ref]).options[0]
        recommended = ranking.options[0]
        periods.append(
            BacktestPeriod(
                start=y,
                end=y + HORIZON - 1,
                recommended=recommended,
                realised_best=realised,
                hit=recommended == realised,
            )
        )

    n = len(periods)
    return Evaluation(
        method=METHOD,
        n=n,
        hit_rate=sum(p.hit for p in periods) / n if n else 0.0,
        baseline_hit_rate=sum(p.realised_best == BASELINE for p in periods) / n if n else 0.0,
        baseline=BASELINE_TEXT,
        periods=periods,
        # Engine is pure: no clock. The API layer replaces this with the server time.
        generated_at=f"{last}-01-01T00:00:00Z",
    )
