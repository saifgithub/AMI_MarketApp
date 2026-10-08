#!/usr/bin/env bash
# melehost_matrix.sh — launch the unattended 300-room risk-matrix v2 from melehost.
#
# CR251 v2: the shipped stack (CR249 repair gate + CR252 evaluation parameters +
# CR253 data lanes + DEF451 fix) re-measured as the new production baseline, so
# the monotonicity science can diff against the frozen heuristics-off baseline
# (docs/forward_planning/CR251_risk_monotonicity_matrix/BASELINE.md).
#
# Why melehost: the Mac may be shut down. The run executes INSIDE the promoted
# api-alpha image (the exact deployed code), reaches vLLM over the LAN
# (192.168.20.74:8000 — no Tailscale relay), writes results to a host dir that
# survives, and is launched with nohup so it outlives this ssh session.
#
# Preconditions (checked, loud abort on failure — CR040):
#   1. This script runs on a machine with ssh access to melehost.
#   2. The promote has landed (~/ami_trade holds the new code; the image builds
#      from it on first `compose run`).
#   3. The D28 EDGAR ingest has run (rooms see SBC/ROIC for all 30 tickers).
#
# Usage:  bash melehost_matrix.sh            # R5 first, then R4..R1
# Results: melehost:~/cr251_v2/r{1..5}/      (pull: scp -r melehost:~/cr251_v2 .)
# Logs:    melehost:/tmp/cr251_v2.log
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
JEV_KEY="$(grep '^JEV_API_KEY=' "$REPO_ROOT/.env" | cut -d= -f2- | tr -d '"'"'")"
[ -n "$JEV_KEY" ] || { echo "JEV_API_KEY missing from repo .env"; exit 1; }

ssh melehost-ts 'bash -s' <<REMOTE
set -euo pipefail
cd ~/ami_trade
mkdir -p ~/cr251_v2
# Backend reachability preflight (LAN path, not the relay).
curl -sf -m 5 http://192.168.20.74:8000/v1/models >/dev/null || { echo "vLLM unreachable on LAN"; exit 1; }
PGPW=\$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
[ -n "\$PGPW" ] || { echo "POSTGRES_PASSWORD missing in ~/ami_trade/.env"; exit 1; }
JEK_ENV() { docker compose run --rm --no-deps --entrypoint python \
  -v ~/ami_trade:/harness:ro \
  -v ~/cr251_v2:/out \
  -e "DATABASE_URL=postgresql+psycopg2://postgres:\$PGPW@postgres:5432/ami_trade" \
  -e "VLLM_BASE_URL=http://192.168.20.74:8000" \
  -e USE_REAL_MARKET_DATA=true \
  -e "JEV_API_KEY=$JEV_KEY" \
  api-alpha "\$@"; }
for R in 5 4 3 2 1; do
  echo "=== V2 MATRIX RISK LEVEL \$R \$(date -u +%H:%M:%S) ==="
  JEK_ENV /harness/docs/tools/room_investigation_V2/tools/room_benchmark.py \
    --benchmark cr251-risk-matrix-r\$R --provider vllm \
    --skip-gate --max-concurrent 8 \
    --out-dir /out/r\$R || echo "R\$R exited non-zero — continuing"
done
echo "=== V2 MATRIX DONE \$(date -u +%H:%M:%S) ==="
REMOTE
