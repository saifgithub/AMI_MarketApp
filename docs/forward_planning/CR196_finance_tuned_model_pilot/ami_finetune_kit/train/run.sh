#!/usr/bin/env bash
# run.sh — CR196 real training run. Only after smoke_test.sh printed VERDICT: PASS.
# Survives SSH disconnects (nohup); tail the log to watch. Re-run with RESUME=1 after a crash.
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-/runs/ami-lora-r1}"
mkdir -p "$OUT"
FLAGS=""
[ "${RESUME:-0}" = "1" ] && FLAGS="--resume"
nohup python3 "$KIT/train/train_lora.py" --config "$KIT/train/config.yaml" --out "$OUT" $FLAGS \
  >> "$OUT/train.log" 2>&1 &
echo "PID $! — tail -f $OUT/train.log"
