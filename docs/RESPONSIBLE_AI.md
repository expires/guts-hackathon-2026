# Responsible AI

This document states where Penny uses a large language model (LLM), what stays deterministic, how the system checks LLM output, and what happens when the LLM fails.

## How Penny uses AI

This section is also shown in the app (You tab) and in the README. Source: `services/api/lifeline_explain/ai_disclosure.json`. A unit test keeps the two in step. ADR 0043, amended by ADR 0054 and ADR 0058.

### Where AI is used

- An AI model (Claude Opus, from Anthropic) rewords the text of game events, their outcomes and the Next Move card.
- Ask Penny uses a faster model (Claude Sonnet, from Anthropic) to write chat answers.
- Ask Penny gives two kinds of answer. Checked with your data: Penny used the app's tools. General answer: Penny works like a normal assistant and can search the web.
- Lessons are fixed text. AI does not write them.
- The app never calls the AI model. Only our server calls it.

### What stays deterministic

- The engine calculates and ranks the options and picks your Next Move. AI explains it. AI never makes the decision.
- Every number about your money comes from your data, a public data source or the engine.
- The engine writes the trade-off of each move (What you give up). Penny can only say it in other words.
- The game engine decides every event, outcome and money change. The same seed gives the same game.

### How output is checked

- Checked with your data: a number verifier checks every number against the facts from the app's tools. It also checks the unit: a money fact needs a £ sign and a percent fact needs a % sign. Code: services/api/lifeline_explain/verifier.py.
- General answer: Penny must not state your own money numbers. If she does, the app blocks the answer and Penny tries again with the app's tools. Web sources are shown under the answer.
- Rules questions (tax, student loans, ISAs, Railcard and similar): Penny uses the app's facts table first and shows the official page and the date it was checked. If the rule is not there, she searches official sites only, such as gov.uk, and quotes a number only if the official page states it. If no official page states it, she says so and gives no number.
- Penny must not say she has no live data. The app has live Bank of England rates, and a test checks this rule.
- Safety: Penny does not pick shares or crypto and does not give regulated advice. If you sound in distress, she replies kindly and points to your university hardship fund, student support and Samaritans (116 123).
- Prompt injection tests put hostile text in statements, news headlines and user messages. The model gets this text fenced as data, and the system prompt treats web pages as data too. The tests check that hostile text cannot change a rule or add a number.
- Golden tests for both answer modes, safety and live rates: services/api/tests/unit/explain/test_chat.py and services/api/tests/unit/explain/test_chat_v2.py, services/api/tests/unit/explain/test_chat_v6_direction.py and services/api/tests/unit/explain/test_official_sources.py.
- Verifier tests: services/api/tests/unit/explain/test_explain.py and services/api/tests/unit/explain/test_trade_off.py.

### What happens when AI fails

- No AI key, an AI error or a failed check: events, outcomes and the Next Move card show the engine's template text. The template text is complete and correct.
- If a checked answer fails the number check, Penny gets one rewrite. If it fails again, Penny shows a summary of the tool facts, marked as not checked.
- If the AI model is off, times out or fails before any tool runs, the chat shows: Penny is unavailable right now. Try again.
- By default, each AI call stops after 12 seconds and an Ask Penny answer stops after 24 seconds.
- A number that fails the check is never shown.

## Where AI is used

The LLM rewrites wording only. It never decides an outcome, a number, a ranking or a recommendation.

| Text | Function | Fields the LLM may change |
|---|---|---|
| Game event text | `lifeline_explain.api.event_text(event)` | `Event.text` |
| Choice outcome text | `lifeline_explain.api.outcome_text(event, outcome)` | `Outcome.text` |
| Ask Penny chat answers (ADR 0031, 0051) | `lifeline_explain.chat.answer(request, ctx)` | Bubble wording. Checked mode: every number comes from a tool fact. General mode: no personal numbers. |
| Next Move card wording (ADR 0018) | `lifeline_explain.api.move_text(move)` | `Move.headline`, `EvidencePoint.text` (never `Move.action`: it must match the option label) |

- Rewording model: `claude-opus-5-5` (ADR 0007). Set by the `LLM_MODEL` environment variable.
- Chat model: `claude-sonnet-5-5` (ADR 0051). Set by the `CHAT_MODEL` environment variable.
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

## Ask Penny (ADR 0031, 0033, 0034)

Penny answers chat questions in two modes (ADR 0051). The LLM chooses which tool to call and writes the wording.

### Two modes (ADR 0051)
- `mode: "checked"` ("Checked with your data"): at least one app tool ran (engine, `boe_rates`, `facts_table`, news, rate dates). Every number must match a tool fact from this turn.
- `mode: "general"` ("General answer"): no app tool ran. Claude answers like a normal assistant with a student-focused prompt and Anthropic's server web search tool (`web_search_20260209`, at most 2 searches). Web results become sources in the `general_knowledge` group with their URL.
- A general answer must not state the user's own money numbers. The service compares each `£` number with the user's personal facts (`EngineToolSet.personal_facts()`: the `finance_summary` money facts). A match blocks the answer, and the model gets one retry that tells it to call an app tool. A percent next to a rate word with no web search is blocked the same way. A second failure gives the template.
- Rules questions (ADR 0058, `lifeline_explain/official.py`): facts table first, with each source's official URL and "checked <date>". Otherwise web search with `allowed_domains` set to the official domains; results from other domains are ignored; a rule number counts only if it appears in the cited official text (`web.N` facts), else one retry, then the answer without that number, or "I could not find an official source" with no number. Facts-table answers are `checked`; web-only answers are `general`, with the official page and "retrieved <date>" as the source.
- V6 fixes: distress and pick checks normalise text (NFKC, no zero-width characters) and also run on the model's answer; a general answer that names a buy or sell of an asset gets the fixed refusal; in general mode "GBP", bare numbers next to money words and rounded forms ("about £140", "£0.1k") count as the user's money, and "your balance is £X" claims are blocked unless a tool backs them.
- A general answer that says Penny lacks live or current data is blocked the same way. The retry tells the model to call `boe_rates` (live Bank of England rates: Bank Rate, savings, mortgages, credit cards).
- Fixed replies before any LLM call: distress (kind reply, university hardship fund, student support, Samaritans 116 123) and stock, fund or crypto picks or regulated advice (polite refusal).
- Speed (V1, first bubble under 3 s): the system prompt is static and sent with `cache_control`. Before the first model call the service runs `finance_summary` and `next_move` (and `facts_table` for rules questions) and sends their facts as APP DATA, so a personal question needs one model call; those tools are not offered again unless the user challenges the answer, and they count as tool calls only when the answer uses them. Chat calls run without thinking, effort low, `max_tokens` 700. The first bubble streams as soon as its JSON is complete and it passes every check on its own; a failing second bubble is dropped instead of a rewrite. Tool calls in one model step run in parallel.
- Tools (ADR 0060): next_move, test_move, finance_summary, user_balance, cash_flow_projection, spend_prediction, habit_score, facts_table, boe_rates, inflation (ONS CPI), fx_convert (Frankfurter, ECB reference rates), news and rate dates, official web search. Each real call streams a plain step label such as "Checking exchange rates…".
- Penny never asks the user for rates, conversions, public dates or public facts. An answer that asks for one is blocked and retried with an instruction to use the tool.
- Suggestion chips answer Penny's follow-up question; no question means no chips.

### Loop
1. The service builds the prompt: the versioned system prompt (`prompts.PENNY_PROMPT_VERSION`), earlier turns, what the app knows, the screen context and the user message.
2. The model calls tools (`tool_choice` auto). At most 5 tool calls per turn. Extra calls get an error result.
3. Each tool validates its input with a Pydantic model before it runs. Bad input returns an error result to the model.
4. Tool results go back as JSON: `result`, `facts` (id, value, unit, label) and `sources`.
5. The final answer is JSON (schema output format): reaction, out_of_scope, summary_available and bubbles.
6. Overall deadline: 2 x `LLM_TIMEOUT_SECONDS`. The SDK retries once on transient errors.

### Untrusted text (ADR 0034)
- These texts sit inside `<untrusted source="...">...</untrusted>` blocks: the user message, earlier user messages, profile values, news headlines, merchant names and every other free-text string in a tool result.
- Before fencing, the service applies NFKC normalisation to the text. It then removes control and format characters (zero-width, bidi, Unicode tag characters U+E0000 to U+E007F) and replaces every `<` with `‹`. A hostile string cannot open or close a block, whether it is spaced, fullwidth or split.
- The system prompt says that block content is data. The model must never follow it or take a number from it.
- Only machine fields (ids, units, statuses, dates, URLs) stay unfenced.
- No key, token or other user's data enters a prompt or a log.

### Number checks
- Allowed numbers are the union of the tool facts from this turn, `facts_table` entries included.
- The engine tools emit every number inside their text fields as a fact (`<tool>.text.<path>.n<i>`). The verifier has no exception for engine text.
- The service drops a `.text.` fact when its path holds a user or bank text key (merchant, name, description, payee, subscription, bill, headline and others), or when its value appears inside such a string in any tool result this turn. Test case: the merchant "Netflix 77777 0%" can never make 77,777 or 0% a fact.
- Matching is unit-aware for chat:
  - Money facts need "£" or "pounds".
  - Percent facts need "%" or "percent", or a ratio such as "7 in 10".
  - Count and duration facts never match a "%" or "£" number.
  - "one" and "none" before a unit word count as numbers. "nil" and "nought" count as 0.
- News results carry no facts. Penny cannot cite a headline as a source for a number.
- Trade-offs (ADR 0042): the engine writes each move's `trade_off`. The numbers in its points become facts with ids `tf_<move_id>_<key>`, so Penny may quote them. The system prompt (`penny-v4`) tells Penny to state the trade-off ("What you give up:") when she explains or recommends a move. Any other trade-off number fails the verifier.
- Matching uses the same rules as the event verifier above.
- In checked mode, a general-knowledge bubble may hold no number at all.
- Verifier failure: the service asks the model for one rewrite. A second failure gives a template summary of the tool facts with `verified: false`.
- An unparseable answer, a refusal, a timeout or an error also gives the template summary.
- With no LLM, or when the LLM fails before any tool ran, the response says "Penny is unavailable right now. Try again." with `verified: false`.
- An unverified number is never sent.

### Response rules applied by code
- Highlights map money and rate numbers (units `gbp`, `gbp_per_month`, `gbp_per_year`, `percent`) to a fact id and a source id. Years, dates and counts are checked but never highlighted.
- Source labels use human names, for example "Bank of England · savings rates · live". They never show series codes (`lifeline_explain/source_names.py`).
- Sources are grouped as `your_data` (bank data, the sim), `live_sources` (BoE, ONS, Guardian and others) and `general_knowledge` (GOV.UK facts table, concept answers).
- The output keeps at most 2 bubbles and 3 sentences per bubble. If the model wrote more, `summary_available` is set to true.
- `suggestions` keeps at most 2 follow-up chips of 40 characters or less. Lone answers such as "Yes" and chips with numbers are dropped.
- The output keeps at most one follow-up question.
- The service removes markdown, emoji, exclamation marks and em dashes.
- The service removes "not financial advice" sentences. The disclaimer appears only in `disclaimer`: "Penny is AI and can make mistakes. Guidance only, not regulated financial advice. Check before big decisions."
- A challenge ("are you sure?") with no tool call gets one nudge to call the tool again. The first bubble starts with "Fair".
- Out of scope: the service sends a fixed reply with reaction `shrug`, no facts and no sources.
- `verified: false` always sets the reaction to `question`.
- Penny does not reveal her instructions (system prompt rule). A bubble that repeats 6 or more consecutive words of the system prompt is replaced with a fixed reply.

### Streaming (ADR 0031 amendment)
- `answer_stream` emits events in this order: `reaction` (a keyword heuristic, before any LLM call), then `tool_step` for each real tool call (a server web search is reported after the model call that ran it), `keepalive` every 2 seconds while waiting, then `verifying`, then `bubble` events, then `done`.
- The stream emits a `bubble` only for a verified answer, and only after a per-bubble check that each of its numbers matches a fact.
- When Penny is unavailable, the stream emits `error`, then `done` with the fixed reply. It emits no `bubble` events. The client falls back to `POST /v1/chat`, then shows "Penny is unavailable right now. Try again."
- Step labels contain only engine values and validated integers, never untrusted text.
