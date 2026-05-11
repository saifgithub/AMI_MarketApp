# Local dev infrastructure

Configuration for the local Docker Compose stack running on melehost (or any Docker host).

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
| `backend` | 8000 | FastAPI (mounts `./backend/app` for hot-reload) |
| `cloudflared` | — | (optional) Cloudflare Tunnel for HTTPS access |

## Cloudflare Tunnel (for HTTPS dev URL)

When you need HTTPS — for Apple/Google OAuth callbacks, TestFlight, webhook testing — start the tunnel profile:

```bash
docker compose --profile tunnel up -d
```

You need to set `CF_TUNNEL_TOKEN` in your `.env` first. Get it by:

1. Sign in to https://one.dash.cloudflare.com/
2. Networks → Tunnels → Create a tunnel
3. Choose "Cloudflared" connector
4. Copy the tunnel token (begins with `eyJ...`)
5. Add Public Hostname route: `api-dev.agenticmarketintel.ai` → `http://backend:8000`
6. Save

Your local stack is now reachable at `https://api-dev.agenticmarketintel.ai` over real HTTPS. No port forwarding needed.

## Running on melehost

If running on melehost (192.168.20.59) rather than your Mac:

```bash
# From your Mac, push the project
rsync -avz --delete \
  --exclude='.git' --exclude='**/__pycache__' --exclude='**/.dart_tool' \
  "/Volumes/Extreme Pro/AMI_MarketApp/" \
  melehost:~/ami_trade/

# SSH into melehost and run the stack
ssh melehost
cd ~/ami_trade
docker compose up -d
```

For day-to-day dev, simpler: run the stack on your Mac (Docker Desktop) and only sync to melehost for longer-running tests.

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
