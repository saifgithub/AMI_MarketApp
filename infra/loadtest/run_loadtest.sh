#!/usr/bin/env bash
# CR246 — run the multi-user concurrency harness against the ami-loadtest
# stack on minihost. k6 runs dockerized ON minihost (nothing to install on
# the Mac, and timings aren't polluted by LAN latency).
#
# Usage (from the repo root on the Mac):
#   infra/loadtest/run_loadtest.sh
#   VUS=10 DURATION=20m infra/loadtest/run_loadtest.sh
#
# Results land in backtest_results/loadtest/<timestamp>/ on the Mac.
# k6's exit code is reported but does NOT abort the script — the post-run
# audits (backend/scripts/loadtest_audit.sh) must still run.

set -uo pipefail

HOST="${LOADTEST_HOST:-minihost}"
VUS="${VUS:-10}"
DURATION="${DURATION:-20m}"
TS="$(date +%Y%m%dT%H%M%S)"
REMOTE_RESULTS="~/ami_loadtest/results/${TS}"
LOCAL_RESULTS="backtest_results/loadtest/${TS}"

echo "== load test: ${VUS} users, ${DURATION}, target http://api:8000 (minihost)"
ssh "${HOST}" "mkdir -p ${REMOTE_RESULTS} && chmod 777 ${REMOTE_RESULTS}"

ssh "${HOST}" "
  docker run --rm -i \
    --network ami_loadtest_internal \
    -v ~/ami_loadtest/backend/scripts:/scripts:ro \
    -v ${REMOTE_RESULTS}:/results \
    grafana/k6 run \
      -e BASE_URL=http://api:8000 \
      -e VUS=${VUS} \
      -e DURATION=${DURATION} \
      -e SUMMARY_OUT=/results/summary.json \
      /scripts/load_test_mix.js
"
K6_EXIT=$?

mkdir -p "${LOCAL_RESULTS}"
scp -q "${HOST}:${REMOTE_RESULTS}/summary.json" "${LOCAL_RESULTS}/" 2>/dev/null || true

echo
if [ "${K6_EXIT}" -eq 0 ]; then
  echo "K6 THRESHOLDS: PASS"
else
  echo "K6 THRESHOLDS: FAIL (exit ${K6_EXIT}) — see summary.json"
fi
echo "Results: ${LOCAL_RESULTS}/summary.json"
echo "Next: backend/scripts/loadtest_audit.sh"
