# ADR 0023: Confidence for multi-option moves, and honest accuracy reporting

- Status: accepted (amends ADR 0018 and ADR 0020)
- Date: 2026-10-17

## Context
- Measured against doing nothing, a tracker beats the revert-to rate in every (twin, period) pair. Mortgage confidence was always 1.0 ("All twins did better"). That number carries no information about the choice the user faces: which option to take.
- On the mock table, `decide()` recommends a tracker in all 28 backtest years. Its hit rate (71.4%) equals the rule "always take a tracker". The engine shows no skill over that fixed rule on this data.
- The spend model (ADR 0017) is worse than the weekday-average baseline for one persona (homeowner-leeds: MAE £28.74 vs £26.93).

## Decision
1. **Confidence for a move with several options** = the share of (twin, period) pairs, including the stress period, where the recommended option was the best of the move's options. The label reads, for example, "In 6 of 10 similar cases this was the best choice". For single-option moves (cancel, cut), confidence stays as defined in ADR 0018.
2. **Report skill honestly.**
   - `/v1/evaluation`, `NextMoveResponse.backtest` and `docs/prediction.md` show the engine against two baselines: the naive baseline ("always fix 2 years") and the best constant rule ("always take a tracker").
   - The spend model's MAE is shown next to the weekday baseline for each persona, including personas where the model loses.
   - No tuning to beat baselines on fixture data.
3. `FinanceSnapshot.holder` (name, birth year, occupation, region, town, postcode) replaces guessed age and region in the profile.
4. The `Reason` docstring now matches ADR 0017: each effect is per feature group, so effects need not sum exactly to predicted minus baseline.

## Consequences
- The demo card may show a lower, but meaningful, confidence.
- Judges see where the engine adds value and where it does not.

## Notes from V2 Tier 1
- Single-option moves whose saving does not depend on markets (cancel a subscription, cut a budget) use a non-twin basis for confidence: certainty of the saving, or the share of recent months the user stayed at the target. The label states that basis. This is an accepted exception to ADR 0018's twin wording.
- Subscription price rise: one step up of up to 50% still counts as the same subscription with a price rise. The 10% rule applies to stable amounts. (Amends ADR 0016's wording.)
- Emergency-fund confidence uses a seeded draw. Each user has a fixed seed (sha256 of the subject), so a user always sees the same value.
