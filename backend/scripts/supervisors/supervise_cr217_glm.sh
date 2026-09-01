#!/usr/bin/env bash
# CR217 — GLM decision-diff arm: 54 pairs replayed from the banked ami-llm batch.
#
# Same supervisor shape as `supervise_cr214.sh` (the sweep dies silently when
# another lane recreates ami_api_alpha, and it is resumable, so relaunching is
# the right response) with one addition that matters more than the retry loop:
#
#   **The provider is re-verified before EVERY attempt.**
#
# The sweep talks to the sidecar on :8001. If that process is gone — a container
# recreate wipes it, since it is not a compose service — then :8001 refuses the
# connection and the batch merely fails, which is survivable. The unsurvivable
# case is subtler: point this at :8000 by accident, or start the sidecar without
# GLM_BASE_URL, and `_active_provider_name` silently falls through to the
# INCUMBENT. The sweep completes, the report renders, and every number in it is
# ami-llm scored against itself. There is no downstream check that would catch
# it, so the check goes here, before each attempt, and a mismatch aborts rather
# than runs.
#
# `--window-start 2025-08-01` is GLM's window, NOT the baseline's 2025-02-28, and
# the difference is the whole reason the cutoff probe was run first. Measured
# 2026-09-01: GLM's price knowledge collapses at 2025-05 and it still recalls
# events into 2025-06, so collapse + 8 weeks puts its first honest as-of date at
# 2025-08-01. Five of the banked baseline's eighteen dates (2025-02-28, 04-11,
# 05-09, 06-13, 07-11) fall INSIDE that memory — on those, GLM would be recalling
# the outcome rather than forecasting it, and its "judgement" would beat the
# incumbent's for a reason that has nothing to do with judgement.
#
# The pairs file is already restricted to the 13 shared dates. This flag is the
# structural backstop: `backtest_sweep.py` refuses any as_of before window-start
# outright, so a regenerated or hand-edited pairs file cannot quietly reintroduce
# a contaminated date.
#
# Exit 3 (DEF336 outage abort) is never retried — a dead provider is not a
# transient, and retrying it manufactures exactly the dataset DEF336 refuses.
# Exit 4 is this script's own: the provider was not what the benchmark requires.
set -u
cd ~/ami_trade || exit 1

LOG=/tmp/cr217_glm.log
BATCH=cr217-glm-1
PORT=8001
PAIRS=/backtest_results/pairs_cr217_glm_smoke.jsonl

for attempt in $(seq 1 200); do
  for _ in $(seq 1 90); do
    st=$(docker inspect -f '{{.State.Health.Status}}' ami_api_alpha 2>/dev/null || echo none)
    [ "$st" = healthy ] && break
    sleep 20
  done

  # Bring the sidecar back if a recreate took it, then prove which model answers.
  if ! bash backend/scripts/supervisors/glm_sidecar.sh check >> "$LOG" 2>&1; then
    echo "=== SUPERVISOR attempt $attempt: sidecar not serving glm — restarting ===" >> "$LOG"
    bash backend/scripts/supervisors/glm_sidecar.sh start >> "$LOG" 2>&1
    if ! bash backend/scripts/supervisors/glm_sidecar.sh check >> "$LOG" 2>&1; then
      echo '=== SUPERVISOR: ABORT — cannot confirm glm is serving :8001.' >> "$LOG"
      echo '    Running now would score the INCUMBENT against itself.' >> "$LOG"
      exit 4
    fi
  fi

  echo "=== SUPERVISOR attempt $attempt start $(date -u +%FT%TZ) ===" >> "$LOG"
  docker compose exec -e AMI_SWEEP_SUPERVISOR=1 -T api-alpha \
    python scripts/backtest_sweep.py \
      --batch-id "$BATCH" \
      --base-url "http://127.0.0.1:$PORT" \
      --pairs-file "$PAIRS" \
      --window-start 2025-08-01 \
      --n-pairs 52 \
      --seed 217 \
      --universe-file /backtest_results/_tickers_142.txt \
      --out-dir /backtest_results >> "$LOG" 2>&1
  rc=$?
  echo "=== SUPERVISOR attempt $attempt exit rc=$rc $(date -u +%FT%TZ) ===" >> "$LOG"
  case "$rc" in
    0) echo '=== SUPERVISOR: sweep COMPLETE ===' >> "$LOG"; exit 0 ;;
    3) echo '=== SUPERVISOR: DEF336 outage abort — NOT retrying ===' >> "$LOG"; exit 3 ;;
  esac
  sleep 60
done
echo '=== SUPERVISOR: attempt cap reached ===' >> "$LOG"
exit 1
