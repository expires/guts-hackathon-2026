# ADR 0055: Demo requirements (provisional)

Date: 2026-10-17. Status: provisional. Source: DIRECTION_V2.md section 10.

- The user sends the final demo script later. DEMO.md is not written until then.
- Build what the provisional demo needs: Quick Life, live Ask Penny, lobby, sample statements, judge mode.
- Targets: import under 10 s, Penny first bubble under 3 s, Quick Life round under 60 s with 2 to 3 events, lobby join under 10 s.
- V5 rehearsal (later): 4 simulated players, onboarding to leaderboard, 5 runs in a row on Railway, timings reported.

## Amendment (V4 demo risk)

- Demo sign-in is limited per IP (`AUTH_RATE_LIMIT_PER_MINUTE`, default 20). At the venue all phones share one Wi-Fi IP, so Railway sets `AUTH_RATE_LIMIT_PER_MINUTE=300` and keeps the per-user limits unchanged. Judge mode "New player" signs in once per tap, so 300 a minute covers a room of phones with margin.
