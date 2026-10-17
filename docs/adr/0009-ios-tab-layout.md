# ADR 0009: iOS tab layout and client conventions

- Status: superseded by ADR 0016 for the tab layout (other client conventions still apply)
- Date: 2026-10-17

## Context
The spec lists five action tabs (Job, Assets, Relationships, Activities, Money) plus the Life screen. iPhone shows at most 5 tabs; a sixth goes under "More".

## Decision
- System `TabView` with 5 tabs: Life, Job, Assets, People (Relationships), Money.
- Activities opens as a sheet from a glass button on the Life screen. Its actions are still the `available_actions` with `tab = activities`.
- An open event sheet sits above all tabs, so it shows on any tab.
- Random mode: the app sends `mode=random` with `seed` taken from the random character id (`random-{seed}`). The API calls `lifeline_engine.api.random_character(seed, macro)`, so `GET /v1/characters?seed=N` and `POST /v1/lives {mode: random, seed: N}` give the same person.
- iOS client: errors are mapped in middleware to plain-English `APIError`. The demo token is held in memory; the device id (anonymous UUID) is in UserDefaults.
- Money shows in GBP, UK format, whole pounds, on every device locale.
