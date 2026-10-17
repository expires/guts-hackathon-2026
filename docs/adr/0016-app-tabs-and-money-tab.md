# ADR 0016: App tabs (Money, Life, Play, You) and the Money tab

- Status: accepted (supersedes the tab layout in ADR 0009)
- Date: 2026-10-17
- Requested by: the user (spec change before Tier 1)

## Decision

### Tabs
- System `TabView`, in this order: **Money** (home, default), **Life** (the game), **Play** (Same Life rooms, challenges, ribbons, concepts), **You** (profile, bank connection, settings).
- The app always opens on Money. It does not restore the last tab.
- Job, Assets, People, Money and Activities are action menus inside the Life tab. They are not system tabs. The `available_actions[].tab` values stay as they are in the contract.

### Money tab (Tier 1, labelled fixtures; TrueLayer sandbox in Tier 2)
- Balance and net worth over time (Swift Charts line charts).
- Spending by category for the month (bar or donut).
- Subscriptions: list, monthly total, price-rise flags.
- Bills and upcoming payments (next 30 days).
- Budgets per category with progress (limits set by the user, stored server-side).
- Savings goals.
- The Real-life Decision as one action card at the top (`POST /v1/decisions` with the profile from `/v1/finance/profile`).
- Every response carries `meta.data_status` (`live` | `cached` | `mock`). Mock data shows the label "Sample data".

### Backend
- Contract: `/v1/finance/overview`, `/spending`, `/subscriptions`, `/bills`, `/budgets` (GET, PUT), `/goals` (GET, POST), `/profile`, and `GET /v1/lives` for the Play tab. Models in `lifeline_contracts/finance.py`.
- Data (W1): `lifeline_data.finance` produces a `FinanceSnapshot` (accounts + transactions). Tier 1: labelled fixture personas, chosen deterministically per user. Tier 2: TrueLayer sandbox through the bank OAuth session.
- Insights (W2): `lifeline_engine.money` is pure code. It does categorisation (merchant rules and keyword rules), subscription detection (same merchant, regular cadence, amount within 10%, price rise = last charge above the previous one), bills (recurring outflows with a next due date), budgets, goals arithmetic, history series, the `DecisionProfile` and `CharacterSpec` builder, and personal facts. No LLM.
- API (W4): routes, per-user budget limits and goals in the store.

### Bridge
- Money tab data feeds "Play yourself": `/v1/finance/profile` returns a `CharacterSpec` that `POST /v1/lives {mode: self}` accepts.
- Lessons link to real numbers. `Lesson.personal` holds one sentence such as "You spend £47 a month on 6 subscriptions.", taken from `PersonalFact`s whose `concept_id` matches the lesson. The API fills it. Every number in that sentence comes from `PersonalFact.facts`. The explain verifier applies to it if an LLM rewrites it.

### iOS ownership for new screens
- ADR 0011 still holds: agents never edit existing files under `Features/**/Views/**` or `DesignSystem/**`.
- For a screen with no View file yet (Money tab, Play tab, You tab, Life action menus), the agent may create the first draft View once. The file header says `// Draft by <agent>. Owned by the UI owner from creation.` The agent also adds a "draft created, please review" entry to `docs/UI_REQUESTS.md`. After that, the agent never edits the file again.
- Tab structure lives in agent-owned glue (`App/RootScreen.swift` and `*Screen.swift`). The Life action menus attach from glue (for example `.safeAreaInset`) so the existing `LifeView` needs no edit. Any change to the existing `LifeView` goes through `docs/UI_REQUESTS.md`.

## Consequences
- The app opens on real (or labelled sample) money data, not the game. The game remains one tap away.
- Tier 1 grows: the Money tab and seven finance endpoints. Bank OAuth stays in Tier 2. Until then, all Money data is mock and labelled.
- The teammate's `docs/PLAN.md` dashboard idea (Monzo and Trading212) overlaps with the Money tab. BUILD_SPEC wins; STATUS lists the difference.
