#!/usr/bin/env bash
# CR214 sharded sweep supervisor. One shard = one batch-id + one disjoint
# pairs file, so every writer has a disjoint path (runs_<batch>.jsonl and
# complete_<batch>.json are per-shard) and no two shards can race a file.
#
# DEF387: a bare 'nohup docker compose exec' dies with its ssh channel. This
# script must be started under setsid, and it relaunches the resumable sweep
# across any exec death. Exit 3 (DEF336 outage abort) is NOT retried.
set -u
SHARD=$1
cd ~/ami_trade || exit 1
BATCH=r74c-out-s${SHARD}
LOG=/tmp/cr214c_shard${SHARD}.log
for attempt in $(seq 1 200); do
  for _ in $(seq 1 90); do
    st=$(docker inspect -f '{{.State.Health.Status}}' ami_api_alpha 2>/dev/null || echo none)
    [ "$st" = healthy ] && break
    sleep 20
  done
  echo "=== SHARD $SHARD attempt $attempt start $(date -u +%FT%TZ) ===" >> "$LOG"
  docker compose exec -e AMI_SWEEP_SUPERVISOR=1 -T api-alpha python scripts/backtest_sweep.py     --batch-id "$BATCH" --window-start 2025-08-01 --window-end 2026-07-27     --n-pairs 700 --seed 214     --pairs-file /backtest_results/pairs_cr214_s${SHARD}.jsonl     --universe-file /backtest_results/_tickers_142.txt     --out-dir /backtest_results >> "$LOG" 2>&1
  rc=$?
  echo "=== SHARD $SHARD attempt $attempt exit rc=$rc $(date -u +%FT%TZ) ===" >> "$LOG"
  case "$rc" in
    0) echo "=== SHARD $SHARD COMPLETE ===" >> "$LOG"; exit 0 ;;
    3) echo "=== SHARD $SHARD DEF336 outage abort — NOT retrying ===" >> "$LOG"; exit 3 ;;
  esac
  sleep 60
done
exit 1
