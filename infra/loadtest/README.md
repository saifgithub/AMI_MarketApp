# CR246 — Load-test environment runbook (minihost)

How to deploy, run, and read the backend concurrency load test. The *what and
why* lives in
[`docs/forward_planning/CR246_backend_concurrency_load_testing/test_plan.md`](../../docs/forward_planning/CR246_backend_concurrency_load_testing/test_plan.md);
this file is the *how*.

## Topology

1. **minihost** (192.168.20.14, `ssh minihost`) runs the disposable stack as
   compose project `ami-loadtest`: `ami_loadtest_postgres`,
   `ami_loadtest_redis`, `ami_loadtest_api`. API on LAN port 8000.
2. Code lives at `~/ami_loadtest/` on minihost (rsync target).
3. Secrets live at `~/ami_loadtest/infra/loadtest/.env` on minihost only —
   generated on first deploy, never on the Mac, never in git.
4. The harness is k6, run dockerized on minihost (nothing to install anywhere).

## Deploy / redeploy

```bash
infra/loadtest/deploy.sh        # from the repo root on the Mac
```

Idempotent. Re-running ships current code onto existing data. Full reset:

```bash
ssh minihost "cd ~/ami_loadtest/infra/loadtest && docker compose down -v"
infra/loadtest/deploy.sh
```

## Run the load test

```bash
infra/loadtest/run_loadtest.sh            # defaults: 10 VUs, 20m
VUS=10 DURATION=20m infra/loadtest/run_loadtest.sh
```

This runs `grafana/k6` in a throwaway container on minihost against
`http://api:8000` (the compose-internal address), writes
`~/ami_loadtest/results/<timestamp>/summary.json`, and pulls it back to
`backtest_results/loadtest/<timestamp>/` on the Mac. k6 exits non-zero if the
thresholds break (p99 < 2s, zero 5xx, zero cross-user leaks) — the script
reports but does not stop, so the audits still run.

## Audit correctness (after every run)

```bash
backend/scripts/loadtest_audit.sh
```

Checks the loadtest DB directly: duplicate portfolio rows (the CR246 trigger
race), credit-ledger sums vs balances, referential integrity, connection
high-water. Prints per-check PASS/FAIL and a final `VERDICT:` line; exit code
matches.

## The verdict bar (fixed 2026-09-30 with Saiful)

1. 10 distinct concurrent users, sustained 20 minutes.
2. Zero data corruption, zero cross-user leakage.
3. 5xx rate < 1%.
4. p99 < 2s on all endpoints (mock LLM — a slow endpoint is an app/DB problem).

Result is reported pass / fail / partial in the CR246 folder; any defects
found get their own DEFs.

## Debugging

```bash
ssh minihost "docker logs ami_loadtest_api --tail 100"
ssh minihost "docker exec ami_loadtest_postgres psql -U postgres -d ami_trade -c '\dt'"
curl -s http://192.168.20.14:8000/v1/health
```
