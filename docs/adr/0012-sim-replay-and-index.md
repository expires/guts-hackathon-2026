# ADR 0012: Sim replay model and INDEX edge cases (W3, Tier 0)

- Status: accepted
- Date: 2026-10-17

## Decision
- Replay is the source of truth. State = f(character, mode, start year, seed, recorded choices, MacroTable). Rewind = replay with one choice flipped. A bounded in-process memo makes normal play about 1 ms per call. A memo hit returns exactly what a replay would build.
- The API pins one MacroTable per life (sha256 snapshot, W4). A data refresh never changes a past life.
- RNG keys are SHA-256 of `(seed, year, "event", template_id)`. Adding templates does not change the existing rolls.
- Templates are YAML validated by Pydantic. Formulas run in a safe `ast` evaluator, never `eval`. Sources come from the macro names each formula reads.
- `decision_id` = `event_id` (`ev-<year>-<n>`). Tab actions (Tier 1) record `choice_id` as `<tab>/<action>?k=v`.
- INDEX follows BUILD_SPEC exactly, including the absolute penalties. A player who copies the autopilot scores exactly 100 when the life has no missed payments and no drawdown. With penalties, the score is 100 minus those penalties. The fairness test runs on penalty-free lives. No upper cap. Display formatting is a UI concern.
- Drawdown base is max(peak net worth, Income(0)). Income(0) is floored at £10,000 (`config/index.toml`).
- Added money rules: debt write-off above 3x income (bankruptcy), graduation at 22 with a maintenance loan, bills shocks as one-year costs, pay growth carried past the end of the table.
- Simplifications: 2025/26 tax bands for every year; Scotland uses rUK bands.
- New `SimError` code `invalid_input` (start age below 16 and similar). The API maps it to 422.
