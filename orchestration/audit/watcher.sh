#!/bin/sh
# watcher.sh - lane-state watcher for the audit handshake (PROTOCOL.md v2 lanes).
# Derives per-item state from the two lane files exactly as PROTOCOL.md defines it:
#   UNPUSHED           : a VERDICT is committed but not on origin's default branch — the other      <-- loud
#                        role works from its own checkout and cannot see it; chase the push
#   UNCOMMITTED_SUBMIT : the SUBMISSION is not committed — nobody but its author can see it   <-- loud
#   UNPUSHED_SUBMIT    : the SUBMISSION is committed but not on origin — same, one step on   <-- loud
#                        These two are the submitter's OWN job to clear, never anyone else's.
#   AWAITING_AUDIT : architect SUBMITTED round > auditor VERDICT round, or no auditor file yet
#   DRAFT          : a lane file exists but has emitted NO `SUBMITTED:` round yet — authored, not
#                    submitted. Not work for anybody, and deliberately not AWAITING_AUDIT (DEF300)
#   AWAITING_FIXES : auditor's LATEST verdict keyword is AWAITING_FIXES (keyword wins, per protocol note)
#   COMPLETE       : auditor's latest verdict keyword is COMPLETE and rounds have caught up
#   BAD_ROUND      : VERDICT round > SUBMITTED round — impossible, so a round was mistyped  <-- loud
# `state` also reports a watcher that DIED — a stale heartbeat it never cleaned up — because a
# dead watcher and an empty queue are otherwise byte-identical from the outside.
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

unpushed() {  # $1=file; echoes "1" if the file's newest commit is not on the shared remote branch
  # `undelivered` above closes the working-tree gap. This closes the one after it, and they are NOT
  # the same gap: a file can be committed (so `undelivered` is silent) and still exist only in this
  # clone. The auditor works from its OWN checkout and reaches this repo through `origin`, so an
  # unpushed SUBMITTED marker makes the lane read AWAITING_AUDIT here and not exist at all there.
  # Both sides then behave correctly and disagree forever — the architect waits for a verdict on
  # work never delivered, the auditor truthfully reports nothing to audit.
  # Silent when git is unavailable, this is not a repo, or no remote branch can be resolved (a fresh
  # clone, a deploy host, a detached CI checkout): the check may degrade, never fail the caller.
  command -v git >/dev/null 2>&1 || { echo ""; return; }
  d=$(dirname -- "$1")
  git -C "$d" rev-parse --git-dir >/dev/null 2>&1 || { echo ""; return; }
  # The handshake medium is the shared default branch, not this checkout's upstream: a lane worktree
  # tracks `origin/lane/...`, which the auditor never reads. Resolve origin's HEAD, fall back to
  # origin/main, and stay silent if neither exists rather than inventing a branch name.
  rem=$(git -C "$d" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null)
  [ -n "$rem" ] || rem=$(git -C "$d" rev-parse --verify --quiet origin/main >/dev/null 2>&1 && echo origin/main)
  [ -n "$rem" ] || { echo ""; return; }
  sha=$(git -C "$d" log -1 --format=%H -- "$1" 2>/dev/null)
  [ -n "$sha" ] || { echo ""; return; }
  # NOTE: read against the LOCAL remote-tracking ref — no fetch. A watcher must not do network I/O
  # on every poll, and for ordinary staleness the error direction is the safe one: after your own
  # push the ref is current so the normal flow never false-alarms, and a ref stale because SOMEONE
  # ELSE pushed can only over-report, costing a `git fetch`.
  # That claim does NOT generalise to a rewritten remote, which is the one construction that
  # under-reports: rebase or force-push the commit off the remote and the local ref still holds the
  # old sha, so `--is-ancestor` passes and this reports delivered for a commit the remote no longer
  # has — until the next fetch. Narrow, since it requires rewriting shared history, but real: do not
  # read this as "staleness can only over-report".
  git -C "$d" merge-base --is-ancestor "$sha" "$rem" 2>/dev/null && { echo ""; return; }
  echo "1"
}

lane_state() {  # $1=item id; echoes "STATE sub vr keyword"
  a="$CR_DIR/$1.architect.md"; u="$CR_DIR/$1.auditor.md"
  sub=$(last_round "$a" 'SUBMITTED: *round *[0-9]+'); sub=${sub:-0}
  # Never call an uncommitted submission AWAITING_AUDIT: an auditor told to audit the committed SHA
  # would find no submission at all. UNCOMMITTED_SUBMIT is submitter-actionable and one `git add`
  # from fixed — do not confuse it with the verdict-side UNCOMMITTED emitted further down.
  if [ "$sub" -gt 0 ] && [ -n "$(undelivered "$a")" ]; then echo "UNCOMMITTED_SUBMIT $sub - -"; return; fi
  # Committed is not delivered. Checked immediately after UNCOMMITTED_SUBMIT and before any state
  # that would tell someone to act, because the auditor cannot see this file at all until it is
  # pushed. The `_SUBMIT` suffix is load-bearing: it separates "the submitter must push" from the
  # verdict-side states below, which mean "chase the other role". Answering the second to the first
  # leaves both sides waiting on each other, which is the whole failure this check exists to name.
  if [ "$sub" -gt 0 ] && [ -n "$(unpushed "$a")" ]; then echo "UNPUSHED_SUBMIT $sub - -"; return; fi
  # DEF300 — "no auditor file yet" is only AWAITING_AUDIT once something was actually submitted.
  # This fired unconditionally, so an architect file authored ahead of its evidence — the normal way
  # a SHA-pinned lane is written — woke the auditor for a lane with nothing in it. The two checks
  # directly above already guard on `sub -gt 0`; the omission here was an inconsistency inside one
  # function, not a considered choice, and the value it needed was computed two lines up and already
  # printed in the output. The cost is not the wasted poll: a false AWAITING_AUDIT teaches the
  # auditor that the signal does not mean what it says, which is DEF277/DEF290's failure in the
  # audit path instead of the promotion path.
  if [ ! -f "$u" ]; then
    [ "$sub" -gt 0 ] && echo "AWAITING_AUDIT $sub - -" || echo "DRAFT $sub - -"
    return
  fi
  # Same rule on the verdict side, so this table and the dispatch board cannot disagree about
  # whether a gate has been satisfied.
  if [ -n "$(undelivered "$u")" ]; then echo "UNCOMMITTED $sub - -"; return; fi
  if [ -n "$(unpushed "$u")" ]; then echo "UNPUSHED $sub - -"; return; fi
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
    # DEF300, second door into the same wrong state: an auditor file with no verdict and no
    # submission behind it. That combination is exactly what the false signal PRODUCES — the auditor
    # is woken, opens a file, finds nothing committed, and writes no verdict — so leaving this arm
    # unguarded would let the lane keep re-reporting itself as work forever.
    *)              [ "$sub" -gt 0 ] && echo "AWAITING_AUDIT $sub $vr -" || echo "DRAFT $sub $vr -" ;;
  esac
}

# --- watcher liveness -----------------------------------------------------------------------------
# A blocking watcher that DIES is indistinguishable from an empty queue: both produce silence, so the
# audit queue stops being served while every board still reads healthy. A running watcher therefore
# stamps a heartbeat each poll and REMOVES it on any clean exit (work found, or the -t timeout). A
# stamp left behind does not mean "a watcher is running" — it means "a watcher stopped without saying
# so", which is the only thing worth alarming on.
#
# Absence is deliberately NOT an alarm. An auditor spawned per item is told not to watch at all, so no
# heartbeat is the normal state under that model; alarming on it would be permanently red and would
# desensitise the one signal this exists to carry.
#
# TERM and KILL are deliberately NOT trapped: a watcher killed by a process teardown is exactly the
# failure being caught, and cleaning up on the way out would erase the evidence. INT is trapped
# because a human pressing ctrl-C already knows the watcher stopped.
hb_path() { echo "$CR_DIR/.watch-$1.hb"; }
hb_write() { printf '%s %s\n' "$(date +%s)" "$INTERVAL" > "$(hb_path "$1")" 2>/dev/null || true; }
hb_clear() { rm -f "$(hb_path "$1")" 2>/dev/null || true; }

hb_stale() {  # $1=mode; echoes "age limit" if a stamp exists and is too old, else nothing
  f=$(hb_path "$1"); [ -f "$f" ] || return 0
  read -r ts iv < "$f" 2>/dev/null || return 0
  case "${ts:-}" in ''|*[!0-9]*) return 0 ;; esac
  case "${iv:-}" in ''|*[!0-9]*) iv=30 ;; esac
  age=$(( $(date +%s) - ts ))
  # Three missed polls, floored so a fast poll interval cannot alarm on ordinary scheduling jitter.
  limit=$((iv * 3)); [ "$limit" -lt 90 ] && limit=90
  [ "$age" -gt "$limit" ] && echo "$age $limit"
  return 0
}

print_liveness() {  # loud line per mode whose watcher died; silent when none did
  for m in auditor architect; do
    set -- $(hb_stale "$m")
    [ -n "${1:-}" ] || continue
    printf '!! NO %s WATCHER — last poll %ss ago (limit %ss), and it never exited cleanly.\n' \
      "$(echo "$m" | tr 'a-z' 'A-Z')" "$1" "$2"
    echo "   Nothing is serving this queue. Restart it; the table above is still accurate."
  done
  return 0
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
  print_liveness
  # Explicit, and load-bearing: without it the bare `&&` above is the function's last statement, so
  # its status becomes the script's. A populated board makes that test FALSE and a correct table
  # exits 1 — the only exit 0 being the empty board, which is the one result a caller would least
  # want to read as success. The sibling dispatch.sh already returns 0 here; this closes the gap.
  return 0
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
  state) print_state; exit 0 ;;
  auditor|architect)
    [ "$MODE" = "auditor" ] && TARGET=AWAITING_AUDIT || TARGET=AWAITING_FIXES
    if [ "$TIMEOUT" -gt 0 ]; then
      echo "watching $CR_DIR for $TARGET (poll ${INTERVAL}s, give up after ${TIMEOUT}s)..."
    else
      echo "watching $CR_DIR for $TARGET (poll ${INTERVAL}s, ctrl-c to stop)..."
    fi
    elapsed=0
    trap 'hb_clear "$MODE"; exit 130' INT
    hb_write "$MODE"
    while :; do
      c=$(count_state "$TARGET")
      if [ "$c" -gt 0 ]; then
        hb_clear "$MODE"
        echo "$(date '+%H:%M:%S') $c lane(s) $TARGET:"; print_state; exit 0
      fi
      # A blocking watch is correct for a standing session and fatal for a one-shot: an agent
      # spawned per audit has no terminal to interrupt it, so an unbounded wait means it is
      # killed by its own harness with no verdict and no trace of why. -t bounds it and exits 3,
      # which a caller can tell apart from "found work" (0) and "bad usage" (2).
      if [ "$TIMEOUT" -gt 0 ] && [ "$elapsed" -ge "$TIMEOUT" ]; then
        hb_clear "$MODE"
        echo "no lane reached $TARGET within ${TIMEOUT}s — exiting rather than blocking." >&2
        exit 3
      fi
      sleep "$INTERVAL"
      elapsed=$((elapsed + INTERVAL))
      hb_write "$MODE"
    done ;;
  *) echo "usage: watcher.sh state | auditor [-i N] [-t N] | architect [-i N] [-t N]" >&2; exit 2 ;;
esac
