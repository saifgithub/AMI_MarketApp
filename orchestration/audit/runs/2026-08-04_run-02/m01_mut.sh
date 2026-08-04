#!/bin/bash
set -u
W="/Volumes/Extreme Pro/AMI_MarketApp/.claude/worktrees/audit-m01r1"
PY="/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python"
cd "$W/backend" || exit 1

T=(tests/unit/test_cr136_price_history.py)
run() { PYTHONPATH=. "$PY" -m pytest "${T[@]}" -q 2>&1 | tail -1; }
killed() { PYTHONPATH=. "$PY" -m pytest "${T[@]}" -q 2>&1 | grep "^FAILED" | sed 's/FAILED tests.unit.test_cr136_price_history.py:://'; }
patch() { "$PY" - "$1" "$2" "$3" <<'EOF'
import sys
p, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(p).read(); assert s.count(old) == 1, f"{p}: matched {s.count(old)}"
open(p, "w").write(s.replace(old, new))
EOF
}
restore() { git -C "$W" checkout -- backend/; }

PH=app/services/price_history.py

echo "=== BASELINE ==="; run

echo; echo "=== AUD-1 (his attack 4): replace_foreign_rows expression INVERTED at the call site ==="
patch "$PH" 'replace_foreign_rows=source != _MOCK_SOURCE,' \
            'replace_foreign_rows=source == _MOCK_SOURCE,'
run; killed; restore

echo; echo "=== AUD-2 (his attack 4): replace_foreign_rows expression DELETED (defaults) ==="
patch "$PH" '                replace_foreign_rows=source != _MOCK_SOURCE,
' ''
run; killed; restore

echo; echo "=== AUD-3 (mine): detect_bad_print_days loop starts at 0 instead of 1 ==="
grep -n "for i in range(1" "$PH" | head -3

echo; echo "=== TREE CLEAN ==="
git -C "$W" status --short | head
