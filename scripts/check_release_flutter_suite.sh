#!/usr/bin/env bash
# Release gate — does the FLUTTER suite exit 0? (CR195)
#
# Named to match `check_release_schema_parity.py` beside it: both are gates on
# the path from a commit to a binary on a tester's phone, and neither belongs to
# `/promote-to-alpha`. That placement is deliberate, not incidental — `mobile/`
# is excluded from the promotion rsync, so blocking a BACKEND deploy on a client
# test failure would be a gate firing on work it has no relationship to, which
# is DEF277's shape. The client suite gates the client's release path.
#
# WHY THIS EXISTS
#
# Nothing on that path ran `flutter test`. Not `/promote-to-alpha` (it runs the
# backend suite and `flutter analyze`), not `build_testflight.sh`, not
# `build_playstore.sh`, not `publish_playstore.sh`. DEF331 sat red from
# 03992d26 (2026-08-17) until 2026-08-19 — through a backend promotion and a
# store build — while `flutter analyze` returned 0 the entire time, because the
# failure was a test assertion and analyze does not run tests. It was caught
# because a human ran the suite by hand before a release.
#
# Third instance of the same pattern: DEF195 (a release gate that existed and
# was never called) and DEF326 (a suite whose failing state was invisible in the
# line an operator actually reads). *A check nothing invokes is not a check.*
#
# So this does the reading, exactly as DEF326's backend wrapper does: it ends in
# one VERDICT line carrying the word PASS or FAIL, and in an exit code. The
# operator is never asked to interpret a scroll of test output — that ask is how
# DEF326 happened.
#
# Exit 0 suite green · 1 suite not green · 2 could not run.
#
# "Could not run" is exit 2 and is NOT a pass. A gate that waves the build
# through because it could not find `flutter` reports safety it never verified
# (CR040), which is the same reasoning that makes the schema-parity gate exit 1
# when it cannot reach the backend. Callers treat any non-zero as a block.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="$REPO_ROOT/mobile"

if ! command -v flutter >/dev/null 2>&1; then
  echo "VERDICT: FAIL — flutter is not on PATH, so the suite did not run."
  echo "         A suite that could not run is not a green suite."
  exit 2
fi

if [ ! -d "$MOBILE_DIR" ]; then
  echo "VERDICT: FAIL — $MOBILE_DIR not found, so the suite did not run."
  exit 2
fi

LOG="$(mktemp -t ami_release_flutter_suite)"

echo "▶ running flutter test (mobile/) …"
(cd "$MOBILE_DIR" && flutter test "$@") >"$LOG" 2>&1
SUITE_EXIT=$?

# The compact reporter's last counter line looks like
#   00:14 +1113: All tests passed!
#   00:14 +1110 -3: Some tests failed.
# Counts are for the human-readable line only. The VERDICT below keys off the
# EXIT CODE, never off these numbers — DEF326 is precisely the case where a
# summary line read green while the exit code said otherwise.
SUMMARY="$(grep -oE '\+[0-9]+( -[0-9]+)?( ~[0-9]+)?:' "$LOG" | tail -1)"
PASSED="$(grep -oE '\+[0-9]+' <<<"$SUMMARY" | tr -d '+' || echo '?')"
FAILED="$(grep -oE '\-[0-9]+' <<<"$SUMMARY" | tr -d '-')"
: "${PASSED:=?}"
: "${FAILED:=0}"

echo "  passed=$PASSED failed=$FAILED exit=$SUITE_EXIT"

if [ "$SUITE_EXIT" -ne 0 ]; then
  echo
  echo "── what failed ─────────────────────────────────────────────────────"
  # Anchored on the compact reporter's `[E]` suffix, which marks the counter
  # line naming a failing test, then the few lines after it that carry the
  # Expected/Actual and the failing source location.
  #
  # Anchoring matters. The obvious grep — pull every `Expected:` / `package:`
  # line out of the log — matches stack frames printed by tests that PASS, and
  # on the real 1,113-test suite it filled the excerpt with unrelated riverpod
  # frames and pushed the actual failing test name off the top. An excerpt that
  # buries the answer is the DEF326 failure again, one level down.
  FAILING=$(grep -cE '\[E\]$' "$LOG")
  if [ "$FAILING" -gt 0 ]; then
    echo "  $FAILING failing test(s):"
    echo
    awk '/\[E\]$/ { show=8; print; next } show>0 { print; show-- }' "$LOG" \
      | sed 's/^/  /' | head -60
  else
    # No `[E]` anywhere means the suite never got as far as running a test —
    # a compile error, a missing dependency, a bad pubspec. The tail is the
    # only thing that carries it, and printing nothing here would leave the
    # operator with a bare FAIL and no cause.
    echo "  No test-level failures found — the suite did not get that far."
    echo "  (compile error, dependency resolution, or a crash). Log tail:"
    echo
    tail -25 "$LOG" | sed 's/^/  /'
  fi
  echo
  echo "  full log: $LOG"
  echo
  echo "VERDICT: FAIL — flutter test exited $SUITE_EXIT. Do not release."
  echo "         \`flutter analyze\` returning 0 does not answer this question;"
  echo "         that is how DEF331 shipped past two releases (CR195)."
  exit 1
fi

rm -f "$LOG"
echo "VERDICT: PASS — flutter test exited 0."
exit 0
