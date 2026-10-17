# ADR 0025: Tier 1 iOS structure (W6, W7)

- Status: accepted
- Date: 2026-10-17

## Decision
- Tabs live in `App/RootScreen.swift`: Money (always the start tab, never restored), Life, Play, You.
- The Life tab shows character select when no life is running.
- The Life menus (Job, Assets, People, Money, Activities) are a bar under `LifeView`, attached from glue with `.safeAreaInset`. Each opens its menu as a sheet. `LifeView` is not edited.
- The Money tab code lives in `Features/Home/`. This avoids a collision with the Life menu in `Features/Money/`.
- Next Move card:
  - Test it opens `TestItScreen` (W7) through one `TestItRoute`. "Open in Life" loads the stored life (`GameSession.openLife(id:)`) and switches to the Life tab.
  - Why? shows the 3 evidence points and the lesson for `concept_id`. If the API omits `Lesson.personal`, the client fills it from the matching personal fact.
  - Do this posts to `/v1/plan` and shows the yearly total.
- Money widgets link back to the card by move kind:
  - subscriptions: cancel or switch subscription
  - bills: fix mortgage, remortgage, switch energy
  - budgets, spending and Guess my spend: cut budget
  - goals: emergency fund, move savings
  - overview: move savings, pay off debt
- Guess my spend: the prediction, range and reasons are absent from the ViewState until the user guesses (tested). Client-side input check: £0 to £100,000; "£" and "," accepted.
- The Test it ViewModel takes a loader closure (W7). Its fixtures live in `Features/TestIt/`.
- 11 draft Views were created under the ADR 0016 rule (UIR-7 to UIR-17). W6 edited two drafts once more in the same run to fix accessibility identifiers; no pre-existing View was edited.
