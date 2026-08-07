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

**Expect a short outage at step 4, and errors in the window BEFORE it.**

> **Correction (audit MAJOR 2).** An earlier version of this runbook said everything before step 4
> was "additive and safe to run against the live system." **That is wrong, and step 3 is the
> reason.** The currently-running `api-alpha` has `postgres:postgres` as a *hardcoded literal* in
> its container env — it cannot pick up the new password without the recreate in step 4. Postgres
> does not drop open sessions on `ALTER USER … PASSWORD`, so the existing pool keeps working, but
> `session.py` sets no `pool_size`/`pool_pre_ping`, so SQLAlchemy defaults apply
> (`QueuePool`, base 5, overflow 10, no pre-ping). **Any burst past 5 concurrent DB operations
> between step 3 and step 4 opens a fresh connection with the stale password and fails**, surfacing
> as an error to whatever request triggered it.
>
> **Therefore: run steps 3 and 4 back-to-back, in one sitting, at a quiet hour.** Do not run step 3
> and come back later. The SQL ordering itself is correct — the new password is never used before
> it is set — but the gap between them is a live-error window, not a safe pause point.

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

> **Corrected (2026-08-07): verify a credential change OVER THE NETWORK, never via `docker exec`.**
> The first attempt used shell-nested quote escaping and set the password to something other than the
> intended value. `ALTER ROLE` reported success and a `docker exec … psql` check appeared to pass —
> but that check is worthless: `docker exec` reaches Postgres over a local socket where `pg_hba`
> trusts without a password, so `PGPASSWORD` is never exercised. **Only a TCP probe from another
> machine tests the password at all.** Prefer piping SQL via stdin with psql's `:'var'` binding —
> `-c` does not interpolate psql variables:
>
> ```bash
> PGPW=$(grep '^POSTGRES_PASSWORD=' infra/alpha.env | cut -d= -f2-)
> printf "ALTER USER postgres WITH PASSWORD :'pw';\n" \
>   | ssh melehost "docker exec -i ami_postgres psql -v ON_ERROR_STOP=1 -U postgres -d ami_trade -v pw=\"$PGPW\""
> ```
>
> Then prove it from the Mac with `psycopg2.connect(host=192.168.20.59, port=5434, ...)` — the old
> password must fail AND the new one must succeed, both over TCP.

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

> **Corrected after the first real execution (2026-08-07).** Two things below were wrong the first
> time and both failed *silently* — the stack came up healthy while the hardening was absent.

**Ship the Dockerfiles too, not just compose.** CR124 changes `backend/Dockerfile` and
`website_api/Dockerfile`, and those live in melehost's **build context**. Shipping only
`docker-compose.yml` produced containers that still ran as **root** with `HOME=/root` and the dev
dependency group installed — `docker compose ps` said healthy and nothing complained. `uv.lock` must
go too or `uv sync --locked` fails the build.

```bash
scp docker-compose.yml   melehost:~/ami_trade/docker-compose.yml
scp backend/Dockerfile   melehost:~/ami_trade/backend/Dockerfile
scp backend/uv.lock      melehost:~/ami_trade/backend/uv.lock
scp website_api/Dockerfile melehost:~/ami_trade/website_api/Dockerfile
# uv sync --locked fails if the lock has drifted from pyproject — confirm they match first
ssh melehost 'cd ~/ami_trade/backend && sha256sum pyproject.toml uv.lock'
ssh melehost 'cd ~/ami_trade && docker compose config >/dev/null && echo "compose parses"'
```

**Use `--profile tunnel` on the recreate.** `cloudflared` is profile-gated, so a bare
`docker compose up -d` **skips it** — every other service moves to the new `ami_internal` network and
the tunnel is left behind on the old one. That is a **502 on Alpha** until it is reattached, and it is
the single most likely way this runbook takes the site down.

```bash
ssh melehost 'cd ~/ami_trade && docker compose --profile tunnel up -d --build'
ssh melehost "docker inspect ami_tunnel --format '{{range \$k,\$v := .NetworkSettings.Networks}}{{\$k}} {{end}}'"
# must print ami_internal. If you already broke it, `docker network connect ami_internal ami_tunnel`
# restores service immediately — but recreate under the profile afterwards so compose owns it,
# or the manual attach vanishes on the next recreate.
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
