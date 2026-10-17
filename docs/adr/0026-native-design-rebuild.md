# ADR 0026: Native rebuild of the design handoff, installed on the user's iPhone after each step

- Status: accepted (temporary ownership change)
- Date: 2026-10-17
- Requested by: the user (NEW TOP PRIORITY)

## Decision
- Source: `lifeline-design/HANDOFF.md` plus `screens/*.dc.html` as visual and markup reference. Every screen is rebuilt in SwiftUI. No web views.
- Ownership: W6 and W7 may edit `Features/**/Views/**` and `DesignSystem/**` for this task. The paths return to the user afterwards (BOSS records the end here).
- Order, with a phone install after each step:
  1. DesignSystem: tokens (light and dark), Bricolage Grotesque 800 and Atkinson Hyperlegible 400/700 (bundled, registered at launch, OFL licences in Credits), type scale 40/24/17/13, spacing 4/8/12/16/20/32, uneven radii, 3 px ink outlines, offset hero shadow. Icons from `Icon.dc.html` as vector assets. All emoji and SF Symbols replaced.
  2. Tab bar (Money, Life, Play, You) and Money home with the Next Move card.
  3. Life main, action menus, event choice.
  4. Test it, lesson, rewind, life summary.
  5. Play, You, demo paywall.
- Phone build: Mock configuration (MockClient + fixtures), so it runs on any network with no backend. `make ios-device` (tools/ios-device.sh) builds, installs with `xcrun devicectl` and launches. Signing from the git-ignored `apps/ios/Config/Local.xcconfig`; the Team ID is never guessed.
- One xcodebuild at a time on `apps/ios/.build/DerivedData` (`tools/with-ios-lock.sh`).
- Data integrity: the design's sample numbers are layout references only. Every number on screen comes from ViewState, filled from fixtures or the API. Placeholders from the user:
  - 2021 five-year fix = 1.28% (BoE IUMBV42, Sep 2021). Fixture data with a SourceRef.
  - Hackathon name = "GUTS Hackathon 2026" (credits).
  - Paywall: £0.99 Rewind Pass, £1.99 God Mode, £2.99 Boss Mode, each labelled "Demo payment".
- Mock data shows the label "Mock data" (handoff) instead of the earlier "Sample data".
- The View / ViewState / ViewModel split stays. Previews and Playground fixtures are updated for every screen.
- V4 runs after step 5: build, tests, light and dark screenshots compared with the handoff.
