# Responsible AI

This document states where Lifeline uses a large language model (LLM), what stays deterministic, how the system checks LLM output, and what happens when the LLM fails.

## Where AI is used

The LLM rewrites wording only. It never decides an outcome, a number, a ranking or a recommendation.

| Text | Function | Fields the LLM may change |
|---|---|---|
| Game event text | `lifeline_explain.api.event_text(event)` | `Event.text` |
| Choice outcome text | `lifeline_explain.api.outcome_text(event, outcome)` | `Outcome.text` |
| Next Move card wording (ADR 0018) | `lifeline_explain.api.move_text(move)` | `Move.headline`, `EvidencePoint.text` (never `Move.action`: it must match the option label) |

- Model: `claude-opus-5-5` (ADR 0007). Set by the `LLM_MODEL` environment variable.
- Provider: Anthropic Messages API, through the official `anthropic` Python SDK.
- The iOS app never calls the LLM. Only the backend calls it.

## What stays deterministic

- The sim engine (`lifeline_sim`) decides every event, choice, outcome, money change and stat change.
- The decision engine (`lifeline_engine`) computes every Next Move: candidates, yearly impact, worst case, confidence, ranking, deadline and evidence facts.
- The engine writes a template text for every event, outcome and move. The template text is complete and correct without the LLM.
- The LLM does not see user identity data. It receives the template text, the engine facts, the event year and age, and choice labels.
- The LLM cannot change these fields: `facts`, `choices`, `deltas`, `good`, `action`, `impact_per_year`, `worst_case_per_year`, `confidence`, `confidence_label`, `options`, `deadline`, `days_left`, `sources`.

## How outputs are checked

Each LLM reply goes through these checks, in this order:

1. Structure. The request uses a JSON schema output format. The service rejects a reply that is not valid JSON, or a Move reply whose evidence list has a different length.
2. Clean-up. The service removes extra whitespace and replaces em dashes. It rejects empty text and text much longer than the template (event and outcome: more than 2x the template length or 160 characters more; move headline: 120 characters).
3. Number verifier (`lifeline_explain/verifier.py`). The verifier extracts every number from the text and checks it against an allowed set.

### Number verifier rules

- Formats it reads: `£1,050.17`, `4.1%`, `12.5 per cent`, `45`, `£4.2k`, `5 million`, number words (`seven`, `twenty`, `dozen`, `half`, `twice`), ratios (`7 in 10`, `seven out of ten`, `1 in every 5`), and years.
- Allowed set: the engine `facts`, the numbers in the template text, the event year and the event age. For outcomes, the set also contains the money change (`deltas.money`). For moves, it contains `impact_per_year`, `worst_case_per_year`, `confidence`, `days_left` and the test period years.
- A number matches when it equals an allowed number after rounding to the precision the text uses (`£1,050` matches `1050.17`), or when it is within 0.5% of an allowed number (`£4.2k` matches `4183`).
- A percent matches a fact stored as a percent (`4.1`) or as a fraction (`0.041`).
- A ratio `a in b` matches a share fact when both round to the same first decimal (`7 in 10` matches `0.7` or `0.68`). The two numbers in a ratio are not checked one by one.
- Signs are ignored, because the text says "lose £300" for a fact of `-300`.
- The word "one" counts only inside a ratio, because "no one" and "the one" are common.
- Any unmatched number rejects the text. Event and outcome: the whole text. Move: only the field that failed. Other fields keep the LLM wording.

The verifier fails closed. A false rejection costs only the LLM wording. The player still sees the correct template text.

## What happens on failure

| Condition | Result |
|---|---|
| `ANTHROPIC_API_KEY` not set, or `LLM_ENABLED=0` | No LLM call. Template text. |
| Call takes longer than `LLM_TIMEOUT_SECONDS` (default 12) | Call is cancelled. Template text. The SDK does not retry. |
| API error, network error, refusal, or truncated reply | Template text. |
| Reply fails a check above | Template text (or the original field for a move). |
| Any unexpected exception in the explain layer | Template text. The functions never raise. |

- `Event.text_source` and `Outcome.text_source` show `"llm"` or `"template"`, so the client and the logs show which text the player saw.
- Logs record the failure type and the unmatched numbers. Logs never contain the API key.

## Caching

- The service caches verified LLM replies in Redis (`REDIS_URL`) for 30 days. If Redis is not available, it uses an in-memory cache and retries Redis after 30 seconds.
- Cache key: SHA-256 of the prompt version, model, kind, template id, facts, choice id and template text. A change to any fact gives a new key.
- A verifier rejection is cached too, so the service does not pay for the same rejected call again.
- A cache hit goes through the verifier again before use.

## Secrets

- The key comes only from the `ANTHROPIC_API_KEY` environment variable. The service passes it to the SDK client and stores it nowhere else.
- No code path prints or logs the key. `ExplainSettings` and `AnthropicLLM` have a `repr` that omits it.

## Tests

`services/api/tests/unit/explain/` uses a fake LLM client. Tests never call the network. They cover: valid text accepted; invented number rejected; timeout, exception and bad JSON fall back to the template; no key falls back to the template; a cache hit avoids a second call; Redis failure falls back to memory; Move rewording changes only the allowed fields.
