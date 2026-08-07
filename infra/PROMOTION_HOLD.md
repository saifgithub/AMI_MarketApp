# PROMOTION HOLD — do not promote `main` to Alpha

**If this file exists and lists an ACTIVE hold below, `/promote-to-alpha` must ABORT at preflight.**

This file is the structural guard for the case where `main` is green, audited, and still must not
ship — because a backend change depends on a *client* change that hasn't reached devices yet. Backend
promotion is an rsync; a Flutter build is a store release. Those are days apart, and nothing else in
the pipeline notices the gap.

To clear a hold: delete its block, and record in the trail *why* the precondition is now met
(measured, not assumed). An empty holds list means promotion is unblocked.

---

## ACTIVE HOLDS

*(none — promotion is unblocked)*

---

## CLEARED HOLDS

### CR124-HARDENING — compose required credentials the host had never been given

**Raised:** 2026-08-07 (AT:R66) · **CLEARED:** 2026-08-07 (AT:R66) · **Blocked:** every Alpha promotion carrying `docker-compose.yml` at or after the CR124 commit

**Why the precondition is met — measured, not assumed.** `infra/CR124_HARDENING_RUNBOOK.md` was
executed end to end on melehost with Saiful's explicit go-ahead. All five acceptance probes, run
after the final rebuild:

1. **Loopback binds** — `ss -ltn` on melehost: `127.0.0.1:5434`, `127.0.0.1:6379`,
   `127.0.0.1:8001`. No `0.0.0.0`, no `[::]`.
2. **The original exploit is dead.** From the Mac (an ordinary LAN device), `psycopg2.connect(host=192.168.20.59, port=5434, user=postgres, ...)` is refused with **both** the old
   password and the new one; a raw socket `PING` to 6379 gets `ConnectionRefusedError`. Before the
   apply the same two probes returned **35 readable tables** and `+PONG`.
3. **API still serves** — `/v1/health` through the tunnel returns `{"status":"ok",...}`.
4. **Non-root** — `docker exec ami_api_alpha whoami` → `ami`; `ami_website_api` → `amiweb`.
5. **The attachment volume still works** — uid 1001 writes to `/data/bug_attachments` (60 existing
   files preserved), and the DEF201 janitor still reports `scanned 59, would delete 8` as non-root.

Also verified: `HOME=/data` with a writable cache (the audit's MAJOR 3 yfinance fix), `import pytest`
fails inside the image (M14's `--no-dev` really took), `ami_internal` holds only the five AMI
containers, and the website API answers `{"ok":true}` on its new low-privilege `ami_website` role.

**Two things the runbook got wrong, both found by executing it and both now fixed in it:**

- **It shipped only `docker-compose.yml`.** CR124 also changed `backend/Dockerfile` and
  `website_api/Dockerfile`, which live in melehost's *build context* — so the first rebuild produced
  containers that still ran as **root** with `HOME=/root`. Probe 4 caught it. N7, the `HOME` fix and
  `--no-dev` were all silently absent until the Dockerfiles and `uv.lock` were shipped too.
- **`cloudflared` is `profiles: [tunnel]`, so `docker compose up -d` skipped it** — every other
  service moved to the new `ami_internal` network and the tunnel was left on the old one. **Alpha
  returned 502 for about a minute.** Recovered with `docker network connect`, then made durable by
  recreating it under `--profile tunnel` so compose owns the attachment rather than a manual attach
  that would vanish on the next recreate.

**One in-flight defect of my own, worth recording because the first attempt looked like it worked:**
the initial `ALTER USER` used shell-nested quote escaping and set the password to something other
than the intended value. `ALTER ROLE` reported success and a `docker exec` check "passed" — but that
check was worthless, because `docker exec` reaches Postgres over a local socket where `pg_hba` trusts
without a password, so `PGPASSWORD` was never exercised. **Only the network probe from the Mac
revealed the mismatch.** Fixed by piping SQL via stdin with psql's `:'var'` binding (which `-c` does
not interpolate). The lesson is in the runbook now: **verify a credential change over the network,
never through `docker exec`.**

### CR090-ROOM — charging code on `main`, disclosure not on devices

**Raised:** 2026-07-27 (AT:R65) · **CLEARED:** 2026-07-28 (AT:R65) · **Blocked:** any Alpha promotion carrying `backend/app/services/room_runner.py`'s surcharge charge

**Why the precondition is met — measured, not assumed:**

1. Build `0.1.0+56` was uploaded to **both** stores on 2026-07-28: iOS `** EXPORT SUCCEEDED **` →
   App Store Connect "Upload succeeded"; Android `Successfully finished the upload to Google Play`
   (internal track).
2. The `+56` tree **provably contains** the disclosure's only delivery channel. The bump commit is
   `4f9dbfb`; both CR090-MOBILE integration commits are ancestors of it
   (`git merge-base --is-ancestor 5aed494 4f9dbfb` → yes; same for `d3ce06c`), and the two files this
   hold named both carry the parser in that exact tree —
   `git grep -c live_data_notice 4f9dbfb -- mobile/lib/services/api/api_client.dart
   mobile/lib/state/room_providers.dart` → `2` and `3`. This is the tree, not `main`, and not a test run.
3. **Actual install confirmed by Saiful**, 2026-07-28: *"+56 is loaded."* This is the bar the hold set
   — an install on a real device, explicitly not a green `flutter test`.

All three legs of "in testers' hands, confirmed by an actual install" are satisfied, so the hold is
retired rather than waived. Kept here rather than deleted: the next person to raise a hold should be
able to read what clearing one is supposed to cost.

`main` now carries CR090-ROOM (merged at AT:R65, audited COMPLETE r1, zero findings). It debits a
live-data surcharge on every entitled Room run and emits a structural `live_data_notice` SSE event as
the disclosure.

**The disclosure has exactly one delivery channel and it is not on any device yet.** Verified twice,
independently — by the Architect and re-verified by the track-U auditor rather than relayed:

- `mobile/lib/services/api/api_client.dart` and `mobile/lib/state/room_providers.dart` both parse the
  event **only as of CR090-MOBILE**, which is on `main` but **not in any shipped build**.
- The state is **not persisted** — `RoomRun` (`backend/app/schemas/room.py:44-68`) and `RoomRunRow`
  (`backend/app/db/models.py:383-410`) carry `credit_cost` but no live-data field, so a reopened run
  cannot surface it retroactively either.

Promote the backend alone and every Room run costs more with **no explanation anywhere, ever**. That
is CR090's own first acceptance criterion inverted, with a price attached.

**Clear this hold when:** a mobile build containing CR090-MOBILE is in testers' hands (TestFlight +
Play), confirmed by an actual install — not by a green `flutter test`.

**Do NOT clear it by:** reverting the charge, gating it behind a flag nobody flips, or promoting "just
the other files" — the rsync ships the whole tree.
