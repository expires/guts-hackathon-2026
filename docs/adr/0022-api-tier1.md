# ADR 0022: Tier 1 API choices (W4)

- Status: accepted
- Date: 2026-10-17

## Decision
- Reference day: every engine call uses the finance snapshot's `as_of` as "today", so one snapshot always gives the same answers.
- Seeds: next-move seed = sha256(subject). Test it seed = sha256(subject + move id). Testing the same move again gives the same lives.
- Test it shifts the character's `birth_year` so the user is the same age at `test_period.start` as today.
- A move id that is not in the stored next move triggers one recompute before a 404. A non-testable move returns 409.
- Outcome path: last value of each year, dated 31 December; the first point is the starting state. Worst year = the largest year-on-year fall.
- Fixture profiles take name, age, region, town, postcode and job from the W1 persona.
- The Test it summary is a fixed template; every number in it comes from the outcomes.
- LLM text for new events is stored in the life, so replays never call the LLM again. Action outcomes are not reworded (no event to anchor the verifier). Test mode sets `LLM_ENABLED=0`.
- Store: a `user_docs` table (owner, kind, JSON) holds plan items, budgets, goals and guesses.
- Next Move first call takes about 5 s (LLM rewording, run in parallel); repeat calls about 0.06 s; Test it about 0.04 s.
- `make test` now includes Tier 1 tests by default (only `tier2` and `live` are deselected).
