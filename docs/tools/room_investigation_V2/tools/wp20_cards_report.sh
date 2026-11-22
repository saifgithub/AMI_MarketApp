#!/usr/bin/env bash
# wp20_cards_report.sh: run evidence_card_report.py over a finished WP-20 cards-ON arm, on melehost, in a
# throwaway container of the deployed image with a READ-ONLY database session (PGOPTIONS).
# usage: wp20_cards_report.sh NAME PROVIDER RUNS_IN_CONTAINER OUTDIR_IN_CONTAINER
#   e.g. wp20_cards_report.sh arm2 qwen38-flash-next-abliterated-nvfp4 /out/arm2/runs_wp20-arm2.jsonl /out/arm2/card_report
# The tool files (evidence_card_report.py, cards_run.py, evidence_gate_fit.py) are read from
# $HOME/cr267_wp20/cards_tool, mounted at a path five levels deep because the scripts compute REPO from
# `parents[4]`. The DB password comes from $HOME/cr267_wp20/frozen/.env, is never printed and never copied.
# Container name wp20cards_NAME; stop it with `docker stop wp20cards_NAME`. Writes only under /out.
set -uo pipefail
NAME=$1; PROVIDER=$2; RUNS=$3; OUTDIR=$4
W=$HOME/cr267_wp20
PGPW=$(grep '^POSTGRES_PASSWORD=' "$W/frozen/.env" | cut -d= -f2-)
[ -n "$PGPW" ] || { echo "POSTGRES_PASSWORD missing"; exit 1; }
cd "$HOME/ami_trade"
exec docker compose -p ami-trade-local run --rm --no-deps --name "wp20cards_$NAME" --entrypoint python \
  -v "$W/cards_tool:/r/a/b/c/tools:ro" -v "$W/out:/out" \
  -e "DATABASE_URL=postgresql+psycopg2://postgres:$PGPW@postgres:5432/ami_trade" \
  -e "PGOPTIONS=-c default_transaction_read_only=on" \
  -e VLLM_BASE_URL= -e VLLM_FALLBACK_BASE_URL= -e ANTHROPIC_API_KEY= -e LLM_PROVIDER_ALLOWLIST=mock \
  api-alpha /r/a/b/c/tools/evidence_card_report.py --provider "$PROVIDER" --runs "$RUNS" --out-dir "$OUTDIR"
