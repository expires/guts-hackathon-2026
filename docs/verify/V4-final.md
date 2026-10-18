# V4 final: iOS verification (PENNY_V3_BUILD B3, B4, B5, C, D, E, F, G)

- Date: 2026-10-18, 09:13 to 09:20 BST
- Verifier: V4 (read-only on code)
- Target: iOS tree on origin/main 3eae93c6. The local checkout is at `cfff461e` with uncommitted changes. Its `apps/ios` is identical to the `phone-build8` scratch tree (`diff -rq` shows no differences, excluding `.build` and `.xcodeproj`).
- Simulator: "Helper iPhone" (CF4BB22E). No other simulator used. Xcode default DerivedData not touched.
- Screenshots: `/private/tmp/claude-501/-Users-ash-Workspace-dyhtg/d2613979-29cc-4f7b-8a9a-40abef46e06e/scratchpad/v4-final/`
  - `live-*.png`: taken in this run.
  - `run0848-*.png`: exported from the xcresult of the 08:48 test run on the same tree.

## Verdict: PASS

No blocking failures. Five non-blocking notes are listed at the end.

## Checks

| # | Check | Command / method | Result |
|---|---|---|---|
| 1 | Full test suite | Cited log `scratchpad/pb8-test.log` (`make ios-test`, 08:48). Not run again. | PASS: 379 unit tests in 43 suites, 18 UI tests, 0 failures, `** TEST SUCCEEDED **` |
| 2 | App launches on simulator | `xcrun simctl install` + `launch -uiTestingMock -skipOnboarding` with the Debug-iphonesimulator app from phone-build8 | PASS |
| 3 | Money home, on track (B3.1, B3.2) | `live-money-ontrack.png`, `run0848-money-en-1/2.png` vs `Main.dc.html` | PASS. Chip, headline, next money line, £135 a week (about £19 a day), habit line, timeline, See the maths, Ask Penny, pie, See all spending, Due before 2 November, One thing that helps (Bank of England rate), "In your account £318". Matches canvas. |
| 4 | Money home, running short | `live-money-short.png`, `run0848-money-short-1.png` (`-mockForecastShort`) vs `Short.dc.html` | PASS. Text and numbers match canvas (£80 a week, run out 28 October, Runs out 28 Oct in the timeline). |
| 5 | The maths (B3.3) | `run0848-maths-1/2.png` vs `Why.dc.html` | PASS with note 3. 4 steps with sources, buffer 0/5/10/15/20, £270 ÷ 2 weeks = £135, habits, detailed breakdown link, Ask Penny about this. |
| 6 | Detailed breakdown (B3.4) | `run0848-breakdown-1..4.png` vs `Detail.dc.html` | PASS. Sums checked by hand: 318.40 − 17.99 = 300.41; buffer 30.04; 270.37 ÷ 14 × 7 = 135.19; average (131+118+126+113) ÷ 4 = 122.00; 13.19 × 2 = 26.38. All add up. |
| 7 | All spending (B3.5) | `run0848-spending-1/2.png` vs `Spend.dc.html` | PASS. Month switch, pie, share and change vs Sep, rent and bills listed separately. |
| 8 | Category (B3.6) | `run0848-category-1/2.png` vs `Category.dc.html` | PASS. Total, usual monthly, bars by week, every transaction. See note 5. |
| 9 | Penny chat (D1-D3) | `run0848-penny-1-one-answer.png`, `run0848-penny-2-past-chats.png` | PASS. One answer, one header label, New chat and Past chats buttons in header. See note 2. |
| 10 | Onboarding Welcome (C1) | `live-onboarding-welcome.png`, `run0848-en-01-welcome.png` | PASS. Headline plus 3 lines (who, what data, what you get). |
| 11 | Pick your student (C6, B4) | `run0848-en-06*.png` | PASS. Larger cards (name, age, uni and city, funding, money in with dates, housing, habit line). Honesty line present, text matches B4 exactly. No tags. |
| 12 | Play tab (F4, F5) | `run0848-Picker-*.png`, `run0848-Lobby-host-Quick-Life.png`; `PlayCutUITests.testPlayTabShowsFriendsAndLearnOnly` passed at 08:48 | PASS. Quick Life first, Money Quiz below. |
| 13 | Learn screen (E) | Live screenshot | NOT RUN. No tap tool on the simulator (no idb/axe). Covered only by passing UI tests. |
| 14 | You tab (E5, G1) | Live screenshot | NOT RUN (same reason). `PlayCutUITests.testYouTabShowsLessonsAndNoCutRows` passed at 08:48; `YouView.swift:128` labels "Lessons X". |
| 15 | No "Mock data" / "Sample data" text (B4, G4, G5) | `NoMockTextUITests` passed at 08:48 (all 4 tabs, 3 scroll positions). Code: `DemoDataBadge` body is `EmptyView()` (`DesignSystem/Components.swift:130`). None visible in any screenshot. | PASS |
| 16 | Accessibility labels and 44 pt targets on new screens | Read `Features/Forecast/Views/*.swift`, `Features/Penny/Views/*.swift` | PASS. Text buttons get labels from their titles. Icon-only month arrows have labels and 44×44 frames (`SpendingViews.swift:66-77`). Buffer buttons: 32 pt + 2×6 pt padding = 44 pt hit area with labels "Buffer N percent". Penny header pills: `frame(minHeight: Theme.minTarget)` (44). Detail link 52 pt. `Theme.minTarget = 44`. |
| 17 | Floating tab bar and bottom padding (G2) | All screenshots | PASS. Last items (Ask Penny about this, In your account, rent and bills) scroll clear of the bar. Penny input sits above the bar. |

## Notes (non-blocking)

1. Mock fixture mismatch. Money home in Mock config greets "Hi, Priya" but shows Eilidh's forecast ("SAAS loan, £735"). Priya is a commuter student on an Access grant. Source: `Features/Forecast/Mock/ForecastMock.swift` (Eilidh/Callum) vs the mock profile. Affects Mock config and UI tests only. Phones run Demo config (`LIFELINE_CLIENT: live`). Owner: W6/W7 (Forecast mock).
2. Penny mock answer text mentions "mortgage" ("Your savings cover your bills and mortgage until April"), `Features/Penny/PennyFixtures.swift:15`. Mock only. Owner: W7.
3. Spec deviation. The maths shows "Ask Penny "what if..."" in place of "What if prices rose like in 2022?" (`ForecastMathsView.swift:75-76`, comment says user request). `runStress()` still exists in the ViewModel but has no button. BOSS: record the decision in an ADR.
4. Detailed breakdown omits the canvas rent row ("Rent, £540 paid 3 Oct, next due 3 Nov, £0.00"). Minor. Owner: W6/W7.
5. Category mock says "usually about £568 a month" for groceries while the weekly bars total about £80 a week. Mock data plausibility only.
