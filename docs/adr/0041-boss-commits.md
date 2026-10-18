# ADR 0041: BOSS commits on main

Date: 2026-10-17. Status: accepted. Supersedes the "no git writes" rule for BOSS only.

## Decision

- BOSS may run `git add` and `git commit` on `main`.
- One commit per accepted milestone or meaningful fix. Conventional Commits style (`feat(api): ...`, `fix(ios): ...`).
- The message comes from `docs/COMMITS.md`. BOSS writes the entry first, then commits with it.
- `make secrets-scan` runs before every commit. A finding blocks the commit.
- BOSS stages explicit paths, never `git add -A`. `.env`, `Local.xcconfig` and `**/data/private/` stay ignored.
- Never push, never force, never rewrite history (no amend, rebase, reset, stash). The user pushes.
- Workers and verifiers keep the old rule: only `git status` and `git diff`.
- A milestone commit includes only work that passed its verifier. Work in progress in other paths stays uncommitted.

## Amendment (2026-10-18, user instruction)

- BOSS pushes `main` to origin after each verified commit, with a normal push (no force). All other rules stay: secret scan first, one logical change per commit, tests passing on the committed tree.
