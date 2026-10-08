#!/usr/bin/env bash
# v2_resume.sh — post-promote resume driver for the CR251 v2 matrix (AT:K3 CR251).
#
# Why this exists: ami-host (DGX Spark, 192.168.20.74 — the ami-llm vLLM host)
# went hard-down during the promote of alpha-2026-10-09-1 (no LAN ARP, no
# Tailscale, last seen ~7.5h before detection). The promote itself completed;
# postflight is green on 7/8 checks — the only failure is `readiness`, caused
# entirely by the dead vLLM host. Physical reboot of ami-host is Saiful's
# job; the moment it answers again this driver fires the rest of the train:
#
#   1. AAPL sweep R5→R1 (room_sweep.py, in-container, results ~/cr251_smoke)
#   2. D28 EDGAR ingest (--force, 30 CR228 tickers) + SBC row-count verify
#   3. The 300-room v2 matrix via melehost_matrix.sh (nohup, ~12–15h)
#
# A cron fires this every 20 min. Exit codes (the cron reads them):
#   0 — vLLM still down, or a stage is in flight: keep waiting, cron stays.
#   2 — matrix launcher fired (or already running): cron deletes itself.
#   1 — RED: cron reports the log tail verbatim, deletes itself, stops.
#
# All state lives on melehost (~/cr251_smoke/.sweep_done|.sweep_failed,
# ~/ami_trade/.d28_done|.d28_failed, /tmp/v2_*.log, /tmp/v2_*.sh) so a Mac
# reboot loses nothing; the next cron fire re-reads remote state.
set -uo pipefail

SSh() { ssh -o ConnectTimeout=10 melehost-ts "$@"; }

# Stage helpers. Each remote stage is a script dropped on melehost via stdin
# (no quote nesting), fired with nohup, and polled via sentinel files.
# stage_poll <done> <failed> <log> <running-cmd>
stage_poll() {
  local done_mark=$1 failed_mark=$2 log=$3 running=$4
  if SSh "[ -f $failed_mark ]"; then
    echo "RED: stage failed — $log tail:"
    SSh "tail -30 $log"
    return 1
  fi
  if SSh "[ -f $done_mark ]"; then return 2; fi
  if SSh "[ -f $log ]"; then
    # In flight, or died without writing a sentinel?
    if SSh "$running" >/dev/null 2>&1; then return 3; fi
    # No process and no sentinel: if the log went quiet >30 min it is stuck.
    if SSh "[ -n \"\$(find $log -mmin +30)\" ]"; then
      echo "RED: stage stalled (log idle >30m, no sentinel) — $log tail:"
      SSh "tail -30 $log"
      return 1
    fi
    return 3
  fi
  return 0   # never started
}

# ── Stage 0: is vLLM back? ───────────────────────────────────────────────────
if ! SSh 'curl -sf -m 6 http://192.168.20.74:8000/v1/models >/dev/null'; then
  echo "vLLM still unreachable on LAN — waiting for ami-host reboot."
  exit 0
fi
echo "vLLM is BACK ($(date -u +%H:%M:%SZ))"

# ── Stage 1: AAPL sweep R5→R1 ────────────────────────────────────────────────
stage_poll ~/cr251_smoke/.sweep_done ~/cr251_smoke/.sweep_failed /tmp/v2_sweep.log \
  'docker ps --format "{{.Names}}" | grep -q api-alpha-run'
case $? in
  1) exit 1 ;;
  2) echo "sweep DONE" ;;
  3) echo "sweep in flight — waiting."; exit 0 ;;
  0)
    echo "firing AAPL sweep R5→R1 (detached on melehost)"
    SSh 'cat > /tmp/v2_sweep.sh' <<'SCRIPT'
#!/usr/bin/env bash
cd ~/ami_trade
PGPW=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
docker compose run --rm --no-deps --entrypoint python \
  -v ~/ami_trade/docs/tools/room_investigation_V2:/harness:ro \
  -v ~/cr251_smoke:/out \
  -e "DATABASE_URL=postgresql+psycopg2://postgres:${PGPW}@postgres:5432/ami_trade" \
  -e VLLM_BASE_URL=http://192.168.20.74:8000 \
  -e USE_REAL_MARKET_DATA=true \
  api-alpha /harness/tools/room_sweep.py --ticker AAPL --risk-scores 5,4,3,2,1 \
    --provider vllm --out-dir /out
rc=$?
echo "sweep exit: $rc" >> /tmp/v2_sweep.log
if [ $rc -eq 0 ]; then touch ~/cr251_smoke/.sweep_done; else touch ~/cr251_smoke/.sweep_failed; fi
SCRIPT
    SSh 'mkdir -p ~/cr251_smoke && nohup bash /tmp/v2_sweep.sh </dev/null >/tmp/v2_sweep.log 2>&1 & disown; echo launched'
    exit 0 ;;
esac

# ── Stage 2: D28 EDGAR ingest + verify ───────────────────────────────────────
stage_poll ~/ami_trade/.d28_done ~/ami_trade/.d28_failed /tmp/v2_ingest.log \
  'docker exec ami_api_alpha pgrep -f ingest_edgar_facts >/dev/null'
case $? in
  1) exit 1 ;;
  2) echo "ingest DONE" ;;
  3) echo "ingest in flight — waiting."; exit 0 ;;
  0)
    echo "firing D28 ingest (detached on melehost)"
    SSh 'cat > /tmp/v2_ingest.sh' <<'SCRIPT'
#!/usr/bin/env bash
cd ~/ami_trade
docker compose exec -T api-alpha python scripts/ingest_edgar_facts.py \
  --tickers-file docs/forward_planning/CR228_risk_appetite_differentiation/tickers_30.txt \
  --user-agent "AMI MarketApp admin@agenticmarketintel.ai" --force
rc=$?
echo "ingest exit: $rc" >> /tmp/v2_ingest.log
if [ $rc -eq 0 ]; then touch ~/ami_trade/.d28_done; else touch ~/ami_trade/.d28_failed; fi
SCRIPT
    SSh 'nohup bash /tmp/v2_ingest.sh </dev/null >/tmp/v2_ingest.log 2>&1 & disown; echo launched'
    exit 0 ;;
esac

SBC=$(SSh 'cd ~/ami_trade && docker compose exec -T postgres psql -U postgres -d ami_trade -tAc "SELECT count(DISTINCT ticker) FROM edgar_facts WHERE tag='"'"'ShareBasedCompensation'"'"'" 2>/dev/null || echo query-failed')
echo "SBC tickers in edgar_facts: $SBC"
case "$SBC" in
  ''|*[!0-9]*) echo "RED: SBC verify query did not return a number (got '$SBC')"; exit 1 ;;
esac
if [ "$SBC" -lt 20 ]; then
  echo "RED: only $SBC tickers have SBC facts (<20) — ingest did not take; not launching the matrix on a broken D28."
  exit 1
fi

# ── Stage 3: launch the 300-room v2 matrix ───────────────────────────────────
if SSh '[ -f ~/cr251_v2/.matrix_launched ]'; then
  echo "matrix already launched — nothing to do."
  exit 2
fi
echo "launching v2 matrix (nohup on Mac; runs ~12–15h on melehost)"
SSh 'mkdir -p ~/cr251_v2 && touch ~/cr251_v2/.matrix_launched'
cd "$(dirname "$0")"
nohup bash melehost_matrix.sh </dev/null >/tmp/v2_matrix.log 2>&1 & disown
echo "matrix launcher fired — driver complete."
exit 2
