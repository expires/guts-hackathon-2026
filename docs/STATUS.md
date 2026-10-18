# STATUS

## Penny V3 build (night of 18 Oct), updated 09:00

Source of truth: `PENNY_V3_BUILD.md`, ADR 0072 (with "Decisions during the build"). Deadline: everything complete by 10:00.

### Installed on both phones (08:55, Demo build, talks to Railway)
- iOS: commit `a494ff2d` on `wip/direction-v2`. Tests on the installed tree: 379 unit tests and 18 UI tests passed (08:48).
- Server: commit `8516f6a1`, live on Railway. Backend: 2263 tests passed on the committed tree.
- Final verifier run: started 09:00 (report: `docs/verify/V7-final-v3.md`). Merge to main follows when it passes.

### Done (all of PENNY_V3_BUILD.md A to H, plus the what-if change)
| Item | Notes |
|---|---|
| Location bug | Town and region from the card for all 10 students |
| Reseed A1-A5 | 10 students rebuilt; statements 1 Jul to yesterday; banks per A4; September non-rent within 0.1% of target (Priya +8.6%); `docs/seed_sources.md` |
| Forecast B1-B3 | Engine and 3 routes; Money card, Where your money goes, Due before, One thing that helps, The maths, Detailed breakdown, All spending, Category; live states: Jordan, Callum, Hugo running short, other 7 on track |
| What-ifs | "Ask Penny 'what if...'"; forecast_what_if tool; checked live ("£60 concert on the 30th": stays on track, £141 to £137 a week) |
| B4 and F | Old move card, Test it, Why?, tiles, Guess my spend and data tags gone; Life game, Challenges, Same Decision, Collection behind one flag; Debug and Playground in Debug builds only; tests that no "mock"/"sample data" text shows |
| G | "Hi, <name>", floating tab bar, no duplicate amounts, no Monzo, student-facing sources, credits |
| C (onboarding) | All 11 screens; honesty line; profile with one period and a pie; forecast steps and card |
| D (Penny) | General questions answer (checked live: library question in 20 s); one bubble per answer; New chat; Past chats; data chips; links open The maths; lesson card context |
| E (Learn) | No locks; "Why this matters to you" on all 86 facts; progress segments; "Lessons X/48" on You |
| Quick Life | First in the picker; one tap per student; no "I'm ready"; QR deep link lands in the lobby (UI tests, warm and cold) |

### Decisions taken overnight (ADR 0072)
- Next money = the main income; smaller payments before it are expected income.
- Under 14 days to next money: the card shows a total until that date (Eilidh, Lena).
- Overdrawn with nothing left: the card shows the amount missing (Callum).
- Callum's first loan payment is late (26 Oct).
- Learn has no locks on the server either.
- Penny's time limit is 30 s on Railway, with keepalives during the answer (web search takes about 16 s).

### Known limits
- A real iPhone camera scan of the lobby QR is not tested (UI tests open the same link).
- Learn lesson text, "Why this matters" lines and Next Move fixed text are English in other languages where no translation exists (unit titles and app UI are translated).
- General Penny answers that need a web search take about 20 s.

### What to test first
1. You > Judge mode > New player; go through onboarding; on Try Penny ask "How long does the library stay open?".
2. Pick Callum Reid: running short, "You are £385 short before 23 October". New player again, pick Eilidh Fraser: "You can spend £930 until 26 October".
3. "See the maths": change the buffer; "See the detailed breakdown": the sums add up.
4. "Ask Penny 'what if...'": "Can I afford a £60 concert on the 30th?".
5. Play > Play with friends > Quick Life > tap a student; on the second phone scan the QR with the camera; the host can start without "I'm ready".
6. Play > Learn: every lesson opens; each number has "Why this matters to you".

## Direction V2 progress (23:32)

Direction: `DIRECTION_V2.md` (ADRs 0046-0061). Feature freeze 09:30, coding closes 12:00 on 18 Oct.

| Step | State |
|---|---|
| 1 Bugs 1-9, chat fixes | Built. Backend verified (V1 PASS, V2 fixes re-checked, V6 fixes in). iOS: V4 re-check running. |
| 2 Four tabs, compact, Penny tab | Built. V4 re-check running. |
| 3 Student onboarding, samples, judge mode | Built. V4 re-check running. |
| 4 Student moves, verified facts, habit score | Built. All 69 official amounts (55 facts + 14 sim tables) verified against official sources (URL + checked date). |
| 5 Play: lobby, Quiz, Same Decision, Quick Life, Circles | Built. V1 PASS. V6 re-check running (2 low findings fixed). |
| ADR 0060 instant screens, Penny tools | Built. Tab switch ~0.5 s; Penny first bubble 1.4-2.6 s. |
| 6 Life student paths, challenges | Built (paths, student challenges, old presets removed). |
| 7 README, DEMO.md, V5 rehearsal | Not started. DEMO.md waits for the user's script. |

- Railway still runs the 19:00 build; the phone has the 19:33 build. Deploy + install after V4 passes (Railway gets AUTH_RATE_LIMIT_PER_MINUTE=300, ADR 0055).
- About 420 files uncommitted; they become per-feature commits after the verifiers pass.
- Feature map with screenshots: docs/FEATURE_MAP.md and https://claude.ai/artifact/7AQVTwaKBUwS8UgYnT9agF.
## 18:45 update

- Product renamed to **Penny** ("Your money, played forward.", ADR 0040). Railway API redeployed ("Penny API", /v1/finance/home live, read limit 300/min).
- Git: BOSS commits on main, never pushes (ADR 0041). The iOS work is uncommitted until the build is green and V4 passes.
- Official brief (ADR 0043): trade-offs on every move (ADR 0042, contract done; W2 engine, W5 Penny and AI disclosure running), "24 hours" copy, named user Yaffy.
- Crashes: 10 simulator crashes (worker simulators, 18:31-18:36) from one bug in W9's mock room server (exclusivity conflict). No crash reports on the iPhone. W9 is fixing it.
- iOS build: red only in W7 Penny files (2 errors) and W9 MockRoomTransport (1). V4 fix pass: FAIL on j, k, l (sent to W6, helper).

## Phone install 19:33 ("install now", not V4-checked)

- App "Penny" (`com.akshat.lifeline`), Demo config, Railway. Checkpoint 2. Features: penny-rename, trade-offs, ask-penny, same-life, presentation-mode.
- Known open: "Play yourself" form test fails (W6). V4 has not run on this build.
- An old app "Lifeline" (`com.lifeline.app`, not ours) is also on the phone.

## Phone install (checkpoint 3)

- "Penny" (`com.akshat.lifeline`), Demo config, Railway backend deployed ~00:50. Build from a snapshot that passed 245 iOS tests; V4 passed steps 1-3. Includes: four tabs, Penny tab, new onboarding with language choice, 10 sample students, judge mode, Play with friends (4-digit lobby, Quiz, Same Decision, Quick Life), Circles, habit score on You, instant screens.
- Not in this build yet: most translated strings (wrapping in progress), the Store removal.

## Needs Akshat (do these when back; nothing waits on them)

- [ ] README Team table: 3 rows still say "TBC".
- [ ] Final demo script (DEMO.md waits for it).


- [ ] Bank tokens: on `merge/yaffy`, Monzo and Trading212 tokens are plain files under `CREDENTIALS_DIR`. BOSS moves them to encrypted Postgres during the merge (README "Security" stays unticked until then).

- [x] Facts: BOSS verifies every facts-table entry against official sources (URL and date stored per entry); only facts with no official source are flagged here.

- [ ] **URGENT: secrets in the public repo.** Branch `integration` (commit 31eaaa6) contains `services/api/data/private/aa298cec…/credentials.json` with Trading212 api_key/api_secret and Monzo access/refresh tokens, plus real Monzo history and a finance snapshot. Revoke the Trading212 key and the Monzo tokens now, purge the files from history (git filter-repo or BFG) and force-push. Our `.gitignore` now ignores `**/data/private/`, `**/data/cache/` and `**/credentials.json` (the old rule only matched the repo root); keep this on merge. Also check `services/api/tests/integration/test_live_data_flow.py` lines 26-27 (gitleaks hit).
- [ ] **Named user Yaffy (ADR 0043):** send his age, his situation (student or working), his city, and his consent to show his real Monzo and Trading212 data on stage. Until then README shows placeholders and the demo uses Priya.
- [x] Yaffy merge: permission given. BOSS merges `merge/yaffy` into main after milestone 1 is green (keep: Monzo bank routes, TrueLayer off, Insights behind Spending, no data/private, tokens encrypted in Postgres). No push.
- [ ] Phone installs: the phone is away. All UI work is checked on the simulator. Run `make ios-device` when the phone is back (Mock config) or the Demo config once Railway is up.
- [ ] TrueLayer: disabled by your rule (sandbox has test banks only). No action unless you change that.
- [ ] Monzo / Trading212: Yaffy's area. Untouched until you merge his branch. The onboarding buttons call `/v1/bank` and `/v1/connections` and show "unavailable" until then.
- [ ] Sign in with Apple: needs the "Sign in with Apple" capability on team 472PHZCF99 in the Apple Developer portal (bundle `com.akshat.lifeline`). A free personal team cannot use it. Until then the app falls back to the demo sign-in.


Last update: 2026-10-17 17:15, **Tier 0 accepted**. Tier 1 backend green; iOS fix pass and V4 in progress. Railway live.

## Phone checkpoints

| # | Time | App | Source | Features |
|---|---|---|---|---|
| 1 | 18:08 | Lifeline Dev (`com.akshat.lifeline.dev`, Railway) | last green snapshot 38faeaa | Design rebuild, UI fix pass, Next Move, Test it, Money home, Life, Guess my spend |

- From 18:50 (ADR 0039): one app, **Lifeline** (`com.akshat.lifeline`, Railway). Installs only at milestones after V4: 1 Onboarding + Money empty state, 2 Ask Penny, 3 Same Life PvP, 4 Final. Or on "install now". Checkpoint 1's "Lifeline Dev" app can be deleted.
- Railway runs in live mode: Money and Next Move show "Connect your money first" until onboarding (W6) lands.

## Away plan progress (updated 18:40)

| # | Item | State |
|---|---|---|
| 1 | UI fix pass + V4 (simulator) | W6 and W7 green on the simulator. **V4 running** (screenshots of every screen, your fix list) |
| 2 | Railway | **Done.** https://api-production-15615.up.railway.app; 16 live, 6 unavailable, 0 mock (18 live locally with Guardian and MPC dates; Railway redeploy pending); Demo iOS config; GUARDIAN_API_KEY set there (stdin) |
| — | No mock in Live (ADR 0027) | **Done** (data, sim, API, iOS "Unavailable" state) |
| 3 | Onboarding + accounts | Backend **done** (me, delete revokes all tokens, reset, logout, Apple sign-in, statement upload, manual entry, logged payments, encrypted at rest). iOS: W6 in progress |
| 4 | News + Ask Penny | Backend **done** (Guardian + MPC live; tools; Penny with verifier; streaming; threads; chat rate limit). Railway timings: reaction 0.32 s warm (3.35 s cold), first bubble 7.7-12.4 s, all verified. iOS: W7 in progress |
| 5 | Same Life PvP | Backend **done** (rooms, Redis pub/sub, server-owned seed and numbers, reconnect 10 min, 4-client test). iOS: W9 in progress |
| 6 | On-device connectors | Backend **done** (reverse postcode live, health effect, log payment). iOS after features 3-5 |
| 7 | Presentation mode | Client only. After step 6 |
| — | Challenges + demo store | Backend **done** (challenge scoring per life; demo purchases labelled "Demo payment") |
| — | Widget | Cut. StoreKit only if all else is green |

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
| Tier 1 | Backend gate green (V1, V2, V3, V5, V6 PASS; 860 tests). iOS: ADR 0026 design rebuild steps 1-5 built; user's UI fix pass in progress (W6: own tab bar and sheets, no Liquid Glass, compact Money home; W7: Test it and Rewind numbers from data). V4 after the fix pass. Build installed on the user's iPhone (Mock config, recorded engine data) |
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

## Demo persona and Next Move (current)

- Persona (devices demo-presenter-01..05): Priya Shah, 34, Nurse, Leeds LS6 1AN; £180,000 mortgage, 25 years, 2-year fix 4.42% (BoE IUMBV34 Apr 2025) ending 2027-03-31; Netflix £12.99 + PureGym £24.99 (£37.98 a month).
- Engine decision on real BoE rates: **"Take a tracker"**, £3,097 a year vs doing nothing, "In 8 of 10 similar cases this was the best choice". Evidence 1 states the 5-year vs 2-year gap at today's rates (£189 a year) and her stressed payment (69% of take-home). ADR 0020 Amendment 2 records why the engine does not pick "Fix for 5 years": today's tracker rate (4.23%) is below both fixes, and the 2007 matched period makes a 5-year fix the riskiest option by regret.
- The phone's Mock build serves recorded real engine responses (`make ios-record-mock`), not contract examples.

## Secret scan

| Milestone | Tool | Result |
|---|---|---|
| Step A | gitleaks (`make secrets-scan`) | No leaks. `.env` ignored |
| Tier 1 (re-run) | gitleaks (`make secrets-scan`) | No leaks. Allowlist covers enum assignments; fake test keys built at run time |
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
