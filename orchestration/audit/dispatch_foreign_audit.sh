#!/bin/sh
# dispatch_foreign_audit.sh — foreign (non-Claude) advisory audit of a committed SHA (CR215).
#
# WHY: every audit this project has run was Claude auditing Claude. That gate cannot see a
# CORRELATED ERROR — a defect the builder and the auditor both miss because they share a model
# family. CR057 named this gap and deferred it ("our auditor.core is same-family Claude today").
# This closes it with kimi-code/k3 (Moonshot), the foreign harness from the heritage MHBP design.
#
# ADVISORY, NEVER BINDING. MHBP invariant 2: the foreign tier is additive insurance, never a
# replacement verifier. The Claude auditor's `VERDICT:` on orchestration/audit/cr/<ITEM>.auditor.md
# stays the only thing the dispatch board honours. Kimi writes `FOREIGN-VERDICT:` — a token no
# watcher parses — into a file no watcher reads, on a branch that never reaches main. Three
# independent reasons it cannot move the gate; see FOREIGN_AUDIT.md.
#
# WHY KIMI HOLDS ITS OWN PEN: MHBP §1.3 has the architect write the foreign finding on a tool-less
# model's behalf. That collides with ARCHITECT_LOOP_PROMPT.md:137-142 — "The auditor writes and
# pushes its own verdict. You never transcribe it... an inconvenient verdict is one edit away from
# never existing." Kimi Code is a HARNESS (MHBP §1.2): it reads the diff itself and commits its own
# file, so nothing passes through the architect's hands.
#
# USAGE (launch with the Bash tool run_in_background:true, NO trailing &):
#   sh orchestration/audit/dispatch_foreign_audit.sh <ITEM> <sha> <round> "<lane-specific criteria>"
#
# Env: FOREIGN_TIMEOUT_S  wall-clock cap on the harness (default 900)
#      FOREIGN_PUSH=1  also push the branch to origin (default: local commit only — the commit is
#      already tamper-evident, and advisory branches are not worth publishing by default).
# Exit: 0 findings produced · 2 bad usage · 3 foreign tier UNAVAILABLE (recorded, never silent)
set -eu

if [ $# -lt 3 ]; then
  echo "usage: dispatch_foreign_audit.sh <ITEM> <sha> <round> [\"criteria\"]" >&2; exit 2
fi
ITEM=$1; SHA=$2; ROUND=$3; shift 3; CRITERIA=${*:-"no lane-specific criteria supplied"}

REPO=$(cd "$(dirname "$0")/../.." && pwd)
KIMI_BIN="${AMI_KIMI_BIN:-$HOME/.kimi-code/bin/kimi}"
AGENT_FILE="$REPO/orchestration/audit/foreign/AUDITOR_AGENT.md"
LEDGER="$REPO/orchestration/audit/foreign_trail.md"
BRANCH="foreign/$ITEM.r$ROUND"
WORKTREE="$REPO/.claude/worktrees/foreign-$ITEM-r$ROUND"
REL_OUT="orchestration/audit/foreign/$ITEM.r$ROUND.foreign.md"

# Record unavailability rather than exiting quietly. DEF059: a gate that fails silently manufactures
# false confidence — the absence of foreign findings must never read as "the foreign tier was happy".
unavailable() {
  printf '| %s | %s | %s | r%s | auditor | — | — | UNAVAILABLE: %s |\n' \
    "$(date -u +%Y-%m-%d)" "$ITEM" "$SHA" "$ROUND" "$1" >> "$LEDGER"
  echo "FOREIGN: unavailable ($1) — recorded in $LEDGER" >&2
  exit 3
}

[ -x "$KIMI_BIN" ] || unavailable "kimi not executable at $KIMI_BIN"
[ -f "$AGENT_FILE" ] || unavailable "agent file missing: $AGENT_FILE"
git -C "$REPO" cat-file -e "$SHA^{commit}" 2>/dev/null || { echo "FATAL: no such commit: $SHA" >&2; exit 2; }

# --- Invariant 1: decorrelation is the MODEL FAMILY, not the tool ------------------------------
# "An audit run on a Claude model is void — same family again, regardless of which tool ran it."
MODEL=$("$KIMI_BIN" provider list 2>/dev/null | sed -n 's/^Default model: *//p' | head -1) \
  || unavailable "kimi provider list failed"
[ -n "$MODEL" ] || unavailable "no default model configured in the auditor home"
case "$MODEL" in
  kimi-code/*) : ;;
  *claude*|*Claude*|*anthropic*) unavailable "VOID — resolved model '$MODEL' is same-family Claude (invariant 1)" ;;
  *) unavailable "resolved model '$MODEL' is not a kimi-code model; refusing to claim a foreign audit" ;;
esac

# --- Invariant 5: read-only / isolated ---------------------------------------------------------
# MHBP invariant 5 exists because an unscoped foreign harness silently edited 4 files in its first
# run. Here every write it can make is confined to a throwaway branch, and checked below.
git -C "$REPO" worktree remove --force "$WORKTREE" 2>/dev/null || true
git -C "$REPO" branch -D "$BRANCH" 2>/dev/null || true
git -C "$REPO" worktree add -q -b "$BRANCH" "$WORKTREE" "$SHA"

BRIEF="You are the foreign auditor for AMI Trade. Read your role file first: $AGENT_FILE

You are in a clean worktree at $WORKTREE, checked out at the SHA under audit. Review the change:
  git show $SHA

ITEM: $ITEM   ROUND: $ROUND   SHA: $SHA

LANE-SPECIFIC CRITERIA: $CRITERIA

Write your findings to $REL_OUT (mkdir -p its directory first), in the format your role file
specifies. Then: git add $REL_OUT and ONLY that path, git commit -m 'audit(foreign): $ITEM r$ROUND advisory findings', and STOP. Do not push. Do not modify any other file. Do not run the test suite."

echo "==> foreign audit: $ITEM r$ROUND @ $SHA  model=$MODEL"
# `kimi -p` does not reliably exit once it has finished (verified 2026-09-01: it wrote its file
# correctly, then sat). The watchdog caps it; 124 means "capped", not "failed" — whether the run
# succeeded is decided below by what it actually committed, never by its exit code.
KRC=0
( cd "$WORKTREE" && python3 "$REPO/orchestration/harness/run_timeout.py" "${FOREIGN_TIMEOUT_S:-900}" \
    "$KIMI_BIN" -p "$BRIEF" ) || KRC=$?

# --- Machine-verify, never trust (BINDINGS.md:121) ---------------------------------------------
# "A worker's 'done / pushed / green' prose AND its STATUS token are claims, not evidence."
if [ "$(git -C "$REPO" rev-parse "$BRANCH")" = "$(git -C "$REPO" rev-parse "$SHA")" ]; then
  git -C "$REPO" worktree remove --force "$WORKTREE" 2>/dev/null || true
  if [ "$KRC" -eq 124 ]; then unavailable "kimi hit the ${FOREIGN_TIMEOUT_S:-900}s cap without committing"; fi
  if [ "$KRC" -ne 0 ]; then unavailable "kimi exited $KRC without committing"; fi
  unavailable "the foreign auditor committed nothing"
fi
TOUCHED=$(git -C "$REPO" show --name-only --format= "$BRANCH" | grep -v '^$' || true)
if [ "$TOUCHED" != "$REL_OUT" ]; then
  echo "QUARANTINED: branch $BRANCH touched paths other than its findings file:" >&2
  echo "$TOUCHED" >&2
  echo "Not reading it. Inspect by hand, then: git branch -D $BRANCH" >&2
  git -C "$REPO" worktree remove --force "$WORKTREE" 2>/dev/null || true
  exit 3
fi

# Structural backstop for the one hard rule. Prompt instructions are not controls (CLAUDE.md), so
# the token is checked, not merely requested. Mirrors the board's own parse:
#   dispatch.sh:62  TOK='^(#{1,6} )?\*{0,2}'  +  VERDICT: *(COMPLETE|AWAITING_FIXES)
if git -C "$REPO" show "$BRANCH:$REL_OUT" | grep -qE '^(#{1,6} )?\*{0,2}VERDICT: *(COMPLETE|AWAITING_FIXES)'; then
  echo "QUARANTINED: findings file emits a board-parseable VERDICT: token. Advisory output must not." >&2
  git -C "$REPO" worktree remove --force "$WORKTREE" 2>/dev/null || true
  exit 3
fi

FV=$(git -C "$REPO" show "$BRANCH:$REL_OUT" | sed -n 's/^FOREIGN-VERDICT: *//p' | head -1)
N_FIND=$(git -C "$REPO" show "$BRANCH:$REL_OUT" | grep -cE '^### \[(blocking|question|noted)\]' || true)
printf '| %s | %s | %s | r%s | auditor | %s | %s | %s findings, dispositions pending |\n' \
  "$(date -u +%Y-%m-%d)" "$ITEM" "$SHA" "$ROUND" "$MODEL" "${FV:-none}" "$N_FIND" >> "$LEDGER"

# Explicit `if`, not `[ ... ] && cmd`: under `set -e` the && form makes the script's exit status
# depend on whether the flag happened to be set, which is not what "optionally push" should mean.
if [ "${FOREIGN_PUSH:-0}" = "1" ]; then
  git -C "$REPO" push -q origin "$BRANCH"
fi

git -C "$REPO" worktree remove --force "$WORKTREE" 2>/dev/null || true
echo
echo "branch:   $BRANCH   (read with: git show $BRANCH:$REL_OUT)"
echo "model:    $MODEL"
echo "findings: $N_FIND   FOREIGN-VERDICT: ${FV:-none}"
echo "The Claude auditor must now disposition each finding real/false-divergence/noise."
