# V5 final: demo rehearsal against Railway

- Date: 2026-10-18, 09:12-09:20 BST.
- Target: https://api-production-15615.up.railway.app (main 3eae93c6 per BOSS; `/v1/health` gives no commit SHA, so the SHA is not confirmed). Health: postgres ok, redis ok, warming false.
- Method: API only, the same calls the app makes. Script: `/private/tmp/claude-501/-Users-ash-Workspace-dyhtg/d2613979-29cc-4f7b-8a9a-40abef46e06e/scratchpad/v5.py` (httpx + websockets from `services/api/.venv`). Raw logs: `run1.txt`, `run2.txt` in the same folder.
- Simulator and phone: NOT RUN (API rehearsal only).
- Latency budget (DIRECTION_V2.md line 150, ADR 0060): import < 10 s, Penny first bubble < 3 s, Quick Life round < 60 s, lobby join < 10 s, tab content < 0.5 s.

## Verdict: FAIL (Penny latency only; every functional step works)

## Results

| # | Step | Call | Time | Result |
|---|---|---|---|---|
| 1 | New demo account | POST /v1/auth/demo | 196-292 ms | PASS |
| 2 | Onboarding "Try Penny": "How long does the library stay open?" | POST /v1/chat/stream, screen=onboarding | reaction 229 ms, first bubble **3039 ms**, done 3104 ms | FAIL on budget (39 ms over 3 s). Answer correct, mode=general, no personal numbers. |
| 3 | Samples list | GET /v1/samples | 202 ms | PASS, 10 students. Callum=`working`, Eilidh=`scottish`. |
| 4 | Import Callum | POST /v1/samples/working/import | 667 ms | PASS, 187 transactions, 3.6 months |
| 5 | Callum forecast card | GET /v1/forecast | 253 ms | PASS. budget_line "You are £385 short before 23 October", state running_short. See finding F3 on the headline. |
| 6 | Import Eilidh (new account) | POST /v1/samples/scottish/import | 489 ms, 651 ms | PASS, 129 transactions |
| 7 | Eilidh forecast card | GET /v1/forecast | 232-300 ms | PASS. "You'll make it to 26 October" / "You can spend £930 until 26 October (about £116 a day)" |
| 8 | Buffer change (Eilidh 10% -> 20%) | PUT /v1/forecast/settings then GET /v1/forecast | 215 ms + 230 ms | PASS. Buffer £103.36 -> £206.72; card £930 -> £827. Sum checks: 1,033.60 - 0 - 103.36 = 930.24 (to_spend). |
| 8b | Buffer change (Callum) | same | 199 ms | No visible change: Callum is overdrawn, so buffer is £0 at any %. Use Eilidh for the buffer demo. |
| 9 | Category list | GET /v1/finance/spending | 195-205 ms | PASS. Categories sum 844.71 = total 844.71 (Eilidh). |
| 10 | Category detail x3 (housing, groceries, bills) | GET /v1/finance/spending/{category} | 193-215 ms | PASS. Transactions = weeks = total = list amount for all 3. |
| 11 | Chat: "Explain my weekly budget" (Callum) | POST /v1/chat/stream, screen=forecast | reaction 193 ms, first bubble **2526 ms**, done 2643 ms | PASS. mode=checked, numbers highlighted to forecast facts. |
| 12 | Chat: "Can I afford a £60 concert on the 30th?" (Callum) | POST /v1/chat/stream, screen=forecast | reaction 183 ms, first bubble **7006 ms**, done 7016 ms | FAIL on budget (7.0 s vs 3 s). Answer correct, mode=checked. |
| 13 | Learn path | GET /v1/learn | 192-225 ms | PASS. 48 lessons. |
| 14 | Every lesson opens | GET /v1/learn/lessons/{id} x48 | about 190-300 ms each | PASS. 48/48 open, 0 facts without "Why this matters to you". |
| 15 | One lesson attempt | POST /v1/learn/lessons/needs-vs-wants/attempts | 201 ms | PASS. 1/3 correct (deliberate first choices), passed=false, pass_mark 2. |
| 16 | Quick Life room: create + guest lookup | POST /v1/rooms, GET /v1/rooms/{code} | 205 ms, 180 ms | PASS |
| 17 | Both players join (WS) | `join` -> `welcome` x2 | 1381 ms from create | PASS (< 10 s) |
| 18 | Host starts without guest "ready" | `pick_game` same_life quick (qs-priya) -> `start` -> `started` x2 | 288 ms | PASS, status playing, both lives created by the room |
| 19 | Play both lives to the end, `finish` | /v1/lives/{id}/age, /choices, WS `finish` -> `ranking`, `finished` | 13.2 s total API time | PASS (< 60 s). 2 events per player. winner_line "Player 1 wins with an INDEX of 100 and a habit score of 88 out of 100." |

Other reads: GET /v1/me 280 ms, GET /v1/finance/home 332 ms, GET /v1/paths 194 ms. All reads were under 0.5 s.

## Findings

- F1 (FAIL, latency). What-if chat first bubble 7006 ms against a 3 s budget. File: `services/api/lifeline_api/routes/chat.py` (stream, line 105) and the what-if tool path in `services/api/lifeline_explain/`. Owner: W5 (Penny), W4 (route). The reaction arrives at 183 ms, so the user sees activity; the delay is the tool + model step.
- F2 (FAIL, marginal latency). Onboarding library question first bubble 3039 ms (budget 3 s). One sample only; within normal model variance. Owner: W5.
- F3 (low, copy). Callum headline says "Your bills take all your money before 23 October", but bills before 23 October are £0. The cause is a £385 overdraft. `services/api/lifeline_engine/forecast.py:577-578` uses this headline whenever `m.left <= 0`. The STATUS demo line ("You are £385 short before 23 October") is the budget_line, so the demo still shows it. Owner: W2.
- F4 (low, observation). The forecast `result` step `amount` is `per_week` (£813.96 for Eilidh), not `to_spend` (£930.24), although `budget_period` is `until_next_money`. The step text explains it ("£930.24 ÷ 8 days = £116.28 a day, £813.96 a week"). `services/api/lifeline_engine/forecast.py:678`. The iOS maths view (`Features/Forecast/ViewModels/ForecastMathsViewModel.swift`) builds its rows from forecast fields, so the app probably does not show this amount. NOT confirmed on screen. Owner: W2.
- F5 (low, observation). Two `/v1/lives/{id}/age` calls took 2990 ms and 2155 ms (others about 200 ms). The round still fit the budget. Owner: W3/W4.
- Demo note: run the buffer demo on Eilidh, not Callum (Callum's buffer is £0 at every %).

## NOT RUN

- Simulator and iPhone UI steps (QR camera scan, tab switch timing on device, "See the maths" screen rendering).
- Repeat chat timings (limit of 3 Penny calls used).
- Deployed commit SHA check (no SHA in /v1/health).


## BOSS re-check after the fix (09:48)

F1 fixed by commit e73b4f72: when Penny calls forecast_what_if, the stream sends an acknowledgement bubble at once (no numbers), then every checked answer bubble. Live `/v1/chat/stream`, "Can I afford a £60 concert on the 30th?" (scholarship, screen forecast): first bubble 2.69 s, total 7.06 s, answer bubbles with engine numbers. F2 (library question 3.04 s once) is model variation; the earlier run measured it under budget. Verdict after the fix: PASS.
