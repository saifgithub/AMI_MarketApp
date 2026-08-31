#!/usr/bin/env bash
# CR214 — run the eight shard supervisors ONE AT A TIME.
#
# Saiful, 2026-08-31, after the 8-way parallel fleet saturated the vLLM host:
# "restart the backtesting but only send 1 at a time." The shard split stays —
# it is the coverage design (each shard is a stride-8 sample of the 52 Fridays,
# so a completed shard is 6-7 dates spread evenly across the whole window, not a
# contiguous block) — what changes is that exactly one supervisor is alive at any
# moment. backtest_sweep.py is itself strictly serial, so one supervisor is one
# convene in flight.
#
# DEF387: start this under setsid. A bare backgrounded ssh command dies with the
# channel, which is how three hours were lost earlier today.
set -u
LOG=/tmp/cr214_sequential.log
cd ~/ami_trade || exit 1
echo "=== SEQUENTIAL DRIVER start $(date -u +%FT%TZ) pid=$$ ===" >> "$LOG"
for i in $(seq "${1:-1}" 8); do
  echo "--- shard $i begin $(date -u +%FT%TZ) ---" >> "$LOG"
  bash backtest_results/_supervise_shard.sh "$i"
  rc=$?
  echo "--- shard $i end rc=$rc $(date -u +%FT%TZ) ---" >> "$LOG"
  if [ "$rc" -ne 0 ]; then
    echo "=== HALT at shard $i (rc=$rc) — not advancing $(date -u +%FT%TZ) ===" >> "$LOG"
    exit "$rc"
  fi
done
echo "=== SEQUENTIAL DRIVER all shards complete $(date -u +%FT%TZ) ===" >> "$LOG"
