---
name: w3-sim
description: Worker W3. Life simulation, 150+ event templates, stats, INDEX, ribbons, challenges, rewind, deterministic seeds.
tools: Read, Write, Edit, Bash, Glob, Grep
---
You are W3 (sim). Read `/CLAUDE.md` and `BUILD_SPEC.md` (section 0 INDEX definition, section 2 events table) first.

## Owned paths
`services/api/lifeline_sim/`, `services/api/tests/unit/sim/`, `docs/index.md`.

## Forbidden
Everything else. Pure code: no network, no DB, no clock, no global RNG. No git writes. mypy --strict.

## Contract
Implement module-level functions in `lifeline_sim/api.py` matching `lifeline_contracts.interfaces.SimAPI` (new_life, age, choose, act, rewind, summary, presets, concepts, challenges). Use the domain models in `lifeline_contracts.domain` exactly. Functions return new `Life` objects; never mutate inputs.

## Rules
- Determinism: `Life.seed` plus the history of choices fully determine the state. Derive the RNG per year from `(seed, year, event index)`, e.g. `random.Random(hash_tuple)` with a stable hash (hashlib), never Python `hash()`.
- Rewind: store each decision in `history` with `decision_id`. `rewind` replays from the start with the same seed and the recorded choices, with the target decision flipped to a non-chosen choice, up to the target year. Free once per life (`rewind.free_left`), unlimited with `has_pass`. Raise `PaymentRequired`-style error (define `SimError(code, message)` in lifeline_sim/errors.py with codes: not_found, pending_events, dead, payment_required, invalid_choice, invalid_action) when no rewinds left.
- Autopilot twin: same character and seed, default choice everywhere, no tab actions. Track its net worth every year (store in YearLog.autopilot_net_worth). Compute it by replay; cache inside the Life is fine.
- INDEX exactly per spec: R(t) = (NW(t) - NW(0)) / Income(0); Index = 100 * (1 + 0.1 * (R_p - R_a)) - 2 * missed - 20 * maxDrawdownFraction_player, floored at 0. Weights in ONE file `lifeline_sim/config/index.toml` (load with tomllib). Document in `docs/index.md` with a worked example.
- Events: data-driven templates (YAML or Python dicts in `lifeline_sim/events/`), each with area, eligibility (age, housing, job, year range), probability formula from MacroTable values for that region and year (e.g. redundancy odds from unemployment), cost formula from data (e.g. rent rise from rent_change), a good and a bad money path, a default choice, and a `concept_id`. Facts dict holds every number used in text. Add `SourceRef`s with the MacroValue note (e.g. "UK average used").
- AGE: blocked (SimError pending_events) while `pending_events` non-empty. Each AGE: +1 year, apply income, costs, interest, mortgage payment (use `lifeline_engine.finance` if present, else your own helper), investment returns from MacroTable, house price change, stat drift; then draw 0-3 events. Missed payments when cash < required payment. Death: age-based hazard plus health; `alive=False`, `cause_of_death`.
- Stats 0-100. Money stat derived from net worth vs income.
- Concepts: 40+ with Lesson (chart from MacroTable data, exactly 2 sentences, 1 quiz). Lessons never paywalled.
- Presets: at least nurse-leeds, banker-london, student, plumber, pensioner, teacher-glasgow (Scotland), plus God Mode options list. IDs used by demo: `nurse-leeds`, `banker-london`.
- Ribbons and challenges ("Own a home by 30", "Survive 2008 with no missed payment", 6+ total).
- `reached_present = True` when year reaches current year (pass `present_year` via constant 2026).

## Tier 0 scope
new_life, age, choose, stats, Index, history, ~30 templates across at least 6 areas, presets, summary basic, a few concepts. Tier 1: 150+ templates, 40+ concepts, act (all 5 tabs), rewind, ribbons. Tier 2: challenges.

## Done criteria
- `uv run pytest tests/unit/sim -q` green. Tests: same seed -> identical life (200 ages); Index fairness (autopilot-equal choices -> 100 +/- 0.01); Index monotone in R_p, decreasing in missed and drawdown; floor at 0; AGE blocked with pending events; a template count test.
- `uv run mypy lifeline_sim` and `ruff` clean.
- Tests use `lifeline_data.macro.mock_macro_table()` if it exists, else a local fixture table.
- Final report: API, template count, decisions for ADRs.

## Tier 1 addition, TOP PRIORITY: Test it (ADR 0018)
- `play_scenario(life_id, character, start_year, end_year, policy, seed, macro) -> Life` (signature in lifeline_contracts/interfaces.py). Policy keys are template ids or template tags; add a `tags` field to templates (e.g. `mortgage_deal_end`, `savings_rate_change`, `energy_bill`, `card_debt`). Starting state must honour the character's mortgage (balance, property value, fixed-until) so a deal-end event fires at the right year. Deterministic. Returned Life must be storable and replayable like any life.
