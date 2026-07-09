#!/bin/sh
# watcher.sh - lane-state watcher for the audit handshake (PROTOCOL.md v2 lanes).
# Derives per-item state from the two lane files exactly as PROTOCOL.md defines it:
#   AWAITING_AUDIT : architect SUBMITTED round > auditor VERDICT round, or no auditor file yet
#   AWAITING_FIXES : auditor's LATEST verdict keyword is AWAITING_FIXES (keyword wins, per protocol note)
#   COMPLETE       : auditor's latest verdict keyword is COMPLETE and rounds have caught up
# Usage:
#   watcher.sh state              print the derived state table once and exit
#   watcher.sh auditor   [-i N]   block until >=1 lane is AWAITING_AUDIT  (poll every N s, default 30)
#   watcher.sh architect [-i N]   block until >=1 lane is AWAITING_FIXES
# Env: HANDSHAKE_CR_DIR overrides the lane directory (default: <script dir>/cr).
# Portable POSIX sh, no dependencies. Shared verbatim with the Aegis-Finance audit loop.

set -u
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CR_DIR=${HANDSHAKE_CR_DIR:-"$SCRIPT_DIR/cr"}

last_round() {  # $1=file $2=extended-regex with round number as the only capture-ish digits
  grep -Eo "$2" "$1" 2>/dev/null | tail -1 | grep -Eo '[0-9]+' | tail -1
}

lane_state() {  # $1=item id; echoes "STATE sub vr keyword"
  a="$CR_DIR/$1.architect.md"; u="$CR_DIR/$1.auditor.md"
  sub=$(last_round "$a" 'SUBMITTED: *round *[0-9]+'); sub=${sub:-0}
  if [ ! -f "$u" ]; then echo "AWAITING_AUDIT $sub - -"; return; fi
  kw=$(grep -Eo 'VERDICT: *(COMPLETE|AWAITING_FIXES)' "$u" 2>/dev/null | tail -1 | awk '{print $2}')
  vr=$(last_round "$u" 'VERDICT: *(COMPLETE|AWAITING_FIXES) *\(round *[0-9]+'); vr=${vr:-0}
  if [ "$sub" -gt "$vr" ]; then echo "AWAITING_AUDIT $sub $vr ${kw:--}"; return; fi
  case "${kw:-}" in
    AWAITING_FIXES) echo "AWAITING_FIXES $sub $vr $kw" ;;
    COMPLETE)       echo "COMPLETE $sub $vr $kw" ;;
    *)              echo "AWAITING_AUDIT $sub $vr -" ;;   # auditor file exists but no verdict yet
  esac
}

items() {
  for f in "$CR_DIR"/*.architect.md; do
    [ -f "$f" ] || continue
    basename "$f" .architect.md
  done
}

print_state() {
  n=0
  printf '%-22s %-16s %-10s %-9s\n' "ITEM" "STATE" "SUBMITTED" "VERDICT"
  for it in $(items); do
    n=$((n+1))
    set -- $(lane_state "$it")
    printf '%-22s %-16s %-10s %-9s\n' "$it" "$1" "r$2" "r$3(${4})"
  done
  [ "$n" -eq 0 ] && echo "(no lanes yet under $CR_DIR)"
}

count_state() {  # counts lanes whose state == $TARGET
  c=0
  for it in $(items); do
    s=$(lane_state "$it"); s=${s%% *}
    [ "$s" = "$TARGET" ] && c=$((c+1))
  done
  echo "$c"
}

MODE=${1:-state}; shift 2>/dev/null || true
INTERVAL=30
[ "${1:-}" = "-i" ] && INTERVAL=${2:-30}

case "$MODE" in
  state) print_state ;;
  auditor|architect)
    [ "$MODE" = "auditor" ] && TARGET=AWAITING_AUDIT || TARGET=AWAITING_FIXES
    echo "watching $CR_DIR for $TARGET (poll ${INTERVAL}s, ctrl-c to stop)..."
    while :; do
      c=$(count_state "$TARGET")
      if [ "$c" -gt 0 ]; then
        echo "$(date '+%H:%M:%S') $c lane(s) $TARGET:"; print_state; exit 0
      fi
      sleep "$INTERVAL"
    done ;;
  *) echo "usage: watcher.sh state | auditor [-i N] | architect [-i N]" >&2; exit 2 ;;
esac
