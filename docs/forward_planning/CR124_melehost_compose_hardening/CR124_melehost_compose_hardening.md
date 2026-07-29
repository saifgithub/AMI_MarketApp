# CR124 — melehost / compose hardening

## What

Close the LAN-exposed datastore and the container-privilege gaps on melehost. Rolls up
security-review items **C3** (was H3), **N6**, **N7**, **M8**, **M13**, **M14**.

## Why

Proven live this session from an ordinary LAN device (the dev Mac): Postgres reachable as
superuser `postgres`/`postgres` — connected and read all 30 tables (users, magic-link
challenges, journals, mandates) — and Redis answering `PING` with no auth.
`docker-compose.yml:26-31,45-46,210-211,299-300` publish 5434/6379/8000/8001 on `0.0.0.0`
and `[::]`, and Docker bypasses ufw. "Alpaca rows are encrypted" is no defense here: the
`SECRET_KEY` that derives the encryption key sits in the same host's `.env` (see DEF182/N1).
The sibling `n8n` container on the same host already binds `127.0.0.1` — the safe pattern is
known and simply not applied to the AMI stack.

## Scope

1. **Loopback binds** — `127.0.0.1:5434:5432`, `127.0.0.1:6379:6379`, `127.0.0.1:8001:8000`.
   The Cloudflare Tunnel reaches the API over the compose network (`http://api-alpha:8000`),
   so `8000` need not be published on `0.0.0.0` either.
2. **Real Postgres password** via env — kill `postgres`/`postgres`.
3. **Redis `requirepass`.**
4. **Dedicated low-privilege `ami_website` role** (`:286` currently shares the superuser →
   marketing API is a pivot into the app DB). M8.
5. **Network isolation** — put the AMI stack on its own Docker network; evict `n8n` (N6).
6. **Non-root `USER`** in `backend/Dockerfile` and the `website_api` Dockerfile (N7 — both
   run as root today).
7. **`mem_limit`** on every service (unbounded at 14.86 GiB today; supports the DEF184
   body-buffering DoS fix).
8. **Honour `uv.lock`** (`uv sync --locked --no-dev`) + pin images by digest (M14).
9. **Encrypt + `chmod 600` DB backups**, require a password in `infra/backups/pg-backup.sh`
   (M13).

## Acceptance

- From the Mac: `psycopg2.connect(host=melehost,port=5434,user=postgres,password=postgres)`
  **fails**; Redis `PING` from the LAN **refused**.
- `ssh melehost 'ss -ltn'` → 5434/6379/8001 on `127.0.0.1` only.
- `/v1/health` through the tunnel still returns 200 (API reachability preserved).
- `docker inspect` → app containers not on `n8n`'s network; `whoami` in each app container
  is non-root.
- `test_config_compose_parity.py` still green after compose edits.

## Out of scope

Cloudflare edge policy (Access, WAF, security headers) is tracked under CR123 backlog; the
`SECRET_KEY`-rotation prerequisite is DEF182 (must land first).
