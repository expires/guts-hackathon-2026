# ADR 0031: Ask Penny, a chat that answers only through engine tools

- Status: accepted
- Date: 2026-10-17

## Decision
- `POST /v1/chat` (non-streaming), `GET /v1/chat/threads`, `GET /v1/chat/threads/{id}`.
  - Threads and messages are stored per user in Postgres and deleted with the account.
- Loop (W5 builds it, W4 wires it):
  - Anthropic tool use with `LLM_MODEL` (Opus).
  - At most 5 tool calls per turn.
  - Overall timeout = 2 x `LLM_TIMEOUT_SECONDS`, with bounded retries.
- Tools (W2; ADR 0033): `next_move`, `test_move`, `finance_summary`, `spend_prediction`, `cash_flow_projection`, `life_replay`, `news_search`, `rate_decision_dates`, `facts_table`. Each returns `result`, `facts[]` (id, value, unit, label) and `sources[]` (SourceRef).
- **The LLM never produces a number.**
  - Allowed numbers = the union of tool facts and facts-table entries used in this turn.
  - On a verifier failure: one rewrite, then a plain template summary of the tool results (`verified: false`).
  - An unverified number is never sent.
- Highlights map each number in a bubble to a fact id and a source id. The client makes them tappable.
- Sources are grouped as "Your data", "Live sources" and "General knowledge". "Not financial advice" appears only on the sources card footer.
- System prompt (versioned in `lifeline_explain/prompts.py`):
  - Penny is calm and competent. Sentence case, no filler, no exclamation marks, no markdown, no emoji.
  - Bubble 1 gives the answer, then the reason in one sentence. A caveat goes in its own bubble. At most one follow-up question, in its own bubble.
  - Each bubble has 1-3 sentences. At most 4 bubbles; for anything longer, Penny offers a summary.
  - She uses what the app already knows and does not ask again.
  - When challenged: rerun the tool, start with "Fair…", and correct plainly if wrong.
  - Ambiguous requests get one either/or question.
  - General knowledge is allowed for concepts only, labelled, with no numbers.
  - Out of scope (stock picks, regulated advice, unrelated topics): a fixed short reply plus a link to the Next Move, with reaction `shrug`.
- Reactions: `eyes` (data lookup), `brain` (engine, replay, projection), `thumbs` (confirmed action), `tick` (action done), `question` (low confidence), `shrug` (out of scope). The reaction is set within 1 s, before the answer.
- Proactive messages (worker): only for time-sensitive money events (deal ending within 30 days, a price rise, a budget over its limit). At most 1 a day, as a notification that opens the chat.
- Presentation mode applies to all chat output.
- Chat serves the one decision; it never makes a different decision from the engine.

## Implementation notes (W5)
- Prompt version `penny-v1`. Tools, `tool_choice` auto and a JSON output schema in one call (SDK 1.15). At most 5 tool calls; unknown tools are rejected; tool input is validated with Pydantic before it runs.
- Numbers inside engine-written text fields (`action`, `headline`, labels, evidence) and test-period years count as allowed facts, extending the ADR 0019 template rule. Target: W2 emits these as explicit facts, so this exception can go.
- News gives no number facts. Rate-decision tools give date facts (days until, day, year).
- Confidence is set by code (the `*.confidence` fact, else a fixed value per outcome), never by the model.
- `ChatResponse.links` (next_move, test_it, why, plan) carries in-app destinations. The out-of-scope reply links to the Next Move.
- Presentation mode is applied by the client to all chat output.
- With no LLM, the service calls `next_move` and returns a template summary (`verified: false`).

## Amendment: perceived speed (streaming)
- `POST /v1/chat/stream` returns Server-Sent Events. Each `data:` line is one `ChatStreamEvent`, in this order:
  1. `reaction` within 1 s, from `quick_reaction`, before any LLM call.
  2. `tool_step` for each **real** tool call as it starts, with a plain label ("Checking Bank of England…", "Replaying 2022…", "Projecting your cash…").
  3. `verifying` ("Checking the numbers…") when the verifier runs.
  4. `bubble` events one at a time. Each is emitted only after it passes the verifier, with its highlights.
  5. `done` with the full `ChatResponse`.
  - On failure, an `error` event, then `done` with the template summary.
- No fake steps. A step label is shown only for a tool call that actually runs.
- `POST /v1/chat` (non-streaming) stays as the fallback, with identical content.
- iOS (Ask Penny UI step):
  - typing dots under Penny while working;
  - tool steps as one small grey line that updates in place;
  - each bubble appears after a typing pause of 400-700 ms, scaled to its length;
  - fallback to the non-streaming endpoint if the stream fails.
- Measured on Railway and reported in STATUS: time to reaction, time to first bubble, total time.
- W2 now emits every number inside tool text fields as a fact (`<tool>.text.<path>.n<i>`). The verifier exception for engine-written text is removed.

## Measured on Railway (2026-10-17, Opus, live BoE data, manual-entry user)
| Question | Reaction | First bubble | Total |
|---|---|---|---|
| Why this move? (first call after deploy) | 3.35 s | 12.4 s | 12.5 s |
| What if I lose my job? | 0.32 s | 7.7 s | 7.7 s |
| What's happening with interest rates? | 0.32 s | 8.7 s | 8.7 s |
- Reaction meets the 1 s target after warm-up. The first call after a deploy is a cold start; a startup warm-up is a follow-up.
- Bubbles arrive together after verification, because the model writes the whole answer in one call. The client paces them (400-700 ms). Per-bubble streaming would need the LLM to stream bubbles with incremental verification; not done.
