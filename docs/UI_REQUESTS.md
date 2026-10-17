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
- W6 note: `Fixtures.galleryCatalog` now exists (`Preview/FixturesGallery.swift`). `GalleryViewModel.catalog` returns it, so the previews still compile. Replace `GalleryViewModel.catalog` with `Fixtures.galleryCatalog` in the previews.
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

### UIR-7: Draft created, please review: Next Move card
- From: W6
- Screen / file: `apps/ios/Lifeline/Features/Home/Views/NextMoveCardView.swift` (draft per ADR 0016; W6 will not edit it again)
- Need: Review the draft. First element on the Money tab: headline, action, £ a year (`.numericText()`), confidence label, worst case, deadline, source chips, "Sample data", buttons Test it / Why? / Do this, plan message, backtest line, runner-up rows.
- Why: ADR 0018 (Tier 1 top priority).
- ViewState change: new `NextMoveCardState`, `NextMoveActions` in `Features/Home/ViewModels/NextMoveViewState.swift`. Fixtures: `Fixtures.NextMove` (ready, inPlan, adding, focusedRunnerUp, liveUntestable, loading, error).
- Status: open

### UIR-8: Draft created, please review: Guess my spend card
- From: W6
- Screen / file: `apps/ios/Lifeline/Features/Home/Views/GuessSpendCardView.swift` (draft per ADR 0016; W6 will not edit it again)
- Need: Review the draft. Guess entry first; `state.reveal` is nil until the guess, so no prediction can show early. After the guess: your guess vs the model, range, top 3 reasons in £, actual, points and beat-the-model for past days, streak, history, link to model accuracy.
- Why: ADR 0017.
- ViewState change: new `GuessSpendViewState`, `GuessSpendActions`. Fixtures: `Fixtures.Guess` (beforeGuess, revealed, pastDay, submitting, invalidEntry, loading, error).
- Status: open

### UIR-9: Draft created, please review: Money widgets
- From: W6
- Screen / file: `apps/ios/Lifeline/Features/Home/Views/MoneyWidgetsView.swift` (draft per ADR 0016; W6 will not edit it again)
- Need: Review the draft. Balance and net worth (Swift Charts line), spending by category (bar), subscriptions with price-rise flags, bills next 30 days, budgets with progress, savings goals. Each widget loads and fails on its own and shows a "Your next move" link when a move relates.
- Why: ADR 0016 Money tab.
- ViewState change: new `MoneyWidgetsViewState`, `WidgetSection`, `MoveLinkState`, `MoneyWidgetsActions`. Fixtures: `Fixtures.Widgets` (ready, partialError, empty, loading).
- Status: open

### UIR-10: Draft created, please review: Money tab
- From: W6
- Screen / file: `apps/ios/Lifeline/Features/Home/Views/MoneyHomeView.swift` (draft per ADR 0016; W6 will not edit it again)
- Need: Review the draft. Composes the Next Move card, Guess my spend and the widgets in one scroll view with pull to refresh. Move links scroll back to the card.
- Why: ADR 0016 and 0018: the app opens here.
- ViewState change: new `MoneyHomeViewState`, `MoneyHomeActions`. Fixtures: `Fixtures.MoneyHome` (ready, revealed, loading, offline).
- Status: open

### UIR-11: Draft created, please review: Why? for a Next Move
- From: W6
- Screen / file: `apps/ios/Lifeline/Features/Home/Views/NextMoveWhyView.swift` (draft per ADR 0016; W6 will not edit it again)
- Need: Review the draft. Headline, action, confidence, the 3 evidence points with source chips, the lesson preview with the personal sentence and "Open the lesson", and "See the full decision" for mortgage moves (W7 screen).
- Why: ADR 0018 "Why?".
- ViewState change: new `NextMoveWhyViewState`, `NextMoveWhyActions`. Fixtures: `Fixtures.Why` (noLesson, withLesson, loadingLesson, lessonError).
- Status: open

### UIR-12: Draft created, please review: Your plan
- From: W6
- Screen / file: `apps/ios/Lifeline/Features/Home/Views/PlanView.swift` (draft per ADR 0016; W6 will not edit it again)
- Need: Review the draft. List of moves added with "Do this" and the total a year.
- Why: ADR 0018 "Do this".
- ViewState change: new `PlanViewState`, `PlanActions`. Fixtures: `Fixtures.Plan` (oneItem, empty, loading, error).
- Status: open

### UIR-13: Draft created, please review: Spend model accuracy
- From: W6
- Screen / file: `apps/ios/Lifeline/Features/Home/Views/SpendAccuracyView.swift` (draft per ADR 0016; W6 will not edit it again)
- Need: Review the draft. Model error vs the weekday-average baseline, range coverage, chart of predicted, range and actual per day, method text, sample-data note.
- Why: ADR 0017 model accuracy link.
- ViewState change: new `SpendAccuracyViewState`, `SpendAccuracyActions`. Fixtures: `Fixtures.SpendAccuracy`.
- Status: open

### UIR-14: Draft created, please review: Play tab
- From: W6
- Screen / file: `apps/ios/Lifeline/Features/Play/Views/PlayView.swift` (draft per ADR 0016; W6 will not edit it again)
- Need: Review the draft. Start or continue a life, Same Life rooms (W7), concepts count, challenges (tap starts the preset), your lives (tap opens it in the Life tab) and ribbons.
- Why: ADR 0016 Play tab.
- ViewState change: new `PlayViewState`, `PlayActions`. Fixtures: `Fixtures.Play` (ready, noLives, loading, error).
- Status: open

### UIR-15: Draft created, please review: You tab
- From: W6
- Screen / file: `apps/ios/Lifeline/Features/You/Views/YouView.swift` (draft per ADR 0016; W6 will not edit it again)
- Need: Review the draft. Profile from `/v1/finance/profile` with personal facts, bank connection (W7), plan, data sources, advice backtest, spend model accuracy, extras, debug menu (Debug builds), version.
- Why: ADR 0016 You tab.
- ViewState change: new `YouViewState`, `YouActions`. Fixtures: `Fixtures.You` (ready, release, loading, error).
- Status: open

### UIR-16: Draft created, please review: Advice backtest
- From: W6
- Screen / file: `apps/ios/Lifeline/Features/Evaluation/Views/EvaluationView.swift` (draft per ADR 0016; W6 will not edit it again)
- Need: Review the draft. Hit rate vs baseline from `/v1/evaluation` and one row per past period.
- Why: Tier 1 backtest screen (BUILD_SPEC).
- ViewState change: new `EvaluationViewState`, `EvaluationActions`. Fixtures: `Fixtures.Evaluation`.
- Status: open

### UIR-17: Draft created, please review: Life action menu bar
- From: W6
- Screen / file: `apps/ios/Lifeline/Features/Life/Views/LifeMenuBarView.swift` (draft per ADR 0016; W6 will not edit it again)
- Need: Review the draft. Row of glass buttons (Job, Assets, People, Money, Activities) with action counts. The glue attaches it under `LifeView` with `.safeAreaInset(edge: .bottom)`; each opens the existing menu screen as a sheet.
- Why: ADR 0016: game menus live inside the Life tab.
- ViewState change: new `LifeMenuViewState`, `LifeMenuActions`. Fixtures: `Fixtures.LifeMenu` (midLife, dead).
- Status: open

### UIR-18: Lesson shows the personal sentence
- From: W6
- Screen / file: `apps/ios/Lifeline/Features/Lesson/Views/LessonView.swift`
- Need: Show `state.personal` (when not nil) under the 2 sentences, for example "You spend £47 a month on 6 subscriptions."
- Why: ADR 0016 bridge: lessons link to the player's real numbers (`Lesson.personal`).
- ViewState change: added `LessonViewState.personal: String?` (default nil).
- Status: open

### UIR-19: Life screen: menus moved and duplicate entry points
- From: W6
- Screen / file: `apps/ios/Lifeline/Features/Life/Views/LifeView.swift`, `apps/ios/Lifeline/Features/CharacterSelect/Views/CharacterSelectView.swift`
- Need: Optional cleanup. The Life tab now has the menu bar under `LifeView` (Job, Assets, People, Money, Activities), so the "Activities" quick link in `LifeView` duplicates it. Rooms, store and sources are now also in the Play and You tabs, so the matching buttons on character select are optional. Check that the AGE button and the history feed are not hidden behind the menu bar at AX sizes.
- Why: ADR 0016 tab layout.
- ViewState change: none
- Status: open

### UIR-20: Duplicate source chips on one move
- From: W6 (via BOSS)
- Screen / file: `apps/ios/Lifeline/Features/Home/Views/NextMoveCardView.swift` and the shared source chip in `DesignSystem/`
- Need: The mortgage move cites 3 BoE series, so the card shows "Bank of England live" 3 times. Group chips by source with a count, or show the series name in the chip (for example "BoE 5-year fix").
- Why: Clarity of evidence on the main card.
- ViewState change: none (`SourceChipState` already carries the series id)
- Status: open
