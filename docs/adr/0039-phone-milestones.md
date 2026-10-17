# ADR 0039: Phone installs at milestones only (one app)

- Status: accepted (replaces the automatic Lifeline Dev installs)
- Date: 2026-10-17
- Requested by: the user

## Decision
- One app on the phone: **Lifeline** (`com.akshat.lifeline`, Demo configuration, Railway backend). The Dev configuration stays in `project.yml` but is not installed automatically. The user can delete the "Lifeline Dev" app from checkpoint 1.
- Install (`make ios-device CONFIG=Demo CHECKPOINT=n FEATURES=…`) only at these milestones, each after its feature passes V4:
  1. Onboarding + Money empty-state fixes
  2. Ask Penny
  3. Same Life PvP
  4. Final (connectors, presentation mode)
- Also install immediately when the user writes "install now", from the latest green build.
- After each install: a 5-step test checklist for the user. The user tests and sends feedback; fixes come before the next milestone.
- Each install is logged in `docs/STATUS.md` (Phone checkpoints).
