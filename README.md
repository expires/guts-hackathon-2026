# Penny

_Your money, played forward._

**Rich or broke, it's about habits.**

GUTS Hackathon 2026 (24 hours). BlackRock / Aladdin challenge: "One app. Every source. One clear decision."

- This README is the submission checklist. Section 15 maps each brief requirement to its evidence.
- Product direction: [DIRECTION_V2.md](DIRECTION_V2.md), recorded as ADRs 0046 to 0061.
- Code names keep the earlier working name "Lifeline": bundle ids, the Xcode project, `LifelineClient`, the Python packages `lifeline_*` (ADR 0040).

> **Penny is AI and can make mistakes. Guidance only, not regulated financial advice. Check before big decisions.**

## 1. User story

**Who:** a UK student or young graduate who manages money alone for the first time (ADR 0046).

- Income is any mix of maintenance loan, scholarship, bursary, grant, parents or family, part-time job or first salary.
- Each source arrives on its own schedule: loan instalments, termly bursary payments, weekly shifts, monthly salary.
- Housing: halls, rent or living with family.
- Costs: subscriptions, maybe Klarna, an overdraft or a card.

**The one decision:** "Where should my money go this month?"

**Examples:** the 4 built-in sample students (synthetic, 3 months each, labelled "Sample data"). The values are the engine's output on 17 Oct 2026, from the V2 and V4 reports. The engine computes them again on every request.

| Sample student | Money | Penny's Next Move |
|---|---|---|
| Scholarship student | Scholarship and bursary, about £420 a month. Halls paid. No debt. | Nothing urgent. Cash covers 5.5 months of spending. |
| Rich student | About £2,000 a month from parents. City flat, many subscriptions, Klarna. | "Plan for £612 you are missing before 2 November" |
| Working student | Maintenance loan and bar shifts with pay that changes. Overdrawn. | "Plan for £131 you are missing before 23 October" |
| Commuter student | Lives with family. Grant and family help. 16-25 Railcard. Saving for a deposit. | "Put £952 in a Lifetime ISA" (£238 bonus) |

- Habit score (0 to 100, ratios only): scholarship 82, rich 47 (V2 final re-check). Income does not set the score. Habits do.
- 4 more sample profiles exist for the team phones: fresher in halls, graduate in a first job, placement year, delivery rider.

## 2. The decision: Next Move

`GET /v1/next-move` answers "Where should my money go this month?" (the `question` field in the contract). It returns one top move and up to two runners-up. The engine (`lifeline_engine`) computes and ranks every move. No AI chooses the move.

Each move has these parts (`services/api/lifeline_contracts/next_move.py`):

| Part | Field | What the user sees |
|---|---|---|
| Gain | `impact_per_year`, `cover_months` or `shortfall` (`gain_kind`) | £ a year, months of cover, or "£X short before DATE" |
| Trade-off | `trade_off.summary`, `trade_off.points` (ADR 0042) | "What you give up" on the card; all points in Why? |
| Worst case | `worst_case_per_year` | £ a year in the worst matched past period |
| Confidence | `confidence_level`, `sample_size`, `confidence_label` | For example "Medium confidence (sample: 6 past periods)" |
| Evidence | `evidence` (exactly 3 points, each number in `facts`) | Three lines in Why? |
| Sources | `decision_sources`, `decision_source_count` (ADR 0032) | "Based on N sources", each with its status |

Student options (ADR 0046). Trade-off text is quoted from `lifeline_engine/trade_offs.py`. The engine offers a move only when the user's data meets its preconditions (`lifeline_engine/preconditions.py`, ADR 0053 bug 1).

| Option | Move kind | Trade-off it states |
|---|---|---|
| Weekly budget until the next money arrives (loan instalment, bursary, family transfer or payday) | `weekly_budget` | "£X a week less to spend until DATE", or "Nothing safe to spend until DATE: bills come first" when money runs short |
| Build a safety fund | `build_emergency_fund` | "Less money invested, so lower expected growth" |
| Pay off expensive debt (card, overdraft above the free limit, BNPL with a rate) | `pay_off_debt` | "Less cash on hand" or "£X a month less to spend or save" |
| Lifetime ISA (25% government bonus) | `lifetime_isa` | "A 25% charge if you take it out for anything but a first home" |
| Cut subscriptions | `cancel_subscription`, `switch_subscription` | "You lose NAME and anything saved in it", or fewer features on a cheaper plan |
| Move savings to a better rate | `move_savings` | "The rate can change, and some top rates need notice to take money out" |
| Keep as cash | `keep_cash` | "Rising prices can make your cash worth less over time" |

- Also in the engine: `cut_budget` (spending above the user's usual level), and `fix_mortgage`, `remortgage`, `switch_energy` only when the user has a mortgage or energy details.
- `spread_investments` is deprecated (ADR 0046).

How the engine picks the move:

1. **Candidates.** Only moves whose preconditions match the data.
2. **Urgent first.** A `weekly_budget` move with a shortfall above £0 always ranks first (ADR 0057). Running out of money before the next payment is the most urgent decision.
3. **Score.** Twin-based moves simulate similar synthetic people ("twins") through matched past periods and one stress period. The option with the highest `expected - 0.5 x max regret` wins (ADR 0020).
4. **Rank.** Moves are ranked by `impact + 0.5 x min(0, worst case)`, scaled by confidence.
5. **Confidence (ADR 0053 amendment).** "High" needs at least 8 independent cases and a 70% share. "Medium" needs 5 cases and 55%. The label names the unit ("6 past periods", "4 of the last 4 weeks"). Plain arithmetic on the user's own numbers says "Based on your own numbers".
6. **Trade-off.** The engine writes it per move kind (`lifeline_engine/trade_offs.py`). No AI writes it.

Card buttons:

- **Test it:** `POST /v1/next-move/test` plays the user's profile through a past period once per option, on the same seed. Only twin-based moves are testable.
- **Why?:** evidence, trade-off, sources, confidence and a lesson.
- **Do this:** `POST /v1/plan` adds the move to the user's plan.
- **Ask Penny:** switches to the Penny tab with the move loaded.

Accuracy is reported as measured: [docs/prediction.md](docs/prediction.md) (ADR 0023).

## 3. Architecture

Full description: [docs/architecture.md](docs/architecture.md).

```mermaid
flowchart TB
  subgraph EXP["Experience layer: iOS 26 app (apps/ios)"]
    TABS["Tabs: Money, Penny, Play, You<br/>pure SwiftUI Views"]
    VM["ViewModels + Screen glue<br/>@Observable, ViewState, disk cache"]
    LC["LifelineClient<br/>LiveClient or MockClient"]
    VM --> TABS
    VM --> LC
  end

  subgraph SVC["Service: FastAPI (services/api/lifeline_api)"]
    REST["REST /v1/*<br/>contract: contracts/openapi.yaml"]
    SSE["POST /v1/chat/stream<br/>Penny, server-sent events"]
    WS["WebSocket /v1/rooms/{code}<br/>lobby, Money Quiz, Same Decision, Same Life"]
    AUTH["Demo JWT / Sign in with Apple<br/>rate limits, body limit, one error format"]
  end

  subgraph DEC["Decision layer: pure Python, no I/O"]
    ENG["lifeline_engine<br/>Next Move, trade-offs, habit score,<br/>facts table, money insights, Penny tools"]
    SIM["lifeline_sim<br/>Life, student paths, Quick Life,<br/>quiz and Same Decision content"]
    EVAL["lifeline_eval<br/>backtest"]
    EXPL["lifeline_explain<br/>Penny chat, number verifier, templates"]
  end

  subgraph DATA["Data integration layer (services/api/lifeline_data)"]
    ADP["One adapter per source<br/>timeouts, retries, circuit breaker"]
    MACRO["Annual MacroTable"]
    STMT["Statement parser + sample statements<br/>FinanceSnapshot (encrypted per user)"]
    ADP --> MACRO
  end

  REDIS[("Redis<br/>source cache, rooms + pub/sub, rate limits")]
  PG[("Postgres<br/>encrypted snapshots, lives, plans, circles")]
  EXT[["20 public sources<br/>BoE, ONS, Nomis, Land Registry, ..."]]
  LLM[["Anthropic API<br/>wording and chat only"]]

  LC -- "HTTPS JSON" --> REST
  LC --> SSE
  LC -- "WebSocket" --> WS
  REST --> AUTH
  REST --> ENG & SIM & EVAL
  SSE --> EXPL
  EXPL --> ENG
  EXPL -.-> LLM
  ENG --> MACRO
  ENG --> STMT
  SIM --> MACRO
  WS <--> REDIS
  REST <--> PG
  ADP <--> REDIS
  ADP -.-> EXT
```

| Layer | Code | What it does |
|---|---|---|
| Experience | `apps/ios` | SwiftUI app, iOS 26. Tabs: Money, Penny, Play, You (ADR 0048). Talks only to our backend. Holds no keys. |
| Decision | `lifeline_engine`, `lifeline_sim`, `lifeline_eval`, `lifeline_explain` | `lifeline_engine` and `lifeline_sim` are pure: no network, no database, no clock, seeded RNG only. Same data and same seed give the same result. `lifeline_explain` writes the wording and checks every number. |
| Data integration | `lifeline_data` | One adapter per source. Each value has a status: `live`, `cached`, `unavailable` (`mock` only in demo mode). Redis cache, Postgres last-good copy, annual `MacroTable`. Statement parser and sample statements. |

A FastAPI service (`lifeline_api`) joins the layers. Errors use one format everywhere: `{"error": {"code": "...", "message": "...", "source": "..."}}`.

## 4. Data

### 4.1 Live market data

`GET /v1/sources` lists 20 sources (`served_sources()` in `services/api/lifeline_data/sources.py`). Status changes at run time. The endpoint is the source of truth.

Key: **D** = Next Move input (`DECISION_PROVIDERS` in `lifeline_engine/next_move.py`). **P** = Penny reads it through a tool. **C** = context only, never a decision input (ADR 0030). **G** = Life game or support.

| id | Source | What it supplies | Use |
|---|---|---|---|
| `boe` | Bank of England Database | Bank Rate, savings, mortgage and card rates | D, P |
| `ons` | Office for National Statistics | Inflation (CPI) and other UK statistics | D, P |
| `nomis` | Nomis (ONS labour market and Census) | Earnings (ASHE) and unemployment by region | D, G |
| `landregistry` | HM Land Registry UK House Price Index | House prices by region | D |
| `companieshouse` | Companies House API | Counts of companies in liquidation and administration | D |
| `octopus` | Octopus Energy products API | Energy tariffs | D |
| `frankfurter` | Frankfurter FX rates (ECB reference rates) | Exchange rates; Penny's currency conversion | D, P |
| `coingecko` | CoinGecko | Crypto prices | D |
| `postcodes` | postcodes.io | Postcode to region | G |
| `bankholidays` | GOV.UK bank holidays | Bank holidays for "Guess my spend" | G |
| `openmeteo` | Open-Meteo | Daily weather for "Guess my spend" | G |
| `yahoo` | Yahoo Finance chart endpoint | Monthly stock market history | G |
| `fred` | FRED, Federal Reserve Bank of St. Louis | UK 10-year government bond yield (OECD series) | G |
| `carbonintensity` | Carbon Intensity API | Regional grid carbon intensity | G |
| `police` | Police UK data API | Burglary counts by area | G |
| `environmentagency` | Environment Agency flood monitoring API | Flood warnings | G |
| `statxplore` | DWP Stat-Xplore | Universal Credit caseload, Great Britain | G |
| `epc` | Energy Performance of Buildings register | Share of homes rated A to C by region | G |
| `guardian` | The Guardian Open Platform | Headlines and links only | C, P |
| `boe-mpc` | Bank of England MPC dates | Next Bank Rate decision date | C, P |

- Penny can also call the Next Move, Test it and finance tools, so every D source reaches her answers through the engine.
- Status checks:
  - Local stack, 2026-10-17 22:50 UTC: 18 `live`, 2 `mock` (`yahoo`, `fred`; demo mode).
  - Railway, after the V2 deploy: 20 sources, 17 `live`, `landregistry` `cached`, `yahoo` and `fred` `unavailable`.
- **No fake data in live mode** (ADR 0027). A source with no live or cached real data reports `unavailable`. Its values are absent from the `MacroTable`. The app shows "Unavailable".
- **"Based on N sources" counts decision sources only** (ADR 0032). An unavailable source is listed but not counted. Context and game sources are never counted.
- Cut from the product (ADR 0046): Adzuna, DVLA, DVSA MOT, Open Banking sandbox (TrueLayer). Their adapters stay in the code. `/v1/sources` does not list them.
- Attribution text: `attribution` in `/v1/sources` and [`services/api/lifeline_data_attributions.json`](services/api/lifeline_data_attributions.json).

### 4.2 Personal data

The user picks one of three inputs in onboarding, under "Connect your money" (ADR 0047, 0049):

| Input | How | Route |
|---|---|---|
| Upload a statement | Monzo or Revolut CSV. PDF statements are also read; a bank PDF with embedded fonts fails with a clear message to upload the CSV. Max 5 MB, 20,000 rows. | `POST /v1/finance/statements` |
| Enter your numbers | Student or working, age, postcode, housing, income sources (amount and schedule each), student loan plan, regular costs, savings, debts (card, overdraft, BNPL) | `PUT /v1/finance/manual` |
| Use a sample statement | One of 4 sample student cards | `GET /v1/samples`, `POST /v1/samples/{id}/import` |

- Sample statements are synthetic. Each is a Monzo-style CSV and a PDF with "Sample data" on every page. Files: `demo/statements/`. Generator: `tools/gen_statements.py`.
- Sample snapshots carry `source="sample"`. The app labels them "Sample data".
- Every input becomes the same `FinanceSnapshot`. It is stored encrypted in Postgres (section 13).

### 4.3 Why no bank connection

Penny does not connect to banks. Each route was checked and closed for a student app built in 24 hours:

- **Monzo API:** for personal use only. A public app cannot use it for other customers.
- **Open Banking:** needs FCA authorisation, or a contract with an authorised aggregator.
- **GoCardless Bank Account Data:** closed to new signups in 2025.
- **Apple FinanceKit:** needs a special entitlement from Apple.

Statement upload produces the same `FinanceSnapshot` format as a bank feed. A licensed feed can plug in later with no change to the engine.

## 5. Official facts

Every rule number comes from an official source (ADR 0058).

- **69 official amounts in total:** 55 facts in the facts table and 14 in the Life game tables.
- **Facts table:** `services/api/lifeline_engine/rules.py`. 55 facts for the 2026/27 tax year. Each fact stores its official URL and the date it was checked (`checked="2026-10-17"`).
- **Topics:** ISA and Lifetime ISA (11), income tax (8), Scottish income tax (11), National Insurance (4), student loans (11), student finance and maintenance loan schedule (5), council tax (2), 16-25 Railcard (3).
- **Life game amounts:** `services/api/lifeline_sim/paths.py` adds 14 dated official amounts: tuition fee caps from 2006 to 2027 (legislation.gov.uk and gov.uk) and the Master's Loan maximum for 2024 to 2026 (gov.uk). Each has a URL and a checked date.
- **Allowed domains:** gov.uk (including HMRC, Student Finance England and SLC guidance), saas.gov.uk, studentfinancewales.co.uk, studentfinanceni.co.uk, railcard.co.uk, 16-25railcard.co.uk, legislation.gov.uk, bankofengland.co.uk. Money Quiz sources may also use ons.gov.uk and nomisweb.co.uk (ADR 0058 amendment).

How Penny looks up a rule (tax, student loans, ISAs, benefits, council tax, Railcard), in `lifeline_explain/official.py`:

1. Read the facts table first. Show the official URL and "checked DATE" in the sources.
2. If the fact is not in the table, run web search on the allowed domains only. Quote a number only if it appears in the official page text that came back.
3. If no official page states it, say so and give no number.

## 6. Penny

Penny is a full tab (ADR 0051). One chat, two labelled answer modes. The mode depends on what Penny used (`ChatResponse.mode`).

| Mode | Label | When | Check |
|---|---|---|---|
| `checked` | "Checked with your data" | Penny used an engine tool | The verifier checks every number against the tool facts, with its unit (£ or %) |
| `general` | "General answer" | No engine tool. Student-focused prompt with web search: concepts, student life, cooking, CVs, study help | If the answer states the user's own numbers, the verifier blocks it and Penny retries with an engine tool |

**Tools** (`lifeline_explain/chat_tools.py`, ADR 0033, 0060):

| Tool | What it does |
|---|---|
| `next_move` | The user's Next Move |
| `test_move` | Test it for a move |
| `finance_summary` | Summary of the user's money |
| `user_balance` | The user's balance |
| `cash_flow_projection` | Cash until the next money arrives |
| `spend_prediction` | Today's predicted spend |
| `habit_score` | The 6 habit ratios |
| `facts_table` | Official rule facts with URL and checked date |
| `boe_rates` | Live Bank of England rates |
| `inflation` | ONS CPI inflation |
| `fx_convert` | Currency conversion (Frankfurter, ECB rates) |
| `news_search` | Guardian headlines (context only) |
| `rate_decision_dates` | Next Bank of England rate decision |
| `life_replay`, `event_choices` | Life game questions |
| `web_search` | Anthropic server tool; official domains only for rules questions |

- Each tool call streams a plain-words step, for example "Checking exchange rates…". Steps come only from real tool calls.
- Tools are bound to the signed-in user. A tool cannot read another user's data (V6 step 5).
- Penny asks the user only for what only the user knows. She never asks for rates, conversions or public facts (ADR 0060).

**Safety** (`lifeline_explain/prompts.py`):

- No share or crypto picks. No regulated advice.
- Distress gets a kind reply and support: university hardship fund, student support, Samaritans (116 123).
- Statement text, news headlines, web pages and user messages are data, never instructions. They reach the model fenced in `<untrusted>` blocks (ADR 0034).

**Disclaimer** (in every `ChatResponse`, shown in the app with the sources): "Penny is AI and can make mistakes. Guidance only, not regulated financial advice. Check before big decisions."

**Speed:**

- Chat model: Claude Sonnet 5.5 (`CHAT_MODEL`, default `claude-sonnet-5-5`). Target: first bubble under 3 s.
- V4 measured the first bubble at 2.2 to 2.5 s in the app for 3 questions. The 1 million yuan question took about 7 s (2 tool calls).
- Voice: one bubble, two at most. A reaction shows within 1 s. Keep-alive events, then a non-streaming fallback, then "Penny is unavailable right now. Try again."

## 7. Play

Play opens with two choices: **Play solo** and **Play with friends** (ADR 0052).

### Solo

- **Life:** a career and money simulator from age 18. Student start paths: university, apprenticeship, job at 18, gap year, master's (`GET /v1/paths`). The old banker, plumber, retired and nurse presets are no longer offered.
- Pay per path stage is a labelled game assumption: a share of the regional median full-time pay (Nomis ASHE). Student loan repayment uses the official thresholds from the facts table (ADR 0061).
- **Play yourself:** starts a life from the user's own data and current age.
- **Student challenges:** "Make your money last the term", "1 month safety fund", "Clear Klarna", "Lifetime ISA by 25".
- **Quick Life:** ages 18 to 25 in 5 or 6 taps, 2 or 3 events with choices, then a summary card with a habit score. Game money only. The API runs it with `POST /v1/lives` and `quick: true`. The app offers it as a Same Life round in the lobby.

### With friends

1. Tap "Play with friends". The lobby opens with a QR code and a short code.
2. Friends scan the QR or type the code. Their names come from their accounts.
3. The host picks a game and its options on one sheet.
4. Start. 2 players play a duel. More players play as a group.

| Game | What happens |
|---|---|
| **Money Quiz** | Questions from lessons and the facts table, each with its source. 15 s per answer. Live ranking. Penny explains each answer in one line. 59 questions: 42 from the facts table, 17 from lessons, each with a source URL (`lifeline_sim/quiz.py`). |
| **Same Decision** | Everyone faces the same student money decision in the same year of real history (14 prompts, 2007 to 2023, `lifeline_sim/decisions.py`). Reveal of choices and outcomes in game money. |
| **Same Life** | Everyone plays the same life on the same seed, with live rival updates. Quick Life is the short version. |

### Circles

- Friends in a Circle share **habit scores only**: savings rate, months of cover, spend stability, discretionary share, subscription creep, debt pressure. Each is a ratio from 0 to 100, computed by the engine (`HabitScore` in `lifeline_contracts/domain.py`).
- The leaderboard ranks improvement against each member's own first score.
- Penny posts a weekly recap with ratios only.
- **Privacy rule:** no £ amount, balance, income, transaction or merchant leaves the user's own view. The contract test `test_shared_payloads_never_carry_personal_money` enforces it. V6 scanned every room, Circle and challenge payload for 4 players and found 0 personal amounts.

## 8. API contract

- File: [`contracts/openapi.yaml`](contracts/openapi.yaml), versioned under `/v1`.
- It is generated from the Pydantic models in `services/api/lifeline_contracts/` (ADR 0002). Do not edit it by hand. Regenerate with `make contract`.
- The iOS client is generated from the same file by `swift-openapi-generator`.
- Auth: `POST /v1/auth/demo` or `POST /v1/auth/apple` returns a JWT. Send it as `Authorization: Bearer ...`.

## 9. How to run

Prerequisites:

- Docker (Docker Desktop, or Colima with the compose plugin) and `make`.
- `uv` for Python tests and lint.
- For iOS: Xcode with the iOS 26 SDK, and XcodeGen.
- No API keys are needed to start. A missing key makes that source `mock` (demo mode) or `unavailable` (live mode).

Backend:

```bash
make up     # copies .env.example to .env if missing, starts api, worker, postgres, redis, waits for /v1/health
make test   # Python tests (offline, recorded fixtures)
make down   # stop
```

- API: http://localhost:8000. Health: `GET /v1/health`. All targets: `make help`.
- Local default is demo mode (`DATA_MODE=demo`). Set `DATA_MODE=live` in `.env` for live mode.

iOS:

```bash
make ios-gen    # copies the contract into the app and generates Lifeline.xcodeproj
make ios-test   # unit and UI tests on the simulator
```

| Configuration | Client | Backend |
|---|---|---|
| `Debug` | `LiveClient` | http://localhost:8000 |
| `Mock` | `MockClient`, recorded responses | none |
| `Demo` | `LiveClient` | Railway |
| `Dev` | `LiveClient`, app "Penny Dev" | Railway |
| `Release` | `LiveClient` | as set |

- Schemes: `Lifeline` (Debug, with tests) and `Playground` (Mock, `-playground`: a gallery of every screen).
- Phone build: `make ios-device CONFIG=Mock` or `CONFIG=Demo`. It needs `apps/ios/Config/Local.xcconfig` with your team (ADR 0015).
- Judge mode: You tab > "New player" starts a fresh demo account and onboarding. "Reset demo" clears the demo data and returns to Welcome.

Hosted API (Railway, `DATA_MODE=live`, ADR 0028): https://api-production-15615.up.railway.app

- Railway runs the Direction V2 backend (deployed 2026-10-17, 23:55 local time). `/v1/paths` answers 401 without a token. `/v1/sources` lists 20 sources.
- Smoke test after the deploy: 4 sample imports took 0.36 to 1.44 s. `GET /v1/next-move` took 2.3 to 2.4 s.

## 10. Tests and verifiers

| Suite | Path | Command |
|---|---|---|
| Unit (Python) | `services/api/tests/unit/{api,data,engine,eval,explain,sim}` | `make test` |
| Integration (HTTP and WebSocket) | `services/api/tests/integration` | `make test` |
| Contract (responses against `openapi.yaml`) | `services/api/tests/contract` | `make test`; against the stack: `make test-stack` |
| Lint and types | ruff, `mypy --strict`, AI disclosure copy in sync | `make lint` |
| iOS unit and UI | `apps/ios/LifelineTests`, `apps/ios/LifelineUITests` | `make ios-test` |
| Secrets | gitleaks over the working tree | `make secrets-scan` |

- `make test` collects 1,602 Python tests: unit 1,412 (api 103, data 297, engine 262, eval 3, explain 235, sim 512), integration 100, contract 90. All passed in a run on 2026-10-17, about 22:50 UTC.
- Python tests never call the network. They use recorded fixtures under `services/api/tests/fixtures/`.

Verifiers V1 to V6 are separate agents. They check the work and write reports to [docs/verify/](docs/verify/). Latest section of each report:

| Verifier | Latest run | Verdict | Numbers |
|---|---|---|---|
| [V1](docs/verify/V1.md) contract | Direction V2 step 5 | PASS | 103 contract tests passed, 1 skipped. Probes: 130 REST checks, 63 WebSocket checks plus a 30-check quiz re-run, 16 cold-start checks. |
| [V2](docs/verify/V2.md) engine | Direction V2 engine, final re-check | PASS | 762 engine, eval and sim tests passed. 400 fuzzed snapshots, 0 precondition violations. Hand checks of the 4 students' cards. |
| [V3](docs/verify/V3.md) resilience | Tier 2 | FAIL (1 gate finding, T2-G1) | 267 scratch tests passed, 2 failed. T2-G1: a failed upload stayed in memory. The store now writes memory only after the Postgres commit (`lifeline_data/cache.py`). No V3 re-run is recorded yet. |
| [V4](docs/verify/V4.md) iOS | Direction V2 steps 1 to 3 | FAIL (7 findings) | 231 Swift tests in 29 suites and 4 UI tests passed. 74 screenshots. Findings: wrong data badge on 3 screens, fallback confidence label, source names, 2 Penny labels, one Ask Penny route. Re-check in progress. |
| [V5](docs/verify/V5.md) demo | Tier 1 final | PASS | Earlier mortgage demo. The Direction V2 rehearsal has not run yet. |
| [V6](docs/verify/V6.md) security | Step 5 re-check | PASS | Privacy scan over 4 players: 0 personal amounts. Room abuse, Circle and tool isolation checks pass. Secret scan clean. |

## 11. Graceful failure

| Failure | What happens | Where |
|---|---|---|
| A source is down or has no key | Cached real data if present, else `unavailable`. Never mock in live mode. The decision lists the source but does not count it. | `lifeline_data`, ADR 0027, 0032 |
| API still warming after a start | `/v1/health` reports `warming: true` until the `MacroTable` is built. Sample import does not wait for it. | `lifeline_api/main.py` |
| AI missing, slow or wrong | Engine template text. A number that fails the verifier is never shown. | `lifeline_explain`, ADR 0019 |
| Penny answer fails the number check | One rewrite. Then a summary of the tool facts, marked as not checked. | `lifeline_explain/chat.py` |
| Penny model off or times out | "Penny is unavailable right now. Try again." | ADR 0051 |
| Rate limit (429) | The app retries quietly with backoff and honours `Retry-After`. | `apps/ios/Lifeline/Networking/ResilienceMiddleware.swift`, ADR 0038 |
| Slow network | The app shows the last known response from its disk cache at once and refreshes in the background. Skeletons, never spinners with text. | `apps/ios/Lifeline/Networking/DiskCache.swift`, ADR 0060 |
| No money data yet | Not an error. `GET /v1/finance/home` returns `has_data: false`. Money home asks the user to connect money. | `lifeline_api/routes/finance.py`, ADR 0038 |
| Postgres down | Writes answer 503 `store_unavailable` ("Saving is down. Try again in a minute."). Health reports `degraded`. | V3 Tier 2 |

## 12. Security and secrets

- **Keys live only in `.env`** (git-ignored) and in Railway variables. `.env.example` lists every variable name. The app holds no keys.
- **gitleaks before every commit.** `make secrets-scan` runs before each commit. A finding blocks the commit (ADR 0041).
- **User money data is encrypted at rest.** `UserSnapshotStore` stores each user's `FinanceSnapshot` as Fernet ciphertext with `TOKEN_ENCRYPTION_KEY` (`lifeline_data/crypto.py`, `lifeline_data/cache.py`). In live mode a missing key stops the store; nothing is stored as plain text.
- **No bank tokens.** Penny has no bank connection (section 4.3), so it stores no bank tokens.
- **Untrusted text is fenced.** Statement text, merchant names, news headlines, web pages and chat messages reach the model inside `<untrusted source="...">` blocks. The system prompt says this text is data, never instructions (ADR 0034).
- **Names are cleaned.** Room and Circle names lose control and bidi characters (`lifeline_api/names.py`).
- **Rate limits** per user on reads, writes and chat; per IP on sign-in and wrong Circle codes.
- Bearer tokens are removed from logs (`lifeline_api/logsafe.py`).
- Account: `POST /v1/me/reset` clears the user's data. `DELETE /v1/me` deletes the account and removes the user from every Circle.
- Security report: [docs/verify/V6.md](docs/verify/V6.md).

## 13. AI disclosure: How Penny uses AI

Source: [`services/api/lifeline_explain/ai_disclosure.json`](services/api/lifeline_explain/ai_disclosure.json). The You tab shows the same text. `make lint` fails if the app copy differs.

**Where AI is used**

- An AI model (Claude Opus, from Anthropic) rewords the text of game events, their outcomes and the Next Move card.
- Ask Penny uses a faster model (Claude Sonnet, from Anthropic) to write chat answers.
- Ask Penny gives two kinds of answer. Checked with your data: Penny used the app's tools. General answer: Penny works like a normal assistant and can search the web.
- Lessons are fixed text. AI does not write them.
- The app never calls the AI model. Only our server calls it.

**What stays deterministic**

- The engine calculates and ranks the options and picks your Next Move. AI explains it. AI never makes the decision.
- Every number about your money comes from your data, a public data source or the engine.
- The engine writes the trade-off of each move (What you give up). Penny can only say it in other words.
- The game engine decides every event, outcome and money change. The same seed gives the same game.

**How output is checked**

- Checked with your data: a number verifier checks every number against the facts from the app's tools. It also checks the unit: a money fact needs a £ sign and a percent fact needs a % sign. Code: `services/api/lifeline_explain/verifier.py`.
- General answer: Penny must not state your own money numbers. If she does, the app blocks the answer and Penny tries again with the app's tools. Web sources are shown under the answer.
- Rules questions: Penny uses the facts table first and shows the official page and the date it was checked. If the rule is not there, she searches official sites only and quotes a number only if the official page states it. Otherwise she says so and gives no number.
- Penny must not say she has no live data. The app has live Bank of England rates, and a test checks this rule.
- Safety: Penny does not pick shares or crypto and does not give regulated advice. If you sound in distress, she replies kindly and points to your university hardship fund, student support and Samaritans (116 123).
- Prompt injection tests put hostile text in statements, news headlines and user messages. The tests check that hostile text cannot change a rule or add a number.
- Golden tests: `services/api/tests/unit/explain/test_chat.py`, `test_chat_v2.py`, `test_chat_v6_direction.py`, `test_official_sources.py`. Verifier tests: `test_explain.py`, `test_trade_off.py`.

**What happens when AI fails**

- No AI key, an AI error or a failed check: events, outcomes and the Next Move card show the engine's template text. The template text is complete and correct.
- If a checked answer fails the number check, Penny gets one rewrite. If it fails again, Penny shows a summary of the tool facts, marked as not checked.
- If the AI model is off, times out or fails before any tool runs, the chat shows: "Penny is unavailable right now. Try again."
- By default, each AI call stops after 12 seconds and an Ask Penny answer stops after 24 seconds.
- A number that fails the check is never shown.

How we used AI to build Penny (Claude Code agents, verifiers, gates): [docs/AI_USAGE.md](docs/AI_USAGE.md). Product rules: [docs/RESPONSIBLE_AI.md](docs/RESPONSIBLE_AI.md).

## 14. Decisions

Every decision is an Architecture Decision Record (ADR) in [docs/adr/](docs/adr/). ADRs 0046 to 0061 record Direction V2 and supersede earlier ADRs where they conflict.

| ADR | Decision |
|---|---|
| [0001](docs/adr/0001-record-decisions.md) | Record decisions as ADRs |
| [0002](docs/adr/0002-contract-generated-from-pydantic.md) | Generate `openapi.yaml` from shared Pydantic models |
| [0003](docs/adr/0003-spec-file-name-and-existing-repo.md) | Spec file name and the existing team repo |
| [0004](docs/adr/0004-ownership-of-shared-build-files.md) | Who owns Makefile, docker-compose and Dockerfile |
| [0005](docs/adr/0005-pure-core-macro-table.md) | Engine and sim consume an annual MacroTable |
| [0006](docs/adr/0006-local-tooling.md) | Local toolchain |
| [0007](docs/adr/0007-llm-model-opus.md) | Claude Opus 5.5 for engine text wording |
| [0008](docs/adr/0008-engine-conventions.md) | Engine conventions |
| [0009](docs/adr/0009-ios-tab-layout.md) | iOS tab layout and client conventions |
| [0010](docs/adr/0010-data-fallback-and-mapping.md) | Data fallback order and series mapping |
| [0011](docs/adr/0011-ios-view-viewmodel-split.md) | iOS split into pure Views and ViewModels |
| [0012](docs/adr/0012-sim-replay-and-index.md) | Sim replay model and Index edge cases |
| [0013](docs/adr/0013-index-relative-penalties.md) | Index penalties relative to the autopilot twin |
| [0014](docs/adr/0014-year-end-values-for-fast-series.md) | Year-end values for fast-moving series |
| [0015](docs/adr/0015-device-signing-local-xcconfig.md) | Device signing through a git-ignored `Local.xcconfig` |
| [0016](docs/adr/0016-app-tabs-and-money-tab.md) | App tabs and the Money tab (tab list superseded by 0048) |
| [0017](docs/adr/0017-spend-prediction-and-guess-my-spend.md) | Daily spend prediction and "Guess my spend" |
| [0018](docs/adr/0018-next-move.md) | One question answered by the Next Move |
| [0019](docs/adr/0019-explain-layer.md) | Explain layer: AI wording, number verifier, templates |
| [0020](docs/adr/0020-stress-period-in-risk.md) | Stress period in Next Move risk; the demo follows the engine |
| [0021](docs/adr/0021-data-tier1.md) | Tier 1 data choices |
| [0022](docs/adr/0022-api-tier1.md) | Tier 1 API choices |
| [0023](docs/adr/0023-confidence-and-honest-accuracy.md) | Confidence for multi-option moves; honest accuracy reporting |
| [0024](docs/adr/0024-sim-tier1.md) | Tier 1 sim choices |
| [0025](docs/adr/0025-ios-tier1.md) | Tier 1 iOS structure |
| [0026](docs/adr/0026-native-design-rebuild.md) | Native SwiftUI rebuild of the design handoff |
| [0027](docs/adr/0027-no-mock-in-live.md) | No mock data in live mode; disabled sources |
| [0028](docs/adr/0028-railway-deploy.md) | Railway deployment |
| [0029](docs/adr/0029-tier2-away-plan.md) | Tier 2 scope |
| [0030](docs/adr/0030-news-and-rate-dates.md) | News and rate-decision dates are context only |
| [0031](docs/adr/0031-ask-penny.md) | Ask Penny answers through engine tools |
| [0032](docs/adr/0032-decision-sources-count.md) | "Based on N sources" counts decision sources only |
| [0033](docs/adr/0033-chat-tools-and-facts-table.md) | Engine tools for Penny, cash-flow projection, facts table |
| [0034](docs/adr/0034-untrusted-text.md) | Untrusted text is data, never instructions |
| [0035](docs/adr/0035-parallel-backend-tier2.md) | Tier 2 backend in parallel with the Tier 1 iOS gate |
| [0036](docs/adr/0036-yaffy-merge.md) | Merge of a teammate's integration branch (cancelled by 0046) |
| [0037](docs/adr/0037-parallel-ios-features.md) | Parallel iOS feature work |
| [0038](docs/adr/0038-money-empty-state-and-limits.md) | No-data is a normal state; one Money home request; quiet rate limits |
| [0039](docs/adr/0039-phone-milestones.md) | Phone installs at milestones only (superseded by 0056) |
| [0040](docs/adr/0040-product-name-penny.md) | Product name "Penny" |
| [0041](docs/adr/0041-boss-commits.md) | Commit rules on main |
| [0042](docs/adr/0042-trade-offs.md) | Every Next Move states its trade-off |
| [0043](docs/adr/0043-official-brief-alignment.md) | Official GUTS brief alignment (named user superseded by 0046) |
| [0044](docs/adr/0044-same-life-room-rules.md) | Same Life room rules |
| [0045](docs/adr/0045-test-it-same-age.md) | Test it replays today's you at today's age |
| [0046](docs/adr/0046-direction-v2-product.md) | Direction V2: Penny for UK students |
| [0047](docs/adr/0047-data-and-sample-statements.md) | Data sources, sample statements, no bank connections |
| [0048](docs/adr/0048-four-tabs-compact.md) | Four tabs (Money, Penny, Play, You), compact layout |
| [0049](docs/adr/0049-student-onboarding-judge-mode.md) | Student onboarding and judge mode |
| [0050](docs/adr/0050-money-tab-v2.md) | Money tab V2 |
| [0051](docs/adr/0051-penny-tab.md) | Penny tab with two answer modes |
| [0052](docs/adr/0052-play-solo-and-friends.md) | Play solo and Play with friends; Circles privacy rule |
| [0053](docs/adr/0053-phone-test-bugs.md) | Bugs from phone testing; confidence rules |
| [0054](docs/adr/0054-responsible-ai-v2.md) | Responsible AI, V2 |
| [0055](docs/adr/0055-demo-provisional.md) | Demo requirements (provisional) |
| [0056](docs/adr/0056-v2-order-and-gates.md) | V2 order, installs and commits |
| [0057](docs/adr/0057-monthly-costs-meaning.md) | What `monthly_costs` means; shortfall ranks first |
| [0058](docs/adr/0058-official-sources-for-rules.md) | Rules and facts come from official sources |
| [0059](docs/adr/0059-play-contract.md) | Play with friends contract |
| [0060](docs/adr/0060-instant-screens-and-penny-tools.md) | Instant screens and Penny's full toolset |
| [0061](docs/adr/0061-student-paths-and-games.md) | Student paths, Quick Life and game content |

## 15. Official checklist

| | Brief requirement | Evidence |
|---|---|---|
| [x] | Clear user | Section 1. Persona from ADR 0046, shown with 4 sample students. No named real user. |
| [x] | One clear decision | Section 2. `GET /v1/next-move`, `lifeline_engine/next_move.py`, ADR 0018, 0046 |
| [x] | Evidence | 3 evidence points with facts, worst case, confidence with sample size, decision sources. `lifeline_contracts/next_move.py`, [docs/prediction.md](docs/prediction.md) |
| [x] | Trade-offs | "What you give up" on every move. `lifeline_engine/trade_offs.py`, ADR 0042 |
| [x] | Multiple data sources | Section 4: 20 public sources (8 decision inputs) plus the user's own statement or numbers |
| [x] | Meaningful version control | Section "Version control", [docs/COMMITS.md](docs/COMMITS.md), ADR 0041 |
| [x] | AI disclosure | Section 13, `ai_disclosure.json`, You tab, [docs/RESPONSIBLE_AI.md](docs/RESPONSIBLE_AI.md), [docs/AI_USAGE.md](docs/AI_USAGE.md) |
| [x] | How to run | Section 9, `Makefile` |
| [x] | Tests | Section 10, `services/api/tests/`, `apps/ios/LifelineTests/`, [docs/verify/](docs/verify/) |
| [x] | Security | Section 12, [docs/verify/V6.md](docs/verify/V6.md) (latest run PASS), `make secrets-scan` |
| [ ] | All verifiers green | V3 (Tier 2) and V4 (Direction V2 steps 1 to 3) last reported FAIL. Re-runs pending. V5 Direction V2 rehearsal not run. |
| [x] | Hosted API on the current build | Section 9. https://api-production-15615.up.railway.app runs the V2 backend: `/v1/paths` 401 without a token, 20 sources (17 live), smoke test of 4 sample imports (0.36 to 1.44 s) and Next Move (2.3 to 2.4 s). |
| [ ] | Demo script | `docs/DEMO.md` is rewritten when the final script arrives (ADR 0055). |

## Version control

- One logical change per commit.
- Conventional Commits style messages (for example `feat:`, `fix:`, `chore:`).
- Tests pass on each commit.
- `make secrets-scan` runs before each commit. A finding blocks the commit (ADR 0041).
- Commit messages are also listed in [docs/COMMITS.md](docs/COMMITS.md). Decisions are in [docs/adr/](docs/adr/).

## Team

| Name | Area |
|---|---|
| Yath | "Play yourself" layer: adapters, habit vector, backtest, scenarios, dashboard, friends |
| Ash | Historical engine: synthetic population, twin matching, past-period replay, life loop |
| TBC | TBC |
| TBC | TBC |
| TBC | TBC |
