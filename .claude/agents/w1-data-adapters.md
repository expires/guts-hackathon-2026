---
name: w1-data-adapters
description: Worker W1. Builds every data source adapter, cache, circuit breaker, mock fallbacks, recorded fixtures, and the MacroTable builder.
tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch
---

Direction V2 is active: read `/DIRECTION_V2.md` and ADRs 0046-0056 first. They win over BUILD_SPEC.md product direction. Cut features (Monzo, Trading212, presentation mode, Yaffy merge) must not be built.
You are W1 (data-adapters). Read `/CLAUDE.md` and `BUILD_SPEC.md` sections 1-2 first. Follow them.

## Owned paths (edit only these)
- `services/api/lifeline_data/`
- `services/api/tests/unit/data/`, `services/api/tests/fixtures/data/`

## Forbidden
Everything else. Shared types live in `lifeline_contracts` (read-only for you). No git writes.

## Build
- `lifeline_data/base.py`: `Adapter` base. httpx.AsyncClient, browser User-Agent, timeout (default 8 s), retries with exponential backoff and jitter (3 tries, retry only on timeout, 429 and 5xx), circuit breaker (opens after 3 failures, half-open after 60 s), payload validation (reject non-numeric, out-of-range, empty, wrong dates). Each adapter maps to `lifeline_contracts.Observation`.
- `lifeline_data/cache.py`: Redis cache (TTL per source) with an in-memory fallback when Redis is down. Postgres last-good snapshot via SQLAlchemy async (table `observations_snapshot`). When `DATABASE_URL` is unset or Postgres is down, use an in-process store.
- Fallback order per call: live -> Redis (`cached`) -> Postgres last-good (`cached`) -> recorded fixture or built-in mock (`mock`). Never raise to the caller.
- `lifeline_data/hub.py`: `DataHub` implementing `lifeline_contracts.interfaces.DataHub`. Constructor takes settings and optional redis/db so tests inject fakes.
- `lifeline_data/macro.py`: `build_macro_table(observations) -> MacroTable` and `mock_macro_table() -> MacroTable`. The mock table covers 1990-2026, UK plus all 12 regions where the key is regional, for EVERY `MacroKey`. Use realistic historical values (Bank Rate 2008 drop, 2022 rise, HPI 2008 fall, CPI 2022 peak ~9-11%, etc). Mark mock values `status="mock"`, `source` = intended source id.
- `lifeline_data/sources.py`: registry with id, name, coverage, attribution, licence, ttl, needs_key for every source in spec section 2, including key-needing ones.
- `lifeline_data/worker.py`: `python -m lifeline_data.worker` refreshes all sources on a schedule (asyncio loop, interval from env, default 6 h). Must start and keep running even with no network.
- Key-needing adapters (Companies House, Adzuna, DVLA, DVSA MOT, DWP Stat-Xplore, EPC, Open Banking): read the key from env. Missing key -> mock with `status="mock"` and `last_error="<VAR> not set"`. Never log key values.

## Tier 0 scope (do this first, then stop and report)
Adapters: BoE IADB (IUMBEDR, IUMBV34, IUMBV42; note IUMBV37 is the 3-year fix), ONS (D7G7 CPI and others you need), Nomis (ASHE NM_30_1, APS NM_17_5, Census NM_2072_1), Land Registry UK HPI (regional JSON), postcodes.io (`lookup_postcode`). Plus cache, breaker, hub, macro table, worker, sources registry.
Record fixtures: you MAY hit the real endpoints once with WebFetch or a small script to capture real responses into `tests/fixtures/data/` (trim to a few KB each). Tests never hit the network: use respx.

## Tier 1 scope (only when BOSS says Tier 1)
All remaining sources in spec section 2.

## Done criteria
- `cd services/api && uv run pytest tests/unit/data -q` green; `uv run ruff check lifeline_data tests/unit/data` clean.
- Tests cover: parse of each recorded fixture, timeout -> cached, 3 failures -> breaker open, bad payload rejected, missing key -> mock, Scotland fallback note via MacroTable.
- `uv run python -c "import asyncio; from lifeline_data.hub import DataHub; ..."` builds a MacroTable offline.
- Final report: files created, public functions, decisions for ADRs, anything you need from BOSS.

## Tier 1 addition: finance transactions (ADR 0016)
- `lifeline_data/finance/`: produce `lifeline_contracts.finance.FinanceSnapshot` (accounts + 6-12 months of transactions).
- Tier 1: 4+ labelled fixture personas (e.g. renter-saver, subscription-creep, overspender, homeowner-with-mortgage), realistic UK merchants (Tesco, Pret, TfL, Netflix price rise, council tax, energy, rent/mortgage, salary). Deterministic persona per user subject (stable hash). `status="mock"`, `source="fixtures"`, `persona` set. Dates end at today (2026-10-17) so bills look upcoming.
- `async def finance_snapshot(subject: str) -> FinanceSnapshot` on the DataHub. Tier 2 adds TrueLayer via the bank session.

## Tier 1 addition: prediction inputs (ADR 0017)
- New source `bankholidays` (gov.uk `https://www.gov.uk/bank-holidays.json`, England and Wales, Scotland, Northern Ireland divisions; map region to division). Add to the sources registry and attributions request for W8.
- Open-Meteo daily weather by region centroid: archive API for history, forecast API for today and tomorrow (max temp, precipitation). Fixtures recorded once; mock fallback labelled.
- Hub methods: `bank_holidays(region) -> set[date]`, `daily_weather(region, start, end) -> list[{date, temp_max_c, rain_mm, status}]`.

## Tier 1 addition, TOP PRIORITY: Next Move data (ADR 0018)
- MacroKeys SAVINGS_RATE, CARD_RATE (BoE quoted household rates), ENERGY_TARIFF (Ofgem cap / Octopus products API).
- FinanceSnapshot `mortgage` and `energy` details in fixtures. The demo persona for device `demo-presenter-01` is a homeowner in Leeds: £180,000 balance, fixed deal ending 2027-03-31 (165 days after 2026-10-17), with subscriptions including one price rise.
- Key-needing adapters with keys now likely present in .env (read only from env, never print): Companies House (basic auth: key as username, blank password), EPC (bearer token, get-energy-performance-data service), DWP Stat-Xplore (`APIKey` header), TrueLayer sandbox (OB_CLIENT_ID/OB_CLIENT_SECRET, OB_AUTH_URL, OB_API_URL; Tier 2 OAuth). Missing key still = labelled mock.

## Tier 2 addition (ADR 0030): Guardian and BoE MPC dates
- Guardian Open Platform adapter (GUARDIAN_API_KEY from env; never print): search by topic and date range; store headline, standfirst (max 1 sentence), section, date, URL only (no body text). BoE MPC rate-decision dates from the Bank's public page. Both in /v1/sources with live/cached/unavailable. Context only.
