# Demo script

Four scenes from `BUILD_SPEC.md` section 7. Each scene gives the taps in the app, the API calls behind them, and a fallback. Total time: about 6 minutes.

All API calls follow `contracts/openapi.yaml`. Errors always have the shape `{"error": {"code", "message", "source"}}`. An endpoint that is not built yet returns `501` with `code: "not_implemented"`.

## Tier status

| Scene | Needs | Works now (Tier 0) | Until it is built |
|---|---|---|---|
| 1 Same crash | lives, age, choices, summary | Yes | n/a |
| 2 Same Life room | `/v1/rooms`, WebSocket (Tier 2) | No, 501 | Two terminals, same preset and seed |
| 3 Rewind | `/v1/lives/{id}/rewind` (Tier 1) | No, 501 | Two lives, same seed, different first choice |
| 4 Real-life Decision | `/v1/decisions` (Tier 1) | No, 501 | Seeded `self-2020` life at the present, plus `/v1/sources` |

## Before the demo (10 minutes before)

1. Start the stack:
   ```bash
   make up          # builds and starts api, worker, postgres, redis; waits for /v1/health
   ```
2. Load the demo data:
   ```bash
   make demo-seed   # runs python -m seed.load inside the api container
   ```
   - The seed signs in with device id **`demo-presenter-01`**. Lives belong to the signed-in device, so you must use the same id to see them.
   - To use another id: `docker compose exec -T -e DEMO_DEVICE_ID=<id> api python -m seed.load`.
   - The loader prints a JSON manifest. Keep it open. Keys:
     - `device_id`: the id that owns the seeded lives.
     - `lives.nurse-leeds-2006`, `lives.banker-london-2006`: fresh lives for scene 1.
     - `lives.nurse-leeds-2008-fallback`, `lives.banker-london-2008-fallback`: the same lives, aged to 2008 with the default choice at every event.
     - `lives.<key>.first_decision_id`: the first past decision of that life.
     - `lives.self-2020`: a "Play yourself" life aged to the present (2026).
     - `rooms`, `decision`: present only when those endpoints are built.
     - `skipped`: steps whose endpoint returned `501 not_implemented`. In Tier 0 this lists `scene2 room 2021` and `scene4 real-life decision`. The exit code stays 0.
3. Load the shell helpers (bash or zsh, needs `curl` and `jq`):
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
5. Start the iOS app on the simulator with the same device id, so it sees the seeded lives. Default simulator: **iPhone 18 Pro Max** (`make ios-build`; override with `SIM="..."`). Use one of these:
   - Launch argument: `-demoDeviceID demo-presenter-01` (Xcode: Product > Scheme > Edit Scheme > Run > Arguments).
   - Debug menu (Debug builds): on character select, long-press the version label. Tap **Use presenter id**. The same menu has the mock-client toggle.
   - Without either, the app signs in with its own anonymous device id and shows only lives it creates.
   - Do not use the `Playground` scheme for the demo. It runs the mock client with fixture data, not the stack.

## Check before presenting (scene 1)

The sim and data change during the build. Run this before every demo and narrate only what it prints.

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

Expected output (2026-10-17 stack, seed 424242, default choices). If your output differs, narrate your output:

| Life | 2008 events (sources) | Net worth 2007 | 2008 | 2010 |
|---|---|---|---|---|
| Amira, nurse, Leeds, renting | "The stock market crashes" (`yahoo:^FTAS=mock`); "Savings rates fall" (`boe:IUMBEDR=live`, Bank Rate 5.50% to 2.00%); "House prices have fallen" (`landregistry:ukhpi-annual-change=live`, Yorkshire and the Humber -13.4%) | -£6,163 | -£2,401 | £10,691 |
| Tom, banker, London, mortgage | "Your mortgage deal is ending" (`boe:IUMBV34`, `IUMBV42=live`); "House prices are falling" (`landregistry=live`, London -14.8%, -£68,386 on his flat); "The stock market crashes" (`yahoo=mock`); no bonus in 2008 | £317,645 | £255,490 | £421,743 |

## Scene 1: Same crash, different lives (2006 to 2008)

Say: "Aladdin stress tests portfolios. We stress test a life. Here are two people in 2006, on the same seed."

| Step | Tap | API call |
|---|---|---|
| 1 | Character select. Tap **Amira, nurse, Leeds**. Set start year **2006**. Tap **Start**. | `POST /v1/lives` `{"mode":"preset","preset_id":"nurse-leeds","start_year":2006,"seed":424242}` |
| 2 | Tap **AGE**. An event sheet opens. | `POST /v1/lives/{id}/age` |
| 3 | Pick a choice. Point at the source chip on the sheet. | `POST /v1/lives/{id}/choices` `{"event_id":"...","choice_id":"..."}` |
| 4 | Tap **AGE** until **2008**. Show the 2008 events and the Lesson screen. | `POST /v1/lives/{id}/age`, then `/choices` |
| 5 | Go back. Start **Tom, banker, London**, 2006, same seed. Tap **AGE** to 2008. | same calls with `"preset_id":"banker-london"` |
| 6 | Compare Money, Index and net worth for the two lives. | `GET /v1/lives/{id}` and `GET /v1/lives/{id}/summary` for each |

Narration (matches the expected output above; change the numbers to match your check):
- "Same year, same seed, different person and place. Every event cites its source and says whether the data is live, cached or mock."
- "2008. Bank of England data: Bank Rate falls from 5.50% to 2.00%. Land Registry data: house prices fall about 15%."
- "Tom owns a London flat with a mortgage. The flat loses £68,386 and there is no bonus this year. His net worth falls from £317,645 to £255,490."
- "Amira rents in Leeds. She owns no house, so the price fall does not hit her. Her net worth keeps rising, from -£6,163 to -£2,401."
- "Same crash, different lives. Who you are and where you live decides what a crash does to you."
- The share-price fall uses `mock` data (`yahoo`). Do not call it real market data.
- Do not claim a job loss. Neither life loses a job in this run.

Fallback:
- If ageing is slow or an event fails, open the pre-aged lives from the manifest:
  ```bash
  path <nurse-leeds-2008-fallback id>; path <banker-london-2008-fallback id>
  ```
- If a data source is down, the event still shows. Its source chip reads `cached` or `mock`.

## Scene 2: A judge joins a Same Life room (2021 to 2023 rate shock)

Say: "Now you play. Same character, same seed, same events. You go at your own pace."

Character: **Tom, banker, London**. He has a mortgage, so the rate rises reach him. (Amira rents and gets no mortgage event in 2021 to 2023.)

When rooms are built (Tier 2):

| Step | Tap (presenter) | Tap (judge) | API call |
|---|---|---|---|
| 1 | **Rooms** tab. Tap **Create room**, mode **Group**, character **Tom**, year **2021**. A QR code shows. | | `POST /v1/rooms` `{"mode":"group","host_name":"Host","preset_id":"banker-london","start_year":2021}` |
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

- Expected events (2026-10-17 stack): 2022 "Savings rates are up" (`boe:IUMBEDR=live`), "Energy bills jump" (`ons:D7GT=live`); 2023 "Your mortgage deal is ending" (`boe:IUMBV34`, `IUMBV42=live`).
- With default choices in both terminals, the event lists are identical. Same seed gives the same life.
- With `alt` the judge takes a different first choice. Show where the lists and net worth paths split.

## Scene 3: Rewind a bad choice

Say: "Everyone makes a bad call. Here you can go back and see the other path."

When rewind is built (Tier 1):

| Step | Tap | API call |
|---|---|---|
| 1 | Open the nurse life. Tap the timeline. Pick a past choice. | `GET /v1/lives/{id}` (read `history[].decision_id`) |
| 2 | Tap **Rewind**. The first rewind in a life is free. | `POST /v1/lives/{id}/rewind` `{"decision_id":"..."}` |
| 3 | The life returns to that year. Pick the other choice. | `POST /v1/lives/{id}/choices` |
| 4 | The screen shows the Index of the abandoned path next to the new one. | `RewindResult.abandoned_index`, `RewindResult.abandoned_net_worth`, `life.index.value` |

- With the manifest: `api -X POST $BASE/v1/lives/<nurse-leeds-2008-fallback id>/rewind -d '{"decision_id":"<first_decision_id>"}' | jq '{abandoned_index, new_index: .life.index.value}'`.
- A second rewind returns `402 payment_required`. Tap **Rewind Pass** (labelled "Demo payment"; `POST /v1/purchases/verify` `{"product_id":"lifeline.rewindpass","demo":true}`).

Until rewind is built (works now): two lives on the same seed, different first choice.

```bash
source services/api/seed/demo.sh
A=$(new_life nurse-leeds 2006 424242); B=$(new_life nurse-leeds 2006 424242)
play_to $A 2010          # path A: default choice everywhere
play_to $B 2010 alt      # path B: the other choice at the first decision, then defaults
path $A; path $B         # net worth and Index per year, side by side
```

- Both paths match until the first decision, then split. Show the Index difference in the last year.

## Scene 4: Play yourself to today, then one clear decision

Say: "The game ends where your real life is now. One clear decision, with evidence."

When the Real-life Decision is built (Tier 1):

| Step | Tap | API call |
|---|---|---|
| 1 | Character select. Tap **Play yourself**. Enter age, region, income, savings, home and mortgage. Or tap **Connect bank** (sandbox, Tier 2). | `POST /v1/lives` `{"mode":"self","start_year":2020,"character":{...}}`. Bank: `GET /v1/bank/auth-link`, then `GET /v1/bank/summary?session=...` |
| 2 | Tap **AGE** until the present (2026). | `POST /v1/lives/{id}/age` until `life.reached_present` is `true` |
| 3 | The **Real-life Decision** screen opens. Read the headline. | `POST /v1/decisions` `{"profile":{...},"life_id":"..."}` |
| 4 | Point at the evidence line, the matched periods, and the source chips with `live`/`cached`/`mock` status. | `Decision.evidence`, `Decision.sources[]` |
| 5 | Optional: open **How good is this?** to show the backtest hit rate against the baseline. | `GET /v1/evaluation` |

- If the manifest has a `decision` key, it holds the headline, evidence and sources the screen will show.

Until the decision is built (works now):

```bash
source services/api/seed/demo.sh
api $BASE/v1/lives/<self-2020 id> | jq '{year, age, reached_present, net_worth: .finances.net_worth, index: .index.value}'
path <self-2020 id>
curl -s $BASE/v1/sources | jq -r '.sources[] | "\(.id)  \(.status)  \(.coverage)"'
```

- Show that the "Play yourself" life reached 2026 (`reached_present: true`).
- Show `/v1/sources`. Say: "The decision uses these sources. Each one says whether it is live, cached or mock. A source with no key serves labelled mock data."
- Say what the decision will do: match the user to similar people (twins) and similar past periods, and give one action with the share of twins who did better. Do not show a headline: no headline exists until `/v1/decisions` is built.

## Reset

```bash
make down                  # stops the stack; the postgres volume keeps data
docker compose down -v     # also deletes demo lives and rooms
```

Run `make up && make demo-seed` again for a clean set.
