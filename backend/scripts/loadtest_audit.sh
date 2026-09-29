#!/usr/bin/env bash
# loadtest_audit.sh — post-run audit of the CR246 disposable loadtest database.
# Runs FROM THE MAC against minihost's ami_loadtest_postgres container and
# verifies the invariants CR246 cares about: the ensure_portfolio duplicate
# race (sim_engine.py), exact credit ledger math, cross-user referential
# integrity, and (informational) the live connection count. Exit 0 only when
# every check passes.
#
# Usage:
#   ./loadtest_audit.sh
#   LOADTEST_HOST=minihost LOADTEST_CONTAINER=ami_loadtest_postgres LOADTEST_DB=ami_trade ./loadtest_audit.sh

set -euo pipefail

LOADTEST_HOST="${LOADTEST_HOST:-minihost}"
LOADTEST_CONTAINER="${LOADTEST_CONTAINER:-ami_loadtest_postgres}"
LOADTEST_DB="${LOADTEST_DB:-ami_trade}"
LOADTEST_DB_USER="${LOADTEST_DB_USER:-postgres}"

# The SQL argument is embedded in the remote command string; it must not
# contain double quotes, dollar signs, or backticks (the remote shell would
# re-parse them). Single quotes are safe.
psql() {
  ssh "$LOADTEST_HOST" "docker exec \"$LOADTEST_CONTAINER\" psql -U \"$LOADTEST_DB_USER\" -d \"$LOADTEST_DB\" -tAc \"$1\""
}

FAILURES=0

report() { # name, rows-or-empty
  if [ -z "$2" ]; then
    echo "PASS  $1"
  else
    echo "FAIL  $1"
    echo "$2" | sed 's/^/      /'
    FAILURES=$((FAILURES + 1))
  fi
}

echo "== CR246 loadtest audit: ${LOADTEST_HOST} :: ${LOADTEST_CONTAINER} / ${LOADTEST_DB} =="

# 1. Duplicate training portfolios — the ensure_portfolio race (sim_engine.py):
#    two concurrent first-touches both miss the SELECT and both INSERT. The
#    (user_id, kind, run_id) unique constraint can't fire because Postgres
#    treats NULLs as distinct, so (user_id, 'training', NULL) duplicates stand.
DUPES=$(psql "SELECT user_id::text || '  kind=' || kind || '  rows=' || count(*) FROM sim_portfolios WHERE run_id IS NULL GROUP BY user_id, kind HAVING count(*) > 1")
report "no duplicate training portfolios (run_id IS NULL)" "$DUPES"

# 2. Credit math: every app-side credit writer (spend/refund/_ensure_period's
#    credits_reset/streak credits_added) records a from_value/to_value pair on
#    subscription_events, and anon users start at credit_balance 0, so the
#    signed ledger delta must equal the stored balance exactly. Non-credit
#    event types (account_adoption, revenuecat, ...) are excluded — their
#    from/to values aren't balances.
CREDIT_MISMATCH=$(psql "SELECT u.id::text || '  balance=' || u.credit_balance || '  ledger_sum=' || COALESCE(SUM(se.to_value::int - se.from_value::int), 0) FROM users u LEFT JOIN subscription_events se ON se.user_id = u.id AND se.event_type IN ('credits_spent','credits_refunded','credits_reset','credits_added') GROUP BY u.id, u.credit_balance HAVING u.credit_balance <> COALESCE(SUM(se.to_value::int - se.from_value::int), 0)")
report "credit ledger sums equal stored balances" "$CREDIT_MISMATCH"

# 3. Cross-user referential integrity: every owned row must point at an
#    existing user, and every trade at an existing portfolio.
ORPHAN_TRADES=$(psql "SELECT count(*) FROM sim_trades t LEFT JOIN users u ON u.id = t.user_id WHERE u.id IS NULL")
report "every sim_trades.user_id exists in users" "$([ "${ORPHAN_TRADES:-0}" = "0" ] || echo "orphan trade rows: ${ORPHAN_TRADES}")"

ORPHAN_PORTFOLIOS=$(psql "SELECT count(*) FROM sim_portfolios p LEFT JOIN users u ON u.id = p.user_id WHERE u.id IS NULL")
report "every sim_portfolios.user_id exists in users" "$([ "${ORPHAN_PORTFOLIOS:-0}" = "0" ] || echo "orphan portfolio rows: ${ORPHAN_PORTFOLIOS}")"

ORPHAN_TRADE_PORTFOLIOS=$(psql "SELECT count(*) FROM sim_trades t LEFT JOIN sim_portfolios p ON p.id = t.portfolio_id WHERE p.id IS NULL")
report "every sim_trades.portfolio_id exists in sim_portfolios" "$([ "${ORPHAN_TRADE_PORTFOLIOS:-0}" = "0" ] || echo "orphan trade.portfolio_id rows: ${ORPHAN_TRADE_PORTFOLIOS}")"

ORPHAN_ROOMS=$(psql "SELECT count(*) FROM room_runs r LEFT JOIN users u ON u.id = r.user_id WHERE u.id IS NULL")
report "every room_runs.user_id exists in users" "$([ "${ORPHAN_ROOMS:-0}" = "0" ] || echo "orphan room_runs rows: ${ORPHAN_ROOMS}")"

# 4. Connection count — point-in-time snapshot (Postgres exposes no historical
#    high-water mark). Informational only.
CONN_COUNT=$(psql "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
echo "INFO  connections to ${LOADTEST_DB} right now: ${CONN_COUNT:-unknown}"

echo
if [ "$FAILURES" -eq 0 ]; then
  echo "VERDICT: PASS — all checks clean"
  exit 0
else
  echo "VERDICT: FAIL — ${FAILURES} check(s) failed"
  exit 1
fi
