#!/usr/bin/env bash
# CR228 Step 1 pilot — R1 vs R5 over the same 30 tickers.
#
# Runs INSIDE ami_api_alpha (CR035's ops lesson: run in-container, not from the
# Mac). Strictly one convene in flight, arms sequential — the documented vLLM
# ceiling. Each arm mints its OWN user via --fresh-user, which is MANDATORY:
# resolve_mandate (mandate_store.py:292) ignores mandate_override when the user
# already has a stored mandate, so without it both arms silently run identically.
#
# The two mandates differ in risk_score ONLY. Every other field is pinned so the
# arm is the single variable. max_drawdown_pct is held at 30 deliberately: it is
# NOT part of risk_score's preset table, and letting it track the tier would
# confound the cap effect with a drawdown-headroom effect.
set -euo pipefail

STAMP="${STAMP:-$(date -u +%Y%m%d)}"
OUT="${OUT:-/tmp/cr228}"
BASE="${BASE:-http://localhost:8000}"
TICKERS="${TICKERS:-/tmp/cr228/tickers_30.txt}"

mkdir -p "$OUT"

base_mandate() {  # $1 = risk_score
  cat <<JSON
{"display_name":"CR228 R$1","primary_goal":"long_term_wealth","horizon":"long",
 "path":"long_horizon","risk_score":$1,"drawdown_response":$1,"regret_asymmetry":0,
 "concentration_tolerance":$1,"max_drawdown_pct":30,"compliance":{}}
JSON
}

for RS in 1 5; do
  BATCH="cr228-r${RS}-${STAMP}"
  echo "=== arm risk_score=${RS} · batch=${BATCH} · $(date -u +%H:%M:%SZ) ==="
  python -m scripts.room_benchmark "$TICKERS" \
    --batch-id "$BATCH" \
    --fresh-user \
    --plan trader \
    --base-url "$BASE" \
    --out-dir "$OUT" \
    --mandate-json "$(base_mandate "$RS" | tr -d '\n')" \
    >> "$OUT/driver_${BATCH}.log" 2>&1
  echo "=== arm ${RS} done · $(date -u +%H:%M:%SZ) ==="
done
echo "ALL ARMS COMPLETE"
