# Local dev infrastructure

Docker Compose stack for the AMI Trade backend. Same image and service
shape whether it runs on:

- **Saiful's Mac** (Docker Desktop) — day-to-day iteration without an
  SSH round-trip. `host.docker.internal` is provided for free.
- **`melehost`** (Ubuntu Linux server on the LAN, `192.168.20.9`) —
  the Alpha-phase production host. Plain Docker Engine; the compose
  file's `extra_hosts` line bridges the `host.docker.internal` gap.

See [`docs/08_tech/hosting.md`](../../docs/08_tech/hosting.md) for
the full melehost spec and the systemd-based production launch
covered in [`infra/systemd/`](../systemd/).

## Quick start (from project root)

```bash
# 1. Copy environment template
cp .env.example .env
# Edit .env and fill in at least OPENROUTER_API_KEY and ANTHROPIC_API_KEY

# 2. Bring up the stack
docker compose up -d

# 3. Verify backend is healthy
curl http://localhost:8000/v1/health

# 4. Tear down when done
docker compose down

# To wipe data and start fresh:
docker compose down -v
```

## Components

| Service | Port | Purpose |
|---|---|---|
| `postgres` | 5432 | App database (`ami_trade`) |
| `redis` | 6379 | Cache, rate limits, session state |
| `api-alpha` | 8000 | FastAPI backend (mounts `./backend/app` for hot-reload). Service name matches the public hostname `api-alpha.agenticmarketintel.ai`. |
| `cloudflared` | — | (optional, `--profile tunnel`) Cloudflare Tunnel connector. |

## Cloudflare Tunnel (for HTTPS dev URL)

When you need HTTPS — for Apple Sign-In callbacks, TestFlight,
webhook testing, or simply for offsite testers — start the tunnel
profile:

```bash
# CF_TUNNEL_TOKEN must be in .env (gitignored).
docker compose --profile tunnel up -d
```

Full setup, dashboard config, deployment-shape table, and Beta
retirement runbook live in
[`infra/cloudflared/README.md`](../cloudflared/README.md). The
short version: paste the **connector token** (long base64 starting
with `eyJ...`, NOT the tunnel UUID) into `.env`, then bring the
profile up. The CF dashboard tells the connector what hostname to
serve and what to proxy.

## Running on melehost

melehost is the Ubuntu Linux server on Saiful's LAN at
`192.168.20.9` — see
[`docs/08_tech/hosting.md`](../../docs/08_tech/hosting.md) for the
full spec.

```bash
# From the Mac, push the project
rsync -avz --delete \
  --exclude='.git' --exclude='**/__pycache__' --exclude='**/.dart_tool' \
  "/Volumes/Extreme Pro/AMI_MarketApp/" \
  melehost:~/ami_trade/

# SSH into melehost and run the stack
ssh melehost
cd ~/ami_trade
docker compose up -d
```

For day-to-day dev, simpler: run the stack on the Mac (Docker
Desktop) and only sync to melehost for longer-running tests or
when validating the production launch path.

For the **production** launch on melehost (systemd-managed backend
+ cloudflared, pg backup timer, etc.) see
[`infra/systemd/`](../systemd/) and
[`infra/backups/`](../backups/) — those install runbooks assume the
Ubuntu / `apt` / `dpkg` / `systemctl` toolchain.

## Hot reload

The backend Docker service mounts `./backend/app` read-only. Changes to Python files trigger uvicorn auto-reload. No rebuild needed for most code changes.

When you change `pyproject.toml` or `Dockerfile`, rebuild:

```bash
docker compose up -d --build backend
```

## Database access

```bash
# Connect to postgres
docker compose exec postgres psql -U postgres -d ami_trade

# Run a one-off script
docker compose exec backend python -m app.scripts.your_script
```

## Migration to GCP (W9)

Once we're ready to move to production, see [`docs/10_delivery/timeline.md`](../../docs/10_delivery/timeline.md) for the migration playbook. Short version: `pg_dump` → restore into Supabase Cloud, deploy backend container to Cloud Run, switch DNS via Cloudflare.
