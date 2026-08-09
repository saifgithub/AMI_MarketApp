#!/usr/bin/env bash
# Build the iOS Simulator .app the UAT harness drives, and install it (CR162).
#
# This is NOT a shipping build path. It exists because black-box UI automation
# on iOS is impossible against a normal build: Flutter paints to a canvas, so
# XCUITest can only see the accessibility semantics tree, and the iOS engine
# gates that tree on
#
#     UIAccessibilityIsVoiceOverRunning() || UIAccessibilityIsSwitchControlRunning()
#
# (flutter#25485, open since 2018). Without VoiceOver actually running, the whole
# app presents as one opaque FlutterView with an empty page source. So this build
# passes --dart-define=AMI_QA_SEMANTICS=1, which makes main.dart call
# SemanticsBinding.instance.ensureSemantics() and force the tree on.
#
# Android needs none of this — its accessibility tree is built as soon as a
# client interrogates the window, which is why scripts/install_android.sh has no
# equivalent flag and the rig has always worked without one.
#
# Why the Simulator and not the real iPhone: no WebDriverAgent provisioning, no
# Apple developer cert, no device to keep unlocked. The real iPhone 17 is the
# follow-up once this suite is green — a device profile plus signing caps in
# qa/appium/config/, not new code here.
#
# Why debug-mode and not release: a Simulator build cannot be release-signed the
# way scripts/install_iphone.sh does for a device, and the Simulator runs the
# same Skia/Impeller rendering path either way. The semantics tree — the only
# thing this harness reads — is identical. Where it differs from
# install_iphone.sh's reasoning (release, because JIT is slow and shows
# non-representative overlays on real hardware) is that none of that applies to
# a Mac-hosted Simulator.
#
# Usage:
#   scripts/build_qa_ios_sim.sh                 # build + install on "iPhone 17"
#   scripts/build_qa_ios_sim.sh --sim "iPhone 16 Pro"
#   scripts/build_qa_ios_sim.sh --no-install    # build only

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="${PROJECT_ROOT}/mobile"

SIM_NAME="${AMI_IOS_SIM_NAME:-iPhone 17}"
DO_INSTALL=1

while (( $# )); do
  case "$1" in
    --sim) shift; SIM_NAME="$1" ;;
    --no-install) DO_INSTALL=0 ;;
    -h|--help) sed -n '2,/^set -euo/p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

# Same backend wiring as scripts/run_dev.sh — the harness drives the app against
# Alpha, so it must reach the same backend a tester would.
: "${AMI_API_URL_ALPHA:=https://api-alpha.agenticmarketintel.ai}"
: "${AMI_API_URL_BETA:=}"
: "${AMI_API_URL_PROD:=}"
: "${SENTRY_DSN:=}"

BUNDLE_ID="ai.agenticmarketintel.amiTrade"
APP_PATH="${MOBILE_DIR}/build/ios/iphonesimulator/Runner.app"

echo "▶ QA iOS Simulator build (CR162)"
echo "  simulator:  ${SIM_NAME}"
echo "  alpha URL:  ${AMI_API_URL_ALPHA}"
echo "  semantics:  AMI_QA_SEMANTICS=1  ← the whole point of this script"
echo ""

cd "${MOBILE_DIR}"
flutter build ios --simulator --debug \
  --dart-define=AMI_QA_SEMANTICS=1 \
  --dart-define=ALLOW_BACKEND_SWITCH=true \
  --dart-define=AMI_API_URL_ALPHA="${AMI_API_URL_ALPHA}" \
  --dart-define=AMI_API_URL_BETA="${AMI_API_URL_BETA}" \
  --dart-define=AMI_API_URL_PROD="${AMI_API_URL_PROD}" \
  --dart-define=SENTRY_DSN="${SENTRY_DSN}"

[ -d "${APP_PATH}" ] || {
  echo "✗ expected app bundle not found at ${APP_PATH}" >&2
  echo "  flutter build reported success — check the path above against its output." >&2
  exit 1
}
echo ""
echo "✓ built ${APP_PATH}"

if (( ! DO_INSTALL )); then
  echo "  (--no-install: stopping here)"
  exit 0
fi

UDID="$(xcrun simctl list devices available --json \
  | python3 -c "
import json,sys
name=sys.argv[1]
data=json.load(sys.stdin)['devices']
hits=[d for ds in data.values() for d in ds if name.lower() in d['name'].lower()]
if not hits:
    sys.exit('no available simulator matching %r' % name)
booted=[d for d in hits if d['state']=='Booted']
print((booted or hits)[0]['udid'])
" "${SIM_NAME}")"

echo "▶ simulator UDID: ${UDID}"
xcrun simctl boot "${UDID}" 2>/dev/null || true   # already-booted exits non-zero
xcrun simctl bootstatus "${UDID}" >/dev/null
xcrun simctl install "${UDID}" "${APP_PATH}"
echo "✓ installed ${BUNDLE_ID}"
echo ""
echo "Next:"
echo "  appium --address 127.0.0.1 --port 4723 &"
echo "  cd qa/appium && AMI_PLATFORM=ios AMI_IOS_SIM_NAME='${SIM_NAME}' .venv/bin/python -m pytest -m smoke -v"
