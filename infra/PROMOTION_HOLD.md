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

### CR124-HARDENING — compose now REQUIRES credentials the host has never been given

**Raised:** 2026-08-07 (AT:R66) · **Blocks:** every Alpha promotion carrying `docker-compose.yml` at or after the CR124 commit

**What breaks, precisely.** CR124 replaces the hardcoded `postgres`/`postgres` and unauthenticated
Redis with `${POSTGRES_PASSWORD:?…}`, `${REDIS_PASSWORD:?…}` and `${WEBSITE_DB_PASSWORD:?…}`. Compose
evaluates `:?` at *parse* time, so on a host whose `.env` lacks those keys **every compose command
fails, including `docker compose up -d`**. A promotion that rsyncs this file and recreates the stack
does not degrade — it takes Alpha down and cannot bring it back up until the keys exist.

**Second, independent failure even once the keys exist.** `POSTGRES_PASSWORD` is read by Postgres
**only at first initdb**. melehost's `postgres_data` volume already exists, so the `postgres` role
keeps its current password no matter what the env says. Setting the variable without the matching
`ALTER USER … WITH PASSWORD` leaves the API authenticating with a password the database does not
have. Same shape for `ami_website`, whose role does not exist on that volume at all
(`infra/local/postgres-init/01_website_role.sql` runs on a *fresh* volume only), and for the
`bug_attachments` named volume, which is root-owned and becomes unwritable the moment the API runs as
the non-root `ami` user.

**This hold is not "wait for a build to ship" — it is "run the runbook".** The precondition is
[`infra/CR124_HARDENING_RUNBOOK.md`](CR124_HARDENING_RUNBOOK.md) executed on melehost, in order, in
one window. It is written to be run by hand because every step needs a live database.

**To clear:** record here, measured rather than assumed — (1) `ssh melehost 'ss -ltn'` showing
5434/6379/8001 on `127.0.0.1` only; (2) a psycopg2 connect from the Mac as `postgres`/`postgres`
**failing**; (3) `/v1/health` through the tunnel returning 200 after the recreate; (4) `whoami` in
both app containers returning non-root; (5) a POST to `/v1/feedback/bug` with an attachment
succeeding, which is the one thing the non-root switch can silently break.

**Blocked on, today:** SSH to melehost is down — `~/.ssh/id_ed25519` is passphrase-protected and the
Keychain stopped supplying it (DEF224). Saiful runs `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`;
until then no step of the runbook can execute and this hold cannot be cleared by anyone.

---

## CLEARED HOLDS

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
