#!/usr/bin/env bash
# Run the Appium UAT harness on the melehost Android rig (Galaxy A17) for
# scripts/uat/run_uat.sh --device android (CR263).
#
#   scripts/uat/android_rig.sh <run_dir> [--no-build] [--uat-ids-file <file>]
#
# 1. Build a fresh release APK and push it to the rig (share_apk_to_tester.sh),
#    so the Android evidence is for the code being released, not whatever the
#    rig last installed. --no-build tests the APK already on the phone.
# 2. Sync qa/appium/ + qa/uat/uat_plugin.py into the rig's harness/. ADDITIVE:
#    never --delete, and never test_data/.env — the rig-only Alpaca keys live
#    there and DEF434 was exactly a --delete that wiped them.
# 3. On the rig, take bin/pipeline.sh's flock (so the hourly cron and this run
#    never drive the phone at once), install the new APK, run smoke, then the
#    rest with the UAT results plugin.
# 4. Copy uat_results.json / junit.xml / summary.json back to <run_dir>/android/.
#
# Exit: the remote pytest status (0 green, 1 failures, 2 smoke gate failed,
# 3 rig precondition, 75 lock not acquired within an hour).

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST="${AMI_RIG_HOST:-melehost}"
RIG="/home/saiful/projects/AMI_MarketApp"

RUN_DIR="${1:?usage: android_rig.sh <run_dir> [--no-build] [--uat-ids-file <file>]}"
shift
BUILD=1; IDS_FILE=""
while (( $# )); do
  case "$1" in
    --no-build) BUILD=0 ;;
    --uat-ids-file) shift; IDS_FILE="$1" ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
RUN_ID="$(basename "$RUN_DIR")-uat-android"
OUT="${RUN_DIR}/android"
mkdir -p "$OUT"

if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" true 2>/dev/null; then
  echo "   rig: cannot ssh to ${HOST} (key not loaded? run ssh-add)" >&2
  exit 3
fi

if (( BUILD )); then
  echo "   rig: building + sharing a fresh release APK"
  if ! "${PROJECT_ROOT}/scripts/share_apk_to_tester.sh" > "${OUT}/apk_build.log" 2>&1; then
    echo "   rig: APK build/share failed — see ${OUT}/apk_build.log" >&2
    exit 3
  fi
fi

echo "   rig: syncing harness (additive, test_data/.env untouched)"
rsync -a \
  --exclude '.venv/' --exclude '_report/' --exclude '_runs/' --exclude '__pycache__/' \
  --exclude '.pytest_cache/' --exclude '.DS_Store' --exclude 'test_data/.env' \
  "${PROJECT_ROOT}/qa/appium/" "${HOST}:${RIG}/harness/" || { echo "   rig: harness rsync failed" >&2; exit 3; }
rsync -a "${PROJECT_ROOT}/qa/uat/uat_plugin.py" "${HOST}:${RIG}/harness/uat_plugin.py" || exit 3
REMOTE_IDS=""
if [[ -n "$IDS_FILE" ]]; then
  REMOTE_IDS="${RIG}/reports/${RUN_ID}.ids"
  rsync -a "$IDS_FILE" "${HOST}:${REMOTE_IDS}" || exit 3
fi

echo "   rig: waiting for the rig lock, then running"
ssh -o BatchMode=yes "$HOST" \
  RUN_ID="$RUN_ID" DO_INSTALL="$BUILD" REMOTE_IDS="$REMOTE_IDS" bash -s <<'REMOTE'
set -uo pipefail
source /home/saiful/projects/AMI_MarketApp/bin/env.sh
exec 9>"${LOGS_DIR}/pipeline.lock"
flock -w 3600 9 || { echo "rig lock not acquired within 1h"; exit 75; }
STATE=$("$ADB" devices | awk -v s="$DEVICE_SERIAL" '$1==s {print $2}')
[[ "$STATE" == "device" ]] || { echo "rig: phone ${DEVICE_SERIAL} not connected (adb state: ${STATE:-absent}) — plug in + unlock + allow USB debugging"; exit 3; }
if [[ "$DO_INSTALL" == "1" ]]; then
  "${RIG_ROOT}/bin/install_if_new.sh" --force >/dev/null 2>&1
  irc=$?
  [[ $irc == 0 || $irc == 10 ]] || { echo "rig: APK install failed (rc=$irc)"; exit 3; }
fi
OUTDIR="${REPORTS_DIR}/${RUN_ID}"
mkdir -p "$OUTDIR"
cd "$HARNESS_DIR"
# Rig-only secrets (Alpaca paper keys, the phone's unlock PIN) — never in git.
if [[ -f test_data/.env ]]; then set -a; source test_data/.env; set +a; fi
export AMI_PLATFORM=android AMI_SERIAL="$DEVICE_SERIAL" AMI_REPORT_DIR="$OUTDIR" \
       UAT_LAYER=device UAT_PLATFORM=android UAT_RESULTS_JSON="${OUTDIR}/uat_results.json" \
       PYTHONPATH="$HARNESS_DIR"
"$PYTHON" -m pytest -m smoke -q -p uat_plugin > "${OUTDIR}/smoke.log" 2>&1 || { tail -3 "${OUTDIR}/smoke.log"; exit 2; }
ARGS=(-q -p uat_plugin -m "not smoke and not exhaustive" --junitxml="${OUTDIR}/junit.xml")
[[ -n "$REMOTE_IDS" ]] && ARGS+=("--uat-ids=@${REMOTE_IDS}")
"$PYTHON" -m pytest "${ARGS[@]}" > "${OUTDIR}/pytest.log" 2>&1
rc=$?
tail -2 "${OUTDIR}/pytest.log"
exit $rc
REMOTE
rc=$?

for f in uat_results.json junit.xml summary.json pytest.log smoke.log; do
  rsync -a "${HOST}:${RIG}/reports/${RUN_ID}/${f}" "${OUT}/${f}" 2>/dev/null || true
done
exit "$rc"
