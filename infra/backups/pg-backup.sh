#!/usr/bin/env bash
# A9 — Postgres backup script for AMI Trade.
#
# Runs pg_dump against the local Postgres (docker container on host port
# 5434, or a direct host install if you swap PG_HOST / PG_PORT), gzips the
# dump, drops it in a dated file under $BACKUP_DIR, prunes anything older
# than $RETENTION_DAYS, and (optionally) rsyncs the latest snapshot to
# $OFFSITE_TARGET so a single-machine fire doesn't lose everything.
#
# Configure via env or /etc/ami-trade-backup.env. Defaults aim at the
# Docker compose stack the W8 commit landed.
#
# Run by hand (sanity check after install):
#   bash infra/backups/pg-backup.sh
#
# Run on a timer — see infra/backups/ami-trade-pg-backup.{service,timer}
# and the README in this directory.
#
# Restore drill — see infra/backups/README.md (the restore command is the
# whole point of running these backups).

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

# CR124/M13 — the password no longer has a default.
#
# `PGPASSWORD="${PGPASSWORD:-postgres}"` silently used the superuser default,
# so this script kept working after the C3 rotation only because the rotation
# had not happened. Refuse rather than emit an empty/failed dump that the timer
# reports as success.
if [[ -z "${PGPASSWORD:-}" ]]; then
    echo "[$(date -u +%FT%TZ)] FAIL — PGPASSWORD unset. Set it in /etc/ami-trade-backup.env (CR124/M13)." >&2
    exit 1
fi
export PGPASSWORD

# CR124/M13 — dumps are encrypted at rest.
#
# A plaintext dump of this database is every user record, magic-link challenge
# and mandate in one file, and it is rsynced OFFSITE below. Symmetric age/gpg
# encryption keeps the offsite copy useless without the key.
#   BACKUP_ENCRYPTION_PASSPHRASE  — required unless BACKUP_ALLOW_PLAINTEXT=1
#   BACKUP_ALLOW_PLAINTEXT=1      — explicit, logged opt-out for a local drill
BACKUP_ENCRYPTION_PASSPHRASE="${BACKUP_ENCRYPTION_PASSPHRASE:-}"
BACKUP_ALLOW_PLAINTEXT="${BACKUP_ALLOW_PLAINTEXT:-0}"

if [[ -z "${BACKUP_ENCRYPTION_PASSPHRASE}" && "${BACKUP_ALLOW_PLAINTEXT}" != "1" ]]; then
    echo "[$(date -u +%FT%TZ)] FAIL — BACKUP_ENCRYPTION_PASSPHRASE unset and BACKUP_ALLOW_PLAINTEXT!=1." >&2
    echo "  A plaintext dump is the whole user table; refusing to write one by default (CR124/M13)." >&2
    exit 1
fi

if [[ -n "${BACKUP_ENCRYPTION_PASSPHRASE}" ]] && ! command -v gpg >/dev/null 2>&1; then
    echo "[$(date -u +%FT%TZ)] FAIL — gpg not installed but encryption requested (CR124/M13)." >&2
    exit 1
fi

mkdir -p "${BACKUP_DIR}"
# Directory itself is private, not just the files in it — a listing leaks the
# backup cadence and the retention window.
chmod 700 "${BACKUP_DIR}"

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
    pg_dump \
        --host="${PG_HOST}" \
        --port="${PG_PORT}" \
        --username="${PG_USER}" \
        --dbname="${PG_DB}" \
        --format=plain \
        --no-owner \
        --no-privileges \
        | gzip -9 \
        | gpg --batch --symmetric --cipher-algo AES256 \
              --passphrase-fd 3 --output "${OUTFILE}.tmp" \
              3<<<"${BACKUP_ENCRYPTION_PASSPHRASE}"
else
    pg_dump \
        --host="${PG_HOST}" \
        --port="${PG_PORT}" \
        --username="${PG_USER}" \
        --dbname="${PG_DB}" \
        --format=plain \
        --no-owner \
        --no-privileges \
        | gzip -9 > "${OUTFILE}.tmp"
fi

# Atomic finalise — never leave a half-written file in the rotation
mv "${OUTFILE}.tmp" "${OUTFILE}"
chmod 600 "${OUTFILE}"
ln -sf "$(basename "${OUTFILE}")" "${LATEST_LINK}"

SIZE_BYTES="$(stat -c %s "${OUTFILE}" 2>/dev/null || stat -f %z "${OUTFILE}")"
echo "[$(date -u +%FT%TZ)] dump complete — ${SIZE_BYTES} bytes"

# Sanity check — fail loudly if the dump is suspiciously small
if (( SIZE_BYTES < 1024 )); then
    echo "[$(date -u +%FT%TZ)] FAIL — dump under 1KB, treating as failure" >&2
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

# Offsite copy — best-effort, don't fail the timer if the remote is down
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
