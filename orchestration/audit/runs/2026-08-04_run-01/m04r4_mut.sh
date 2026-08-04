#!/bin/bash
set -u
W="/Volumes/Extreme Pro/AMI_MarketApp/.claude/worktrees/audit-m04r4"
PY="/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python"
cd "$W/backend" || exit 1

T=(tests/unit/test_cr136_metrics_engine.py)
run() { PYTHONPATH=. "$PY" -m pytest "${T[@]}" -q 2>&1 | tail -1; }
killed() { PYTHONPATH=. "$PY" -m pytest "${T[@]}" -q 2>&1 | grep "^FAILED" | sed 's/FAILED tests.unit.test_cr136_metrics_engine.py:://'; }
patch() { "$PY" - "$1" "$2" "$3" <<'EOF'
import sys
p, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(p).read(); assert s.count(old) == 1, f"{p}: matched {s.count(old)}"
open(p, "w").write(s.replace(old, new))
EOF
}
restore() { git -C "$W" checkout -- backend/; }

ENG=app/services/portfolio_health.py
CON=app/services/portfolio_health_constants.py

echo "=== BASELINE ==="; run

echo; echo "=== MUT-1 (his): guard branch removed ==="
patch "$ENG" '    elif window_days / t_obs > GRID_DENSITY_MAX:' \
             '    elif False:'
run; killed; restore

echo; echo "=== MUT-2 (his): threshold LOOSENED 1.65 -> 3.0 ==="
patch "$CON" 'GRID_DENSITY_MAX = 1.65' 'GRID_DENSITY_MAX = 3.0'
run; killed; restore

for V in 1.45 1.50 1.55; do
  echo; echo "=== MUT-3' (his): threshold TIGHTENED 1.65 -> $V ==="
  patch "$CON" 'GRID_DENSITY_MAX = 1.65' "GRID_DENSITY_MAX = $V"
  run; killed; restore
done

echo; echo "=== AUD-1 (mine): threshold 1.60 — inside the unpinned band? ==="
patch "$CON" 'GRID_DENSITY_MAX = 1.65' 'GRID_DENSITY_MAX = 1.60'
run; killed; restore

echo; echo "=== AUD-2 (mine): threshold 2.20 — just under the gappy book's 2.34 ==="
patch "$CON" 'GRID_DENSITY_MAX = 1.65' 'GRID_DENSITY_MAX = 2.20'
run; killed; restore

echo; echo "=== MUT-4 (his): sparse_grid checked BEFORE short_window ==="
"$PY" - <<'EOF'
p = "app/services/portfolio_health.py"
s = open(p).read()
short = "    if t_obs < T_MIN:\n"
assert s.count(short) == 1, s.count(short)
old_sparse = "    elif window_days / t_obs > GRID_DENSITY_MAX:"
assert s.count(old_sparse) == 1
s = s.replace(old_sparse, "    elif False:")
s = s.replace(short, "    if t_obs and window_days / t_obs > GRID_DENSITY_MAX:\n        estimator_cause = INSUFFICIENT_SPARSE_GRID\n    elif t_obs < T_MIN:\n")
open(p, "w").write(s)
EOF
run; killed; restore

echo; echo "=== TREE CLEAN AFTER ALL ==="
git -C "$W" status --short | head
