# ADR 0008: Engine conventions (W2, Tier 0)

- Status: accepted
- Date: 2026-10-17

## Decision
- Mortgage maths: UK repayment annuity, monthly compounding (r = annual % / 1200), term rounded to whole months. Check: £180,000, 25 years, 4.98% gives £1,050.17 a month.
- Synthetic population: IPF over region (12) x age band (6) x occupation group (9) x tenure (4) x income band (5). Regional tenure from `OWNER_OCCUPIED_SHARE`, unemployment from `UNEMPLOYMENT`, pay and house prices scaled by regional `MEDIAN_PAY` and `HOUSE_PRICE`. Other marginals are labelled seed approximations.
- Twins: Mahalanobis k-NN with `pinv(cov + 1e-6 I)` because one-hot housing makes the covariance singular.
- Period matching: z-scored UK macro state (bank rate, rate change, CPI, house price change, unemployment, stock return), Euclidean k-NN.
- Decision: options simulated for 20 twins across 5 matched past periods over 5 years. Only windows that ended before the decision year are used (no look-ahead).
- Backtest: walk-forward. Overlapping windows are hidden. Baseline "always fix for 2 years".
- Labelled assumptions without a data source: tracker = Bank Rate + 1.0, savings = Bank Rate - 0.5, fund fee 0.2%, unsecured debt = Bank Rate + 15.
- Engine has no clock. The API overwrites `generated_at` with server time.
