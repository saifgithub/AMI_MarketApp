#!/usr/bin/env bash
# Build a signed AAB and push it to the Play Console internal testing track.
#
# One-command release path for release #2 onward. Wraps:
#   1. scripts/build_playstore.sh   (bump build number + signed AAB)
#   2. fastlane supply (internal track)
#
# The very FIRST upload of a new app must be manual (Play App Signing enrollment
# via the web UI) — see scripts/build_playstore.sh and CR048. Run this only
# after that first upload and after the Play Console service account exists.
#
# Introduced by CR048.
#
# Usage (from repo root or anywhere):
#   scripts/publish_playstore.sh                # bump + build + upload
#   scripts/publish_playstore.sh --no-bump      # upload whatever's in pubspec
#   scripts/publish_playstore.sh --no-commit    # don't auto-commit the bump
#   scripts/publish_playstore.sh --validate      # dry run: build + validate, no publish
#
# Required setup before first run (Saiful's one-time work, per CR048):
#   - ~/.android-keys/play-service-account.json   (Play Console API key; JSON)
#     Play Console → Setup → API access → create service account → grant
#     "Release to testing tracks" → download JSON key here.
#   Overridable path: SUPPLY_JSON_KEY=/path/to/key.json
#   Also inherits build_playstore.sh's requirements (keystore, dart-defines).

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VALIDATE=0
BUILD_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --validate) VALIDATE=1 ;;
    -h|--help)
      sed -n '2,/^$/p' "$0"
      exit 0
      ;;
    *) BUILD_ARGS+=("$arg") ;;   # passed through to build_playstore.sh
  esac
done

: "${SUPPLY_JSON_KEY:=$HOME/.android-keys/play-service-account.json}"
export SUPPLY_JSON_KEY
if [[ ! -f "$SUPPLY_JSON_KEY" ]]; then
  echo "✗ no Play Console service-account key at $SUPPLY_JSON_KEY" >&2
  echo "  Create it once (Play Console → Setup → API access → service account →" >&2
  echo "  grant 'Release to testing tracks' → download JSON), or set SUPPLY_JSON_KEY." >&2
  echo "  See docs/forward_planning/CR048_playstore_internal_track_fastlane/." >&2
  exit 1
fi

# 1. build the signed AAB (bump + flutter build appbundle)
"${PROJECT_ROOT}/scripts/build_playstore.sh" "${BUILD_ARGS[@]}"

# 2. upload (or validate) via fastlane supply
cd "${PROJECT_ROOT}/mobile/android"
if [[ "$VALIDATE" == "1" ]]; then
  echo "▶ fastlane validate (dry run — no publish)"
  bundle exec fastlane validate
else
  echo "▶ fastlane internal (upload to Play internal testing track)"
  bundle exec fastlane internal
  echo ""
  echo "✓ pushed to internal track — testers get it as a Play Store update."

  # CR079 — the store release ships an AAB to Play, but our automated tester on
  # melehost consumes an APK. Build + scp it here too so the rig is refreshed on
  # this build, not only when install_android.sh happens to run. Guarded: a scp
  # hiccup must not fail a release whose Play upload already succeeded — but the
  # helper's loud STALE warning still fires so a stale rig can't pass unnoticed.
  echo ""
  echo "▶ refreshing the automated-tester APK on melehost (CR079)"
  if ! "${PROJECT_ROOT}/scripts/share_apk_to_tester.sh"; then
    echo "⚠ Play upload succeeded but the automated-tester APK is STALE — see above." >&2
  fi
fi
