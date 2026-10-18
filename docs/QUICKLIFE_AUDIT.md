# Quick Life audit

Date: 18 Oct 2026. Read-only audit of the code on `main` (`a3290ae8`). No code was changed. Event lists come from running the engine with seed 1 and default choices.

## 1. Flow

### Host
| # | Screen | Shows | Buttons |
|---|---|---|---|
| 1 | Play tab | "Play with friends" card, "Learn", "Join a game", Circles | "Play with friends": `POST /v1/rooms`, opens the room cover on the lobby |
| 2 | Lobby ("Your lobby") | QR code, 4-digit code, "Share the link", players with ticks (every seated player counts as ready for Quick Life), game card | Back arrow: leave the room. "Pick a game" / "Change the game": game picker. "Start with N players": on at 2 or more players once a game is picked |
| 3 | Game picker | Quick Life (first), Money Quiz; Same Decision and full Same Life only behind `FeatureFlags.showsCutFeatures` | Quick Life: opens "Pick a student". Close: keep the old pick |
| 4 | Pick a student | 5 student cards (from `GET /v1/paths` `quick_students`) | One tap: sends `pick_game` (`same_life`, `quick: true`, `quick_student_id`, its `path_id`), closes, back to the lobby. Back: games list |
| 5 | Live screen | Header (face, name, "Age N · Room CODE", "In the bank"), rival strip, this year's story, event card, Happiness and Money bars | Age up pill: one tap (1 or 2 years). Event choice buttons. "Not sure? Ask Penny": Penny sheet over the round. "Finish my run": sends `finish`. Back arrow: leave |
| 6 | Room results | "Winner" (or "Leader" while others play), Penny's winner line, ranking (INDEX vs autopilot, game net worth, ribbons), "Your Quick Life · <path>" card with habit score, "Where your lives split", "You earned" | "Rematch": host opens a new lobby (friends are not moved). "Share results": share sheet. X: leave |

### Guest
| # | Screen | Shows | Buttons |
|---|---|---|---|
| 1 | Play tab | as above | "Join a game": QR scanner. Or iPhone camera scan of the lobby QR: opens `lifeline://join/CODE`, Play tab, lobby |
| 2 | QR scanner | camera frame | "Type a code instead": code entry (4 digits, "Join") |
| 3 | Lobby | same as host, no "I'm ready" for Quick Life | Text only: "Waiting for <host> to pick a game" or "Waiting for <host> to start". Back arrow: leave |
| 4-6 | Live screen, results | same as host | Results: "Rematch" for a guest only leaves and closes |

## 2. A round
- Ages 18 to 25 (7 years), in 5 or 6 Age up taps. The split is seeded by the room seed: each tap is 1 or 2 years (`lifeline_sim/quick.py` `plan`). The start year is the server default 2018 (no year step); the last tap ends at 25 in 2025.
- At each tap the engine runs the year(s): pay or loans, rent and living costs, prices from the macro table, savings interest, Quick Life credit limit.
- Events: 2 or 3 per round, at seeded tap years before the last tap (never on the last tap). Each event is a seeded pick from the Quick Life pool (`events/engine.py` `draw_quick_event`): templates tagged `quick`, matching the student's stage (study or work) and age. A template fires once per life. Same room seed, path and start year give every player the same events; choices never change which events come.
- Choices per event: 3. The first is the default and is neutral (no change or a small one).
- Time limit: none. Quick Life is self-paced; each player taps at their own speed. (Money Quiz has 15 s questions; Same Decision 20 s.)

## 3. Events per student
The 5 students: Priya (university, Birmingham, full loan), Amara (university, London, £2,000 bursary), Jordan (apprentice electrician, Manchester), Kai (job at 18, Leeds, lives at home), Maya (gap year in Bristol, then university).

Which events come depends on the room seed, not the student. The pool depends on the stage:
- Study stage (Priya, Amara, Maya after the gap year): all `stage_any` events plus `stage_study`.
- Work stage (Jordan, Kai, Maya in the gap year): all `stage_any` events plus `stage_work`.

Example with seed 1 (taps end 2019, 2021, 2022, 2023, 2024, 2025; events at 2019 and 2021):
| Student | Age 19 event | Age 21 event | End (defaults): net worth, INDEX, Money stat |
|---|---|---|---|
| Priya | A 1 month safety fund | A 16-25 Railcard? | -£26,865, 100, 30 |
| Amara | A 1 month safety fund | A 16-25 Railcard? | -£37,607, 100, 29 |
| Jordan | Your first workplace pension | A 16-25 Railcard? | £39,650, 100, 81 |
| Kai | Your first workplace pension | A 16-25 Railcard? | £30,737, 100, 79 |
| Maya | A 1 month safety fund | A 16-25 Railcard? | -£47,332, 100, 18 |

The full Quick Life pool (12 events; default choice first; effects from `events/templates/student.yaml`):
| Event | Stage, ages | Choices and what they change |
|---|---|---|
| A 1 month safety fund | any, 18-25 | Save a little (cash to savings) / Spend the spare money (wants +£20 a week) / Set up the standing order (a month of costs to savings, happiness +2, wants -£35) |
| A 16-25 Railcard? | any, 18-25 | Buy tickets as you go (none) / Take taxis when trains are dear (wants +£20) / Buy the Railcard (cash + saving, wants -£35) |
| Pay in 3? (trainers) | any, 18-25 | Buy a cheaper pair (cash - cheap price) / Skip them (happiness -1, wants -£35) / Pay in 3 (cash - cost or a late-fee total, happiness +1 to +3, wants +£45) |
| Festival tickets | any, 18-25 | Go for one day (cash - day ticket, happiness +3) / Put it on a card (debt + cost, happiness +6, wants +£45) / Save up for next year (happiness -3, wants -£35) |
| A Lifetime ISA? | any, 18-39, from 2017 | Not now (none) / Spend the money instead (wants +£20) / Pay in now (cash - amount, savings + amount + 25% bonus, happiness +2, wants -£35) |
| Another subscription | any, 18-25 | Keep the one you have (none) / Sign up (monthly cost, happiness +2, wants +£35) / Share a friend's plan (happiness +1, wants -£30) |
| A 0% student overdraft | study, 18-24 | Leave it (none) / Keep it for emergencies (happiness -1, wants -£35) / Book the trip (debt + trip, happiness +6, wants +£45) |
| The house energy bill | study, 18-24 | Pay your share (none) / Leave the heating on (cash - extra, happiness +2, wants +£20) / Agree a house plan (cash + saving, happiness -1, wants -£35) |
| Make your money last the term | study, 16-30 | A rough plan (cash - small) / Spend as it comes (cash - overspend, happiness +2, wants +£45) / Set a weekly budget (savings + kept, happiness -1, smarts +1, wants -£35) |
| Your first workplace pension | work, 18-25 | Stay in (none) / Pay in 1% more (cash to pension, wants -£25) / Opt out (cash + take-home, pension - lost, happiness +2, wants +£40) |
| Clear the pay-later plans | work, 18-25 | Pay the next instalment (cash - part) / Keep rolling them (cash - rolled, wants +£40) / Clear them all now (cash - owed, happiness +3, wants -£35) |
| A job in a bigger city | work, 20-25 | Say not yet (none) / Stay and keep costs low (happiness +1, wants -£25) / Take the job (income + pay gain, new rent, happiness +3, wants +£45) |

"Wants" (`want_weekly`) changes weekly spending on wants for the rest of the life, in 2024 pounds.

## 4. Stats
| Stat | Range | Changed by | Shown |
|---|---|---|---|
| Cash, savings, debt, pension | £ | event effects (cash, savings, other_debt, pension, income, rent), pay, loans, costs each year | "In the bank" (cash + savings) in the header |
| Net worth (game money) | £ | all of the above | rival strip, results |
| Happiness | 0-100 | event `happiness` effects, some yearly rules | bar on the live screen |
| Money | 0-100 | derived from finances | bar on the live screen |
| Health | 0-100 | yearly rules; no Quick Life event changes it | not shown in rooms |
| Smarts | 0-100 | `smarts` effects (weekly budget +1), study years | not shown in rooms |
| INDEX | 100 = autopilot twin | your net-worth path against the same life with default choices | rival strip ("age · INDEX"), results |
| Habit score | 0-100, 6 parts | computed from the life at the end | Quick Life card on results |

Ranking: INDEX first, then habit score, then name (`lifeline_api/routes/rooms.py` `_life_results`). Score shown = INDEX rounded.

## 5. End of game
- A player finishes when their life ends (`alive` false), when they tap "Finish my run", or when `reached_present` is true. The client then sends `finish`, which marks that player finished.
- Waiting state: a finished player sees Room results with "Leader" (not "Winner"), "N players still playing", "Still playing" rows, and no Penny line.
- The room finishes only when every player is marked finished (`all(x["finished"])`). The server then sends `ranking` and `finished` with `winner_line`.
- Winner: highest INDEX, then highest habit score, then name.
- Penny's winner line is a template: "<name> wins with an INDEX of <n> and a habit score of <h> out of 100." Every number comes from the result.

## 6. Known bugs
1. **A fast finisher does not reach the waiting page by themselves.** At age 25 a Quick Life is over (`quick_finished`), but the life is still `alive` and `reached_present` is false (2025 < 2026). The app sends `finish` only when `!alive || reachedPresent` (`RoomFlowViewModel.lifeChanged`, line 535), so it never sends it on its own. The live screen keeps the Age up pill (`done` is false), and a tap fails on the server ("This Quick Life is over"). The player must find "Finish my run". Fix: also finish when `life.nextAge == nil` for a Quick Life, or have the server set a finished flag.
2. **A player who leaves mid-round blocks the end.** `leave` during play sets `connected = false` but not `finished`, and the room finishes only when every player is finished. No timeout ends the round.
3. **Ties at INDEX 100 are common.** With default (neutral) choices, a player's INDEX equals the autopilot twin (100), so the habit score decides most rankings.
4. **Results page layout:** not verified in this audit (no screenshot of a finished 2-player round on a phone). V4 checked Money, Penny, onboarding and the picker, not Room results.
5. **"Rematch" for a guest** only leaves and closes; the host's "New lobby" does not bring friends.
6. **Game money not labelled:** the rival strip and results show other players' game net worth without the "game money" label that Same Decision uses.

## 7. Files and messages
Server:
- `services/api/lifeline_sim/quick.py` (tap plan), `lifeline_sim/paths.py` (5 students, paths, `QUICK_START_AGE` 18, `QUICK_END_AGE` 25, start year 2018), `lifeline_sim/events/engine.py` (`quick_pool`, `draw_quick_event`), `lifeline_sim/events/templates/student.yaml` (events), `lifeline_sim/api.py` (`new_path_life`, `age`, `quick_finished`), `lifeline_sim/project.py` (`next_age`)
- `services/api/lifeline_api/routes/rooms.py` (WebSocket, `_is_quick_life`, start, progress, finish, `_life_results`), `lifeline_api/rooms.py` (room doc, code, QR, join URL), `lifeline_api/routes/lives.py` (room lives)

iOS:
- `Features/Rooms/ViewModels/RoomFlowViewModel.swift` (stages, start, finish), `RoomSession.swift` (socket), `RoomMapping.swift` (lobby, live, results states), `GameMapping.swift` (picker, Quick Life card)
- `Features/Rooms/Views/GamePickerView.swift`, `RoomLobbyView.swift`, `RoomLiveView.swift`, `RivalStripView.swift`, `RoomResultView.swift`
- `Features/Rooms/Transport/RoomTransport.swift` (`RoomLink` join URL), `App/AppRoutes.swift` (deep link), `DesignSystem/LLAgeUpButton.swift`

HTTP: `POST /v1/rooms`, `GET /v1/rooms/{code}`, `GET /v1/paths`, `POST /v1/lives` (`room_code`, `seed`, `path_id`, `quick`, `quick_student_id`), `POST /v1/lives/{id}/age`, `POST /v1/lives/{id}/choices`, `GET /v1/lives/{id}`, `GET /v1/lives/{id}/summary`.

WebSocket `/v1/rooms/{code}`: client `join`, `ready` (host auto), `pick_game`, `start`, `progress`, `finish`, `leave`, `ping`; server `welcome`, `roster`, `game_picked`, `started`, `rival`, `ranking`, `finished` (with `winner_line`), `error`, `pong`.
