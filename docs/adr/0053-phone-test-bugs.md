# ADR 0053: Bugs from phone testing

Date: 2026-10-17. Status: accepted. Source: DIRECTION_V2.md section 8.

1. Next Move offers only moves whose preconditions match the user's data (tests). Owner W2.
2. "In your account" and "Net worth" come only from entered data; `FinanceOverview.balance_parts` and `net_worth_parts` feed the Why? calculation. Owners W4, W6.
3. No invented fields (no "Payday in N days" without a known payday). Owners W4, W2, W6.
4. Confidence "high" only with a sufficient, relevant sample; `Move.sample_size` and `confidence_level` shown. Owner W2, W6.
5. Months of cover with no costs entered: "Add your monthly costs to see this". Owners W2, W6.
6. "Earned £0 in interest" only with a known rate; otherwise ask or omit. Owners W2, W6.
7. You tab profile line matches onboarding (age, job or student, housing). Owner W7 (You).
8. Event choice buttons: the greyed state reads clearly as "chosen", or the bug is fixed. Owner W6.
9. The tracker example (£3,097 a year) is recalculated with a hand-checked test. Owner W2.

## Amendment (V1, V2 reviews)

- Confidence: "high" needs at least 8 independent cases (past periods, years or months of the user's own data) and a 70% share; "medium" needs 5 and 55%. The label names the unit, e.g. "(sample: 6 past periods)".
- Moves that are plain arithmetic on the user's own numbers (cancel_subscription, lifetime_isa) may be "high" with no sample; their label says "Based on your own numbers".
- weekly_budget is a projection of usual spending (median week), so it is "medium".
- The fallback move ("Nothing urgent") has no confidence level.
- Every count of months uses whole months with data only (ADR 0057).
