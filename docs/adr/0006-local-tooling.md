# ADR 0006: Local toolchain

- Status: accepted
- Date: 2026-10-17

## Decision
- Python 3.12 through `uv` (system Python is 3.9).
- Docker through Colima.
- XcodeGen generates the Xcode project from `apps/ios/project.yml`, so parallel workers never edit `project.pbxproj`.
- Secret scan: gitleaks (installed).
- Docker Compose v2 plugin installed with Homebrew (`docker-compose`) and linked into `~/.docker/cli-plugins/`.
- Simulator: the iOS 27.0 runtime files went missing after the 27.1 download, so devices on 27.0 fail to boot. iOS 27.1 offers only the "iPhone Duo" device type here. `make ios-test` defaults to `SIM=iPhone Duo`.
- Update: restarting CoreSimulatorService (`xcrun simctl shutdown all; killall -9 com.apple.CoreSimulator.CoreSimulatorService`) fixed both runtimes. Default is now `SIM=iPhone 18 Pro Max` (iOS 27.0), the user's preferred device.
- CLI iOS builds (Makefile, verifiers, agents) use `-derivedDataPath apps/ios/.build/DerivedData`. The user's Xcode GUI builds keep the default DerivedData, so the two never conflict. `.build/` is git-ignored.
