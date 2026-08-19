#!/bin/sh
# run_full_suite.sh — run the full backend unit suite SAFELY (CR061).
#
# WHY: background+poll, not foreground. The premise was re-measured 2026-08-19 (CR061 close) because
# the number this file used to assert was wrong, and wrong in the direction that invites someone to
# delete the safeguard:
#
#   uv run pytest tests/unit/          549s wall   (544.04s pytest-reported, 4387 tests)
#   backend/.venv/bin/python -m pytest 559s wall   (542.28s pytest-reported)
#
# Same tree, same day, back to back. So `uv run` costs ~nothing — the "828s vs 112s, unresolved"
# note in BINDINGS.md was never about the invocation, it was suite growth: 112s was measured
# 2026-07-23 on a much smaller suite, and 828s is stale in the other direction.
#
# 545s is UNDER the 600s Bash-tool ceiling — by 55s, about 10%, on a suite that grew by 19 tests
# during the two runs above. So a foreground call is not impossible today; it is a coin flip that
# gets worse every week, and when it loses it auto-backgrounds and kills a headless one-shot worker
# (failure_patterns P7). Do not read "549 < 600" as permission to drop this. The safe way is
# background+poll:
#
#   1. Launch THIS script with the Bash tool's run_in_background:true (NO trailing &).
#   2. Poll its output file until the line  SUITE_EXIT=<code>  appears.
#   3. Read that code — do NOT infer pass/fail from the tail of pytest's progress dots.
#
# A fresh worktree needs deps first: pass  SYNC=1  to run  uv sync --extra dev --python 3.13  first.
set -u
cd "$(dirname "$0")/../../backend" || { echo "SUITE_EXIT=127 (cannot cd backend)"; exit 127; }
if [ "${SYNC:-0}" = "1" ]; then uv sync --extra dev --python 3.13 || { echo "SUITE_EXIT=126 (uv sync failed)"; exit 126; }; fi
uv run pytest tests/unit/ -q
ec=$?
echo "SUITE_EXIT=$ec"
exit $ec
