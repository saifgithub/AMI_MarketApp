#!/usr/bin/env bash
# CR217 — start/stop/check a GLM-forced API process INSIDE ami_api_alpha.
#
# Why a second process rather than flipping LLM_FORCE_PROVIDER on the container:
# `settings` is instantiated per process from env, and `backtest_sweep.py` reaches
# the Room over HTTP rather than in-process, so the SERVER's env decides which
# provider answers. Flipping it on `ami_api_alpha` would serve an untested
# candidate model to live Alpha users for the length of the run, and would land
# GLM-authored convenes in the same `room_runs` table the live retro panel scores.
# A second uvicorn on :8001 with its own env keeps :8000 on the incumbent and
# gives the benchmark a clean, fully isolated arm against the same database.
#
# Why a second CONTAINER was rejected: `api-alpha`'s environment block is ~380
# lines, so a cloned compose service drifts from it the first time anyone edits
# one and not the other — and a benchmark arm that silently differs from
# production in one env var is worse than no benchmark.
#
# This script is version-controlled for the same reason the sweep supervisors are
# (DEF387): `backtest_results/` is rsync-excluded, so anything kept there is one
# disk away from gone and invisible to review.
set -euo pipefail

CONTAINER="${CONTAINER:-ami_api_alpha}"
PORT="${GLM_SIDECAR_PORT:-8001}"

# Matched to the BASELINE, not to production. The banked ami-llm batch
# (`r70-outcome-2`, 2026-08-20/21) ran before CR214 raised
# `pm_self_consistency_samples` to 5 — its report's rank-IC section reads
# "SKIPPED — no run in this batch carries approve_votes". Alpha runs 5 today.
# Five independent CIO draws with a majority vote cut the verdict flip rate from
# ~19.7% to ~6.6% (`risk_officer.py`), so running the candidate at 5 against a
# baseline at 1 would hand GLM a noise reduction that is a property of the
# VOTING, not of the model, and it would show up as apparent edge. Override only
# to deliberately measure the voting effect, never for the head-to-head.
SAMPLES="${PM_SELF_CONSISTENCY_SAMPLES:-1}"

usage() { echo "usage: $0 {start|stop|status|check}" >&2; exit 64; }
[ $# -ge 1 ] || usage

case "$1" in
  start)
    docker exec -d \
      -e LLM_FORCE_PROVIDER=glm \
      -e PM_SELF_CONSISTENCY_SAMPLES="$SAMPLES" \
      "$CONTAINER" \
      uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level warning
    echo "started (provider=glm, pm_samples=$SAMPLES); waiting for health…"
    for _ in $(seq 1 30); do
      if docker exec "$CONTAINER" curl -sf "http://127.0.0.1:$PORT/v1/health" >/dev/null 2>&1; then
        echo "healthy on :$PORT"
        exec "$0" check
      fi
      sleep 2
    done
    echo "FAILED: sidecar never became healthy on :$PORT" >&2
    exit 1
    ;;
  stop)
    # Match on the port so the live :8000 uvicorn is never a candidate.
    docker exec "$CONTAINER" pkill -f "uvicorn app.main:app.*--port $PORT" || true
    echo "stopped (port $PORT)"
    ;;
  status)
    docker exec "$CONTAINER" sh -c "ps aux | grep -c '[u]vicorn.*--port $PORT'" || true
    ;;
  check)
    # The whole point of the sidecar. If this does not say glm, every number the
    # run produces is the INCUMBENT scored against itself — `_active_provider_name`
    # falls through silently when a forced provider is unregistered.
    echo "--- :$PORT (benchmark arm) must be glm ---"
    docker exec "$CONTAINER" curl -s "http://127.0.0.1:$PORT/v1/llm/status"
    echo
    echo "--- :8000 (live Alpha) must be UNCHANGED ---"
    docker exec "$CONTAINER" curl -s "http://127.0.0.1:8000/v1/llm/status"
    echo
    ;;
  *) usage ;;
esac
