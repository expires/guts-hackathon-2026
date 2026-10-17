# ADR 0014: Year-end values for fast-moving series

- Status: accepted (amends ADR 0010)
- Date: 2026-10-17

## Context
V5 found that annual averages hide the 2008 crash. London house prices fall only 1.1% on the 2008 average. Bank Rate averages 4.63% in 2008 but ends the year at 2.0%. One AGE tap is one year, so the player experiences the state at the end of that year.

## Decision
- Change series use December on December (or Q4 on Q4) when monthly or quarterly data exists: `HOUSE_PRICE_CHANGE`, `CPI_INFLATION`, `RENT_CHANGE`, `ENERGY_PRICE_CHANGE`, `FUEL_PRICE_CHANGE`, `STOCK_RETURN`, `CRYPTO_RETURN`.
- Level series for policy and pricing use the year-end value: `BANK_RATE`, `MORTGAGE_2Y_FIX`, `MORTGAGE_5Y_FIX`, `GILT_10Y`, `GBP_USD`, `HOUSE_PRICE`.
- Annual-by-nature series stay as published: `MEDIAN_PAY` (ASHE, April), `UNEMPLOYMENT` (APS Jan-Dec), `OWNER_OCCUPIED_SHARE`.
- The current, incomplete year uses the latest available month.
- The mock table follows the same rule.

## Consequences
- 2008 shows a large fall (UK HPI Dec 2008 about -15% y/y; Bank Rate 2.0%).
- Values differ from published annual averages. The event source chips show the series id, and `docs/index.md` and the README note the rule.

## Implementation notes (W1)
- `build_macro_table` takes the latest point in each year (December, or the latest month for the current year).
- Stack values for 2008: UK house price change -14.9%, London -14.8%, Bank Rate 2.0 (0.5 at end 2009).
- Regional rents come from ONS IPHRP (`RENT_CHANGE`). ONS stopped IPHRP in February 2024 (replaced by PIPR), so 2024 is January 2024 only and 2025-2026 are mock. A PIPR adapter is a Tier 1 item.
- A discontinued source's last year can be a single month. The source chip shows the series id, so the user can see this.
