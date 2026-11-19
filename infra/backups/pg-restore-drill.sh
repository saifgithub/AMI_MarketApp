#!/usr/bin/env bash
# CR267 WP-44 — restore drill for the encrypted Postgres backups.
#
# Downloads the NEWEST backup from the S3-compatible bucket (or takes --file for
# a local one), decrypts it, restores it into a throwaway Postgres container,
# runs row-count sanity checks, and prints a timing line per phase. The numbers
# it prints are what WP-44 records as "one restore drill with timings".
#
# Plaintext never touches disk: gpg | gunzip | psql is one stream, and the only
# file on disk is the still-encrypted download, in a temp dir removed on exit.
# The throwaway container is removed on exit too; it publishes no port and is
# never attached to the live database. It does not read or write the live DB.
#
# Usage:
#   BACKUP_S3_ENDPOINT=... BACKUP_S3_BUCKET=... BACKUP_S3_ACCESS_KEY_ID=... \
#   BACKUP_S3_SECRET_ACCESS_KEY=... BACKUP_ENCRYPTION_PASSPHRASE_FILE=/etc/ami-trade-backup.pass \
#       bash infra/backups/pg-restore-drill.sh
#   bash infra/backups/pg-restore-drill.sh --file /var/backups/ami-trade/ami_trade-latest.sql.gz.gpg
#
# Exit 0 only if the restore ran without a single SQL error AND the sanity
# checks passed. Any other outcome prints FAIL and exits non-zero.

set -euo pipefail

if [[ -f /etc/ami-trade-backup.env ]]; then
    # shellcheck disable=SC1091
    source /etc/ami-trade-backup.env
fi

BACKUP_S3_ENDPOINT="${BACKUP_S3_ENDPOINT:-}"
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:-}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-pg}"
BACKUP_S3_ACCESS_KEY_ID="${BACKUP_S3_ACCESS_KEY_ID:-}"
BACKUP_S3_SECRET_ACCESS_KEY="${BACKUP_S3_SECRET_ACCESS_KEY:-}"
BACKUP_S3_PROVIDER="${BACKUP_S3_PROVIDER:-Cloudflare}"
BACKUP_ENCRYPTION_PASSPHRASE="${BACKUP_ENCRYPTION_PASSPHRASE:-}"
BACKUP_ENCRYPTION_PASSPHRASE_FILE="${BACKUP_ENCRYPTION_PASSPHRASE_FILE:-}"
RESTORE_PG_IMAGE="${RESTORE_PG_IMAGE:-postgres:15-alpine}"   # match the live server's major version
RESTORE_MIN_TABLES="${RESTORE_MIN_TABLES:-20}"
RESTORE_DB="${RESTORE_DB:-ami_trade}"
LOCAL_FILE=""

log() { echo "[$(date -u +%FT%TZ)] $*"; }
fail() { echo "[$(date -u +%FT%TZ)] FAIL — $*" >&2; exit 1; }

while (( $# > 0 )); do
    case "$1" in
        --file) LOCAL_FILE="${2:-}"; shift 2 ;;
        *) fail "unknown argument '$1' (usage: pg-restore-drill.sh [--file <backup.sql.gz.gpg>])" ;;
    esac
done

if [[ -z "${BACKUP_ENCRYPTION_PASSPHRASE}" && -n "${BACKUP_ENCRYPTION_PASSPHRASE_FILE}" ]]; then
    [[ -s "${BACKUP_ENCRYPTION_PASSPHRASE_FILE}" ]] || fail "BACKUP_ENCRYPTION_PASSPHRASE_FILE missing or empty"
    BACKUP_ENCRYPTION_PASSPHRASE="$(<"${BACKUP_ENCRYPTION_PASSPHRASE_FILE}")"
fi
[[ -n "${BACKUP_ENCRYPTION_PASSPHRASE}" ]] || fail "no BACKUP_ENCRYPTION_PASSPHRASE / _FILE — cannot decrypt"
for tool in gpg gunzip docker; do
    command -v "${tool}" >/dev/null 2>&1 || fail "${tool} not installed"
done

WORK="$(mktemp -d)"
CONTAINER="ami_restore_drill_$$"
cleanup() {
    docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
    rm -rf "${WORK}"
}
trap cleanup EXIT

declare -a PHASES=()
phase_start() { PHASE_T0=$SECONDS; PHASE_NAME="$1"; }
phase_end() { PHASES+=("${PHASE_NAME}=$((SECONDS - PHASE_T0))s"); log "${PHASE_NAME} took $((SECONDS - PHASE_T0))s"; }
DRILL_T0=$SECONDS

# 1. Fetch
phase_start download
if [[ -n "${LOCAL_FILE}" ]]; then
    [[ -f "${LOCAL_FILE}" ]] || fail "--file ${LOCAL_FILE} not found"
    BACKUP="${LOCAL_FILE}"
else
    [[ -n "${BACKUP_S3_ENDPOINT}" && -n "${BACKUP_S3_BUCKET}" && -n "${BACKUP_S3_ACCESS_KEY_ID}" && -n "${BACKUP_S3_SECRET_ACCESS_KEY}" ]] \
        || fail "BACKUP_S3_* incomplete and no --file given"
    command -v rclone >/dev/null 2>&1 || fail "rclone not installed"
    export RCLONE_S3_PROVIDER="${BACKUP_S3_PROVIDER}"
    export RCLONE_S3_ENDPOINT="${BACKUP_S3_ENDPOINT}"
    export RCLONE_S3_ACCESS_KEY_ID="${BACKUP_S3_ACCESS_KEY_ID}"
    export RCLONE_S3_SECRET_ACCESS_KEY="${BACKUP_S3_SECRET_ACCESS_KEY}"
    export RCLONE_S3_REGION="${RCLONE_S3_REGION:-auto}"
    export RCLONE_S3_NO_CHECK_BUCKET=true
    export RCLONE_S3_ENV_AUTH=false
    REMOTE=":s3:${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX#/}"
    REMOTE="${REMOTE%/}"
    NEWEST="$(rclone lsf --files-only "${REMOTE}" | grep -E '^ami_trade-[0-9]{8}T[0-9]{6}Z\.sql\.gz\.gpg$' | sort | tail -n1)" \
        || fail "could not list ${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}"
    [[ -n "${NEWEST}" ]] || fail "no backups found in ${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}"
    log "newest backup: ${NEWEST}"
    rclone copyto "${REMOTE}/${NEWEST}" "${WORK}/${NEWEST}" --quiet || fail "download failed"
    BACKUP="${WORK}/${NEWEST}"
fi
BYTES="$(stat -c %s "${BACKUP}" 2>/dev/null || stat -f %z "${BACKUP}")"
phase_end
log "backup file: $(basename "${BACKUP}") (${BYTES} bytes encrypted)"

# 2. Throwaway server
phase_start start_postgres
docker run -d --name "${CONTAINER}" -e POSTGRES_PASSWORD=drill -e POSTGRES_DB="${RESTORE_DB}" \
    "${RESTORE_PG_IMAGE}" >/dev/null || fail "could not start ${RESTORE_PG_IMAGE}"
ready=0
for _ in $(seq 1 60); do
    # The image restarts once during init; require two consecutive successes.
    if docker exec "${CONTAINER}" pg_isready -U postgres -d "${RESTORE_DB}" >/dev/null 2>&1 \
        && sleep 2 && docker exec "${CONTAINER}" pg_isready -U postgres -d "${RESTORE_DB}" >/dev/null 2>&1; then
        ready=1; break
    fi
    sleep 1
done
(( ready == 1 )) || fail "throwaway Postgres never became ready"
phase_end

# 3. Decrypt + restore (one stream, no plaintext on disk)
phase_start decrypt_and_restore
set +e
gpg --batch --quiet --pinentry-mode loopback --decrypt --passphrase-fd 3 "${BACKUP}" 3<<<"${BACKUP_ENCRYPTION_PASSPHRASE}" \
    | gunzip -c \
    | docker exec -i "${CONTAINER}" psql -U postgres -d "${RESTORE_DB}" -v ON_ERROR_STOP=1 -q -o /dev/null
rcs=("${PIPESTATUS[@]}")
set -e
(( rcs[0] == 0 )) || fail "decrypt failed (gpg exit ${rcs[0]}) — wrong passphrase or corrupt file"
(( rcs[1] == 0 )) || fail "gunzip failed (exit ${rcs[1]}) — corrupt dump"
(( rcs[2] == 0 )) || fail "restore reported SQL errors (psql exit ${rcs[2]})"
phase_end

# 4. Sanity checks
phase_start sanity_checks
psql_q() { docker exec "${CONTAINER}" psql -U postgres -d "${RESTORE_DB}" -Atq -c "$1"; }
TABLES="$(psql_q "select tablename from pg_tables where schemaname='public' order by 1")"
TABLE_COUNT="$(grep -c . <<<"${TABLES}" || true)"
(( TABLE_COUNT >= RESTORE_MIN_TABLES )) \
    || fail "only ${TABLE_COUNT} public tables restored (expected >= ${RESTORE_MIN_TABLES})"
ALEMBIC="$(psql_q "select version_num from alembic_version limit 1" 2>/dev/null || true)"
[[ -n "${ALEMBIC}" ]] || fail "alembic_version is empty or missing — the dump is not a full schema"
log "tables: ${TABLE_COUNT}   alembic_version: ${ALEMBIC}"
echo "row counts (non-empty tables):"
NONEMPTY=0
while IFS= read -r t; do
    [[ -z "${t}" ]] && continue
    n="$(psql_q "select count(*) from public.\"${t}\"")"
    if (( n > 0 )) && [[ "${t}" != "alembic_version" ]]; then
        NONEMPTY=$((NONEMPTY + 1))
        printf '  %-40s %s\n' "${t}" "${n}"
    fi
done <<<"${TABLES}"
USERS="$(psql_q "select count(*) from public.users" 2>/dev/null || echo missing)"
[[ "${USERS}" != "missing" ]] || fail "public.users table missing"
if (( NONEMPTY == 0 )); then
    [[ "${RESTORE_REQUIRE_DATA:-0}" != "1" ]] || fail "every data table is empty and RESTORE_REQUIRE_DATA=1"
    log "WARNING — every data table is empty (fine for a brand-new Beta; set RESTORE_REQUIRE_DATA=1 once it has users)"
fi
phase_end

TOTAL=$((SECONDS - DRILL_T0))
log "RESTORE DRILL PASSED — ${PHASES[*]} total=${TOTAL}s users=${USERS} file=$(basename "${BACKUP}")"
