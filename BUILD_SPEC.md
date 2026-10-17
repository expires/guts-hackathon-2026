# BUILD_SPEC.md — Lifeline (working name)

You are the BOSS agent for a 30-hour solo hackathon build. Build the complete product below, end to end, with maximum parallelism and strict verification. Work autonomously. Do not ask questions unless a step is impossible without user input. If a decision is open, choose, record it in `docs/adr/`, and continue.

---

## 0. Product

**Working name:** "Lifeline". Keep the name in one constant so it can change.

A BitLife-style iOS game about money. The player lives a full financial life, birth to death, on REAL UK data. Purpose: financial literacy for anyone, through play.

**Hackathon brief (BlackRock / Aladdin):** "One app. Every source. One clear decision." Combine independent data sources into a clear, personalised decision. Go beyond a dashboard.

**Pitch:** "Many sources. One answer: your next money move. Play it before you live it." (Earlier line: "Aladdin stress tests portfolios. We stress test a life.")

### The one question (TOP PRIORITY, ADR 0018)

**The product answers ONE question: "What is my next money move?"** Everything else serves this.

**Pitch:** "Many sources. One answer: your next money move. Play it before you live it."

1. **Next Move engine** (W2, engine code, not LLM): candidate moves from the user's finance data + live sources: fix or remortgage, move savings to a better rate, cancel or switch subscriptions, switch energy deal, pay off expensive debt, build emergency fund, cut a budget category. Score each move in £ per year and risk (worst case), using twins and similar past periods. Return ONE top move: action, £ impact, confidence, 3 evidence points, sources with live/cached/mock status. Plus up to 2 runner-ups. Endpoint: `GET /v1/next-move`. Backtest where possible.
2. **"Test it"** (W3 + W4): from the Next Move card, create a Life simulation of the user's real profile and play each option through the most relevant past period (e.g. 2021-2023 for mortgages). Return side-by-side outcomes. Endpoint: `POST /v1/next-move/test`.
3. **iOS** (W6 + W7): the Next Move card is the first element on the Money tab. Buttons: "Test it" (opens the Life comparison), "Why?" (lesson + evidence), "Do this" (adds to plan, `POST /v1/plan`). Other Money tab widgets link back to it.
4. **Demo** (W8): DEMO.md opens with this story: Money tab, "Your deal ends in 165 days", Test it (2022 replay, both options), "Fix for 5 years, 7 in 10 twins did better", Do this.

### Core loop (self-paced, NO timers anywhere)

1. Pick a life and a start year. **DEFAULT first life = "Play yourself"** (manual entry or bank connection). Other options: Random (from the synthetic UK population) and God Mode (choose job, income, town, wealth: student, nurse, plumber, banker, pensioner, etc.).
2. Tap **AGE** → one year passes. Real-data events pop up as choice sheets.
3. Act through action menus in the Life tab: **Job, Assets, Relationships, Activities, Money** (see App tabs below).
4. Stats change: **Happiness, Health, Smarts, Money**, plus **INDEX**.
5. Important results open a full-screen **Lesson** (short chart, 2 sentences, 1-tap quiz) and unlock a **Concept** (collection of 40+).
6. **Rewind:** go back to any past choice and play the other path. Free once per life; unlimited with the paid pass.
7. Death → **Life Summary**: ribbons, final Index, net worth, key moments.
8. "Play yourself" reaching the present → **Real-life Decision** screen: ONE clear recommended action for the user's real situation, with evidence. Example: "Fix for 5 years. 7 in 10 twins in similar past periods did better."

### App tabs and the Money tab (spec change, ADR 0016)

**Tabs, in this order:** **Money** (home, default tab), **Life** (the game), **Play** (Same Life rooms, challenges, ribbons, concepts), **You** (profile, bank connection, settings). The app always opens on Money. The game's Job, Assets, People, Money and Activities are action menus inside the Life tab, not system tabs.

**Money tab** (Emma/Snoop style, Tier 1, labelled mock data until bank OAuth works in Tier 2):
- Balance and net worth over time (line charts, Swift Charts)
- Spending by category this month (bar or donut)
- Subscriptions: list, monthly total, price-rise flags
- Bills and upcoming payments
- Budgets per category with progress
- Savings goals
- The Real-life Decision as one action card at the top

**Spend prediction** (Money tab, Tier 1, ADR 0017):
- Each morning predict today's spend with a range (engine code: gradient boosting or regression on transaction history + Open-Meteo weather + day of week + payday cycle + gov.uk bank holidays JSON). Not an LLM.
- "Guess my spend": user guesses first, then sees the prediction; at end of day compare with the actual total; points for the closest guess; streak of good guesses.
- Show the top 3 reasons with their effect in £ (feature contributions).
- Backtest the model on fixture history and show its accuracy in docs and in the app.
- Mock transaction fixtures until bank OAuth works.

Backend: `/v1/finance/*` endpoints built from transactions (TrueLayer sandbox in Tier 2, labelled fixtures now). Categorisation and subscription detection are engine code, not LLM.

**Bridge:** Money tab data feeds "Play yourself" in Life. Lessons link to real numbers ("You spend £47 a month on 6 subscriptions").

### Live PvP: "Same Life"

- Room code or QR. 2–8 players.
- Same character, same seed, same events.
- Each player ages at their own pace.
- Live rival strip: age, net worth, Index.
- End: compare ribbons, Index and net worth. Side-by-side replay of where the lives split.
- Modes: Duel, Group, Class (a host runs the room).

### Challenges

Examples: "Own a home by 30", "Survive 2008 with no missed payment".

### Paid extras (DEMO ONLY, label every screen "Demo payment")

Rewind Pass, God Mode, Boss Mode (start a business using Companies House data). Implement with StoreKit 2 and a `.storekit` configuration file. **Lessons are never paywalled.**

### INDEX (define exactly, test exactly)

- **Baseline** = "autopilot" twin: same character, same seed, default choice at every decision.
- `R(t) = (NetWorth(t) − NetWorth(0)) / AnnualIncome(0)` — income-normalised, so lives of different wealth compare fairly.
- `Index(t) = 100 × (1 + 0.1 × (R_player(t) − R_autopilot(t))) − 2 × missedPayments − 20 × maxDrawdownFraction_player`, floored at 0.
- Keep the formula and weights in one config file. Document it in `docs/index.md`.
- Unit-test it: monotonicity, and fairness (same choices as autopilot → 100 ± rounding).

---

## 1. Architecture (three layers, required by the brief)

### Experience: native iOS app

- Swift, SwiftUI, **iOS 26** deployment target.
- **Liquid Glass:** system `TabView`; `.buttonStyle(.glass)` and `.buttonStyle(.glassProminent)`; `GlassEffectContainer`; `glassEffectID` with `@Namespace`.
- Emoji characters as TEXT, SF Symbols icons, no third-party art.
- Motion: default `.spring(response: 0.35, dampingFraction: 1.0)`; sheets `response 0.3, damping 0.8`; `.contentTransition(.numericText())` for money and age; `.sensoryFeedback` on age-up, ribbons and bad events. Respect Reduce Motion (cross-fade only).
- Plain English. Zero finance jargon on main screens.
- Dynamic Type, VoiceOver labels, 44 pt touch targets.

### Decision: Python 3.12 package, PURE (no network, no DB)

Synthetic population, twin matching, period matching, event engine, life simulation (seeded RNG → identical life for identical seed), scoring and Index, ranking for the Real-life Decision, backtest.

### Data integration

One adapter per source → canonical schema
`Observation(series_id, source, date, value, unit, region?, fetched_at, status)`
→ Redis cache (TTL per source) → Postgres last-good snapshot.
Status values: `live` | `cached` | `mock`.

### Service

FastAPI app exposing the contract. Postgres. Redis. WebSocket for rooms. Worker for scheduled refresh.

**The iOS app talks ONLY to our backend. No keys or secrets in the app.**

---

## 2. Data sources

Every adapter handles: timeouts, retries with backoff, circuit breaker, bad data validation.

### Verified working without a key (October 2026)

- **Bank of England IADB CSV:**
  `https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2000&Dateto=now&SeriesCodes=IUMBEDR,IUMBV34,IUMBV42&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N`
  - `IUMBEDR` = Bank Rate. `IUMBV34` = 2-year fix, 75% LTV. `IUMBV42` = 5-year fix, 75% LTV. **`IUMBV37` is the 3-year fix, not 5-year.**
  - Send a browser User-Agent.
- **ONS time series JSON**, e.g. `https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/data`. ONS beta API: `https://api.beta.ons.gov.uk/v1/datasets`.
- **Nomis API CSV:** ASHE earnings `NM_30_1`; unemployment (APS) `NM_17_5`; Census 2021 tenure `NM_2072_1`. Census tables cover **England and Wales only**.
- **Land Registry UK HPI** linked-data JSON, regions include Scotland, e.g. `/data/ukhpi/region/scotland/month/2026-06.json`.
- **gov.uk bank holidays JSON** (`https://www.gov.uk/bank-holidays.json`), **postcodes.io**, **Frankfurter FX** (follow redirects), **CoinGecko**, **Yahoo chart endpoint** (unofficial, may block → cache hard), **FRED CSV** (`fredgraph.csv?id=IRLTLT01GBM156N`), **Octopus Energy products API**, **Carbon Intensity API**, **Open-Meteo**, **Police UK** (England and Wales only), **Environment Agency flood API** (England only).

### Need a free key (env vars)

If a key is missing, the adapter serves clearly labelled MOCK data with status `mock`.

- `COMPANIES_HOUSE_KEY`
- `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`
- `DVLA_KEY`, `DVSA_MOT_KEY`
- `DWP_STATXPLORE_KEY`, `EPC_KEY`
- Open Banking sandbox (TrueLayer or Yapily): `OB_CLIENT_ID`, `OB_CLIENT_SECRET`, `OB_REDIRECT_URI`
- `ANTHROPIC_API_KEY`, `LLM_MODEL` (default `claude-haiku-5-5`)

**Bank OAuth flow:** app opens `ASWebAuthenticationSession` on a backend-generated consent link (state + PKCE) → provider redirects to the BACKEND callback → backend exchanges the code → backend redirects to `lifeline://connected?status=ok`. Tokens never reach the device.

**Scotland:** where a source excludes Scotland, use the UK average and show "UK average used" in the event detail.

### Life areas → events

Odds AND costs come from real data for that person, place and year. Each event has a good and a bad money path, and links to a lesson concept.

| Area | Example events |
|---|---|
| Work | Pay rise, redundancy, job offer |
| Home | Rent rise, deal ends, house price crash, boiler breaks |
| Money | Market crash, inflation, crypto boom and bust |
| Bills | Energy shock, fuel price jump |
| Car | MOT fail, repair bill |
| Health | Time off sick |
| Family | Baby, wedding, divorce, inheritance |
| Place | Burglary, flood |
| Employer | Insolvency (Companies House) |
| Study | Student loan interest |
| State | Benefit change, pension age |

Build events from data-driven templates. **Target: 150+ event templates.**

---

## 3. AI use (Responsible AI is judged)

- The LLM writes event flavour text and lesson wording ONLY. The engine decides all outcomes and numbers.
- `explain/verifier`: extract every number from the LLM text. Each must match an engine fact. Otherwise use a deterministic template.
- LLM failure or timeout → templates. Cache LLM outputs.
- `docs/RESPONSIBLE_AI.md`: where AI is used, what stays deterministic, how outputs are checked, what happens when AI fails.
- `docs/AI_USAGE.md`: a log of how Claude Code built this, for the event's AI-level paragraph.

---

## 4. API-first contract

Write `contracts/openapi.yaml` FIRST, with example requests and responses for every endpoint.

**One error format everywhere:** `{"error": {"code": "...", "message": "...", "source": "..."}}`

### Minimum endpoints

```
GET  /v1/health
GET  /v1/sources
GET  /v1/characters                 presets + random
POST /v1/lives
GET  /v1/lives/{id}
POST /v1/lives/{id}/age
POST /v1/lives/{id}/choices
POST /v1/lives/{id}/actions         tab actions
POST /v1/lives/{id}/rewind
GET  /v1/lives/{id}/summary
GET  /v1/concepts
GET  /v1/challenges
POST /v1/decisions                  real-life decision
GET  /v1/evaluation                 backtest
POST /v1/rooms
WS   /v1/rooms/{code}
GET  /v1/lives                     the caller's lives (Play tab)
GET  /v1/finance/overview | spending | subscriptions | bills | budgets | goals | profile   (Money tab; PUT budgets, POST goals)
GET  /v1/next-move                 the one answer (top move + 2 runners-up)
POST /v1/next-move/test            Test it: side-by-side replay of each option
GET|POST /v1/plan                  Do this: the user's plan
GET  /v1/finance/prediction · GET|POST /v1/finance/guesses · GET /v1/finance/prediction/evaluation   (spend prediction, Guess my spend)
GET  /v1/bank/auth-link
GET  /v1/bank/callback
POST /v1/purchases/verify           demo
```

- Generate the Swift client with Apple's `swift-openapi-generator`.
- The backend validates against the same file.
- A contract test suite calls every endpoint and checks schemas.

---

## 5. Repository

**Remote:** `https://github.com/expires/guts-hackathon-2026.git` (PUBLIC, shared with a teammate).

Rules:
- **NO GIT OPERATIONS BY ANY AGENT.** Do not run `git commit`, `git add`, `git push`, `git merge`, `git branch`, `git checkout`, `git worktree`, `git stash` or `git reset`. The user commits and pushes by hand.
- Read-only git commands (`git status`, `git diff`) are allowed.
- `.gitignore` must contain `.env`, `.env.*`, `!.env.example`, `*.p8`, `*.mobileprovision`, `xcuserdata/`, `DerivedData/`, `__pycache__/`, `.venv/`. Create or fix it first.
- Run a secret scan (gitleaks or detect-secrets) on the working tree after every milestone. Report findings in `docs/STATUS.md`.
- Never print, log or write the values from `.env` into any other file.
- At each green milestone, add a suggested commit message (Conventional Commits) to `docs/COMMITS.md`, so the user can commit by hand.

## 5b. Repo layout

```
/CLAUDE.md                     rules for all agents (write first)
/BUILD_SPEC.md                 this file
/contracts/openapi.yaml
/docs/architecture.md          + Mermaid diagram
/docs/index.md  /docs/RESPONSIBLE_AI.md  /docs/AI_USAGE.md  /docs/DEMO.md  /docs/STATUS.md
/docs/adr/0001-*.md ...
/services/api/
  lifeline_api/        FastAPI, auth, websocket
  lifeline_data/       adapters
  lifeline_engine/     pure decision code
  lifeline_sim/        game rules
  lifeline_explain/    LLM + verifier + templates
  lifeline_eval/       backtest
  tests/               unit, contract, integration (recorded fixtures)
/apps/ios/
  Lifeline/            Views, Features, DesignSystem, Networking
  LifelineTests/       Swift Testing
  LifelineUITests/
  Lifeline.storekit
/docker-compose.yml            api, worker, postgres, redis
/Makefile                      make up · make test · make lint · make ios-test · make demo-seed
/.env.example
/.github/workflows/ci.yml      ruff, mypy, pytest, contract tests, xcodebuild test
/README.md                     one-command run, architecture, trade-offs, data sources + attributions, demo
```

---

## 6. Execution model: BOSS → WORKERS → VERIFIERS

### Step A — BOSS (sequential, fast)

1. Create the structure, `CLAUDE.md`, `.env.example`, `docs/architecture.md` skeleton, complete `contracts/openapi.yaml` with examples, canonical schema, docker-compose skeleton, Makefile and CI skeleton.
2. Create subagent definitions in `.claude/agents/` for each worker and verifier below: role, owned paths, done criteria, forbidden paths.
3. Assign each worker its owned paths (section 5b). Workers share one working tree and never edit paths they do not own. Shared files (contract, `CLAUDE.md`, Makefile, docker-compose) are edited only by the BOSS.

### Step B — WORKERS (in PARALLEL via subagents; each owns only its paths)

| ID | Name | Scope |
|---|---|---|
| W1 | data-adapters | All sources, cache, circuit breaker, mock fallbacks, recorded fixtures, finance transactions (fixture personas; TrueLayer in Tier 2) |
| W2 | engine | Synthetic population (IPF from live Nomis/Census marginals), twins (Mahalanobis k-NN), period matching (standardised macro state, k-NN), ranking, backtest, Money insights (categorisation, subscriptions, bills, budgets, goals, profile; no LLM). **Tests first** with hand-calculated cases, e.g. £180,000 over 25 years at 4.98% → £1,050.17 per month |
| W3 | sim | Life simulation, `play_scenario` for Test it, 150+ event templates, stats, Index, ribbons, challenges, rewind, deterministic seeds |
| W4 | api | FastAPI routes per contract, Sign in with Apple → JWT, rooms over WebSocket + Redis pub/sub, bank OAuth, demo purchases |
| W5 | explain | LLM client, prompts, number verifier, templates, caching |
| W6 | ios-core | Design system, navigation (Money, Life, Play, You tabs), Money tab, character select, Life screen, Age button, event sheets, Life action menus, lessons, rewind, summary, collection |
| W7 | ios-social-store | Play tab rooms/PvP UI, You tab bank connection, live rival strip, Real-life Decision screen, bank connect, StoreKit demo store, widget (Tier 2) |
| W8 | infra-docs | Docker, Makefile, CI, README, ADRs, attributions screen data, `DEMO.md`, demo seed data |

### Step C — VERIFIERS (run after each worker milestone; a worker's milestone is not accepted until its verifier passes)

| ID | Name | Checks |
|---|---|---|
| V1 | contract | Every endpoint matches `openapi.yaml`; error format everywhere |
| V2 | engine | Hand-calculated cases, Hypothesis property tests, determinism (same seed → same life), Index fairness |
| V3 | resilience | Kill or slow each source → API still answers with `cached`/`mock`; bad payloads rejected; no crash |
| V4 | ios | `xcodebuild` build + Swift Testing + UI tests on simulator; screenshot every screen to `docs/screens/`; accessibility labels present |
| V5 | demo | Runs `DEMO.md` end to end against the docker compose stack + simulator |
| V6 | security | No secrets in repo (scan), inputs validated, rate limits, OAuth state and PKCE |

### Gates and order

- **TIER 0** (must be green before any Tier 1 work starts): contract; BoE, ONS, Nomis, Land Registry and postcodes adapters; engine core; sim core (age, events, stats, Index); lives API; iOS character select + Life screen + Age + event sheet. `make up && make test` green. V1–V5 green.
- **TIER 1:** FIRST the Next Move (engine, Test it, plan, card, demo story); then Money tab and `/v1/finance/*` on labelled fixtures, spend prediction and Guess my spend, Play and You tabs, Life action menus, all sources, 150+ events, lessons, concepts, rewind, ribbons, summary, Real-life Decision, backtest screen, LLM explain + verifier.
- **TIER 2:** Same Life PvP, bank OAuth, StoreKit demo store, challenges, widget.
- Never start a tier until the previous tier is green.
- If a Tier 2 item threatens Tier 0 or 1 stability, cut it and record why in `docs/adr/`.

### Rules for all agents

- No git operations (see section 5). The working tree must stay runnable after every milestone.
- Python: ruff + mypy strict on engine and sim; pytest.
- Swift: Swift 6 where it compiles cleanly, otherwise Swift 5 mode (record an ADR).
- No secrets in code. Config from env only. Validate all inputs (Pydantic).
- Every number shown to the user must trace to a source or the engine.
- Plain English in UI copy. No jargon on main screens.

---

## 7. Demo (write `docs/DEMO.md` and seed data to make it exact)

1. Play a nurse (Leeds) and a banker (London) from 2006 through 2008: same crash, different lives.
2. A judge joins a Same Life room via QR and plays the 2021–2023 rate shock.
3. Rewind a bad choice. Show the other path and the Index difference.
4. Play yourself to today → Real-life Decision screen with evidence and source status.

---

## 8. Finish

When done, or when time-boxed, produce:

- `docs/STATUS.md`: what is complete per tier, what is mocked and why, known issues.
- Final architecture diagram and trade-offs in `README.md`.
- A one-paragraph AI-usage statement draft in `docs/AI_USAGE.md`. The user sets the AI level.

**Start now with Step A.**
