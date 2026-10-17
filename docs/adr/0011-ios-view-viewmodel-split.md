# ADR 0011: iOS split into pure Views (human-owned) and ViewModels (agent-owned)

- Status: accepted
- Date: 2026-10-17
- Requested by: the user (UI owner)

## Context
The user wants to work on the UI in parallel with the agents. Agents and the user must not edit the same Swift files. Views must render without a backend.

## Decision
1. Networking sits behind `protocol LifelineClient`. Two implementations:
   - `LiveClient`: wraps the generated OpenAPI client.
   - `MockClient`: returns contract examples and `Fixtures`, instantly, with no backend.
2. Client selection, in order of precedence:
   - Launch argument `-mockClient` or `-uiTestingMock`, then the Debug-only toggle (UserDefaults key `debug.useMockClient`, set from a hidden debug menu).
   - Otherwise the build setting `LIFELINE_CLIENT` (Info.plist key `LifelineClient`): `live` in Debug and Release, `mock` in the `Mock` configuration.
3. Every screen has two parts:
   - `Features/<Feature>/ViewModels/<Screen>ViewModel.swift` (agent-owned). It is `@MainActor @Observable`, calls `LifelineClient`, and exposes `state: <Screen>ViewState` plus action closures or methods.
   - `Features/<Feature>/Views/<Screen>View.swift` (user-owned). It is a pure view that takes `<Screen>ViewState` (a plain `struct`, `Equatable`, `Sendable`) and action closures. It never imports the networking layer and never calls the network.
   - Screen-to-ViewModel glue is in `Features/<Feature>/<Screen>Screen.swift` (agent-owned). The glue owns the ViewModel and passes the state and closures into the View.
4. ViewState types live with the ViewModel (`ViewModels/<Screen>ViewState.swift`), so the agent controls the data shape. Views read them. A change to a ViewState that breaks a View is a request in `docs/UI_REQUESTS.md`, not a direct edit.
5. `Lifeline/Preview/Fixtures.swift` holds realistic `ViewState` values for every screen and state (new life, mid-life, crisis event, lesson, rewind, death summary, 4-player PvP room, real-life decision, error, loading, mock-source labels). Every View file has `#Preview` blocks for each fixture, in light and dark, and at a large Dynamic Type size.
6. The `Playground` scheme runs the `Mock` configuration with `-playground`. The app then opens a gallery of every screen and fixture state, backed by `MockClient`.
7. Ownership after the restructure:
   - The user owns `apps/ios/Lifeline/Features/**/Views/**` and `apps/ios/Lifeline/DesignSystem/**`.
   - Agents never edit these paths. An agent that needs a view change adds a request to `docs/UI_REQUESTS.md`.
   - The restructure itself (one W6 run) is the last agent edit to those paths.

## Consequences
- The user and the agents can work at the same time without file conflicts.
- Pure views make previews and snapshot tests cheap.
- An extra glue layer per screen. A ViewState change needs coordination through `docs/UI_REQUESTS.md`.
- Tier 1 and Tier 2 screens (lesson, rewind, summary, PvP room, decision) get pure Views and fixtures now, so the UI owner can design them before their ViewModels exist.

## Implementation notes (W6)
- Each screen: `<Screen>ViewState` (plain, `Equatable`, `Sendable`) and `<Screen>Actions` (struct of `@MainActor` closures, `.noop` default).
- Shared view-state types live in `Features/Common/ViewModels/CommonViewState.swift` (`DataStatus`, `SourceChipState`, `LoadPhase`, `StatState`, `HistoryItemState`, `OutcomeState`, `ChartState`, `ActionItemState`). `ActionTabActions` and `GalleryView` serve several screens, so they do not follow one-file-per-screen naming.
- ViewStates carry raw numbers for `.numericText()` transitions. Views format money with `Money`.
- One `@MainActor` `GameSession` holds the current life. ViewModels read from it.
- Debug menu: long-press the version label on character select (Debug builds). It sets the mock toggle and `-demoDeviceID`.
- The Playground gallery has 63 entries (V4 count).
- Rewind stays enabled on a dead life by design: the player can go back to any past choice after death (spec section 0, step 6).
- Known: the app bundle includes `openapi.yaml` and the generator config as resources. They hold no secrets. They stay in the target because the OpenAPI build plugin reads them from the target's files.
- Test it (W7): `TestItViewModel` takes a loader closure (`TestItLoader`) instead of `any LifelineClient`, so W7 built in parallel with W6's client change. Feature fixtures may live in the feature folder (`Features/TestIt/TestItFixtures.swift`) when the feature belongs to a different worker than `Preview/Fixtures.swift`.
