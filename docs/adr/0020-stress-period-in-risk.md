# ADR 0020: Next Move risk includes a standard stress period; the demo follows the engine

- Status: accepted (amends ADR 0018)
- Date: 2026-10-17

## Context
W2's first engine run on the demo persona (homeowner-leeds, deal ends in 165 days) recommends "Take a tracker", not "Fix for 5 years": £1,376 a year better, 8 in 10 twins. The matched past periods (2005-2007, 2017, 2018) led into the 2008 rate cuts. "Test it" replays 2021-2023 (rate shock), where a tracker loses. The card and the replay would disagree, and the user would not see why.

## Decision
1. **No tuning to fit a script.** The engine output is the answer. DEMO.md narrates the live engine output (action, £ impact, confidence). It does not hardcode "Fix for 5 years".
2. **Each move kind has a standard stress period**, named in the engine config:
   - Mortgage moves: 2021-2023 (rate shock).
   - Savings: 2009-2011 (rates near zero).
   - Energy: 2021-2023 (price shock).
   - Debt and emergency fund: 2008-2010 (recession).
3. `worst_case_per_year` = the minimum over the matched periods AND the stress period. The ranking already penalises it (`impact + 0.5 x min(0, worst)`, scaled by confidence).
4. `test_period` = the stress period, with label "<years> <name> (stress test)". The evidence lists one point about the matched periods and one point about the stress period, so the card explains any gap between expected and stress results.
5. The result keeps all three numbers: expected impact (matched periods), worst case (including stress) and confidence.

## Consequences
- The card and Test it tell one consistent story: "Expected £X a year better; in a 2022-style shock, £Y." This matches the brief's stress-test pitch.
- The top move for the demo persona may be a tracker or a fix. Either is valid if the numbers support it.

## Amendment (same day): choose between options by regret, not only gain vs doing nothing

### Why
The first ADR 0020 run kept "Take a tracker" on top: expected £1,376 a year, stress gain £1,814 a year vs doing nothing, so no penalty. But in the 2021-2023 stress period the tracker was £5,255 a year worse than "Fix for 5 years". The rule measured risk only against doing nothing, not against the option the user would otherwise pick. That does not match this ADR's intent ("a move that fails the stress test is penalised openly"). This amendment fixes the rule for every move kind. It is not tuned to the demo: the result stands whichever option wins.

### Rule
- For a move with several options, each option o gets:
  - `expected(o)`: mean £/year vs doing nothing over the matched periods (as before).
  - `regret(o, p)`: £/year by which o trails the best option in period p (0 if o is best), over the matched periods and the stress period.
  - `score(o) = expected(o) - 0.5 x max_p regret(o, p)`.
- The recommended option = the highest score. `impact_per_year` = its expected value. `worst_case_per_year` = its worst result vs doing nothing (as before). `confidence` = the share of (twin, period) pairs where the recommended option beat doing nothing.
- Moves are still ranked against each other by `impact + 0.5 x min(0, worst)`, scaled by confidence.
- Evidence point 3 states the stress result of the recommended option and of the best alternative, so the trade-off is visible either way.

## Amendment 2 (2026-10-17): risk weight depends on affordability (rule fixed before running it)

### Why
The user asked that the demo persona's real inputs decide the card, and that any gap from "Fix for 5 years" be explained by naming the input that decides it. Diagnosis of the current choice ("Take a tracker"):
1. Today's tracker rate (BoE IUMBV48, 4.23%) is below both fixes (IUMBV42 4.98%, IUMBV34 5.13%).
2. The matched past periods (2005-2007, 2017-2018) were followed by flat or falling rates, so trackers usually won there.
3. The regret weight was a constant 0.5, so a borrower near the limit of what they can afford weighed the 2021-2023 shock the same as a borrower with plenty of slack.

Point 3 is a model gap, not a data choice. UK affordability rules stress a borrower's payment at a higher rate (lenders test about 3 percentage points above the reversion rate). A stretched borrower should weigh the stress case more.

### Rule (fixed before computing the demo result)
- `stressed_payment` = monthly payment on the user's balance and remaining term at (reversion rate + 3.0 percentage points). The reversion rate is BoE IUMTLMV.
- `ratio` = `stressed_payment` / net monthly income (from detected salary credits).
- Regret weight λ:
  - λ = 0.5 when ratio ≤ 0.30
  - λ = 1.5 when ratio ≥ 0.45
  - linear in between
- Option score = expected(o) − λ × max regret(o, p). Everything else in ADR 0020 is unchanged.
- The 3.0 points, 30% and 45% are labelled assumptions:
  - 3.0 follows the common UK affordability stress.
  - 30% and 45% of take-home pay follow typical "comfortable" and "stretched" lender guides.
- They are not tuned. If the demo result is still "Take a tracker", the card shows it, and this ADR records which input decides it.

### Result (W2, implemented exactly as written)
Priya Shah (demo persona), mock table 2026:
- Today's rates: reversion (IUMTLMV) 6.58%, tracker (IUMBV48) 4.23%, 2-year fix 5.13%, 5-year fix 4.98%.
- Stressed payment £1,582.68 a month (9.58%, £180,000, 25 years); net income £2,280.48; ratio 0.694, so λ = 1.5 (stretched).
- Matched periods: 2005, 2006, 2007, 2017, 2018. Stress period 2021-2023.

| Option | Expected £/yr | Max regret £/yr (period) | Score (λ = 1.5) |
|---|---|---|---|
| Take a tracker | 3,097 | 2,464 (2021 stress) | -598 |
| Fix for 2 years | 1,206 | 2,295 (2007) | -2,237 |
| Fix for 5 years | 1,228 | 4,335 (2007) | -5,275 |

**The engine's decision is "Take a tracker" at every λ ≥ 0.** Score(tracker) - score(fix 5y) = 1,869 + 1,871 x λ.

**Deciding inputs:**
1. **Today's quoted tracker rate (IUMBV48, 4.23%) is below both fixes.** It makes the tracker's expected gain in the matched periods £1,869 a year higher than the 5-year fix.
2. **The 2007 matched period.** Bank Rate then fell from 5.5% to 0.5%, so a 5-year fix taken in 2007 locked in a high rate. That gives the 5-year fix a larger worst regret (£4,335 a year) than the tracker's worst regret in the 2021 shock (£2,464 a year). Raising λ therefore penalises the fix more, not less.

**What would change it:** a matched set without a big rate-cutting episode, or a tracker priced above the 5-year fix. The card shows the engine's actual decision. Evidence 1 states the stretched affordability (69% of take-home at 9.58%), and evidence 3 states the 2021-2023 shock where the 5-year fix saved more. So the user sees the trade-off.

**Other decisions:**
- A user with no detected salary gets λ = 1.5 (cautious end).
- The mortgage backtest keeps λ = 0.5, because its reference profile has no income.
