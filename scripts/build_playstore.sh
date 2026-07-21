#!/usr/bin/env bash
# Build a signed AAB for Google Play Console internal testing track.
#
# Sibling of scripts/build_testflight.sh. Same monotonic build number
# is shared across iOS + Android (the `+N` in pubspec.yaml).
#
# Pipeline:
#   1. (optional) bump pubspec build number
#   2. flutter build appbundle --release --dart-define=...
#         (Gradle signs the AAB using ~/.android-keys/keystore.properties
#          when present; falls back to debug signing when absent — that
#          fallback path is OK for local smoke testing only, never for
#          Play upload.)
#   3. surface the AAB path + the manual upload reminder
#
# First upload to Play Console is mandatory-manual (Play App Signing
# enrollment on the very first build). For every release AFTER the first,
# use scripts/publish_playstore.sh — it builds (via this script) then pushes
# to the internal track with `fastlane supply` (CR048). No web UI.
#
# Usage:
#   scripts/build_playstore.sh                  # bump + build + show path
#   scripts/build_playstore.sh --no-bump        # use whatever's in pubspec
#   scripts/build_playstore.sh --no-commit      # don't auto-commit the bump
#
# Required env (defaults match the production alpha setup):
#   AMI_API_URL_ALPHA              - backend URL baked into the build
#   GOOGLE_OAUTH_WEB_CLIENT_ID     - GCP OAuth 2.0 Web client_id for Google Sign-In
#                                    (the same value the backend has in
#                                     GOOGLE_AUDIENCES env var on melehost)
#   SENTRY_DSN                     - optional; left empty if unset
#
# Required setup before first run (per D-057):
#   - ~/.android-keys/ami-trade-upload.keystore     (Saiful's keystore)
#   - ~/.android-keys/keystore.properties           (referenced from build.gradle.kts)
#     Format:
#       storeFile=/Users/<saiful>/.android-keys/ami-trade-upload.keystore
#       storePassword=<...>
#       keyAlias=upload
#       keyPassword=<...>

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="${PROJECT_ROOT}/mobile"

: "${AMI_API_URL_ALPHA:=https://api-alpha.agenticmarketintel.ai}"
# CR050 — GCP OAuth 2.0 **Web** client_id (ami-trade-web). Public config: it is
# stamped into the Google ID token's `aud` and the backend verifies it against
# GOOGLE_AUDIENCES. Baked as the default so Google Sign-In is never silently
# disabled by a forgotten export (DEF038-class). Override via env if the key rotates.
: "${GOOGLE_OAUTH_WEB_CLIENT_ID:=153141744056-03d6sabmvita0a2civs6e0ngjoac54v7.apps.googleusercontent.com}"
: "${SENTRY_DSN:=}"

DO_BUMP=1
DO_COMMIT=1
for arg in "$@"; do
  case "$arg" in
    --no-bump)   DO_BUMP=0 ;;
    --no-commit) DO_COMMIT=0 ;;
    -h|--help)
      sed -n '2,/^$/p' "$0"
      exit 0
      ;;
    *)
      echo "✗ unknown flag: $arg" >&2
      exit 2
      ;;
  esac
done

keystore_props="$HOME/.android-keys/keystore.properties"
if [[ ! -f "$keystore_props" ]]; then
  echo "⚠ no keystore at $keystore_props — Gradle will fall back to DEBUG signing"
  echo "  That AAB will NOT be accepted by Play Console. Set up the keystore"
  echo "  first (per D-057 / docs/initial_specs/10_delivery/you_do_i_do.md), then re-run."
  echo "  Continuing anyway for local smoke testing only."
  echo ""
fi

pubspec="${MOBILE_DIR}/pubspec.yaml"
current_line=$(grep -E "^version:" "$pubspec")
current_version=$(echo "$current_line" | sed -E 's/version:[[:space:]]*//')
semver="${current_version%+*}"
build_num="${current_version#*+}"

if [[ "$DO_BUMP" == "1" ]]; then
  new_build=$((build_num + 1))
  new_version="${semver}+${new_build}"
  echo "▶ bumping pubspec: ${current_version} → ${new_version}"
  sed -i '' "s/^version: ${current_version}$/version: ${new_version}/" "$pubspec"
  build_num="$new_build"
  if [[ "$DO_COMMIT" == "1" ]]; then
    (cd "$PROJECT_ROOT" && git add mobile/pubspec.yaml && \
      git commit -m "chore(mobile): bump build ${semver}+$((build_num - 1)) → ${semver}+${build_num} for Play Store" \
      > /dev/null && echo "▶ committed bump")
  fi
else
  echo "▶ using existing version ${semver}+${build_num} (--no-bump)"
fi

if [[ -z "$GOOGLE_OAUTH_WEB_CLIENT_ID" ]]; then
  echo "⚠ GOOGLE_OAUTH_WEB_CLIENT_ID is empty — Google Sign-In button will be"
  echo "  disabled in this build. Set it once the GCP OAuth Web client is created."
  echo ""
fi

echo "▶ flutter build appbundle  (release, signed if keystore present)"
cd "$MOBILE_DIR"
flutter build appbundle --release \
  --dart-define=ALLOW_BACKEND_SWITCH=true \
  --dart-define=AMI_API_URL_ALPHA="${AMI_API_URL_ALPHA}" \
  --dart-define=GOOGLE_OAUTH_WEB_CLIENT_ID="${GOOGLE_OAUTH_WEB_CLIENT_ID}" \
  --dart-define=SENTRY_DSN="${SENTRY_DSN}"

aab="${MOBILE_DIR}/build/app/outputs/bundle/release/app-release.aab"
if [[ ! -f "$aab" ]]; then
  echo "✗ no AAB produced at $aab — flutter build appbundle failed?"
  exit 1
fi
size_mb=$(du -m "$aab" | cut -f1)
echo "▶ built $(basename "$aab") (${size_mb} MB, build ${semver}+${build_num})"

echo ""
echo "✓ AAB ready: ${aab}"
echo ""
echo "Next step — manual upload to Play Console internal track:"
echo "  1. open  https://play.google.com/console"
echo "  2. App → Testing → Internal testing → Create new release"
echo "  3. Upload  ${aab}"
echo "  4. Fill release notes, save, review, roll out"
echo ""
echo "First upload also enrolls in Play App Signing (one-time, irreversible)."
echo "Internal testers get the build via the opt-in link once review completes."
echo ""
echo "After that first upload, ship release #2+ with one command:"
echo "  scripts/publish_playstore.sh          # build + fastlane push to internal"
