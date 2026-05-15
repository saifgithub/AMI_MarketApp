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

cd "$MOBILE_DIR"

# Resolve target device via `flutter devices --machine` (JSON) instead of
# the text-mode listing, which triggers a LAN-wide wireless-discovery
# probe and prints loud unrelated errors for every paired-but-offline
# iPhone on the account (e.g. "Browsing on the local area network for
# Saiful's iPhone 17 … (code -27)"). The JSON variant skips that probe
# and just lists devices that are reachable right now.
TARGET_NAME=$(flutter devices --machine 2>/dev/null \
  | python3 -c "
import sys, json
try:
    devs = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for d in devs:
    if d.get('id') == '${DEVICE_ID}':
        print(d.get('name', ''))
        break
")

if [ -z "$TARGET_NAME" ]; then
  echo "✗ device ${DEVICE_ID} is not connected right now."
  echo ""
  echo "Reachable devices:"
  flutter devices --machine 2>/dev/null \
    | python3 -c "
import sys, json
try:
    devs = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for d in devs:
    print(f\"  {d.get('name', '?'):<28} {d.get('id', '?')}\")
"
  echo ""
  echo "If the target device is asleep, wake it; wireless devices need the"
  echo "Mac and iPhone on the same LAN and the phone unlocked at least once."
  exit 1
fi

echo "▶ Target device : ${TARGET_NAME} (${DEVICE_ID})"
echo "▶ Alpha URL     : ${AMI_API_URL_ALPHA}"

# Drop the LAN-discovery noise from build + install. We've already
# resolved the target by UDID; Flutter's complaints about other
# paired-but-offline devices are not actionable here.
_quiet() {
  grep -vE "Browsing on the local area network|opted into Developer Mode to connect wirelessly|\(code -27\)" || true
}

echo "▶ flutter build ios --release"
flutter build ios --release \
  --dart-define=ALLOW_BACKEND_SWITCH=true \
  --dart-define=AMI_API_URL_ALPHA="${AMI_API_URL_ALPHA}" \
  2> >(_quiet >&2)

echo "▶ flutter install -d ${DEVICE_ID} (${TARGET_NAME})"
flutter install -d "${DEVICE_ID}" 2> >(_quiet >&2)

echo ""
echo "✓ installed on ${TARGET_NAME}. Launch the app from the home screen."
echo "  (Auto-launch via CLI requires the macOS Automation permission for"
echo "   Flutter to control Xcode — see notes in HANDOVER.md.)"
