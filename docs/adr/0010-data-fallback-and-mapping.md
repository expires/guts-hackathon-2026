# ADR 0010: Data fallback order and series mapping (W1, Tier 0)

- Status: accepted
- Date: 2026-10-17

## Decision
- Fallback per call: fresh Redis (within TTL) -> live fetch -> stale Redis (`cached`) -> Postgres `observations_snapshot` (`cached`) -> built-in mock (`mock`). Never raises.
- Redis keeps entries 30 days so a stale copy exists. In-memory cache takes over when Redis is down.
- Circuit breaker: opens after 3 failed fetches (each after 3 retries); half-open after 60 s. Validation failures count as failures.
- `APP_ENV=test` or `DATA_OFFLINE=1`: no network, Redis or Postgres. The hub returns the mock table.
- Annual table: monthly and quarterly values averaged per year. Each value takes the worst status of its inputs. Gaps filled from the mock table and labelled `mock`.
- Coverage follows the real source. No Scotland row means the UK value with note "UK average used". Census tenure "UK" row is the England and Wales total.
- Series: Nomis ASHE median gross annual pay, full-time (`sex=8, item=2, pay=7`); APS variable 83 (unemployment 16+), Jan-Dec windows; Census tenure "Owned" (1001). Energy CPI = ONS `D7GT`.
- `MacroTable` accepts string keys and keeps a cached year index (20,000 lookups in 0.03 s).
