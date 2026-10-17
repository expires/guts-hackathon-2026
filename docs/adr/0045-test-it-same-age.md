# ADR 0045: Test it replays today's you at today's age

Date: 2026-10-17. Status: accepted (records existing behaviour, `shift_to_period` in `lifeline_api/routes/next_move.py`).

- Test it places today's user in the past period at the same age and with the same money. Priya (born 1992, 34 today) starts the 2020-2023 replay at age 34, so the Test it life has birth year 1986.
- This is not a second persona. The screen labels years as "2020 · Age 34".
- V4 must not flag the shifted birth year in `testNextMove` recordings.
