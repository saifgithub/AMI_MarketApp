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
  --dart-define=SENTRY_DSN="${SENTRY_DSN}"

APK="${MOBILE_DIR}/build/app/outputs/flutter-apk/app-release.apk"

# CR078 — publish the APK to melehost's shared folder, replacing what's there.
# Saiful hands this path out for sideloading, so a stale copy is worse than no
# copy: it looks current and isn't. Failure is reported loudly at the end rather
# than aborting, so a LAN hiccup never costs an otherwise-good device install.
: "${AMI_APK_SHARE_DEST:=saiful@192.168.20.59:/home/saiful/hermes_folder/project/AMI_MarketApps/apk/}"
SHARE_OK=0
if [[ ! -f "$APK" ]]; then
  echo "✗ no APK at $APK — flutter build apk failed?" >&2
  exit 1
fi
echo "▶ publishing APK → ${AMI_APK_SHARE_DEST}"
if scp -o ConnectTimeout=10 "$APK" "$AMI_APK_SHARE_DEST"; then
  SHARE_OK=1
  echo "✓ shared copy replaced"
else
  echo "⚠ scp FAILED — the shared copy at ${AMI_APK_SHARE_DEST} is now STALE." >&2
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
if [[ "$SHARE_OK" == "1" ]]; then
  echo "✓ shared APK is current: ${AMI_APK_SHARE_DEST}"
else
  echo "✗ shared APK is STALE — ${AMI_APK_SHARE_DEST} still holds the previous build."
  echo "  Re-run, or copy by hand:  scp \"${APK}\" \"${AMI_APK_SHARE_DEST}\""
fi
if [[ "$INSTALLED" == "0" ]]; then
  echo "✗ no devices were updated. Plug in a device with USB debugging enabled."
  echo "  Run  scripts/install_android.sh --list  to see what's connected."
  exit 1
fi
echo "✓ done — ${INSTALLED} device(s) updated. Launch AMI Trade from the home screen."
echo "  APK also at: ${APK}  (share via WhatsApp to install on other devices)"
