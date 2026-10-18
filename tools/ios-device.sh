#!/usr/bin/env bash
# BOSS-owned. Build the Mock configuration for the user's iPhone, install and launch it.
# Usage: tools/ios-device.sh            (from repo root; `make ios-device`)
# Exit codes: 0 installed+launched; 2 signing not set; 3 no device; other = build/install failure.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IOS="$ROOT/apps/ios"
DD="$IOS/.build/DerivedData"
LOCAL="$IOS/Config/Local.xcconfig"

team=$(sed -nE 's/^DEVELOPMENT_TEAM *= *([A-Z0-9]{10}) *$/\1/p' "$LOCAL" 2>/dev/null || true)
if [[ -z "$team" ]]; then
  echo "SIGNING: DEVELOPMENT_TEAM is empty in apps/ios/Config/Local.xcconfig" >&2; exit 2
fi
bundle=$(sed -nE 's/^LIFELINE_BUNDLE_ID *= *([A-Za-z0-9.-]+) *$/\1/p' "$LOCAL" || true)
bundle=${bundle:-com.lifeline.app}
[[ "${CONFIG:-Mock}" == "Dev" ]] && bundle="$bundle.dev"

json=$(mktemp); xcrun devicectl list devices --json-output "$json" >/dev/null 2>&1 || true
udid=$(python3 - "$json" <<'PY'
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception: sys.exit(0)
for dev in d.get("result",{}).get("devices",[]):
    hw=dev.get("hardwareProperties",{}); cp=dev.get("connectionProperties",{})
    if hw.get("reality")=="physical" and hw.get("platform")=="iOS" and cp.get("tunnelState")!="unavailable" and dev.get("deviceProperties",{}).get("developerModeStatus","enabled")=="enabled":
        print(hw.get("udid","")); break
PY
)
rm -f "$json"
# DEVICE_UDID=<udid> installs on a specific phone when several are connected.
[[ -n "${DEVICE_UDID:-}" ]] && udid="$DEVICE_UDID"
if [[ -z "$udid" ]]; then
  echo "DEVICE: no connected iPhone with Developer Mode on (unlock it, connect by cable or same Wi-Fi, trust this Mac)" >&2; exit 3
fi

# One xcodebuild at a time per DerivedData (several agents share it).
mkdir -p "$IOS/.build"; until mkdir "$IOS/.build/build.lock" 2>/dev/null; do sleep 5; done
trap 'rmdir "$IOS/.build/build.lock" 2>/dev/null || true' EXIT
cp "$ROOT/contracts/openapi.yaml" "$IOS/Lifeline/Networking/openapi.yaml"
(cd "$IOS" && xcodegen generate --quiet)
(cd "$IOS" && xcodebuild -project Lifeline.xcodeproj -scheme Lifeline -configuration "${CONFIG:-Mock}" \
  -destination "id=$udid" -derivedDataPath "$DD" -allowProvisioningUpdates \
  LIFELINE_CHECKPOINT="${CHECKPOINT:-}" LIFELINE_BUILD_TIME="$(date '+%Y-%m-%d %H:%M')" LIFELINE_FEATURES="${FEATURES:-}" \
  -skipPackagePluginValidation -skipMacroValidation build 2>&1 | tail -5)
rmdir "$IOS/.build/build.lock" 2>/dev/null || true; trap - EXIT

app="$DD/Build/Products/${CONFIG:-Mock}-iphoneos/Lifeline.app"
[[ -d "$app" ]] || { echo "BUILD: $app not found" >&2; exit 4; }
xcrun devicectl device install app --device "$udid" "$app" | tail -2
echo "INSTALLED: $bundle on $udid"
if ! xcrun devicectl device process launch --device "$udid" "$bundle" >/dev/null 2>&1; then
  echo "LAUNCH: not launched (phone locked?). The app is installed; tap Lifeline on the phone." >&2
else
  echo "LAUNCHED: $bundle"
fi
