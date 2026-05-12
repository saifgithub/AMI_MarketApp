# Cloudflare Tunnel (A7)

Exposes the on-prem AMI Trade backend to the public internet over a
secure outbound-only TLS tunnel. The Cloudflare edge terminates HTTPS
at the public hostname, runs Access checks (email allowlist for Alpha
testers), and forwards to `localhost:8000` inside `melehost`. The
backend itself never opens an inbound port on the WAN.

This is a **token-mode** (a.k.a. "connector token") tunnel. Ingress
rules, hostname binding, and Access policies are all configured in
the Cloudflare dashboard — `cloudflared` only needs the connector
token to authenticate.

## What's where

| Where | What |
|---|---|
| Cloudflare dashboard (`one.dash.cloudflare.com`) | Tunnel name, hostname (`api-alpha.<domain>`), ingress rule → `http://localhost:8000`, Access policy (email allowlist) |
| `infra/cloudflared/ami-trade-tunnel.service` | systemd unit |
| `infra/cloudflared/ami-trade-tunnel.env.example` | env template → installs to `/etc/ami-trade-tunnel.env` |
| `.env` (root, gitignored) | Same token for local `docker compose --profile tunnel up` |
| `docker-compose.yml` (cloudflared service) | Dev path — uses `CF_TUNNEL_TOKEN` from `.env` |

## One-time setup on melehost (systemd path)

Use this on the production host. The docker-compose path below is fine
for ad-hoc testing but systemd survives reboots cleanly alongside
`ami-trade-backend.service`.

```bash
# 1. Install cloudflared (Ubuntu / Debian)
curl -L --output cloudflared.deb \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
rm cloudflared.deb

# 2. Dedicated service user
sudo useradd --system --no-create-home --shell /usr/sbin/nologin cloudflared

# 3. Install env file + unit
sudo install -m 0600 -o root -g root \
    /opt/ami-trade/infra/cloudflared/ami-trade-tunnel.env.example \
    /etc/ami-trade-tunnel.env
sudo $EDITOR /etc/ami-trade-tunnel.env          # paste the real CF_TUNNEL_TOKEN
sudo install -m 0644 \
    /opt/ami-trade/infra/cloudflared/ami-trade-tunnel.service \
    /etc/systemd/system/ami-trade-tunnel.service

# 4. Start
sudo systemctl daemon-reload
sudo systemctl enable --now ami-trade-tunnel

# 5. Verify
systemctl status ami-trade-tunnel
journalctl -u ami-trade-tunnel -f
# Look for: "Registered tunnel connection" and the connector ID
```

In the Cloudflare dashboard, the tunnel should show 1+ healthy
connectors and the configured hostname should now return 200 from the
backend's `/v1/health`:

```bash
curl https://api-alpha.<your-domain>/v1/health
# → {"status":"ok","version":"0.1.0","env":"prod"}
```

## Local / dev path (docker compose)

```bash
# Put the token in .env (NOT .env.example — that's committed)
echo 'CF_TUNNEL_TOKEN=<real-token-from-CF-dashboard>' >> .env

# Bring up Postgres + Redis + backend + tunnel
docker compose --profile tunnel up -d

# Logs
docker compose logs -f cloudflared
```

## Token hygiene

The connector token grants anyone who holds it the ability to register
as `ami-trade` and answer for the hostname. Treat it like a database
password:

- **Never paste it into `.env.example`** — that file is committed.
- Local: live in `.env` (gitignored).
- Prod: live in `/etc/ami-trade-tunnel.env`, mode `0600`, owner `root`.
- Rotate at the first sign of leak — CF dashboard → tunnel → rotate
  token; update both `.env` and `/etc/ami-trade-tunnel.env`; restart
  the connector(s). Old connectors stop registering and age out.

## CORS / hostname coupling

Once the tunnel is up at e.g. `https://api-alpha.<your-domain>`:

1. Add the hostname to `CORS_ORIGINS` in `/etc/ami-trade.env` so the
   backend accepts Authorization headers from the iPhone build.
2. Rebuild the Flutter app with the cloud-reachable URL baked in
   (A25):
   ```bash
   flutter build ipa --release \
       --dart-define=AMI_API_URL=https://api-alpha.<your-domain> \
       --dart-define=AMI_ENV=prod \
       --dart-define=SENTRY_DSN=...
   ```

## CF Access policy (Alpha)

In the CF dashboard:
- Type: **Self-hosted**
- Application name: `ami-trade-alpha`
- Application domain: same hostname as the tunnel ingress
- Policy: action = **Allow**, include = email → `<tester1@…>, <tester2@…>, …`
- Session duration: 24h is fine for Alpha

That email allowlist is the entire "who can reach the backend" gate
during Alpha. App-level auth (Apple Sign-In + magic-link) gates
`/v1/auth/*` separately once it lands (A4–A6).
