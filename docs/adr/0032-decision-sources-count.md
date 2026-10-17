# ADR 0032: "Based on N sources" counts decision sources only

- Status: accepted
- Date: 2026-10-17

## Decision
- `NextMoveResponse.decision_sources` and `decision_source_count` list only sources that are inputs to the decision:
  - the user's own data
  - BoE, ONS, Nomis, Land Registry
  - Companies House, Octopus
  - FX (Frankfurter), CoinGecko
- Game-only sources (Police, Environment Agency, Carbon Intensity, Open-Meteo, EPC, Stat-Xplore when used only in the Life game) and context sources (Guardian, MPC dates) are not counted.
- A source counts only when the engine actually read it for this move. Status comes from `/v1/sources` (live, cached, unavailable). An unavailable source is listed but not counted.
- "Why?" lists them with their status.
