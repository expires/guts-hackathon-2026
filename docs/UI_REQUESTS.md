# UI requests

Agents cannot edit `apps/ios/Lifeline/Features/**/Views/**` or `apps/ios/Lifeline/DesignSystem/**` (ADR 0011). The UI owner (the user) edits those paths.

An agent that needs a view change adds one entry below. The UI owner marks it done.

## Format

```
### UIR-<n>: <short title>
- From: <agent id>
- Screen / file: <path>
- Need: <what must change, in one or two sentences>
- Why: <the feature or bug it unblocks>
- ViewState change: <new or changed fields, or "none">
- Status: open | done
```

## Open

### UIR-1: Character card at accessibility text sizes
- From: V4
- Screen / file: `apps/ios/Lifeline/Features/CharacterSelect/Views/CharacterSelectView.swift:71-80`
- Need: At accessibility sizes, stack the title and badge vertically (`ViewThatFits` or `dynamicTypeSize.isAccessibilitySize`) and shrink or hide the emoji column. Today "Play yourself" wraps word by word and the badge breaks as "Rec-om-men ded".
- Why: Dynamic Type (BUILD_SPEC section 1). Ref: `docs/screens/ax-xxxl-character-select.png`.
- ViewState change: none
- Status: open

### UIR-2: Sheet spring is never applied
- From: V4
- Screen / file: `apps/ios/Lifeline/DesignSystem/Theme.swift:54`
- Need: Apply `Motion.sheet(reduceMotion:)` (spring 0.3 / 0.8) to sheet transitions, or remove the constant.
- Why: BUILD_SPEC motion spec for sheets.
- ViewState change: none
- Status: open

### UIR-3: Debug menu not reachable with VoiceOver
- From: V4
- Screen / file: `apps/ios/Lifeline/Features/CharacterSelect/Views/CharacterSelectView.swift:40`
- Need: Add `.accessibilityAction(named: "Debug menu", actions.onVersionLongPress)` to the version label.
- Why: The long-press is the only way in (Debug builds only).
- ViewState change: none
- Status: open

### UIR-4: Gallery previews read a ViewModel type
- From: V4
- Screen / file: `apps/ios/Lifeline/Features/Playground/Views/GalleryView.swift:39,43,47`
- Need: Previews use a `Fixtures` gallery value instead of `GalleryViewModel.catalog` (ADR 0011: previews use Fixtures). W6 can add the fixture value on request.
- Why: Keeps Views independent of ViewModels.
- ViewState change: needs a `Fixtures.galleryCatalog` (W6)
- Status: open

### UIR-5: Draft created, please review: Test it comparison
- From: W7
- Screen / file: `apps/ios/Lifeline/Features/TestIt/Views/TestItView.swift` (draft per ADR 0016; W7 will not edit it again)
- Need: Review the draft. It shows the period, summary and evidence sentence, one card per option (net worth chart with a shared y range, end net worth, total paid, missed payments, worst year, Index, "Open in Life"), the recommended card highlighted in green, source chips and the "Sample data" badge. Two options sit side by side; three or more scroll sideways; accessibility sizes stack them.
- Why: ADR 0018 "Test it" (Tier 1 top priority).
- ViewState change: new `TestItViewState`, `TestItActions` in `Features/TestIt/ViewModels/TestItViewState.swift`. Unused fields you may want: `Option.endNetWorthGap`, `Option.facts`, `Option.accessibilitySummary`, `Option.startNetWorth`, `Option.worstYearChange`. Fixtures: `TestItFixtures` (ready, sampleData, mixed, single, loading, offline, notFound).
- Status: open

### UIR-6: Real-life Decision shows its entry point and "Test it"
- From: W7
- Screen / file: `apps/ios/Lifeline/Features/Decision/Views/RealLifeDecisionView.swift`
- Need: Use `state.title` for the navigation title (today it is fixed to "Your real decision"). When `state.canTestIt` is true, show a "Test it" button that calls `actions.onTestIt`. Show `DemoDataBadge` when `state.isSampleData`. Optional: use `state.basisSentence` in place of the inline "Based on ..." text (it joins periods with "and"), and `state.successText` ("7 in 10") for the progress value.
- Why: ADR 0018. The screen now opens from "Why?" on a mortgage move (title "Why this move?") and from a "Play yourself" life that reaches today (title "You reached today").
- ViewState change: added `context`, `title`, `actionID`, `successText`, `basisSentence`, `canTestIt`, `isSampleData` (all with defaults); `RealLifeDecisionActions.onTestIt`.
- Status: open

### UIR-7: Drafts created, please review: Money tab, You tab, Accounts, Investments, Habits
- From: W6 (integration branch, user allowed View edits)
- Screen / file: `Features/Home/Views/MoneyHomeView.swift`, `MoneyWidgetsView.swift`, `Features/You/Views/YouView.swift`, `Features/{Accounts,Investments,Habits}/Views/*View.swift`
- Need: Review the drafts. Open items: the "Why?" button on the Next Move card has no destination yet (no Why screen); Play tab, Plan, Evaluation and Spend accuracy have ViewModels but no screens; the Life tab hides the app tab bar while a life runs and shows a "Back to Money" button instead.
- Why: Live Monzo and Trading212 connections, investments replay, habits.
- ViewState change: new `AccountsViewState`, `InvestmentsViewState`, `HabitsViewState`; `MoneyHomeViewState.connections`, `.investmentsLink`.
- Status: open
