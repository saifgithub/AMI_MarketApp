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
#   UNPUSHED       : verdict committed but not on origin's default branch — the Architect's  <-- loud
#                    checkout cannot see it; chase the push, never merge
#   UNCOMMITTED_SUBMIT : YOUR OWN submission is not committed — the auditor cannot see it  <-- loud
#   UNPUSHED_SUBMIT    : YOUR OWN submission is committed but not on origin — same  <-- loud
#   BAD_ROUND      : VERDICT round > audit-lane SUBMITTED round — a mistyped stamp  <-- loud
#   DONE           : DISPATCH = ACCEPTED *and* the lane's GATE is satisfied
#   UNGATED        : DISPATCH = ACCEPTED but the gate is NOT satisfied  <-- loud
#
# DONE does not derive from DISPATCH: ACCEPTED alone: that is the Architect's own token, so reading
# it without a verdict cannot express "shipped without a gate" and prints ungated lanes identically
# to audited ones. UNGATED is that state.
#   GATE: none                -> no audit required; recorded UPFRONT at decomposition time, never
#                                at hand-off (the tired-at-hand-off window is where gates get waived)
#   GATE: spawned|independent -> requires audit VERDICT: COMPLETE, else UNGATED
#   GATE: absent              -> UNGATED. An unbound gate fails LOUD, never open.
# Usage:
#   dispatch.sh state              print the derived board once and exit
#   dispatch.sh inbox              one-shot, non-blocking: lanes the Architect must resolve before
#                                    taking new work — a finished verdict (AUDIT_PASSED,
#                                    UNCOMMITTED, UNPUSHED), an unreadable stamp (BAD_ROUND), or
#                                    THEIR OWN undelivered submission (UNCOMMITTED_SUBMIT,
#                                    UNPUSHED_SUBMIT). Also reports a DEAD audit watcher — a
#                                    heartbeat it never cleaned up, the one condition under which
#                                    every row can be right and nobody is reading them — and work
#                                    STRANDED on a lane branch (STRANDED_HANDOFF / STRANDED_BRIDGE,
#                                    DEF175): a finished lane whose hand-off or audit bridge never
#                                    reached this checkout is otherwise indistinguishable from a
#                                    lane that never started. Scoped to lanes not yet ACCEPTED.
#                                    Exit 1 if any. Run at session start + each work unit.
#   dispatch.sh verdict <ITEM>     print a lane's verdict, refusing if it is not yet delivered
#   dispatch.sh architect [-i N]   block until >=1 lane needs the Architect — every state in
#                                    needs_architect() below; keep that function the only list.
#   dispatch.sh inst <id> [-i N]   block until >=1 lane is ASSIGNED to <id> or AUDIT_RETURNED on it
# Env: DISPATCH_LANE_DIR overrides the lane dir (default <script dir>/lanes).
#      DISPATCH_AUDIT_DIR overrides the audit lane dir (default <script dir>/../audit/cr).
# Only lines that EMIT a token count as state (see TOK below); a line quoting one is prose.
# Portable POSIX sh, no dependencies. Sibling of orchestration/audit/watcher.sh.

set -u
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LANE_DIR=${DISPATCH_LANE_DIR:-"$SCRIPT_DIR/lanes"}
AUDIT_DIR=${DISPATCH_AUDIT_DIR:-"$SCRIPT_DIR/../audit/cr"}

# A token is machine state only on a line that EMITS it. Markdown emphasis and headings are
# formatting, so `**TOKEN:` and `## TOKEN:` still count; a backtick, a blockquote `>`, indentation,
# or any preceding word means the line is TALKING ABOUT the token. Without this filter a lane file
# that quotes the protocol sets its own state, and `tail -1` gives the last sentence the last word.
# Both watchers share this rule verbatim so the two boards cannot disagree about what a line means.
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
  # Evidence that lives only in one working tree is not evidence. These scripts read the working
  # tree, where an untracked file and a pushed one are otherwise indistinguishable — so an
  # uncommitted verdict would read as AUDIT_PASSED and authorise a merge to the shared branch.
  # Silent when git is unavailable or this is not a repo: the check may degrade, never fail
  # the caller.
  command -v git >/dev/null 2>&1 || { echo ""; return; }
  git -C "$(dirname -- "$1")" rev-parse --git-dir >/dev/null 2>&1 || { echo ""; return; }
  git -C "$(dirname -- "$1")" ls-files --error-unmatch -- "$1" >/dev/null 2>&1 || { echo "1"; return; }
  git -C "$(dirname -- "$1")" diff --quiet HEAD -- "$1" 2>/dev/null || { echo "1"; return; }
  echo ""
}

unpushed() {  # $1=file; echoes "1" if the file's newest commit is not on the shared remote branch
  # The gap AFTER `undelivered`, and not the same gap: a committed file still lives only in this
  # clone until it is pushed. Both roles reach each other through `origin`, so an unpushed verdict
  # is exactly as invisible to the Architect as an unpushed submission is to the auditor — and this
  # board would call it AUDIT_PASSED. The prose above already told you to "chase, then merge" and to
  # "commit and push" — but nothing checked it, and a claim in a comment is not a control.
  # Silent when git is unavailable, this is not a repo, or no remote branch resolves: degrade,
  # never fail the caller.
  command -v git >/dev/null 2>&1 || { echo ""; return; }
  d=$(dirname -- "$1")
  git -C "$d" rev-parse --git-dir >/dev/null 2>&1 || { echo ""; return; }
  rem=$(git -C "$d" symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null)
  [ -n "$rem" ] || rem=$(git -C "$d" rev-parse --verify --quiet origin/main >/dev/null 2>&1 && echo origin/main)
  [ -n "$rem" ] || { echo ""; return; }
  sha=$(git -C "$d" log -1 --format=%H -- "$1" 2>/dev/null)
  [ -n "$sha" ] || { echo ""; return; }
  # Local remote-tracking ref only — no fetch on a board read. For ordinary staleness the error
  # direction is the safe one: someone else's push can only over-report, costing a `git fetch`,
  # where under-reporting costs a lane that never gets audited.
  # That does NOT generalise to a rewritten remote, which is the one construction that under-reports:
  # rebase or force-push the commit off the remote and the local ref still holds the old sha, so
  # `--is-ancestor` passes and this reports delivered for a commit the remote no longer has — until
  # the next fetch. Narrow, since it requires rewriting shared history, but real.
  git -C "$d" merge-base --is-ancestor "$sha" "$rem" 2>/dev/null && { echo ""; return; }
  echo "1"
}

hb_stale() {  # $1=mode; echoes "age limit" if the audit watcher's heartbeat is stale, else nothing
  # Byte-identical twin of the same function in orchestration/audit/watcher.sh — keep them in step.
  # A running watcher stamps each poll and removes the stamp on any clean exit, so a stamp left
  # behind means it stopped without saying so. Absence is NOT an alarm: an auditor spawned per item
  # never watches, so no-heartbeat is normal under that model and alarming on it would be
  # permanently red.
  f="$AUDIT_DIR/.watch-$1.hb"; [ -f "$f" ] || return 0
  read -r ts iv < "$f" 2>/dev/null || return 0
  case "${ts:-}" in ''|*[!0-9]*) return 0 ;; esac
  case "${iv:-}" in ''|*[!0-9]*) iv=30 ;; esac
  age=$(( $(date +%s) - ts ))
  limit=$((iv * 3)); [ "$limit" -lt 90 ] && limit=90
  [ "$age" -gt "$limit" ] && echo "$age $limit"
  return 0
}

lane_state() {  # $1=item; echoes "STATE instance asg_round st_kw verdict gate"
  a="$LANE_DIR/$1.assign.md"
  asg_line=$(last_match "$a" 'ASSIGNED: *[A-Za-z0-9._-]+ *round *[0-9]+')
  # Read GATE before the UNASSIGNED return. A lane written at decomposition and not yet assigned is
  # exactly what the record-upfront rule produces; if the board skipped its gate it would print a
  # bare `-` whether GATE was recorded or forgotten. The rule says decide upfront, so the board has
  # to be able to show you did.
  gate_kw=$(last_kw "$a" 'GATE: *(independent|spawned|none)')

  if [ -z "$asg_line" ]; then echo "UNASSIGNED - - - - ${gate_kw:-MISSING}"; return; fi
  inst=$(echo "$asg_line" | awk '{print $2}')
  asg_round=$(echo "$asg_line" | grep -Eo '[0-9]+' | tail -1); asg_round=${asg_round:-0}

  u="$AUDIT_DIR/$1.auditor.md"
  s="$AUDIT_DIR/$1.architect.md"
  # The round a verdict answers is the SUBMITTED round in the audit lane beside it, not the instance
  # lane's STATUS round. They are separate counters kept by separate writers and the corpus shows
  # them drifting apart; comparing across the pair makes this board and watcher.sh disagree about
  # whose turn it is, which is the disagreement the round comparison was added to end.
  sub_round=$(last_round "$s" 'SUBMITTED: *round *[0-9]+')
  # The SUBMISSION side of the delivery question, checked before anything else can call this lane
  # in-flight. Guarding only the verdict below closes the MIRROR of the failure, not the failure:
  # this board is the ARCHITECT's, and the file the architect writes is `$s`. An unpushed
  # `SUBMITTED:` marker reads as an ordinary in-flight lane here while the auditor's clone does not
  # contain the lane at all — both roles behaving correctly, disagreeing, indefinitely.
  # Named apart from the verdict-side states deliberately: UNPUSHED means chase someone else, these
  # two mean push it yourself, and answering the first to the second is the mistake being prevented.
  # Placed ahead of the DISPATCH: ACCEPTED branch so this board and watcher.sh, which checks the same
  # file first, cannot disagree about whether the record has been delivered.
  if [ "${sub_round:-0}" -gt 0 ] && [ -n "$(undelivered "$s")" ]; then
    echo "UNCOMMITTED_SUBMIT $inst $asg_round - - ${gate_kw:-MISSING}"; return
  fi
  if [ "${sub_round:-0}" -gt 0 ] && [ -n "$(unpushed "$s")" ]; then
    echo "UNPUSHED_SUBMIT $inst $asg_round - - ${gate_kw:-MISSING}"; return
  fi
  # Read the verdict's ROUND, not just its keyword: a verdict only answers the submission at its own
  # round, so once a newer submission lands the old keyword is history.
  v_kw=$(last_kw "$u" 'VERDICT: *(COMPLETE|AWAITING_FIXES)')
  v_round=$(last_round "$u" 'VERDICT: *(COMPLETE|AWAITING_FIXES) *\(round *[0-9]+'); v_round=${v_round:-0}
  # A verdict nobody committed has not been delivered, so it cannot satisfy a gate. Render it as
  # its own loud state rather than letting it read as a pass — the same reason UNGATED exists.
  if [ -n "$v_kw" ] && [ -n "$(undelivered "$u")" ]; then v_kw="UNCOMMITTED"
  elif [ -n "$v_kw" ] && [ -n "$(unpushed "$u")" ]; then v_kw="UNPUSHED"; fi

  disp_kw=$(last_kw "$a" 'DISPATCH: *(OPEN|ACCEPTED)')
  if [ "$disp_kw" = "ACCEPTED" ]; then
    case "${gate_kw:-}" in
      none)                echo "DONE $inst $asg_round - ${v_kw:--} none" ;;
      spawned|independent)
        if [ "${v_kw:-}" = "COMPLETE" ]; then echo "DONE $inst $asg_round - $v_kw $gate_kw"
        else                                  echo "UNGATED $inst $asg_round - ${v_kw:--} $gate_kw"; fi ;;
      *)                   echo "UNGATED $inst $asg_round - ${v_kw:--} MISSING" ;;
    esac
    return
  fi

  i="$LANE_DIR/$1.$inst.md"
  st_kw=$(last_kw "$i" 'STATUS: *(CLAIMED|IN_PROGRESS|BLOCKED|NEEDS-INFO|READY_FOR_AUDIT|READY_FOR_REVIEW)')
  st_round=$(last_round "$i" 'STATUS: *(CLAIMED|IN_PROGRESS|BLOCKED|NEEDS-INFO|READY_FOR_AUDIT|READY_FOR_REVIEW) *\(round *[0-9]+'); st_round=${st_round:-0}

  g=${gate_kw:-MISSING}

  if [ ! -f "$i" ] || [ "$asg_round" -gt "$st_round" ]; then
    echo "ASSIGNED $inst $asg_round ${st_kw:--} - $g"; return
  fi

  case "${st_kw:-}" in
    CLAIMED|IN_PROGRESS) echo "IN_PROGRESS $inst $asg_round $st_kw - $g" ;;
    BLOCKED)             echo "BLOCKED $inst $asg_round $st_kw - $g" ;;
    NEEDS-INFO)          echo "NEEDS-INFO $inst $asg_round $st_kw - $g" ;;
    READY_FOR_REVIEW)    echo "IN_REVIEW $inst $asg_round $st_kw - $g" ;;
    READY_FOR_AUDIT)
      # No bridge file yet means no submission to compare against; fall back to the instance counter
      # rather than inventing a round the audit lane never recorded.
      sr=${sub_round:-$st_round}
      # A verdict can only answer a submission that exists. A verdict round ahead of the submission
      # round is a mistyped stamp, and the strict test below then reads the lane as already-answered
      # permanently: the builder fixes, bumps, resubmits, and the board still says AUDIT_RETURNED.
      # Nothing errors and nothing logs, so the lane just stops in a state that looks routine.
      if [ "$v_round" -gt "$sr" ]; then echo "BAD_ROUND $inst $asg_round $st_kw ${v_kw:--} $g"; return; fi
      # A submission newer than the last verdict is unanswered, whatever that verdict said.
      if [ "$sr" -gt "$v_round" ]; then echo "IN_AUDIT $inst $asg_round $st_kw - $g"; return; fi
      case "${v_kw:-}" in
        AWAITING_FIXES) echo "AUDIT_RETURNED $inst $asg_round $st_kw $v_kw $g" ;;
        COMPLETE)       echo "AUDIT_PASSED $inst $asg_round $st_kw $v_kw $g" ;;
        # A written-but-uncommitted verdict is its own state, not "still auditing". The auditor has
        # finished and the result exists in exactly one working tree; the fix is one `git add`, and
        # nobody can act on it until then. Architect-actionable: chase the delivery, never merge.
        UNCOMMITTED)    echo "UNCOMMITTED $inst $asg_round $st_kw $v_kw $g" ;;
        # Committed but unpushed: the verdict exists in the auditor's clone and nowhere this
        # Architect can reach. Same shape as UNCOMMITTED, one step further along, and equally
        # un-mergeable. Architect-actionable: chase the push (or `git fetch` first — a stale
        # remote-tracking ref reports this too, and that is the cheap direction to be wrong in).
        UNPUSHED)       echo "UNPUSHED $inst $asg_round $st_kw $v_kw $g" ;;
        *)              echo "IN_AUDIT $inst $asg_round $st_kw ${v_kw:--} $g" ;;
      esac ;;
    *) echo "ASSIGNED $inst $asg_round ${st_kw:--} - $g" ;;
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
  printf '%-14s %-16s %-16s %-5s %-18s %-9s %-12s\n' "ITEM" "STATE" "INSTANCE" "ASG" "STATUS" "VERDICT" "GATE"
  for it in $(items); do
    n=$((n+1))
    set -- $(lane_state "$it")
    printf '%-14s %-16s %-16s r%-4s %-18s %-9s %-12s\n' "$it" "$1" "$2" "$3" "$4" "$5" "$6"
  done
  [ "$n" -eq 0 ] && echo "(no lanes yet under $LANE_DIR)"
  return 0
}

# needs_architect: lane state is one the Architect must act on.
# UNGATED is included: an accepted lane whose gate is unsatisfied or unrecorded is a
# protocol breach the Architect must resolve — either route it to an auditor or record GATE: none.
needs_architect() {
  case "$1" in
    UNASSIGNED|BLOCKED|NEEDS-INFO|IN_REVIEW|AUDIT_PASSED|UNGATED|UNCOMMITTED|UNPUSHED|BAD_ROUND) return 0 ;;
    UNCOMMITTED_SUBMIT|UNPUSHED_SUBMIT) return 0 ;;
    *) return 1 ;;
  esac
}

# An audit lane with no assign file is an item its author executed directly, with no coder lane and
# so no `*.assign.md`. items() cannot see those, which means the whole state machine above never
# runs for them — yet their submission is exactly the one the author is responsible for delivering,
# and guarding only the lanes that happen to have an assign file would leave the self-executed case
# open for the same reason the verdict-only guard left the submission case open.
# Swept for the DELIVERY question ONLY. Rounds, verdicts and gates for these lanes stay off this
# board: a long-closed self-executed lane must not reappear here as unfinished business.
orphan_undelivered() {  # echoes "ITEM STATE" per undelivered orphan; nothing for the rest
  for f in "$AUDIT_DIR"/*.architect.md; do
    [ -f "$f" ] || continue
    it=$(basename "$f" .architect.md)
    [ -f "$LANE_DIR/$it.assign.md" ] && continue
    sr=$(last_round "$f" 'SUBMITTED: *round *[0-9]+')
    { [ -n "$sr" ] && [ "$sr" -gt 0 ]; } || continue
    if   [ -n "$(undelivered "$f")" ]; then echo "$it UNCOMMITTED_SUBMIT"
    elif [ -n "$(unpushed "$f")" ];    then echo "$it UNPUSHED_SUBMIT"; fi
  done
}

# The mirror of the above, and the one it left open (AT:R66, 2026-08-08).
#
# orphan_undelivered() asks "did MY submission reach the auditor?". Nothing asked the converse —
# "did the auditor answer, and have I acted on it?" — for a self-executed lane. Measured cost: a
# DEF231 round-2 verdict returned a MAJOR thirteen minutes after the submission was pushed; the
# architect promoted off the submission without reading it and left a reproducible false annotation
# on the live Verdict Board for seven hours. `inbox` was run and said "clear", because this lane has
# no *.assign.md and so never entered the state machine that would have called it AUDIT_RETURNED.
#
# Scoped to AWAITING_FIXES at the CURRENT submitted round, which is the only state that means
# "somebody is waiting on you and nothing else will move until you answer". Deliberately NOT
# COMPLETE: a passed lane is finished business, and surfacing it here would resurrect every
# long-closed self-executed item and desensitise the whole board — the concern the comment above
# already names. A verdict at an OLDER round has been superseded by a newer submission and is not
# owed. A verdict at a NEWER round is BAD_ROUND, which nobody can act on and which must be loud.
orphan_unanswered_verdict() {  # echoes "ITEM STATE" per self-executed lane awaiting the architect
  for f in "$AUDIT_DIR"/*.architect.md; do
    [ -f "$f" ] || continue
    it=$(basename "$f" .architect.md)
    [ -f "$LANE_DIR/$it.assign.md" ] && continue
    u="$AUDIT_DIR/$it.auditor.md"
    [ -f "$u" ] || continue
    sr=$(last_round "$f" 'SUBMITTED: *round *[0-9]+'); sr=${sr:-0}
    v_kw=$(last_kw "$u" 'VERDICT: *(COMPLETE|AWAITING_FIXES)')
    v_round=$(last_round "$u" 'VERDICT: *(COMPLETE|AWAITING_FIXES) *\(round *[0-9]+'); v_round=${v_round:-0}
    # A verdict the auditor has written but not committed is the FRESHEST one there
    # is, and skipping it blinds this check at exactly the moment it matters most —
    # found within minutes of shipping the first version, when a CR124 round-4
    # COMPLETE sat uncommitted in the working tree and `inbox` reported clear.
    # Same treatment the assigned-lane machine already gives it: UNCOMMITTED is hot,
    # "chase, then merge". Verdict-bearing only; an uncommitted file with no VERDICT
    # line is someone mid-write, not a verdict owed.
    if [ -n "$(undelivered "$u")" ]; then
      [ -n "$v_kw" ] && echo "$it UNCOMMITTED"
      continue
    fi
    if [ "$v_round" -gt "$sr" ]; then echo "$it BAD_ROUND"
    elif [ "$v_round" -eq "$sr" ] && [ "$v_round" -gt 0 ] && [ "$v_kw" = "AWAITING_FIXES" ]; then
      echo "$it AUDIT_RETURNED"
    fi
  done
}

# DEF175 — a finished lane and an invisible lane look identical from `main`.
#
# Every state above is derived from files in THIS checkout. A coder works in its own worktree on
# `lane/<ITEM>.<instance>` — correctly; that isolation is what CR052 rests on — and writes its
# hand-off and its §6 audit bridge THERE. Nothing transports them. So a complete, self-verified,
# pushed lane sits one branch away reading as ASSIGNED-with-no-status, and the independent gate
# never fires because the queue it reads from is empty. The failure state is SILENCE, and silence
# is also what an unstarted lane looks like — which is why this escaped notice three times (CR120,
# DEF142 `d5ac6614`, CR112 `eab8470f`) and was hand-delivered by the Architect each time.
#
# This is the guard `failure_patterns.md` asked for on occurrence two. It reads the lane branches
# directly, so a hand-off that exists ONLY on a branch is loud instead of invisible.
#
# Scans local `lane/*` AND `origin/lane/*`: a worker on this machine may not have pushed yet, and a
# worker elsewhere shows up only on origin. Refs can be stale — `git fetch` before trusting a clean
# result on a lane built off this box.
#
# SCOPED TO IN-FLIGHT LANES, deliberately. An ACCEPTED lane whose hand-off never reached `main` is
# history: the work is integrated, and the only thing left on the branch is the paperwork. Measured
# on the first run of this guard, the unscoped version reported CR087-BE, CR087-MOBILE and DEF114 —
# all three long since merged and closed. Those rows would be permanently red and never actionable,
# which is precisely the desensitisation print_inbox's own comment warns about: a chronic backlog
# teaches the reader to skip the section that exists to catch two rare events.
#
# KNOWN LIMIT: a lane with no `*.assign.md` (self-executed, no coder lane) is not scanned here. Its
# delivery question is already swept by orphan_undelivered() for the audit bridge, and its author is
# by definition the one holding the file locally. If self-executed lanes ever start being run by
# someone other than their author, this is the line to revisit.
# PERFORMANCE, because this runs on every work unit: a `git show` per candidate path cost ~130ms on
# this repo (large history, external volume), so the obvious loop spent ~11s on top of the board's
# own ~9s and would have been switched off within a day. Existence is resolved for every candidate
# in ONE `git cat-file --batch-check`, and content is read only for the handful that exist.
stranded_on_lane_branches() {  # echoes "ITEM WHAT" per lane branch carrying work `main` lacks
  command -v git >/dev/null 2>&1 || return 0
  git rev-parse --git-dir >/dev/null 2>&1 || return 0

  # Build every candidate as "<ref>:<path> <item>|<kind>|<lane>". batch-check echoes %(rest) for an
  # object that exists and prints "<input-up-to-first-space> missing" for one that does not, so the
  # tag after the space is how a hit is identified without a second lookup.
  probes=$(
    # One ref per LANE, not per ref: a lane that exists both locally and on origin would otherwise
    # be walked twice, doubling the grep cost for an identical answer. Heads are listed first, so
    # keeping the first occurrence prefers the local ref — which is the fresher one for a lane built
    # on this box, and the only one that exists before the worker pushes.
    { git for-each-ref --format='%(refname:short)' refs/heads/lane/ 2>/dev/null
      git for-each-ref --format='%(refname:short)' refs/remotes/origin/lane/ 2>/dev/null
    } | awk '{ l=$0; sub(/^origin\//,"",l); sub(/^lane\//,"",l);
               if (!(l in seen)) { seen[l]=1; print } }' | while IFS= read -r br; do
      ref="$br"
      lane=${br#origin/}      # remotes arrive as `origin/lane/<ITEM>.<instance>`
      lane=${lane#lane/}
      it=${lane%%.*}          # ITEM never contains a dot; the instance (`coder.api`) does
      [ -n "$it" ] || continue

      # Cheap file tests BEFORE emitting a probe — the filter that keeps this affordable.
      [ -f "$LANE_DIR/$it.assign.md" ] || continue
      [ -n "$(emits "$LANE_DIR/$it.assign.md" 'DISPATCH: *ACCEPTED')" ] && continue

      # The hand-off filename is `<ITEM>.<instance>.md`, and the instance comes from the ASSIGN
      # file — NOT from the branch name. Measured 2026-07-30: the BE-TRUST worker pushed
      # `lane/BE-TRUST` instead of `lane/BE-TRUST.coder.api`, and the first version of this guard
      # skipped any branch without a dot outright — so a lane that named its branch loosely became
      # invisible to the check written to stop lanes being invisible. Deriving from the assign also
      # survives a worker that renames its branch for any other reason.
      inst=$(last_match "$LANE_DIR/$it.assign.md" 'INSTANCE: *[A-Za-z0-9_.-]+' | sed 's/^INSTANCE: *//')
      [ -n "$inst" ] || inst=${lane#"$it."}
      lane="$it.$inst"

      # Only probe for what this checkout is actually missing. A lane whose hand-off is already on
      # `main` is the normal, healthy case and needs no object lookup at all.
      [ -z "$(emits "$LANE_DIR/$lane.md" 'STATUS: *READY_FOR_')" ] &&
        printf '%s:orchestration/dispatch/lanes/%s.md %s|handoff\n' "$ref" "$lane" "$it"
      [ -z "$(emits "$AUDIT_DIR/$it.architect.md" 'SUBMITTED: *round *[0-9]+')" ] &&
        printf '%s:orchestration/audit/cr/%s.architect.md %s|bridge\n' "$ref" "$it" "$it"
    done
  )
  [ -n "$probes" ] || return 0

  hits=$(printf '%s\n' "$probes" | git cat-file --batch-check='%(objectname) %(rest)' 2>/dev/null \
           | grep -v ' missing$')
  [ -n "$hits" ] || return 0

  # Dedupe per item: the same lane present both locally and on origin yields two identical hits, and
  # one lane must not produce two rows.
  seen=""
  while read -r oid tag; do
    [ -n "${oid:-}" ] || continue
    it=${tag%%|*}
    kind=${tag##*|}
    case " $seen " in *" $it "*) continue ;; esac

    # Only now read content, and only for objects that exist. A file can be present on the branch
    # without carrying the token — an in-progress hand-off is not a stranded one.
    case "$kind" in
      handoff)
        git cat-file -p "$oid" 2>/dev/null | grep -qE "${TOK}STATUS: *READY_FOR_" || continue
        seen="$seen $it"
        echo "$it STRANDED_HANDOFF" ;;
      bridge)
        git cat-file -p "$oid" 2>/dev/null | grep -qE "${TOK}SUBMITTED: *round *[0-9]+" || continue
        seen="$seen $it"
        echo "$it STRANDED_BRIDGE" ;;
    esac
  done <<EOF
$hits
EOF
}

count_architect() {
  c=0
  for it in $(items); do
    st=$(lane_state "$it"); s=${st%% *}
    needs_architect "$s" && c=$((c+1))
  done
  o=$(orphan_undelivered | grep -c . 2>/dev/null || echo 0)
  echo $((c + o))
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

print_inbox() {
  # Exit 1 on AUDIT_PASSED (merge it), UNCOMMITTED (verdict uncommitted — chase, then merge),
  # UNPUSHED (committed but not on origin — chase the push; `git fetch` first, the ref may be stale),
  # BAD_ROUND (a stamp nobody can act on — repair it), or either *_SUBMIT state (your own submission
  # never reached the auditor — push it, and do not sit waiting for a verdict on it), so a caller can
  # gate "take new work" on a clean inbox. Other Architect-owed states go on one trailer line and DO
  # NOT affect the exit code: a chronic backlog would otherwise keep this permanently red and
  # desensitise it to the two events it exists to catch — a fresh auditor verdict, and a submission
  # of your own that never reached the auditor.
  hot=0; other=0; hot_rows=""
  for it in $(items); do
    set -- $(lane_state "$it")
    case "$1" in
      AUDIT_PASSED|UNCOMMITTED|UNPUSHED|BAD_ROUND|UNCOMMITTED_SUBMIT|UNPUSHED_SUBMIT)
        hot=$((hot+1))
        row=$(printf '  %-14s %-13s %-16s verdict=%s' "$it" "$1" "$2" "$5")
        hot_rows="${hot_rows}${row}
"
        ;;
      UNASSIGNED|BLOCKED|NEEDS-INFO|IN_REVIEW|UNGATED) other=$((other+1)) ;;
    esac
  done
  # Self-executed lanes, which items() above cannot enumerate. Fed through a heredoc rather than a
  # pipe so the counter survives: a `while` on the right of a pipe runs in a subshell and its
  # increments are discarded, which would show the rows and still exit 0.
  orph=$(orphan_undelivered)
  if [ -n "$orph" ]; then
    while read -r oit ost; do
      [ -n "$oit" ] || continue
      hot=$((hot+1))
      row=$(printf '  %-14s %-13s %-16s verdict=%s' "$oit" "$ost" "(self-executed)" "-")
      hot_rows="${hot_rows}${row}
"
    done <<EOF
$orph
EOF
  fi
  # AT:R66 — a self-executed lane whose auditor answered and whose architect has not. Same
  # heredoc-not-pipe reason as above: increments on the right of a pipe run in a subshell and are
  # discarded, which would print the rows and still exit 0 — the silent pass this guard removes.
  unanswered=$(orphan_unanswered_verdict)
  if [ -n "$unanswered" ]; then
    while read -r uit ust; do
      [ -n "$uit" ] || continue
      hot=$((hot+1))
      row=$(printf '  %-14s %-13s %-16s verdict=%s' "$uit" "$ust" "(self-executed)" "see lane file")
      hot_rows="${hot_rows}${row}
"
    done <<EOF
$unanswered
EOF
  fi
  # DEF175 — work that exists only on a lane branch. Same heredoc-not-pipe reason as above: a
  # `while` on the right of a pipe runs in a subshell and its increments are discarded, which would
  # print the rows and still exit 0 — the exact silent-pass this guard exists to remove.
  strand=$(stranded_on_lane_branches)
  if [ -n "$strand" ]; then
    while read -r sit swhat; do
      [ -n "$sit" ] || continue
      hot=$((hot+1))
      row=$(printf '  %-14s %-13s %-16s verdict=%s' "$sit" "$swhat" "(on lane branch)" "-")
      hot_rows="${hot_rows}${row}
"
    done <<EOF
$strand
EOF
  fi
  # A watcher that DIED is not a lane, so it cannot appear in the rows above — and it is the one
  # condition under which every row above can be correct and still nobody is reading them.
  dead=0
  for m in auditor architect; do
    set -- $(hb_stale "$m")
    [ -n "${1:-}" ] || continue
    dead=$((dead+1))
    echo "!! NO $(echo "$m" | tr 'a-z' 'A-Z') WATCHER — last poll $1s ago (limit $2s), never exited cleanly."
    echo "   Nothing is serving that queue: a lane can sit waiting indefinitely while every board"
    echo "   reads healthy. Restart it before you submit anything else."
  done
  if [ "$hot" -gt 0 ]; then
    # Not "AUDITOR DONE": the *_SUBMIT states are the Architect's OWN undelivered work, and a heading
    # naming the auditor teaches exactly the misattribution these states exist to prevent.
    echo "RESOLVE BEFORE TAKING NEW WORK ($hot):"
    printf '%s' "$hot_rows"
  else
    echo "inbox clear — no verdict awaiting integration, no submission of yours undelivered."
  fi
  [ "$other" -gt 0 ] && echo "(also owing you: $other lane(s) UNASSIGNED/BLOCKED/NEEDS-INFO/IN_REVIEW/UNGATED — full board: dispatch.sh state)"
  # DEF277 — two different failures, two different exit codes.
  #
  # `hot` and `dead` used to share `return 1`, so a promotion gate reading only
  # "did inbox succeed" aborted on an IDLE AUDIT FLEET. That is the normal state
  # whenever nobody is running an audit, and a gate that fires when nothing is
  # wrong teaches the operator that firing does not mean stop — which is exactly
  # what happened: `alpha-2026-08-13-1` shipped past this gate on 2026-08-13
  # with `hot=0` and this function printing "inbox clear" on the same run.
  #
  #   1 — a verdict awaits integration, or a submission of yours never reached
  #       the auditor. Your code may already be known-broken. STOP.
  #   2 — no watcher is serving the queue. Do not SUBMIT (it would sit unread);
  #       shipping already-audited code is unaffected.
  #
  # Callers that must refuse both keep testing `if ! dispatch.sh inbox`, which is
  # unchanged for them — every non-zero still means something. Only a caller that
  # cares about the difference has to look, and `/promote-to-alpha` is the one
  # that does.
  [ "$hot" -gt 0 ] && return 1
  [ "$dead" -gt 0 ] && return 2
  return 0
}

print_verdict() {  # $1=item; print the verdict ONLY once it has been delivered
  # An .auditor.md in the working tree may be mid-write: the auditor is still reasoning, and the
  # round number and the findings can both still change. Reading it directly and acting on what it
  # says is how an undelivered verdict becomes a dispatched instruction. This is the accessor that
  # can say no. It does not stop anyone opening the file — it makes the checked read the easy one,
  # and the board state it prints is the same one every other mode derives.
  u="$AUDIT_DIR/$1.auditor.md"
  [ -f "$u" ] || { echo "no verdict file for $1 ($u)" >&2; return 1; }
  if [ -n "$(undelivered "$u")" ]; then
    echo "UNDELIVERED — $1's verdict exists only in this working tree. Do not quote it, dispatch on" >&2
    echo "it, or merge on it: it is still being written. Chase the auditor to commit and push." >&2
    return 1
  fi
  kw=$(last_kw "$u" 'VERDICT: *(COMPLETE|AWAITING_FIXES)')
  [ -n "$kw" ] || { echo "no VERDICT line in $u" >&2; return 1; }
  vr=$(last_round "$u" 'VERDICT: *(COMPLETE|AWAITING_FIXES) *\(round *[0-9]+')
  echo "$1  VERDICT: $kw (round ${vr:-?})  [delivered]"
  return 0
}

MODE=${1:-state}; shift 2>/dev/null || true

case "$MODE" in
  state) print_state; exit 0 ;;
  inbox) print_inbox; exit $? ;;
  verdict)
    ITEM=${1:-}
    [ -z "$ITEM" ] && { echo "usage: dispatch.sh verdict <ITEM>" >&2; exit 2; }
    print_verdict "$ITEM"; exit $? ;;
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
  *) echo "usage: dispatch.sh state | inbox | verdict <ITEM> | architect [-i N] | inst <id> [-i N]" >&2; exit 2 ;;
esac
