# Alpha-host infrastructure (Docker Compose)

Docker Compose stack for the AMI Trade backend on **melehost** (Ubuntu
Linux server on Saiful's LAN, `192.168.20.59`). See
[`docs/08_tech/hosting.md`](../../docs/08_tech/hosting.md) for the
full melehost spec, and
[`docs/10_delivery/promotion_protocol.md`](../../docs/10_delivery/promotion_protocol.md)
for how code reaches it.

**The Mac is not a deployment target.** Mac is pure editor — no
backend, no DB, no compose stack. Every change ships to melehost
via [`/promote-to-alpha`](../../.claude/commands/promote-to-alpha.md)
to be exercised. Backend unit tests on the Mac use the sqlite
tempfile fixture in `backend/tests/conftest.py` — no Postgres
needed for them.

The compose file's `extra_hosts: ["host.docker.internal:host-gateway"]`
line on the cloudflared service is what lets the same dashboard
ingress rule work on plain Docker Engine (melehost) — Docker Desktop
provides that hostname for free, Docker Engine does not.

## Quick start (on melehost)

```bash
# 0. Code reaches melehost via /promote-to-alpha, which rsyncs the Mac
#    worktree to ~/ami_trade/. The .env file lives at ~/ami_trade/.env
#    on melehost (gitignored on the Mac, scp'd over by the promotion).
ssh melehost
cd ~/ami_trade

# 1. Bring up the stack (with the public-tunnel profile)
docker compose --profile tunnel up -d

# 2. Verify health from inside the LAN
curl http://localhost:8000/v1/health

# 3. Verify health from outside (through the tunnel)
curl https://api-alpha.agenticmarketintel.ai/v1/health

# 4. Tear down when done (state persists in named volumes)
docker compose --profile tunnel down

# To wipe data and start fresh:
docker compose --profile tunnel down -v
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

## How code reaches melehost

Use [`/promote-to-alpha`](../../.claude/commands/promote-to-alpha.md).
That handles the rsync + recreate + smoke-check end to end. Manual
rsync is reserved for emergencies — see
[`docs/10_delivery/promotion_protocol.md`](../../docs/10_delivery/promotion_protocol.md).

For the **production** launch on melehost (systemd-managed backend
+ cloudflared, pg backup timer, etc.) see
[`infra/systemd/`](../systemd/) and
[`infra/backups/`](../backups/) — those install runbooks assume the
Ubuntu / `apt` / `dpkg` / `systemctl` toolchain.

## Hot reload

The `api-alpha` service mounts `./backend/app` and `./backend/tests`
read-only. Changes to Python files trigger uvicorn auto-reload — but
only for code that was rsync'd over via the promotion script. Mac
edits don't reach the container until you `/promote-to-alpha`.

When `pyproject.toml` or `Dockerfile` changes, the image needs to
rebuild — the promotion script does this with `--build api-alpha`.

## Database access

```bash
# Connect to postgres (from inside melehost)
docker compose exec postgres psql -U postgres -d ami_trade

# Run a one-off script
docker compose exec backend python -m app.scripts.your_script
```

## Migration to GCP (W9)

Once we're ready to move to production, see [`docs/10_delivery/timeline.md`](../../docs/10_delivery/timeline.md) for the migration playbook. Short version: `pg_dump` → restore into Supabase Cloud, deploy backend container to Cloud Run, switch DNS via Cloudflare.
