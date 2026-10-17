# Feature map: Penny iOS app (17 Oct 2026, 22:15)

Written by the feature mapper. Read-only on code.

## How this map was made

- Source: the current uncommitted code in `apps/ios` and `contracts`, copied to a snapshot. No repo code was changed.
- Backend: the LOCAL stack (`http://localhost:8000`, health ok). **Not Railway.** Railway does not have the V2 endpoints yet.
- Build: Demo configuration on simulator "Map iPhone" (iPhone 18 Pro Max, iOS 27.0). API base URL set to the local stack in the snapshot only.
- Sample student: fresh demo user `featuremap-working-214051`, "working" sample imported through the API (`POST /v1/auth/demo`, then `POST /v1/samples/working/import`). The app has no "Use a sample statement" button.
- Onboarding shots use a second fresh user with no data.
- Screens were driven by an XCUITest in the snapshot. Each shot was taken with `xcrun simctl io "Map iPhone" screenshot`.
- Other agents share the local stack and the client IP. The API log shows `429` on `POST /v1/auth/demo` from them during the run. Some "offline" states below may be partly caused by this. The cause is noted where the log shows it.

## Summary

| Status | Count |
|---|---|
| Working (seen on screen) | 22 |
| Partly working or wrong values | 14 |
| Broken on screen | 6 |
| Placeholder | 1 |
| Not reached (no screenshot) | 12 |
| Not built (V2 list below) | 18 |
| Screenshots in `docs/feature-map/screens/` | 42 |

### Broken on screen (fix first)

| # | Screen | What the screen shows |
|---|---|---|
| B1 | Play solo, "Start life" | Server returns `201 Created`, app shows "Something went wrong. Cannot reach the Penny server." and returns to Play. Running life, events, menus, rewind, summary cannot be reached. |
| B2 | Where our data comes from | "Something went wrong. The server sent data the app cannot read." (`/v1/sources` returns 200). App and server disagree on the response shape. |
| B3 | Play tab, Challenges | First load: "You are offline" (server returned 200). A later load showed the list. |
| B4 | See all, Budgets section | "You are offline. Cannot reach the Penny server." (`/v1/finance/budgets` returns 200). |
| B5 | Play with friends, room setup | "Couldn't load. Pull to refresh." in the Life list; "Make the room" is disabled. On another run the list loaded. |
| B6 | You, profile row | Tap does nothing. No account screen opens (sign out, reset, delete are not reachable from You). |

### Wrong values or labels

| # | Where | Issue |
|---|---|---|
| W1 | Every Money screen, You | Badge says "Mock data. Not from your bank or the live server." The data is the sample statement. V2 label is "Sample data". |
| W2 | Next Move card | "£131, a year better off". £131 is a one-off shortfall before 23 October, not a yearly gain. |
| W3 | Next Move card vs Why? | Card says "Medium confidence, 2 of 3". Why? says "High". Bug 4. |
| W4 | In your account, Net worth | Both £0. The sample has a £371 overdraft at 39%. Net worth should be about -£371. Bug 2. |
| W5 | Why? sources line | "Sources: Bank:Sample · sample" (internal code style). |
| W6 | You, Connect your money | Says "Not added yet" although sample data is imported. Tap opens onboarding at Welcome page 1, not at "Connect your money". |
| W7 | Play yourself form | Born 1991 (age 35) and pay £0. Profile says age 21, student. V2: start from the user's real age and data. |
| W8 | You, Version | "Penny 1.0 - dev build", "Features: none listed" in a Demo build. |
| W9 | Penny general answer | "What is a Lifetime ISA?" is labelled "Checked with your data". It also offers a "Test it" chip. V2: label "General answer" when no engine tool is used. Money shows "£4000" (no comma) and "25.0%". |
| W10 | Penny tab | Keyboard stays open after the answer and covers half the screen. |

### Conflicts with DIRECTION_V2

| # | Where | Conflict |
|---|---|---|
| C1 | Onboarding, Connect your money | No "Use a sample statement" (4 student cards). Monzo and Trading 212 are hidden on screen (still in code). |
| C2 | Onboarding, Enter your numbers | Old adult form: "I own it outright", "Mortgage", "Take-home pay a month". No student or working, income sources, maintenance loan, student loan plan, debts. |
| C3 | Play solo, Choose a life | Presets Amira (NHS nurse), Tom (investment banker), Dan (plumber), Maureen (retired, owns her home), Callum (teacher). Only Priya is a student. |
| C4 | Play yourself form | "Fill in from my bank" button; "Paying a mortgage" and "Debts, not counting a mortgage". |
| C5 | Play, Challenges | Old challenges: "Get through the 2008 crash without missing a single payment", "Beat your twin (Index of 110)", "Ride out the 2022 rate shock" ("Your fix ends as rates jump"). |
| C6 | Play with friends | Opens the old "Same Life" room form: name field, mode, preset life (nurse, banker, plumber, retired), start year. V2: lobby first with QR and code, names from the account, game picker. |
| C7 | You, How good is the advice? | Mortgage backtest: "Right in 71% of 28 past periods", "Advice: Tracker. Best in hindsight: Fix 2y." Shown to a student. |
| C8 | You tab | "Best INDEX" and "Ribbons" from the old game. |
| C9 | Welcome page 3, Test it | "Play the move through past years, like the 2008 crash". Fits the old mortgage product, not a student. |
| C10 | Penny Plus store | God Mode, Boss Mode ("Start a business with Companies House data"), Rewind Pass. V2: store only if all else is green. |
| C11 | Code | Presentation mode, Bank connect, Real-life Decision (mortgage), Monzo and Trading 212 kinds are still in the code. Not seen on screen in this run. |
| C12 | Name | Internal names only: bundle id `com.lifeline.app`, URL scheme `lifeline://`. No "Lifeline" seen on screen. |

Not a conflict: Penny shows the new disclaimer ("Penny is AI and can make mistakes. Guidance only, not regulated financial advice. Check before big decisions.").

## Onboarding

### Welcome (3 pages)
- Does: 3 intro pages, Skip, Next.
- Status: working.
- Copy: "Your money, played forward." / "One next move." / "Test it first." (C9).

![Welcome 1](feature-map/screens/onboarding-welcome-1.png)
![Welcome 2](feature-map/screens/onboarding-welcome-2.png)
![Welcome 3](feature-map/screens/onboarding-welcome-3.png)

### Sign in ("Save your progress")
- Does: explains sign-in; Apple sign-in is not set up, so only "Continue" (demo account).
- Status: partly working (no Apple sign-in in this build).

![Sign in](feature-map/screens/onboarding-sign-in.png)

### Connect your money
- Does: two options: "Upload a statement" (Monzo or Revolut CSV, or PDF, max 5 MB) and "Enter your numbers".
- Status: partly working. **CONFLICT C1** (no sample statement cards).

![Connect your money](feature-map/screens/onboarding-connect.png)

### Upload a statement
- Status: not reached. The file picker did not show in the simulator run. No screenshot.

### Enter your numbers
- Does: postcode, "Use my location", home (rent, own outright, mortgage, with family), rent, take-home pay, regular costs, savings, "Save my numbers".
- Status: partly working. **CONFLICT C2.**

![Enter your numbers](feature-map/screens/onboarding-manual.png)

### Import progress, Next Move reveal, 3 tips
- Status: not reached (sample was imported through the API). API import: 153 transactions, 17 Jul to 16 Oct 2026, finished in under 1 s with 5 stages. No screenshot.

## Money tab

### Money home
- Does: greeting, Next Move card, two tiles, Guess my spend, Coming up (3), See all, Ask Penny.
- Status: working, with wrong values (W1, W2, W4).
- Sample student:
  - "In your account £0", "Net worth £0".
  - Coming up: 17 Oct Netflix £6, 5 Nov Ellie Shaw £38, 6 Nov Smarty £8.

![Money home](feature-map/screens/money-home.png)
![Money home, scrolled](feature-map/screens/money-home-2.png)

### Next Move card
- Does: move, gain, confidence, trade-off, Why?, Do this, "Based on 5 sources", Ask Penny.
- Status: partly working.
- Sample student: "Plan for £131 you are missing before 23 October"; "You are set to be £131 short before 23 October"; "Medium confidence, 2 of 3"; "What you give up: Nothing safe to spend until 23 October: bills come first".
- No "Test it" button (the move has `testable: false`). This is correct for this move.
- Issues: W2, W3. No sample size shown on the card.
- Screenshot: see Money home.

### Weekly budget until the next money arrives
- Status: not built on screen. Only the Next Move shortfall is shown.

### Why? sheet
- Does: 3 evidence bubbles from Penny, "What you give up" with 2 points, sources, confidence, lesson card ("Track the bills"), Ask Penny follow-up, Got it.
- Status: working, with issues W3 and W5.
- Sample student: "Your pay arrives on 23 October, in 7 days, and until then you have £0, with £6 of regular bills to cover." / "about £125 a week ... £131 short once bills are added." / "You spend £12 a month on 2 subscriptions."
- Gap: V2 wants one sentence per source plus one combining sentence. Not present.

![Why?](feature-map/screens/why-sheet.png)
![Why?, scrolled](feature-map/screens/why-sheet-3.png)

### Test it
- Status: not reached. No Test it button for the sample student's top move. No screenshot.

### Do this and Your plan
- Status: partly working. "Do this" was not tapped in the run (Why? sheet stayed open). Your plan shows "Your plan is empty. Tap "Do this" on a move to add it."

![Your plan](feature-map/screens/your-plan.png)

### In your account (balance details)
- Does: total, "How we worked it out", accounts list, date.
- Status: working, value wrong (W4).
- Sample student: "Monzo Current Account £0", "As of 16 Oct 2026".

![In your account](feature-map/screens/balance-details.png)

### Net worth details
- Does: chart Jul to Oct, "Down £493 since Jul", calculation, accounts.
- Status: partly working (W4).

![Net worth](feature-map/screens/net-worth-details.png)

### See all ("Your money")
- Does: spending by category, bills next 30 days, subscriptions, budgets, savings goals.
- Status: partly working (B4).
- Sample student:
  - Spending £1,419 in October 2026: shopping £549, housing £460, travel £94, groceries £71, entertainment £68, eating out £63, bills £46, education £42, fees £10, transport £9, subscriptions £6.
  - Bills next 30 days £58: Netflix £6, Ellie Shaw £38, Smarty £8, Spotify £6.
  - Subscriptions £12 a month: Netflix £5.99, Spotify £5.99.
  - Budgets: "You are offline" (B4). Savings goals: "No savings goals yet."

![See all](feature-map/screens/see-all.png)
![See all, scrolled](feature-map/screens/see-all-3.png)

### Coming up
- Status: working (max 3 items). Screenshot: see Money home, scrolled.

### Guess my spend
- Does: guess today's spend, reveal range, top 3 reasons, streak, past days, model error.
- Status: working.
- Sample student: guess £22.00; Penny £6.99, range £0 to £43; reasons "13°C and rainy +£1.18", "spent less than usual -£0.62", "Friday +£0.07"; "The model is off by £21.12 on a typical day".

![Guess my spend](feature-map/screens/guess-my-spend-result.png)

### How good is the spend guess?
- Status: working. "Off by £21.12 on a typical day", "59% of days fell inside the range", tested on 63 days, chart. Says "These figures describe mock data" (W1).

![Spend guess accuracy](feature-map/screens/spend-guess-accuracy.png)

### Habit score
- Status: not built on screen. API works: overall 42 (savings rate 0, months of cover 0, spend stability 0, discretionary share 70, subscription creep 93, debt pressure 88).

### Lessons and concepts collection
- Status: not reached (Collection tab not opened). No screenshot.

## Penny tab

### Penny tab, empty
- Does: full tab, intro bubble, 4 chips ("What if I lose my job?", "Can I afford a holiday in June?", "Why this move?", "What's happening with interest rates?"), input.
- Status: working.

![Penny empty](feature-map/screens/penny-tab-empty.png)

### Penny answer (personal question)
- Question: "Can I afford a night out this week?"
- Status: working. LLM is on. Label "Checked with your data". Short bubbles; follow-up chips "Next move", "Summary"; "Test it" chip.
- Answer: "you are set to be £131 short once £6 of bills are covered", "What you give up: nothing is safe to spend until 23 October...".
- Issue W10 (keyboard stays open).

![Penny answer](feature-map/screens/penny-tab-answer.png)

### See sources
- Status: working. Human names: "Your money data · sample data", "Bank of England · credit card rates · live", "ONS Nomis · unemployment · live", "HM Land Registry · live", "ONS · inflation (CPI) · live". New disclaimer at the bottom.

![Penny sources](feature-map/screens/penny-tab-sources.png)

### General answer
- Question: "What is a Lifetime ISA?"
- Status: partly working (W9). Content is correct: £4,000 a year, 25% bonus up to £1,000, 25% charge, open before 40.

![Penny general answer](feature-map/screens/penny-tab-general-answer.png)

### Ask Penny from Money
- Status: working. Switches to the Penny tab and answers about the move.

![Ask Penny from Money](feature-map/screens/ask-penny-from-money.png)

### Ask Penny from You
- Status: partly working. Opens a separate "Ask Penny" SHEET, not the Penny tab (ADR 0048). Shows "Earlier chats".

![Ask Penny from You](feature-map/screens/you-ask-penny.png)

## Play tab

### Play home
- Does: "Play solo", "Play with friends", "Join a game", Challenges / Collection.
- Status: partly working (B3, C5).

![Play tab](feature-map/screens/play-tab.png)

### Play solo, Choose a life
- Does: Play yourself (Recommended), God Mode (Demo payment, locked), presets, links "Play with friends", "Extras (Demo payment)", "Data sources".
- Status: working. **CONFLICT C3.**
- Presets on screen: Amira (NHS nurse, £24,800), Tom (investment banker, £92,000), Priya (second-year student, £7,800), Dan (plumber, £36,000), Maureen (retired), more below.

![Choose a life](feature-map/screens/life-character-select.png)
![Choose a life, presets](feature-map/screens/life-character-select-2.png)

### Play yourself form
- Status: partly working (W7, C4). Prefilled: name "You", born 1991, job "Student", North West, Manchester, renting, pay £0, savings £0, debts £0.

![Play yourself form](feature-map/screens/life-play-yourself-form.png)
![Play yourself form, money](feature-map/screens/life-play-yourself-form-3.png)

### God Mode
- Status: placeholder for V2. Locked; tap opens the store.

### Start year
- Status: working. "Priya, Student, Birmingham, born 2005", start year 2023, "Priya is 18 in 2023."

![Start year](feature-map/screens/life-start-year.png)

### Start life
- Status: **broken (B1).** Error alert, then back to Play.

![Start life error](feature-map/screens/start-life-error.png)

### Running life, event sheet, lesson, Job, Assets, People, Money, Activities menus, Rewind, Life summary, Real-life Decision
- Status: not reached because of B1. No screenshots.

### Quick Life, student paths, student challenges, Circles
- Status: not built (see list below). `/v1/paths` returns 404 on the local stack; `/v1/circles` returns an empty list.

## Rooms (Play with friends)

### Room setup ("Same Life")
- Does: join by code or QR; make a room with name, mode (Duel, Group, Class), preset life, start year.
- Status: partly working (B5). **CONFLICT C6.**

![Room setup](feature-map/screens/rooms-lobby.png)
![Room setup, load error](feature-map/screens/rooms-lobby-open.png)

### Lobby with QR, live room, results
- Status: not reached ("Make the room" disabled in the run). No screenshots.

### Scanner
- Status: working. Simulator: "This device has no camera. Type the room code instead."

![Scanner](feature-map/screens/rooms-scanner.png)

### Code entry
- Status: working. Unknown code shows "Room not found".

![Code entry](feature-map/screens/rooms-code-entry-error.png)

## You tab

### You home
- Does: profile, scores, two insight lines, "Your money and data", settings rows, version, credits.
- Status: partly working (W1, W6, W8, B6, C8).
- Sample student: "Age 21 · Student · Renting" (bug 7 looks fixed); "You spend £12 a month on 2 subscriptions"; "Your cash and savings cover 0 months of spending"; Concepts 0/50.
- No "New player" or "Reset demo" (judge mode not built). No presentation mode toggle on screen.

![You](feature-map/screens/you-tab.png)
![You, scrolled](feature-map/screens/you-tab-2.png)

### Connect your money (from You)
- Status: partly working (W6). Opens onboarding at Welcome page 1.

![Connect from You](feature-map/screens/you-connect-money.png)

### Where our data comes from
- Status: **broken (B2).**

![Sources](feature-map/screens/sources-screen.png)

### How Penny uses AI
- Does: where AI is used (Claude Opus for event text, Claude Sonnet for chat), what stays deterministic, how output is checked, what happens when AI fails.
- Status: working. Text matches ADR 0054. It lists test file paths, which is technical for a student.

![How Penny uses AI](feature-map/screens/how-penny-uses-ai.png)
![How Penny uses AI, end](feature-map/screens/how-penny-uses-ai-2.png)

### Penny Plus (store)
- Does: Rewind Pass £0.99, God Mode £1.99, Boss Mode £2.99, all "Demo payment"; restore.
- Status: working. **CONFLICT C10.**

![Store](feature-map/screens/store-paywall.png)

### Your plan
- Status: working (empty). Screenshot above in Money.

### How good is the advice?
- Status: working. **CONFLICT C7.**

![Advice evaluation](feature-map/screens/advice-evaluation.png)

### How good is the spend guess?
- Status: working. Screenshot above in Money.

### Account (sign out, reset, delete)
- Status: broken from You (B6). No screenshot.

### Debug menu
- Status: hidden in Demo builds (expected).

## Hidden or Playground-only

- Playground gallery (`-playground`, Mock config): 120+ fixture states. Not built or shot in this run. Includes mortgage Why? (`why.mortgage`) and the Priya nurse persona.
- Real-life Decision (mortgage), Bank connect, presentation mode: in code, not seen on screen (C11).
- Deep link `lifeline://join/CODE`: in code, not tested.

## Not built yet (DIRECTION_V2)

1. "Use a sample statement" with 4 student cards (API ready).
2. Student "Enter your numbers" form.
3. Judge mode: "New player" and "Reset demo" on You.
4. Weekly budget block on Money home.
5. Habit score on screen.
6. Why? "one sentence per source plus one combining sentence".
7. "Sample data" label (screens say "Mock data").
8. Lobby-first Play with friends (QR and code at once, names from the account).
9. Game picker: Money Quiz, Same Decision, Same Life.
10. Money Quiz.
11. Same Decision.
12. Quick Life.
13. Student start paths (`/v1/paths` 404 locally).
14. Student challenges.
15. Circles and habits leaderboard.
16. Penny weekly Circle recap.
17. "Where our data comes from": why there is no bank connection.
18. Removal of old presets, old challenges, mortgage evaluation, God or Boss Mode store items.

## Screens with no screenshot

- Upload a statement (picker), import progress, Next Move reveal, 3 tips.
- Test it (no testable move for this student).
- Concepts collection and lessons.
- Running life and everything after "Start life" (B1).
- Room lobby with QR, live room, results.
- Account screen (B6).
- Playground-only screens.
