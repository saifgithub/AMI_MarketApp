# Production launch — systemd + env file + log rotation (A8)

The on-prem Alpha backend runs as a systemd service under a dedicated
user, with env vars in `/etc/ami-trade.env`. This replaces the dev-only
`nohup uvicorn ... &` pattern that's been carrying us through W7–W18.

**Host:** all commands below run on `melehost` — the **Ubuntu Linux**
server on Saiful's LAN at `192.168.20.9`. Specs + role in
[`docs/08_tech/hosting.md`](../../docs/08_tech/hosting.md). The
`apt` / `dpkg` / `systemctl` toolchain is assumed throughout.

## Files

| File | Installs to | Notes |
|---|---|---|
| `ami-trade-backend.service` | `/etc/systemd/system/ami-trade-backend.service` | systemd unit |
| `ami-trade.env.example` | `/etc/ami-trade.env` (rename, mode 0640) | env vars |
| `ami-trade-backend.logrotate` | `/etc/logrotate.d/ami-trade` | aux log rotation |

## One-time setup on melehost

```bash
# 1. Create the service user + checkout location
sudo useradd --system --create-home --home-dir /opt/ami-trade --shell /usr/sbin/nologin ami
sudo install -d -o ami -g ami -m 0755 /opt/ami-trade
sudo install -d -o ami -g ami -m 0750 /var/log/ami-trade

# 2. Clone the repo into /opt/ami-trade
sudo -u ami git clone <repo-url> /opt/ami-trade
sudo -u ami python3.13 -m venv /opt/ami-trade/backend/.venv
sudo -u ami /opt/ami-trade/backend/.venv/bin/pip install -e '/opt/ami-trade/backend[dev]'

# 3. Install env file (mode 0640 — root-readable only)
sudo install -m 0640 -o root -g ami \
    /opt/ami-trade/infra/systemd/ami-trade.env.example /etc/ami-trade.env
sudo $EDITOR /etc/ami-trade.env        # fill in DATABASE_URL, VLLM_*, etc.

# 4. Install the systemd unit
sudo install -m 0644 \
    /opt/ami-trade/infra/systemd/ami-trade-backend.service \
    /etc/systemd/system/ami-trade-backend.service
sudo systemctl daemon-reload
sudo systemctl enable --now ami-trade-backend

# 5. Install logrotate (only needed if anything writes /var/log/ami-trade/*.log)
sudo install -m 0644 \
    /opt/ami-trade/infra/systemd/ami-trade-backend.logrotate \
    /etc/logrotate.d/ami-trade

# 6. Cap journal disk usage (systemd captures backend stdout/stderr)
sudo mkdir -p /etc/systemd/journald.conf.d
echo -e '[Journal]\nSystemMaxUse=500M\nMaxRetentionSec=14day' \
    | sudo tee /etc/systemd/journald.conf.d/50-ami-trade.conf
sudo systemctl restart systemd-journald
```

## Day-to-day

```bash
# Status
systemctl status ami-trade-backend

# Live logs (replaces tail -f /tmp/ami-backend.log)
journalctl -u ami-trade-backend -f

# Reload after editing /etc/ami-trade.env
sudo systemctl restart ami-trade-backend

# Update after `git pull` (in /opt/ami-trade)
sudo -u ami git -C /opt/ami-trade pull
sudo -u ami /opt/ami-trade/backend/.venv/bin/alembic \
    -c /opt/ami-trade/backend/alembic.ini upgrade head
sudo systemctl restart ami-trade-backend
```

Restart-on-failure is wired in the unit (`Restart=on-failure`, 5s
backoff). The unit waits up to 30s for graceful shutdown before SIGKILL
so in-flight SSE streams get a chance to close cleanly.
