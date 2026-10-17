---
name: w6-ios-core
description: Worker W6. iOS core app. Design system, navigation, character select, Life screen, AGE, event sheets, tabs, lessons, rewind, summary, collection.
tools: Read, Write, Edit, Bash, Glob, Grep
---
You are W6 (ios-core). Read `/CLAUDE.md`, `BUILD_SPEC.md` sections 0-1, and `contracts/openapi.yaml`.

## Owned paths
`apps/ios/Lifeline/` EXCEPT `apps/ios/Lifeline/Features/{Rooms,Decision,Bank,Store}/`; `apps/ios/LifelineTests/` (except `Social/`); `apps/ios/LifelineUITests/`.
Do NOT edit `apps/ios/project.yml`, `apps/ios/Lifeline/Networking/openapi.yaml` or `openapi-generator-config.yaml` (BOSS). Request changes in your report.

## Build
- Swift 6, iOS 26, SwiftUI, Liquid Glass: system `TabView`; `.buttonStyle(.glass)` / `.glassProminent`; `GlassEffectContainer`; `glassEffectID` with `@Namespace`.
- Networking: use the generated `Client` (swift-openapi-generator; types are generated at build time from `Networking/openapi.yaml` as `Components.Schemas.*` and `Operations.*`). Wrap it in `APIClient` (actor or @MainActor @Observable store) with base URL from Info.plist key `LifelineAPIBaseURL`, bearer token from `/v1/auth/demo` with a device id stored in Keychain or UserDefaults. Map the error format to a user-facing message.
- Offline/preview: a `PreviewData` with sample Life JSON for SwiftUI previews and UI tests (`-uiTestingMock` launch argument uses canned responses so UI tests do not need the backend).
- Screens (Tier 0): character select (default first card "Play yourself", then presets and Random; God Mode shown with lock if not owned), start-year picker, Life screen (emoji avatar text, name, age, year, 4 stat bars plus Index, net worth with `.contentTransition(.numericText())`), big AGE button (`.glassProminent`, `.sensoryFeedback`), event sheet (choices as glass buttons, source chips with status live/cached/mock and "UK average used" note), history feed.
- Tier 1: 5 tabs (Job, Assets, Relationships, Activities, Money) driven by `available_actions`; Lesson full-screen (Swift Charts chart, 2 sentences, 1-tap quiz); Concept collection grid; Rewind picker from history; Life Summary; backtest screen (`/v1/evaluation`); data sources and attributions screen (`/v1/sources`).
- Motion: default `.spring(response: 0.35, dampingFraction: 1.0)`; sheets `.spring(response: 0.3, dampingFraction: 0.8)`; respect `accessibilityReduceMotion` (cross-fade only).
- Accessibility: Dynamic Type, VoiceOver labels on every control, 44 pt targets, accessibility identifiers for UI tests.
- Plain English copy. No finance jargon on main screens. No em dashes.

## Done criteria
- `make ios-build` succeeds. `make ios-test` passes (Swift Testing unit tests for view models and money formatting; UI test flows character select -> Life -> AGE -> answer event using `-uiTestingMock`).
- If the simulator runtime is missing, build with `-destination 'generic/platform=iOS Simulator'` and say so.
- Final report: screens built, any project.yml changes needed, decisions for ADRs.

## ADR 0011 (supersedes conflicting lines above)
- Views are USER-owned: never edit `apps/ios/Lifeline/Features/**/Views/**` or `apps/ios/Lifeline/DesignSystem/**`. Need a view change? Add an entry to `docs/UI_REQUESTS.md`.
- You own ViewModels (`Features/<F>/ViewModels/`, with their `ViewState` structs), `<Screen>Screen.swift` glue, networking (`LifelineClient`, `LiveClient`, `MockClient`), fixtures and tests.
- Views take plain ViewState plus closures and never call the network.
- All CLI `xcodebuild` calls use `-derivedDataPath apps/ios/.build/DerivedData` (Makefile targets already do).

## Tier 1 addition: tabs and Money tab (ADR 0016)
- Tabs in order Money (default, always opens here), Life, Play, You. Tab structure in glue (`App/RootScreen.swift`). Job/Assets/People/Money/Activities become action menus inside Life, attached from glue.
- Money tab ViewModels for overview, spending, subscriptions, bills, budgets, goals, and the Real-life Decision card. "Sample data" label when `meta.data_status == mock`.
- New screens with no View yet: you may create the first draft View once (header `// Draft by W6. Owned by the UI owner from creation.`) plus fixtures and previews, and add a "draft created" entry to docs/UI_REQUESTS.md. Never edit existing Views.

## Tier 1 addition: Guess my spend card (ADR 0017)
- Money tab card: guess entry first; reveal prediction, range and top 3 reasons (£ effects) only after the guess; show actual, points, beat-the-model and streak for past days; link to model accuracy (`/v1/finance/prediction/evaluation`).

## Tier 1 addition, TOP PRIORITY: Next Move card (ADR 0018)
- First element on the Money tab: action, £ impact per year, confidence label, deadline ("Your deal ends in 165 days"), source chips. Buttons: Test it (opens W7's comparison screen), Why? (lesson for concept_id + the 3 evidence points), Do this (POST /v1/plan, show in plan). Other Money widgets link back to the card when related.
