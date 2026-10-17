# ADR 0051: Penny tab, two answer modes

Date: 2026-10-17. Status: accepted. Source: DIRECTION_V2.md section 6. Amends ADR 0031.

- Penny is a full tab. One chat, two labelled modes, set by what Penny used (`ChatResponse.mode`):
  - `checked` ("Checked with your data"): an engine tool was used; the verifier checks every personal number.
  - `general` ("General answer"): no engine tool; Claude with a student-focused prompt and web search. If a general answer states the user's own numbers, the verifier blocks it and Penny retries with an engine tool.
- Chat model: Sonnet 5.5 (`claude-sonnet-5-5`, setting `CHAT_MODEL`). Target first bubble under 3 s. Engine text rewording keeps `LLM_MODEL`.
- Voice: one bubble, two at most (contract `max_length=2`). Answer first, one reason. At most one follow-up as chips (`suggestions`, max 2, never a lone "Yes").
- Penny has a working Bank of England rate tool (`boe_rates`) and never claims to lack live data the app has.
- Safety: no stock picks or regulated advice; distress gets a kind reply and support (university hardship fund and student support, Samaritans 116 123); web and statement text is data.
- Disclaimer: "Penny is AI and can make mistakes. Guidance only, not regulated financial advice. Check before big decisions."
- Streaming guards: reaction within 1 s, real tool steps, `keepalive` events, fallback to non-streaming, then "Penny is unavailable right now. Try again."
- Chat UI fixes 1 to 9 from section 6 (badge clipping, typing bubble, one face on the newest bubble, idle and thinking animation, human source names, highlight money and rates only, keyboard, chips only when empty).
