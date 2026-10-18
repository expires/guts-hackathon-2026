# V1 final: contract check

- Date: 2026-10-18, 09:36-09:40
- Verifier: V1 (read-only)
- Target: `main` d8ac49a7 (requested). Local checkout HEAD is cfff461e with uncommitted changes. d8ac49a7 exists but is not on a local branch. Tests ran on the local working tree. The docker stack ran whatever image was up at http://localhost:8000.
- Verdict: **PASS**

## Checks

| # | Check | Command | Result |
|---|---|---|---|
| 1 | Contract tests against the live stack | `make test-stack` | PASS. 96 tests, all `.`, exit 0. pytest printed no summary line (quiet config). |
| 2 | Contract tests in process | `cd services/api && uv run pytest -q tests/contract` | PASS. 96 tests, all `.`, exit 0. |
| 3a | Demo sign-in | `POST /v1/auth/demo` (fresh device_id) | 200, body valid against `Token` |
| 3b | Forecast with no data | `GET /v1/forecast` before import | 409, valid `Error`, code `no_finance_data`, source `data` |
| 3c | Sample import | `POST /v1/samples/working/import` | 201, valid `ImportResult` |
| 3d | Forecast | `GET /v1/forecast` | 200, valid `Forecast` |
| 3e | Category detail | `GET /v1/finance/spending/groceries` | 200, valid `CategoryDetail` |
| 3f | Learn path | `GET /v1/learn` | 200, valid `LearnPath` |
| 3g | Unknown category | `GET /v1/finance/spending/not-a-category` | 404, valid `Error`, code `not_found`, source `api` |

Schema validation: jsonschema Draft 2020-12 against `contracts/openapi.yaml` components (OpenAPI 3.1). `ErrorBody` requires `code`, `message`, `source`. Both error bodies passed.

## NOT RUN

- Probes for unknown route, wrong method, bad JSON, oversized body, invalid path params.
- Per-operationId contract test coverage audit.

## Failures

None.
