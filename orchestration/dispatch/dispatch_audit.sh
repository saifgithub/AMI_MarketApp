#!/bin/sh
# dispatch_audit.sh — templatized auditor.core launch (CR061).
#
# WHY: every code lane's audit was hand-bridged (I re-typed the same preamble each time: read
# AUDITOR.md, verify the SHA in a clean tree, run the full suite SAFELY, write the verdict, clean up).
# This encodes that boilerplate once; the caller supplies only the lane, the SHA, and the
# lane-specific verification criteria. It execs dispatch_launch.sh (premium tier — the auditor gate).
#
# USAGE (launch with the Bash tool run_in_background:true, NO trailing &):
#   sh orchestration/dispatch/dispatch_audit.sh <lane> <sha> "<lane-specific criteria + any blind probe>"
set -u
if [ $# -lt 3 ]; then
  echo "usage: dispatch_audit.sh <lane> <sha> \"<verification criteria>\"" >&2; exit 2
fi
LANE=$1; SHA=$2; shift 2; CRITERIA=$*
HERE=$(dirname "$0")

BODY="You are auditor.core, the independent verification gate, as a headless one-shot claude -p session in the MAIN repo. The working tree is clean at HEAD = $SHA (the SHA under audit). You do NOT modify product code; you verify and issue a verdict. First READ CLAUDE.md and orchestration/dispatch/loop_prompts/AUDITOR.md, then review the diff:  git show $SHA.

VERIFY (lane $LANE): $CRITERIA

RUN THE FULL SUITE SAFELY — it is ~828s, LONGER than the 600s max Bash timeout, so it can NEVER finish in one foreground call and would auto-background and kill you (P7). Do this instead: launch  sh orchestration/dispatch/run_full_suite.sh  with the Bash tool run_in_background:true (NO trailing &), then POLL its output file until the line  SUITE_EXIT=<code>  appears; read that code (do NOT infer pass/fail from pytest's progress dots). Expect SUITE_EXIT=0. If you run any blind probe, create the probe file, run ONLY the fast corpus test (cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py -q) to confirm it fails as required, then DELETE the probe and re-run to confirm green — never leave a probe in the tree and never run a probe concurrently with the full suite.

CLEAN UP: git status --porcelain must show only your verdict lane before you commit. NEVER commit a probe file, backend/uv.lock, .claude/settings.local.json, Archive.zip, or a roster file.

VERDICT: write orchestration/dispatch/lanes/$LANE.audit.md with, byte-exact at line start,  VERDICT: COMPLETE (round 1)  if everything holds, else  VERDICT: AWAITING_FIXES (round 1)  with a numbered list of exactly what failed. Include the full-suite pass count + SUITE_EXIT and any blind-probe result. Stage ONLY that lane file by name, commit -m starting  chore(audit): $LANE verdict (AT:auditor.core $LANE) , git pull --rebase --autostash origin main, git push origin main, print the pushed SHA. Then STOP."

exec sh "$HERE/dispatch_launch.sh" auditor.core "$LANE" premium solo "$BODY"
