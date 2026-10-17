# The INDEX

The INDEX scores how well a player manages money compared with an "autopilot" twin. A score of 100 means "as good as autopilot, with no missed payments and no falls in wealth".

- Code: `services/api/lifeline_sim/index.py`
- Weights: `services/api/lifeline_sim/config/index.toml` (the only place the weights live)
- Tests: `services/api/tests/unit/sim/test_index.py`

## Terms

| Term | Meaning |
|---|---|
| Autopilot twin | Same character, same seed, same macro data. Takes the default choice at every event. Takes no tab actions. |
| NetWorth(t) | cash + savings + investments + crypto + pension + home value − mortgage − card debt − student loan, at time t. |
| NetWorth(0) | Net worth at the start of the life. Player and twin share it. |
| AnnualIncome(0) | Gross annual income at the start of the life (`CharacterSpec.annual_income`). |
| missedPayments | Months in which the player could not cover required costs from cash and savings. Counted at each AGE (max 12 per year). |
| maxDrawdownFraction | Largest fall from a running peak in net worth, as a fraction. Range 0 to 1. |

## Formula

BUILD_SPEC form (player penalties only):

```
Index(t) = 100 × (1 + 0.1 × (R_player − R_autopilot)) − 2 × missed_p − 20 × dd_p
```

Form used in code (ADR 0013, penalties relative to the twin):

```
R(t)     = (NetWorth(t) − NetWorth(0)) / max(AnnualIncome(0), min_income0)

Index(t) = base × (1 + r_weight × (R_player(t) − R_autopilot(t)))
           − missed_payment_penalty × (missed_p − missed_a)
           − drawdown_penalty × (dd_p − dd_a)

Index(t) = max(Index(t), floor)
```

`missed_a` and `dd_a` are the twin's missed payments and largest drawdown.

Reason: with player-only penalties, a player who copies the twin scores below 100 whenever the shared life has a missed payment or a fall in wealth. In checks, 0 of 25 all-default lives were penalty-free. The relative form gives exactly 100 for a copy of the twin, for every seed. When the twin has no missed payments and no drawdown, both forms give the same value.

Weights from `index.toml`:

| Key | Value |
|---|---|
| `base` | 100 |
| `r_weight` | 0.1 |
| `missed_payment_penalty` | 2 |
| `drawdown_penalty` | 20 |
| `floor` | 0 |
| `min_income0` | 10,000 |

`min_income0` stops a division by zero (or by a very small income) for students and other lives with little starting pay.

## Drawdown

The sim tracks the player's net worth after every AGE and after every choice.

```
peak      = highest net worth so far (starts at NetWorth(0))
drawdown  = (peak − NetWorth) / max(peak, AnnualIncome(0) with the min_income0 floor)
maxDrawdownFraction = largest drawdown so far, clamped to [0, 1]
```

The denominator uses income when the peak is small or negative. A person in debt is measured against their pay. A wealthy person is measured against their wealth.

## When the Index updates

1. AGE: the year passes for the player and the twin. While the player has open events, the twin is compared before it answers any of this year's events. Ageing moves both lives with the same data, so the Index does not jump before the player answers.
2. Each choice: the twin answers (with its default) the events whose ids the player has answered this year. The Index updates.
3. When the player has no open events, the twin has answered all of its events for the year. A player who took every default then has R_player = R_autopilot and the same penalties, so the Index is exactly 100.

The Index can still move at AGE when the player's choices made the two lives different. For example, a player who holds more shares than the twin gains or loses more in a market year. That movement is real.

## Tab actions, rewind and "Test it" (Tier 1)

- Tab actions (Job, Assets, Relationships, Activities, Money) change the player only. The twin takes no actions, so an action moves the Index at once.
- AnnualIncome(0) and NetWorth(0) come from the life's start state. For an unedited preset, the start money scales with the start year (regional pay, CPI, regional house prices), so a 2021 nurse starts on 2021 pay.
- Rewind replays the life with one decision changed. The twin does not change, because its choices never depend on the player.
- "Test it" (`play_scenario`, ADR 0018) builds an ordinary life. Its twin takes every default, so the Index of each option compares that option with the default path. The option that equals the default (for example `fix_2y` at a mortgage deal end) scores exactly 100.

## Worked example

Amira, a nurse in Leeds. AnnualIncome(0) = £24,800. NetWorth(0) = −£10,500.

Some years later:

- Player net worth: £14,300
- Twin net worth: £9,340
- Missed payments: 1 (twin: 0)
- Largest fall: from a peak of £20,000 to £18,760, so drawdown = 1,240 / max(20,000, 24,800) = 0.05 (twin: 0)

Step 1. R values.

```
R_player    = (14,300 − (−10,500)) / 24,800 = 24,800 / 24,800 = 1.00
R_autopilot = ( 9,340 − (−10,500)) / 24,800 = 19,840 / 24,800 = 0.80
```

Step 2. Index.

```
Index = 100 × (1 + 0.1 × (1.00 − 0.80)) − 2 × 1 − 20 × 0.05
      = 100 × 1.02 − 2 − 1
      = 99.0
```

The twin has no penalties, so both forms give the same value. Amira beat her twin by 0.2 years of starting pay (+2 points). The missed payment (−2) and the fall in wealth (−1) cancel that out.

## Properties (tested)

- Fairness: a player who takes every default scores exactly 100 at the end of every year, for any seed and character (Hypothesis test).
- Beating the twin on missed payments or drawdown raises the Index above 100.
- Monotone: the Index never falls when R_player rises.
- The Index never rises when missed payments or drawdown rise.
- Floor: the Index is never below 0.
- No upper cap. A player far ahead of the twin can score well above 100.

## Student paths and Quick Life (ADR 0052, ADR 0059)

The Index works the same way on student path lives. The twin plays the same path, seed and start year with every default choice.

- Path lives start from `lifeline_sim.paths`: university, apprenticeship, job at 18, gap year, master's.
- Stage pay = a fixed share of regional median full-time pay (MacroTable `median_pay`, Nomis ASHE). The shares are game assumptions.
- Student loan repayment uses `lifeline_engine.rules`: 9% of pay above the plan threshold (6% above the postgraduate threshold). Plan by course start year in England: Plan 1 before 2012, Plan 2 from 2012 to 2022, Plan 5 from 2023. A year before 2026 uses the 2026/27 threshold in that year's prices (CPI).
- Quick Life: ages 18 to 25 in 5 or 6 AGE taps (each tap is 1 or 2 years), with 2 or 3 student events. The taps and events depend only on the seed and the start year, so a room plays the same life.
- The Quick Life summary card also shows a habit score (`lifeline_sim.habits`). It uses the same six ratio names and targets as the real-money score in `lifeline_engine.habits`, computed from game money only. It does not change the Index.
