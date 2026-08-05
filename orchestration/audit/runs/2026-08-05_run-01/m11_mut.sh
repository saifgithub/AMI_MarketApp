#!/bin/bash
# M11 r1 audit — mutation battery. QA-A/B/C reproduced + AUD-1.
set -u
ROOT="/Volumes/Extreme Pro/AMI_MarketApp/.claude/worktrees/audit-m11r1"
W="$ROOT/backend"
PY="/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python"
SUITE="tests/unit/test_cr136_rule_engine.py tests/unit/test_cr136_health_gate.py tests/unit/test_portfolio_snapshot.py"
cd "$W" || exit 1

restore() {
  git -C "$ROOT" checkout -- \
    backend/app/services/portfolio_rules.py \
    backend/app/services/portfolio_snapshot.py \
    backend/app/services/journal_store.py
}

run() {  # $1 = label
  out=$(PYTHONPATH=. "$PY" -m pytest $SUITE -q 2>&1)
  printf '%-58s %s\n' "$1" "$(echo "$out" | tail -1)"
  echo "$out" | grep -E "^FAILED" | sed 's/^/      /'
}

restore
run "baseline"

perl -0pi -e 's/invested_fraction = max\(0\.0, 1\.0 - cash_pct_total \/ 100\.0\)/invested_fraction = 1.0/' app/services/portfolio_rules.py
run "QA-A  R0 reverted to the invested-sleeve basis"
restore

perl -0pi -e 's/        if sector == OTHER:\n            continue\n//' app/services/portfolio_rules.py
run "QA-B  R0 unclassified-bucket exclusion removed"
restore

perl -0pi -e 's/    as_of = resolve_day\(\)\n    if as_of is None:/    as_of = resolve_day()\n    if as_of is None:\n        as_of = now.date().isoformat()\n    if False:/' app/services/portfolio_snapshot.py
run "QA-C  snapshot tick fabricates a calendar date"
restore

perl -0pi -e 's/and _as_utc\(r\.created_at\) >= day_start/and _as_utc(r.created_at) > day_start/' app/services/journal_store.py
run "AUD-1 journal daily count: >= day_start  ->  > day_start"
restore

run "restored"
echo "--- tree ---"
git -C "$ROOT" status --short | head
