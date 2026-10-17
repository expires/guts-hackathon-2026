# ADR 0043: Official GUTS brief alignment

Date: 2026-10-17. Status: accepted.

## Decision

- Name and tagline: Penny, "Your money, played forward." (ADR 0040). The event is 24 hours, not 30. All copy says 24.
- Named user: Yaffy. He uses Monzo and a Trading212 ISA and rents. Decision: "What is my next money move?". The user story leads README and DEMO.
- The demo runs on Yaffy's real connected data after the Yaffy merge. There is no planned headline: the demo follows the engine's top move.
- Priya Shah stays as the Mock and test persona (recorded data, unit tests). She is not the named user.
- Trade-offs on every move (ADR 0042).
- Version control: BOSS commits per milestone (ADR 0041). README explains the history: one foundation commit, then one commit per milestone, decisions in `docs/adr/`.
- AI disclosure: You tab "How Penny uses AI", README and RESPONSIBLE_AI carry the same content.
- README becomes the submission checklist, in the brief's order.
- V4 adds accessibility checks: Dynamic Type up to XXL, VoiceOver labels, contrast, tap targets. Every screen links back to the Next Move.
- Priorities: 1 onboarding + Money empty state + rename + trade-off on the card; 2 Ask Penny; 3 Same Life PvP; 4 presentation mode, then connectors if time. Then the README pass and a V5 rehearsal on Railway.

## Open (Needs Akshat)

- Yaffy's age, situation and consent to show his data on stage. Until then README shows placeholders and the demo uses Priya.

## Amendment (W5 report)

- The disclosure states only what the code does. Lessons are fixed text (`lifeline_sim/concepts.py`); AI does not write them. AI rewords events, outcomes, the Next Move headline and evidence lines, and Ask Penny answers.
- Source of the text: `services/api/lifeline_explain/ai_disclosure.json`. `make ai-disclosure` copies it into the iOS app; `make lint` fails if the copies differ. README and RESPONSIBLE_AI carry the same points.
- Ask Penny states the trade-off ("What you give up: ...") from the engine text only; its numbers are checked facts (`tf_<move_id>_<key>`). Prompt `penny-v4`.
