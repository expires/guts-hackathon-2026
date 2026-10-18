# V3 final: resilience spot checks

- Date: 2026-10-18, 09:36-09:40
- Target: `main` d8ac49a7, local stack `http://localhost:8000`. No chat calls.
- Verdict: **PASS** (no failures)

## Tree note

- Local `main` points at cfff461e. d8ac49a7 is on `origin/main`, 16 commits ahead.
- The working tree has 610 uncommitted changes. The tests ran on that working tree, not on a clean d8ac49a7 checkout.
- The stack version on port 8000 was not checked against d8ac49a7.

## 1. Forecast routes (local stack, new demo account each run)

| Check | Request | Result |
|---|---|---|
| No data | `GET /v1/forecast` | 409 `no_finance_data`, source `data`. PASS |
| Bad buffer | `GET /v1/forecast?buffer_pct=7` | 422 `validation_error` "buffer_pct: pick 0, 5, 10, 15 or 20". PASS |
| Bad stress | `GET /v1/forecast?stress=2008` | 422 `validation_error` "stress: only 2022 is available". PASS |
| Import | `POST /v1/samples/scholarship/import` | `status: done`, 128 transactions. PASS |
| After import | `GET /v1/forecast` | 200, `meta.label` "Sample data", `state: on_track`. PASS |
| After import | `GET /v1/forecast?stress=2022&buffer_pct=10` | 200. PASS |

## 2. Tests (from `services/api`)

- `uv run pytest -q tests/integration -k "stale or keepalive or room or forecast"`: 36 passed, 0 failed (36 dots, no F or E). One `PytestCollectionWarning` for `TestPeriod` in `lifeline_contracts/next_move.py:64`. The project pytest config hides the summary line.
- `uv run pytest -q tests/unit/api/test_chat_keepalive.py`: 1 passed, 0 failed.

## 3. Quick Life, 2 accounts, WebSocket on local stack

Script: scratch file outside the repo. It uses the protocol from `tests/integration/test_rooms_ws.py::test_quick_life_join_counts_as_ready`.

1. Two demo accounts sign in. Host creates a `duel` room.
2. Both join (`welcome` to each).
3. Host sends `pick_game` `same_life` with `{"quick": true, "path_id": "apprentice"}`. Result: `game_picked`.
4. Host sends `start`. The guest never sends `ready`.
5. Result: host gets `started` (status `playing`). Guest gets `started` (status `playing`). PASS

Observation (not a failure): `POST /v1/auth/demo` returned 429 five times in a row before it succeeded. Other verifiers share the same rate-limit bucket. The limiter works as designed.

## Not run

- Source kill tests (timeout, 500, garbage, empty body) from the V3 agent brief: NOT RUN (out of scope for this final pass).
- Stop redis or postgres: NOT RUN (the brief says do not stop the local stack).

## Failures

None.
