# ADR 0021: Tier 1 data choices (W1)

- Status: accepted
- Date: 2026-10-17

## Decision
- Finance fixtures: 4 labelled personas, 12 months to a fixed "today" of 2026-10-17 (keeps "deal ends in 165 days" true). Device `demo-presenter-01` maps to `homeowner-leeds`. Other subjects map by stable hash. `persona:<id>` selects one directly.
- Fixture price rises stay under 10% so the subscription rule (amount within 10%) still matches them.
- Fixture daily spend follows weekday, payday, bank holidays, weather, December and January, so the spend model (ADR 0017) has signal. Fixture weather is mock, so live weather will not line up with fixture history.
- Rents: ONS PIPR from 2016 (IPHRP before). Each value keeps its own series id.
- Police and Environment Agency publish counts, not rates. They feed event facts (`burglary-1mile`, `flood-warnings`). `BURGLARY_RATE` and `FLOOD_RISK` stay labelled mock.
- `ENERGY_TARIFF`: mean of Octopus Flexible dual-fuel quotes across regions, plus regional values.
- Stock return: FTSE All-Share price index (no dividends). Crypto: current year only (CoinGecko free tier).
- Weather: one point per region (main city).
- Yahoo returns 429 and FRED times out from this network: both mock with hand-made sample fixtures, labelled.
- XML from ONS xlsx is parsed with `defusedxml`.
