#!/bin/sh
# dispatch.sh - lane-state watcher for the dispatch handshake (DISPATCH_PROTOCOL.md §4).
# Derives per-item state from three files: the assign lane, the instance lane, and (for code) the
# audit lane's VERDICT. No shared flag; state is derived from round watermarks + keywords.
#   UNASSIGNED     : assign lane has no ASSIGNED line
#   ASSIGNED       : ASSIGNED round > instance STATUS round, or no instance file yet
#   IN_PROGRESS    : instance STATUS = CLAIMED|IN_PROGRESS
#   BLOCKED        : instance STATUS = BLOCKED
#   NEEDS-INFO     : instance STATUS = NEEDS-INFO (architect must answer Q:)
#   IN_REVIEW      : instance STATUS = READY_FOR_REVIEW (content; architect review)
#   IN_AUDIT       : READY_FOR_AUDIT + audit VERDICT not yet returned
#   AUDIT_RETURNED : audit VERDICT = AWAITING_FIXES
#   AUDIT_PASSED   : audit VERDICT = COMPLETE, DISPATCH not yet ACCEPTED
#   DONE           : DISPATCH = ACCEPTED
# Usage:
#   dispatch.sh state              print the derived board once and exit
#   dispatch.sh architect [-i N]   block until >=1 lane needs the Architect
#                                    (UNASSIGNED|BLOCKED|NEEDS-INFO|IN_REVIEW|AUDIT_PASSED)
#   dispatch.sh inst <id> [-i N]   block until >=1 lane is ASSIGNED to <id> or AUDIT_RETURNED on it
# Env: DISPATCH_LANE_DIR overrides the lane dir (default <script dir>/lanes).
#      DISPATCH_AUDIT_DIR overrides the audit lane dir (default <script dir>/../audit/handshake/cr).
# Portable POSIX sh, no dependencies. Sibling of audit/handshake/watcher.sh.

set -u
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LANE_DIR=${DISPATCH_LANE_DIR:-"$SCRIPT_DIR/lanes"}
AUDIT_DIR=${DISPATCH_AUDIT_DIR:-"$SCRIPT_DIR/../audit/handshake/cr"}

last_round() {  # $1=file $2=extended-regex; echoes the last round number or empty
  [ -f "$1" ] || { echo ""; return; }
  grep -Eo "$2" "$1" 2>/dev/null | tail -1 | grep -Eo '[0-9]+' | tail -1
}

last_kw() {  # $1=file $2=extended-regex; echoes the 2nd token of the last match (the keyword)
  [ -f "$1" ] || { echo ""; return; }
  grep -Eo "$2" "$1" 2>/dev/null | tail -1 | awk '{print $2}'
}

lane_state() {  # $1=item; echoes "STATE instance asg_round st_kw verdict"
  # Dispatch tokens (ASSIGNED/DISPATCH/STATUS) MUST be at line start — anchored so a token
  # mentioned in prose/backticks is never parsed as a live signal. (VERDICT is read unanchored to
  # mirror audit/handshake/watcher.sh, whose files carry a `## VERDICT:` heading + a trailer.)
  a="$LANE_DIR/$1.assign.md"
  asg_line=$(grep -Eo '^ASSIGNED: *[A-Za-z0-9._-]+ *round *[0-9]+' "$a" 2>/dev/null | tail -1)
  if [ -z "$asg_line" ]; then echo "UNASSIGNED - - - -"; return; fi
  inst=$(echo "$asg_line" | awk '{print $2}')
  asg_round=$(echo "$asg_line" | grep -Eo '[0-9]+' | tail -1); asg_round=${asg_round:-0}

  disp_kw=$(last_kw "$a" '^DISPATCH: *(OPEN|ACCEPTED)')
  if [ "$disp_kw" = "ACCEPTED" ]; then echo "DONE $inst $asg_round - -"; return; fi

  i="$LANE_DIR/$1.$inst.md"
  st_kw=$(last_kw "$i" '^STATUS: *(CLAIMED|IN_PROGRESS|BLOCKED|NEEDS-INFO|READY_FOR_AUDIT|READY_FOR_REVIEW)')
  st_round=$(last_round "$i" '^STATUS: *(CLAIMED|IN_PROGRESS|BLOCKED|NEEDS-INFO|READY_FOR_AUDIT|READY_FOR_REVIEW) *\(round *[0-9]+'); st_round=${st_round:-0}

  if [ ! -f "$i" ] || [ "$asg_round" -gt "$st_round" ]; then
    echo "ASSIGNED $inst $asg_round ${st_kw:--} -"; return
  fi

  u="$AUDIT_DIR/$1.auditor.md"
  v_kw=$(last_kw "$u" 'VERDICT: *(COMPLETE|AWAITING_FIXES)')

  case "${st_kw:-}" in
    CLAIMED|IN_PROGRESS) echo "IN_PROGRESS $inst $asg_round $st_kw -" ;;
    BLOCKED)             echo "BLOCKED $inst $asg_round $st_kw -" ;;
    NEEDS-INFO)          echo "NEEDS-INFO $inst $asg_round $st_kw -" ;;
    READY_FOR_REVIEW)    echo "IN_REVIEW $inst $asg_round $st_kw -" ;;
    READY_FOR_AUDIT)
      case "${v_kw:-}" in
        AWAITING_FIXES) echo "AUDIT_RETURNED $inst $asg_round $st_kw $v_kw" ;;
        COMPLETE)       echo "AUDIT_PASSED $inst $asg_round $st_kw $v_kw" ;;
        *)              echo "IN_AUDIT $inst $asg_round $st_kw ${v_kw:--}" ;;
      esac ;;
    *) echo "ASSIGNED $inst $asg_round ${st_kw:--} -" ;;
  esac
}

items() {
  for f in "$LANE_DIR"/*.assign.md; do
    [ -f "$f" ] || continue
    basename "$f" .assign.md
  done
}

print_state() {
  n=0
  printf '%-14s %-16s %-16s %-5s %-18s %-9s\n' "ITEM" "STATE" "INSTANCE" "ASG" "STATUS" "VERDICT"
  for it in $(items); do
    n=$((n+1))
    set -- $(lane_state "$it")
    printf '%-14s %-16s %-16s r%-4s %-18s %-9s\n' "$it" "$1" "$2" "$3" "$4" "$5"
  done
  [ "$n" -eq 0 ] && echo "(no lanes yet under $LANE_DIR)"
  return 0
}

# needs_architect: lane state is one the Architect must act on
needs_architect() {
  case "$1" in
    UNASSIGNED|BLOCKED|NEEDS-INFO|IN_REVIEW|AUDIT_PASSED) return 0 ;;
    *) return 1 ;;
  esac
}

count_architect() {
  c=0
  for it in $(items); do
    st=$(lane_state "$it"); s=${st%% *}
    needs_architect "$s" && c=$((c+1))
  done
  echo "$c"
}

count_inst() {  # uses $TARGET_INST; counts lanes ASSIGNED to it or AUDIT_RETURNED on it
  c=0
  for it in $(items); do
    set -- $(lane_state "$it")
    s=$1; who=$2
    if [ "$who" = "$TARGET_INST" ]; then
      case "$s" in ASSIGNED|AUDIT_RETURNED) c=$((c+1)) ;; esac
    fi
  done
  echo "$c"
}

MODE=${1:-state}; shift 2>/dev/null || true

case "$MODE" in
  state) print_state; exit 0 ;;
  architect)
    INTERVAL=30; [ "${1:-}" = "-i" ] && INTERVAL=${2:-30}
    echo "watching $LANE_DIR for Architect-actionable lanes (poll ${INTERVAL}s, ctrl-c to stop)..."
    while :; do
      c=$(count_architect)
      if [ "$c" -gt 0 ]; then echo "$(date '+%H:%M:%S') $c lane(s) need the Architect:"; print_state; exit 0; fi
      sleep "$INTERVAL"
    done ;;
  inst)
    TARGET_INST=${1:-}; shift 2>/dev/null || true
    [ -z "${TARGET_INST:-}" ] && { echo "usage: dispatch.sh inst <instance-id> [-i N]" >&2; exit 2; }
    INTERVAL=30; [ "${1:-}" = "-i" ] && INTERVAL=${2:-30}
    echo "watching $LANE_DIR for lanes targeting $TARGET_INST (poll ${INTERVAL}s, ctrl-c to stop)..."
    while :; do
      c=$(count_inst "$TARGET_INST")
      if [ "$c" -gt 0 ]; then echo "$(date '+%H:%M:%S') $c lane(s) for $TARGET_INST:"; print_state; exit 0; fi
      sleep "$INTERVAL"
    done ;;
  *) echo "usage: dispatch.sh state | architect [-i N] | inst <instance-id> [-i N]" >&2; exit 2 ;;
esac
