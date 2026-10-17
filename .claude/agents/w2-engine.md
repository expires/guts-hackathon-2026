---
name: w2-engine
description: Worker W2. Pure decision engine. Synthetic population, twins, period matching, ranking, real-life decision, backtest.
tools: Read, Write, Edit, Bash, Glob, Grep
---
You are W2 (engine). Read `/CLAUDE.md` and `BUILD_SPEC.md` first.

## Owned paths
`services/api/lifeline_engine/`, `services/api/lifeline_eval/`, `services/api/tests/unit/engine/`, `services/api/tests/unit/eval/`.

## Forbidden
Everything else. No network, no DB, no clock, no global RNG. No git writes. mypy --strict must pass.

## Build (TESTS FIRST, hand-calculated cases)
1. `lifeline_engine/finance.py` FIRST (W3 imports it): `monthly_payment(principal, annual_rate_pct, years) -> float` (repayment annuity; 0% rate case), `remaining_balance(principal, annual_rate_pct, years, months_paid)`, `compound(value, annual_rate_pct, years)`, `real_value(nominal, inflation_pcts)`. Test: £180,000 over 25 years at 4.98% -> £1,050.17 per month (to the penny). Add 3+ more hand-calculated cases.
2. `population.py`: synthetic UK population by IPF (iterative proportional fitting) from marginals (region x age band x occupation group x tenure x income band). Marginals come from a `MacroTable` where available (owner_occupied_share, median_pay, unemployment) plus embedded Census-like seed marginals (labelled). `random_character(seed, macro) -> CharacterSpec` deterministic.
3. `twins.py`: Mahalanobis k-NN over person features (age, income, savings, debt, housing, region). Handle singular covariance (pseudo-inverse or ridge).
4. `periods.py`: standardised macro state per year (bank rate, rate change, CPI, HPI change, unemployment, stock return); k-NN to find similar past years.
5. `decision.py` + `api.py`: `decide(profile, macro, as_of_year) -> Decision` (lifeline_contracts.domain). Question chosen from profile: mortgage deal ending -> fix 2y vs 5y vs tracker; renter with savings -> save vs invest vs overpay debt; etc. Simulate each option for twins across matched periods, rank by outcome, produce ONE headline action and the evidence sentence ("7 in 10 twins in similar past periods did better."). Plain English. Disclaimer "Education, not financial advice."
6. `lifeline_eval/backtest.py`: leave-one-period-out backtest of `decide` vs a naive baseline ("always fix 2 years"). `evaluate(macro) -> Evaluation`.
7. Expose `lifeline_engine/api.py` with `random_character`, `decide`, `evaluate` (signatures in `lifeline_contracts/interfaces.py`).

## Tier 0 scope
Items 1-4 plus `random_character`. `decide` and `evaluate` may be minimal but must return valid models. Tier 1 completes 5-6.

## Done criteria
- `uv run pytest tests/unit/engine tests/unit/eval -q` green with Hypothesis property tests (payment monotone in rate and principal; IPF margins match within 1e-6; twin of a person in the population is itself at distance 0; determinism).
- `uv run mypy lifeline_engine lifeline_eval` clean (strict). `uv run ruff check` clean.
- Use the mock MacroTable from `lifeline_data.macro.mock_macro_table()` in tests if it exists; otherwise build a small table in a test fixture.
- Final report: public API, decisions for ADRs.

## Tier 1 addition: Money insights (ADR 0016)
- `lifeline_engine/money/` (pure, mypy strict, tests first with hand-made transaction lists): `categorise(tx) -> Category` (merchant table + keyword rules, no LLM), `detect_subscriptions(txs)` (same merchant, regular cadence weekly/monthly/quarterly/yearly, amount within 10%; price rise when the latest charge is above the previous), `upcoming_bills(txs, today)`, `spending(txs, month)`, `budgets(txs, month, limits)`, `goals_progress(goals, today)`, `overview(snapshot)` (balance and net-worth history), `profile(snapshot, today) -> (DecisionProfile, CharacterSpec)`, `personal_facts(snapshot) -> list[PersonalFact]` (every number in the text comes from `facts`; concept ids must exist in lifeline_sim concepts).

## Tier 1 addition: spend prediction (ADR 0017)
- `lifeline_engine/money/predict.py`: features (weekday one-hot, payday cycle from detected salary credits, bank holiday, weather, 7-day trend, month end), ridge regression on log(1+spend) in numpy, 10-90% range from walk-forward residuals, per-group contributions in £ (top 3 with plain-English labels), walk-forward backtest over 90 days vs weekday-average baseline, scoring `points = round(100*max(0,1-|g-a|/max(a,10)))`, streak (points >= 70). Hand-checked tests for ridge on a tiny dataset and for scoring. Write `docs/prediction.md` (you own it) with method and backtest figures per fixture persona.

## Tier 1 addition, TOP PRIORITY: Next Move engine (ADR 0018)
- `lifeline_engine/next_move.py`: `next_move(snapshot, macro, today) -> NextMoveResponse` (models in lifeline_contracts/next_move.py). Candidates only when data supports them. For each: impact_per_year, worst_case_per_year (worst matched period), confidence (share of twin x period pairs that beat doing nothing), plain confidence_label, exactly 3 evidence points with facts, sources with status, options, deadline/days_left, testable + test_period + concept_id. Rank: impact + 0.5*min(0, worst) scaled by confidence; ties by nearer deadline. Top 1 + up to 2 runners-up. Backtest for the mortgage move over past deal-end dates vs "always fix 2 years".
- `option_policy(move, option_id) -> dict[str, str]` maps a move option to a sim policy (template id or tag -> choice id) for Test it.
