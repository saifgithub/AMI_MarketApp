#!/usr/bin/env bash
# CR228 full 5-arm dial re-run on DeepInfra/GLM-5.3-Flash — same 30 tickers as
# the original R1/R5 pilot, risk_score 1..5, 30 convenes per arm = 150 total.
#
# This is the re-run Saiful asked for on 2026-09-27 ("re-run r1 to r5 for the
# same 30 tickers on deepinfra... 150 convenes"), driven from the existing
# generalized toolkit driver (docs/tools/room_investigation/room_ticker_batch.py)
# rather than a new one-off script — that tool already supports
# --provider deepinfra and --risk-score N end to end.
#
# Runs the 5 arms SEQUENTIALLY (one risk_score at a time, all 30 tickers before
# moving to the next) so a mid-run failure only ever needs to resume one arm —
# room_ticker_batch.py's own resumability (skips status=completed tickers on
# re-run with the same --batch-id) handles that per arm.
#
# Usage (from backend/, with real settings exported — backend/.env does not
# exist, see room_ticker_batch.py's own docstring):
#   export DATABASE_URL=postgresql+psycopg2://postgres:<REAL_PW>@localhost:5434/ami_trade
#   export USE_REAL_MARKET_DATA=true
#   export DEEPINFR_API_KEY=...
#   nohup ../docs/forward_planning/CR228_risk_appetite_differentiation/run_deepinfra_dial.sh \
#       > ../docs/forward_planning/CR228_risk_appetite_differentiation/results/dial_run.log 2>&1 &
set -euo pipefail

CR228_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT="$CR228_DIR/../../tools/room_investigation/room_ticker_batch.py"
TICKERS="$CR228_DIR/tickers_30.txt"
OUT_DIR="$CR228_DIR/results"
DATE_TAG="$(date -u +%Y%m%d)"
PYTHON="$(cd "$CR228_DIR/../../../backend" && pwd)/.venv/bin/python3"

for ARM in 1 2 3 4 5; do
  BATCH_ID="cr228-dial-r${ARM}-deepinfra-${DATE_TAG}"
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

echo "=== $(date -u +%FT%TZ) ALL 5 ARMS COMPLETE ==="
