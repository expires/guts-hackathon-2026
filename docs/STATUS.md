# STATUS

Last update: 2026-10-17 14:52, **Tier 0 accepted (all gates green)**. Tier 1 starting.

## Source of truth

`BUILD_SPEC.md` is the source of truth. `docs/PLAN.md` holds the teammate's notes. Where they differ, the build follows `BUILD_SPEC.md`. The table below lists each difference.

## BUILD_SPEC.md vs docs/PLAN.md

| Topic | docs/PLAN.md (teammate notes) | BUILD_SPEC.md (followed) |
|---|---|---|
| Client | Web UI (dashboard, backtest explorer, friends) | Native iOS 26 app, SwiftUI, Liquid Glass |
| Product shape | Finance dashboard plus backtest of own habits | BitLife-style life game, birth to death, plus one Real-life Decision |
| Data sources | User's own Monzo and Trading212 accounts | Public UK data (BoE, ONS, Nomis, Land Registry, postcodes.io and 13 more) plus Open Banking sandbox (TrueLayer or Yapily) |
| Response format | Envelope `{data, error, meta}` on every response | Errors only: `{"error": {"code", "message", "source"}}`. Success bodies are the resource itself |
| Contract | FastAPI-generated spec exported to `docs/openapi.json` | Contract first: `contracts/openapi.yaml` with examples; Swift client generated from it |
| Repo layout | `src/playyourself/`, `data/mock/` | `services/api/lifeline_*`, `apps/ios/` |
| Mock switch | `MONZO_MODE` / `T212_MODE` = mock or live | Missing key = labelled mock data with `status: "mock"` |
| Privacy model | Raw data stays on device; only `habit_vector` leaves | Bank OAuth runs on the backend; tokens never reach the device; app holds no keys |
| Comparison score | Time-weighted return rebased to 100 | INDEX vs autopilot twin (formula in spec section 0, `docs/index.md`) |
| Social | Friends leaderboard, opt-in allocation pie | "Same Life" live PvP rooms, 2 to 8 players, room code or QR |
| Money type | Integer pence | Not specified. Engine uses float GBP, rounded at display (ADR to follow) |
| Run command | `make run` | `make up && make test` |
| Git | Each step merged to `main` | No agent runs git writes. The user commits by hand |
| Money dashboard | Dashboard of Monzo and Trading212 data (step 6) | Money tab (ADR 0016) on `/v1/finance/*`: labelled fixtures in Tier 1, TrueLayer sandbox in Tier 2. No Trading212 |
| Habit vector | 7 habit factors, the only object that leaves the device | Not in spec. Not built |

Both documents agree on: three layers, pure decision layer, AI explains but never decides, number verification with template fallback, timeouts, retries, cache and stale data, no secrets in code.

## Tier progress

| Tier | State |
|---|---|
| Step A (setup) | Done |
| Tier 0 | **Accepted.** `make up` healthy; `make test` 385 passed; `make lint` clean; contract on stack 49 passed; iOS build + 51 tests green; V1-V5 PASS; secret scan clean |
| Tier 1 | In progress (workers W1-W7 launched 14:55). Order: Next Move first (ADR 0018), then Money tab (ADR 0016), spend prediction (ADR 0017), then the original Tier 1 list |
| Tier 2 | Not started |

## Tier 0 verifier results

| Verifier | Verdict | Report |
|---|---|---|
| V1 contract | PASS (2nd run; 1st run found 3 contract gaps, fixed by BOSS) | `docs/verify/V1.md` |
| V2 engine | PASS (2nd run; 1st run found retirement money bug and INDEX fairness conflict: W3 fix, ADR 0013) | `docs/verify/V2.md` |
| V3 resilience | PASS (6 non-blocking findings, all fixed) | `docs/verify/V3.md` |
| V4 iOS | PASS (7 non-blocking findings: 4 logged as UIR-1..4 for the UI owner) | `docs/verify/V4.md` |
| V5 demo | PASS (2nd run; 1st run: 2008 crash invisible: ADR 0014 year-end data, W3 crash dynamics, W8 docs) | `docs/verify/V5.md` |
| V6 security | Runs at Tier 1 and Tier 2 milestones |  |

## What works now

- Backend (`make up`, http://localhost:8000): health, sources, demo sign-in, characters, lives (create, get, age, choices, summary). Error format everywhere, rate limit, 64 KB body limit, 503 when the store is down.
- Data: boe, ons, nomis, landregistry, postcodes are **live**. Year-end values for fast series (ADR 0014). Regional rents from ONS IPHRP (to Jan 2024).
- Engine: mortgage maths, IPF population, twins, period matching, minimal decision and backtest.
- Sim: 44 templates in 11 areas, INDEX (relative penalties, ADR 0013), deterministic replay, crash dynamics, presets.
- iOS: View/ViewModel split (ADR 0011), LiveClient and MockClient, Playground gallery (63 states), character select, Life, AGE, event sheet, lesson. 32 screenshots in `docs/screens/`.
- Contract: 35 paths. Tier 1 and Tier 2 operations answer 501 `not_implemented` (declared) until built.

## Secret scan

| Milestone | Tool | Result |
|---|---|---|
| Step A | gitleaks (`make secrets-scan`) | No leaks. `.env` ignored |
| Tier 0 | gitleaks (`make secrets-scan`) | No leaks after allowlisting one false positive (`key == MacroKey...` in engine code, line-scoped regex in `.gitleaks.toml`). `.env` ignored |

## Mocked and why

| Source or feature | Status | Why |
|---|---|---|
| frankfurter, coingecko, yahoo, fred, octopus, carbonintensity, openmeteo, police, environmentagency | mock | Live adapters are Tier 1 (W1) |
| companieshouse, epc, statxplore, openbanking | mock | Keys being added to `.env` by the user; adapters are Tier 1/2 |
| adzuna, dvla, dvsamot | mock | No key (DVLA registrations closed; DVSA approval slow) |
| Stock returns (2008 crash event) | mock | Yahoo adapter is Tier 1 |
| Rents 2025-2026 | mock | ONS stopped IPHRP in Feb 2024; PIPR adapter is Tier 1 |
| All Money tab data | mock (fixtures) | Bank OAuth is Tier 2 (ADR 0016) |

## Known issues

- Rate limit is per client IP. Parallel local agents share one IP. Stack contract tests now honour `Retry-After`.
- The iOS 27.0 and 27.1 simulator runtimes lose their mounts sometimes; fix: `xcrun simctl shutdown all; killall -9 com.apple.CoreSimulator.CoreSimulatorService` (ADR 0006).
- The app bundle includes `openapi.yaml` and the generator config (no secrets; needed by the build plugin).
- Index has no upper cap; random play can show values over 1,000 (display is a UI decision).
- Open UI requests for the UI owner: UIR-1..4 (`docs/UI_REQUESTS.md`).
- Railway deploy paused at the user's request.
