# ADR 0038: No-data is a normal state; Money home in one request; quiet rate limits

- Status: accepted
- Date: 2026-10-17
- Requested by: the user (phone review, Money tab with no data)

## Decision
- **Onboarding gate:** a signed-in user with no connected or entered data (`GET /v1/me` → `has_finance_data: false`) always goes to onboarding ("Connect your money") first, never to an empty Money tab.
- **Empty state, not an error:** `GET /v1/finance/home` returns 200 with `has_data: false` and `connect_prompt`.
  - Money home shows exactly one card, "Connect your money to see your next move", with a primary button "Connect your money" that opens onboarding at the connect step (Monzo, Trading212, statement upload, enter your numbers).
  - No "Try again". No mention of Life or Play yourself.
  - Guess my spend, Coming up and the tiles are hidden until data exists. At most one empty state per screen.
- **One request:** `GET /v1/finance/home` returns everything Money home needs (balance, net worth, next move, prediction, up to 3 coming-up bills). The client also de-duplicates in-flight GETs and caches GET responses for about 20 s.
- **Rate limits:**
  - The per-user budget for reads is raised (about 300 a minute). Writes keep the current limit, and chat stays at 6 a minute.
  - The client retries 429 quietly with backoff, honouring `Retry-After`. It then shows "Couldn't load. Pull to refresh.", never "Too many requests".
- **"Try again"** appears only for real network or server errors.
- **The You tab** has a permanent "Connect your money" entry with its current state.
