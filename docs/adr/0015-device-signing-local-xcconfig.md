# ADR 0015: Device signing through a git-ignored Local.xcconfig

- Status: accepted
- Date: 2026-10-17

## Context
The user wants to build to a physical iPhone. `project.yml` had `CODE_SIGNING_ALLOWED: NO` for all builds and no team. XcodeGen regenerates the project, so a team set in the Xcode GUI is lost on the next `make ios-gen`. The repo is public, so personal Team IDs and hostnames must not be committed.

## Decision
- `apps/ios/Config/Base.xcconfig` (committed) sets `LIFELINE_BUNDLE_ID` and `LIFELINE_API_BASE_URL` and ends with `#include? "Local.xcconfig"`.
- `apps/ios/Config/Local.xcconfig` (git-ignored) holds `DEVELOPMENT_TEAM`, an optional unique `LIFELINE_BUNDLE_ID`, and the Mac's LAN URL for the API. A `.example` file shows the format.
- Code signing is off only for the simulator SDK (`CODE_SIGNING_ALLOWED[sdk=iphonesimulator*] = NO`). Device builds use automatic signing.
- CLI builds use `apps/ios/.build/DerivedData`. GUI builds keep Xcode's default (ADR 0006).

## Consequences
- `make ios-gen` never drops the user's signing settings.
- On a device, the app reaches the backend at `http://<mac>.local:8000`. ATS allows this through `NSAllowsLocalNetworking`.
