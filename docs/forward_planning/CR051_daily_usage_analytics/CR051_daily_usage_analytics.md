# CR051 — Daily usage analytics report (Alpha)

**Status:** in_progress · **Raised:** 2026-07-21 (AT:R64) · **Owner:** Claude (users-manager role)

## What / Why

Saiful (as the app's user manager) wants a **daily analytics report to watch app-usage
progress** during the stealth alpha. Today the only lens on the alpha DB is
`scripts/users.sh` — point-in-time roster/counts, no trend, no engagement, no reliability.
This CR adds a self-contained **HTML dashboard** generated from the live alpha DB, showing
today-vs-yesterday-vs-7d-avg with sparklines so progress reads at a glance.

Consumption + cadence chosen by Saiful: **HTML dashboard, refreshed daily, with a notify.**

## Scope

`scripts/analytics/daily_report.py` — a read-only generator that:

- Queries `ami_trade` on melehost using the **same SSH + `docker exec … psql` pattern as
  `scripts/users.sh`** (stdin-piped SQL, no shell-quoting of the query). `AMI_SSH_HOST`
  override; `--local` runs `docker exec` directly (for an on-host cron).
- Applies the **synthetic-exclusion convention** (13 CR035 `room-benchmark` rows + the 10
  `2026-05-24 05:10` seed rows) — see `memory/feedback_user_report_exclusions.md`.
- Emits a **self-contained, theme-aware HTML dashboard** (inline CSS + inline SVG
  sparklines; AMI hex/amber chrome; semantic green/red deltas) to `--out`, and prints a
  **compact text summary** to stdout for the notification.

Sections: Headline KPIs (new users · DAU · rooms convened · completion rate, today/yest/7d
+ sparkline) · Acquisition (real total, new today/wk, iOS/Android split, claimed) ·
Activation & engagement (7d-cohort activation, rooms/active-user, median duration, today's
actions) · Retention (DAU/WAU/MAU + stickiness, returning-vs-new) · Reliability (completion
rate, aborted/failed, LLM error rate + p50 latency, open bugs by platform) · Monetization
(plan mix, credits) · Auto-flags (high-convene/low-completion, claimed-with-0-rooms, orphan
runs).

**Timezone:** `Asia/Kuala_Lumpur` (matches `users.sh`).

## Cadence + automation (shipped)

Saiful's call (2026-07-21): **no alerting** — he refreshes/views the HTML on demand — but
**a daily generation crontab on melehost**, built to grow more reports later.

- **First dashboard** published as a private claude.ai **Artifact** for immediate viewing.
- **`scripts/analytics/generate_reports.sh`** — the extensible generation shell. A `reports`
  array (`name | generator | args`) drives it; adding a report = one line + its generator.
  Writes `~/ami_trade/reports/<name>.html` + `.txt` and a dated `archive/` snapshot (60-day
  prune). No notify.
- **melehost host crontab:** `30 23 * * *` (UTC) = **07:30 Asia/Kuala_Lumpur**, appended
  without disturbing the 5 pre-existing crons. Runs on the host (Python 3.14, `saiful` in the
  `docker` group → `--local` uses `docker exec ami_postgres psql` directly).
- **`--local` fix:** the local psql argv is now a clean list (`-F |`), not a shell-split
  string — the SSH path strips the quotes, a direct `subprocess` argv would not. Only the SSH
  path was exercised before; the cron uses `--local`, so this mattered.
- **Viewing:** open `~/ami_trade/reports/daily_usage.html` (scp, or a future CF-Access-gated
  serve route — deferred; the page carries user emails so it must not be public).
- **Notify:** none, by choice. No outbound push/email infra exists anyway (CR043).

## Out of scope

No DB writes. No new backend endpoint / served route (self-hosted dashboard = later). No
schema change. Synthetic rows are excluded, not deleted (Saiful's call, 2026-07-21).

## Acceptance

- `python3 scripts/analytics/daily_report.py --out <file>` produces a valid self-contained
  HTML dashboard from the live alpha DB and a text summary, all figures excluding synthetics.
- Numbers reconcile with `scripts/users.sh` and hand `psql` spot-checks (real total = 36 on
  2026-07-21).
- Dashboard published as an Artifact; Saiful can open it.
