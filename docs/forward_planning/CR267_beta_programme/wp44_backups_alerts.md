# WP-44 Backups, monitoring, alerts: what is built, what Saiful creates, how to drill

Lane `lane/WP44-backups-alerts`. Everything here is code, config templates and docs. Nothing has run against a real host or bucket: no Beta host exists (gate S4), and the scripts are proven against stubs and a real gpg only.

## 1. What is built

1. **Encrypted nightly backup with an off-server copy.** `infra/backups/pg-backup.sh` already did `pg_dump | gzip | gpg` (AES256, symmetric). Added:
   1. Upload to any S3-compatible bucket (Cloudflare R2) with `rclone`, configured only by env (`BACKUP_S3_ENDPOINT`, `_BUCKET`, `_PREFIX`, `_ACCESS_KEY_ID`, `_SECRET_ACCESS_KEY`, `_PROVIDER`). The four credentials are all-or-nothing. Once set, the upload is mandatory and any failure is fatal.
   2. Size check after upload: the object's size in the bucket must equal the local file's, else exit non-zero.
   3. Remote retention: newest `BACKUP_KEEP_DAILY` (14) plus the newest file of each of the `BACKUP_KEEP_WEEKLY` (8) most recent older ISO weeks. Logic is `infra/backups/retention_select.py` (stdlib). It only ever names files matching `ami_trade-<ts>.sql.gz.gpg`; foreign objects in the bucket are never deleted.
   4. Loud failure: an EXIT trap prints `FAIL` with the exit code, removes any `.tmp`, and POSTs to `BACKUP_ALERT_WEBHOOK_URL` when set. A second path, `ami-trade-pg-backup-failed.service` (systemd `OnFailure=`), covers what a trap cannot see (timeout, SIGKILL). That unit fails itself if the webhook is unset.
   5. No plaintext on disk: the encrypted path streams, so no plaintext file is ever created. With an upload configured, `BACKUP_ALLOW_PLAINTEXT` is ignored and the script refuses to run without a passphrase. The script also refuses to upload anything not ending `.gpg`.
   6. `BACKUP_ENCRYPTION_PASSPHRASE_FILE` (preferred over the env passphrase), `BACKUP_REQUIRE_OFFSITE=1` (fail if no bucket configured), `PG_DOCKER_CONTAINER` (dump through `docker exec ami_postgres pg_dump`, so the client matches the server's major version).
2. **Restore drill.** `infra/backups/pg-restore-drill.sh`: finds the newest object in the bucket (or takes `--file`), downloads it, starts a throwaway `postgres:15-alpine`, streams `gpg | gunzip | psql -v ON_ERROR_STOP=1`, then checks table count (>= 20), `alembic_version`, and prints row counts and one timing per phase (`download`, `start_postgres`, `decrypt_and_restore`, `sanity_checks`, `total`). Removes the container and the temp dir on exit, success or not. It never touches the live database.
3. **Schedule.** `ami-trade-pg-backup.timer` (existing, 02:30 UTC daily, `Persistent=true`) and `.service` (now `TimeoutStartSec=1h`, `OnFailure=`). Env template for Beta: `infra/backups/ami-trade-backup.env.beta.example`.
4. **Operator alerts in the backend.** `backend/app/services/ops_alerts.py`, run every 5 minutes by `app.main._ops_alert_tick`:

   | Signal | Source | Fires when |
   |---|---|---|
   | 5xx rate | `http_audit` | >= `OPS_ALERT_5XX_RATE` (5%) of the last 15 min, with at least 20 requests |
   | LLM spend | `llm_audit` via `llm_spend.todays_spend()` | today's UTC spend >= `OPS_ALERT_SPEND_FRACTION` (80%) of `LLM_DAILY_SPEND_CEILING_USD` |
   | Room failures | `room_runs` | >= `OPS_ALERT_ROOM_FAILURE_RATE` (25%) of Rooms finished in the last 60 min were `failed`, with at least 5 finished |

   Delivery: Sentry message plus a POST of `{"text","content"}` to `OPS_ALERT_WEBHOOK_URL` (Slack, Mattermost and Discord all accept this shape). One alert per kind per hour; the cooldown starts only after a delivered message. A probe whose DB read fails raises its own "unmonitored" alert. Enabled with an empty URL logs an error every pass and one Sentry message per day.
   - The existing `llm_spend` Sentry message at 100% of the ceiling stays; this adds the 80% early warning and a human-reachable channel.
   - Test alert: `docker exec ami_api_alpha python -m app.services.ops_alerts test` (exit 0 only if the webhook returned 2xx). This is WP-44's "a test alert received".
5. **Sentry.** `app/core/observability.py::init_sentry` reads `settings.sentry_dsn` (`SENTRY_DSN`), forwarded by compose. `infra/beta.env.example` already had it `[REQUIRED]`. New: `beta_boot_problems` now refuses `ENV=beta` with an empty DSN (previously an empty DSN was a silent no-op). Mobile DSN stays WP-45's refusal.
6. **Tunnel watchdog.** `infra/watchdog/cf_tunnel_watchdog.sh` is Alpha-specific (hardcoded Alpha hostname, `/home/saiful`, `ami_tunnel`). Reuse for Beta means copying it with the hostname changed to `api-beta.agenticmarketintel.ai` in WP-42. Not done here: it needs the Beta host's paths.

### Settings added (all forwarded in `docker-compose.yml`, all in `infra/beta.env.example`)

| Variable | Default | Beta example file |
|---|---|---|
| `OPS_ALERTS_ENABLED` | `false` | `[REQUIRED]` `true` |
| `OPS_ALERT_WEBHOOK_URL` | empty | `[REQUIRED]` empty, Saiful fills |
| `OPS_ALERT_5XX_RATE` | `0.05` | `[OPTIONAL]` |
| `OPS_ALERT_SPEND_FRACTION` | `0.8` | `[OPTIONAL]` |
| `OPS_ALERT_ROOM_FAILURE_RATE` | `0.25` | `[OPTIONAL]` |

Alpha: off, because the compose default is `false` and no equivalent exists there today.

## 2. What Saiful must create (S4/S5)

1. **R2 bucket** in the Cloudflare account, for example `ami-beta-backups`. No public access. Optional: a lifecycle rule to abort incomplete multipart uploads. Retention is handled by the script.
2. **R2 API token**: Object Read & Write, scoped to that one bucket only. Note the access key id, secret and the account's S3 endpoint `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.
3. **Backup passphrase**: generate on the Beta host (`openssl rand -base64 32` into `/etc/ami-trade-backup.pass`, mode 0600). **Store a copy in the password manager.** Without it every backup is unreadable. Do not store it only on the server it protects.
4. **Alert destination**: one incoming-webhook URL (Slack, Discord or Mattermost). Used for `OPS_ALERT_WEBHOOK_URL` and `BACKUP_ALERT_WEBHOOK_URL` (may be the same). Treat it as a secret.
5. **Sentry**: a Beta project (so release health is clean) and its backend DSN into `SENTRY_DSN`.
6. **External uptime monitor** (section 4), once the hostname exists.

Then on the Beta host (WP-42 follow-up):

```bash
sudo apt install -y rclone gnupg python3
sudo install -m 0640 -o root -g ami /opt/ami-trade/infra/backups/ami-trade-backup.env.beta.example /etc/ami-trade-backup.env   # edit the <...> values
sudo install -m 0644 /opt/ami-trade/infra/backups/ami-trade-pg-backup{,-failed}.service /etc/systemd/system/
sudo install -m 0644 /opt/ami-trade/infra/backups/ami-trade-pg-backup.timer /etc/systemd/system/
sudo usermod -aG docker ami                      # PG_DOCKER_CONTAINER needs it
sudo systemctl daemon-reload && sudo systemctl enable --now ami-trade-pg-backup.timer
sudo systemctl start ami-trade-pg-backup.service && journalctl -u ami-trade-pg-backup -n 40
```

Acceptance check for a failing backup: set a wrong `BACKUP_S3_SECRET_ACCESS_KEY`, start the service, confirm a `FAIL` line and a webhook message, restore the key.

## 3. Restore drill procedure (WP-44 acceptance: one drill recorded with timings)

Run on the Beta host, or any machine with docker, gpg, rclone and the env file. It does not touch the live database.

```bash
set -a; . /etc/ami-trade-backup.env; set +a
bash /opt/ami-trade/infra/backups/pg-restore-drill.sh        # newest object in the bucket
# or a local copy:
bash /opt/ami-trade/infra/backups/pg-restore-drill.sh --file /var/backups/ami-trade/ami_trade-latest.sql.gz.gpg
```

Pass criteria: exit 0 and a final line `RESTORE DRILL PASSED — download=..s start_postgres=..s decrypt_and_restore=..s sanity_checks=..s total=..s users=N file=...`. Copy that line, the encrypted file size it prints, and the date into the "Drill record" section below. Once Beta has users, run it with `RESTORE_REQUIRE_DATA=1` so an empty restore fails. Repeat quarterly and after any change to the schema tooling, the passphrase or the bucket.

Failure reading: `decrypt failed` = wrong passphrase or damaged file; `restore reported SQL errors` = the dump is broken, treat the backup chain as unsafe; `only N public tables` = partial dump.

### Drill record

| Date | Backup file | Size | download | start_postgres | decrypt_and_restore | sanity | total | Result |
|---|---|---|---|---|---|---|---|---|
| (pending: needs the Beta host and bucket) | | | | | | | | |

## 4. External uptime check (docs only; nothing created)

An in-server check cannot see "the whole host or the tunnel is down", so this must run elsewhere. Probe **`/v1/ready`**, not just `/v1/health`: `/v1/health` is liveness only and returns 200 while Postgres is down (its own docstring says so); `/v1/ready` returns 503 when a gating dependency fails and, unauthenticated, exposes only the verdict. Alert on a non-200 or on `env` not equal to `beta`.

1. **Cloudflare Worker with a Cron Trigger** (preferred: same vendor as the tunnel and R2, covered by the credits per `cloudflare_options_2026-11-19.md` section 5). A Worker with `triggers.crons = ["* * * * *"]` or `*/2 * * * *` runs `scheduled()`:

   ```js
   export default {
     async scheduled(_event, env, ctx) {
       let bad = null;
       try {
         const r = await fetch("https://api-beta.agenticmarketintel.ai/v1/ready", { signal: AbortSignal.timeout(8000) });
         const j = await r.json().catch(() => ({}));
         if (r.status !== 200 || j.ready !== true || j.env !== "beta") bad = `ready check: HTTP ${r.status}, env=${j.env}, failed=${(j.failed_probes || []).join(",")}`;
       } catch (e) { bad = `unreachable: ${e.name}`; }
       if (bad) ctx.waitUntil(fetch(env.ALERT_WEBHOOK_URL, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text: `[AMI beta] ${bad}`, content: `[AMI beta] ${bad}` }) }));
     },
   };
   ```

   Store `ALERT_WEBHOOK_URL` with `wrangler secret put`. It alerts on every failing minute; add a Workers KV or Durable Object flag if that is too noisy. Check current Cron Trigger limits and the Workers plan on Cloudflare's pricing page before relying on it (not re-verified in this lane).
2. **Free third-party monitor** (simplest: no code). UptimeRobot, Better Stack or similar free tiers poll an HTTPS URL every few minutes and notify by email or webhook. Configure: URL `https://api-beta.agenticmarketintel.ai/v1/ready`, expect 200 and keyword `"ready":true`. Free-tier intervals and limits change; confirm at signup.
3. **Both** is reasonable: the vendor-independent monitor catches a Cloudflare-side outage that would also silence the Worker.

## 5. What is left

1. S4: provision the host, create the bucket, token, passphrase and webhook (section 2), install the units, run the first real backup and the first drill, fill in the Drill record.
2. S4: copy `infra/watchdog/cf_tunnel_watchdog.sh` for the Beta hostname and paths.
3. S5: set up the external monitor (section 4); run `ops_alerts test` and record that a message arrived.
4. Not exercised anywhere yet: real R2 behaviour (rclone with `provider=Cloudflare`, `RCLONE_S3_NO_CHECK_BUCKET`, `lsf --format s`) and a real Postgres 15 restore. The shims prove the script logic and gpg round trip; the first run on the host is the real test.
5. Alerts are evaluated per container process; on a single-container Beta that is correct. Running more than one API container would send duplicates (cooldown is in-process).
