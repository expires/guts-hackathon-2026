# ADR 0029: Tier 2 scope from the user's away plan

- Status: accepted (replaces the BUILD_SPEC Tier 2 list)
- Date: 2026-10-17

## Scope, in order (after the Tier 1 gate, V4)
1. **Onboarding:**
   - Welcome (3 screens).
   - Sign in with Apple.
   - "Connect your money": Monzo, Trading212, statement upload (Monzo and Revolut CSV first, then PDF), or manual entry (postcode, rent or own plus mortgage and deal end, take-home pay, regular costs, savings).
   - "Importing your history" with progress stages.
   - Next Move reveal.
   - 3 tips: the top personal facts.
   - The Monzo and Trading212 buttons call `/v1/bank` and `/v1/connections` (Yaffy's area) and show "Unavailable" until his branch is merged.
2. **Accounts:**
   - Per-user data in Postgres: `GET /v1/me`.
   - Sign out: `POST /v1/auth/logout` revokes the token.
   - Delete account: `DELETE /v1/me` removes every record.
   - Demo reset: `POST /v1/me/reset`.
3. **Same Life PvP on Railway:**
   - Room code, QR and the deep link `lifeline://join/CODE`.
   - Lobby with a ready state (`Player.ready`).
   - The server owns the seed and the state.
   - Live rival strip over WebSocket.
   - Reconnect after sleep: the server sends `welcome` with the player id; the client re-joins with `player_id`.
   - End-of-life comparison.
   - Tested with 4 simulated clients.
4. **On-device connectors:**
   - Location fills the postcode (`GET /v1/postcodes/reverse`, postcodes.io).
   - HealthKit steps and sleep (`PUT /v1/me/health`) add a bounded effect (-10 to +10) to the Life Health stat at the next AGE.
   - App Intent "Log a payment" (`POST /v1/finance/transactions`) for a Shortcuts Wallet-tap automation, with setup steps in the app.
5. **Presentation mode:** a client-side toggle that rounds or hides exact amounts on every screen.
6. **Cut:** the widget. StoreKit demo store only if everything else is green.

## Notes
- Statement upload is multipart, max 5 MB, and exempt from the 64 KB JSON body limit. Parsing is deterministic code (no LLM). Imported transactions feed the same `lifeline_engine.money` pipeline as fixtures, so the Next Move works on real user data in live mode.
- Bank tokens, when they exist (Yaffy's connections), are stored encrypted in Postgres with `TOKEN_ENCRYPTION_KEY` (ADR 0028).
- In live mode (ADR 0027), a user with no statement and no manual entry gets 409 `no_finance_data`. Onboarding is the way in.
