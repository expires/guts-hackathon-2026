# ADR 0017: Daily spend prediction and "Guess my spend"

- Status: accepted
- Date: 2026-10-17
- Requested by: the user (Money tab, Tier 1)

## Decision

### Model (engine code, no LLM)
- Target: log(1 + daily spend), where daily spend = sum of outflows that day, excluding transfers, savings, rent, mortgage and other scheduled bills. Bills appear in the bills list, not in this prediction.
- Model: ridge regression (L2, alpha chosen by walk-forward validation) in numpy. The spec allows gradient boosting or regression. Ridge was chosen because:
  - Feature contributions are exact and additive, so the "top 3 reasons in £" are true values, not approximations (gradient boosting would need SHAP).
  - Fixture history is 6 to 12 months (180 to 365 rows). Gradient boosting overfits at that size.
- Features:
  - day of week (one-hot)
  - payday cycle: days since payday, plus a flag for the first 3 days after payday (payday is detected from salary credits)
  - UK bank holiday flag (gov.uk `bank-holidays.json`, W1)
  - weather for the user's region: max temperature and rain (Open-Meteo archive for history, forecast for today, W1)
  - recent trend: 7-day mean of log spend
  - month-end flag
- Range: the 10th and 90th percentiles of walk-forward residuals in log space, mapped back to GBP.
- Reasons: each feature group's contribution is converted to GBP as `predicted - prediction_without_that_group` (baseline = the same day with features at their training means). Groups: weekday, payday, bank_holiday, weather, recent_trend, month_end. The top 3 by absolute effect are shown in plain English ("It is Friday", "You were paid 2 days ago"). The effects shown are in GBP.
- Backtest: walk-forward over the last 90 days. Train on all days before each test day and predict that day. Report MAE, the MAE of the baseline (that weekday's average), and range coverage. The figures appear in `docs/prediction.md` and in the app (`GET /v1/finance/prediction/evaluation`).

### Guess my spend
- One guess per user per day, made before the prediction is shown. The API returns the prediction with `guess` empty until the user guesses. The client hides the number, range and reasons until then. A second guess for the same day returns 409.
- Scoring when the day's actual is known: `points = round(100 x max(0, 1 - |guess - actual| / max(actual, 10)))`. `beat_model` is true when the guess was closer to the actual than the prediction was.
- Streak: consecutive scored days with points >= 70. The response also has `best_streak` and `points_total`.
- Fixtures: until bank OAuth (Tier 2), "today" uses fixture data. The actual for a day becomes known when the fixture history covers it. For the demo, the user can view past days (`date` query parameter) with their actuals.
- Scoring and the streak are pure functions in `lifeline_engine.money.predict` (W2). Guesses are stored per user (W4).

### Owners
- W1: `bank_holidays` source (gov.uk JSON) and Open-Meteo daily weather (archive and forecast) by region centroid, with fixtures. Missing or failing data falls back to mock, labelled.
- W2: `lifeline_engine/money/predict.py`: features, ridge fit, intervals, contributions, backtest, scoring. Writes `docs/prediction.md` with the backtest results.
- W4: endpoints and guess storage.
- W6: Money tab "Guess my spend" card and ViewModels. Draft Views follow the ADR 0016 rule.

## Consequences
- The prediction is explainable and auditable. Every £ in a reason traces to the model's coefficients and that day's feature values.
- With mock fixtures, accuracy figures describe the fixture personas, not real users. Docs and the app say so ("Sample data").
