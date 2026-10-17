# ADR 0033: Engine tools for Penny, cash-flow projection and the official facts table

- Status: accepted
- Date: 2026-10-17

## Decision (W2, pure functions, mypy strict)
- `cash_flow_projection(snapshot, months, what_if)`:
  - A month-by-month balance from real income, bills and subscriptions.
  - `what_if` supports `job_loss(months)`, `rate_rise(points)`, `one_off_cost(gbp, month)` and `cancel(subscription_ids)`.
  - Returns months of cover, the lowest balance, the month the money runs out, and facts.
  - Hand-calculated tests (V2 checks them).
- **Facts table:** official UK rule numbers (ISA allowance, personal allowance, tax bands, student loan thresholds), each with a gov.uk source URL and an "as of" date. Stored as engine data with tests. Penny may cite only these rule numbers outside tool results.
- Tool wrappers over existing functions: `next_move`, `test_move` (Test it replay), `finance_summary`, `spend_prediction`, `life_replay` (a Life replay of the user for a period), `news_search` and `rate_decision_dates` (both context only).
- Every tool returns `{result, facts: [{id, value, unit, label}], sources: [SourceRef]}`. Fact ids are stable within a turn so highlights can reference them.

## Implementation notes (W2)
- "Based on N sources" counts **providers**, not series. Each provider's `series_id` lists the series it read, and its status is the weakest of them. Demo persona: 6 (bank, BoE, Land Registry, Nomis, Octopus, ONS).
- Cash-flow projection: start = current-account cash + cash savings. Income = net salary from detected salary credits. Outgoings = average of the last 3 complete months.
  - Months of cover = cash ÷ average monthly spend, assuming no income. Card repayments are not counted as spending.
  - A rate rise applies only after a fixed deal ends, or from month 1 when the rate is not fixed. Horizon is 1-60 months.
- Facts table: 37 official 2026/27 values, each checked on gov.uk on 2026-10-17 and stored with its URL. Income tax bands are "income after allowances", as gov.uk states them. A cross-check test asserts £12,570 + £37,700 = £50,270.
