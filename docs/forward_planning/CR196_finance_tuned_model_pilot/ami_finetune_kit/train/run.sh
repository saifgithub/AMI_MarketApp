#!/usr/bin/env bash
# run.sh — CR196 real training run. Only after smoke_test.sh printed VERDICT: PASS.
# Survives SSH disconnects (nohup); tail the log to watch. Re-run with RESUME=1 after a crash.
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-/runs/ami-lora-r1}"
mkdir -p "$OUT"
FLAGS=""
[ "${RESUME:-0}" = "1" ] && FLAGS="--resume"
# -u is not optional. Without it python buffers stdout when it is a file rather than
# a TTY, so a container run emits NOTHING — no step counter, no loss line — while the
# GPU sits at 90%+. Measured on the run-2 probe: 14 minutes in, the log was still
# byte-identical to startup. On a 25-hour run that is the difference between watching
# it and guessing.
nohup python3 -u "$KIT/train/train_lora.py" --config "$KIT/train/config.yaml" --out "$OUT" $FLAGS \
  >> "$OUT/train.log" 2>&1 &
echo "PID $! — tail -f $OUT/train.log"
