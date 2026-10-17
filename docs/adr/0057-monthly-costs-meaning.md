# ADR 0057: What `monthly_costs` means

Date: 2026-10-17. Status: accepted. Source: V2 finding F-V2-1.

- `FinanceSnapshot.monthly_costs` is the user's entered REGULAR costs per month (rent, bills, subscriptions). It is not total spending.
- Months of cover, the safety-net target, the Lifetime ISA amount and habit parts use MEASURED average monthly spending when the snapshot has at least 1 month of outgoing transactions. They use `monthly_costs` only when there are no transactions (manual entry), and then say "regular costs" in the text.
- Shortfall checks compare cash against the regular costs due before the next money arrives, plus measured weekly spending for the same period.
- Sample hints keep `monthly_costs` as bills only (no change for W1).

## Amendment (W2 report)

- Shortfall = regular bills due before the next money + usual weekly spending (median of the last 4 weeks) × weeks to that date − cash. Shown as a plain amount (`Move.shortfall`), never annualised.
- A weekly_budget move with a shortfall above £0 always ranks first: running out of money before the next payment is the most urgent decision.
- Monthly spending counts whole months with data only.
