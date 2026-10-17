# ADR 0047: Data sources and sample statements

Date: 2026-10-17. Status: accepted. Source: DIRECTION_V2.md section 2.

- Market data stays live (BoE, ONS, Nomis, Land Registry, Companies House, Guardian, gov.uk facts), cached, "unavailable" when missing. Never fake.
- Personal data: manual entry, statement upload (Monzo and Revolut CSV or PDF), or a built-in sample statement, always labelled "Sample data".
- No bank connections. README and "Where our data comes from" explain why: Monzo API is personal-use only; Open Banking needs FCA authorisation or an aggregator contract; GoCardless closed new signups in 2025; Apple FinanceKit needs a special entitlement. Statement upload uses the same snapshot format, so a bank feed plugs in later.
- Sample statements: 4 synthetic students (scholarship, rich, working, commuter), 3 months each, Monzo-style CSV and PDF in `demo/statements/`, generator in `tools/gen_statements.py`. Funding sources and habits vary so income does not predict the habit score. Plus 4 team profiles for the team phones. Owner: W1 (generator, parser support).

## Amendment (W1 report)

- 8 profiles: scholarship, rich, working, commuter, team1-team4. 3 months each (2026-07-17 to 2026-10-16). CSV in Monzo format and a PDF marked "Sample data" on every page.
- PDF writing and text reading use the standard library only (no new dependency). Bank PDFs with embedded fonts fail with a clear message to upload a CSV.
- Detection rules (income kinds, schedules, overdraft, BNPL, student signals) live in `lifeline_data/statements/detect.py`.
- Sample snapshots use `status="mock"`, `source="sample"`, so the app labels them "Sample data".
- Canonical files are package data in `lifeline_data/statements/samples/` (shipped to Railway); `demo/statements/` is an identical copy for judges.
- `FinanceSnapshot.housing` added for the hints.
