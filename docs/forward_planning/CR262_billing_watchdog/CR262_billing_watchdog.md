<!--
CR262 — billing watchdog: AI-picked detection of CR261 manual-ops incidents
(Saiful 2026-10-18: "can you build it?"). Companion to CR261's manual-ops
catalog — CR261 says WHAT a human must do; this CR automates the DETECTION
and notification so no incident waits for a human to grep logs.
-->

# CR262 — Billing watchdog

**Status:** proposed · **Minted:** 2026-10-18 · **Author:** Kimi (AT:K6)
**Scope:** billing / subscriptions (CR084 stack, CR261 companion)

## What was built (phase 1, 2026-10-18)

A deterministic, no-LLM daily scan that turns CR261's loud-refusal log lines
(entries 1–5) into same-day WhatsApp alerts in the AMI-Chief of Staff group.

### Architecture

```
melehost (where the logs live)                  minihost (where WhatsApp lives)
┌───────────────────────────────┐   forced-command ssh   ┌──────────────────────────┐
│ crontab 06:17 UTC daily       │  (dedicated ed25519    │ authorized_keys:         │
│ revenuecat_error_scan.py      │   key, no-pty, single  │  -> ami-notify-stdin     │
│  └─ docker logs ami_api_alpha │   forced command)      │  -> ami-notify finance   │
│     --since 25h               │ ─────────────────────► │     cos "<incident>"     │
│  └─ dedup vs ~/.ami_billing_  │                        │  -> hermes send (WhatsApp)│
│     watchdog/seen.json (14d)  │                        └──────────────────────────┘
└───────────────────────────────┘
```

Why this direction: melehost's firewall blocks minihost→melehost (no log
pull), while melehost→minihost ssh works and minihost owns the sole sanctioned
proactive path (`ami-notify`). The ssh key is scoped to a single forced
command (`ami-notify-stdin`) whose only capability is relaying lines to the
CoS group as the `finance` persona — no shell, no other targets.

### Files

| Host | Path |
|---|---|
| melehost | `~/ami_billing_watchdog/revenuecat_error_scan.py` |
| melehost | `~/.ami_billing_watchdog/` (seen.json, scan.log, cron.log) |
| melehost | `~/.ssh/ami_billing_watchdog` (keypair) + `~/.ssh/config` Host `minihost-watcher` |
| melehost | crontab: `17 6 * * *` (09:17 Asia/Riyadh) |
| minihost | `~/bin/ami-notify-stdin` (forced-command wrapper) |
| minihost | `~/.ssh/authorized_keys` (scoped entry, last line) |

### Detection signals (calibrated against `backend/app/api/webhooks.py`)

1. structlog: `revenuecat_webhook_secret_unset` (CR261 #3), `revenuecat_webhook_sandbox_in_production` (#4), `revenuecat_webhook_unknown_user` (#5).
2. uvicorn access log: `POST /v1/webhooks/revenuecat` with status 400/401/403/404/422/503 → mapped to CR261 entries #1/#2/#3/#4/#5.

Each new (signal, identity) pair alerts once, then is suppressed for 14 days
(seen-file retention) — a still-ongoing incident re-alerts after retention
prunes it, so nothing nags daily but nothing is forgotten either.

### Verified

1. `--dry-run` against live logs: clean (no billing traffic in 7d, as expected at alpha).
2. Logic test with canned 401×2 / 422 / sandbox lines: 3 incidents, counts and dedup correct.
3. Live e2e: test line delivered to the CoS group as `[finance]` via the forced-command key.

## Deliberate boundaries

1. **No automatic state mutation.** The watchdog never touches `users.plan`,
   allowances, or the RC dashboard. Alerts end with "Reply 'go' to have
   finance proceed" — human-gated, same pattern as the Asana bridge.
2. **No LLM in the loop.** Unattended LLM turns on the personas have a history
   of failing closed (heredoc/execute_code blocks); detection must not depend
   on one. (The `finance` persona can still act on a 'go' interactively.)

## Phase 2 (follow-up, not built)

1. **RC-ledger reconcile cron** (CR261 #6 — the silent lost-event case):
   pull active subscribers via the RevenueCat REST API and diff against the
   `subscription_events` ledger. Needs the RC project + API key staged to
   melehost (secrets source of truth: Mac repo-root `.env`).
2. **Wire the admin revoke/grant endpoint** once it exists (CR261 gaps, entries 7+11) so refund-revocation becomes a 'go'-confirmed action instead of a DB step.
3. **Optional**: route alerts through Angelia for triage before the CoS group (she reads, dedups against her Asana/ops context, forwards) — only if volume justifies it.

## Standing ops

1. Incident handling follows the per-entry playbooks in
   [CR261](CR261_billing_manual_ops.md) — the watchdog only changes HOW
   FAST you learn, not WHAT to do.
2. Log review: `ssh melehost "tail -50 ~/.ami_billing_watchdog/scan.log"`.
3. Key rotation: regenerate `~/.ssh/ami_billing_watchdog` on melehost, update
   the authorized_keys line on minihost (marked by the `ami_billing_watchdog`
   comment tag in the key).
4. On full CR248/CR262 teardown also remove the authorized_keys line, the
   minihost wrapper, and the melehost crontab entry.

## Cross-references

- Incident catalog: [CR261](CR261_billing_manual_ops.md)
- Webhook implementation: `backend/app/api/webhooks.py`
- Provisioning runbook: [CR084 rc_production_runbook.md](../CR084_revenuecat_integration/rc_production_runbook.md)
- Notification path: minihost `~/bin/ami-notify` (CR248, commit 9bfe88b7)
