#!/usr/bin/env bash
# smoke_test.sh — CR196 kit go/no-go gate. Run this BEFORE the real training run and
# send smoke_report.md back. It answers, on THIS box: does the harness load the model,
# train 10 steps, save, merge, reload, and generate — and what do memory + step-time
# actually measure?  Exit 0 = PASS (proceed to run.sh), anything else = STOP and report.
set -uo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-/runs/smoke}"
REPORT="$OUT/smoke_report.md"
mkdir -p "$OUT"

{
  echo "# CR196 smoke report"
  echo "- date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "- host: $(hostname) / $(uname -m)"
  echo "- gpu: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo unknown)"
  echo "- mem_before: $(free -h | awk '/^Mem:/{print $3" used / "$2" total, "$7" available"}')"
} > "$REPORT"

echo "=== [1/4] weight verification ==="
python3 "$KIT/model/download_base.py" --dest "${MODEL_DIR:-/models/fastino-finance-bf16}" --skip-download \
  | tee -a "$OUT/verify.log"
VERIFY=$?
echo "- weight_verify: $([ $VERIFY -eq 0 ] && echo PASS || echo FAIL)" >> "$REPORT"
[ $VERIFY -ne 0 ] && { echo "VERDICT: FAIL (weights)"; exit 1; }

echo "=== [2/4] 10-step smoke train ==="
START=$(date +%s)
python3 "$KIT/train/train_lora.py" --config "$KIT/train/config.yaml" --out "$OUT" --smoke \
  2>&1 | tee "$OUT/smoke_train.log"
TRAIN=${PIPESTATUS[0]}
ELAPSED=$(( $(date +%s) - START ))
{
  echo "- smoke_train: $([ $TRAIN -eq 0 ] && echo PASS || echo FAIL) (${ELAPSED}s wall)"
  echo "- harness: $(python3 -c "import json;print(json.load(open('$OUT/run_report.json'))['harness'])" 2>/dev/null || echo unknown)"
  echo "- mem_peak_after: $(free -h | awk '/^Mem:/{print $3" used, "$7" available"}')"
  echo "- trainable_params: $(grep -m1 -i 'trainable' "$OUT/smoke_train.log" || echo 'not printed')"
} >> "$REPORT"
[ $TRAIN -ne 0 ] && { echo "VERDICT: FAIL (train)"; exit 1; }

echo "=== [3/4] merge + reload + generate ==="
python3 "$KIT/train/merge_and_generate.py" --model "${MODEL_DIR:-/models/fastino-finance-bf16}" \
  --adapter "$OUT/adapter_final" --out "$OUT" 2>&1 | tee "$OUT/merge.log"
MERGE=${PIPESTATUS[0]}
echo "- merge_reload_generate: $([ $MERGE -eq 0 ] && echo PASS || echo FAIL)" >> "$REPORT"
[ $MERGE -ne 0 ] && { echo "VERDICT: FAIL (merge)"; exit 1; }

echo "=== [4/4] freeze environment ==="
pip freeze > "$OUT/frozen_env.txt"
echo "- frozen_env: $OUT/frozen_env.txt ($(wc -l < "$OUT/frozen_env.txt") packages)" >> "$REPORT"

echo "VERDICT: PASS" | tee -a "$REPORT"
echo "Send back: $REPORT, $OUT/frozen_env.txt, $OUT/smoke_train.log"
