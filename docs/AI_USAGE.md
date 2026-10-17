# AI usage log

How Claude Code built Lifeline. This log supports the event's AI-level declaration. The user sets the final AI level.

AI use inside the product (LLM wording for events and lessons, with a number verifier) is described in `docs/RESPONSIBLE_AI.md`. This file covers AI use in development.

## Roles

| Role | What it is | What it may write |
|---|---|---|
| User | Human. Wrote `BUILD_SPEC.md`. Commits and pushes by hand. Sets the AI level. | Everything |
| BOSS | One Claude Code session (main agent). Plans, creates shared files, launches workers and verifiers, decides gates. | Shared files: contract, `CLAUDE.md`, `Makefile`, `docker-compose.yml`, `.env.example`, `pyproject.toml`, `project.yml`, `docs/adr/`, `docs/STATUS.md` |
| Workers W1 to W8 | Claude Code subagents, one per area. Run in parallel on one working tree. | Only their owned paths (table in `CLAUDE.md`) |
| Verifiers V1 to V6 | Claude Code subagents. Read code, run checks, write a report. | Only `docs/verify/V*.md` |

Agent definitions live in `.claude/agents/` (role, owned paths, done criteria).

## Rules every agent follows

- No git writes. Agents may run `git status` and `git diff` only. The user commits.
- Edit only owned paths. A change to a shared file goes to BOSS as a request in the agent's final report.
- Never read, print or copy `.env` values. A missing key gives labelled mock data.
- Never ask the user questions. Decide, report the decision, and BOSS records it as an ADR.
- Keep the tree runnable. Run your own tests before reporting done.

## Log

### Step A: BOSS setup (sequential)

1. Renamed the spec file to `BUILD_SPEC.md` and imported the team repo history without a checkout (ADR 0003).
2. Wrote `CLAUDE.md` with hard rules and the ownership table.
3. Wrote the shared Pydantic wire models in `services/api/lifeline_contracts/`.
4. Generated `contracts/openapi.yaml` from those models with `contracts/build_openapi.py`. Every endpoint has examples that are model instances, so each example validates against its schema (ADR 0002).
5. Wrote the canonical `Observation` schema and the annual `MacroTable` interface for the pure core (ADR 0005).
6. Wrote `docker-compose.yml` (api, worker, postgres, redis), `Makefile`, `.env.example`, `.gitleaks.toml`, an initial Dockerfile and the contract test suite.
7. Wrote 14 agent definitions in `.claude/agents/`: W1 to W8 and V1 to V6.
8. Recorded decisions as ADRs 0001 to 0006 and the spec-versus-team-plan differences in `docs/STATUS.md`.

### Step B: workers in parallel

BOSS launched the eight workers at the same time. Each worker read `CLAUDE.md`, `BUILD_SPEC.md`, the ADRs and the contract, then built only its owned paths.

| Worker | Area | Tier 0 scope |
|---|---|---|
| W1 data-adapters | `lifeline_data` | BoE, ONS, Nomis, Land Registry, postcodes adapters; cache; mock fallback; recorded fixtures |
| W2 engine | `lifeline_engine`, `lifeline_eval` | Population, twins, period matching, finance maths; tests first with hand-calculated cases |
| W3 sim | `lifeline_sim` | Age, events, stats, Index; deterministic seeds |
| W4 api | `lifeline_api` | Routes per contract, auth, error format, lives store |
| W5 explain | `lifeline_explain` | LLM client, number verifier, templates |
| W6 ios-core | `apps/ios/Lifeline` | Design system, character select, Life screen, AGE, event sheet |
| W7 ios-social-store | iOS Rooms, Decision, Bank, Store | Tier 1 and Tier 2 screens |
| W8 infra-docs | Dockerfile, CI, docs, seed | Image, CI workflow, README, architecture, demo script, seed loader, attributions |

Workers do not wait for each other. They code against `lifeline_contracts` and the generated contract, so a worker can build and test before the others finish.

### Step C: verifier gates

A worker milestone counts only when its verifier passes.

| Verifier | Checks |
|---|---|
| V1 contract | Every endpoint matches `contracts/openapi.yaml`; one error format |
| V2 engine | Hand-calculated cases, property tests, determinism, Index fairness |
| V3 resilience | Kill or slow each source; the API still answers with `cached` or `mock` |
| V4 ios | `xcodebuild` build and tests on the simulator; screenshots; accessibility labels |
| V5 demo | Runs `docs/DEMO.md` end to end on the compose stack and simulator |
| V6 security | Secret scan, input validation, rate limits, OAuth state and PKCE |

Tier order: Tier 0 must be green (`make up && make test`, V1 to V5) before Tier 1 starts. Tier 1 must be green before Tier 2.

### ADR process

1. A worker meets an open question (for example a shared-file change or a library choice).
2. The worker decides, continues, and lists the decision in its final report.
3. BOSS reviews the report and writes `docs/adr/NNNN-title.md` (context, decision, consequences).
4. BOSS applies any requested shared-file change, regenerates the contract if needed (`make contract`), and tells affected workers.

### Entries

| When | Who | What |
|---|---|---|
| 2026-10-17 | BOSS | Step A complete. ADRs 0001 to 0006. |
| 2026-10-17 | W8 | Tier 0 infra and docs: two-stage non-root Dockerfile, `.dockerignore`, CI workflow (ruff, mypy, pytest, contract drift, compose build, gitleaks, iOS tests), README product section, architecture, demo script, seed loader, attributions JSON. `docker compose build` passes. |
| 2026-10-17 | W1 to W7 | Tier 0 workers ran in parallel. W1: BoE, ONS, Nomis, Land Registry and postcodes adapters, Redis and Postgres fallback, circuit breaker (ADR 0010). W2: mortgage maths, population, twins, period matching (ADR 0008). W3: replay-based sim, YAML event templates, Index (ADR 0012). W4: Tier 0 routes, demo auth, rate and body limits, 501 for Tier 1 and 2 routes. W5: explain layer; BOSS switched the model to Opus at the user's request (ADR 0007). W6: iOS character select, Life screen, AGE, event sheet (ADR 0009). |
| 2026-10-17 | V1, BOSS | V1 contract run 1 FAIL: `listCharacters` auth and an undeclared 422 did not match the contract, and the suite missed `signInDemo`, 413, path-param and 501 cases. BOSS fixed the contract and added the tests. Run 2 PASS (31 contract tests, 97 probe checks). |
| 2026-10-17 | V2, W3, BOSS | V2 engine run 1 FAIL. F1: wealthy retirees missed payments, so an all-default life could score Index 0 (retirement money bug). W3 fixed the payment logic. F2: the spec's absolute penalties conflicted with the fairness test ("same choices as autopilot gives 100"). BOSS decided to measure penalties relative to the autopilot twin (ADR 0013). Run 2 PASS: 180 all-default lifetimes score exactly 100 when settled. |
| 2026-10-17 | V3 | V3 resilience PASS: 88 scratch tests (timeouts, 500, 429, garbage and absurd payloads, breaker timing) plus stack checks with Redis, Postgres and network down. Six non-blocking findings queued to W1 and W4, for example 500 instead of 503 on `/v1/characters` with Postgres down, and postcodes cache TTL equal to the stale-keep window. |
| 2026-10-17 | V5, W1, W3, W8 | V5 demo run 1 FAIL. Annual averages hid the 2008 crash (London house prices -1.1%), the banker's net worth rose, the seed and DEMO.md used different device ids, and DEMO.md had no fallbacks for unbuilt scenes. Fixes: W1 switched fast series to year-end values (ADR 0014); W3 added rate-cut and house-price events and tied the bonus to markets; W8 unified the device id (`demo-presenter-01`), skipped 501 steps in the seed, and added "check before presenting" and tier fallbacks to DEMO.md. Run 2 PASS: the banker's net worth falls from £317,645 to £255,490 in 2008. |
| 2026-10-17 | User, BOSS, W6 | The user asked to own the iOS UI. BOSS wrote ADR 0011: pure Views and DesignSystem owned by the user; ViewModels, glue and `LifelineClient` (live or mock) owned by agents; requests through `docs/UI_REQUESTS.md`; a `Playground` scheme with a fixture gallery. W6 did the restructure in one run, then added `-demoDeviceID` and a Debug menu. |
| 2026-10-17 | BOSS | Simulator issue: after the iOS 27.1 runtime download, the 27.0 runtime files went missing and devices failed to boot. Restarting CoreSimulatorService fixed both runtimes. Default simulator: iPhone 18 Pro Max. CLI builds use a separate DerivedData path (ADR 0006). CI picks the first available iPhone simulator at runtime. |

Add one row per milestone.

## Human review

- The user wrote the spec, set the rules, and chose the stack.
- The user commits every change by hand after reading `git diff`.
- Generated code passes ruff, mypy (strict on the pure core), pytest and the verifier reports before a tier is accepted.

## AI-usage statement (draft)

> We built Lifeline with Claude Code as the main engineering tool. A human wrote the product spec and the rules. One Claude Code session (the "BOSS") turned the spec into a shared contract, an ownership table and decision records. It then ran eight worker agents in parallel, each restricted to its own folders, and six verifier agents that had to pass before each milestone was accepted. Agents could not commit; a human read every diff and committed by hand. Inside the app, an LLM writes only event and lesson wording. The engine computes every number, and a verifier rejects any LLM text whose numbers do not match the engine, falling back to fixed templates. No AI output decides a game outcome or the Real-life Decision.
