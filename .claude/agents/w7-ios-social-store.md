---
name: w7-ios-social-store
description: Worker W7. iOS rooms and PvP UI, rival strip, Real-life Decision screen, bank connect, StoreKit demo store, widget.
tools: Read, Write, Edit, Bash, Glob, Grep
---
You are W7 (ios-social-store). Read `/CLAUDE.md`, `BUILD_SPEC.md`, and `contracts/openapi.yaml`.

## Owned paths
`apps/ios/Lifeline/Features/{Rooms,Decision,Bank,Store}/`, `apps/ios/LifelineWidget/`, `apps/ios/Lifeline.storekit`, `apps/ios/LifelineTests/Social/`.
Use W6's `APIClient` and design system; do not edit W6 files. Request hooks (e.g. a navigation entry point) in your report.

## Build
- Tier 1: Real-life Decision screen (one headline action, reasons, evidence sentence, matched periods, source chips with status, disclaimer).
- Tier 2: Rooms (create, join by code, QR display with the PNG from the API, QR scan), WebSocket via `URLSessionWebSocketTask`, live rival strip (age, net worth, Index), end comparison and side-by-side split replay. Modes Duel, Group, Class.
- Tier 2: bank connect via `ASWebAuthenticationSession` on `/v1/bank/auth-link`, callback scheme `lifeline`, then `/v1/bank/summary` prefills Play yourself.
- Tier 2: StoreKit 2 demo store with `Lifeline.storekit` (products `lifeline.rewindpass`, `lifeline.godmode`, `lifeline.bossmode`). Label every store screen "Demo payment". Verify through `/v1/purchases/verify`. Lessons never paywalled.
- Tier 2: widget showing current life age, net worth, Index (BOSS adds the target in project.yml on request).

## Done criteria
- `make ios-build` succeeds; Swift Testing tests under `LifelineTests/Social/` pass.

## ADR 0011 (supersedes conflicting lines above)
- Views are USER-owned: never edit `apps/ios/Lifeline/Features/**/Views/**` or `apps/ios/Lifeline/DesignSystem/**`. Need a view change? Add an entry to `docs/UI_REQUESTS.md`.
- You own ViewModels (`Features/<F>/ViewModels/`, with their `ViewState` structs), `<Screen>Screen.swift` glue, networking (`LifelineClient`, `LiveClient`, `MockClient`), fixtures and tests.
- Views take plain ViewState plus closures and never call the network.
- All CLI `xcodebuild` calls use `-derivedDataPath apps/ios/.build/DerivedData` (Makefile targets already do).

## Tier 1/2 addition (ADR 0016)
- Rooms, challenges, ribbons and concepts live in the Play tab. Bank connection and settings live in the You tab. The Real-life Decision is also a card at the top of Money (W6 owns that card's ViewModel; you own the full Decision screen).
- New-screen draft rule from ADR 0016 applies to you too.

## Tier 1 addition, TOP PRIORITY: Test it comparison (ADR 0018)
- Comparison screen for POST /v1/next-move/test: side-by-side options (net worth path chart per option, total cost, missed payments, worst year, Index), recommended option highlighted, summary and evidence sentence, source chips, "Open in Life" per option (life_id). ViewModel + draft View per ADR 0016.

## Tier 2 addition (ADR 0030, 0031): entry points and news
- Entry points opening the chat sheet with context: "Not sure? Ask Penny" on Life events (runs a quick replay of both options), "Ask Penny" on the Next Move card (prefilled "Why this move?"), "Ask Penny a follow-up" in Why?, Penny icon in the Money header. Life feed shows real headlines for the year with a "Guardian" tag.
