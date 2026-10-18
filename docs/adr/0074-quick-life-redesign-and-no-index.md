# ADR 0074: Quick Life redesign, and no INDEX anywhere

Date: 2026-10-18. Status: accepted (judge feedback). Replaces the Quick Life round of ADR 0052, 0059 and 0064. Based on `docs/QUICKLIFE_AUDIT.md`; fixes its bugs 1 (fast finisher stuck) and 2 (a leaver blocks the end).

## Quick Life
- New room game `quick_life` (contract: `RoomGame`, `QuickQuestion`, `QuickFeedback`, `QuickPlayerResult`, WebSocket `ql_question`, `ql_feedback`, `ql_results`, client `end_round`, `play_again`).
- Round: 5 ages (18, 19, 20, 22, 25), one preset question per age, the same 5 for everyone in the room. Each of the 5 students has a fixed set of 5 events from the existing 12, fitted to their stage, in life order. 3 choices each, shuffled. One tap answers and moves on. No Age up button.
- Score: each choice is worth 20, 10 or 0 points (best, okay, poor), set from the engine's money effect of that choice. Total = finance skill score out of 100. After each answer: one feedback line with the points and one sentence with the real number. Game money at 25 is shown small, labelled "game money", and used only as the tiebreak. No Happiness, Smarts, bars, INDEX or habit-score tiebreak in Quick Life.
- Waiting page: after question 5, "You scored N. Waiting for <names>..." with a tick per finished player. Other scores stay hidden until everyone is done. A player who leaves counts as finished. The host gets "End round" after 30 seconds.
- Winner page: the winner at the top; the ranking with scores out of 100; Penny's one line naming the winner's best move; each player's best and worst decision in one line. Buttons: "Play again" (the host picks a new student, everyone stays in the room, guests wait) and "Leave".
- Penny in Quick Life never recommends a choice and never sees answers before the reveal.

## No INDEX anywhere
- No player sees the word "INDEX" or an index number: Life, Same Life, rooms, results, rival strips, Penny answers, winner lines. Quick Life ranks by the finance skill score; other modes rank by game money, labelled "game money". A test fails if "INDEX" appears in any user-facing string in any of the 8 languages. The engine keeps its internal index for backtests.
