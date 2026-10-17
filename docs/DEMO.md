# Demo script

## User story

**Yaffy**, **[age]**, **[student/working]** in **[city]**.

- He banks with Monzo.
- He holds a Stocks and Shares ISA at Trading212.
- He rents.
- His question: **"What is my next money move?"**
- Penny reads his money, adds live UK data, and gives him one move with its gain, its trade-off ("What you give up"), its worst case, its confidence and its evidence. He can play that move through a past shock before he makes it in real life.

Status (ADR 0043):

- The three bracketed values are placeholders until Yaffy confirms them.
- The demo runs on Yaffy's real connected data after the Yaffy merge (ADR 0036). Until then, it uses the Mock and test persona Priya Shah (`homeowner-leeds`). Priya is not the named user.
- There is no planned headline. The demo follows the engine's actual top move.

The demo answers one question: **"What is my next money move?"** It opens with the Next Move story on the Money tab. Then it plays the four life scenes from `BUILD_SPEC.md` section 7. Total time: about 8 minutes.

Rule (ADR 0020): **the demo follows the engine.** Narrate what the API returns on the day. Do not read a fixed answer from this page. The "Expected output" blocks show one run of the stack on 2026-10-17 so you know what to look for.

All API calls follow `contracts/openapi.yaml`. Errors always have the shape `{"error": {"code", "message", "source"}}`. An endpoint that is not built yet returns `501` with `code: "not_implemented"`.

## Tier status

| Part | Needs | Works now | Until it is built |
|---|---|---|---|
| Opening: Next Move | `/v1/next-move`, `/v1/next-move/test`, `/v1/plan`, `/v1/concepts` | Yes (Tier 1) | n/a |
| 1 Same crash | lives, age, choices, summary | Yes | n/a |
| 2 Same Life room | `/v1/rooms`, WebSocket (Tier 2) | No, 501 | Two terminals, same preset and seed |
| 3 Rewind | `/v1/lives/{id}/rewind` | Yes (Tier 1). Rewind Pass purchase is Tier 2 (501) | Second rewind: show the `402` and say the pass is Tier 2 |
| 4 Play yourself and decision | `/v1/decisions`, `/v1/evaluation` | Yes (Tier 1) | n/a |
| Life tab actions | `/v1/lives/{id}/actions` | Yes (Tier 1) | n/a |

## Before the demo (15 minutes before)

1. Start the stack:
   ```bash
   make up          # builds and starts api, worker, postgres, redis; waits for /v1/health
   ```
2. Load the demo data:
   ```bash
   make demo-seed   # runs python -m seed.load inside the api container; about 2 minutes on a cold cache
   ```
   - The seed signs in with device id **`demo-presenter-01`**. Lives, plan and Next Move belong to the signed-in device, so the app and your terminal must use the same id. This device maps to the fixture persona `homeowner-leeds` (ADR 0021).
   - The first `GET /v1/next-move` after a restart takes longer because the LLM rewords the text (ADR 0019). The seed warms that cache, so the live demo call is fast.
   - To use another id: `docker compose exec -T -e DEMO_DEVICE_ID=<id> api python -m seed.load`.
   - To show "Do this" adding the first plan item live, the device must have no plan yet. `--no-plan` only skips the plan step; it does not clear an existing plan, and no endpoint removes a plan item. Use one of these:
     - Preferred (no reset): device ids `demo-presenter-01` to `demo-presenter-05` all map to Priya (`homeowner-leeds`). Seed `demo-presenter-02` without a plan, then use that id in the app (`-demoDeviceID demo-presenter-02`) and in your terminal (`export DEMO_DEVICE_ID=demo-presenter-02` before `source services/api/seed/demo.sh`):
       `docker compose exec -T -e DEMO_DEVICE_ID=demo-presenter-02 api python -m seed.load --no-plan`
       For another rehearsal, use the next unused id (`-03`, `-04`, `-05`).
     - Fallback (deletes all data): `docker compose down -v && make up`, then `docker compose exec -T api python -m seed.load --no-plan`.
   - A plan item keeps the action text from the moment it was added. An old item can show older wording than the card.
   - The loader prints a JSON manifest. Keys:
     - `device_id`: the id that owns the seeded data.
     - `next_move`: action, headline, impact, confidence label, test period, options (`*` marks the recommended one), evidence, runners-up.
     - `next_move_test`: Test it period, summary, and one outcome per option with its `life_id`.
     - `plan`: plan items and total yearly impact.
     - `lives.nurse-leeds-2006`, `lives.banker-london-2006`: fresh lives for scene 1.
     - `lives.nurse-leeds-2008-fallback`, `lives.banker-london-2008-fallback`: the same lives, aged to 2008 with default choices.
     - `lives.<key>.first_decision_id`: the first past decision of that life.
     - `lives.self-2020`: a "Play yourself" life for Priya (from `/v1/finance/profile`), aged to the present (2026). `self_profile_from` says which profile was used.
     - `decision`: the Real-life Decision for the `self-2020` profile.
     - `rooms`: present only when rooms are built.
     - `skipped`: steps whose endpoint returned `501 not_implemented`. Today this lists only `scene2 room 2021`. The exit code stays 0.
3. Load the shell helpers from the repo root (bash or zsh, needs `curl` and `jq`):
   ```bash
   source services/api/seed/demo.sh   # signs in as $DEMO_DEVICE_ID (default demo-presenter-01); sets BASE, TOKEN
   ```
   The file defines four commands:
   - `api ...`: curl with the bearer token.
   - `new_life PRESET YEAR SEED`: creates a preset life and prints its id.
   - `play_to ID YEAR [FIRST_CHOICE]`: answers open events with the default choice and taps AGE until YEAR. It prints `year  title  -> choice  [source:series=status, ...]` for every event. `FIRST_CHOICE` overrides the first event's choice; `alt` picks its first non-default choice. Do not pipe it into `head`: that stops the run early.
   - `path ID`: prints net worth, autopilot net worth and Index per year from `GET /v1/lives/{id}/summary`.
4. Check data sources:
   ```bash
   curl -s $BASE/v1/sources | jq -r '.sources[] | "\(.id)  \(.status)  \(.coverage)"'
   ```
   `live` or `cached` is good. `mock` means no key or no data; the app labels it.
5. Start the iOS app on the simulator with the same device id. Default simulator: **iPhone 18 Pro Max** (`make ios-build`; override with `SIM="..."`). Use one of these:
   - Launch argument: `-demoDeviceID demo-presenter-01` (Xcode: Product > Scheme > Edit Scheme > Run > Arguments).
   - Debug menu (Debug builds): on character select, long-press the version label. Tap **Use presenter id**. The same menu has the mock-client toggle.
   - Without either, the app signs in with its own anonymous device id. It then shows a different fixture persona and only lives it creates.
   - Do not use the `Playground` scheme for the demo. It runs the mock client with fixture data, not the stack.
6. The app opens on the **Money** tab (tabs: Money, Life, Play, You; ADR 0016). Money data is labelled "Sample data" until bank OAuth (Tier 2).

## Check before presenting (opening)

Run this before every demo. Narrate only what it prints.

```bash
source services/api/seed/demo.sh

# 1. The card
api $BASE/v1/next-move | jq '{status: .meta.data_status, label: .meta.label} + (.top | {id, action, headline, days_left, deadline,
  impact_per_year, worst_case_per_year, confidence_label, test_period: .test_period.label, concept_id,
  options: [.options[] | "\(.label)\(if .is_recommended then " (recommended)" else "" end)"],
  evidence: [.evidence[].text], sources: [.sources[] | "\(.source):\(.series_id)=\(.status)"]})'

# 2. Test it (replace the move id if the card shows another one)
api -X POST $BASE/v1/next-move/test -d '{"move_id":"fix_mortgage"}' | jq '{period: .period.label, summary, evidence_sentence,
  outcomes: [.outcomes[] | {label, is_recommended, end_net_worth, total_cost, missed_payments, worst_year, index, life_id}]}'

# 3. Why? (lesson for the card's concept_id, with the personal sentence)
api $BASE/v1/concepts | jq '.concepts[] | select(.id=="interest-rates") | {title, summary, lesson: {title: .lesson.title,
  sentences: .lesson.sentences, personal: .lesson.personal, chart_source: .lesson.chart.source}}'

# 4. Do this
api -X POST $BASE/v1/plan -d '{"move_id":"fix_mortgage"}' | jq '{action, impact_per_year, status}'
api $BASE/v1/plan | jq '{items: [.items[].action], total_impact_per_year}'

# 5. How good is the engine? (honest accuracy, ADR 0023)
api $BASE/v1/next-move | jq '.backtest'
```

Expected output (2026-10-17, persona `homeowner-leeds`, Priya, Leeds):

| Field | Value |
|---|---|
| `meta` | `mock`, "Sample data" (fixture bank data) |
| `action` | "Take a tracker" (equals the recommended option label) |
| `headline` | "Your current deal finishes in 165 days" (deadline 2027-03-31; the LLM may reword it, the 165 days stay) |
| `impact_per_year` | £3,078.94 (expected, vs doing nothing) |
| `worst_case_per_year` | £2,550.96 |
| `confidence_label` | "In 8 of 10 similar cases this was the best choice" |
| Evidence 1 | Fixed rate 2.09% runs out in 165 days, then about 6.58%; a 2-year fix is 5.13% and a 5-year fix 4.98% today |
| Evidence 2 | 20 people like you in similar past periods (2005-2011, 2017-2022): "Take a tracker" saved £3,079 a year on average vs doing nothing |
| Evidence 3 | For a mortgage like yours in the 2021-2023 rate shock, "Take a tracker" saved £4,593 a year vs doing nothing, while "Fix for 5 years" saved £7,038 a year. Test it replays your whole life in those years, so its totals may be different (wording can vary; numbers do not) |
| Runners-up | "Pay off £3,421 of card debt from savings"; "Cut transport to £51 a month" |
| Sources | `boe` IUMBEDR, IUMBV34, IUMBV42, IUMTLMV, IUMBV48 all `live`; `bank:fixtures:homeowner-leeds=mock` |
| Test it | 2021-2023 rate shock (stress test). Total cost: tracker £33,245; fix 5 years £26,005; fix 2 years £25,966; do nothing £38,944. Summary: "Take a tracker" cost £7,280 more than "Fix for 2 years". No missed payments. End net worth on `demo-presenter-02` (preferred device): tracker £133,828; fix 5 years £141,004; fix 2 years £141,071; do nothing £131,697 |
| Why? | "Rates set the bill". Personal: "Your mortgage rate is 2.09% and your fixed deal ends in 165 days." Chart source `boe IUMBV34 live` |
| Plan | One item, total £3,078.94 a year. The item text is the card action at the time it was added |
| Backtest | 28 deal-end years 1995-2022: engine 64.3%; "always fix 2 years" 14.3%; best constant rule "always take a tracker" 71.4% |

Test it end net worth depends on the device's own life history, so it differs between device ids (for example `demo-presenter-01` shows tracker £125,285, fix 2 years £132,474). Total costs and the summary are the same on every device. Narrate the live output of the device you present with.

These values change when W2 changes the engine. Re-run the check and update this table before each demo.

## Opening: Your next money move (about 2 minutes)

Say: "Penny. Your money, played forward. Many sources. One answer: your next money move. Play it before you live it."

| Step | Tap | API call | Say (from the check output) |
|---|---|---|---|
| 1 | The app opens on **Money**. Point at the "Sample data" label and the balance, spending and bills. | `GET /v1/finance/overview`, `/spending`, `/bills` | "This is Priya's money. Today it is sample bank data, labelled." |
| 2 | Point at the **Next Move** card at the top. | `GET /v1/next-move` | Read the headline (today "Your current deal finishes in 165 days"), the action, the yearly impact and the confidence label. |
| 3 | Point at the source chips on the card. | `top.sources[]` | "Bank of England rates, live today. Her bank data is sample data." |
| 4 | Tap **Test it**. Two to four lives play side by side through the stress period. | `POST /v1/next-move/test` `{"move_id":"<top.id>"}` | Read the period label and the summary. Then compare total cost per option. |
| 5 | Tap **Why?**. The lesson opens with the evidence. | `GET /v1/concepts` (lesson for `concept_id`), card `evidence[]` | Read the personal sentence and evidence 3. |
| 6 | Tap **Do this**. | `POST /v1/plan` `{"move_id":"<top.id>"}`, then `GET /v1/plan` | "One move, in her plan, worth about £3,079 a year on average." |

The honest part (say it; it is the point of the stress test):
- "On average, in past periods like today, a tracker was the best choice in 8 of 10 cases. In a 2022-style rate shock, a fixed deal would have cost less. The card shows both numbers, and Test it shows the shock year by year. You choose with the risk in view."
- Use the Test it numbers from your check (today: the tracker cost £7,280 more than a 2-year fix over 2021-2023).
- If asked why the Test it totals differ from the card's £ a year: "The card compares the mortgage alone, per year. Test it replays Priya's whole life in 2021 to 2023: pay, bills and every other event. So its totals are larger and can rank the fixes differently. Evidence point 3 says this on the card."
- If the card shows "Fix for 5 years" instead, say that. Both are valid when the numbers support them (ADR 0020).

Accuracy (only if asked, or on the backtest screen):
- "We test the engine on 28 past deal-end years. It beats 'always fix for 2 years' (64% vs 14%). It does not beat the simple rule 'always take a tracker' (71%) on this data. We show that openly." (ADR 0023, `docs/prediction.md`.)
- Two backtests, two rules: the Next Move backtest (64.3%) tests the Next Move engine with its stress-period regret rule. `/v1/evaluation` (71.4%, scene 4) tests the Real-life Decision engine `decide()`, which picks the tracker every year. Do not mix the two numbers.

Fallback:
- Slow first call: the seed warms the LLM cache. If the stack restarted after seeding, run `make demo-seed` again.
- No LLM (key missing or timeout): the headline and evidence show the template wording (for example "Your deal ends in 165 days"). The action and the numbers do not change.
- Test it lives open in the **Life** tab. Their ids are in the Test it response and in `manifest.next_move_test.outcomes[].life_id`.

## Scene 1: Same crash, different lives (2006 to 2008)

Say: "Aladdin stress tests portfolios. We stress test a life. Here are two people in 2006, on the same seed."

### Check before presenting (scene 1)

```bash
source services/api/seed/demo.sh
N=$(new_life nurse-leeds 2006 424242); B=$(new_life banker-london 2006 424242)
play_to $N 2010; play_to $B 2010      # every event with its cited sources
path $N; path $B                     # net worth 2006 to 2010 for both lives
```

Read the output for:
- The 2008 events in each life.
- The sources and status on each event. Do not name a source unless an event cites it. `yahoo:^FTAS=mock` means the share-price fall uses mock data.
- The year-by-year net worth of each life. Say "fell" only if the number falls.

Expected output (2026-10-17, seed 424242, default choices):

| Life | 2008 events (sources) | Net worth 2007 | 2008 | 2010 |
|---|---|---|---|---|
| Amira, nurse, Leeds, renting | "The stock market crashes" (`yahoo:^FTAS=mock`); "Savings rates fall" (`boe:IUMBEDR=live`); "House prices have fallen" (`landregistry=live`) | -£5,135 | -£1,366 | £11,504 |
| Tom, banker, London, mortgage | "Your mortgage deal is ending" (`boe` IUMBEDR, IUMBV34, IUMBV42, IUMTLMV, IUMBV48 `live`); "House prices are falling" (`landregistry:ukhpi-annual-change=live`); "The stock market crashes" (`yahoo=mock`) | £317,633 | £255,478 | £421,374 |

### Steps

| Step | Tap | API call |
|---|---|---|
| 1 | **Life** tab. Character select. Tap **Amira, nurse, Leeds**. Set start year **2006**. Tap **Start**. | `POST /v1/lives` `{"mode":"preset","preset_id":"nurse-leeds","start_year":2006,"seed":424242}` |
| 2 | Tap **AGE**. An event sheet opens. | `POST /v1/lives/{id}/age` |
| 3 | Pick a choice. Point at the source chip on the sheet. | `POST /v1/lives/{id}/choices` `{"event_id":"...","choice_id":"..."}` |
| 4 | Tap **AGE** until **2008**. Show the 2008 events and the Lesson screen. | `POST /v1/lives/{id}/age`, then `/choices` |
| 5 | Optional: open the **Job** action menu and tap **Ask for a raise**. | `POST /v1/lives/{id}/actions` `{"tab":"job","action_id":"ask_raise"}` |
| 6 | Go back. Start **Tom, banker, London**, 2006, same seed. Tap **AGE** to 2008. | same calls with `"preset_id":"banker-london"` |
| 7 | Compare Money, Index and net worth for the two lives. | `GET /v1/lives/{id}` and `GET /v1/lives/{id}/summary` for each |

Narration (matches the expected output; change the numbers to match your check):
- "Same year, same seed, different person and place. Every event cites its source and says whether the data is live, cached or mock."
- "2008. Bank of England data: Bank Rate falls. Land Registry data: house prices fall."
- "Tom owns a London flat with a mortgage. His net worth falls from £317,633 to £255,478."
- "Amira rents in Leeds. She owns no house, so the price fall does not hit her. Her net worth keeps rising, from -£5,135 to -£1,366."
- "Same crash, different lives. Who you are and where you live decides what a crash does to you."
- The share-price fall uses `mock` data (`yahoo`). Do not call it real market data.
- Do not claim a job loss unless the check shows one.

Fallback:
- If ageing is slow or an event fails, open the pre-aged lives from the manifest:
  ```bash
  path <nurse-leeds-2008-fallback id>; path <banker-london-2008-fallback id>
  ```
- If a data source is down, the event still shows. Its source chip reads `cached` or `mock`.

## Scene 2: A judge joins a Same Life room (2021 to 2023 rate shock)

Say: "Now you play. Same character, same seed, same events. You go at your own pace."

Character: **Tom, banker, London**. He has a mortgage, so the 2023 deal end reaches him. (Amira rents and gets no mortgage event in 2021 to 2023.)

When rooms are built (Tier 2):

| Step | Tap (presenter) | Tap (judge) | API call |
|---|---|---|---|
| 1 | **Play** tab. Tap **Create room**, mode **Group**, character **Tom**, year **2021**. A QR code shows. | | `POST /v1/rooms` `{"mode":"group","host_name":"Host","preset_id":"banker-london","start_year":2021}` |
| 2 | | Scan the QR with the iPhone camera. The app opens on `lifeline://join/{code}`. Enter a name. | `GET /v1/rooms/{code}`, then WebSocket `/v1/rooms/{code}?token={jwt}`, send `{"type":"join","name":"Judge"}` |
| 3 | Host taps **Start**. | | WS `{"type":"start"}`; server sends `started` |
| 4 | Both tap **AGE** through 2021, 2022, 2023. The rival strip shows the other player's age, net worth and Index. | same | Each player: `POST /v1/lives` with `"room_code"`, then `/age` and `/choices`. After each AGE: WS `{"type":"progress",...}`; server broadcasts `rival` |
| 5 | At 2023, both tap **Finish**. Compare ribbons, Index and net worth. | same | WS `{"type":"finish"}`; `GET /v1/lives/{id}/summary` for each |

- If the manifest has `rooms.rate-shock-2021.code`, a room is ready. Type the code in **Join with code** on a second simulator if there is no camera.

Until rooms are built (works now): two terminals, one per player. A room shares a seed; here both players type the same seed.

```bash
# Terminal 1 (presenter)
source services/api/seed/demo.sh
P=$(new_life banker-london 2021 777001); play_to $P 2023; path $P

# Terminal 2 (judge, own device id)
export DEMO_DEVICE_ID=judge-01; source services/api/seed/demo.sh
J=$(new_life banker-london 2021 777001); play_to $J 2023 alt; path $J
```

- Expected events (2026-10-17): 2022 "Bonus season" (`yahoo=mock`), "Energy bills jump" (`ons:D7GT=live`), "The price cap rises" (`octopus=mock`); 2023 "Your mortgage deal is ending" (`boe` rates `live`).
- With default choices in both terminals, the event lists are identical. Same seed gives the same life.
- With `alt` the judge takes a different first choice. Show where the lists and net worth paths split.

## Scene 3: Rewind a bad choice

Say: "Everyone makes a bad call. Here you can go back and see the other path."

| Step | Tap | API call |
|---|---|---|
| 1 | Open the nurse life. Tap the timeline. Pick a past choice. | `GET /v1/lives/{id}` (read `history[].decision_id`) |
| 2 | Tap **Rewind**. The first rewind in a life is free. | `POST /v1/lives/{id}/rewind` `{"decision_id":"..."}` |
| 3 | The life returns to that year with the other choice taken. Answer the next open events. | `RewindResult.life.pending_events`, then `POST /v1/lives/{id}/choices` |
| 4 | The screen shows the Index and net worth of the abandoned path next to the new one. | `RewindResult.abandoned_index`, `RewindResult.abandoned_net_worth`, `life.index.value` |

- With the manifest:
  ```bash
  api -X POST $BASE/v1/lives/<nurse-leeds-2008-fallback id>/rewind -d '{"decision_id":"<first_decision_id>"}' \
    | jq '{abandoned_index, abandoned_net_worth, year: .life.year, index: .life.index.value, open: [.life.pending_events[].title]}'
  ```
  Expected (2026-10-17): rewind of `ev-2007-1` returns the life to 2007, abandoned net worth -£1,365.65, with the remaining 2007 events open.
- A second rewind in the same life returns `402` with `code: "payment_required"` ("You have used your free rewind. A Rewind Pass gives unlimited rewinds."). The Rewind Pass purchase (`POST /v1/purchases/verify`) is Tier 2 and returns 501 today. Show the 402 message and say the pass is a demo payment in Tier 2.
- To compare two full paths side by side (works now):
  ```bash
  A=$(new_life nurse-leeds 2006 424242); B=$(new_life nurse-leeds 2006 424242)
  play_to $A 2010; play_to $B 2010 alt; path $A; path $B
  ```

## Scene 4: Play yourself to today, then one clear decision

Say: "The game ends where your real life is now. One clear decision, with evidence."

| Step | Tap | API call |
|---|---|---|
| 1 | **Life** tab. Character select. Tap **Play yourself**. The form is prefilled from Priya's Money data. | `GET /v1/finance/profile`, then `POST /v1/lives` `{"mode":"self","start_year":2020,"character":<profile.character>}` |
| 2 | Tap **AGE** until the present (2026). | `POST /v1/lives/{id}/age` until `life.reached_present` is `true` |
| 3 | The **Real-life Decision** screen opens. Read the headline. | `POST /v1/decisions` `{"profile":<profile.profile>,"life_id":"..."}` |
| 4 | Point at the evidence line and the source chips with `live`/`cached`/`mock` status. | `Decision.evidence`, `Decision.sources[]` |
| 5 | Open **How good is this?** Show the hit rate against both baselines. | `GET /v1/evaluation` |

Check before presenting:

```bash
source services/api/seed/demo.sh
api $BASE/v1/lives/<self-2020 id> | jq '{year, age, reached_present, net_worth: .finances.net_worth, index: .index.value}'
api $BASE/v1/finance/profile | jq '.profile'          # Priya's real profile from the Money data
api $BASE/v1/finance/profile | jq '{profile}' | api -X POST $BASE/v1/decisions -d @- \
  | jq '{headline, action, evidence: .evidence.sentence, sources: [.sources[] | "\(.source):\(.series_id)=\(.status)"]}'
api $BASE/v1/evaluation | jq '{n, hit_rate, baseline, baseline_hit_rate}'
```

Expected (2026-10-17):
- Profile: age 38, Yorkshire and the Humber, income £35,947, savings £6,850, card debt £3,421, mortgage £180,000 on a £240,000 home, 23 years left, deal ends in 6 months.
- `self-2020` life: Priya, age 38 in 2026, `reached_present: true`.
- Decision: "Take a tracker deal.", "8 in 10 twins in similar past periods did better." Sources: `boe`, `ons`, `landregistry` live; `nomis` NM_17_5 and NM_30_1 `mock`.
- Evaluation: 28 years, hit rate 71.4%; baseline "always fix 2 years" 14.3%; the baseline text names the best constant rule "always take a tracker" at 71.4%.
- Say: "It beats the naive rule. It ties the best simple rule on this data. We say so." (ADR 0023.)

Fallback:
- Use the pre-aged `self-2020` life from the manifest. Its decision is in the manifest under `decision`.
- No bank keys: Money data and the profile are labelled sample data.

## Reset

```bash
make down                  # stops the stack; the postgres volume keeps data
docker compose down -v     # also deletes demo lives, plan and rooms
```

Run `make up && make demo-seed` again for a clean set.
