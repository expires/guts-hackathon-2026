# ADR 0027: No mock data in the Live configuration; disabled sources

- Status: accepted
- Date: 2026-10-17
- Requested by: the user (replaces the earlier mock-fallback rule for Live)

## Decision
- Two data modes, set by env `DATA_MODE`:
  - `live`: the default on Railway and in the iOS Live and Demo configurations.
  - `demo`: local dev, tests, and the iOS Mock configuration (Playground).
- In `live` mode:
  - A source with no live or cached real data is **disabled**. `/v1/sources` reports `status: "unavailable"` with a reason. The built-in mock fallback is not used.
  - The annual `MacroTable` holds only real values (live or cached). Years or regions without data are absent. Lookups that hit a gap raise "unavailable"; they never fall back to mock.
  - Sim events whose inputs come from a disabled source, or from a key with no real value for that year and place, do not fire.
  - The finance fixture personas are not served. A user's Money data comes only from their own input: statement upload or manual entry (Tier 2 onboarding). Until then, `/v1/finance/*` and `/v1/next-move` return `409` with code `no_finance_data` and the message "Connect your money first."
  - Life characters from the synthetic population stay allowed, labelled "Simulated from ONS and Nomis data".
- The `Status` literal gains `unavailable` (contract change). The UI shows "Unavailable" for it.
- `demo` mode keeps fixtures and labelled mock data for development, tests, Playground and the recorded Mock build.

## Disabled sources (live mode)
| Source | Reason |
|---|---|
| Adzuna | No key. Disabled by the user |
| DVLA | Registrations closed; no key. Disabled by the user |
| DVSA MOT | Needs an approval that takes days. Disabled by the user |
| TrueLayer (Open Banking) provider only | The sandbox offers test banks only, so it cannot give real data. Disabled by the user. `/v1/bank/*` itself is **not** disabled: it is Yaffy's live Monzo OAuth flow. Only `provider=truelayer` answers 409 `source_disabled` |
| EPC | Key set, but the live fetch times out. Disabled if not live by 17:19 on 2026-10-17 (20 minutes after the rule was set) (decision recorded below) |
| Yahoo, FRED | Blocked or timing out from our network. Disabled while unavailable; they return automatically when live |

Companies House, DWP Stat-Xplore and EPC are live.

## EPC outcome
Live before the 17:19 deadline. The endpoint, bearer auth and query were correct (HTTP 200). Whole-council counts take 7 to 11 s (Westminster 11.1 s), which exceeded the 8 s default timeout on every retry. Fix: a per-source timeout of 30 s for EPC, 4 regions at a time, and a failed region is skipped. Result: 16 live sources.

## Implementation notes (W1)
- `DATA_MODE` defaults to `demo`. Railway sets `DATA_MODE=live`.
- Bank holidays: if gov.uk cannot be reached, the recorded gov.uk copy (real data, saved 2026-10-17) is served as `cached`, never `mock`.
- Live-mode MacroKeys with **no** real data: `gilt_10y` (FRED unavailable), `stock_return` (Yahoo unavailable), `burglary_rate` and `flood_risk` (the sources publish counts, not rates). Events that need them do not fire.
- In live mode `lookup_postcode` returns nothing on failure (no postcode-area guess), and `daily_weather` returns only real days.

## Correction (2026-10-17): bank routes
- `/v1/bank/auth-link`, `/v1/bank/callback` and `/v1/bank/summary` are Yaffy's live **Monzo** OAuth routes (from the `integration` branch, merged per ADR 0036). They work in live mode when Monzo OAuth is configured.
- `GET /v1/bank/auth-link?provider=truelayer` answers 409 `source_disabled`. `provider` defaults to `monzo`.
- In live mode, if Monzo OAuth is not configured, the routes answer 409 `source_unavailable`. They never return a mock link (the mock link stays in demo mode only).
