# ADR 0007: Use Claude Opus 5.5 for flavour text

- Status: accepted
- Date: 2026-10-17

## Context
BUILD_SPEC section 2 sets `LLM_MODEL` default to `claude-haiku-5-5`. The user asked for Opus and accepts the cost.

## Decision
- `LLM_MODEL=claude-opus-5-5` in `.env.example` and `.env`. The code default in `lifeline_explain` is also `claude-opus-5-5`.
- The model remains configurable by env.

## Consequences
- Higher latency per call. The explain layer keeps its timeout (`LLM_TIMEOUT_SECONDS`) and template fallback, and caches outputs, so a slow call never blocks AGE.
- Role is unchanged: the LLM writes wording only. The verifier still rejects any number that does not match an engine fact.
