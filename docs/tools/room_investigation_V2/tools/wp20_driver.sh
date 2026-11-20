#!/usr/bin/env bash
# wp20_driver.sh — CR267 WP-20 full baseline, unattended on melehost (AT:B1 CR267).
#
# Sequence (one job at a time, max 2 Rooms in flight, per the founder's 2026-11-20 pacing ruling):
#   1. arm1  — 30 tickers x risk 1-5 x 2 reps, cards OFF (300 rooms)
#   2. side  — 5 lowest-consensus tickers x risk 1-5 x 2 reps, cards OFF (50 rooms)
#   3. arm2  — same 300-room matrix, cards ON (evidence only), started only if arm 1's measured wall
#              time scaled by the pilot's cards/no-cards ratio predicts <= 24 h (else it stops and says so)
# Idempotent: every job resumes on the harness's completed-arm records, so re-running this script after a
# crash or reboot continues where it stopped. Launch (detached):
#   cd ~/cr267_wp20 && setsid nohup bash wp20_driver.sh > logs/driver.log 2>&1 < /dev/null &
# Stop: touch ~/cr267_wp20/STOP (checked between jobs), then `docker stop wp20_<label>` for the running job.
set -uo pipefail
W=$HOME/cr267_wp20
cd "$W"
CONC=${WP20_CONC:-2}
say() { echo "[driver $(date -u +%FT%TZ)] $*"; }
stop_requested() { [ -f "$W/STOP" ]; }

run_job() { # label bench cards
  stop_requested && { say "STOP present, not starting $1"; return 1; }
  say "start $1"
  bash "$W/wp20_run.sh" "$1" "$2" "$CONC" "$3" > "$W/logs/$1.log" 2>&1
  say "end $1 rc=$?"
}

T0=$(date +%s)
run_job arm1 wp20-arm1 false
T1=$(date +%s)
ARM1_S=$((T1 - T0))
run_job side wp20-side false

# Pilot ratio of cards-on to cards-off wall per room (same 3 rooms); fall back to 1.3 if unmeasured.
RATIO=$(python3 - <<'PY'
import json, os
def mean(p):
    try:
        d = [json.loads(l)["duration_ms"] for l in open(p) if l.strip()]
        return sum(d) / len(d)
    except Exception:
        return None
w = os.path.expanduser("~/cr267_wp20/out")
a, b = mean(f"{w}/pilot/runs_wp20-pilot.jsonl"), mean(f"{w}/pilot-cards/runs_wp20-pilot-cards.jsonl")
print(round(b / a, 3) if a and b else 1.3)
PY
)
EST_ARM2_H=$(python3 -c "print(round($ARM1_S * $RATIO / 3600, 1))")
say "arm1 wall ${ARM1_S}s; cards/no-cards pilot ratio $RATIO; arm2 estimate ${EST_ARM2_H}h (cap 24h)"
if python3 -c "import sys; sys.exit(0 if $EST_ARM2_H <= 24 else 1)"; then
  run_job arm2 wp20-arm2 true
else
  say "arm2 NOT started: estimate ${EST_ARM2_H}h exceeds 24h"
fi
say "driver done"
