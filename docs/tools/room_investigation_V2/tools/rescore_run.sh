#!/usr/bin/env bash
# rescore_run.sh — copy of wp10_run.sh for the 2026-11-19 Ling-3.0-flash re-score; only key loading differs.
# wp10_run.sh — one CR240 / CR267 WP-10 benchmark job, run ON melehost.
#
# Runs a benchmark YAML through the research harness inside a throwaway
# `docker compose run` container (the promoted api-alpha image, repo mounted
# read-only at /harness) with production Room settings: prompts backend-default,
# veto + resurrection reviews ON, no failover slot, no spend ceiling. Writes ONLY
# under ~/cr267_wp10/ — never into ~/ami_trade, never touches the live
# ami_api_alpha container. The DeepInfra key arrives in the caller's environment as
# DEEPINFRA_API_KEY (piped over ssh stdin, never on a command line or on disk) and is never echoed.
#
# usage: wp10_run.sh LABEL PROVIDER MODEL BENCH OUTSUB CONC TEMP EXTRA_BODY_JSON
#   TEMP           desk temperature; empty = omit LLM_DESK_TEMPERATURE (server default)
#   EXTRA_BODY_JSON  deepinfra only: DEEPINFRA_EXTRA_BODY_JSON (thinking-off body); "" = none
#   EXTRA_DOCKER_ARGS (env) extra `-e K=V` args, e.g. the Ling vLLM endpoint.
set -uo pipefail
LABEL=$1; PROVIDER=$2; MODEL=$3; BENCH=$4; OUTSUB=$5; CONC=$6; TEMP=${7:-}; EXTRA=${8:-}
W=$HOME/cr267_wp10
cd ~/ami_trade
PGPW=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
[ -n "$PGPW" ] || { echo "POSTGRES_PASSWORD missing"; exit 1; }
if [ "$PROVIDER" = deepinfra ]; then
  [ -n "${DEEPINFRA_API_KEY:-}" ] || { echo "DEEPINFRA_API_KEY missing from the calling environment"; exit 1; }
  export DEEPINFR_API_KEY="$DEEPINFRA_API_KEY"
fi
PRICES='{"Qwen/Qwen3.8-Flash":{"in":0.113,"out":0.382},"deepseek-ai/DeepSeek-V4-Flash":{"in":0.09,"out":0.18},"zai-org/GLM-5.3-Flash":{"in":0.15,"out":0.50},"inclusionAI/Ling-3.0-flash":{"in":0.06,"out":0.18},"ling-3.0-flash-fin-fp4":{"in":0,"out":0},"/models/Ling-3.0-flash-Fin-fp4":{"in":0,"out":0},"ami-llm":{"in":0,"out":0},"/models/qwen38-flash-next-abliterated-nvfp4":{"in":0,"out":0}}'
mkdir -p "$W/out/$LABEL/$OUTSUB" "$W/logs"
chmod -R a+rwx "$W/out"
ARGS=(compose run --rm --no-deps --entrypoint python
  -v "$HOME/ami_trade:/harness:ro"
  -v "$W/overlay/provider_gateway.py:/harness/docs/tools/room_investigation_V2/library/provider_gateway.py:ro"
  -v "$W/bench:/bench:ro"
  -v "$W/out:/out"
  -e "DATABASE_URL=postgresql+psycopg2://postgres:$PGPW@postgres:5432/ami_trade"
  -e USE_REAL_MARKET_DATA=true
  -e ROOM_VETO_REVIEW_ENABLED=true -e ROOM_RESURRECTION_REVIEW_ENABLED=true
  -e VLLM_FALLBACK_BASE_URL= -e VLLM_FALLBACK_MODEL= -e VLLM_FALLBACK_API_KEY=
  -e ANTHROPIC_API_KEY=
  -e LLM_DAILY_SPEND_CEILING_USD=
  -e "LLM_PRICES_JSON=$PRICES"
  -e "LLM_DESK_TEMPERATURE=$TEMP"
  -e ROOM_BENCH_AGENT_TIMEOUT_S="${ROOM_BENCH_AGENT_TIMEOUT_S:-300}")
[ "$PROVIDER" = deepinfra ] && ARGS+=(-e DEEPINFR_API_KEY)
[ -n "$EXTRA" ] && ARGS+=(-e "DEEPINFRA_EXTRA_BODY_JSON=$EXTRA")
# shellcheck disable=SC2206
[ -n "${EXTRA_DOCKER_ARGS:-}" ] && ARGS+=($EXTRA_DOCKER_ARGS)
ARGS+=(api-alpha /harness/docs/tools/room_investigation_V2/tools/room_benchmark.py
  --benchmark "/bench/$BENCH.yaml" --provider "$PROVIDER" --model "$MODEL"
  --skip-gate --max-concurrent "$CONC" --out-dir "/out/$LABEL/$OUTSUB")
echo "=== $LABEL/$OUTSUB start $(date -u +%FT%TZ) bench=$BENCH provider=$PROVIDER model=$MODEL conc=$CONC temp='${TEMP}' extra='${EXTRA}'"
docker "${ARGS[@]}"
rc=$?
echo "=== $LABEL/$OUTSUB end $(date -u +%FT%TZ) rc=$rc"
exit $rc
