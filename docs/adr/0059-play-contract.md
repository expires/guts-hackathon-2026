# ADR 0059: Play with friends contract (step 5)

Date: 2026-10-17. Status: accepted. Implements ADR 0052. Contract: `lifeline_contracts/play.py`, rooms and lives in `api_models.py`.

- Lobby first: `POST /v1/rooms` with an empty body opens a lobby. Names come from the account (`Me.display_name`, else "Player N"); `host_name` is a fallback only. `mode` is set at start: 2 players = duel, more = group.
- The host sends WebSocket `pick_game` with `game` (quiz | same_decision | same_life) and `options` (GameOptions: path, quick, start year, quiz length, topic). The server broadcasts `game_picked`, then `start` begins the game.
- Money Quiz: the server sends `question` (QuizQuestion, 15 s, source label and official URL), players send `answer`, the server sends `quiz_reveal` (correct choice, Penny's one line, source, ranking). Questions come only from lessons and the facts table (ADR 0058). Points: correct answers, with a small speed bonus.
- Same Decision: the server sends `decision` (DecisionPrompt: one student money decision in one year of real history), players `answer`, the server sends `decision_reveal` (each player's choice, outcome per option in GAME money, Penny's line, ranking).
- Same Life and Quick Life: `POST /v1/lives` gains `path_id` and `quick`. Quick Life runs ages 18 to 25 in 5 to 6 AGE taps with 2 or 3 events with choices, then a summary card with the habit score. In a room, progress uses the existing `progress` and `finish` messages.
- `GET /v1/paths` lists student start paths (university, apprenticeship, job at 18, gap year, master's).
- Circles: `GET/POST /v1/circles`, `POST /v1/circles/join`, `POST /v1/circles/{id}/leave`. Members share `HabitScore` and `improvement` (overall points vs their own first score) only. Rank is by improvement. Penny's weekly recap uses ratios only.
- Privacy (ADR 0052) is enforced by `test_shared_payloads_never_carry_personal_money` and V6.
