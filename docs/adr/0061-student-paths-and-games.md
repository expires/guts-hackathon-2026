# ADR 0061: Student paths, Quick Life and game content (W3)

Date: 2026-10-17. Status: accepted. Implements ADR 0052 and 0059 in `lifeline_sim`.

- Paths: uni, apprentice, job18, gap_year (start 18, Quick Life) and masters (start 21). Pay per path stage is a labelled game assumption: a fixed share of the regional median full-time pay (Nomis ASHE). Real pay by occupation needs an ASHE occupation series (not added).
- Student loans: study years add tuition fee and maintenance loans; repayment is 9% above the plan threshold (6% above the postgraduate threshold) from `lifeline_engine.rules`. Plan by course start year in England: Plan 1 before 2012, Plan 2 from 2012 to 2022, Plan 5 from 2023. Earlier years use the 2026/27 threshold scaled by CPI. Tuition fee caps by year and these rules are being verified against official sources (ADR 0058) and moved into the facts table.
- Old presets (banker, plumber, retired, nurse) are no longer offered (`offered_presets()`); `presets()` still loads every id so stored lives and rooms replay.
- Quick Life: ages 18 to 25 in 5 or 6 taps, 2 or 3 events from 14 student templates, picked by seed, path and start year only (choices never change later events), so a room plays the same life. Quick lives cannot die. AGE after the last tap raises "finished" (409).
- Habit score for path lives is computed from the game ledger with the same 6 ratio names and 0-100 scale as the engine, game money only.
- Money Quiz: 59 questions (42 from the facts table, 17 from lessons), all on student money, each with an official URL; choice ids a-d after a seeded shuffle.
- Same Decision: 14 prompts from 2007 to 2023; context and outcomes from the macro table for that year, in game money.
- Lives without a path keep their old rules, so stored lives replay unchanged.

## Amendment (habit score must reflect choices; V2 W-F-1)

- The game ledger records weekly "wants" spending (baseline £35 students / £90 workers, 2024 prices, CPI-scaled); Quick Life choices raise or lower it. Living costs by path and region are labelled game assumptions in `lifeline_sim/params.py`.
- Card debt in a Quick Life is capped at a realistic credit limit for an 18 to 25 year old (£3,000 at most); overspending beyond the limit shows as missed payments and a lower habit score, not unlimited debt. Default choices are the neutral option, so a player who taps through gets a middle result, not a debt spiral.

## Amendment (user rule)

- Every offered Life preset is a student or graduate profile. The teacher preset is removed from the offered list too; old ids still load for stored lives.
- The job-at-18 path keeps its "school leaver" character: it is one of the student-lifecycle start paths (user decision, 2026-10-18).
