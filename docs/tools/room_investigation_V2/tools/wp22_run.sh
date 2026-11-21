#!/usr/bin/env bash
# wp22_run.sh: run wp22_score.py in a throwaway container of the deployed Alpha image (read-only DB, on-prem vLLM only).
# usage: wp22_run.sh NAME ARGS...   (container name wp22_NAME; stop with: docker stop wp22_NAME)
set -uo pipefail
NAME=$1; shift
W=$HOME/cr267_wp20
VLLM=http://192.168.20.74:8000
PGPW=$(grep '^POSTGRES_PASSWORD=' $W/frozen/.env | cut -d= -f2-)
[ -n "$PGPW" ] || { echo "POSTGRES_PASSWORD missing"; exit 1; }
cd $HOME/ami_trade
exec docker compose -p ami-trade-local run --rm --no-deps --name "wp22_$NAME" --entrypoint python \
  -v "$W/wp22_tool:/wp22:ro" -v "$W/out:/out" \
  -e "WP22_DSN=postgresql+psycopg2://postgres:$PGPW@postgres:5432/ami_trade" \
  -e "DATABASE_URL=sqlite:////tmp/wp22_sink.db" \
  -e "VLLM_BASE_URL=$VLLM" -e VLLM_MODEL=ami-llm \
  -e VLLM_FALLBACK_BASE_URL= -e VLLM_FALLBACK_MODEL= -e VLLM_FALLBACK_API_KEY= \
  -e ANTHROPIC_API_KEY= -e LLM_DAILY_SPEND_CEILING_USD= -e LLM_DESK_TEMPERATURE= \
  -e "LLM_PROVIDER_ALLOWLIST=vllm" \
  api-alpha /wp22/wp22_score.py "$@"
