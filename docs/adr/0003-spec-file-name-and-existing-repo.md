# ADR 0003: Spec file name and the existing team repo

- Status: accepted
- Date: 2026-10-17

## Context
- The spec arrived as `BUILD_SPEC (1).md`. The spec and CLAUDE.md refer to `BUILD_SPEC.md`.
- The user asked to pull in `github.com/expires/guts-hackathon-2026`. `origin/main` has one commit with `README.md`, `.gitignore` and `docs/PLAN.md` from a teammate (Yath). That plan covers a separate "Play yourself" web layer (Monzo, Trading212, habit vector) under `src/playyourself/`.

## Decision
- Rename the spec to `BUILD_SPEC.md`.
- Clone into a scratch folder and copy its `.git` into the workspace. No checkout, reset or merge. The user commits by hand.
- Keep `docs/PLAN.md` unchanged. Merge `.gitignore` (spec rules first, team rules appended).
- W8 extends `README.md` and keeps the teammate's sections and team table.
- Our code lives in `services/api/` and `apps/ios/`, so it does not collide with `src/playyourself/`.
- Error format: BUILD_SPEC wins (`{"error": {...}}`), not the `{data, error, meta}` envelope in the team README. W8 notes this in the README.
