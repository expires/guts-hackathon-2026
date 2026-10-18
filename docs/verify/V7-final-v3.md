# V7: final verifier run, Penny V3 (PENNY_V3_BUILD.md H4)

- Date: 2026-10-18, 08:51 to 09:00 BST.
- Live server: https://api-production-15615.up.railway.app (backend commit 8516f6a1).
- iOS tree: scratchpad `phone-build8` (commit a494ff2d). Test evidence: `pb8-test.log` and the xcresult `apps/ios/.build/DerivedData/Logs/Test/Test-Lifeline-2026.10.18_08-41-07-+0100.xcresult` in that tree.
- Scope: read-only. No code edits. No git writes. Live chat calls used: 3 of 6.
- Accounts: a new demo account (`POST /v1/auth/demo` with a random `device_id`) for each check.

## Summary

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | Fresh account empty | PASS | `/v1/me` `has_finance_data: false`, `finance_inputs: []`. `/v1/finance/home` `has_data: false`. `/v1/finance/profile`, `/overview`, `/v1/forecast` all 409 `no_finance_data`. |
| 2 | 10 students import, states, towns, no Monzo | PASS | `GET /v1/samples` returns exactly 10. All 10 imports 201. States: `loan_england`, `working`, `rich` = `running_short`; other 7 = `on_track`. Profile `character.town` equals the card `city` for all 10. No "Monzo" in any response. No "Pots" in samples, overview or profile (see note N1). |
| 3 | Forecast maths | PASS | 3 students checked exactly (table below). `steps` = 4, each with sources. Buffer 10% to 20% to 0% changes `buffer_amount`, `to_spend` and `per_week`. Invalid 7% is rejected with 422. |
| 4 | September non-rent vs A4 target, seed sources | PASS | All 10 within ±15% (table below). `docs/seed_sources.md` exists (135 lines). Every figure row has a source and URL, plus "official figure" or "example within ... range". |
| 5 | Penny on live | PASS | Library question: general answer with web search, 18.3 s, no "unavailable". What-if: `forecast_what_if` + `forecast`, verified, with numbers. "Explain my weekly budget": `forecast` tool, verified, with numbers. |
| 6 | Quick Life, 2 accounts, WebSocket | PASS | Room 0281: host and guest join, host `pick_game` `same_life` `{quick: true, quick_student_id: "qs-priya"}`, host `start` without guest `ready`. Both sockets get `started`, `status: playing`, both players have a `life_id`. |
| 7 | Learn | PASS | `GET /v1/learn`: 48 lessons, all `status: open`, none locked. Lessons `payslips` (#31) and `childcare` (last) open with 200. All 48 lessons open with 200. 86 fact objects, 0 without `why_it_matters`. |
| 8 | Onboarding end to end (simulator) | PASS (from last full run) | Makefile has no single-class test target, so no new run. xcresult 08:41 for a494ff2d: `OnboardingUITests` `testFullFlowInEnglish`, `testFullFlowInChinese`, `testManualEntryChecks` all Passed. Full run: 379 unit tests passed, 18 UI tests 0 failures, `** TEST SUCCEEDED **`. 396 passed, 1 skipped (`screens(language:)`). |
| 9 | No "Mock data" / "Sample data" text | PASS | xcresult: `NoMockTextUITests.testNoMockOrSampleDataTextOnAnyTab` Passed. All 12 `CutV3Tests` Passed, including `noMockOrSampleDataTextInTheApp` and `noCatalogKeyWithMockOrSampleDataIsUsed`. Grep of phone-build8 Swift: the remaining literals are in cut or non-rendering code only (see N4). |

## Item 2 detail

| Sample id | Name | Card city | Profile town | State (live) | A4 expected |
|---|---|---|---|---|---|
| scholarship | Amara Okoye | Sheffield | Sheffield | on_track | on track |
| scottish | Eilidh Fraser | Edinburgh | Edinburgh | on_track | on track |
| commuter | Priya Patel | Bolton | Bolton | on_track | on track |
| loan_england | Jordan Hughes | Newcastle | Newcastle | running_short | running short |
| working | Callum Reid | Leeds | Leeds | running_short | running short |
| mature | Grace Mensah | Birmingham | Birmingham | on_track | on track |
| international | Yutong Chen | Coventry | Coventry | on_track | on track |
| final_year | Sam Whitfield | Exeter | Exeter | on_track | on track |
| rich | Hugo Ashworth | Leeds | Leeds | running_short | running short |
| graduate | Lena Novak | London | London | on_track | on track |

## Item 3 detail (buffer 10%, live)

| Student | money_now | + income | - bills | - buffer | = to_spend | per_day x days | per_week | round(per_day x 7, 2) |
|---|---|---|---|---|---|---|---|---|
| scholarship | 1950.00 | 0.00 | 47.97 | 190.98 | 1711.05 | 20.13 x 85 = 1711.05 | 140.91 | 140.91 |
| commuter | 1400.00 | 480.00 | 467.97 | 141.28 | 1270.75 | 14.95 x 85 = 1270.75 | 104.65 | 104.65 |
| mature | 2750.00 | 2153.91 | 1721.97 | 318.29 | 2863.65 | 33.69 x 85 = 2863.65 | 235.83 | 235.83 |

- The identity also holds for 9 of 10 students. Exception: `working` (Callum), see N2.
- Steps (scholarship): `money_now` [Your statement], `bills` [Your statement], `buffer` [Your setting], `result` [Student Finance England payment dates].
- Buffer change (scholarship): 20% gives `buffer_amount` 380.53, `to_spend` 1521.50, `per_week` 125.30. 0% gives `buffer_amount` 0.58, `to_spend` 1901.45, `per_week` 156.59 (see N3).

## Item 4 detail (GET /v1/finance/spending?month=2026-09, all categories except `housing`)

| Student | Target | Actual | Diff |
|---|---|---|---|
| scholarship | 380 | 380.00 | +0.0% |
| scottish | 560 | 560.03 | +0.0% |
| commuter | 330 | 358.42 | +8.6% |
| loan_england | 620 | 620.15 | +0.0% |
| working | 650 | 650.00 | +0.0% |
| mature | 520 | 520.00 | +0.0% |
| international | 520 | 520.02 | +0.0% |
| final_year | 520 | 520.56 | +0.1% |
| rich | 1000 | 1000.03 | +0.0% |
| graduate | 700 | 700.01 | +0.0% |

- With `bills` also removed, all 10 stay within ±15% (largest -10.5%, final_year).

## Item 5 detail (POST /v1/chat/stream)

1. Fresh account, `screen: onboarding`, "How long does Edinburgh uni library stay open?": 18.3 s, `mode: general`, tool `web_search`, 2 bubbles of kind `general_knowledge`. Answer: Main Library at George Square open 24 hours, 7 days; smaller site libraries have shorter hours.
2. Amara (scholarship), `screen: forecast`, "Can I afford a £60 concert on the 30th?": 7.4 s, `mode: checked`, `verified: true`, tools `forecast_what_if` + `forecast`. Answer: yes, on track to 11 January, weekly spend £157 to £152, spare £626 to £566.
3. Same account, `screen: forecast`, "Explain my weekly budget": 2.6 s, `mode: checked`, `verified: true`, tool `forecast`. Answer: £1,950 now, minus £48 bills, until loan on 11 January, £157 a week, about £22 a day.
- The figures in answers 2 and 3 match the live forecast at the buffer then set (0%, from item 3): `per_week` 156.59.

## FAILs

None.

## Notes (not failures)

- N1. `/v1/finance/home` for 5 students contains the advice text "Keep it in a separate savings pot". This is a generic word, not the Monzo "Pots" feature. Samples, overview and profile have no match.
- N2. Callum (`working`): `money_now` -385.00, `to_spend` 0, `per_day` 0, `run_out_date` 2026-10-17 (the day before import). The engine sets buffer, per day and to spend to 0 when money minus bills is below 0 (`lifeline_engine/forecast.py` docstring line 28; ADR 0072 "shows the amount missing"). This is by design. A "run out" date in the past can read oddly on the card; BOSS may want to check the copy.
- N3. At 0% buffer, `buffer_amount` is 0.58, not 0. The engine rounds per day DOWN to pence and puts the remainder in the buffer (`forecast.py` lines 22 to 25), so money now minus bills minus buffer equals per day x days exactly. By design. The buffer step text should not say "£0" in that case; not checked on screen.
- N4. Swift literals with "Mock data"/"Sample data" in phone-build8 outside Debug/Preview/Fixtures/Mock: `GuessSpendView.swift`, `SpendAccuracyView.swift` (row gated by `state.showsCutFeatures`, false in every build), `NextMoveWhyViewModel.swift` (old Why?, cut), `FinanceMapping.badgeText` (only used as a Bool by `isSample`). `DataBadge` and `DemoDataBadge` render `EmptyView()`. All are on the `CutV3Tests.allowedPaths` list. The API still returns `meta.label: "Sample data"`; the app does not display it.
- N5. Item 8 used the 08:41 xcresult of the same tree (a494ff2d) instead of a new simulator run. The UI tests run on MockClient, not on the live server.
- N6. One test skipped in the full run: `screens(language:)`.

## Verdict

PASS. All 9 items pass on live backend 8516f6a1 and iOS tree a494ff2d. No blocker for the merge to main.

Scripts and raw responses: scratchpad `v7/` (`students.json`, `chat.log`, `tests.json`). Demo tokens are in those files; they are not secrets of the product but should not be committed.
