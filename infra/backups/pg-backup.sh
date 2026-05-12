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
PGPASSWORD="${PGPASSWORD:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/ami-trade}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
OFFSITE_TARGET="${OFFSITE_TARGET:-}"   # e.g. user@offsite-host:/path  or  rclone:remote:bucket

export PGPASSWORD

mkdir -p "${BACKUP_DIR}"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTFILE="${BACKUP_DIR}/ami_trade-${TIMESTAMP}.sql.gz"
LATEST_LINK="${BACKUP_DIR}/ami_trade-latest.sql.gz"

echo "[$(date -u +%FT%TZ)] pg_dump → ${OUTFILE}"

pg_dump \
    --host="${PG_HOST}" \
    --port="${PG_PORT}" \
    --username="${PG_USER}" \
    --dbname="${PG_DB}" \
    --format=plain \
    --no-owner \
    --no-privileges \
    | gzip -9 > "${OUTFILE}.tmp"

# Atomic finalise — never leave a half-written file in the rotation
mv "${OUTFILE}.tmp" "${OUTFILE}"
ln -sf "$(basename "${OUTFILE}")" "${LATEST_LINK}"

SIZE_BYTES="$(stat -c %s "${OUTFILE}" 2>/dev/null || stat -f %z "${OUTFILE}")"
echo "[$(date -u +%FT%TZ)] dump complete — ${SIZE_BYTES} bytes"

# Sanity check — fail loudly if the dump is suspiciously small
if (( SIZE_BYTES < 1024 )); then
    echo "[$(date -u +%FT%TZ)] FAIL — dump under 1KB, treating as failure" >&2
    rm -f "${OUTFILE}" "${LATEST_LINK}"
    exit 1
fi

# Prune old dumps
find "${BACKUP_DIR}" \
    -maxdepth 1 \
    -name 'ami_trade-*.sql.gz' \
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
