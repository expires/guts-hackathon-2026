# ADR 0035: Tier 2 backend runs in parallel with the Tier 1 iOS gate

- Status: accepted
- Date: 2026-10-17
- Requested by: the user (overrides "never start a tier until the previous tier is green" for backend only)

## Decision
- Backend Tier 2 work starts now, in parallel with V4 (the Tier 1 iOS gate), because it touches no iOS views:
  - W1: Guardian news, BoE MPC dates (ADR 0030), statement parsers (Monzo and Revolut CSV first, then PDF).
  - W2: `cash_flow_projection`, the facts table, tool wrappers, decision sources (ADR 0032, 0033).
  - W5: Ask Penny service, prompt and golden tests (ADR 0031, 0034).
  - W4, in this order: accounts and onboarding routes (ADR 0029) → PvP rooms and WebSocket → `/v1/chat` wiring.
- iOS stays sequential: V4 fixes → onboarding and accounts → Ask Penny UI → PvP UI → connectors → presentation mode.
- **Each backend part must pass its verifier before iOS uses it:**
  - V1 for the contract.
  - V2 for the engine tools.
  - V3 for resilience: Guardian down, LLM down.
  - V6 for prompt injection and rate limits.
- Tier 0 and Tier 1 stability come first. A Tier 2 change that breaks the Tier 0 or Tier 1 suites is reverted by its owner before anything else.
