# Cloudflare Tunnel (A7)

Exposes the on-prem AMI Trade backend to the public internet over a
secure outbound-only TLS tunnel. The Cloudflare edge terminates HTTPS
at the public hostname, runs Access checks (email allowlist for Alpha
testers), and forwards to `localhost:8000` inside `melehost`. The
backend itself never opens an inbound port on the WAN.

**Host context:** `melehost` is the **Ubuntu Linux** server on
Saiful's LAN at `192.168.20.59` — see
[`docs/08_tech/hosting.md`](../../docs/08_tech/hosting.md) for the
full spec. Everything below assumes Ubuntu + Docker Engine + systemd
in production. Docker Desktop on the dev Mac works too; the compose
file's `extra_hosts` line bridges the Docker Engine vs Docker
Desktop difference so the same dashboard ingress rule works on
either host.

This is a **token-mode** (a.k.a. "connector token") tunnel. Ingress
rules, hostname binding, and Access policies are all configured in
the Cloudflare dashboard — `cloudflared` only needs the connector
token to authenticate.

## Where to point the tunnel (CF dashboard ingress rule)

Token-mode tunnels are **remotely-managed** — the connector
authenticates with the token, and the Cloudflare dashboard tells it
what to proxy where. Nothing in this repo configures the ingress; it
all lives at:

> [one.dash.cloudflare.com](https://one.dash.cloudflare.com/) → **Networks** → **Tunnels** → `ami-trade` → **Public Hostname** tab → **Add a public hostname**

Fill it in like this:

| Field | Value |
|---|---|
| Subdomain | `api-alpha` (or whatever you want) |
| Domain | your CF-managed domain |
| Path | leave blank |
| Service — Type | `HTTP` |
| Service — URL | depends on deployment shape — see below |

**Service URL by deployment shape:**

| If the tunnel runs as… | Service URL | Why |
|---|---|---|
| **Compose tunnel + Compose backend** (`docker compose --profile tunnel up -d` — full stack) | `http://api-alpha:8000` | Both containers share the Compose network; `api-alpha` is the backend service name in `docker-compose.yml` (chosen to match the public hostname). The cleanest long-term shape. |
| **Compose tunnel + host backend** (cloudflared container, backend running on the host as systemd / uvicorn / etc.) | `http://host.docker.internal:8000` | The compose file's cloudflared service declares `extra_hosts: host.docker.internal:host-gateway`, so this name resolves to the host on plain Docker Engine (Linux) as well as Docker Desktop (Mac/Windows). |
| **Systemd tunnel + host backend** (production launch on melehost via the systemd units in this directory) | `http://localhost:8000` | Both processes on the same host; backend binds `0.0.0.0:8000`. No Docker, no DNS magic. |
| **Systemd tunnel + Compose backend** | `http://localhost:8000` | Backend container publishes `8000:8000` to the host, where systemd's cloudflared can reach it. |

Use **`http://`**, not `https://`. TLS terminates at the Cloudflare
edge; the tunnel-to-backend hop is plain HTTP over the encrypted
tunnel. The backend doesn't need its own cert.

Under "Additional application settings": defaults are fine.
The HTTP Host Header should be **blank** (default) — Cloudflare
forwards the public hostname, which is what FastAPI's
ProxyHeadersMiddleware uses to build absolute URLs.

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

## Two deployment shapes — pick one

The tunnel can run two ways. The codebase ships both because the
backend itself has two deployment shapes (Docker compose today, plain
systemd on bare-metal hosts). Whichever shape the backend uses,
match the tunnel to it:

| Backend runs as | Tunnel runs as | When to choose |
|---|---|---|
| `docker compose up -d backend` | `docker compose --profile tunnel up -d` (cloudflared container) | **Default.** One stack, one set of commands, simplest to retire at Beta. |
| `ami-trade-backend.service` (systemd, A8) | `ami-trade-tunnel.service` (systemd, this file) | Bare-metal host without Docker, or operators who prefer systemd's restart semantics over Compose. |

Don't run both. They both register against the same token and will
race for connector slots on the Cloudflare side. The Docker path is
recommended unless there's a reason to avoid Compose.

## Decommission at Beta (when GCP Cloud Run lands)

Cloudflare Tunnel is an Alpha-only piece. The reason it exists is that
the backend lives on-prem behind NAT, so the public internet can't
reach `melehost:8000` directly. Cloud Run hands you a public HTTPS
endpoint, so the tunnel becomes redundant.

The retirement is a DNS swap, not a rebuild. The iPhone TestFlight
build points at `https://api-alpha.<your-domain>` (the Cloudflare
hostname), not at the tunnel itself — repointing that hostname to
Cloud Run keeps every installed build working.

Sequence at Beta:

1. **Deploy backend to Cloud Run** (project plan: B2 / B3). You get
   back a `https://ami-trade-prod-<hash>.run.app` URL.
2. **Map the public hostname**. Either:
   - **Keep Cloudflare in front** — change the existing DNS record
     for `api-alpha.<your-domain>` from `CNAME → <tunnel-id>.cfargotunnel.com`
     to `CNAME → ami-trade-prod-<hash>.run.app`. CF Access policy
     stays in place (still gates by email allowlist for testers).
   - **Or skip Cloudflare** — use Cloud Run's custom-domain mapping
     directly so the hostname resolves straight to GCP. Drop CF
     Access; rely on app-level auth (A4-A6) for gating.
3. **Verify** — `curl https://api-alpha.<your-domain>/v1/health`
   from outside the LAN returns 200 from Cloud Run.
4. **Stop the connector** on melehost:
   ```bash
   # Docker compose path:
   docker compose --profile tunnel down cloudflared

   # OR systemd path:
   sudo systemctl disable --now ami-trade-tunnel
   sudo rm /etc/systemd/system/ami-trade-tunnel.service /etc/ami-trade-tunnel.env
   sudo systemctl daemon-reload
   ```
5. **Delete the tunnel in the CF dashboard** — Networks → Tunnels →
   ami-trade → Delete. The connector token in `.env` /
   `/etc/ami-trade-tunnel.env` is now worthless; clear it from both.
6. **Trim the codebase** — drop the `cloudflared` service from
   `docker-compose.yml`, drop `infra/cloudflared/`, drop the
   `CF_TUNNEL_TOKEN` slot from `.env.example` and
   `infra/systemd/ami-trade.env.example`. One commit.

The Flutter app **doesn't need a rebuild** because the
`--dart-define=AMI_API_URL=https://api-alpha.<your-domain>` baked into
the TestFlight build still resolves — just to a different IP now.
That's the whole point of using a domain we control as the public
boundary instead of the tunnel's own `*.cfargotunnel.com` hostname.

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
