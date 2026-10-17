# ADR 0044: Same Life room rules

Date: 2026-10-17. Status: accepted. Source: W9 report.

## Decision

- The host counts as ready.
- Start needs at least 2 ready players.
- `ready` is one-way. The contract has no un-ready message.
- A player can see results after their own finish while others still play. Others' rows update live.
- Reconnect: on stream end (with backoff) and when the app becomes active, the client re-joins with its `player_id` and resends its last progress or finish.
- Mock mode uses W9's timed mock server (3 rivals; 1 in a duel). Mock rivals finish after 10 years.
- Other players' lives (ribbons, split points): a room member may read a life started with that room's code. Everyone else gets 404 (W4). Until that lands, results say "Other players' choices are not available yet."
