# ADR 0037: Parallel iOS feature work with BOSS-owned shared files

- Status: accepted
- Date: 2026-10-17
- Requested by: the user (replaces the sequential iOS order)

## Decision
- Three iOS features run in parallel:
  - W6: onboarding and accounts (`Features/Onboarding`, `Features/Account`).
  - W7: Ask Penny UI (`Features/Penny`).
  - W9 (new): Same Life PvP UI (`Features/Rooms`, `Features/Play`), taking Rooms over from W7.
- **BOSS owns the shared files:**
  - root navigation (`App/**`);
  - `LifelineClient`, `LiveClient`, `MockClient`;
  - recorded mock data;
  - `project.yml`;
  - all DesignSystem additions.
- A BOSS helper agent edits only those files, on BOSS instructions. It adds client methods for every new contract operation (accounts, onboarding, chat and its SSE stream, rooms WebSocket, news, rate decisions), entry points, and shared components.
- Workers request shared changes with exact signatures. Until a change lands, they code against closures or protocols.
- Builds stay serialised by the DerivedData lock. Each worker uses its own simulator.
- **One verifier pass per feature:** V4 (build, tests, screenshots, rules). V1 checks any contract use.
- The design system and no-system-look rules (ADR 0026, the user's fix pass) apply to every new screen.
