# Suggested commits

The user commits by hand. Each entry is one green milestone. Conventional Commits format.

## 1. Step A: BOSS setup

```
chore: scaffold Lifeline repo, contract and agent rules

- Add BUILD_SPEC.md, CLAUDE.md (agent rules and path ownership)
- Merge .gitignore with spec section 5 rules; add .env.example and .gitleaks.toml
- Add lifeline_contracts (canonical Observation, MacroTable, domain and API models)
- Generate contracts/openapi.yaml with examples from the shared models
- Add contract test suite, Makefile, docker-compose, initial Dockerfile
- Add XcodeGen project with swift-openapi-generator and skeleton iOS app
- Add .claude/agents definitions for workers W1-W8 and verifiers V1-V6
- Add ADRs 0001-0006 and docs/STATUS.md

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01P5CCRiMB1AiGA5fCFcV2NP
```

## 2. Tier 0: core game, data, API and iOS (all gates green)

```
feat: Tier 0 Lifeline core (data, engine, sim, API, iOS) with green gates

- data: BoE, ONS, Nomis, Land Registry, postcodes.io adapters with retries,
  circuit breaker, Redis cache, Postgres last-good, labelled mock fallback;
  year-end values for fast series (ADR 0014); worker refresh
- engine: mortgage maths, IPF synthetic population, Mahalanobis twins,
  period matching, minimal decision and walk-forward backtest
- sim: deterministic life replay, 44 data-driven events, stats, INDEX with
  penalties relative to the autopilot twin (ADR 0013), crash dynamics
- api: FastAPI per contract, demo JWT, rate limit, body limit, one error
  format, Postgres store with 503 fallback, 501 stubs for later tiers
- contract: Money tab, spend prediction and Next Move operations
  (ADR 0016-0018); 35 paths with examples
- ios: View/ViewModel split (ADR 0011), Live/Mock client, Playground
  gallery, character select, Life, AGE, event sheet; device signing via
  git-ignored Local.xcconfig (ADR 0015)
- infra/docs: Dockerfile, CI, README, architecture, DEMO.md, seed data,
  verifier reports V1-V5, ADRs 0001-0018, STATUS

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01P5CCRiMB1AiGA5fCFcV2NP
```

## 3. Tier 1 backend: Next Move, Money tab, spend prediction (V1, V2, V3, V5, V6 green; iOS V4 pending)

```
feat: Next Move engine, Test it, Money tab API and spend prediction

- next-move: one answer to "What is my next money move?" with 3 evidence
  points, live/cached/mock sources, regret-based option choice, stress
  periods and honest confidence (ADR 0018, 0020, 0023)
- test it: play_scenario replays the user's profile through the stress
  period for each option, with costs (ADR 0018, 0024)
- money: /v1/finance/* from labelled fixture personas: overview,
  spending, subscriptions, bills, budgets, goals, profile (ADR 0016)
- prediction: ridge model on daily spend with £ reasons, Guess my spend,
  walk-forward backtest vs weekday baseline (ADR 0017)
- data: 13 live sources incl. BoE SVR and tracker series, gov.uk bank
  holidays, Open-Meteo; key-safe logging (ADR 0021)
- sim: 152 events, 50 concepts, 31 actions, rewind, ribbons (ADR 0024)
- explain: Opus rewording with number verifier and template fallback
  (ADR 0019)
- api: all Tier 1 endpoints, plan, store fallbacks, calendar validation
- docs: DEMO.md opens with the Next Move story; README accuracy section;
  verifier reports V1-V3, V5, V6 (Tier 1)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01P5CCRiMB1AiGA5fCFcV2NP
```

## 4. Live data mode, Railway deploy, design rebuild

```
feat: live data mode, Railway deploy, native design rebuild

- data: DATA_MODE=live serves real data only; sources without real data
  are "unavailable"; Adzuna, DVLA, DVSA, TrueLayer disabled (ADR 0027);
  Companies House, Stat-Xplore and EPC live (16 live sources); key aliases
- deploy: Railway project in the personal workspace, api + worker from one
  image (ROLE), Postgres, Redis, health check, Demo iOS config (ADR 0028,
  docs/DEPLOY.md)
- engine: affordability-weighted regret; demo persona Priya Shah; card
  states today's 5y vs 2y gap from live BoE rates (ADR 0020 amendment 2)
- sim: no event repeats within 3 years (except mortgage deal end)
- ios: native rebuild of the design handoff (tokens, fonts, icons, own tab
  bar and sheets, no Liquid Glass), Mock build serves recorded engine
  output (ADR 0026)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01P5CCRiMB1AiGA5fCFcV2NP
```


## 5. Tier 2 backend and Penny rename (sectioned commits, ADR 0041)

```
chore(repo): BOSS commit rule, Penny rename, tooling

- CLAUDE.md: BOSS may commit on main, never push (ADR 0041)
- product renamed to Penny, tagline "Your money, played forward." (ADR 0040)
- Makefile, tools and agent definitions for parallel iOS workers (ADR 0037)
- .env.example: Guardian, token encryption and rate limit settings

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01P5CCRiMB1AiGA5fCFcV2NP
```

```
feat(contracts): accounts, onboarding, Ask Penny, rooms, finance home

- Me (with bank_name), statement import, manual input, connectors
- chat models, SSE stream events, news and rate decisions
- room player ready/connected state and WebSocket messages
- GET /v1/finance/home with an explicit empty state
- regenerated contracts/openapi.yaml

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01P5CCRiMB1AiGA5fCFcV2NP
```

```
feat(data): news, rate decision dates, statements, encryption

- Guardian headlines (headline and link only) and BoE MPC dates
- Monzo and Revolut statement parser
- Fernet encryption for tokens and bank data in Postgres
- reverse postcode lookup; live mode never serves mock values

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01P5CCRiMB1AiGA5fCFcV2NP
```

```
feat(engine,sim): Penny tools, Next Move sources, health effect

- engine tools: cash flow projection, gov.uk 2026/27 facts table,
  wrappers that emit ChatFacts
- decision source count and context lines on the Next Move (ADR 0032)
- sim: projection, health effect, play_scenario, event choices
- no event repeats within 3 years

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01P5CCRiMB1AiGA5fCFcV2NP
```

```
feat(explain): Ask Penny with tools, verifier and streaming

- Anthropic tool-use loop, max 5 tools, template fallback
- unit-aware number verifier, number words, fenced untrusted text
- prompt penny-v3 (product name Penny)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01P5CCRiMB1AiGA5fCFcV2NP
```

```
feat(api): accounts, onboarding, chat stream, rooms, finance home

- sign in (demo, Apple), account delete with token revocation
- statement upload and manual input; encrypted snapshots in Postgres
- POST /v1/chat/stream (reaction first, warm-up at startup)
- Same Life PvP rooms over WebSocket; challenges with progress
- GET /v1/finance/home; read 300/min, chat 6/min, Retry-After on 429
- Railway health check config

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01P5CCRiMB1AiGA5fCFcV2NP
```

```
docs: ADRs 0029-0041, status, verify reports, screenshots

- decisions for news, Ask Penny, PvP, connectors, phone milestones,
  Penny rename and BOSS commits
- V2, V3, V4, V6 reports and fix-pass screenshots

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01P5CCRiMB1AiGA5fCFcV2NP
```


## 6. Official brief alignment: trade-offs, AI disclosure

```
feat: trade-offs on every Next Move, AI disclosure, room life sharing

- contract: Move.trade_off, gain_kind, cover_months, spread_investments
  (ADR 0042); contract test requires a trade-off on every move
- engine: one engine-defined trade-off per move kind, months of cover
  for the emergency fund, spread_investments scoring (inactive until
  holdings data lands)
- explain: Ask Penny states the trade-off from engine text only, numbers
  verified as facts; prompt penny-v4; "How Penny uses AI" text
- api: room members can read lives started in their room; others 404
- docs: brief alignment (ADR 0043), room rules (ADR 0044), 24 hours

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01P5CCRiMB1AiGA5fCFcV2NP
```

## 7. README submission checklist

```
docs: README as the GUTS submission checklist

- sections in the brief's order: user story (Yaffy, details pending),
  one decision with trade-offs, architecture, three layers, live source
  table (24 sources, 18 live), contract, how to run, tests, graceful
  failure, security, AI disclosure, ADR index, checklist
- unticked until true: named user details, Yaffy's real data (merge),
  bank tokens encrypted in Postgres
- DEMO.md opens with the same user story; architecture labels fixed

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01P5CCRiMB1AiGA5fCFcV2NP
```

## Milestone: Penny V3 build (18 Oct, 05:00 to 09:05), verified by V7

Committed on `wip/direction-v2` as small commits by feature (fdf5ca7 to 3625a48f), then fast-forwarded to `main` after the V7 final verifier passed (docs/verify/V7-final-v3.md). Suggested summary message:

```
feat: Penny V3, reseeded students and the forecast Next Move

- 10 sample students rebuilt with sources (PENNY_V3_BUILD.md A), town from the card
- forecast engine, The maths, detailed breakdown, all spending, category (B)
- what-ifs through Penny; Try Penny general answers; one bubble per answer (C5, D)
- onboarding C1-C9; Learn without locks; Quick Life without "I'm ready"
- cut behind one flag; floating tab bar; no mock or sample data tags (B4, F, G)
Checks: make up && make test (2250 passed), make test-stack, make lint, 379 iOS unit
and 18 UI tests, V7 9 of 9 PASS, secret scan clean.
```

Final checks after the merge (09:15 to 09:45): V1, V2, V3, V4 PASS on the final build; V5 every demo step works, FAIL on the 3 s first-bubble budget for tool answers (known limit, ADR 0072). Follow-up commit: `fix(engine): truthful headline when overdrawn, no run-out after next money`.
