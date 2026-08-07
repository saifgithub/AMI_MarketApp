# CR124 — melehost hardening runbook

**Run this on melehost, in order, in one window.** Every step needs a live database, which is why
none of it is automated into `/promote-to-alpha`. Until it has run, `infra/PROMOTION_HOLD.md` carries
an ACTIVE hold and promotion aborts at preflight.

**Prerequisite: SSH works.** As of 2026-08-07 it does not — `~/.ssh/id_ed25519` is passphrase-
protected and the macOS Keychain stopped supplying it (DEF224). On the Mac:

```bash
ssh-add --apple-use-keychain ~/.ssh/id_ed25519   # one passphrase prompt, then done
ssh melehost 'echo ok'
```

**Expect a short outage.** Step 4 recreates the stack. Everything before it is additive and safe to
run against the live system.

---

## Why each step exists

The compose file no longer contains credentials. Three things follow, and each is a *separate*
failure if skipped:

| Skipped | Symptom |
|---|---|
| `.env` keys (step 2) | **every** `docker compose` command fails to parse — the stack cannot start at all |
| `ALTER USER` (step 3) | Postgres keeps its old password; the API authenticates with one the DB does not have |
| volume `chown` (step 6) | API runs as non-root `ami`, cannot write `bug_attachments`; bug reports fail on upload |

`POSTGRES_PASSWORD` is read by Postgres **only at first initdb**. melehost's `postgres_data` volume
already exists, so the environment variable alone changes nothing about the role.

---

## Step 1 — capture the current state (so the rollback is real)

```bash
ssh melehost 'cd ~/ami_trade && cp .env .env.pre-cr124 && cp docker-compose.yml docker-compose.yml.pre-cr124'
ssh melehost 'cd ~/ami_trade && docker compose ps && ss -ltn | grep -E "5434|6379|8001|8000"'
```

Record that `ss` output. It is the before-half of the acceptance evidence.

## Step 2 — generate credentials and put them in `.env`

Generate on the **Mac**, into the gitignored canonical `infra/alpha.env`, so the next promotion
carries them (`infra/alpha.env` is the source of truth; melehost's `.env` is derivative — never
hand-edit it, per CLAUDE.md):

```bash
python3 -c "import secrets;print('POSTGRES_PASSWORD='+secrets.token_urlsafe(32))" >> infra/alpha.env
python3 -c "import secrets;print('REDIS_PASSWORD='+secrets.token_urlsafe(32))"    >> infra/alpha.env
python3 -c "import secrets;print('WEBSITE_DB_PASSWORD='+secrets.token_urlsafe(32))" >> infra/alpha.env
```

Then copy those three lines into melehost's `~/ami_trade/.env` for this run (the promotion that would
normally ship them is held). Keep `POSTGRES_USER` unset — it defaults to `postgres`, and renaming the
superuser is not in scope.

> These are the only secrets in CR124. Do not commit them; `infra/alpha.env` is gitignored and
> `infra/alpha.env.example` carries the shape only.

## Step 3 — rotate the roles **inside the live database**

Still on the OLD stack, which is still running and still using the old password:

```bash
ssh melehost 'cd ~/ami_trade && set -a && . ./.env && set +a && \
  docker exec -e PGPASSWORD=postgres -i ami_postgres psql -U postgres -d ami_trade <<SQL
ALTER USER postgres WITH PASSWORD '"'"'${POSTGRES_PASSWORD}'"'"';
SQL'
```

Then create the low-privilege website role (M8). `ami_website` does not exist on this volume —
`infra/local/postgres-init/01_website_role.sql` only runs on a fresh one:

```bash
ssh melehost 'cd ~/ami_trade && set -a && . ./.env && set +a && \
  docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" -i ami_postgres psql -U postgres -d postgres <<SQL
CREATE ROLE ami_website WITH LOGIN PASSWORD '"'"'${WEBSITE_DB_PASSWORD}'"'"';
ALTER DATABASE ami_website OWNER TO ami_website;
REVOKE ALL ON DATABASE ami_trade FROM ami_website;
REVOKE CONNECT ON DATABASE ami_trade FROM PUBLIC;
GRANT CONNECT ON DATABASE ami_website TO ami_website;
SQL'
```

Verify before going further — the new password must work and the website role must be locked out of
the app DB:

```bash
# new superuser password works
ssh melehost 'cd ~/ami_trade && set -a && . ./.env && set +a && \
  docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" ami_postgres psql -U postgres -d ami_trade -c "select 1"'
# website role CANNOT reach ami_trade — this command must FAIL
ssh melehost 'cd ~/ami_trade && set -a && . ./.env && set +a && \
  docker exec -e PGPASSWORD="${WEBSITE_DB_PASSWORD}" ami_postgres psql -U ami_website -d ami_trade -c "select 1"'
```

## Step 4 — ship the new compose and recreate

Clear the hold in `infra/PROMOTION_HOLD.md` only *after* the acceptance checks below pass; for this
first apply, copy the file directly rather than running the held promotion:

```bash
scp docker-compose.yml melehost:~/ami_trade/docker-compose.yml
ssh melehost 'cd ~/ami_trade && docker compose config >/dev/null && echo "compose parses"'
ssh melehost 'cd ~/ami_trade && docker compose up -d --build'
```

`docker compose config` is the cheap check that step 2 was done: if any of the three keys is missing
it fails here, before anything is torn down.

## Step 5 — evict `n8n`

The AMI services now declare their own `ami_internal` network, so they have already left the project
default network. Confirm `n8n` did not follow them, and detach it if its own compose file names the
network explicitly:

```bash
ssh melehost 'docker inspect ami_internal --format "{{range .Containers}}{{.Name}} {{end}}"'
```

Expect exactly `ami_postgres ami_redis ami_api_alpha ami_website_api` (+ `ami_tunnel` when the tunnel
profile is up). If `n8n` appears, `docker network disconnect ami_internal n8n` and fix its compose
file.

## Step 6 — fix the attachment volume for the non-root user

The API now runs as uid 1001. The existing named volume is root-owned:

```bash
ssh melehost 'docker run --rm -v ami-trade-local_bug_attachments:/d alpine chown -R 1001:1001 /d'
ssh melehost 'docker compose -f ~/ami_trade/docker-compose.yml restart api-alpha'
```

Confirm the volume name first with `docker volume ls | grep bug_attachments` — the project prefix
comes from `name: ami-trade-local` at the top of the compose file.

## Step 7 — backups (M13)

`pg-backup.sh` now refuses to run without a password and without an encryption passphrase:

```bash
ssh melehost 'sudo tee -a /etc/ami-trade-backup.env >/dev/null <<EOF
PGPASSWORD=<the POSTGRES_PASSWORD from step 2>
BACKUP_ENCRYPTION_PASSPHRASE=<generate a fresh one; store it OUTSIDE melehost>
EOF
sudo chmod 600 /etc/ami-trade-backup.env'
ssh melehost 'sudo apt-get install -y gnupg'
ssh melehost 'sudo bash /path/to/pg-backup.sh'   # writes ami_trade-<ts>.sql.gz.gpg
```

**Store the passphrase off melehost.** An encrypted backup whose key lives on the same host it backs
up protects against exactly nothing.

---

## Acceptance — the evidence that clears the hold

Run all five, paste the output into `infra/PROMOTION_HOLD.md` under CLEARED HOLDS:

```bash
# 1. loopback binds only
ssh melehost 'ss -ltn' | grep -E '5434|6379|8001'
# expect 127.0.0.1:<port>, never 0.0.0.0 or [::]

# 2. the original exploit is dead — from the MAC, this must FAIL
python3 -c "
import psycopg2
try:
    psycopg2.connect(host='192.168.20.59', port=5434, user='postgres',
                     password='postgres', dbname='ami_trade', connect_timeout=5)
    print('STILL VULNERABLE')
except Exception as e:
    print('refused:', type(e).__name__)
"
# and Redis, from the Mac
redis-cli -h 192.168.20.59 -p 6379 ping   # expect connection refused

# 3. API still serves
curl -s https://api-alpha.agenticmarketintel.ai/v1/health

# 4. non-root
ssh melehost 'docker exec ami_api_alpha whoami; docker exec ami_website_api whoami'
# expect ami / amiweb, never root

# 5. the thing non-root most likely broke
# submit a bug report WITH a photo attachment from the app, confirm it lands:
ssh melehost 'ls -la /var/lib/docker/volumes/ami-trade-local_bug_attachments/_data/ | tail -3'
```

## Rollback

```bash
ssh melehost 'cd ~/ami_trade && cp docker-compose.yml.pre-cr124 docker-compose.yml && docker compose up -d'
```

The `ALTER USER` from step 3 is **not** undone by that — the old compose has `postgres`/`postgres`
hardcoded and will fail to authenticate. Either also revert the password:

```bash
ssh melehost 'cd ~/ami_trade && set -a && . ./.env && set +a && \
  docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" -i ami_postgres \
  psql -U postgres -d ami_trade -c "ALTER USER postgres WITH PASSWORD '"'"'postgres'"'"';"'
```

…or keep the new password and rollback only the *binds* by editing the pre-CR124 file's `ports:`
lines. The second is strictly better — reverting to a LAN-reachable superuser database restores the
exact vulnerability this CR closed.
