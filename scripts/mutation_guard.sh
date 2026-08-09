#!/usr/bin/env bash
# mutation_guard.sh — make a mutation run unable to lie to you.
#
# failure_patterns.md P9. Mutation testing is how this project proves a guard is
# real, and both halves of the loop have produced confident, meaningless results:
#
#   DEF136  ran the matrix with `pytest -x`, so pytest stopped at the first
#           failure and never revealed that one of the two tests was green
#           against a real regression.
#   DEF127  reverted each mutation with `git checkout -- <file>` while the fix
#           was still uncommitted. git cannot tell a mutation from a fix — both
#           are uncommitted changes to the same file — so it deleted the fix.
#   DEF130  the identical `git checkout` mistake, ~20 minutes after the operator
#           wrote "never do this" into DEF127's hand-off.
#
# That third one is why this file exists rather than another paragraph of advice.
# The rule did not survive an hour as prose (CR038: instructions are not controls).
#
# Usage:
#   scripts/mutation_guard.sh <target-file> <mutate-cmd> <test-cmd>
#
#   <mutate-cmd>  applies the mutation (any shell command)
#   <test-cmd>    runs the tests; must NOT contain -x
#
# Example:
#   scripts/mutation_guard.sh backend/app/api/sse.py \
#     "python3 -c \"...break it...\"" \
#     "./backend/.venv/bin/python -m pytest backend/tests/unit/test_x.py -q"
#
# Exits non-zero on any precondition breach. The mutation is always reverted.

set -euo pipefail

if [ $# -ne 3 ]; then
  echo "usage: $0 <target-file> <mutate-cmd> <test-cmd>" >&2
  exit 2
fi

TARGET="$1"
MUTATE="$2"
TEST_CMD="$3"

fail() { echo "MUTATION GUARD: $*" >&2; exit 1; }

# DEF248: every git call below is pinned to the repo root, and both eval'd
# commands run in subshells. Before this, `eval "$TEST_CMD"` ran in the script's
# own shell — so a test command containing `cd mobile` moved the SCRIPT's cwd,
# the repo-relative `git checkout -- "$TARGET"` then failed to resolve, and
# `set -e` exited before the "revert INCOMPLETE" check below could fire. The
# mutation stayed in the working tree while the run looked like a clean catch.
# P9 inside the script written to prevent P9.
REPO_ROOT=$(git rev-parse --show-toplevel) || fail "not inside a git repository"
git() { command git -C "$REPO_ROOT" "$@"; }

[ -e "$TARGET" ] || fail "target '$TARGET' does not exist"

# DEF248: resolve TARGET to an absolute path *before* any git call, so the
# cwd-relative `-e` test above and the repo-root-pinned git calls below can
# never disagree about which file we mean. git accepts an absolute pathspec as
# long as it is inside the worktree.
TARGET="$(cd "$(dirname "$TARGET")" && pwd)/$(basename "$TARGET")"

# 1. The target must be tracked. An untracked file cannot be restored by git at
#    all — DEF127's sse.py kept its mutation because `git checkout` simply errored.
git ls-files --error-unmatch "$TARGET" >/dev/null 2>&1 \
  || fail "'$TARGET' is UNTRACKED. git checkout cannot restore it, so a mutation
  applied here is unrecoverable. Commit it first."

# 2. The target must be clean. This is the DEF127/DEF130 failure: the revert
#    would take the fix with it.
if ! git diff --quiet -- "$TARGET" || ! git diff --cached --quiet -- "$TARGET"; then
  fail "'$TARGET' has UNCOMMITTED changes.
  Reverting the mutation would delete them — git cannot tell your fix from your
  mutation. Commit the fix first, then mutate. (failure_patterns.md P9)"
fi

# 3. No -x. It stops at the first failure, which is how a still-passing test
#    hides inside a matrix that looks red.
case " $TEST_CMD " in
  *" -x "*|*" --exitfirst "*|*" -x")
    fail "test command contains -x/--exitfirst.
  pytest would stop at the first failure and you would not see which tests are
  still GREEN under the mutation — that is exactly how DEF136's escape hid." ;;
esac

BEFORE_SHA=$(git rev-parse HEAD)

echo "── applying mutation to $TARGET"
( eval "$MUTATE" )

git diff --quiet -- "$TARGET" \
  && fail "mutation command left '$TARGET' unchanged — it did not apply.
  A green result here proves nothing. Check the mutation's match string."

echo "── running tests (mutation ACTIVE — expect RED)"
set +e
( eval "$TEST_CMD" )
TEST_RC=$?
set -e
echo "── test exit code under mutation: $TEST_RC"

echo "── reverting"
# DEF248: never let a failing checkout abort the script under `set -e` — the
# tree comparison below is the authoritative check and MUST get to run. A
# checkout that errors is diagnosis, not a reason to leave the operator with a
# mutated tree and no warning.
set +e
CHECKOUT_ERR=$(git checkout -- "$TARGET" 2>&1)
CHECKOUT_RC=$?
set -e
[ "$CHECKOUT_RC" -eq 0 ] || echo "── checkout returned $CHECKOUT_RC: $CHECKOUT_ERR" >&2

# 4. Prove the revert was total by reading the tree, not by trusting the command.
if ! git diff --quiet -- "$TARGET"; then
  fail "revert INCOMPLETE — '$TARGET' still differs from HEAD (checkout exit
  $CHECKOUT_RC). Do not trust the numbers above; the mutation is STILL APPLIED.
  Restore it now:  git checkout -- $TARGET"
fi
[ "$(git rev-parse HEAD)" = "$BEFORE_SHA" ] || fail "HEAD moved during the run"

echo "── reverted cleanly; tree matches HEAD"

if [ "$TEST_RC" -eq 0 ]; then
  echo "MUTATION GUARD: ⚠️  tests PASSED under the mutation — the guard does NOT catch it." >&2
  exit 3
fi
echo "MUTATION GUARD: ✅ mutation caught (exit $TEST_RC), tree restored."
