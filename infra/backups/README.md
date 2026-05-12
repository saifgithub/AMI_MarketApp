# Postgres backups + restore drill (A9)

Nightly `pg_dump` against the AMI Trade database, retained for
14 days, optionally rsync'd / rcloned offsite. The drill below restores
a backup into a scratch database — run it once on install and then
quarterly so we know the backups actually work.

## Files

| File | Installs to | Notes |
|---|---|---|
| `pg-backup.sh` | `/opt/ami-trade/infra/backups/pg-backup.sh` | the dump script |
| `ami-trade-pg-backup.service` | `/etc/systemd/system/` | oneshot unit |
| `ami-trade-pg-backup.timer` | `/etc/systemd/system/` | nightly 02:30 UTC |
| `/etc/ami-trade-backup.env` (root-owned, 0640) | — | env overrides |

## One-time install

```bash
# Already cloned at /opt/ami-trade per A8. Make the script executable.
sudo chmod +x /opt/ami-trade/infra/backups/pg-backup.sh

# Install systemd unit + timer
sudo install -m 0644 /opt/ami-trade/infra/backups/ami-trade-pg-backup.service \
    /etc/systemd/system/ami-trade-pg-backup.service
sudo install -m 0644 /opt/ami-trade/infra/backups/ami-trade-pg-backup.timer \
    /etc/systemd/system/ami-trade-pg-backup.timer

# Per-host config (offsite target, retention overrides). Optional.
sudo tee /etc/ami-trade-backup.env > /dev/null <<'EOF'
PG_HOST=localhost
PG_PORT=5434
PG_DB=ami_trade
PG_USER=postgres
PGPASSWORD=postgres
BACKUP_DIR=/var/backups/ami-trade
RETENTION_DAYS=14
# Optional offsite target. Pick ONE:
#   user@host:/path        — rsync over SSH
#   rclone:remote:bucket   — rclone (already configured)
# OFFSITE_TARGET=ami-backup@offsite.example.com:/srv/ami-trade
EOF
sudo chmod 0640 /etc/ami-trade-backup.env
sudo chown root:ami /etc/ami-trade-backup.env

sudo install -d -o ami -g ami -m 0750 /var/backups/ami-trade

# Run once by hand to confirm it works
sudo -u ami /opt/ami-trade/infra/backups/pg-backup.sh
ls -lah /var/backups/ami-trade/

# Enable the nightly timer
sudo systemctl daemon-reload
sudo systemctl enable --now ami-trade-pg-backup.timer
systemctl list-timers ami-trade-pg-backup.timer
```

## Day-to-day

```bash
# Show timer state + next firing
systemctl list-timers ami-trade-pg-backup.timer

# Watch the most recent run
journalctl -u ami-trade-pg-backup -n 100

# Force a backup now (sanity check after a config change)
sudo systemctl start ami-trade-pg-backup.service

# Show retention — anything older than RETENTION_DAYS is pruned each run
ls -lt /var/backups/ami-trade/ | head -20
```

## Restore drill — the only thing that matters

Run this on install and quarterly. A backup you've never restored is
not a backup.

```bash
# 1. Pick a snapshot. The script symlinks the freshest as
#    ami_trade-latest.sql.gz; the timestamped file is the canonical record.
DUMP=/var/backups/ami-trade/ami_trade-latest.sql.gz

# 2. Create a scratch database alongside the real one.
docker exec ami_postgres psql -U postgres -c \
    "CREATE DATABASE ami_trade_restore_test;"

# 3. Stream the dump in.
gunzip -c "${DUMP}" \
    | docker exec -i ami_postgres psql -U postgres -d ami_trade_restore_test

# 4. Spot-check row counts vs prod.
docker exec ami_postgres psql -U postgres -d ami_trade_restore_test \
    -c "SELECT count(*) FROM users, mandates, sim_trades, journal_entries;"

# 5. Tear the scratch DB down.
docker exec ami_postgres psql -U postgres -c \
    "DROP DATABASE ami_trade_restore_test;"
```

The drill must pass before we onboard offsite testers. If step 3 throws
a single error, the backup is broken — investigate before deleting the
scratch DB.

## When Supabase plugs in (Beta)

Supabase has its own PITR + daily snapshot machinery. At Beta we
disable this timer (Supabase covers it) but keep `pg-backup.sh` around
as a defence-in-depth weekly dump to a separate cold-storage bucket.
