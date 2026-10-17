# Prediction and backtests

Owner: W2 (engine). Code: `services/api/lifeline_engine/money/predict.py` (spend prediction, ADR 0017) and `services/api/lifeline_engine/next_move.py` (Next Move backtest, ADR 0018 and ADR 0020).

All figures on this page come from labelled fixture data (`status="mock"`, "Sample data"). They describe the four fixture personas. They do not describe real users.

## 1. Daily spend prediction

### What the model predicts

- Target: `log(1 + spend)` for one day.
- Daily spend: the sum of outflows on that day. The engine excludes these categories: transfers, savings, income, housing (rent and mortgage), bills, subscriptions and fees. Scheduled payments are in the bills list.
- The day of `as_of` is not complete. The model trains only on days before it.

### Features

| Group | Features | Source |
|---|---|---|
| `weekday` | One-hot Monday to Sunday | Calendar |
| `payday` | Days since the last salary credit / 30; flag for payday and the 2 days after | Detected salary credits, projected monthly |
| `bank_holiday` | Flag | gov.uk `bank-holidays.json` (W1) |
| `weather` | Max temperature (°C), rain (mm) | Open-Meteo by region (W1) |
| `recent_trend` | Mean log spend of the 7 days before | Transactions |
| `month_end` | Flag for the last 3 days of the month | Calendar |

A missing value (no weather, no payday found) takes the training mean, so it adds nothing to the prediction.

### Model

1. Standardise each feature with the training mean and standard deviation. A constant feature gets weight 0.
2. Fit ridge regression with an unpenalised intercept: `beta = (Z'Z + alpha I)^-1 Z'(y - mean(y))`.
3. Choose `alpha` from {0.3, 1, 3, 10, 30, 100}. Use the lowest walk-forward MAE (in £) over the 28 days before the prediction window.
4. Range: the 10th and 90th percentiles of walk-forward residuals in log space, over the 60 days before the window. Then add the residuals of earlier test days. Map the range back to £.
5. Reasons: effect of group g in £ = `predicted - prediction with group g at its training mean`. The engine shows the 3 groups with the largest absolute effect.
6. Baseline ("typical day"): the prediction with every feature at its training mean = `exp(intercept) - 1`.

Note: the £ effects are exact per group. They do not sum exactly to `predicted - baseline`, because the model is additive in log space (ADR 0017; the `Reason` docstring says the same).

### Backtest method

- Walk-forward over the last 90 complete days (2026-07-19 to 2026-10-16).
- For each test day, train on all days before it, then predict that day.
- Baseline: the mean spend on the same weekday over the days before the test day.
- Coverage: share of test days where the actual is inside the 10% to 90% range.

### Results (fixture personas, mock weather and fixture bank holidays)

| Persona | Model MAE | Weekday-average MAE | Model better by | Range coverage |
|---|---|---|---|---|
| homeowner-leeds | £28.74 | £26.93 | -£1.81 (worse) | 73.3% |
| renter-saver-london | £17.46 | £20.22 | £2.76 | 68.9% |
| subscription-creep-manchester | £19.28 | £22.37 | £3.09 | 81.1% |
| overspender-bristol | £19.80 | £21.62 | £1.82 | 82.2% |

Without weather and bank holidays the results are close: £29.06, £17.35, £19.20 and £19.60 MAE.

Findings:
- The model beats the weekday average for 3 of 4 personas.
- For homeowner-leeds the model is £1.81 worse. That persona has large Friday to Sunday spend and 26% of days with no spend. A log-space model predicts close to the median day, and the weekday mean is closer in £ on this data. A shift of the prediction by `exp(0.3)` lowers the MAE to £27.46, which is still worse than the baseline. We did not add a correction, because ADR 0017 fixes the target and the method.
- The 10% to 90% range should contain about 80% of days. Coverage is 69% to 82%.

### Guess my spend scoring

- `points = round(100 x max(0, 1 - |guess - actual| / max(actual, 10)))`. Rounding is half-up: 72.5 gives 73 (guess £51, actual £40). The engine first rounds the raw value to 9 decimals, so float noise does not change the result.
- `beat_model`: true when the guess is strictly closer to the actual than the prediction.
- Streak: consecutive scored days with points of 70 or more. Days without an actual yet do not break the streak.

Functions: `score_guess`, `beat_model`, `score_day`, `guess_totals`.

## 2. Next Move: mortgage backtest

### Method

1. Test years: past deal-end years Y from 1995 to 2022. Each Y has a full 5-year window of data after it.
2. For each Y, the engine recommends fix 2 years, fix 5 years or tracker. It uses Y's quoted rates and the 5 matched past periods whose windows ended before Y. It includes the 2021-2023 stress period only when that period ended before Y.
3. Option choice by regret (ADR 0020 amendment): `score(o) = expected(o) - 0.5 x max regret(o, p)`.
   Confidence on the card (ADR 0023): the share of (twin, period) pairs, stress period included, where the recommended option was the best of the options. Label: "In 8 of 10 similar cases this was the best choice".
   Rates: BoE 2-year and 5-year fixes, BoE revert-to rate (`MORTGAGE_SVR`) and 2-year tracker (`MORTGAGE_TRACKER`). Without those two series the engine uses Bank Rate + 2.0 and Bank Rate + 1.0 (labelled assumptions).
4. Realised best: the cheapest option over the 5 years after Y, on the real rate path.
5. Reference case: £180,000, 25 years left.
6. Baseline: "always fix for 2 years".

### Result (mock macro table)

| n | Engine hit rate | Baseline "always fix for 2 years" | Best constant rule "always take a tracker" |
|---|---|---|---|
| 28 | 64.3% | 14.3% | 71.4% |

The engine beats the 2-year baseline. It is 7.1 points worse than the best constant rule on this table: the regret rule moves some years away from the tracker, and the tracker was the realised best in 20 of 28 years. ADR 0023 requires this second baseline in every backtest. `NextMoveResponse.backtest` carries it in the `method` and `baseline` text until the contract has fields for it.

The response field `NextMoveResponse.backtest` carries these numbers when the top move is a mortgage move.

## 3. Real-life Decision backtest (`/v1/evaluation`)

`lifeline_eval.backtest.evaluate` runs a leave-one-period-out, walk-forward backtest of `decide` against "always fix for 2 years".

Method:
1. For each start year Y from 1995 to 2022 (a full 5-year window), hide every start year whose window overlaps Y's window.
2. `decide` recommends fix 2, 3 or 5 years or tracker as of Y. It uses only windows that ended before Y. Options are ranked by mean outcome minus 0.5 x the worst regret (same rule as the Next Move).
3. Realised best: the cheapest option for a £180,000, 25-year mortgage on the real rate path from Y.

Result (mock-labelled macro table, `lifeline_data.macro.mock_macro_table()`):

| n | Engine hit rate | Baseline "always fix 2 years" | Best constant rule "always take a tracker" |
|---|---|---|---|
| 28 | 71.4% | 14.3% | 71.4% |

Read this result with care:
- `decide` recommends the tracker in all 28 years. The tracker was the realised best in 20 of 28 years (fix 2 years 4, fix 5 years 3, fix 3 years 1).
- So "always take a tracker" scores the same 71.4%. The engine beats the 2-year baseline, but it adds nothing over a fixed tracker rule on this table.
- The table is mock and labelled. With live BoE series the numbers will change.
