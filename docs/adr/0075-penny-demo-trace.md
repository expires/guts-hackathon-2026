# ADR 0075: Penny demo trace for judges

Date: 2026-10-18. Status: accepted.

- `make penny-trace STUDENT=<first name or sample id> Q="<question>"` runs one real Penny request against the live server for that sample student (a fresh demo account, sample import, then `POST /v1/chat/trace`) and prints the steps in the terminal. No app change.
- Output shape (one coloured line per step, readable at a large font):
  `QUESTION`, `SCOPE` (money, student life or declined, with the check mode), `TOOL` (each call with its arguments), `ENGINE` (each result; before and after for what-ifs), `DRAFT`, `VERIFY` (each number, where it matched: engine, input or official fact, pass or fail; the rewrite or fallback when one fails), `ANSWER` (total time and first-bubble time).
- `POST /v1/chat/trace` (contract `ChatTrace`, `TraceStep`) is off unless `PENNY_TRACE_ENABLED` is set on the server; it only returns the caller's own data. The output never contains keys, tokens, headers or prompts; a test checks this.
