# ADR 0073: Penny's scope (money and student life) and a sources hub

Date: 2026-10-18. Status: accepted (judge feedback). Amends ADR 0051 (answer modes) and the C5 change of ADR 0072.

## Penny scope (corrected the same day: money AND student life)
- Penny answers money and student-finance questions (budgets, loans, rent, bills, jobs and pay, saving, banking, bursaries, costs of student life) AND general student-life questions (uni services and facilities, studying, housing, getting around, wellbeing services, deadlines, societies, moving to a new city).
- Only questions outside both (coding help, homework answers, celebrity news, recipes with no money angle) get one friendly line plus 2 related suggestion chips. No web search for those.
- Student-life answers keep the "General knowledge" label and the relaxed number check (general numbers such as opening hours pass). Answers about the user's own money keep the strict check.
- Where a student-life answer has a money angle, Penny adds it in one line (for example library hours, then late-night café costs and the weekly budget).
- Try Penny chips: 1 money question, 1 student-life question, 1 mixed. All of this in the 8 languages.
- Tests: "How long is Edinburgh library open?" gets a real answer; "Write my Python essay" gets the short no; "How does my student loan work?" gets a real answer.

## Sources hub
- One screen "Where Penny's data comes from", reachable from the forecast card ("Based on N sources"), from The maths and from You.
- Top: "Penny uses your statement plus N live UK sources. Here is what each one does."
- One card per student-facing source (your statement, official facts, Bank of England, ONS, Nomis, Octopus Energy, Frankfurter, Bank of England MPC dates): name, live or cached status with time, what it gives Penny, which screens use it. A tap shows the latest values and a link to the official page. No homeowner sources.
- Contract: `lifeline_contracts/sources_hub.py`, `GET /v1/sources/hub?language=`.
