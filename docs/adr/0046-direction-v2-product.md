# ADR 0046: Direction V2, product for UK students

Date: 2026-10-17. Status: accepted. Source: DIRECTION_V2.md section 1. Supersedes the product direction in BUILD_SPEC.md where they conflict, and ADR 0043 (named user Yaffy).

- Penny is the money app for the student finance lifecycle: before uni (funding), during uni, after uni (first salary, loan repayments, saving).
- Persona: UK students and young graduates. Income is any mix of maintenance loan, scholarship, bursary, grant, parents or family, part-time job, salary.
- The one decision: "Where should my money go this month?"
- Engine options (each with gain, trade-off, worst case, preconditions): weekly budget until the next money arrives, safety fund, pay off expensive debt, Lifetime ISA, cut subscriptions, move savings, keep as cash; mortgage options only with a mortgage.
- Pitch: "Rich or broke, it's about habits."
- Cut: Yaffy's branch and merge, Monzo and Trading212 connections, TrueLayer, receipt photos, HealthKit, Location, Wallet tap, inbound email, presentation mode. StoreKit demo store only if all else is green.
- Consequences: the `merge/yaffy` merge is cancelled. `spread_investments` is deprecated. Existing presentation mode code is removed from the UI in step 2.
- Deadline: coding closes 12:00 on 2026-10-18; feature freeze 09:30.
