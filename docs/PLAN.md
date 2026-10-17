# Plan: "Play yourself" layer

Owner: Yath · Status: draft, 17 Oct 2026 · Related: Ash's historical engine (synthetic UK population, twin matching, replays of 2008, COVID and 2022, life loop)

This layer takes a user's real habits (spending from Monzo, investing from a Trading212 Stocks & Shares ISA) and lets them:

1. **Backtest**: replay their own contribution habits under different allocation splits and techniques through past periods.
2. **Future insight**: compare possible paths using past periods with similar conditions. These are always labelled *modelled scenarios*. They are never forecasts or advice.
3. **Dashboard**: see all their finances in one view.
4. **Friends**: compete on scores and values rebased to 100, and opt in to sharing their invested-assets split as a pie, like Trading212's.

The engine makes every decision. AI only explains results the engine has already produced.

---

## 1. Build order

Each step ends with tests passing and code merged to `main`.

| # | Step | Done when |
|---|------|-----------|
| 0 | Scaffold: `pyproject.toml`, ruff, pytest, `Makefile`, `.env.example`, settings | `make test` and `make lint` run green on an empty package |
| 1 | **Adapter interface + domain models** | `FinanceAdapter` protocol and pydantic models merged, with contract tests written |
| 2 | **Mock adapter** | Deterministic personas pass the contract tests. Optional slow and bad-data modes exist |
| 3 | **`habit_vector()`** | All 7 factors have hand-computed unit tests, and a test proves the output contains no £ amounts |
| 4 | **Minimal backtest on mock data** | DCA and lump sum run over synthetic monthly returns with 2008, COVID and 2022 windows. Closed-form tests pass |
| 5 | API layer | FastAPI app with the response envelope, `/openapi.json` served, and an integration test on mock data |
| 6 | Dashboard | The experience layer reads `/v1/dashboard` and `/v1/habit-vector` |
| 7 | Live adapters | Trading212 and Monzo adapters. **Blocked until the API questions in §9 are answered** |
| 8 | Future insight (analog scenarios) | A fan of outcomes from matched past windows, with the disclaimer always shown |
| 9 | Friends competition | Rebased leaderboard and opt-in pie |
| 10 | Docs and demo | Architecture diagram, trade-offs, AI declaration and demo script in the README |

Steps 1–4 are the immediate task. Steps 5–10 follow, roughly in that order, and steps 6 and 7 can run in parallel.

---

## 2. Architecture (3 layers)

```
experience  ─  web UI (dashboard, backtest explorer, scenarios, friends)
     │  HTTP/JSON, one envelope, OpenAPI
decision    ─  habit_vector · backtest · scenarios · scoring/rebasing · explainer(AI, read-only)
     │  domain models (pydantic), no HTTP or vendor types
data        ─  FinanceAdapter: Trading212Adapter · MonzoAdapter · MockAdapter
               + aggregator (concurrency, timeouts, cache, staleness)
```

Rules:
- Vendor JSON never passes beyond the adapter. Adapters return domain models only.
- The decision layer is pure functions over domain models. No I/O happens there, which makes it trivial to test.
- The API layer is thin. It calls the decision layer, wraps the result in the envelope and maps errors.

### Repo layout (proposed)

```
src/playyourself/
  adapters/      base.py (protocol, errors) · mock.py · trading212.py · monzo.py · aggregator.py
  domain/        models.py (Money, Transaction, Holding, Balance, Snapshot)
  decision/      habits.py (habit_vector) · backtest.py · scenarios.py · scoring.py · explain.py
  api/           app.py · envelope.py · routes/
  settings.py    pydantic-settings, env vars only
data/mock/       personas/*.json · returns_monthly.csv (synthetic, labelled)
tests/unit/ · tests/integration/
docs/            PLAN.md · architecture.md · openapi.json (exported)
```

---

## 3. Adapter interface (step 1)

One interface for every source. Each adapter declares which capabilities it has. The mock implements all of them, so the demo runs fully offline.

```python
class Capability(StrEnum):
    BALANCES = "balances"; TRANSACTIONS = "transactions"; HOLDINGS = "holdings"

class FinanceAdapter(Protocol):
    name: str
    capabilities: frozenset[Capability]
    async def get_balances(self) -> list[Balance]: ...
    async def get_transactions(self, since: date) -> list[Transaction]: ...
    async def get_holdings(self) -> list[Holding]: ...
    async def health(self) -> SourceHealth: ...
```

- Calling a method the adapter doesn't support raises `UnsupportedCapability`. The aggregator checks `capabilities` first, so in practice this never happens.
- Failures raise `SourceError(code, message, retryable: bool)`. Codes: `timeout`, `auth`, `rate_limited`, `bad_data`, `unavailable`.
- Async lets the aggregator fetch both sources concurrently with a timeout per source.

**Domain models:**
- Money is held as **integer pence** plus a currency (GBP only for now). Never floats.
- `Transaction(id, ts, amount_pence (negative = outflow), merchant, category, is_transfer)`
- `Holding(instrument_id, name, quantity, value_pence, asset_class, region?)`
- `Balance(account_id, kind: current|pot|isa_cash, value_pence)`
- `Snapshot(balances, transactions, holdings, sources: dict[name, SourceStatus], as_of)`

**Aggregator (handles slow or bad data):**
- `asyncio.wait_for` per source, with a configurable timeout.
- Bounded retry with backoff, only for `retryable` errors.
- Records that fail validation are dropped and counted in `SourceStatus.dropped`. One bad record doesn't fail the whole fetch.
- The last good snapshot is cached on disk under `data/cache/` (gitignored). If a source fails, the cached data is served with `stale: true` and its `as_of`.
- When one source fails, we return a partial snapshot and show the source status in the UI. We don't return a hard error.
- Each source is selected by env var: `MONZO_MODE=mock|live`, `T212_MODE=mock|live`.

## 4. Mock adapter (step 2)

- Built from deterministic, seeded **personas** in `data/mock/personas/`, e.g. `steady_saver`, `subscription_creep`, `volatile_spender`, `concentrated_isa`. Each produces 12+ months of transactions, current-account and pot balances, and ISA holdings.
- The personas double as test fixtures and as fake friends in the friends demo.
- Fault injection via env or constructor: `latency_ms`, `fail_rate`, and `corrupt_rate` (malformed records). This lets us demo and test the slow and bad-data handling.

## 5. `habit_vector()` (step 3)

`habit_vector(snapshot, window_months=6, as_of=None) -> HabitVector`

**This is the only object that leaves the device.** It holds ratios and scores only, never £ amounts, balances, merchants or transaction details. A unit test enforces this by checking the schema has no money fields and that serialised output contains no values from the input amounts.

| Factor | Raw definition (draft) | Unit |
|---|---|---|
| `savings_rate` | (income − spend) / income over the window. Income = inbound non-transfer credits. Spend = outbound non-transfer debits | ratio |
| `runway_months` | liquid cash (current + pots + ISA cash) / mean monthly spend | months |
| `spend_stability` | 1 − coefficient of variation of monthly spend, clamped to [0, 1] | 0–1 |
| `discretionary_share` | discretionary spend / total spend, via a category map (eating out, entertainment, shopping, holidays = discretionary) | ratio |
| `subscription_creep` | change in monthly recurring-merchant spend, last 3 months vs prior 3 months. Recurring = same merchant, roughly monthly cadence, amount within ±10% | ratio Δ |
| `isa_diversification` | Herfindahl–Hirschman index of ISA holding weights. We also report effective N = 1/HHI | 0–1 |
| `shock_resilience` | months of spend covered if income stops **and** the ISA takes the worst drawdown in the replay set: (liquid cash + ISA × (1 − worst drawdown)) / mean monthly spend | months |

Output shape:

```json
{
  "version": "hv-1",
  "window": {"months": 6, "end": "2026-09-30"},
  "factors": {
    "savings_rate": {"raw": 0.18, "score": 72},
    "runway_months": {"raw": 3.4, "score": 57}
  }
}
```

- `score` is a 0–100 mapping from fixed, documented bands. It doesn't depend on any population data, so it can be computed on-device.
- `version` is there so Ash's twin matching and the friends server can reject vectors they don't understand.
- Edge cases each have a test: zero income, zero spend, fewer than `window_months` of data (returns `null` plus a reason), an empty ISA.

## 6. Minimal backtest (step 4)

`backtest(contributions, weights, returns, rebalance, period) -> BacktestResult`. A pure numpy function on a monthly step.

- **Inputs**
  - Monthly contribution series derived from the persona's habits. Locally this is in pence. It is capped at the ISA allowance per tax year (6 Apr to 5 Apr). The allowance is a config value, defaulting to £20,000.
  - Allocation weights over asset proxies (e.g. global equity, UK equity, gilts, cash).
  - Rebalance rule: `none | annual | threshold(5pp)`.
  - Technique: `dca` or `lump_sum` (put the same total in at the start).
- **Returns data**
  - For step 4 we use a **synthetic** monthly return CSV, clearly labelled, with stylised shock windows for GFC 2007–09, COVID Feb–Mar 2020 and the 2022 rates/inflation drawdown (equities and bonds both down).
  - Real index series come later, either from Ash's engine or a licensed public source. See §9.
- **Outputs**
  - Time-weighted return index rebased to **100** at the start. This is TWR because raw value is inflated by contributions, so it isn't comparable between people.
  - CAGR, volatility, max drawdown, months to recover, and worst 12 months.
  - Money-weighted return and £ values are **local only**.
- **Tests**
  - 0% returns: final value equals the sum of contributions.
  - Constant r: matches the closed-form future value of an annuity.
  - The ISA cap is enforced across a tax-year boundary.
  - Weights still sum to 1 after rebalancing.
  - A known drawdown in the synthetic series gives the expected max drawdown.

## 7. Later steps (outline)

- **API**
  - Endpoints: `GET /v1/health`, `/v1/dashboard`, `/v1/habit-vector`, `POST /v1/backtest`, `POST /v1/scenarios`, `GET /v1/friends/leaderboard`, `PUT /v1/friends/share`.
  - Every response uses one envelope: `{"data": ..., "error": null, "meta": {"request_id", "as_of", "sources": {...}, "stale": false}}`.
  - Errors use the same envelope: `{"data": null, "error": {"code", "message", "details"}, "meta": {...}}`.
  - The spec is exported to `docs/openapi.json`.
- **Future insight**
  - Find past windows whose starting conditions are close to today's (e.g. trailing 12-month return, volatility, rate regime, using whatever features Ash's engine exposes). Run the user's strategy forward from each match and show a fan of outcomes.
  - The fixed label reads: *"Modelled scenarios from similar past periods. Not a forecast. Not financial advice."*
- **Explainer (AI)**
  - Receives the structured result JSON only and returns plain-English text. It cannot change numbers.
  - A template fallback is used when no API key is set.
  - Output is checked so that every number in the text appears in the input JSON.
- **Friends**
  - Shares only the habit vector scores, the rebased TWR index, and an *opt-in* pie of percentages by asset class.
  - Never shares salary, balances or holdings in £.

## 8. Engineering checklist (from the brief)

- [ ] ≥2 data sources (Monzo + Trading212), each behind an adapter with a mock
- [ ] API-first: OpenAPI spec, one response format including errors
- [ ] 3 layers: experience, decision, data integration
- [ ] Unit tests plus ≥1 integration test (API → aggregator → mock adapters)
- [ ] Linted and modular: ruff (lint + format) in CI or a pre-commit hook
- [ ] README
- [ ] Handles slow or bad data: timeouts, retries, partial results, stale cache, record validation
- [ ] No secrets in code: env vars, `.env.example`, `.env` gitignored
- [ ] Runs from one command: `make run`, mock mode by default
- [ ] Architecture diagram with trade-offs
- [ ] AI only explains, and AI use is declared honestly in the README

## 9. Open questions

**I won't assume any of these. They need answers before step 7.**

Trading212 API:
1. Does the API key we have access the **Stocks & Shares ISA** account, or only Invest? Do we need one key per account?
2. Which endpoints do we plan to use (portfolio/positions, account cash, pies, order/dividend history)? Can the key be scoped read-only?
3. What rate limits apply to each endpoint, and what does a rate-limited response look like?
4. Demo or live environment for the hackathon? What does each base URL return?
5. Is instrument metadata (asset class, region) available, or do we map tickers ourselves?

Monzo API:
6. Playground token or a full OAuth 2.0 client for the demo? How long does a playground token last, and do we need refresh?
7. Are there limits on how far back transactions can be fetched, or a time window after authorisation?
8. Rate limits and pagination behaviour for the transactions endpoint?
9. Are pots and their balances accessible with our scopes?

Team and scope:
10. **Stack**: is Python + FastAPI for the API and decision layer OK with the team? What is the frontend stack, and who owns it?
11. **Historical returns**: does Ash's engine provide the monthly return series and the definitions of the 2008, COVID and 2022 windows, or do I source them? If I source them, which data can we legally use?
12. **Contract with Ash**: does twin matching consume `habit_vector`? If so, we should agree the `hv-1` schema now.
13. **What leaves the device**: the brief says `habit_vector` is the only thing that does. Friends also need the rebased TWR index and the opt-in pie percentages. Do we count those as allowed derived outputs, or fold them into the vector?
14. **Friends backend**: who hosts it, and how are friends paired? Invite code is the simplest option.
15. **Bands for the 0–100 scores**: are fixed bands acceptable, or do we want them calibrated on Ash's synthetic population? Calibrating there would still be computed on-device from shipped percentiles.
