#!/usr/bin/env bash
# wp22_run.sh: run wp22_score.py in a throwaway container of the deployed Alpha image (read-only DB).
# usage: wp22_run.sh NAME ARGS...   (container name wp22_NAME; stop with: docker stop wp22_NAME)
# `--grader code` (CodeCardsGrader over the cards-ON arm): no model call, no key, no vLLM; cards rebuilt from llm_audit.
# Default grader (onprem): on-prem vLLM only. With `--grader jev|deepinfra` in ARGS the paid grader's
# key comes ONLY from $HOME/cr267_wp20/bakeoff.env (JEV_API_KEY=..., DEEPINFRA_API_KEY=...), handed to
# the container with `docker compose run --env-from-file`; this script never reads, prints or copies it.
# LLM_PROVIDER_ALLOWLIST then names only the needed slot (jev: mock, i.e. no gateway provider;
# deepinfra: vllm_fallback, the hosted slot wp22_score.py configures in-process); Anthropic stays blanked.
# `--grader ling_room` (the on-prem production grader, WP-23): no key, no bakeoff.env, no spend. Only the
# vllm_fallback slot is allowed; the Ling host comes from `--ling-url/--ling-model` or, if those are omitted,
# from the VLLM_FALLBACK_BASE_URL / VLLM_FALLBACK_MODEL the compose project already carries (not blanked here).
set -uo pipefail
NAME=$1; shift
W=$HOME/cr267_wp20
VLLM=http://192.168.20.74:8000
GRADER=onprem
prev=""
for a in "$@"; do
  [ "$prev" = "--grader" ] && GRADER=$a
  case "$a" in --grader=*) GRADER=${a#--grader=};; esac
  prev=$a
done
PGPW=$(grep '^POSTGRES_PASSWORD=' $HOME/ami_trade/.env | cut -d= -f2-)
[ -n "$PGPW" ] || { echo "POSTGRES_PASSWORD missing"; exit 1; }
ENVFILE_ARGS=()
case "$GRADER" in
  onprem)    ALLOW=vllm;;
  jev)       ALLOW=mock;     VLLM=;;
  deepinfra|cheapllm) ALLOW=vllm_fallback; VLLM=;;
  deepinfra_room) ALLOW=mock; VLLM=;;   # production grader: calls DeepInfra directly, never through the gateway
  code)      ALLOW=mock;     VLLM=;;   # plain code over cards: no model, no key, no network
  ling_room) ALLOW=vllm_fallback; VLLM=; FALLBACK_BLANK=0;;   # on-prem Ling through the gateway slot: no key
  *) echo "unknown --grader $GRADER (onprem|jev|deepinfra|cheapllm|code|deepinfra_room|ling_room)"; exit 1;;
esac
FALLBACK_ARGS=(-e VLLM_FALLBACK_BASE_URL= -e VLLM_FALLBACK_MODEL= -e VLLM_FALLBACK_API_KEY=)
[ "${FALLBACK_BLANK:-1}" = 0 ] && FALLBACK_ARGS=()
if [ "$GRADER" != onprem ] && [ "$GRADER" != code ] && [ "$GRADER" != ling_room ]; then
  case "$GRADER" in jev) KEYNAME=JEV_API_KEY;; cheapllm) KEYNAME=CHEAPLLM_API_KEY;; *) KEYNAME=DEEPINFRA_API_KEY;; esac
  [ -f "$W/bakeoff.env" ] || { echo "bakeoff.env missing $KEYNAME (file not found: $W/bakeoff.env, lines JEV_API_KEY=... and DEEPINFRA_API_KEY=...)"; exit 1; }
  ENVFILE_ARGS=(--env-from-file "$W/bakeoff.env")
fi
cd $HOME/ami_trade
exec docker compose -p ami-trade-local run --rm --no-deps --name "wp22_$NAME" --entrypoint python \
  ${ENVFILE_ARGS[@]+"${ENVFILE_ARGS[@]}"} \
  -v "$W/wp22_tool:/wp22:ro" -v "$W/out:/out" \
  -e "WP22_DSN=postgresql+psycopg2://postgres:$PGPW@postgres:5432/ami_trade" \
  -e "DATABASE_URL=sqlite:////tmp/wp22_sink.db" \
  -e "VLLM_BASE_URL=$VLLM" -e VLLM_MODEL=ami-llm \
  ${FALLBACK_ARGS[@]+"${FALLBACK_ARGS[@]}"} \
  -e ANTHROPIC_API_KEY= -e LLM_DAILY_SPEND_CEILING_USD= -e LLM_DESK_TEMPERATURE= \
  -e "LLM_PROVIDER_ALLOWLIST=$ALLOW" \
  api-alpha /wp22/wp22_score.py "$@"
