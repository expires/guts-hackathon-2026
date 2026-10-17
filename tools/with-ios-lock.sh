#!/usr/bin/env bash
# BOSS-owned. Run a command while holding the apps/ios/.build DerivedData lock (one xcodebuild at a time).
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; L="$ROOT/apps/ios/.build/build.lock"
mkdir -p "$ROOT/apps/ios/.build"; until mkdir "$L" 2>/dev/null; do sleep 5; done
trap 'rmdir "$L" 2>/dev/null || true' EXIT
"$@"
