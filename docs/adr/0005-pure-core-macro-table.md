# ADR 0005: Engine and sim consume an annual MacroTable

- Status: accepted
- Date: 2026-10-17

## Context
Engine and sim must be pure and deterministic. Odds and costs must come from real data for that person, place and year.

## Decision
- Adapters produce `Observation`s. `lifeline_data` reduces them to an annual `MacroTable` (`lifeline_contracts/macro.py`), keyed by `(MacroKey, year, region)`.
- Engine and sim take the table as an argument. Same table plus same seed gives the same life.
- Missing region falls back to the UK value with note "UK average used". The event shows the note.
- The API stores the table hash with each life, so a rewind or replay uses the same numbers.

## Consequences
- Sub-annual detail is lost. Annual granularity matches one AGE tap = one year.
