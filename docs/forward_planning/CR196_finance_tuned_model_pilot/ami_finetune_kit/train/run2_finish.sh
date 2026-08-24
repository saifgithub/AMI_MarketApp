#!/usr/bin/env bash
# ==========================================
# CR196 run 2 — unattended finish: wait for training, merge, evaluate, score.
#
# Runs on alpha-spark OUTSIDE docker (it drives docker), so it must be started with
# setsid+nohup or it dies with the ssh session:
#   setsid nohup ~/amitrade_tuning/kit/ami_finetune_kit/train/run2_finish.sh \
#       > ~/amitrade_tuning/runs/finish.log 2>&1 < /dev/null &
#
# The GPU does one thing at a time, so every stage is sequential by necessity. Each
# stage is idempotent and skipped if its output already exists — a re-run after any
# failure resumes rather than repeating GPU hours.
#
# Stages:
#   0. wait for ami_train_r2 to exit, verify it succeeded
#   1. merge LoRA -> /models/ami-finance-r2-bf16 (CPU-only, shard-wise)
#   2. vanilla baseline for S4/S7/S8 ONLY (the three surfaces the decontamination fix
#      rebuilt; the other five are byte-identical to baseline_vanilla.json's prompts)
#   3. tuned model over all 468 prompts
#   4. score both arms
# ==========================================
set -uo pipefail

BASE=/home/amuneeb/amitrade_tuning
KIT=$BASE/kit/ami_finetune_kit
RUNS=$BASE/runs
OUT=$RUNS/ami-lora-r2b
IMG=ami-train:v1
MERGED=/models/ami-finance-r2-bf16

log() { echo "[finish $(date -u +%H:%M:%S)] $*"; }

dock() {  # dock <name> <extra-args...> -- runs IMG with the standard eval mounts
  local name=$1; shift
  docker run --rm --gpus all --name "$name" \
    -v "$BASE/kit:/kit_outer" \
    -v "$KIT:/kit" \
    -v "$BASE/models:/models" \
    -v "$RUNS:/runs" \
    "$IMG" "$@"
}

# ── 0. wait for training ────────────────────────────────────────────────────
log "waiting for ami_train_r2 to finish..."
while [ "$(docker inspect ami_train_r2 --format '{{.State.Status}}' 2>/dev/null)" = "running" ]; do
  step=$(docker logs ami_train_r2 2>&1 | tr '\r' '\n' | grep -oE '[0-9]+/2504' | tail -1)
  log "  still training: ${step:-?}"
  sleep 600
done

EXIT=$(docker inspect ami_train_r2 --format '{{.State.ExitCode}}' 2>/dev/null || echo missing)
OOM=$(docker inspect ami_train_r2 --format '{{.State.OOMKilled}}' 2>/dev/null || echo '?')
log "training container exited: code=$EXIT oomkilled=$OOM"

# Prefer the completed adapter; fall back to the newest checkpoint so an OOM at
# step 2000/2504 still yields something evaluable. Which one was used is LOUD —
# a checkpoint is mid-cosine-anneal and is NOT equivalent to a finished short run.
ADAPTER=""
if [ -d "$OUT/adapter_final" ]; then
  ADAPTER=$OUT/adapter_final
  log "using adapter_final (training completed)"
else
  CKPT=$(ls -d "$OUT"/checkpoint-* 2>/dev/null | sort -t- -k2 -n | tail -1)
  if [ -n "$CKPT" ]; then
    ADAPTER=$CKPT
    log "!! adapter_final MISSING — falling back to $CKPT (mid-anneal, treat as provisional)"
  else
    log "FATAL: no adapter and no checkpoint in $OUT — nothing to evaluate"; exit 1
  fi
fi

# ── 1. merge ────────────────────────────────────────────────────────────────
if [ -f "$BASE/models/ami-finance-r2-bf16/config.json" ]; then
  log "merge already done, skipping"
else
  log "merging LoRA -> $MERGED (CPU, shard-wise)"
  dock ami_merge_r2 python3 -u /kit/train/merge_lora_to_disk.py \
    --base /models/fastino-finance-bf16 \
    --adapter "${ADAPTER/$BASE/}" \
    --out "$MERGED" || { log "FATAL: merge failed"; exit 1; }
fi

# ── 2. vanilla baseline, S4/S7/S8 only ──────────────────────────────────────
BASE_OUT=$RUNS/baseline_s478.jsonl
if [ -s "$BASE_OUT" ] && [ "$(wc -l < "$BASE_OUT")" -ge 180 ]; then
  log "vanilla S4/S7/S8 baseline already complete, skipping"
else
  log "generating vanilla baseline for S4/S7/S8 (180 prompts, ~1.5h)"
  dock ami_base_s478 python3 -u /kit/eval/surfaces/run_local_surfaces.py \
    --model /models/fastino-finance-bf16 \
    --prompts /kit/eval/surfaces/surface_prompts.jsonl \
    --surfaces S4,S7,S8 --resume \
    --out /runs/baseline_s478.jsonl --label vanilla-s478 \
    || log "WARN: vanilla arm returned nonzero (partial output kept, --resume will continue)"
fi

# ── 3. tuned model, all surfaces ────────────────────────────────────────────
R2_OUT=$RUNS/r2_completions.jsonl
if [ -s "$R2_OUT" ] && [ "$(wc -l < "$R2_OUT")" -ge 468 ]; then
  log "tuned completions already complete, skipping"
else
  log "generating tuned completions over all 468 prompts (~3.5h)"
  dock ami_eval_r2 python3 -u /kit/eval/surfaces/run_local_surfaces.py \
    --model "$MERGED" \
    --prompts /kit/eval/surfaces/surface_prompts.jsonl --resume \
    --out /runs/r2_completions.jsonl --label ours-r2 \
    || log "WARN: tuned arm returned nonzero (partial output kept, --resume will continue)"
fi

# ── 4. score ────────────────────────────────────────────────────────────────
# eval_surfaces.py resolves datagen/ as a sibling of ami_finetune_kit, so the SCORING
# container mounts the OUTER kit dir at /kit. Training mounts ami_finetune_kit itself.
# Crossing these two conventions is what broke both earlier launches.
score() {
  local completions=$1 out=$2 label=$3
  log "scoring $label"
  docker run --rm -v "$BASE/kit:/kit" -v "$RUNS:/runs" "$IMG" bash -lc "
      pip install --quiet yfinance 2>/dev/null;
      python3 -u /kit/ami_finetune_kit/eval/surfaces/eval_surfaces.py --stage score \
        --prompts /kit/ami_finetune_kit/eval/surfaces/surface_prompts.jsonl \
        --completions $completions --json-out $out --label $label"
}
score /runs/baseline_s478.jsonl   /runs/baseline_s478_scored.json   vanilla-s478
score /runs/r2_completions.jsonl  /runs/r2_scored.json              ours-r2

log "DONE — results:"
log "  $RUNS/r2_scored.json"
log "  $RUNS/baseline_s478_scored.json"
