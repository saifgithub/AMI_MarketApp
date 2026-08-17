#!/usr/bin/env bash
# Preflight suite gate — does the backend suite EXIT 0? (DEF326)
#
# `/promote-to-alpha` step 1 said "pytest must exit 0. Surface the failure
# summary if not." and then ran `pytest backend/tests/unit/ -q` inline, leaving
# the operator to judge. On 2026-08-15 an autouse ledger invariant began raising
# in TEARDOWN on 54 CR109 games tests. pytest counts errors separately from
# failures, so the last line the operator reads is:
#
#     4324 passed, 3 skipped, 54 errors
#
# — and the word "failed" never appears in it. `alpha-2026-08-17-1` was promoted
# past that gate two days later, by an operator (me) who read the pass count and
# not the exit code.
#
# Same shape as the tree gate and the audit-lane gate beside it: a check whose
# failing state is invisible in the output a human actually reads is not a gate.
# So this script does the reading. It ends in one VERDICT line that says the
# word PASS or FAIL, and in an exit code, and it counts errors as failure
# because they are one.
#
# Exit 0 suite green · 1 suite not green · 2 could not run.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || exit 2

# An array, not a string: the repo lives under `/Volumes/Extreme Pro/`, and a
# word-split string command turns that space into two arguments and exits 127.
PYTEST=("$REPO_ROOT/backend/.venv/bin/python" -m pytest)
TARGET="${1:-backend/tests/unit/}"
LOG="$(mktemp -t ami_preflight_suite)"

# The Mac has no backend and no database; these run against the sqlite tempfile
# fixture, which is the one backend thing that does work here (CLAUDE.md).
if [ ! -x "$REPO_ROOT/backend/.venv/bin/python" ]; then
  echo "VERDICT: FAIL — backend/.venv/bin/python not found, so the suite did not run."
  echo "         A suite that could not run is not a green suite."
  exit 2
fi

echo "▶ running $TARGET …"
"${PYTEST[@]}" "$TARGET" -q >"$LOG" 2>&1
SUITE_EXIT=$?

SUMMARY="$(grep -E '^[0-9]+ (passed|failed)|passed|failed|error' "$LOG" | tail -1)"

count() { grep -oE "[0-9]+ $1" <<<"$SUMMARY" | grep -oE '^[0-9]+' || echo 0; }
PASSED=$(count passed)
FAILED=$(count failed)
ERRORS=$(count 'error(s)?')
SKIPPED=$(count skipped)

echo "  passed=$PASSED failed=$FAILED errors=$ERRORS skipped=$SKIPPED exit=$SUITE_EXIT"

if [ "$SUITE_EXIT" -ne 0 ]; then
  echo
  echo "── the failing and erroring node ids ───────────────────────────────"
  # Errors as well as failures: the whole point of DEF326 is that the summary
  # line's "errors" bucket is the one nobody reads.
  grep -E '^(FAILED|ERROR) ' "$LOG" | sed 's/^/  /' | head -60
  TOTAL_BAD=$(grep -cE '^(FAILED|ERROR) ' "$LOG")
  if [ "$TOTAL_BAD" -gt 60 ]; then
    echo "  … and $((TOTAL_BAD - 60)) more (full log: $LOG)"
  fi
  echo
  echo "VERDICT: FAIL — the suite exited $SUITE_EXIT. Do not promote."
  echo "         An ERROR is a teardown or fixture that raised. It is not a"
  echo "         lesser kind of green (DEF326)."
  exit 1
fi

rm -f "$LOG"
echo "VERDICT: PASS — the suite exited 0."
exit 0
