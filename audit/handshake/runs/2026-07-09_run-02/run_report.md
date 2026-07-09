<!--
Auditor run report — CR004 round 2, run-02 (2026-07-09, session AT:U1).
Re-audit of the architect's remediation of round-1 findings F1-F6.
Owner: AMI Trade AUDITOR (track U).
-->

# CR004 — audit run-02 (round 2)

- **Auditor session:** AT:U1 (track U), 2026-07-09
- **Audited SHA:** `dca45a91d47534aeb45c5b06e783cb9b68c87d72` (round-2 source
  tip — includes F1 fix `6286937` + F4 fix `dca45a9`). Detached scratch
  worktree, not the shared tree.
- **Round-1 verdict re-audited:** AWAITING_FIXES, 1 MAJOR (F1) + F2-F6.

## Per-finding re-audit

### F1 (MAJOR) → FIXED · confirmed
Fix `6286937` adds `award(..., always_record=False)`; when True it skips the
`remaining <= 0` early-return and clamps `granted = min(points, max(remaining,
0))`, writing a **0-point** `reputation_events` row so the once-ever guard
persists even on a capped day. `_grant_milestone()` passes `always_record=True`.
- Read `reputation_service.py:105-191` + `:275-287` — scrutinized for new bugs:
  0-point rows add 0 to the daily-cap sum, add 0 to `user.reputation` and
  `league_members.points`, and default `always_record=False` leaves all 10
  normal award() call-sites unchanged. No regression introduced.
- **Auditor pin re-run** (same file that FAILED in round 1):
  ```
  $ backend/.venv/bin/python -m pytest \
      audit/handshake/regression/test_streak_milestone_cap_pin.py -q -o addopts=""
  1 passed in 0.45s
  ```
  → credits no longer re-grant on a second streak() call. ✅

### F4 (MINOR) → FIXED · confirmed
Fix `dca45a9`: explicit `s.flush()` after the attempt insert, wrapped in
`try/except IntegrityError` → `s.rollback()`, re-read `_stored_attempt`, return
the winner's row with `already_attempted=True`; re-raise if the stored row isn't
found (an unexpected conflict). Read `daily_challenge.py:171-198` — correct: the
rollback discards only the failed insert (award() calls come after), and the
UNIQUE(user, challenge) race now degrades to the intended response, not a 500.

### F2 (MINOR) → DEFERRED · accepted
`DEF039` filed (`docs/defect/def_list.md:75`, status `open`) — partial-unique
index on the dedup anchor, needs migration 0015 + promote. Legitimate deferral
of a MINOR to a tracked defect; app-code dedup unchanged this round.

### F3 (MINOR) → FIXED (doc) · confirmed
Architect lane DoD "Scope discipline" row now acknowledges the DEF038 bundling
into `15a3ebb` (`def_list.md:74`, resolved). Accurate.

### F5 (OBS) → DEFERRED · accepted
`DEF040` filed (`def_list.md:76`, `open`) — mid-week merge doesn't recompute the
adopter's current-week `league_members.points`. Tracked.

### F6 (OBS) → ACCEPTED-RISK · reasonable
`weekly_roll` concurrent-cohort race is unreachable under the single-container
hourly lifespan tick. Sound; re-file if the deployment moves to multiple
workers.

## Regression + live evidence (this round)
```
$ backend/.venv/bin/python -m pytest tests/unit/ -q -o addopts=""
578 passed, 1 warning in 80.81s              # no regression from the fixes

$ curl -s .../v1/health   -> {"status":"ok",...}   # 200
$ curl .../v1/league/{me,standings,history} -> 401 401 401

# melehost DB state — GATED in round 1, REPRODUCED this round:
$ ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -c \
    'SELECT version_num FROM alembic_version; ...'"
alembic_version = c3d4e5f60014
tables present  = daily_challenge_attempts, league_members, leagues, reputation_events (4 rows)
```
→ Migration 0014 is applied on Alpha and all four CR004 tables exist. The
round-1 "Manual verification" gap is now auditor-reproduced. ✅

## Observation carried into COMPLETE (not a bounce)
The F1 fix `6286937` has **no in-suite regression test** (`backend/tests/unit/`);
its coverage is the committed auditor pin under `audit/handshake/regression/`,
which is not on the `pytest backend/tests/unit/` path. Recommend the architect
port a minimal version into `test_reputation_service.py` so the main suite
guards it. MINOR robustness note — the regression IS captured in-repo, so this
does not block COMPLETE.

## NEEDS-DEVICE-CHECK
B1 celebration/haptic runtime behavior — unchanged from round 1; on-device only,
covered by Saiful's acceptance test.

## Verdict
Zero BLOCKER + zero MAJOR (F1 fixed & confirmed; F4/F3 fixed; F2/F5 deferred to
filed open defects; F6 accepted-risk). → **COMPLETE (round 2)**.
