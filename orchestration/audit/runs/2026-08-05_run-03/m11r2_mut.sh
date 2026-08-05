#!/bin/bash
# M11 r2 audit — his MUT-1..3 re-performed + AUD-1..3.
set -u
ROOT="/Volumes/Extreme Pro/AMI_MarketApp/.claude/worktrees/audit-m11r2"
W="$ROOT/backend"
PY="/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python"
SUITE="tests/unit/test_cr136_live_crosscheck_gate.py"
cd "$W" || exit 1
F="scripts/cr136_live_crosscheck.py"

restore() { git -C "$ROOT" checkout -- backend/$F; }

run() {
  out=$(PYTHONPATH=. "$PY" -m pytest $SUITE -q 2>&1)
  printf '%-58s %s\n' "$1" "$(echo "$out" | tail -1)"
  echo "$out" | grep -E "^FAILED" | sed 's/^/      /'
}

restore
run "baseline"

perl -0pi -e 's/    surprises = \[m for m in unchecked if m not in allowed_unchecked\]/    surprises = []/' $F
run "MUT-1  surprises = []  (the exact round-1 defect)"
restore

perl -0pi -e 's/    surprises = \[m for m in unchecked if m not in allowed_unchecked\]/    surprises = list(unchecked)/' $F
run "MUT-2  surprises = list(unchecked)  (waiver ignored)"
restore

perl -0pi -e 's/            "reads \(a schema drift this gate has no pin against\)\."\n        \)\n        return 1/            "reads (a schema drift this gate has no pin against)."\n        )\n        return 0/' $F
run "MUT-3  the surprise FAIL prints, then returns 0"
restore

perl -0pi -e 's/    surprises = \[m for m in unchecked if m not in allowed_unchecked\]/    surprises = [] if allowed_unchecked else list(unchecked)/' $F
run "AUD-1  any waiver becomes a BLANKET waiver"
restore

perl -0pi -e 's/^from app\.services\.price_history import _MOCK_SOURCE$/from app.services.price_history import _MOCK_SOURCE\nfrom app.trading_math.portfolio_risk import ewma_covariance as _engine_cov/m' $F
run "AUD-2  the harness imports app.trading_math"
restore

perl -0pi -e 's/    if stale_allowances:\n        print\(f"  --allow-unchecked named, but PUBLISHED: \{stale_allowances\}"\)\n//' $F
run "AUD-3  the stale-allowance line is deleted"
restore

run "restored"
echo "--- tree ---"
git -C "$ROOT" status --short | head
