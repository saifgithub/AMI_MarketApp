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
#   scripts/publish_playstore.sh --internal-only # required when the RC key is a test_… key
#
# Track: `internal` (PLAY_TRACK overrides). A RevenueCat Test Store key (test_…)
# is refused on any other track — simulated purchases must not reach a reviewed,
# non-team track. See CR084 "Alpha distribution constraint".
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

# CR084-ALPHA — which fastlane lane (= Play track) this publishes to. Hardcoded
# `internal` since CR048; kept as a variable so the Test Store guard below has
# something to assert against rather than trusting that nobody ever adds a flag.
: "${PLAY_TRACK:=internal}"

# CR084-ALPHA — a RevenueCat Test Store key (`test_…`) makes every purchase
# simulated: the buyer gets Plan + credits for real in our DB, for free. RC's own
# rule is "never submit an app to the App Store or Google Play that is configured
# with a Test Store API key"; our narrowing allows the Play *internal testing*
# track only, which is unreviewed and team-only. Anything wider is refused here,
# at the point of upload, not just at the point of build.
rc_android_key="${REVENUECAT_ANDROID_SDK_KEY:-}"
if [[ -z "$rc_android_key" && -f "${PROJECT_ROOT}/infra/alpha.env" ]]; then
  rc_android_key="$(grep -E '^REVENUECAT_ANDROID_SDK_KEY=' "${PROJECT_ROOT}/infra/alpha.env" 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' ' || true)"
fi
if [[ "$rc_android_key" == test_* && "$PLAY_TRACK" != "internal" ]]; then
  echo "✗ refusing to publish to the '${PLAY_TRACK}' track with a RevenueCat Test Store key." >&2
  echo "  Purchases would be simulated — every tester on that track gets paid" >&2
  echo "  entitlements for free, and the track is store-reviewed. Test Store" >&2
  echo "  builds go to 'internal' only (CR084 alpha distribution constraint)." >&2
  echo "  For a wider track, rebuild with the goog_… key and real Play products." >&2
  exit 1
fi

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
  echo "▶ fastlane ${PLAY_TRACK} (upload to the Play ${PLAY_TRACK} testing track)"
  # DEF283 — stamp the wall clock BEFORE fastlane so the report freshness check
  # below can tell "this run wrote it" from "a previous run left it there".
  run_started_at="$(date +%s)"
  bundle exec fastlane "${PLAY_TRACK}"

  # DEF283 — verify the upload from fastlane's own report rather than inferring
  # it from an exit code. `set -e` means reaching this line implies fastlane
  # returned 0, which is good evidence and not proof: the release verdict is the
  # one fact this script exists to establish, so it gets read back from the
  # artifact fastlane wrote. Twice now (0.1.0+87, 0.1.0+88) the verdict had to be
  # dug out of report.xml by hand after the fact, which is the tell that the
  # script was not reporting it.
  upload_report="${PROJECT_ROOT}/mobile/android/fastlane/report.xml"
  if [[ ! -f "$upload_report" ]]; then
    upload_status="UNVERIFIED — fastlane wrote no report.xml"
  elif [[ "$(stat -f %m "$upload_report")" -lt "$run_started_at" ]]; then
    # A leftover report from an earlier run must never read as this run's
    # success — a stale artifact that looks like a pass is DEF280's shape.
    upload_status="UNVERIFIED — report.xml is stale ($(date -r "$(stat -f %m "$upload_report")" '+%F %T'))"
  elif grep -q '<failure' "$upload_report"; then
    upload_status="FAILED — see $upload_report"
  elif grep -q 'upload_to_play_store' "$upload_report"; then
    upload_status="OK"
  else
    upload_status="UNVERIFIED — no upload_to_play_store step in report.xml"
  fi

  # CR079 — the store release ships an AAB to Play, but our automated tester on
  # melehost consumes an APK. Build + scp it here too so the rig is refreshed on
  # this build, not only when install_android.sh happens to run. Guarded: a scp
  # hiccup must not fail a release whose Play upload already succeeded — but the
  # helper's loud STALE warning still fires so a stale rig can't pass unnoticed.
  echo ""
  echo "▶ refreshing the automated-tester APK on melehost (CR079)"
  # DEF301 — hand the helper the SAME games choice this release was built
  # with. Without it the helper defaults false and the rig runs a 4-tab app
  # while Play serves a 5-tab one, both stamped with this version number.
  #
  # Derived from BUILD_ARGS, NOT from a `DO_GAMES` variable: that one lives
  # in build_playstore.sh and does not exist in this shell, so reading it
  # here would abort the release on `set -u` (unbound variable) at the last
  # step, AFTER the Play upload had already succeeded.
  _apk_games=true
  for _a in ${BUILD_ARGS[@]+"${BUILD_ARGS[@]}"}; do
    [[ "$_a" == "--no-games" ]] && _apk_games=false
  done
  if AMI_GAMES="$_apk_games" "${PROJECT_ROOT}/scripts/share_apk_to_tester.sh"; then
    apk_status="refreshed"
  else
    apk_status="STALE — see the warning above"
    echo "⚠ Play upload succeeded but the automated-tester APK is STALE — see above." >&2
  fi

  # DEF283 — the verdict is the LAST thing printed, always.
  #
  # It used to be printed immediately after the upload, and then the CR079 APK
  # refresh emitted ~30 lines of pub/gradle output on top of it. Anyone reading
  # the tail of a release log — which is how a long build is read — saw an APK
  # line and no upload result, so "did it publish?" had to be answered by
  # opening report.xml. A release script whose last line is about something
  # other than the release teaches you to go look somewhere else for the answer.
  version_line="$(grep -E '^version:' "${PROJECT_ROOT}/mobile/pubspec.yaml" | head -1 | awk '{print $2}')"
  echo ""
  echo "────────────────────────────────────────────────────────────────"
  echo "  PLAY RELEASE SUMMARY — ${version_line}"
  echo "    track                 : ${PLAY_TRACK}"
  echo "    upload                : ${upload_status}"
  echo "    automated-tester APK  : ${apk_status}"
  echo "────────────────────────────────────────────────────────────────"

  if [[ "$upload_status" != "OK" ]]; then
    echo "" >&2
    echo "✗ fastlane exited 0 but its report does not confirm the upload." >&2
    echo "  Treat this build as NOT published until you have checked the Play" >&2
    echo "  Console. Do not bump the build number again on top of it." >&2
    exit 1
  fi
  echo ""
  echo "✓ pushed to ${PLAY_TRACK} track — testers get it as a Play Store update."
fi
