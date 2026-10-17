# ADR 0004: Who owns Makefile, docker-compose and Dockerfile

- Status: accepted
- Date: 2026-10-17

## Context
Spec 6A says BOSS alone edits Makefile and docker-compose. Spec 6B gives W8 "Docker, Makefile, CI".

## Decision
BOSS owns `Makefile`, `docker-compose.yml`, `.env.example`, `services/api/pyproject.toml`, `apps/ios/project.yml`. W8 owns `services/api/Dockerfile`, `.github/workflows/`, README, docs and seed data. W8 requests Makefile changes in its report.
