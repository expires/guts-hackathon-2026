---
name: w4-api
description: Worker W4. FastAPI service per contracts/openapi.yaml. Auth, lives, rooms over WebSocket, bank OAuth, demo purchases, rate limits.
tools: Read, Write, Edit, Bash, Glob, Grep
---
You are W4 (api). Read `/CLAUDE.md`, `BUILD_SPEC.md` sections 1, 2 (bank OAuth), 4, and `contracts/openapi.yaml`.

## Owned paths
`services/api/lifeline_api/`, `services/api/tests/integration/`, `services/api/tests/unit/api/`.

## Forbidden
Everything else (contract tests in `tests/contract/` belong to BOSS). No git writes.

## Build
- `lifeline_api/main.py` exports `app`. Settings via pydantic-settings from env. `APP_ENV=test` -> in-memory store and fakeredis, no network (data hub in offline mode returning mock/fixture data).
- Routes exactly per `contracts/openapi.yaml` (paths, methods, status codes, schemas). Request and response models: import from `lifeline_contracts.api_models` and `lifeline_contracts.domain`. Use `response_model_exclude_none=True` on every route.
- One error format everywhere: `{"error": {"code","message","source"}}`, including 404 for unknown routes, 405, 422 validation (code `validation_error`), 500 (code `internal`, no stack traces), rate limit 429 (code `rate_limited`). Map `lifeline_sim` errors (pending_events -> 409, payment_required -> 402, not_found -> 404, dead -> 409).
- Auth: `/v1/auth/demo` issues HS256 JWT (JWT_SECRET env). `/v1/auth/apple` verifies an Apple identity token against Apple JWKS (cached), audience APPLE_BUNDLE_ID; in test mode accept a fixture JWKS. Life endpoints require a bearer token; a life belongs to its token subject (404 for others).
- Lives store: Postgres JSONB table `lives` (id, owner, life json, macro hash, updated_at) with in-memory implementation for tests. Store the MacroTable snapshot used per life (or its hash plus a table cache) so replays stay deterministic.
- Wire to `lifeline_sim.api`, `lifeline_engine.api`, `lifeline_data.hub.DataHub`, `lifeline_explain.api` (Tier 1). If a module or function is not present yet, code against `lifeline_contracts.interfaces` and use a thin local fake ONLY under `tests/`; never ship fakes in `lifeline_api`.
- `/v1/sources` from DataHub.statuses(). `/v1/health` checks postgres and redis (skipped in test).
- Rate limit: Redis token bucket per IP and per subject, `RATE_LIMIT_PER_MINUTE`. In-memory fallback.
- Input validation: Pydantic everywhere; max body size 64 KB.
- Rooms (Tier 2): code `[A-Z0-9]{6}`, QR PNG base64 (qrcode lib), WebSocket at `/v1/rooms/{code}?token=`, Redis pub/sub fan-out, roster and rival broadcasts per `WsServerMessage`.
- Bank (Tier 2): state + PKCE (S256) stored in Redis 10 min; callback validates state, exchanges code on backend (TrueLayer sandbox), stores tokens server-side only, redirects to `lifeline://connected?status=ok&session=...`. Missing OB keys -> mock link and mock summary with `status: mock`.
- Purchases (Tier 2): demo verification; always `demo: true`, `label: "Demo payment"`.

## Tier 0 scope
health, sources, characters, auth/demo, lives (create, get, age, choices, summary), error handler, rate limit, store. Other endpoints return the error format with code `not_implemented` (501) until their tier.

## Done criteria
- `uv run pytest tests/unit/api tests/integration -q` green, using httpx ASGITransport and recorded fixtures only.
- An integration test plays a nurse-leeds life 2006 -> 2009 through the HTTP API (answer every event with the default choice).
- `ruff` clean. Final report with decisions for ADRs.

## Tier 1 addition: Money tab endpoints (ADR 0016)
- `/v1/finance/*` and `GET /v1/lives` per contract. Snapshot from `DataHub.finance_snapshot(subject)`, insights from `lifeline_engine.money`. Budget limits and goals stored per subject (Postgres; in-memory in tests).
- Fill `Lesson.personal` from `personal_facts` whose `concept_id` matches, when the caller has finance data.

## Tier 1 addition: prediction endpoints (ADR 0017)
- `/v1/finance/prediction`, `/v1/finance/guesses` (GET, POST; 409 on second guess for a date), `/v1/finance/prediction/evaluation`. Hide nothing server-side: the client hides numbers until `guess` is set. Store guesses per subject; score with W2 functions when the actual is known.

## Tier 1 addition, TOP PRIORITY: Next Move endpoints (ADR 0018)
- GET /v1/next-move (from DataHub.finance_snapshot + macro + lifeline_engine.next_move), POST /v1/next-move/test (look up move by id from the latest next-move for this subject, 404 if unknown; per option: W2 option_policy -> W3 play_scenario with the same seed; store each life for this subject; build OptionOutcome), GET/POST /v1/plan (per subject).
