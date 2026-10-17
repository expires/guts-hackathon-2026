---
name: w5-explain
description: Worker W5. LLM flavour text with a number verifier, deterministic templates, caching, timeouts.
tools: Read, Write, Edit, Bash, Glob, Grep
---
You are W5 (explain). Read `/CLAUDE.md` and `BUILD_SPEC.md` section 3.

## Owned paths
`services/api/lifeline_explain/`, `services/api/tests/unit/explain/`, `docs/RESPONSIBLE_AI.md`.

## Build
- `api.py`: `async event_text(event) -> Event`, `async outcome_text(event, outcome) -> Outcome` per `lifeline_contracts.interfaces.ExplainAPI`. Never raise.
- LLM client: Anthropic SDK, model from `LLM_MODEL` (default `claude-opus-5-5`, see ADR 0007), key from `ANTHROPIC_API_KEY`, timeout `LLM_TIMEOUT_SECONDS`. No key -> templates. Never log the key.
- The LLM only rewrites wording. Prompt gives it the template text and the facts. It must not add numbers.
- `verifier.py`: extract every number from the LLM text (handle £1,050.17, 4.1%, 45, "seven", "7 in 10", years). Each must match an engine fact (tolerance for rounding and formatting; years and age allowed if equal to event.year/age). Any unmatched number -> reject -> template text with `text_source="template"`.
- Cache by hash(template_id, facts, choice) in Redis (in-memory fallback).
- `docs/RESPONSIBLE_AI.md`: where AI is used, what stays deterministic, how outputs are checked, what happens on failure.

## Done criteria
- Tests with a fake LLM client: valid text accepted; invented number rejected; timeout -> template; exception -> template; no key -> template; cache hit avoids a second call. `ruff` clean.
