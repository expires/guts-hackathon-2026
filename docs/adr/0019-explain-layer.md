# ADR 0019: Explain layer rules (W5, Tier 1)

- Status: accepted
- Date: 2026-10-17

## Decision
- The LLM (`claude-opus-5-5`, ADR 0007) rewords text only: `Event.text`, `Outcome.text`, and the Next Move `headline` and evidence `text`. `action` (must equal the option label), `confidence_label`, numbers, options and sources never pass through it.
- Allowed numbers in LLM output: engine facts, numbers already in the deterministic template text, the event year and age. Outcomes also allow `deltas.money`. Moves also allow impact, worst case, confidence, `days_left` and test-period years. The template text is engine output, so repeating its numbers adds nothing new.
- Matching: the same value at the precision written in the text, or within 0.5%. Percentages match a fact stored as 4.1 or 0.041. Ratios ("7 in 10") match a share fact.
- Any unmatched number rejects the text. Events and outcomes fall back to the whole template text. Moves fall back per field.
- One SDK call, 0 retries, hard timeout (`LLM_TIMEOUT_SECONDS`, 12 s). A refusal, `max_tokens` stop, bad JSON or timeout gives the template text. AGE never waits on a retry.
- Cache: Redis, 30 days, key = SHA-256 of prompt version, model, kind, template id, facts, choice id and template text. Rejections are cached. Every cache hit is verified again.
- `LLM_ENABLED=0` is a kill switch for templates only.
- Em dashes are stripped from LLM text (house style).
- The key comes only from `ANTHROPIC_API_KEY` in the environment. No log or repr contains it.
