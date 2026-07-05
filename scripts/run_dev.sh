#!/usr/bin/env bash
# Run the AMI Trade Flutter app against the Alpha backend on melehost.
#
# The Mac no longer runs a backend or a database — that all lives on
# melehost (Ubuntu, 192.168.20.9, public hostname
# https://api-alpha.agenticmarketintel.ai). To change backend code,
# edit on the Mac and run /promote-to-alpha to ship the change to
# melehost, then hot-reload here.
#
# Usage:
#   scripts/run_dev.sh              # run on TESTING IPHONE 13 (default)
#   scripts/run_dev.sh simulator    # run on iOS simulator
#   scripts/run_dev.sh <device-id>  # specific device — passed to `flutter run -d`
#
# The build comes up with ALLOW_BACKEND_SWITCH=true so you can flip
# between alpha / beta / prod from Settings → Developer at runtime.
# The three URLs are baked in from the dart-defines below; if you
# omit BETA / PROD they'll show as "not in this build" and only
# Alpha will be reachable. See docs/initial_specs/08_tech/backend_modes.md.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="${PROJECT_ROOT}/mobile"

TARGET="${1:-TESTING IPHONE 13}"

# Backend URLs. Override any of these via env if you're testing against
# a different deployment (e.g. AMI_API_URL_ALPHA=http://localhost:8000
# if you're temporarily running a backend on the Mac for some reason).
: "${AMI_API_URL_ALPHA:=https://api-alpha.agenticmarketintel.ai}"
: "${AMI_API_URL_BETA:=}"
: "${AMI_API_URL_PROD:=}"
: "${SENTRY_DSN:=}"

echo "▶ Flutter target: ${TARGET}"
echo "▶ Alpha URL:      ${AMI_API_URL_ALPHA}"
[[ -n "${AMI_API_URL_BETA}" ]] && echo "▶ Beta URL:       ${AMI_API_URL_BETA}"
[[ -n "${AMI_API_URL_PROD}" ]] && echo "▶ Prod URL:       ${AMI_API_URL_PROD}"
echo ""

# Quick reachability check on the active hostname so we fail fast if
# the tunnel or melehost is down. Skip for the dummy URLs.
if [[ "${AMI_API_URL_ALPHA}" == http* ]]; then
  if ! curl -sfo /dev/null "${AMI_API_URL_ALPHA}/v1/health"; then
    echo "⚠ Couldn't reach ${AMI_API_URL_ALPHA}/v1/health — is melehost up?"
    echo "  ssh melehost 'docker ps --filter name=ami_'"
    echo "  Continuing anyway, but the app may fail on first request."
    echo ""
  fi
fi

cd "${MOBILE_DIR}"
echo "▶ Running Flutter on ${TARGET}…"
echo "  Once running:"
echo "    r → hot reload"
echo "    R → hot restart"
echo "    q → quit"
echo ""

exec flutter run -d "${TARGET}" \
  --dart-define=ALLOW_BACKEND_SWITCH=true \
  --dart-define=AMI_API_URL_ALPHA="${AMI_API_URL_ALPHA}" \
  --dart-define=AMI_API_URL_BETA="${AMI_API_URL_BETA}" \
  --dart-define=AMI_API_URL_PROD="${AMI_API_URL_PROD}" \
  --dart-define=SENTRY_DSN="${SENTRY_DSN}"
