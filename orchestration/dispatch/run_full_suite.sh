#!/bin/sh
# run_full_suite.sh — run the full backend unit suite SAFELY (CR061).
#
# WHY: the suite measured ~828s — LONGER than the 600s max Bash-tool timeout — so it can never
# finish inside one foreground call: it is always auto-backgrounded, which kills a headless one-shot
# worker (failure_patterns P7). The ONLY safe way is background+poll:
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
