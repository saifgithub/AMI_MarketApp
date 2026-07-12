#!/usr/bin/env bash
# General-capability regression battery — catastrophic-forgetting gate.
#
# Runs MMLU, IFEval, GSM8K, HellaSwag against either:
#   - the base model (run once for the reference baseline), or
#   - the base model + a candidate LoRA adapter (run for every LoRA).
#
# Gate: no benchmark drops more than 3 percentage points vs. base.
#
# Usage:
#   ./run_capability_battery.sh base                               # baseline run
#   ./run_capability_battery.sh lora concierge                     # candidate run
#   ./run_capability_battery.sh diff base.json concierge.json      # gate check
#
# Results land in /raid/silent_scout/eval/general/<tag>/

set -euo pipefail

BASE_MODEL="${BASE_MODEL:-/raid/silent_scout/models/Qwen3.6-35B-A3B}"
RESULTS_DIR="${RESULTS_DIR:-/raid/silent_scout/eval/general}"
ADAPTERS_DIR="${ADAPTERS_DIR:-/raid/silent_scout/adapters}"
GATE_PP="${GATE_PP:-3.0}"

TASKS="mmlu,ifeval,gsm8k,hellaswag"

mode="${1:-help}"

run_lm_eval() {
  local tag="$1"
  local model_args="$2"
  mkdir -p "${RESULTS_DIR}/${tag}"
  lm_eval \
    --model hf \
    --model_args "${model_args}" \
    --tasks "${TASKS}" \
    --batch_size auto \
    --output_path "${RESULTS_DIR}/${tag}/" \
    --log_samples
}

case "${mode}" in
  base)
    run_lm_eval "base" "pretrained=${BASE_MODEL},dtype=bfloat16,trust_remote_code=True"
    ;;
  lora)
    role="${2:?lora <role>}"
    adapter="${ADAPTERS_DIR}/${role}"
    [[ -d "${adapter}" ]] || { echo "adapter not found: ${adapter}"; exit 2; }
    run_lm_eval "${role}" "pretrained=${BASE_MODEL},peft=${adapter},dtype=bfloat16,trust_remote_code=True"
    ;;
  diff)
    base_json="${2:?diff <base_results.json> <candidate_results.json>}"
    cand_json="${3:?diff <base_results.json> <candidate_results.json>}"
    python "$(dirname "$0")/diff_capability.py" "${base_json}" "${cand_json}" --gate-pp "${GATE_PP}"
    ;;
  *)
    echo "usage: $0 {base | lora <role> | diff <base.json> <cand.json>}"
    exit 1
    ;;
esac
