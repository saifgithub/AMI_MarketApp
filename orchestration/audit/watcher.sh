#!/bin/sh
# watcher.sh - lane-state watcher for the audit handshake (PROTOCOL.md v2 lanes).
# Derives per-item state from the two lane files exactly as PROTOCOL.md defines it:
#   AWAITING_AUDIT : architect SUBMITTED round > auditor VERDICT round, or no auditor file yet
#   AWAITING_FIXES : auditor's LATEST verdict keyword is AWAITING_FIXES (keyword wins, per protocol note)
#   COMPLETE       : auditor's latest verdict keyword is COMPLETE and rounds have caught up
#   BAD_ROUND      : VERDICT round > SUBMITTED round — impossible, so a round was mistyped  <-- loud
# Only lines that EMIT a token count as state (see TOK below); a line quoting one is prose.
# Usage:
#   watcher.sh state                     print the derived state table once and exit
#   watcher.sh auditor   [-i N] [-t N]   block until >=1 lane is AWAITING_AUDIT  (poll every N s, default 30)
#   watcher.sh architect [-i N] [-t N]   block until >=1 lane is AWAITING_FIXES
# -t bounds the wait: give up after N seconds and exit 3 instead of blocking forever. Omit it only
# in an interactive session someone can interrupt; a one-shot agent has no such interrupt.
# Exit codes: 0 work found (or table printed) · 2 bad usage · 3 timed out with no work.
# Env: HANDSHAKE_CR_DIR overrides the lane directory (default: <script dir>/cr).
# Portable POSIX sh, no dependencies.

set -u
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CR_DIR=${HANDSHAKE_CR_DIR:-"$SCRIPT_DIR/cr"}

# A token is machine state only on a line that EMITS it. Markdown emphasis and headings are
# formatting, so `**TOKEN:` and `## TOKEN:` still count; a backtick, a blockquote `>`, indentation,
# or any preceding word means the line is TALKING ABOUT the token. Without this filter a lane file
# that quotes the protocol sets its own state, and `tail -1` gives the last sentence the last word.
TOK='^(#{1,6} )?\*{0,2}'

emits() {  # $1=file $2=extended-regex for the token; echoes only the lines that emit it
  [ -f "$1" ] || return 0
  grep -E "${TOK}$2" "$1" 2>/dev/null
}

last_match() {  # $1=file $2=token-regex; echoes the token as written on the LAST line emitting it
  # Strip the formatting prefix, then extract with `^` so only the occurrence that OPENS the line is
  # read. Without that anchor a trailing comment on the same line — `GATE: independent  <!-- ... a
  # chunk may carry GATE: none ... -->` — hands `tail -1` the value from the explanation.
  emits "$1" "$2" | tail -1 | sed -e 's/^#\{1,6\} //' -e 's/^\*\{1,2\}//' | grep -Eo "^$2"
}

last_round() {  # $1=file $2=extended-regex; echoes the last round number or empty
  last_match "$1" "$2" | grep -Eo '[0-9]+' | tail -1
}

last_kw() {  # $1=file $2=extended-regex; echoes the 2nd token of the match (the keyword)
  last_match "$1" "$2" | awk '{print $2}'
}

undelivered() {  # $1=file; echoes "1" if the file is untracked or differs from HEAD, else ""
  # A submission that exists only in one working tree has not been delivered. This auditor works
  # from its own checkout, so it would find nothing there while this table said work was waiting.
  # Silent when git is unavailable or this is not a repo: the check may degrade, never fail.
  command -v git >/dev/null 2>&1 || { echo ""; return; }
  git -C "$(dirname -- "$1")" rev-parse --git-dir >/dev/null 2>&1 || { echo ""; return; }
  git -C "$(dirname -- "$1")" ls-files --error-unmatch -- "$1" >/dev/null 2>&1 || { echo "1"; return; }
  git -C "$(dirname -- "$1")" diff --quiet HEAD -- "$1" 2>/dev/null || { echo "1"; return; }
  echo ""
}

lane_state() {  # $1=item id; echoes "STATE sub vr keyword"
  a="$CR_DIR/$1.architect.md"; u="$CR_DIR/$1.auditor.md"
  sub=$(last_round "$a" 'SUBMITTED: *round *[0-9]+'); sub=${sub:-0}
  # Never call an uncommitted submission AWAITING_AUDIT: an auditor told to audit the committed SHA
  # would find no submission at all. UNCOMMITTED is builder-actionable and one `git add` from fixed.
  if [ "$sub" -gt 0 ] && [ -n "$(undelivered "$a")" ]; then echo "UNCOMMITTED $sub - -"; return; fi
  if [ ! -f "$u" ]; then echo "AWAITING_AUDIT $sub - -"; return; fi
  # Same rule on the verdict side, so this table and the dispatch board cannot disagree about
  # whether a gate has been satisfied.
  if [ -n "$(undelivered "$u")" ]; then echo "UNCOMMITTED $sub - -"; return; fi
  kw=$(last_kw "$u" 'VERDICT: *(COMPLETE|AWAITING_FIXES)')
  vr=$(last_round "$u" 'VERDICT: *(COMPLETE|AWAITING_FIXES) *\(round *[0-9]+'); vr=${vr:-0}
  # A verdict can only answer a submission that exists. vr > sub means a round was mistyped, and
  # the strict test below then reads the lane as already-answered permanently: the builder fixes,
  # bumps, resubmits, and the board still says AWAITING_FIXES. Nothing errors and nothing logs, so
  # the lane just stops in a state that looks routine. Name the impossible combination instead.
  if [ "$vr" -gt "$sub" ]; then echo "BAD_ROUND $sub $vr ${kw:--}"; return; fi
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
TIMEOUT=0            # 0 = wait forever (an interactive standing session)
while [ $# -gt 0 ]; do
  case "$1" in
    -i) INTERVAL=${2:-30}; shift 2 ;;
    -t) TIMEOUT=${2:-0};   shift 2 ;;
     *) shift ;;
  esac
done

case "$MODE" in
  state) print_state ;;
  auditor|architect)
    [ "$MODE" = "auditor" ] && TARGET=AWAITING_AUDIT || TARGET=AWAITING_FIXES
    if [ "$TIMEOUT" -gt 0 ]; then
      echo "watching $CR_DIR for $TARGET (poll ${INTERVAL}s, give up after ${TIMEOUT}s)..."
    else
      echo "watching $CR_DIR for $TARGET (poll ${INTERVAL}s, ctrl-c to stop)..."
    fi
    elapsed=0
    while :; do
      c=$(count_state "$TARGET")
      if [ "$c" -gt 0 ]; then
        echo "$(date '+%H:%M:%S') $c lane(s) $TARGET:"; print_state; exit 0
      fi
      # A blocking watch is correct for a standing session and fatal for a one-shot: an agent
      # spawned per audit has no terminal to interrupt it, so an unbounded wait means it is
      # killed by its own harness with no verdict and no trace of why. -t bounds it and exits 3,
      # which a caller can tell apart from "found work" (0) and "bad usage" (2).
      if [ "$TIMEOUT" -gt 0 ] && [ "$elapsed" -ge "$TIMEOUT" ]; then
        echo "no lane reached $TARGET within ${TIMEOUT}s — exiting rather than blocking." >&2
        exit 3
      fi
      sleep "$INTERVAL"
      elapsed=$((elapsed + INTERVAL))
    done ;;
  *) echo "usage: watcher.sh state | auditor [-i N] [-t N] | architect [-i N] [-t N]" >&2; exit 2 ;;
esac
