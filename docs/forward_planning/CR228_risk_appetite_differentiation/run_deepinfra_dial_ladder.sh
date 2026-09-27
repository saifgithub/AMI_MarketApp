#!/usr/bin/env bash
# CR228 5-arm DeepInfra dial re-run, PM_OPTION_LADDER_ENABLED=true — same 30
# tickers, comparing directly against melehost's real 5-arm production pilot
# (vLLM, ladder OFF, room_risk_officer_enabled=true, results/melehost_pilot_20260926/)
# pulled down 2026-09-27. Saiful, 2026-09-27: "1. ensure you have the fixes
# for 244 and 448. 2. run R1 so we can compare directly the impact. 3.
# continue with r3,r5,r2,r4."
#
# Distinct batch-id/log from run_deepinfra_dial.sh's earlier (partial,
# ladder-OFF) run — that data stays as its own dataset, not overwritten or
# conflated with this one. Runs R1 FIRST for the direct A/B against
# melehost's real R1 arm (0/30 approved, ladder off), then R3, R5, R2, R4 in
# the order asked — deliberately not the natural 1-2-3-4-5 sweep order.
#
# Usage (from backend/, with real settings exported — backend/.env does not
# exist, see room_ticker_batch.py's own docstring):
#   export DATABASE_URL=postgresql+psycopg2://postgres:<REAL_PW>@localhost:5434/ami_trade
#   export USE_REAL_MARKET_DATA=true
#   export DEEPINFR_API_KEY=...
#   export PM_OPTION_LADDER_ENABLED=true
#   nohup ../docs/forward_planning/CR228_risk_appetite_differentiation/run_deepinfra_dial_ladder.sh \
#       > ../docs/forward_planning/CR228_risk_appetite_differentiation/results/dial_run_ladder.log 2>&1 &
set -euo pipefail

if [ "${PM_OPTION_LADDER_ENABLED:-}" != "true" ]; then
  echo "PM_OPTION_LADDER_ENABLED is not 'true' in this shell — refusing to run" \
       "a script whose whole point is measuring the ladder ON. Export it first." >&2
  exit 1
fi

CR228_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT="$CR228_DIR/../../tools/room_investigation/room_ticker_batch.py"
TICKERS="$CR228_DIR/tickers_30.txt"
OUT_DIR="$CR228_DIR/results"
DATE_TAG="$(date -u +%Y%m%d)"
PYTHON="$(cd "$CR228_DIR/../../../backend" && pwd)/.venv/bin/python3"

for ARM in 1 3 5 2 4; do
  BATCH_ID="cr228-dial-ladder-r${ARM}-deepinfra-${DATE_TAG}"
  echo "=== $(date -u +%FT%TZ) starting arm risk_score=${ARM} (batch ${BATCH_ID}) ==="
  "$PYTHON" "$TOOLKIT" \
    --tickers-file "$TICKERS" \
    --provider deepinfra \
    --risk-score "$ARM" \
    --batch-id "$BATCH_ID" \
    --out-dir "$OUT_DIR" \
    --fresh-user
  echo "=== $(date -u +%FT%TZ) finished arm risk_score=${ARM} ==="
done

echo "=== $(date -u +%FT%TZ) ALL 5 ARMS COMPLETE (ladder-on run) ==="
