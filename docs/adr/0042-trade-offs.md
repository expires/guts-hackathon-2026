# ADR 0042: Every Next Move states its trade-off

Date: 2026-10-17. Status: accepted. Source: official GUTS brief ("one clear decision with evidence and trade-offs").

## Decision

- `Move` gains (contract, `lifeline_contracts/next_move.py`):
  - `trade_off: TradeOff` with `summary` (max 90 characters, the card line) and 1 to 4 `points` (EvidencePoint, for Why?).
  - `gain_kind`: `gbp_per_year` (uses `impact_per_year`) or `months_of_cover` (uses `cover_months`).
  - New `MoveKind` `spread_investments` (concentrated ISA holdings).
- The engine (W2) defines the trade-off per move kind. No LLM writes it. Every number in a point is in its `facts`, so the verifier can check it when Penny quotes it.
- Trade-offs per kind:

| Kind | What you give up |
|---|---|
| fix_mortgage, remortgage | Flexibility; early repayment charge; no gain if rates fall |
| move_savings | Easy access (notice or fixed term); rate can change |
| cancel_subscription, switch_subscription | The service, or features of it |
| switch_energy | Exit fee on the old deal; price fixed if prices fall |
| pay_off_debt | Less cash on hand for emergencies |
| build_emergency_fund | Less money invested, lower expected growth |
| cut_budget | Less spending on that category |
| spread_investments | Lower upside if the largest holding outperforms |

- iOS: the card shows the `summary` as one line ("What you give up: ..."). Why? shows all points.
- `trade_off` is optional in the schema only so older Mock recordings still decode. The contract test `test_next_move_trade_offs` requires it on every move. It becomes required after the recordings refresh.

## Amendment (W2 report)

- `lifeline_engine/trade_offs.py` builds one trade-off per kind. Typical ranges live in one `TYPICAL` table with source notes. They are used only where no per-user value exists: early repayment charge 1% to 5%, savings notice 30 to 120 days, energy exit fee per fuel, yearly swing of one share vs a broad fund. W2 wrote these from memory; they need a source check before the demo (STATUS).
- Mortgage: a fix states the new rate and the fixed-until year; a tracker states the payment rise per 1 point of Bank Rate.
- Emergency fund: `gain_kind = months_of_cover`. Cost of holding cash = savings rate vs the average UK share return (macro `STOCK_RETURN`).
- `spread_investments`: gain = amount moved × (0.35² − 0.15²) / 2 (volatility drag removed). Not testable. With the current ranking it rarely reaches the top 3. We do not tune the ranking to promote it.
- `FinanceSnapshot.holdings` is not added yet. It lands with the Yaffy merge from his Trading212 data model, so we do not define two shapes. Until then `spread_investments` is inactive.
