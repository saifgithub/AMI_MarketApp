#!/usr/bin/env bash
# Build a release IPA and install it on TESTING IPHONE 13 (or any target
# device passed as $1) — release mode, signed with the same Distribution
# cert TestFlight uses, but installed locally rather than uploaded.
#
# Why release and not debug: debug builds use the JIT VM, run slowly on
# real hardware, and show overlays that don't represent the actual user
# experience. Release matches what TestFlight + the App Store ship.
#
# This is the "send me the latest build" workflow for solo testing —
# NOT the TestFlight upload workflow. See scripts/build_testflight.sh
# for that.
#
# Usage:
#   scripts/install_iphone.sh                       # default: TESTING IPHONE 13
#   scripts/install_iphone.sh <device-id>           # specific device
#   scripts/install_iphone.sh --device-id <id>      # same
#
# Run `flutter devices` to list connected devices and their IDs.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="${PROJECT_ROOT}/mobile"

# TESTING IPHONE 13's wireless UDID — overrideable via $1 or --device-id.
DEFAULT_DEVICE_ID="00008110-000261101A22801E"
DEVICE_ID="$DEFAULT_DEVICE_ID"

while (( $# )); do
  case "$1" in
    --device-id) shift; DEVICE_ID="$1" ;;
    -h|--help)
      sed -n '2,/^$/p' "$0"
      exit 0
      ;;
    *) DEVICE_ID="$1" ;;
  esac
  shift
done

: "${AMI_API_URL_ALPHA:=https://api-alpha.agenticmarketintel.ai}"

echo "▶ Target device: ${DEVICE_ID}"
echo "▶ Alpha URL:     ${AMI_API_URL_ALPHA}"

cd "$MOBILE_DIR"

# Confirm the device is actually connected before spending 30s on a build
# that lands nowhere.
if ! flutter devices 2>/dev/null | grep -q "${DEVICE_ID}"; then
  echo "✗ device ${DEVICE_ID} is not connected."
  echo ""
  echo "Connected devices:"
  flutter devices 2>/dev/null | sed 's/^/  /'
  echo ""
  echo "If TESTING IPHONE 13 is asleep, wake it; wireless devices need the"
  echo "Mac and iPhone on the same LAN and the phone unlocked at least once."
  exit 1
fi

echo "▶ flutter build ios --release"
flutter build ios --release \
  --dart-define=ALLOW_BACKEND_SWITCH=true \
  --dart-define=AMI_API_URL_ALPHA="${AMI_API_URL_ALPHA}"

echo "▶ flutter install -d ${DEVICE_ID}"
flutter install -d "${DEVICE_ID}"

echo ""
echo "✓ installed. Launch the app from the home screen on the device."
echo "  (Auto-launch via CLI requires the macOS Automation permission for"
echo "   Flutter to control Xcode — see notes in HANDOVER.md.)"
