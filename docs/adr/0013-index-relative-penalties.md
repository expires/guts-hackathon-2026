# ADR 0013: INDEX penalties are measured relative to the autopilot twin

- Status: accepted (supersedes the INDEX penalty line of ADR 0012)
- Date: 2026-10-17

## Context
BUILD_SPEC section 0 gives two requirements:
- Formula: `Index = 100 x (1 + 0.1 x (R_p - R_a)) - 2 x missedPayments - 20 x maxDrawdownFraction_player`, floored at 0.
- Test: "same choices as autopilot -> 100 +/- rounding".

With absolute player-only penalties, the two conflict. V2 played 25 all-default lifetimes. None had zero missed payments and zero drawdown, so copying the autopilot almost never scored 100.

## Decision
`Index = max(0, 100 x (1 + 0.1 x (R_p - R_a)) - 2 x (missed_p - missed_a) - 20 x (dd_p - dd_a))`

- `missed_a` and `dd_a` come from the autopilot twin (same character, same seed, default choices).
- Copying the autopilot gives exactly 100. The fairness test asserts this for every seed, with no penalty-free precondition.
- When the autopilot has no missed payments and no drawdown, the value equals the BUILD_SPEC formula.
- The player can beat the twin by missing fewer payments or holding up better in a crash.
- The weights (0.1, 2, 20) and the floor stay in `lifeline_sim/config/index.toml`.
- `docs/index.md` shows both forms and this reason.

## Consequences
- Fairness holds exactly. The score measures the effect of choices, not luck shared with the twin.
- The API keeps `IndexState.missed_payments` and `max_drawdown` as the player's values. The twin's values appear in the docs and the summary text.
