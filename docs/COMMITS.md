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
