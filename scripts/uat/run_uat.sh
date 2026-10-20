#!/usr/bin/env bash
# Run the whole-app UAT (CR263) and record the results in the ledger.
#
#   scripts/uat/run_uat.sh --api                     # live-Alpha API cases
#   scripts/uat/run_uat.sh --device ios              # iOS Simulator (builds + installs the QA app)
#   scripts/uat/run_uat.sh --all                     # api + ios — the nightly run
#   scripts/uat/run_uat.sh --api --changed-only      # only cases not passing at their current version
#   flags: --no-llm (skip LLM-spending cases), --no-build (reuse the installed sim app)
#
# Each run writes qa/uat/_runs/<ts>/{api,ios}/uat_results.json, folds them into
# .deliveryos/uat_ledger.json (what scripts/uat/uat_gate.py reads), and renders
# qa/uat/_runs/<ts>/report.md. Exit 0 only if every layer that ran is green.
#
# Android runs on the melehost rig (Galaxy A17) via scripts/uat/android_rig.sh:
# fresh APK, additive harness sync, the rig's own flock, results copied back.

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UAT="${PROJECT_ROOT}/qa/uat"
HARNESS="${PROJECT_ROOT}/qa/appium"
PY="${PROJECT_ROOT}/backend/.venv/bin/python"
HPY="${HARNESS}/.venv/bin/python"

DO_API=0; DEVICE=""; CHANGED=0; NO_LLM=0; BUILD=1
while (( $# )); do
  case "$1" in
    --api) DO_API=1 ;;
    --device) shift; DEVICE="${1:-}" ;;
    --all) DO_API=1; DEVICE="ios" ;;
    --changed-only) CHANGED=1 ;;
    --no-llm) NO_LLM=1 ;;
    --no-build) BUILD=0 ;;
    -h|--help) sed -n '2,/^set -uo/p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
if (( ! DO_API )) && [[ -z "$DEVICE" ]]; then
  echo "nothing to run — pass --api, --device ios|android, or --all" >&2; exit 2
fi
if [[ -n "$DEVICE" && "$DEVICE" != "ios" && "$DEVICE" != "android" ]]; then
  echo "--device must be ios or android" >&2; exit 2
fi

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${UAT}/_runs/${RUN_ID}"
mkdir -p "$RUN_DIR"
echo "▶ UAT run ${RUN_ID} → ${RUN_DIR}"
OVERALL=0

ids_arg() {  # $1 = target; prints the pytest arg (or "SKIP" when nothing is pending)
  local f="${RUN_DIR}/$1_pending.txt"
  "$PY" "${UAT}/ledger.py" pending --target "$1" > "$f" || return 1
  if [[ ! -s "$f" ]]; then echo "SKIP"; else echo "--uat-ids=@${f}"; fi
}

if (( DO_API )); then
  echo "── api (live Alpha)"
  ARGS=(-q -p no:cacheprovider)
  (( NO_LLM )) && ARGS+=(--no-llm)
  if (( CHANGED )); then
    SEL="$(ids_arg api)" || { echo "ledger failed"; exit 2; }
    [[ "$SEL" == "SKIP" ]] && echo "   nothing pending" || ARGS+=("$SEL")
  fi
  if [[ "${SEL:-}" != "SKIP" ]]; then
    ( cd "$UAT" && UAT_RUN_ID="$RUN_ID" UAT_LAYER=api UAT_PLATFORM=api \
        UAT_RESULTS_JSON="${RUN_DIR}/api/uat_results.json" \
        "$PY" -m pytest api "${ARGS[@]}" --junitxml="${RUN_DIR}/api/junit.xml" )
    rc=$?
    echo "   api exit ${rc}"
    (( rc != 0 )) && OVERALL=1
    [[ -f "${RUN_DIR}/api/uat_results.json" ]] && "$PY" "${UAT}/ledger.py" record "${RUN_DIR}/api/uat_results.json"
  fi
fi
SEL=""

if [[ "$DEVICE" == "android" ]]; then
  echo "── android (melehost rig, Galaxy A17)"
  RARGS=()
  (( BUILD )) || RARGS+=(--no-build)
  if (( CHANGED )); then
    SEL="$(ids_arg android)" || { echo "ledger failed"; exit 2; }
    [[ "$SEL" != "SKIP" ]] && RARGS+=(--uat-ids-file "${RUN_DIR}/android_pending.txt")
  fi
  if [[ "$SEL" == "SKIP" ]]; then
    echo "   nothing pending"
  else
    "${PROJECT_ROOT}/scripts/uat/android_rig.sh" "$RUN_DIR" "${RARGS[@]}"
    rc=$?
    echo "   android exit ${rc}"
    (( rc != 0 && rc != 5 )) && OVERALL=1
    [[ -f "${RUN_DIR}/android/uat_results.json" ]] && "$PY" "${UAT}/ledger.py" record "${RUN_DIR}/android/uat_results.json"
  fi
  SEL=""
fi

if [[ "$DEVICE" == "ios" ]]; then
  echo "── ios (Simulator)"
  if [[ ! -x "$HPY" ]]; then
    echo "   harness venv missing: cd qa/appium && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    OVERALL=1
  else
    if (( CHANGED )); then
      SEL="$(ids_arg ios)" || { echo "ledger failed"; exit 2; }
    fi
    if [[ "$SEL" == "SKIP" ]]; then
      echo "   nothing pending"
    else
      if (( BUILD )); then
        "${PROJECT_ROOT}/scripts/build_qa_ios_sim.sh" > "${RUN_DIR}/ios_build.log" 2>&1
        brc=$?
        if (( brc != 0 )); then
          echo "   QA sim build failed (exit ${brc}) — see ${RUN_DIR}/ios_build.log" >&2
          OVERALL=1; DEVICE=""
        fi
      fi
    fi
    if [[ "$DEVICE" == "ios" && "$SEL" != "SKIP" ]]; then
      APPIUM_PID=""
      if ! nc -z 127.0.0.1 4723 2>/dev/null; then
        appium --address 127.0.0.1 --port 4723 > "${RUN_DIR}/appium.log" 2>&1 &
        APPIUM_PID=$!
        for _ in $(seq 1 30); do nc -z 127.0.0.1 4723 2>/dev/null && break; sleep 1; done
      fi
      export AMI_PLATFORM=ios AMI_REPORT_DIR="${RUN_DIR}/ios" UAT_RUN_ID="$RUN_ID" \
             UAT_LAYER=device UAT_PLATFORM=ios PYTHONPATH="${UAT}${PYTHONPATH:+:$PYTHONPATH}"
      ( cd "$HARNESS" && "$HPY" -m pytest -m smoke -q -p uat_plugin )
      rc=$?
      if (( rc != 0 )); then
        echo "   ios smoke gate failed (exit ${rc}) — skipping the rest of the device run" >&2
        OVERALL=1
      else
        DARGS=(-q -p uat_plugin -m "not smoke")
        [[ -n "$SEL" ]] && DARGS+=("$SEL")
        ( cd "$HARNESS" && UAT_RESULTS_JSON="${RUN_DIR}/ios/uat_results.json" \
            "$HPY" -m pytest "${DARGS[@]}" --junitxml="${RUN_DIR}/ios/junit.xml" )
        rc=$?
        echo "   ios exit ${rc}"
        (( rc != 0 && rc != 5 )) && OVERALL=1
        [[ -f "${RUN_DIR}/ios/uat_results.json" ]] && "$PY" "${UAT}/ledger.py" record "${RUN_DIR}/ios/uat_results.json"
      fi
      [[ -n "$APPIUM_PID" ]] && kill "$APPIUM_PID" 2>/dev/null
    fi
  fi
fi

"$PY" "${UAT}/report.py" "$RUN_DIR" && echo "   report: ${RUN_DIR}/report.md"
if (( OVERALL == 0 )); then echo "VERDICT: PASS"; else echo "VERDICT: FAIL"; fi
exit "$OVERALL"
