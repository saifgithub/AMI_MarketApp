#!/bin/bash
# DEF215 r2 audit. His AUD-2 + MUT-4 re-performed, r1's three re-checked, plus mine.
#
# The m1 guard is TIMING-BASED and his first version of it survived the mutation.
# So the question is not "does it kill" but "does it kill EVERY time" — a
# concurrency guard that kills 3-of-5 lets the regression through on a lucky run.
# Every threaded row is therefore repeated 5x.
set -u
ROOT="/Volumes/Extreme Pro/AMI_MarketApp/.claude/worktrees/audit-def215-r2"
W="$ROOT/backend"
PY="/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python"
SUITE="tests/unit/test_def215_schema_ownership.py"
F="app/db/session.py"
cd "$W" || exit 1

restore() { git -C "$ROOT" checkout -- backend/app/db/session.py; }

run() {  # $1=label
  if git -C "$ROOT" diff --quiet -- backend/app/db/session.py; then
    printf '%-52s %s\n' "$1" "!! NO-OP — pattern did not match, result meaningless"
    return
  fi
  out=$(PYTHONPATH=. "$PY" -m pytest $SUITE -q 2>&1)
  printf '%-52s %s\n' "$1" "$(echo "$out" | tail -1)"
  echo "$out" | grep -E "^FAILED" | sed 's/^/      /'
}

runN() {  # $1=label $2=reps — for the timing-sensitive ones
  if git -C "$ROOT" diff --quiet -- backend/app/db/session.py; then
    printf '%-52s %s\n' "$1" "!! NO-OP — pattern did not match"
    return
  fi
  kills=0
  for i in $(seq 1 "$2"); do
    out=$(PYTHONPATH=. "$PY" -m pytest $SUITE -q 2>&1)
    echo "$out" | tail -1 | grep -q "failed" && kills=$((kills + 1))
  done
  printf '%-52s killed %s/%s runs\n' "$1" "$kills" "$2"
}

restore
echo "=== baseline, 5x (a flaky guard also shows up as flaky RED) ==="
green=0
for i in $(seq 1 5); do
  out=$(PYTHONPATH=. "$PY" -m pytest $SUITE -q 2>&1)
  echo "$out" | tail -1 | grep -q "^6 passed" && green=$((green + 1))
done
printf '%-52s green %s/5\n' "baseline" "$green"
echo

echo "=== his round-2 two ==="
perl -0pi -e 's/        _report_if_behind_head\(engine\)\n        _schema_checked_for = engine\n        return/        _report_if_behind_head(engine)\n        return/' $F
run "AUD-2  drop memoisation on the non-fresh path (mine, r1)"
restore

perl -0pi -e 's/    with _schema_lock:\n        if _schema_checked_for is engine:\n            return\n        _init_schema_locked\(engine\)/    _init_schema_locked(engine)/' $F
run   "MUT-4  remove the lock entirely"
runN  "MUT-4  remove the lock entirely (repeat)" 5
restore

echo
echo "=== round 1's three, still killing? ==="
perl -0pi -e 's/(    engine = get_engine\(\)\n)/$1\n    Base.metadata.create_all(engine)  # MUT-1\n/' $F
run "MUT-1  create_all above the freshness check"
restore
perl -0pi -e 's/        _report_if_behind_head\(engine\)/        pass/' $F
run "MUT-2  _report_if_behind_head -> pass"
restore
perl -0pi -e 's/            alembic_command\.stamp\(cfg, "head"\)/            pass/' $F
run "MUT-3  stamp -> pass"
restore

echo
echo "=== mine, new for r2 ==="
# The 'double' in double-checked locking. Second thread re-runs the body.
perl -0pi -e 's/    with _schema_lock:\n        if _schema_checked_for is engine:\n            return\n        _init_schema_locked\(engine\)/    with _schema_lock:\n        _init_schema_locked(engine)/' $F
run "AUD-5  inner re-check removed (the 'double' of DCL)"
restore

# A non-reentrant lock held across alembic stamp, which executes env.py.
perl -0pi -e 's/_schema_lock = threading\.Lock\(\)/_schema_lock = threading.RLock()/' $F
run "AUD-6  Lock -> RLock (would mask any re-entrant call)"
restore

echo
echo "--- tree must be clean ---"
git -C "$ROOT" status --short -- backend/app/db/session.py
echo "(no output above = restored)"
