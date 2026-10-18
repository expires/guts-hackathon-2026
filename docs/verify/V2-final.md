# V2 final: engine forecast (PENNY_V3_BUILD.md B2 and A5.4)

- Date: 18 Oct 2026, 09:15 BST
- Verifier: V2 (read-only)
- Target: `main` at `3eae93c6` (`origin/main`). The local working tree is at `cfff461e` with uncommitted changes, so I exported `3eae93c6` with `git archive 3eae93c6 services/api` into a scratch folder and ran every check there.
- Verdict: **PASS** (2 non-blocking warnings, see the end)

## Checks

| # | Check | Command or method | Result |
|---|---|---|---|
| 1 | Engine unit tests | `uv run --frozen pytest tests/unit/engine -q` | PASS. 340 passed, exit 0 (1 collection warning: `TestMoveInput` has `__init__`). |
| 2 | mypy strict | `uv run --frozen mypy --strict lifeline_engine lifeline_sim lifeline_contracts` | PASS. "Success: no issues found in 78 source files". |
| 3 | `forecast.py` purity (static) | grep of `lifeline_engine/` and the modules that `forecast.py` imports for `open`, `os`, `pathlib`, `socket`, `httpx`, `requests`, `datetime.now`, `date.today`, `time.time`, global `random`, `np.random.*` | PASS. No I/O, no clock, no global RNG. `today` is a parameter. `population.py` takes an `np.random.Generator` as a parameter. |
| 4 | Purity (dynamic) | Replace `builtins.open`, `socket.socket`, `random.random`, `random.randint`, `time.time` with functions that raise, then call `compute` for 10 students x 5 buffer options, twice each | PASS. No call raised. The two results are identical for all 50 runs. |
| 5 | Hand calculation, Amara (scholarship) | Sample loader in-process, import day 18 Oct, today = 17 Oct, CPI 3.8, buffer 10% | PASS. See below. |
| 6 | Hand calculation, Jordan (loan_england) | Same | PASS. See below. |
| 7 | Exact sums | 10 students x 5 buffer options | PASS. `left - buffer == per_day x days == to_spend`; `per_week == per_day x 7`; step amounts close; bills and expected income totals equal their item sums; buffer is in `[target, target + days pence)`. |
| 8 | Buffer options | Same runs; `compute` with 1, 25, -5 | PASS. `per_week` does not increase as buffer goes 0, 5, 10, 15, 20%. Values outside the 5 options raise `ValueError`. |
| 9 | CPI gap (over 6 weeks) | `what_if` moves Lena's next money to today + 42 and today + 43 days | PASS. 42 days: no CPI. 43 days: CPI on, `usual = round(raw x (1 + 3.8% x 43/365))` matches. `cpi=None`: no CPI. All 10 students: `cpi_adjusted == (gap > 42)`. |
| 10 | Stress test 2022 | All 10 students with `stress=2022` | PASS. `inflation_pct` 9.1, state set. |
| 11 | what_if | One-off cost inside and outside the window, extra income, Spotify price change, move rent bill past next money, `before == compute()` | PASS. Inside cost adds £200 to bills and lowers `per_week`; outside cost leaves it and adds a note; extra income adds £100; price change adds 3 x £6 = £18. Warning W2 below. |
| 12 | A5.4 states, 10 students | In-process loader + `compute`, import days 16 to 23 Oct | PASS. Jordan, Callum, Hugo `running_short`; other 7 `on_track`, on all 8 import days. |
| 13 | Integration test `tests/integration/test_forecast_samples.py` (HTTP path) | - | NOT RUN (check 12 covers the same states in-process). |
| 14 | Production CPI and BoE rate from the live MacroTable | - | NOT RUN. My checks pass CPI 3.8 and rate 4.0 directly. |

## Hand calculation 1: Amara Okoye (scholarship), today 17 Oct 2026

- Money now: Nationwide FlexStudent £1,950.00. Savings £820 not counted. Engine: £1,950.00.
- Next money: SFE loan £3,610.00 on 11 Jan 2027. Bursary next on 12 Feb, after the window.
- Days: 18 Oct to 10 Jan = 14 + 30 + 31 + 10 = 85. Engine: 85.
- Bills: giffgaff £10 x 3 (5 Nov, 5 Dec, 5 Jan) + Spotify £5.99 x 3 (9 Nov, 9 Dec, 9 Jan) = £47.97. Engine: £47.97.
- Left = 1,950.00 - 47.97 = £1,902.03. Target buffer = 10% = £190.20.
- Per day = floor((1,902.03 - 190.20) / 85) = floor(20.139) = £20.13. Per week = £140.91. To spend = 20.13 x 85 = £1,711.05. Buffer = 1,902.03 - 1,711.05 = £190.98 (includes 78p). Engine: same.
- Usual weeks, summed by hand from the transactions: 175.44, 94.25, 49.60, 97.85. Mean = 417.14 / 4 = £104.29.
- Gap = 86 days > 42, so CPI applies: 104.29 x (1 + 0.038 x 86 / 365) = £105.22. Engine: £105.22.
- State: 105.22 <= 140.91, on track. Spare = (140.91 - 105.22) x 85 / 7 = £433.38. Engine: £433.38. Suggestion "Put your £433 spare aside" with the BoE rate.
- Spec match: "on track to her January loan, with spare money".

## Hand calculation 2: Jordan Hughes (loan_england), today 17 Oct 2026

- Money now: HSBC £2,560.00. Next money: SFE loan £3,374.60 on 11 Jan 2027 (under the £10,830 maximum per year). Days: 85.
- Bills: rent £560 x 3 (1 Nov, 1 Dec, 1 Jan) + Apple £0.99 x 3 + Smarty £10 x 2 (12 Nov, 12 Dec) + Spotify £5.99 x 2 (14 Nov, 14 Dec) = 1,680 + 2.97 + 20 + 11.98 = £1,714.95. Engine: £1,714.95.
- Left = £845.05. Target buffer £84.51. Per day = floor(760.54 / 85) = £8.94. Per week £62.58. To spend £759.90. Buffer £85.15. Engine: same.
- Usual weeks: 77.75, 105.93, 134.57, 104.91. Mean £105.79. CPI (86 days): £106.74. Engine: £106.74.
- State: 106.74 > 62.58, running short. Run-out = 17 Oct + floor(845.05 / (106.74 / 7)) = 17 Oct + 55 days = 11 Dec. Engine: 11 Dec. Suggestion: eating out, £41 a week.
- Spec match: "money runs out in December, before the January payment".

## A5.4 table (import day 18 Oct, buffer 10%)

| Student | State | Money now | Expected in | Bills | Per week | Usual | Next money | Run-out |
|---|---|---|---|---|---|---|---|---|
| Amara (scholarship) | on_track | 1,950.00 | 0 | 47.97 | 140.91 | 105.22 | 11 Jan | - |
| Eilidh (scottish) | on_track | 860.00 | 173.60 | 0 | 813.96 | 64.48 | 26 Oct | - |
| Priya (commuter) | on_track | 1,400.00 | 480.00 | 467.97 | 104.65 | 96.33 | 11 Jan | - |
| Jordan (loan_england) | running_short | 2,560.00 | 0 | 1,714.95 | 62.58 | 106.74 | 11 Jan | 11 Dec |
| Callum (working) | running_short | -385.00 | 0 | 0 | 0 | 136.16 | 23 Oct | 17 Oct |
| Grace (mature) | on_track | 2,750.00 | 2,153.91 | 1,721.97 | 235.83 | 102.79 | 11 Jan | - |
| Yutong (international) | on_track | 1,350.00 | 0 | 767.99 | 229.11 | 115.81 | 3 Nov | - |
| Sam (final_year) | on_track | 4,050.00 | 0 | 1,976.98 | 153.58 | 76.96 | 11 Jan | - |
| Hugo (rich) | running_short | 120.00 | 0 | 8.99 | 49.91 | 203.15 | 1 Nov | 20 Oct |
| Lena (graduate) | on_track | 980.00 | 0 | 0 | 1,234.80 | 148.87 | 23 Oct | - |

## Documented differences from the B2 text (accepted, not failures)

- Buffer, per day and run-out use money available = money now + expected income before the next money. B2 says "money now - bills". The module docstring states this and it gives correct results for Priya, Grace and Eilidh.
- Spare uses `days / 7` for "weeks". This is exact and matches B2.

## Warnings (non-blocking)

- W1. Jordan's £45 "BILLS SHARE 41 FOREST RD" is not a bill in the forecast. It has only 2 charges (7 Sep, 5 Oct), and `lifeline_engine/money/recurring.py:45` (`MIN_CHARGES["monthly"] = 3`) needs 3 for a non-housing charge. Rent passes with 2 (`HOUSING_MIN_CHARGES`, line 197). Result: bills are £135 too low (5 Nov, 5 Dec, 5 Jan), and the charge is also out of usual spending because it is in the "bills" category. The state does not change (Jordan is still short, and the run-out date would be earlier). Lena's PureGym (2 charges) has the same cause, but its next charge is after her next money, so no effect today. Owner: W2 (detection rule) or W1 (seed: start Jordan's bills share in July).
- W2. `what_if` summary can name a run-out date after the next money. Example: Jordan, move rent to 20 Jan: "At this pace you run out on 17 January", but the next money is on 11 January. `lifeline_engine/forecast.py:823` (`_summary`) checks only `run_out_date != today`. It must also check `run_out_date < next_money.date`, as `_card_text` does at line 579. Owner: W2.

## Scratch files (outside the repo)

`/private/tmp/claude-501/-Users-ash-Workspace-dyhtg/d2613979-29cc-4f7b-8a9a-40abef46e06e/scratchpad/checks/` (`run_all.py`, `dump.py`, `bills.py`, `props.py`, `days.py`).
