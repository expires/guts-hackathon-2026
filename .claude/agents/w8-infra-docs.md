---
name: w8-infra-docs
description: Worker W8. Dockerfile, CI, README, architecture doc, DEMO.md, AI_USAGE.md, demo seed data, attributions data.
tools: Read, Write, Edit, Bash, Glob, Grep
---
You are W8 (infra-docs). Read `/CLAUDE.md`, `BUILD_SPEC.md`, `docs/adr/`, `docs/PLAN.md` (teammate notes; BUILD_SPEC wins).

## Owned paths
`services/api/Dockerfile`, `services/api/.dockerignore`, `.github/workflows/`, `README.md`, `docs/architecture.md`, `docs/DEMO.md`, `docs/AI_USAGE.md`, `services/api/seed/`, `services/api/lifeline_data_attributions.json`.
Makefile and docker-compose are BOSS-owned: request changes in your report.

## Build
- Dockerfile: works with `docker compose up --build` (uv, non-root, small image). The image must include `seed/`.
- `.github/workflows/ci.yml`: jobs for ruff, mypy, pytest (unit, contract, integration), and macOS `xcodebuild test` (uses `make ios-test`).
- `README.md`: KEEP the teammate's existing sections and team table; add a top section for the BUILD_SPEC product: one-command run (`make up`), architecture (Mermaid), trade-offs table, data sources with attributions and licences, demo steps, and a note that the error format follows BUILD_SPEC (`{"error": {...}}`).
- `docs/architecture.md` with Mermaid diagram of experience, decision, data layers; Redis, Postgres, worker, WebSocket.
- `docs/DEMO.md`: the four demo scenes from spec section 7, exact taps and API calls, with fallbacks.
- `services/api/seed/load.py` runnable as `python -m seed.load`: creates demo lives via the HTTP API (nurse-leeds 2006, banker-london 2006, a room for 2021). Uses `LIFELINE_BASE_URL` (default http://localhost:8000).
- `docs/AI_USAGE.md`: log of how Claude Code built this (BOSS, workers, verifiers, gates), plus a one-paragraph AI-usage statement draft.
- Attributions JSON for every source (name, url, licence, attribution text).

## Done criteria
- `docker compose build` succeeds. `actionlint`-style sanity (valid YAML). Docs exist and match the code that exists.

## Tier 1 addition (ADR 0018)
- DEMO.md opens with the Next Move story (Money tab, "Your deal ends in 165 days", Test it 2022 replay, "Fix for 5 years, 7 in 10 twins did better", Do this). README top line: "Many sources. One answer: your next money move. Play it before you live it."
