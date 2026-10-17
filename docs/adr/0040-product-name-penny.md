# ADR 0040: Product name "Penny"

Date: 2026-10-17. Status: accepted.

## Decision

- The product name is **Penny**. Tagline: **"Your money, played forward."**
- Pitch: "Penny. Your money, played forward. Many sources. One answer: your next money move. Play it before you live it."
- "Ask Penny" stays the name of the chat feature. Penny is also the guide character.
- Changed:
  - `PRODUCT_NAME` and `TAGLINE` in `lifeline_contracts/brand.py`.
  - `Brand.productName` and `Brand.tagline` in `Brand.swift`.
  - App display name: "Penny" (Release, Demo, Mock), "Penny Dev" (Dev).
  - All UI copy: onboarding, You tab, store ("Penny Plus"), rooms.
  - README, BUILD_SPEC, DEMO, architecture, AI_USAGE, RESPONSIBLE_AI and the seed loader text.
  - Ask Penny prompt: now "You are Penny, the money guide in a UK app of the same name". Version `penny-v3`.
- Not changed (user instruction, no risky renames during the build):
  - Bundle ids `com.akshat.lifeline` and `.dev`.
  - Xcode project, schemes, targets and folders (`apps/ios/Lifeline`).
  - Swift types (`LifelineClient`), Python packages (`lifeline_*`), Railway project and service names.
  - The `lifeline://` URL scheme and room join links.
  - Historic ADRs and verify reports keep the old name as a record.

## Consequences

- An installed "Lifeline" app updates in place to "Penny" (same bundle id).
- New UI copy uses `Brand.productName`, not a literal name.
