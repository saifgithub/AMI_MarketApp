#!/bin/sh
# dispatch_verify.sh — mechanical ground-truth checks on the current HEAD (CR061).
#
# WHY: every completed lane, the Architect hand-runs the same checks (a worker's "done/green/pushed"
# prose AND its STATUS token are claims, not evidence — economy=Haiku fabricates completion). This
# scripts the MECHANICAL half so it is fast + consistent. It does NOT replace the Architect's
# content read (voice, P2 numbers, quality) — only the mechanical gate.
#
# USAGE:  sh orchestration/dispatch/dispatch_verify.sh [<expected-file-glob> <expected-count>]
#   e.g.  sh orchestration/dispatch/dispatch_verify.sh 'content/lessons/34[7-9]_*.en.mdx' 3
# Exit 0 = all checks pass; non-zero = at least one failed (details printed).
set -u
cd "$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "FAIL: not in a git repo"; exit 2; }
fail=0

# 1. origin sync — HEAD must equal origin/main (the worker pushed).
git fetch -q origin main 2>/dev/null || true
LH=$(git rev-parse HEAD); RH=$(git rev-parse origin/main 2>/dev/null || echo none)
if [ "$LH" = "$RH" ]; then echo "PASS origin-sync ($LH)"; else echo "FAIL origin-sync: HEAD=$LH origin/main=$RH"; fail=1; fi

# 2. forbidden files must NOT appear in the HEAD commit.
FILES=$(git show --name-only --format= HEAD | sed '/^$/d')
FORBIDDEN=$(printf '%s\n' "$FILES" | grep -E 'uv\.lock|settings\.local\.json|Archive\.zip|(^|/)roster/' || true)
if [ -z "$FORBIDDEN" ]; then echo "PASS no-forbidden-files"; else echo "FAIL forbidden files in HEAD:"; printf '  %s\n' $FORBIDDEN; fail=1; fi

# 3. optional: exactly N files matching the glob in the HEAD commit.
if [ "$#" -ge 2 ]; then
  GLOB=$1; WANT=$2; GOT=0
  for f in $FILES; do
    case "$f" in
      $GLOB) GOT=$((GOT + 1)) ;;
    esac
  done
  if [ "$GOT" = "$WANT" ]; then echo "PASS file-count ($GOT match '$GLOB')"; else echo "FAIL file-count: want $WANT got $GOT for '$GLOB'"; fail=1; fi
fi

# 4. corpus-integrity exit code (fast — ~6s; NOT the full suite).
( cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py -q >/tmp/dv_corpus.log 2>&1 )
cec=$?
if [ "$cec" = "0" ]; then echo "PASS corpus-integrity (exit 0)"; else echo "FAIL corpus-integrity (exit $cec) — see /tmp/dv_corpus.log"; tail -3 /tmp/dv_corpus.log; fail=1; fi

[ "$fail" = "0" ] && echo "== VERIFY PASS ==" || echo "== VERIFY FAIL =="
exit $fail
