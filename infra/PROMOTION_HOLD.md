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

### DEF294-CLIENT — the quiz reveal would mark correct answers WRONG on every installed build

**Raised:** 2026-08-15 (AT:R70) · **Blocks:** any Alpha promotion at or after `badf6a6f`

**Why.** DEF294 (`badf6a6f`) stops `GET /v1/lessons/{id}` from shipping the quiz answer key, and
moves the reveal onto the graded submit response. Both halves are on `main`. **Only the backend half
ships by rsync.** Every device in the field is running a build whose parser is
`answerIndex: ((j['answer_index'] as num?) ?? 0).toInt()`.

**This is not a degraded reveal, it is an inverted one.** Against the new backend `answer_index` is
absent, so an old client reads **0** for every question. `LessonQuizCard._icon` then draws
`check_circle` on option 0 and `cancel` on the user's own selection whenever they picked anything
else. A user who answers a question correctly with option 2 is shown their answer marked **red** and
option 0 marked **green**. Grading itself is server-side and stays correct — score, pass and the
agent unlock are all right — so the app awards the unlock while telling the user they got it wrong.
Nothing errors and nothing logs.

The explanation disappears at the same time (it was read off the question too), so the reveal loses
its teaching content on a build whose whole purpose is teaching.

**This is the exact case this file exists for**, and it was created by the fix rather than found by
it: DEF294's own row records that a server-only ship *"silently degrades to option 0 is always
correct — a leak closed on one side producing a wrong answer on the other, with nothing failing."*
Writing the fix and then promoting only the half that fits down the rsync would have shipped that
sentence.

**Scope note.** `/promote-to-alpha` ships the whole tree, so this blocks **every** lane, including
DEF300/DEF246/DEF220 in the same batch — none of which have a client dependency. If one of those is
urgent, the honest options are to cut a client release first, or to revert `badf6a6f`'s two backend
files and promote the rest. Do not promote past this by reasoning that the other three are safe.

**To clear:** a Flutter release carrying `badf6a6f`'s client half must be **on devices**, not merely
built — TestFlight/Play rollout complete, or the CR121 client release floor raised to that build so
older clients cannot reach the lesson reader at all. Record the build number and how it was
confirmed (store status or a `last_app_version` query), measured rather than assumed.

---

## CLEARED HOLDS

### DEF302-REMEASURE — live corpus run in flight on this exact container

**Raised:** 2026-08-14 (AT:R69) · **CLEARED:** 2026-08-14 (AT:R69) · **Blocked:** any Alpha promotion while the DEF302 re-measurement corpus was running

**Why.** A 39-convene epoch is running live against `alpha-2026-08-14-3` / `913f3b59` to test whether
DEF302's rendering fix changed anything in the agents' prose. The comparison is only meaningful if
every convene in it saw the same prompt bytes — that is CR179 Leg 5's whole method and DEF230's
mix-shift warning applied to code rather than tickers.

**This is not hypothetical right now.** `main` is already ahead of Alpha with **DEF303**
(`5279c721`), which raises `conservative_debator`'s decode cap 800 → 1300. That is a change to the
output of one of the twelve agents being measured. An rsync mid-run would put part of the epoch on
one cap and part on another, and nothing downstream would be able to tell which turns came from
which — the corpus would silently stop being a controlled comparison while still looking like one.

`/promote-to-alpha` ships the whole tree, so this blocks *every* lane's promotion, not just this
one. If something urgent needs to ship, say so and the run will be abandoned and restarted rather
than split.

**To clear:** confirm from `room_runs`/`llm_audit` (not the runner's JSONL — see the CR179-LEG5 hold
below for why) that the epoch is complete, then record the container's `RestartCount` and `version`
at the first and last convene showing one code state throughout.

**Why the precondition is met — measured from the database, not the runner.** 39 convenes, all
`completed`, **13 tickers × 3** with no ticker at 2 or 4, 468 turns with all twelve agents at exactly
39. Window `2026-08-14 10:59:01Z → 13:29:20Z`. `ami_api_alpha`: **`RestartCount=0`**, `StartedAt
2026-08-14T10:22:28Z` — *before* the window opened — `version 913f3b59` / `alpha-2026-08-14-3` and
`Health=healthy` at the end. **One code state served the entire corpus**, which is exactly what the
hold was raised for.

**Two things this hold caught that a file count would not have**, both the same lesson as the
CR179-LEG5 hold below, and both worth writing down because the hold is only as good as the check that
clears it:

1. **Two convenes the runner recorded as `script_error` had completed backend-side.** Round 2's ANET
   and round 3's BAC. Re-running either on the runner's word would have put a **14th convene into a
   13×3 design** — and it would have looked like diligence.
2. **A time-windowed export was contaminated.** Querying `room_runs` over the corpus window returned
   **SCHF and VSS**, neither in the 13-ticker set: other traffic on a live box. The export is
   filtered by **batch user**, not by time. An epoch carrying tickers outside the held-constant set is
   DEF230's mix-shift with extra steps, and nothing downstream would have flagged it.

---

### CR179-LEG5 — live corpus run in flight on this exact container

**Raised:** 2026-08-14 (AT:R68) · **CLEARED:** 2026-08-14 (AT:R68) · **Blocked:** any Alpha promotion while CR179 Leg 5's corpus was running

**Why the precondition is met — measured, not assumed.** The run is complete and the corpus is the
shape the methodology required, verified from the database rather than from the runner's own log:
**39 convenes, all `completed`, 13 tickers × 3, 468 turns with all twelve agents at exactly 39.**
`ami_api_alpha` served the entire window on one code state — `RestartCount 0`, `StartedAt
2026-08-13T23:04:38Z`, `version c79d873c` / `alpha-2026-08-14-1` at both the first and last convene —
so no promotion split the corpus and the hold did the job it was raised for.

**One thing this hold caught that the file count would not have.** Three convenes recorded
`script_error` in the runner's JSONL (`ReadTimeout`, `ConnectError [Errno 64] Host is down`,
`ConnectTimeout`) — Mac→LAN transport blips, not backend faults. Querying `room_runs` showed **two of
the three had completed backend-side**; only AVGO never reached the API. Re-running all three on the
JSONL's word would have produced two 24h-dedup **cache hits** counted as fresh convenes. The corpus
of record is the database, not the runner's bookkeeping.

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
