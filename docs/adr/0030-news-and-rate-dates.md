# ADR 0030: News (Guardian) and Bank of England rate-decision dates are context only

- Status: accepted
- Date: 2026-10-17

## Decision
- **Guardian Open Platform** adapter (W1):
  - Key from env `GUARDIAN_API_KEY`. It is set locally and on Railway, through stdin, never printed.
  - Search by topic and date range.
  - Store only headline, standfirst (at most one sentence), section, date and URL. **Never article body text** (copyright).
- **BoE MPC calendar** adapter (W1): rate-decision dates from the Bank's public page, live with a cache.
- Both appear in `GET /v1/sources` with live, cached or unavailable status. In live mode (ADR 0027) a failure shows "unavailable"; it never falls back to mock.
- Uses:
  - The Life feed shows real headlines for the current year (headline plus link, "Guardian" tag): `GET /v1/news`.
  - Next Move "Why?" shows a context line, for example "Next Bank of England rate decision: 5 Nov 2026" (`context_lines`, `GET /v1/rate-decisions`).
- **Never a decision input.** News and rate dates do not change any engine result. A test asserts this: `next_move` output is identical with and without them.
- Headlines are untrusted text (ADR 0034).
