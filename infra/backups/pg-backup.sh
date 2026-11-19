#!/usr/bin/env bash
# A9 — Postgres backup script for AMI Trade.
#
# Runs pg_dump against the local Postgres (docker container on host port
# 5434, or a direct host install if you swap PG_HOST / PG_PORT), gzips the
# dump, encrypts it, drops it in a dated file under $BACKUP_DIR, prunes anything
# older than $RETENTION_DAYS, and (optionally) copies it off the server so a
# single-machine fire doesn't lose everything.
#
# Configure via env or /etc/ami-trade-backup.env. Defaults aim at the
# Docker compose stack the W8 commit landed.
#
# CR267 WP-44 (Beta): off-server copy to an S3-compatible bucket (Cloudflare R2)
# through rclone, configured ONLY by env (BACKUP_S3_*). When the four BACKUP_S3_*
# credentials are set the upload is MANDATORY: any failure (upload, size check,
# retention) exits non-zero with a FAIL line, and posts to BACKUP_ALERT_WEBHOOK_URL
# if set. A dump is never written in plaintext when an upload is configured, and
# the encrypted pipeline never writes plaintext to disk at all (pg_dump | gzip |
# gpg streams). Remote retention keeps BACKUP_KEEP_DAILY newest + BACKUP_KEEP_WEEKLY
# weekly (retention_select.py). BACKUP_REQUIRE_OFFSITE=1 makes a missing BACKUP_S3_*
# a failure (set it on Beta).
#
# Run by hand (sanity check after install):
#   bash infra/backups/pg-backup.sh
#
# Run on a timer — see infra/backups/ami-trade-pg-backup.{service,timer}
# and the README in this directory.
#
# Restore drill — infra/backups/pg-restore-drill.sh (the restore is the whole
# point of running these backups).

set -euo pipefail

if [[ -f /etc/ami-trade-backup.env ]]; then
    # shellcheck disable=SC1091
    source /etc/ami-trade-backup.env
fi

PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5434}"
PG_USER="${PG_USER:-postgres}"
PG_DB="${PG_DB:-ami_trade}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/ami-trade}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
OFFSITE_TARGET="${OFFSITE_TARGET:-}"   # e.g. user@offsite-host:/path  or  rclone:remote:bucket

# CR267 WP-44. Run pg_dump inside this container instead of with a host client,
# so the client always matches the server major version. Empty = host pg_dump
# over PG_HOST/PG_PORT.
PG_DOCKER_CONTAINER="${PG_DOCKER_CONTAINER:-}"

# CR267 WP-44 — S3-compatible off-server copy (Cloudflare R2). All-or-nothing.
BACKUP_S3_ENDPOINT="${BACKUP_S3_ENDPOINT:-}"             # https://<account>.r2.cloudflarestorage.com
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:-}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-pg}"               # folder inside the bucket
BACKUP_S3_ACCESS_KEY_ID="${BACKUP_S3_ACCESS_KEY_ID:-}"
BACKUP_S3_SECRET_ACCESS_KEY="${BACKUP_S3_SECRET_ACCESS_KEY:-}"
BACKUP_S3_PROVIDER="${BACKUP_S3_PROVIDER:-Cloudflare}"   # rclone s3 provider name
BACKUP_KEEP_DAILY="${BACKUP_KEEP_DAILY:-14}"
BACKUP_KEEP_WEEKLY="${BACKUP_KEEP_WEEKLY:-8}"
BACKUP_REQUIRE_OFFSITE="${BACKUP_REQUIRE_OFFSITE:-0}"
BACKUP_ALERT_WEBHOOK_URL="${BACKUP_ALERT_WEBHOOK_URL:-}" # JSON {"text","content"} on failure
BACKUP_ENCRYPTION_PASSPHRASE_FILE="${BACKUP_ENCRYPTION_PASSPHRASE_FILE:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTFILE=""

log_fail() { echo "[$(date -u +%FT%TZ)] FAIL — $*" >&2; }

# One exit path for every failure: remove any half-written dump, then tell the
# operator. The EXIT trap fires on `set -e` aborts and explicit `exit 1` alike,
# so no step can fail without this line.
cleanup_and_alert() {
    local rc=$?
    [[ -n "${OUTFILE}" ]] && rm -f "${OUTFILE}.tmp"
    if (( rc != 0 )); then
        log_fail "pg-backup exited ${rc} on $(hostname)"
        if [[ -n "${BACKUP_ALERT_WEBHOOK_URL}" ]]; then
            local msg="AMI backup FAILED on $(hostname) (exit ${rc})"
            curl -fsS --max-time 10 -H 'Content-Type: application/json' \
                -d "{\"text\":\"${msg}\",\"content\":\"${msg}\"}" \
                "${BACKUP_ALERT_WEBHOOK_URL}" >/dev/null 2>&1 \
                || echo "[$(date -u +%FT%TZ)] could not post the failure alert to the webhook" >&2
        fi
    fi
}
trap cleanup_and_alert EXIT

# CR124/M13 — the password no longer has a default.
#
# `PGPASSWORD="${PGPASSWORD:-postgres}"` silently used the superuser default,
# so this script kept working after the C3 rotation only because the rotation
# had not happened. Refuse rather than emit an empty/failed dump that the timer
# reports as success.
if [[ -z "${PGPASSWORD:-}" ]]; then
    log_fail "PGPASSWORD unset. Set it in /etc/ami-trade-backup.env (CR124/M13)."
    exit 1
fi
export PGPASSWORD

# CR124/M13 — dumps are encrypted at rest.
#
# A plaintext dump of this database is every user record, magic-link challenge
# and mandate in one file, and it is copied OFFSITE below. Symmetric gpg
# encryption keeps the offsite copy useless without the key.
#   BACKUP_ENCRYPTION_PASSPHRASE       — required unless BACKUP_ALLOW_PLAINTEXT=1
#   BACKUP_ENCRYPTION_PASSPHRASE_FILE  — same, read from a file (CR267; preferred)
#   BACKUP_ALLOW_PLAINTEXT=1           — explicit, logged opt-out for a local drill
BACKUP_ENCRYPTION_PASSPHRASE="${BACKUP_ENCRYPTION_PASSPHRASE:-}"
BACKUP_ALLOW_PLAINTEXT="${BACKUP_ALLOW_PLAINTEXT:-0}"

if [[ -z "${BACKUP_ENCRYPTION_PASSPHRASE}" && -n "${BACKUP_ENCRYPTION_PASSPHRASE_FILE}" ]]; then
    if [[ ! -s "${BACKUP_ENCRYPTION_PASSPHRASE_FILE}" ]]; then
        log_fail "BACKUP_ENCRYPTION_PASSPHRASE_FILE=${BACKUP_ENCRYPTION_PASSPHRASE_FILE} is missing or empty."
        exit 1
    fi
    BACKUP_ENCRYPTION_PASSPHRASE="$(<"${BACKUP_ENCRYPTION_PASSPHRASE_FILE}")"
fi

# CR267 WP-44 — off-server config is all-or-nothing.
OFFSITE_S3=0
s3_set=0
for v in BACKUP_S3_ENDPOINT BACKUP_S3_BUCKET BACKUP_S3_ACCESS_KEY_ID BACKUP_S3_SECRET_ACCESS_KEY; do
    [[ -n "${!v}" ]] && s3_set=$((s3_set + 1))
done
if (( s3_set == 4 )); then
    OFFSITE_S3=1
elif (( s3_set > 0 )); then
    log_fail "BACKUP_S3_* partly set — need all of BACKUP_S3_ENDPOINT, BACKUP_S3_BUCKET, BACKUP_S3_ACCESS_KEY_ID, BACKUP_S3_SECRET_ACCESS_KEY."
    exit 1
elif [[ "${BACKUP_REQUIRE_OFFSITE}" == "1" ]]; then
    log_fail "BACKUP_REQUIRE_OFFSITE=1 but no BACKUP_S3_* configured — a backup that never leaves the server is not a backup."
    exit 1
fi
if (( OFFSITE_S3 == 1 )); then
    if [[ -z "${BACKUP_ENCRYPTION_PASSPHRASE}" ]]; then
        log_fail "off-server upload needs encryption: set BACKUP_ENCRYPTION_PASSPHRASE or BACKUP_ENCRYPTION_PASSPHRASE_FILE (BACKUP_ALLOW_PLAINTEXT is ignored for uploads)."
        exit 1
    fi
    for tool in rclone python3; do
        command -v "${tool}" >/dev/null 2>&1 || { log_fail "${tool} not installed but BACKUP_S3_* is configured."; exit 1; }
    done
fi

if [[ -z "${BACKUP_ENCRYPTION_PASSPHRASE}" && "${BACKUP_ALLOW_PLAINTEXT}" != "1" ]]; then
    log_fail "BACKUP_ENCRYPTION_PASSPHRASE unset and BACKUP_ALLOW_PLAINTEXT!=1."
    echo "  A plaintext dump is the whole user table; refusing to write one by default (CR124/M13)." >&2
    exit 1
fi

if [[ -n "${BACKUP_ENCRYPTION_PASSPHRASE}" ]] && ! command -v gpg >/dev/null 2>&1; then
    log_fail "gpg not installed but encryption requested (CR124/M13)."
    exit 1
fi

mkdir -p "${BACKUP_DIR}"
# Directory itself is private, not just the files in it — a listing leaks the
# backup cadence and the retention window.
chmod 700 "${BACKUP_DIR}"

run_pg_dump() {
    if [[ -n "${PG_DOCKER_CONTAINER}" ]]; then
        docker exec -e PGPASSWORD "${PG_DOCKER_CONTAINER}" pg_dump \
            --username="${PG_USER}" --dbname="${PG_DB}" \
            --format=plain --no-owner --no-privileges
    else
        pg_dump \
            --host="${PG_HOST}" \
            --port="${PG_PORT}" \
            --username="${PG_USER}" \
            --dbname="${PG_DB}" \
            --format=plain \
            --no-owner \
            --no-privileges
    fi
}

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if [[ -n "${BACKUP_ENCRYPTION_PASSPHRASE}" ]]; then
    SUFFIX="sql.gz.gpg"
else
    SUFFIX="sql.gz"
    echo "[$(date -u +%FT%TZ)] WARNING — writing a PLAINTEXT dump (BACKUP_ALLOW_PLAINTEXT=1)." >&2
fi
OUTFILE="${BACKUP_DIR}/ami_trade-${TIMESTAMP}.${SUFFIX}"
LATEST_LINK="${BACKUP_DIR}/ami_trade-latest.${SUFFIX}"

echo "[$(date -u +%FT%TZ)] pg_dump → ${OUTFILE}"

# umask so the .tmp is never briefly world-readable between creation and chmod.
umask 077

if [[ -n "${BACKUP_ENCRYPTION_PASSPHRASE}" ]]; then
    # `set -o pipefail` (set above) makes a pg_dump or gpg failure fail the
    # whole pipeline rather than leaving a truncated, "successful" dump.
    run_pg_dump \
        | gzip -9 \
        | gpg --batch --symmetric --cipher-algo AES256 \
              --passphrase-fd 3 --output "${OUTFILE}.tmp" \
              3<<<"${BACKUP_ENCRYPTION_PASSPHRASE}"
else
    run_pg_dump | gzip -9 > "${OUTFILE}.tmp"
fi

# Atomic finalise — never leave a half-written file in the rotation
mv "${OUTFILE}.tmp" "${OUTFILE}"
chmod 600 "${OUTFILE}"
ln -sf "$(basename "${OUTFILE}")" "${LATEST_LINK}"

SIZE_BYTES="$(stat -c %s "${OUTFILE}" 2>/dev/null || stat -f %z "${OUTFILE}")"
echo "[$(date -u +%FT%TZ)] dump complete — ${SIZE_BYTES} bytes"

# Sanity check — fail loudly if the dump is suspiciously small
if (( SIZE_BYTES < 1024 )); then
    log_fail "dump under 1KB, treating as failure"
    rm -f "${OUTFILE}" "${LATEST_LINK}"
    exit 1
fi

# Prune old dumps. Both suffixes are pruned regardless of which one this run
# wrote — a host that has switched to encryption still has plaintext dumps from
# before the switch, and leaving those to age out forever defeats the change.
find "${BACKUP_DIR}" \
    -maxdepth 1 \
    \( -name 'ami_trade-*.sql.gz' -o -name 'ami_trade-*.sql.gz.gpg' \) \
    -type f \
    -mtime "+${RETENTION_DAYS}" \
    -print -delete

# CR267 WP-44 — S3-compatible off-server copy. Unlike the legacy block below,
# every failure here is fatal (the EXIT trap alerts): the backup is not done
# until a byte-for-byte size match is confirmed in the bucket.
if (( OFFSITE_S3 == 1 )); then
    [[ "${OUTFILE}" == *.gpg ]] || { log_fail "refusing to upload an unencrypted file"; exit 1; }
    export RCLONE_S3_PROVIDER="${BACKUP_S3_PROVIDER}"
    export RCLONE_S3_ENDPOINT="${BACKUP_S3_ENDPOINT}"
    export RCLONE_S3_ACCESS_KEY_ID="${BACKUP_S3_ACCESS_KEY_ID}"
    export RCLONE_S3_SECRET_ACCESS_KEY="${BACKUP_S3_SECRET_ACCESS_KEY}"
    export RCLONE_S3_REGION="${RCLONE_S3_REGION:-auto}"
    export RCLONE_S3_NO_CHECK_BUCKET=true   # object-scoped R2 tokens cannot create buckets
    export RCLONE_S3_ENV_AUTH=false
    REMOTE=":s3:${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX#/}"
    REMOTE="${REMOTE%/}"
    NAME="$(basename "${OUTFILE}")"
    echo "[$(date -u +%FT%TZ)] upload → ${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX#/}/${NAME}"
    UP_START=$SECONDS
    rclone copyto "${OUTFILE}" "${REMOTE}/${NAME}" --quiet \
        || { log_fail "upload failed (rclone copyto)"; exit 1; }
    REMOTE_SIZE="$(rclone lsf --format s "${REMOTE}/${NAME}" 2>/dev/null | head -n1 | tr -d '[:space:]')" || REMOTE_SIZE=""
    if [[ "${REMOTE_SIZE}" != "${SIZE_BYTES}" ]]; then
        log_fail "uploaded size '${REMOTE_SIZE}' != local ${SIZE_BYTES} for ${NAME}"
        exit 1
    fi
    echo "[$(date -u +%FT%TZ)] upload verified — ${SIZE_BYTES} bytes in $((SECONDS - UP_START))s"

    LISTING="$(rclone lsf --files-only "${REMOTE}")" \
        || { log_fail "remote retention listing failed"; exit 1; }
    TO_DELETE="$(python3 "${SCRIPT_DIR}/retention_select.py" \
        --daily "${BACKUP_KEEP_DAILY}" --weekly "${BACKUP_KEEP_WEEKLY}" <<<"${LISTING}")" \
        || { log_fail "remote retention selection failed"; exit 1; }
    while IFS= read -r old; do
        [[ -z "${old}" ]] && continue
        echo "[$(date -u +%FT%TZ)] remote prune ${old}"
        rclone deletefile "${REMOTE}/${old}" --quiet \
            || { log_fail "could not delete ${old} from the bucket"; exit 1; }
    done <<<"${TO_DELETE}"
fi

# Legacy offsite copy — best-effort, don't fail the timer if the remote is down
if [[ -n "${OFFSITE_TARGET}" ]]; then
    echo "[$(date -u +%FT%TZ)] offsite copy → ${OFFSITE_TARGET}"
    if [[ "${OFFSITE_TARGET}" == rclone:* ]]; then
        REMOTE="${OFFSITE_TARGET#rclone:}"
        rclone copy "${OUTFILE}" "${REMOTE}" --quiet || \
            echo "[$(date -u +%FT%TZ)] offsite copy failed (rclone) — leaving local copy in place" >&2
    else
        rsync -az "${OUTFILE}" "${OFFSITE_TARGET}/" || \
            echo "[$(date -u +%FT%TZ)] offsite copy failed (rsync) — leaving local copy in place" >&2
    fi
fi

echo "[$(date -u +%FT%TZ)] done"
