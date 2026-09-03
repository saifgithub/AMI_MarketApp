#!/usr/bin/env bash
# Build a release APK and install it on connected Android devices.
#
# Defaults to installing on all known test devices (Galaxy Note Fan +
# Galaxy A17). Pass a specific serial to target just one.
#
# Usage:
#   scripts/install_android.sh                        # all known devices
#   scripts/install_android.sh <serial>               # specific device
#   scripts/install_android.sh --device-id <serial>   # same
#   scripts/install_android.sh --list                 # show connected devices
#
# Known test devices (hardcoded serials):
#   Galaxy Note Fan (SM-N935F)   ce10171a8017590d01
#   Galaxy A17     (SM-A176B)    R5CY91AY99Y
#
# Run `scripts/install_android.sh --list` to find the serial of a new device.
#
# ADB must be on PATH or at $ANDROID_HOME/platform-tools/adb.
# USB debugging must be enabled on the target device.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="${PROJECT_ROOT}/mobile"

# Known test device serials
NOTE_FAN="ce10171a8017590d01"
A17="R5CY91AY99Y"
ALL_KNOWN=("$NOTE_FAN" "$A17")

: "${AMI_API_URL_ALPHA:=https://api-alpha.agenticmarketintel.ai}"
# CR050 — GCP OAuth 2.0 **Web** client_id (ami-trade-web). Public config: it is
# stamped into the Google ID token's `aud` and the backend verifies it against
# GOOGLE_AUDIENCES. Baked as the default so Google Sign-In is never silently
# disabled by a forgotten export (DEF038-class). Override via env if the key rotates.
: "${GOOGLE_OAUTH_WEB_CLIENT_ID:=153141744056-03d6sabmvita0a2civs6e0ngjoac54v7.apps.googleusercontent.com}"
: "${SENTRY_DSN:=}"

# Locate adb
if command -v adb &>/dev/null; then
  ADB="adb"
elif [[ -n "${ANDROID_HOME:-}" && -f "$ANDROID_HOME/platform-tools/adb" ]]; then
  ADB="$ANDROID_HOME/platform-tools/adb"
else
  echo "✗ adb not found. Add \$ANDROID_HOME/platform-tools to PATH." >&2
  exit 1
fi

# Arg parsing
TARGET_SERIAL=""
LIST_ONLY=0
while (( $# )); do
  case "$1" in
    --device-id) shift; TARGET_SERIAL="$1" ;;
    --list)      LIST_ONLY=1 ;;
    -h|--help)
      sed -n '2,/^$/p' "$0"
      exit 0
      ;;
    *) TARGET_SERIAL="$1" ;;
  esac
  shift
done

# --list: show connected devices and exit
if [[ "$LIST_ONLY" == "1" ]]; then
  echo "Connected Android devices:"
  "$ADB" devices | tail -n +2 | grep -v "^$" | while read -r serial state; do
    model=$("$ADB" -s "$serial" shell getprop ro.product.model 2>/dev/null | tr -d '\r') || model="?"
    echo "  $model ($serial)  [$state]"
  done
  exit 0
fi

# Determine target list
if [[ -n "$TARGET_SERIAL" ]]; then
  TARGETS=("$TARGET_SERIAL")
else
  TARGETS=("${ALL_KNOWN[@]}")
fi

# Build once
echo "▶ Alpha URL : ${AMI_API_URL_ALPHA}"
echo "▶ flutter build apk --release"
cd "$MOBILE_DIR"
flutter build apk --release \
  --dart-define=ALLOW_BACKEND_SWITCH=true \
  --dart-define=AMI_API_URL_ALPHA="${AMI_API_URL_ALPHA}" \
  --dart-define=GOOGLE_OAUTH_WEB_CLIENT_ID="${GOOGLE_OAUTH_WEB_CLIENT_ID}" \
  --dart-define=SENTRY_DSN="${SENTRY_DSN}" \
  --dart-define=AMI_GAMES=true

APK="${MOBILE_DIR}/build/app/outputs/flutter-apk/app-release.apk"

if [[ ! -f "$APK" ]]; then
  echo "✗ no APK at $APK — flutter build apk failed?" >&2
  exit 1
fi

# CR109 — prove the AMI_GAMES define actually took, don't assume it.
#
# `bool.fromEnvironment` accepts ONLY the literal strings "true"/"false";
# anything else silently falls back to the default. Passing AMI_GAMES=1 built
# and installed a perfectly good APK with the game stripped out, and every
# step reported success (AT:R66). A flag that fails silently is worse than one
# that fails loudly, so verify the artefact rather than trusting the flag.
#
# Method: a games-only string must be present in the AOT snapshot. Verified
# against a control (strings that exist in every build are findable this way),
# so an empty result means absent, not unsearchable.
_games_in_apk() {
  local tmp; tmp=$(mktemp -d)
  unzip -q -o "$APK" "lib/arm64-v8a/libapp.so" -d "$tmp" 2>/dev/null || { rm -rf "$tmp"; return 1; }
  local so="$tmp/lib/arm64-v8a/libapp.so"
  [[ -f "$so" ]] || { rm -rf "$tmp"; return 1; }
  local hits control
  # DEF301 — a games-only widget Key, not the ARB disclosure heading, which a
  # copy edit would change without anyone noticing this gate stopped testing.
  hits=$(strings "$so" | grep -ic "games_close_beat_insight" || true)
  control=$(strings "$so" | grep -ic "EDUCATIONAL SIMULATION" || true)
  rm -rf "$tmp"
  [[ "$control" -gt 0 ]] || { echo "control-missing"; return 0; }
  [[ "$hits" -gt 0 ]] && echo "present" || echo "absent"
}

GAMES_CHECK=$(_games_in_apk || echo "unreadable")
case "$GAMES_CHECK" in
  present) echo "▶ AMI_GAMES verified present in the APK" ;;
  absent)
    echo "✗ AMI_GAMES did NOT take — the APK has no game in it." >&2
    echo "  bool.fromEnvironment accepts only \"true\"/\"false\"; any other" >&2
    echo "  value (e.g. =1) silently compiles to the default, false." >&2
    echo "  Check the --dart-define=AMI_GAMES=true line above." >&2
    exit 1
    ;;
  control-missing)
    echo "⚠ games-string check inconclusive — the control string was also" >&2
    echo "  absent, so the search method is no longer valid for this build." >&2
    echo "  Not failing the install, but the gate is UNVERIFIED." >&2
    ;;
  *) echo "⚠ could not read the APK to verify AMI_GAMES — gate UNVERIFIED." >&2 ;;
esac

# DEF306 — leave a NAMED copy beside the fixed path.
#
# `build/app/outputs/flutter-apk/app-release.apk` is one filename that three
# producers write and none label: this script (games ON), share_apk_to_tester.sh
# (games OFF unless the caller says otherwise) and a bare `flutter build apk`
# (games OFF). The version comes from pubspec.yaml either way, so an APK copied
# off the Mac carries no record of which one made it — that is what cost an
# `adb dumpsys` and a `libapp.so` extraction to work out. The installed app now
# states its own gates under Settings; this is the same fact on the artifact,
# for the window before it is installed.
APK_VERSION=$(awk '/^version:/{print $2; exit}' "${MOBILE_DIR}/pubspec.yaml")
LABELLED_APK="${MOBILE_DIR}/build/app/outputs/flutter-apk/app-release-${APK_VERSION}-games.apk"
if cp "$APK" "$LABELLED_APK" 2>/dev/null; then
  echo "▶ labelled copy: $(basename "$LABELLED_APK")"
else
  echo "⚠ could not write the labelled copy — the APK at the shared path is unlabelled." >&2
fi

# CR079 (supersedes CR078's inline copy) — refresh the automated tester's APK on
# melehost. The scp lives in one place, scripts/share_apk_to_tester.sh, shared
# with the store-release path so the rig is refreshed on EVERY build. Guarded so
# a LAN hiccup can never abort an otherwise-good device install; the helper
# prints its own loud STALE warning, which its exit code echoes into SHARE_OK.
#
# The shared script owns the default destination and fallback logic (primary LAN IP
# vs. Tailscale fallback). Pass through any caller override via AMI_APK_SHARE_DEST
# env var, but let the shared script's defaults take over if not set.
SHARE_OK=0
if [[ -n "${AMI_APK_SHARE_DEST:-}" ]]; then
  # Caller set an override; pass it through to the shared script.
  if AMI_APK_SHARE_DEST="$AMI_APK_SHARE_DEST" "${PROJECT_ROOT}/scripts/share_apk_to_tester.sh" "$APK"; then
    SHARE_OK=1
  fi
else
  # No caller override; let the shared script's fallback logic choose LAN or Tailscale.
  if "${PROJECT_ROOT}/scripts/share_apk_to_tester.sh" "$APK"; then
    SHARE_OK=1
  fi
fi

# Install on each target
INSTALLED=0
for SERIAL in "${TARGETS[@]}"; do
  STATE=$("$ADB" devices | awk -v s="$SERIAL" '$1==s {print $2}')
  if [[ "$STATE" != "device" ]]; then
    echo "⚠ $SERIAL not connected (state: ${STATE:-not found}) — skipping"
    continue
  fi
  MODEL=$("$ADB" -s "$SERIAL" shell getprop ro.product.model 2>/dev/null | tr -d '\r') || MODEL="?"
  echo "▶ installing on ${MODEL} (${SERIAL})"
  "$ADB" -s "$SERIAL" install -r "$APK"
  echo "✓ installed on ${MODEL}"
  INSTALLED=$((INSTALLED + 1))
done

echo ""
# The automated-tester APK status was already printed by share_apk_to_tester.sh
# above; SHARE_OK just gates the one-line reminder here so a stale rig can't hide
# under a wall of adb output.
if [[ "$SHARE_OK" != "1" ]]; then
  echo "✗ automated-tester APK is STALE — re-run or fix the LAN route (see above)."
fi
if [[ "$INSTALLED" == "0" ]]; then
  echo "✗ no devices were updated. Plug in a device with USB debugging enabled."
  echo "  Run  scripts/install_android.sh --list  to see what's connected."
  exit 1
fi
echo "✓ done — ${INSTALLED} device(s) updated. Launch AMI Trade from the home screen."
echo "  APK also at: ${APK}  (share via WhatsApp to install on other devices)"
