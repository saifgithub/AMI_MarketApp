# CF-tunnel watchdog — DEF402

## What

`cf_tunnel_watchdog.sh` probes public Alpha
(`https://api-alpha.agenticmarketintel.ai/v1/health`) on a short timeout. If
that fails, it probes the origin directly
(`http://localhost:8000/v1/health`, melehost-local). **Only** when the
origin is healthy and the public hostname is not — i.e. the fault is
provably the Cloudflare connector, not the backend — it runs
`docker restart ami_tunnel` and appends a dated record to the log. A
10-minute cooldown blocks repeat restarts (a persistent CF-edge outage
would otherwise get "fixed" every 2 minutes forever, for no benefit). The
healthy path logs a heartbeat line too, so "is the watchdog actually
running" is answerable from the log alone. Script errors (missing `curl`,
etc.) are logged, never swallowed — CR040 "degrade loudly".

## Why (DEF402)

On 2026-09-03 the `ami_tunnel` container's retry loop wedged twice.
`docker ps` kept reading `Up 2 days` the whole time — container status is
not a usable signal. Public Alpha served 530 for minutes while the origin
answered 200 on the LAN. It surfaced only because an unrelated release
gate (DEF195 parity check) happened to hit `/openapi.json` and failed
closed. `docker restart ami_tunnel` fixed it instantly both times. This
guard is the second occurrence of "public Alpha down, backend healthy"
(DEF070 was the first, and is a different failure mode — QUIC flapping,
fixed by forcing HTTP/2; a wedged connector does not reconnect on its
own the way a flapping one does, so DEF070's fix does not cover this).
Second occurrence ⇒ a guard, not another point fix (`failure_patterns.md`).
It cannot prevent the wedge; it bounds the outage to the probe interval
and turns an invisible failure into a counted one.

Full incident writeup: `docs/defect/_registry/DEF402.row.md`.

## Install (melehost, user `saiful`)

```bash
mkdir -p /home/saiful/watchdog
scp infra/watchdog/cf_tunnel_watchdog.sh saiful@<melehost>:/home/saiful/watchdog/
ssh saiful@<melehost> "chmod +x /home/saiful/watchdog/cf_tunnel_watchdog.sh"

# Append (never replace) to the user crontab — every 2 minutes:
( crontab -l 2>/dev/null; echo "*/2 * * * * /home/saiful/watchdog/cf_tunnel_watchdog.sh" ) | crontab -
```

Log: `/home/saiful/watchdog/cf_tunnel_watchdog.log`.
Cooldown state file: `/home/saiful/watchdog/.last_restart_epoch` (holds
the epoch seconds of the last restart; absent = never restarted).

## Env overrides

| Var | Default | Notes |
|---|---|---|
| `PUBLIC_HEALTH_URL` | `https://api-alpha.agenticmarketintel.ai/v1/health` | |
| `ORIGIN_HEALTH_URL` | `http://localhost:8000/v1/health` | melehost-local, unauthenticated |
| `RESTART_CMD` | `docker restart ami_tunnel` | override for testing, e.g. `echo RESTART-WOULD-FIRE` |
| `LOG_FILE` | `<script dir>/cf_tunnel_watchdog.log` | |
| `STATE_FILE` | `<script dir>/.last_restart_epoch` | |
| `COOLDOWN_SECONDS` | `600` (10 min) | |
| `CURL_TIMEOUT_SECONDS` | `10` | |

## Testing (never restart the live container)

Real run in healthy conditions → expect `OK public=200`, no restart.

Forced decision-branch test — fault is provably the connector — without
touching the real container:

```bash
PUBLIC_HEALTH_URL="http://127.0.0.1:1/v1/health" \
RESTART_CMD="echo RESTART-WOULD-FIRE" \
LOG_FILE=/tmp/wd_test.log STATE_FILE=/tmp/wd_state \
  ./cf_tunnel_watchdog.sh
```

`127.0.0.1:1` is unroutable (nothing listens on port 1), so the public
probe fails fast while the real origin answers normally — same
provable-connector-fault branch the real wedge takes, with zero risk to
the live tunnel. Re-run within 10 minutes to see the cooldown branch log
`action=none reason=cooldown`.
