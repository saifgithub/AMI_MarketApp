#!/usr/bin/env bash
# CR164 Phase B supervisor.
#
# The sweep runs via `docker compose exec`, so it dies the moment another lane
# recreates ami_api_alpha — silently, mid-batch, looking exactly like a sweep
# that is still running. That is how r70-outcome-2 lost 2.5 h after 17 runs.
# The sweep is resumable (completed pairs are skipped from the JSONL), so the
# right response is to relaunch it, not to lose the night.
#
# Staging lives on /backtest_results, not /tmp: a recreate wipes /tmp.
# Exit 3 (DEF336 outage abort) is NOT retried — a dead provider is not a
# transient, and retrying it manufactures exactly the dataset DEF336 refuses.
set -u
cd ~/ami_trade || exit 1
LOG=/tmp/cr214_flipbase2.log
BATCH=r74-flipbase2-cr214

for attempt in $(seq 1 200); do
  for _ in $(seq 1 90); do
    st=$(docker inspect -f '{{.State.Health.Status}}' ami_api_alpha 2>/dev/null || echo none)
    [ "$st" = healthy ] && break
    sleep 20
  done
  echo "=== SUPERVISOR attempt $attempt start $(date -u +%FT%TZ) ===" >> "$LOG"
  docker compose exec -e AMI_SWEEP_SUPERVISOR=1 -T api-alpha python scripts/backtest_sweep.py     --batch-id "$BATCH" --window-start 2025-08-01 --n-pairs 26 --repeat-pairs 26 --seed 214          --universe-file /backtest_results/_tickers_142.txt     --out-dir /backtest_results >> "$LOG" 2>&1
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
