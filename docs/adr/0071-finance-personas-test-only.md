# ADR 0071: Finance personas are test-only

Date: 2026-10-18. Status: accepted. Amends ADR 0016 and ADR 0027 (demo-mode finance data).

- The 4 old non-student finance personas (`lifeline_data/finance/personas.py`) stay in the repo for tests only.
- No app route serves a persona. An account without its own money data gets the "no data" state in every mode: Money home `has_data=false` with the connect prompt, `/v1/me` `has_finance_data=false` (onboarding opens), and 409 `no_finance_data` from finance reads, `/v1/next-move`, `/v1/habits`, goals, budgets and guesses. Penny gets no personal data.
- This holds for a new account, after Reset and after New player. Presenter device ids get no persona either.
- No production module imports `lifeline_data.finance`. Tests seed a persona as the account's own data with `tests/integration/personas.seed_persona`. `tests/integration/test_no_persona.py` fails if any persona name, employer, postcode or amount appears in any response.
- Contract tests against a running stack cannot seed a persona in-process. They need data from `PUT /v1/finance/manual` or a sample import.
