#!/usr/bin/env bash
# Inspect AMI Trade alpha users on melehost.
#
# Usage:
#   scripts/users.sh                  # dashboard — counts + last 10 claimed
#   scripts/users.sh <query>          # search by id / email / apple_id / display_name
#                                       (substring match, case-insensitive on text fields)
#   scripts/users.sh --recent [N]     # last N users by created_at (default 20)
#   scripts/users.sh --anon  [N]      # last N anonymous users (default 10)
#   scripts/users.sh --apple          # all users with apple_id set
#   scripts/users.sh --google         # all users with google_id set
#   scripts/users.sh --counts         # just the counts table, no list
#   scripts/users.sh --events <id>    # subscription_events log for a user
#   scripts/users.sh --contacts [N]   # CSV of contactable (email-having) real users
#                                       to STDOUT for engagement comms (CR082).
#                                       Summary on STDERR. Excludes synthetics/seed/
#                                       probe rows via the CR051 rule, fetched from
#                                       ami_api_alpha at call time (DEF403) — see
#                                       fetch_real_pred() below.
#                                       e.g. scripts/users.sh --contacts > contacts.csv
#
# All queries run against the postgres container on melehost via SSH.
# Read-only — no UPDATE/DELETE in here.

set -euo pipefail

SSH_HOST="${AMI_SSH_HOST:-melehost}"
PSQL="docker exec ami_postgres psql -U postgres -d ami_trade"

run_sql() {
  ssh "$SSH_HOST" "$PSQL -P pager=off -c \"$1\""
}

# CSV variant — raw rows (with a header line) to stdout, nothing else, so the
# caller can redirect straight to a .csv file.
run_sql_csv() {
  ssh "$SSH_HOST" "$PSQL --csv -c \"$1\""
}

# The synthetic/seed/probe exclusion predicate — DEF403: fetched lazily (only
# by the commands that need it, via fetch_real_pred below) from the ONE
# canonical definition (app.services.admin_analytics._real_users_clause()),
# never hand-copied here. This script has no `app` import path of its own,
# so it asks ami_api_alpha (the container that does) for the compiled SQL
# over the same SSH transport as every other query below. Fails loudly on
# error rather than silently falling back to a stale literal — that
# silent-fallback shape is exactly the drift DEF403 found (three hand-synced
# copies missing the 12 probe-id exclusions the ORM copies had).
fetch_real_pred() {
  local pred
  pred=$(ssh "$SSH_HOST" "docker exec ami_api_alpha python3 -m app.services.admin_analytics" 2>/dev/null)
  if [[ -z "$pred" ]]; then
    echo "FATAL: could not fetch the canonical real-users predicate from ami_api_alpha (DEF403)." >&2
    exit 1
  fi
  echo "$pred"
}

# ── helpers ──────────────────────────────────────────────────────────────

cmd_counts() {
  echo "▶ user counts"
  run_sql "
    SELECT
      COUNT(*) AS total,
      COUNT(*) FILTER (WHERE is_anonymous) AS anonymous,
      COUNT(*) FILTER (WHERE NOT is_anonymous) AS claimed,
      COUNT(*) FILTER (WHERE apple_id IS NOT NULL) AS apple,
      COUNT(*) FILTER (WHERE google_id IS NOT NULL) AS google,
      COUNT(*) FILTER (WHERE email IS NOT NULL) AS with_email,
      COUNT(*) FILTER (WHERE display_name IS NOT NULL) AS with_name,
      COUNT(*) FILTER (WHERE suspended_at IS NOT NULL) AS suspended,
      COUNT(*) FILTER (WHERE trial_expires_at > now()) AS in_trial
    FROM users;
  "
}

cmd_dashboard() {
  cmd_counts
  echo ""
  echo "▶ last 10 claimed users"
  run_sql "
    SELECT
      substring(id::text, 1, 8) AS short_id,
      plan,
      COALESCE(display_name, '-') AS name,
      COALESCE(email, '-') AS email,
      CASE WHEN apple_id IS NOT NULL THEN 'apple'
           WHEN google_id IS NOT NULL THEN 'google'
           WHEN email IS NOT NULL THEN 'email'
           ELSE '?' END AS via,
      COALESCE(substring(device_user_id::text, 1, 8), '-') AS device,
      to_char(claimed_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'MM-DD HH24:MI') AS claimed_my
    FROM users
    WHERE NOT is_anonymous
    ORDER BY claimed_at DESC NULLS LAST
    LIMIT 10;
  "
  echo ""
  echo "▶ last 5 anonymous users (most recent activity)"
  run_sql "
    SELECT
      substring(id::text, 1, 8) AS short_id,
      COALESCE(substring(device_user_id::text, 1, 8), '-') AS device,
      to_char(anonymous_session_started_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'MM-DD HH24:MI') AS started_my,
      to_char(created_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'MM-DD HH24:MI') AS created_my
    FROM users
    WHERE is_anonymous
    ORDER BY COALESCE(anonymous_session_started_at, created_at) DESC
    LIMIT 5;
  "
}

cmd_recent() {
  local n="${1:-20}"
  echo "▶ last $n users by created_at"
  run_sql "
    SELECT
      substring(id::text, 1, 8) AS short_id,
      is_anonymous AS anon,
      plan,
      COALESCE(display_name, '-') AS name,
      COALESCE(email, '-') AS email,
      COALESCE(substring(device_user_id::text, 1, 8), '-') AS device,
      to_char(created_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'MM-DD HH24:MI') AS created_my
    FROM users
    ORDER BY created_at DESC
    LIMIT $n;
  "
}

cmd_anon() {
  local n="${1:-10}"
  echo "▶ last $n anonymous users"
  run_sql "
    SELECT
      substring(id::text, 1, 8) AS short_id,
      COALESCE(substring(device_user_id::text, 1, 8), '-') AS device,
      to_char(anonymous_session_started_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'MM-DD HH24:MI') AS started_my,
      to_char(created_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'MM-DD HH24:MI') AS created_my
    FROM users
    WHERE is_anonymous
    ORDER BY COALESCE(anonymous_session_started_at, created_at) DESC
    LIMIT $n;
  "
}

cmd_apple() {
  echo "▶ users with apple_id"
  run_sql "
    SELECT
      substring(id::text, 1, 8) AS short_id,
      COALESCE(display_name, '-') AS name,
      COALESCE(email, '-') AS email,
      substring(apple_id, 1, 30) || '...' AS apple_id_short,
      to_char(claimed_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'MM-DD HH24:MI') AS claimed_my
    FROM users
    WHERE apple_id IS NOT NULL
    ORDER BY claimed_at DESC NULLS LAST;
  "
}

cmd_google() {
  echo "▶ users with google_id"
  run_sql "
    SELECT
      substring(id::text, 1, 8) AS short_id,
      COALESCE(display_name, '-') AS name,
      COALESCE(email, '-') AS email,
      substring(google_id, 1, 30) || '...' AS google_id_short,
      to_char(claimed_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'MM-DD HH24:MI') AS claimed_my
    FROM users
    WHERE google_id IS NOT NULL
    ORDER BY claimed_at DESC NULLS LAST;
  "
}

cmd_search() {
  local q="$1"
  # Escape single quotes for SQL safety.
  local qe="${q//\'/\'\'}"
  echo "▶ search: $q"
  echo ""
  echo "── user rows ──"
  run_sql "
    SELECT
      substring(id::text, 1, 8) AS short_id,
      is_anonymous AS anon,
      plan,
      credit_balance AS credits,
      COALESCE(display_name, '-') AS name,
      COALESCE(email, '-') AS email,
      CASE WHEN apple_id IS NOT NULL THEN 'apple'
           WHEN google_id IS NOT NULL THEN 'google'
           WHEN email IS NOT NULL THEN 'email'
           ELSE '-' END AS via,
      COALESCE(substring(device_user_id::text, 1, 8), '-') AS device,
      to_char(claimed_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'MM-DD HH24:MI') AS claimed_my
    FROM users
    WHERE
      id::text ILIKE '%${qe}%'
      OR device_user_id::text ILIKE '%${qe}%'
      OR email ILIKE '%${qe}%'
      OR display_name ILIKE '%${qe}%'
      OR apple_id ILIKE '%${qe}%'
      OR google_id ILIKE '%${qe}%'
    ORDER BY claimed_at DESC NULLS LAST
    LIMIT 20;
  "
  # If exactly one row matches, show their activity summary.
  local count
  count=$(ssh "$SSH_HOST" "$PSQL -tA -c \"
    SELECT COUNT(*) FROM users
    WHERE id::text ILIKE '%${qe}%'
       OR device_user_id::text ILIKE '%${qe}%'
       OR email ILIKE '%${qe}%'
       OR display_name ILIKE '%${qe}%'
       OR apple_id ILIKE '%${qe}%'
       OR google_id ILIKE '%${qe}%';
  \"" 2>/dev/null | tr -d '[:space:]')
  if [[ "$count" == "1" ]]; then
    echo ""
    echo "── activity summary ──"
    run_sql "
      WITH u AS (
        SELECT id FROM users
        WHERE id::text ILIKE '%${qe}%'
           OR device_user_id::text ILIKE '%${qe}%'
           OR email ILIKE '%${qe}%'
           OR display_name ILIKE '%${qe}%'
           OR apple_id ILIKE '%${qe}%'
           OR google_id ILIKE '%${qe}%'
        LIMIT 1
      )
      SELECT
        (SELECT 1                                      FROM mandates       WHERE user_id = (SELECT id FROM u))     AS has_mandate,
        (SELECT COUNT(*) FROM journal_entries WHERE user_id = (SELECT id FROM u) AND deleted_at IS NULL) AS journal_live,
        (SELECT COUNT(*) FROM sim_trades      WHERE user_id = (SELECT id FROM u))                  AS sim_trades,
        (SELECT COUNT(*) FROM sim_watchlists  WHERE user_id = (SELECT id FROM u))                  AS watchlist,
        (SELECT COUNT(*) FROM room_runs       WHERE user_id = (SELECT id FROM u))                  AS room_runs,
        (SELECT COUNT(*) FROM one_on_one_messages WHERE user_id = (SELECT id FROM u))             AS oo_messages,
        (SELECT COUNT(*) FROM lessons_progress WHERE user_id = (SELECT id FROM u))                AS lessons_done,
        (SELECT COUNT(*) FROM user_overlays    WHERE user_id = (SELECT id FROM u))                AS briefs,
        (SELECT COUNT(*) FROM subscription_events WHERE user_id = (SELECT id FROM u))             AS sub_events;
    "
  fi
}

cmd_events() {
  local id_prefix="$1"
  local qe="${id_prefix//\'/\'\'}"
  echo "▶ subscription_events for user matching '$id_prefix'"
  run_sql "
    SELECT
      to_char(created_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'MM-DD HH24:MI') AS at_my,
      event_type,
      source,
      from_value,
      to_value,
      COALESCE(note, '-') AS note
    FROM subscription_events
    WHERE user_id IN (
      SELECT id FROM users WHERE id::text ILIKE '%${qe}%' LIMIT 1
    )
    ORDER BY created_at DESC
    LIMIT 50;
  "
}

cmd_contacts() {
  local n="${1:-1000}"
  local REAL_PRED
  REAL_PRED="$(fetch_real_pred)"
  # Loud gap summary to stderr — how many real users are actually reachable by
  # email. Anonymous-first means most rows have email IS NULL; make that visible.
  local summary
  summary=$(ssh "$SSH_HOST" "$PSQL -tA -c \"
    SELECT
      count(*) FILTER (WHERE email IS NOT NULL) || ' contactable (email) / ' ||
      count(*) || ' real users'
    FROM users WHERE ${REAL_PRED};
  \"" 2>/dev/null | tr -d '\r')
  echo "▶ contacts: ${summary} — CSV on stdout (excludes synthetics/seed rows)" >&2

  run_sql_csv "
    WITH real_users AS (SELECT * FROM users WHERE ${REAL_PRED}),
    last_act AS (
      SELECT user_id, max(ts) AS last_activity FROM (
        SELECT user_id, triggered_at AS ts FROM room_runs
        UNION ALL SELECT user_id, opened_at FROM sim_trades
        UNION ALL SELECT user_id, created_at FROM journal_entries WHERE deleted_at IS NULL
        UNION ALL SELECT user_id, created_at FROM one_on_one_messages
        UNION ALL SELECT user_id, coalesce(completed_at, started_at)
                    FROM lessons_progress WHERE started_at IS NOT NULL
      ) a GROUP BY user_id
    ),
    rooms AS (SELECT user_id, count(*) AS n FROM room_runs GROUP BY user_id)
    SELECT
      u.email,
      coalesce(u.display_name, '') AS display_name,
      CASE WHEN u.device_model LIKE 'iPhone%' OR u.device_model LIKE 'iPad%' THEN 'ios'
           WHEN u.device_model IS NOT NULL OR coalesce(u.os_version,'') LIKE 'Android%' THEN 'android'
           ELSE 'unknown' END AS platform,
      u.plan,
      to_char(u.created_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'YYYY-MM-DD HH24:MI') AS created_my,
      to_char(u.claimed_at AT TIME ZONE 'Asia/Kuala_Lumpur', 'YYYY-MM-DD HH24:MI') AS claimed_my,
      coalesce(u.last_app_version, '') AS last_app_version,
      coalesce(r.n, 0) AS rooms_convened,
      to_char(la.last_activity AT TIME ZONE 'Asia/Kuala_Lumpur', 'YYYY-MM-DD HH24:MI') AS last_activity_my
    FROM real_users u
    LEFT JOIN rooms r ON r.user_id = u.id
    LEFT JOIN last_act la ON la.user_id = u.id
    WHERE u.email IS NOT NULL
    ORDER BY la.last_activity DESC NULLS LAST, u.created_at DESC
    LIMIT ${n};
  "
}

# ── dispatch ─────────────────────────────────────────────────────────────

if [[ $# -eq 0 ]]; then
  cmd_dashboard
  exit 0
fi

case "$1" in
  --counts)            cmd_counts                              ;;
  --contacts)          cmd_contacts "${2:-1000}"               ;;
  --recent)            cmd_recent "${2:-20}"                   ;;
  --anon)              cmd_anon   "${2:-10}"                   ;;
  --apple)             cmd_apple                                ;;
  --google)            cmd_google                               ;;
  --events)            shift; cmd_events "${1:?need a user id prefix}" ;;
  -h|--help|help)
    sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
    ;;
  *)                   cmd_search "$1"                         ;;
esac
