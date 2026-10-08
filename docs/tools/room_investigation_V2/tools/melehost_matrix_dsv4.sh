#!/usr/bin/env bash
# melehost_matrix_dsv4.sh — launch the 300-room risk-matrix v2 on DeepSeek-V4-Flash.
#
# Why this exists: ami-host (ami-llm) died 2026-10-08 and needs a physical
# reboot. Saiful (2026-10-08): run the v2 matrix NOW on alpha-spark's
# DeepSeek-V4-Flash instead — "we'll see what we get, even if we do have a lot
# of changes." This run therefore CONFOUNDS the frozen-baseline diff with a
# provider change (v1 baseline ran ami-llm); it is kept in its own results dir
# (~/cr251_v2_dsv4) so the CLEAN ami-llm run can still execute later via
# v2_resume.sh (→ ~/cr251_v2) once ami-host is back.
#
# Usage:  bash melehost_matrix_dsv4.sh         # R5 first, then R4..R1
# Results: melehost:~/cr251_v2_dsv4/r{1..5}/
# Logs:    melehost:/tmp/cr251_v2_dsv4.log
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
JEV_KEY="$(grep '^JEV_API_KEY=' "$REPO_ROOT/.env" | cut -d= -f2- | tr -d '"'"'")"
[ -n "$JEV_KEY" ] || { echo "JEV_API_KEY missing from repo .env"; exit 1; }

ssh melehost-ts 'bash -s' <<REMOTE
set -euo pipefail
cd ~/ami_trade
mkdir -p ~/cr251_v2_dsv4 && chmod -R a+rwx ~/cr251_v2_dsv4
# Backend reachability preflight over Tailscale (alpha-spark, not the LAN box).
curl -sf -m 8 http://100.94.223.38:8003/v1/models >/dev/null || { echo "dsv4 unreachable"; exit 1; }
PGPW=\$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
[ -n "\$PGPW" ] || { echo "POSTGRES_PASSWORD missing in ~/ami_trade/.env"; exit 1; }
DSV4_ENV() { docker compose run --rm --no-deps --entrypoint python \
  -v ~/ami_trade:/harness:ro \
  -v ~/cr251_v2_dsv4:/out \
  -e "DATABASE_URL=postgresql+psycopg2://postgres:\$PGPW@postgres:5432/ami_trade" \
  -e VLLM_BASE_URL=http://100.94.223.38:8003 \
  -e VLLM_MODEL=deepseek-ai/DeepSeek-V4-Flash \
  -e USE_REAL_MARKET_DATA=true \
  -e "JEV_API_KEY=$JEV_KEY" \
  api-alpha "\$@"; }
for R in 5 4 3 2 1; do
  echo "=== V2 MATRIX (dsv4) RISK LEVEL \$R \$(date -u +%H:%M:%S) ==="
  DSV4_ENV /harness/docs/tools/room_investigation_V2/tools/room_benchmark.py \
    --benchmark cr251-risk-matrix-r\$R --provider vllm \
    --skip-gate --max-concurrent 4 \
    --out-dir /out/r\$R || echo "R\$R exited non-zero — continuing"
done
echo "=== V2 MATRIX (dsv4) DONE \$(date -u +%H:%M:%S) ==="
REMOTE
