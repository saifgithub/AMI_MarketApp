#!/usr/bin/env bash
# wp20_run.sh — one CR267 WP-20 Room-baseline job, run ON melehost (AT:B1 CR267).
#
# Runs a wp20-*.yaml benchmark through the V2 harness inside a throwaway named `docker compose run`
# container (the promoted api-alpha image, repo mounted read-only at /harness), live data, production Room
# settings (prompts backend-default, veto + resurrection reviews ON, evidence gate OFF), on Alpha's
# on-prem primary vLLM only: the failover slot is blanked so every room is measured on ONE model, and no
# hosted vendor key is passed. Zero spend. Records the model `root` from /v1/models before and after.
# Writes ONLY under ~/cr267_wp20/ (never ~/ami_trade, never the live ami_api_alpha container).
#
# usage: wp20_run.sh LABEL BENCH CONC CARDS   (CARDS = true|false -> ROOM_CARDS_ENVELOPE_ENABLED)
#   container name: wp20_<LABEL>   (stop it with: docker stop wp20_<LABEL>)
set -uo pipefail
LABEL=$1; BENCH=$2; CONC=$3; CARDS=${4:-false}
W=$HOME/cr267_wp20
VLLM=http://192.168.20.74:8000
cd ~/ami_trade
PGPW=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
[ -n "$PGPW" ] || { echo "POSTGRES_PASSWORD missing"; exit 1; }
mkdir -p "$W/out/$LABEL" "$W/logs"; chmod -R a+rwx "$W/out"
root() { curl -s -m 10 "$VLLM/v1/models" | python3 -c "import sys,json;print(','.join(sorted({m.get('root','?') for m in json.load(sys.stdin)['data']})))"; }
ROOT0=$(root) || { echo "vLLM unreachable"; exit 1; }
echo "=== $LABEL start $(date -u +%FT%TZ) bench=$BENCH conc=$CONC cards=$CARDS model_root=$ROOT0 git=$(docker exec ami_api_alpha printenv GIT_SHA)"
echo "$ROOT0" > "$W/out/$LABEL/model_root_start.txt"
docker compose run --rm --no-deps --name "wp20_$LABEL" --entrypoint python \
  -v "$HOME/ami_trade:/harness:ro" -v "$W/bench:/bench:ro" -v "$W/out:/out" \
  -e "DATABASE_URL=postgresql+psycopg2://postgres:$PGPW@postgres:5432/ami_trade" \
  -e "VLLM_BASE_URL=$VLLM" -e VLLM_MODEL=ami-llm \
  -e USE_REAL_MARKET_DATA=true \
  -e ROOM_VETO_REVIEW_ENABLED=true -e ROOM_RESURRECTION_REVIEW_ENABLED=true \
  -e ROOM_EVIDENCE_GATE_ENABLED=false -e "ROOM_CARDS_ENVELOPE_ENABLED=$CARDS" \
  -e VLLM_FALLBACK_BASE_URL= -e VLLM_FALLBACK_MODEL= -e VLLM_FALLBACK_API_KEY= \
  -e ANTHROPIC_API_KEY= -e LLM_DAILY_SPEND_CEILING_USD= -e LLM_DESK_TEMPERATURE= \
  -e ROOM_BENCH_AGENT_TIMEOUT_S="${ROOM_BENCH_AGENT_TIMEOUT_S:-300}" \
  api-alpha /harness/docs/tools/room_investigation_V2/tools/room_benchmark.py \
  --benchmark "/bench/$BENCH.yaml" --provider vllm --skip-gate \
  --max-concurrent "$CONC" --out-dir "/out/$LABEL"
rc=$?
root > "$W/out/$LABEL/model_root_end.txt" 2>/dev/null
echo "=== $LABEL end $(date -u +%FT%TZ) rc=$rc model_root_end=$(cat "$W/out/$LABEL/model_root_end.txt")"
exit $rc
