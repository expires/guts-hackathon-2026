# ADR 0024: Tier 1 sim choices (W3)

- Status: accepted
- Date: 2026-10-17

## Decision
- Scenario setup (`play_scenario`) is stored in the first history entry (`setup/scenario?...`), so replay needs no change to `Life`.
- Forced (focused) scenario events and related mortgage events do not count toward the 3-events-a-year cap. Other events stay identical across options.
- Policy values accept aliases. An unknown value takes the default.
- Each tab action is a decision with an encoded choice id (`<tab>/<action>?amount=...`). The autopilot twin never takes actions.
- Variable and tracker mortgage rates come from BoE `IUMTLMV` and `IUMBV48` when the table has them. Fallback: Bank Rate + 2.0 and + 1.0 (labelled).
- A tracker deal follows the tracker rate for 2 years.
- Model rules added: state pension at pension age also when out of work; Help to Buy loan added to the mortgage balance; "pay the minimum" on card debt adds one more year of interest.
- Rewind uses one rewind even with the pass (the pass makes them unlimited). Unlocked concepts survive a rewind. Ribbons earned in or after the target year are dropped.
- `scenario_cost(life, macro)` defines the cost per tag (mortgage payments, savings interest given up, energy bills, card interest and fees, subscription and budget changes). Callers pass the life's pinned table.
- Preset starting money scales with the start year unless the preset was edited.
- 152 templates, 50 concepts, 31 actions, 11 ribbon kinds, 7 challenges. Lives hit the event cap most years (about 2.85 events a year).
