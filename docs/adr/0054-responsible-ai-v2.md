# ADR 0054: Responsible AI, V2

Date: 2026-10-17. Status: accepted. Source: DIRECTION_V2.md section 9. Amends the "How Penny uses AI" text (ADR 0043 amendment).

- The engine calculates and ranks; AI explains. AI never makes the decision.
- Personal-money answers use engine tools; every number is checked; label "Checked with your data".
- General answers work like a normal assistant with web search; label "General answer"; sources shown.
- Safety rules and support options as in ADR 0051.
- AI failure: engine text falls back to templates; chat shows "Penny is unavailable right now".
- W5 updates `ai_disclosure.json` and RESPONSIBLE_AI.md; `make ai-disclosure` copies it to the app.
