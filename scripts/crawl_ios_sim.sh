#!/usr/bin/env bash
# Autonomously crawl the app on the iOS Simulator and report defects (CR163).
#
# One command: build the QA app, install it, drive it, read back what broke.
#
#   scripts/crawl_ios_sim.sh                       # 4-minute crawl
#   scripts/crawl_ios_sim.sh --budget 600          # longer = deeper
#   scripts/crawl_ios_sim.sh --no-build            # reuse the installed app
#   scripts/crawl_ios_sim.sh --show-known          # ignore the triage ledger
#   scripts/crawl_ios_sim.sh --text-size huge      # crawl at the largest Dynamic Type
#
# --text-size huge is HIGH YIELD and worth knowing about. The very first sink
# capture, taken at accessibility-extra-extra-extra-large, produced a real
# RenderFlex overflow on the launch screen within 25 seconds. Fixed layouts and
# FittedBox labels survive the default size and fall apart at the largest one,
# which is a real accessibility requirement rather than a synthetic stress.
#
# Why the Simulator and not a device: real devices get store builds only
# (Saiful, 2026-08-10), and a store build cannot carry the QA dart-define this
# needs. See CR162.
#
# What this does NOT do: file anything. Review the report, then promote the real
# ones with `qa/appium/tools/triage.py`. That gate exists because CR080 twice
# had a harness bug written up as application failures — and with a fixer agent
# waiting on the queue, an auto-filing crawler would generate fixes for defects
# that never existed.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HARNESS="${PROJECT_ROOT}/qa/appium"

SIM_NAME="${AMI_IOS_SIM_NAME:-iPhone 17}"
BUDGET=240
DEPTH=3
DO_BUILD=1
TEXT_SIZE=""
EXTRA=()

while (( $# )); do
  case "$1" in
    --budget) shift; BUDGET="$1" ;;
    --depth) shift; DEPTH="$1" ;;
    --sim) shift; SIM_NAME="$1" ;;
    --no-build) DO_BUILD=0 ;;
    --show-known) EXTRA+=(--no-ledger) ;;
    --text-size) shift; TEXT_SIZE="$1" ;;
    -h|--help) sed -n '2,/^set -euo/p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

[ -x "${HARNESS}/.venv/bin/python" ] || {
  echo "✗ harness venv missing. Create it:" >&2
  echo "    cd qa/appium && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
}

# Appium must already be up. Starting it here would leave an orphan server
# behind on every run, and a stale server is how three runs in a row got
# misattributed to the app rather than the harness.
if ! curl -sf http://127.0.0.1:4723/status >/dev/null 2>&1; then
  echo "✗ no Appium server on 127.0.0.1:4723. In another terminal:" >&2
  echo "    appium --address 127.0.0.1 --port 4723" >&2
  exit 1
fi

RUN_ID="$(date -u +%Y-%m-%dT%H%M%SZ)-ios"
RUN_DIR="${AMI_CRAWL_DIR:-${PROJECT_ROOT}/qa/appium/_runs}/${RUN_ID}"
mkdir -p "${RUN_DIR}"

echo "▶ crawl ${RUN_ID}"
echo "  simulator: ${SIM_NAME}"
echo "  budget:    ${BUDGET}s, depth ${DEPTH}"
echo "  output:    ${RUN_DIR}"
echo ""

if (( DO_BUILD )); then
  # Builds --debug WITH AMI_QA_SEMANTICS=1. Both matter: the flag installs the
  # error sink and forces the semantics tree; debug is what makes Flutter report
  # framework errors at all (release compiles most of them out, so a release
  # crawl finds only hard crashes).
  "${PROJECT_ROOT}/scripts/build_qa_ios_sim.sh" --sim "${SIM_NAME}"
  echo ""
fi

if [ -n "${TEXT_SIZE}" ]; then
  case "${TEXT_SIZE}" in
    huge) CONTENT_SIZE="accessibility-extra-extra-extra-large" ;;
    large) CONTENT_SIZE="extra-extra-extra-large" ;;
    default) CONTENT_SIZE="medium" ;;
    *) CONTENT_SIZE="${TEXT_SIZE}" ;;
  esac
  UDID="$("${PROJECT_ROOT}/scripts/resolve_sim_udid.py" "${SIM_NAME}")"
  echo "▶ Dynamic Type: ${CONTENT_SIZE}"
  xcrun simctl ui "${UDID}" content_size "${CONTENT_SIZE}"
  # Relaunch so the app rebuilds its layout at the new size; MediaQuery updates
  # live, but a cold start is what a user with this setting actually sees.
  xcrun simctl terminate "${UDID}" ai.agenticmarketintel.amiTrade 2>/dev/null || true
  echo ""
fi

cd "${HARNESS}"
set +e
.venv/bin/python -m crawler.run \
  --out "${RUN_DIR}" \
  --budget "${BUDGET}" \
  --depth "${DEPTH}" \
  --sim-name "${SIM_NAME}" \
  "${EXTRA[@]+"${EXTRA[@]}"}"
RC=$?
set -e

echo ""
if [ "$RC" -eq 2 ]; then
  # Loud, not a silent zero-findings report: a run that could not read the
  # error sink has not tested error reporting at all.
  echo "⚠ the run completed but could NOT read the app's error sink."
  echo "  Flutter-error findings are MISSING. Layout findings are still valid."
  echo "  Usual cause: the installed build lacks --dart-define=AMI_QA_SEMANTICS=1."
elif [ "$RC" -ne 0 ]; then
  echo "✗ crawl failed (exit ${RC})"
  exit "$RC"
fi

echo "Next:"
echo "  open ${RUN_DIR}/report.md"
echo "  cd qa/appium && .venv/bin/python tools/triage.py '${RUN_DIR}'          # list findings"
echo "  cd qa/appium && .venv/bin/python tools/triage.py '${RUN_DIR}' --file <fp>   # promote to the fix queue"
