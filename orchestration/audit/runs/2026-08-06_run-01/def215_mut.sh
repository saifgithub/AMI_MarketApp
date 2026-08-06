#!/bin/bash
# DEF215 r1 audit — his MUT-1..3 re-performed + AUD-1..4.
#
# Discipline learned the hard way on CR136-M10 r2: a perl pattern that does not
# match applies nothing, and a no-op mutation reads EXACTLY like a surviving
# guard. So every mutation asserts its own diff is non-empty before the run.
set -u
ROOT="/Volumes/Extreme Pro/AMI_MarketApp/.claude/worktrees/audit-def215"
W="$ROOT/backend"
PY="/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python"
SUITE="tests/unit/test_def215_schema_ownership.py"
F="app/db/session.py"
cd "$W" || exit 1

restore() { git -C "$ROOT" checkout -- backend/app/db/session.py; }

# $1 = label. Asserts the working tree actually differs from HEAD first.
run() {
  if git -C "$ROOT" diff --quiet -- backend/app/db/session.py; then
    printf '%-56s %s\n' "$1" "!! NO-OP — pattern did not match, result meaningless"
    return
  fi
  out=$(PYTHONPATH=. "$PY" -m pytest $SUITE -q 2>&1)
  printf '%-56s %s\n' "$1" "$(echo "$out" | tail -1)"
  echo "$out" | grep -E "^FAILED" | sed 's/^/      /'
}

restore
base=$(PYTHONPATH=. "$PY" -m pytest $SUITE -q 2>&1 | tail -1)
printf '%-56s %s\n' "baseline (unmutated)" "$base"
echo

# --- his three, re-performed independently -------------------------------
perl -0pi -e 's/(    engine = get_engine\(\)\n)/$1\n    Base.metadata.create_all(engine)  # MUT-1 pre-DEF215 ordering\n/' $F
run "MUT-1  create_all fires ABOVE the freshness check (the defect)"
restore

perl -0pi -e 's/        _report_if_behind_head\(engine\)/        pass/' $F
run "MUT-2  _report_if_behind_head -> pass"
restore

perl -0pi -e 's/            alembic_command\.stamp\(cfg, "head"\)/            pass/' $F
run "MUT-3  stamp -> pass"
restore

# --- mine ------------------------------------------------------------------
perl -0pi -e 's/    fresh = "alembic_version" not in inspect\(engine\)\.get_table_names\(\)/    fresh = "alembic_version" in inspect(engine).get_table_names()/' $F
run "AUD-1  freshness inverted"
restore

# Does anything notice if the non-fresh path stops memoising? (perf + log spam)
perl -0pi -e 's/        _report_if_behind_head\(engine\)\n        _schema_checked_for = engine\n        return/        _report_if_behind_head(engine)\n        return/' $F
run "AUD-2  non-fresh path stops memoising (spam/perf only)"
restore

# A plausible refactor slip: identity check degraded to a null check.
perl -0pi -e 's/    if _schema_checked_for is engine:/    if _schema_checked_for is not None:/' $F
run "AUD-3  'is engine' -> 'is not None' (first engine wins forever)"
restore

# The report fires but names nothing useful.
perl -0pi -e 's/        if head is not None and current != head:/        if False:/' $F
run "AUD-4  behind-head comparison never true"
restore

echo
echo "--- tree must be clean ---"
git -C "$ROOT" status --short -- backend/app/db/session.py
echo "(no output above = restored)"
