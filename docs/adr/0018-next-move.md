# ADR 0018: The product answers one question: "What is my next money move?"

- Status: accepted. TOP PRIORITY for Tier 1.
- Date: 2026-10-17
- Requested by: the user (spec change)

## Pitch
"Many sources. One answer: your next money move. Play it before you live it."

## Decision

### Next Move engine (W2, engine code, no LLM)
- Input: the user's `FinanceSnapshot` (accounts, transactions, mortgage and energy details) plus the `MacroTable` (live sources) plus the synthetic population (twins) and period matching.
- Candidate moves (`MoveKind`): fix_mortgage, remortgage, move_savings, cancel_subscription, switch_subscription, switch_energy, pay_off_debt, build_emergency_fund, cut_budget. A move is a candidate only when the data supports it (for example, fix_mortgage needs a mortgage deal that ends within 12 months).
- Each candidate gets:
  - `impact_per_year`: expected GBP per year vs doing nothing.
  - `worst_case_per_year`: the worst matched past period.
  - `confidence`: the share of (twin, period) pairs where the move beat doing nothing.
  - `confidence_label`: plain English, for example "7 in 10 twins in similar past periods did better".
- Rank by risk-adjusted value. Default: `impact_per_year + 0.5 x min(0, worst_case_per_year)`, scaled by confidence. Ties prefer a nearer deadline.
- Output: ONE top move and up to 2 runners-up. Each move has 3 evidence points (every number in the text appears in `facts`), sources with live, cached or mock status, options, deadline and `days_left`, `testable`, `test_period` and `concept_id`.
- Backtest where data allows (mortgage fix choice over past deal-end dates, 1995-2023, vs "always fix for 2 years"). Results appear in `NextMoveResponse.backtest` and in `docs/prediction.md` or a sibling doc.
- New data keys: `SAVINGS_RATE`, `CARD_RATE` (BoE quoted household rates) and `ENERGY_TARIFF` (Ofgem cap or Octopus). `FinanceSnapshot` gains `mortgage` and `energy` details.

### Test it (W3 + W4)
- `lifeline_sim.api.play_scenario(life_id, character, start_year, end_year, policy, seed, macro)` plays the user's real profile (from `/v1/finance/profile`) through the move's `test_period`. `policy` maps template ids or template tags (for example `mortgage_deal_end`) to choice ids. All other events take the default.
- Default periods: mortgage moves 2021-2023 (rate shock); savings moves 2008-2010; energy 2021-2023; debt and emergency fund: the period that matches today's macro state best.
- `POST /v1/next-move/test` runs one scenario per option with the same seed and stores each as a life (open it in the Life tab). It returns side-by-side outcomes: net worth path, total cost, missed payments, worst year, Index, a one-line summary and the evidence sentence.

### Do this
- `POST /v1/plan` adds the move to the user's plan. `GET /v1/plan` lists it with the total yearly impact.

### Relation to earlier decisions
- The Next Move replaces the Real-life Decision card at the top of the Money tab (ADR 0016). `POST /v1/decisions` stays as the engine primitive for "Play yourself reaching the present" and as the mortgage-specific evidence behind fix_mortgage moves.
- `GET /v1/next-move` uses the same profile as `/v1/finance/profile`, so the Money tab, the Next Move card and "Play yourself" all agree.

### iOS (W6 + W7)
- The Next Move card is the first element on the Money tab. It has three buttons:
  - "Test it": the Life comparison. W7 owns the comparison screen.
  - "Why?": the lesson for `concept_id` plus the evidence.
  - "Do this": adds the move to the plan.
- Other Money widgets (subscriptions, bills, budgets, goals, Guess my spend) link back to the card when a move relates to them.
- New screens follow the ADR 0016 draft rule.

### Demo (W8)
- DEMO.md opens with the Money tab, then "Your deal ends in 165 days", then Test it (2022 replay, both options), then "Fix for 5 years. 7 in 10 twins did better.", then Do this.
- The demo persona (device `demo-presenter-01`) is a homeowner whose fixed deal ends on 2027-03-31, 165 days after 2026-10-17. W1 sets this in the fixtures.

## Consequences
- Tier 1 order: Next Move first (W1 data, W2 engine, W3 scenario, W4 endpoints, W6 card, W7 comparison), then the rest of Tier 1.
- Every number on the card traces to the engine or a source. The LLM (W5) may only reword the text. The verifier rejects new numbers.
