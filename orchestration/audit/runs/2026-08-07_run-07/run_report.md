# Run report — 2026-08-07_run-07

Item: CR095, round 1. SHA: `1520f50e`. Verdict: **AWAITING_FIXES (round 1)** — 3 MAJOR
total, 0 BLOCKER, 0 MINOR. Full findings in `orchestration/audit/cr/CR095.auditor.md`
(1 in the original round-1 body, 2 added as this session's addendum).

## Collision with a concurrent auditor pass

`orchestration/audit/cr/CR095.auditor.md` and `orchestration/audit/cr/INDEX.md` were
read before starting any measurement (per PROTOCOL). `INDEX.md` still showed CR095 as
`AWAITING_AUDIT`, but a concurrent track-U instance (`AT:U66`) had already committed and
pushed `61687969 audit(CR095): AWAITING_FIXES round 1` — confirmed on `origin/main` via
`git fetch origin main && git log --oneline origin/main -5` before writing anything.
That pass found 1 MAJOR (a timezone-only `PUT /v1/daily_challenge/reminder` silently
clears `daily_reminder_hour`) and cleared everything else, including once-per-day/
restart-survival, unreachable-user counting, timezone-degrade, `notify(attempt_push=)`,
the migration, and compose parity.

Independently reproduced that same MAJOR before reading their write-up in detail
(confirmed via a standalone repro script — see below) — same root cause, same fix
direction. Then ran my own adversarial pass on the two properties the task brief
prioritized highest (double-send under a tz change, double-send under concurrency) that
the prior pass's "Everything else — verified directly, holds" section did not exercise.
Found both genuinely reproduce. Folded as an addendum into the same lane file rather
than duplicate-committing, matching this repo's own established convention for this
exact situation (CR131 r1, CR141 r1, CR124 r3, CR132 r1 today).

## Setup

```
cd "/Volumes/Extreme Pro/AMI_MarketApp"
git worktree add .claude/worktrees/audit-CR095 1520f50e
cd .claude/worktrees/audit-CR095/backend
```

## Regression suite (independent, scratch worktree, absolute interpreter)

```
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
2612 passed, 13 warnings in 301.42s (0:05:01)
```

Exact match to the submission's claimed `2612 passed, 13 warnings in 295.84s` (measured
in the architect's shared tree, per DEF159 caveat they themselves flagged) and to
`AT:U66`'s prior scratch-worktree measurement.

## Finding 1 (corroborates AT:U66) — timezone-only PUT clears the hour

Independent repro script against the real endpoint, real DB session, before reading the
prior pass's write-up:

```
after set: {'daily_reminder_hour': 8, 'timezone': 'Asia/Riyadh'}
after tz-only update: {'daily_reminder_hour': None, 'timezone': 'Asia/Kuala_Lumpur'}
stored hour: None stored tz: Asia/Kuala_Lumpur
```

Same root cause identified independently: `row.daily_reminder_hour =
req.daily_reminder_hour` is unconditional in `app/api/daily_challenge.py`'s
`set_reminder_preference`, while `timezone`'s write is guarded
(`if req.timezone is not None:`). Pydantic can't distinguish "field omitted" from
"field sent as null" on `Optional[int] = None`, so a timezone-only PUT zeroes the hour.
Added `backend/tests/unit/test_cr095_reminder_hour_omitted_disables_pin.py` (not yet in
`AT:U66`'s pass) pinning this exact repro as a real pytest case.

## Finding 2 (new) — same-day timezone change causes a second reminder

`backend/tests/unit/test_cr095_timezone_change_double_send_pin.py`. User reminded once
at `2026-06-01T10:05Z` (tz=UTC, hour=10, `source_ref="2026-06-01"`). Timezone changed to
`Pacific/Kiritimati` (UTC+14). Next tick `2026-06-01T20:05Z` — still the same real UTC
calendar day, only 10 hours later — resolves to local `2026-06-02 10:05` under the new
tz, a `local_date` with no existing notification row, so the user is reminded a second
time. `1 passed` — reproduces the double-send on the real `send_due_reminders` path, no
internal mocking of the logic under test. Root cause: `_already_reminded_today`'s dedupe
key is recomputed from the user's *current* `timezone` column on every tick, with no
memory of what timezone produced a prior reminder's `source_ref`.

## Finding 3 (new) — concurrent ticks double-send; no DB-level guard

`backend/tests/unit/test_cr095_concurrent_ticks_double_send_pin.py`. Widened the real
TOCTOU window (a `time.sleep(0.4)` inside the genuine `_already_reminded_today`, after
its real query returns, not a fake) so two real threads calling `send_due_reminders()`
concurrently both observe "not yet reminded" before either writes:

```
1 passed
# both ticks: sent_email=1 each -> 2 emails, 2 NotificationRow rows, same user,
# same source_ref, 0 errors
```

Confirmed by reading `app/db/models.py:528` (`NotificationRow`) that there is no unique
constraint on `(user_id, type, source_ref)` — only 2 unrelated indexes. `notify()`'s
write is a plain INSERT, no `ON CONFLICT`, no lock. Confirmed by reading `Dockerfile`
(`CMD ["uvicorn", "app.main:app", ...]`, no `--workers`) and `docker-compose.yml`
(`container_name: ami_api_alpha`, single service instance, no `deploy.replicas`) that
today's melehost topology happens to make this unreachable in steady state — but that is
an operational fact the code doesn't enforce, contradicted by
`main.py::_daily_reminder_tick`'s own docstring claiming "no risk of a double-send"
unconditionally.

## DST correctness — checked, holds (no new finding)

Empirical trace against `zoneinfo`, America/New_York, 2026 US transitions:

```
spring-forward (2026-03-08): 01:00 UTC-5 -> 03:00 UTC-4 directly (hour "2" skipped on
  the wall clock). The code's `local_now.hour < user.daily_reminder_hour` check uses
  >=, not ==, so a reminder targeting hour=2 fires at the next tick after 03:00 —
  delayed by at most one 900s interval, never skipped.
fall-back (2026-11-01): 01:00 occurs twice (UTC-4 then UTC-5) but `local_date` stays
  2026-11-01 for both -- the SECOND occurrence's `_already_reminded_today` check finds
  the row from the first and correctly skips. No double-fire.
```

Matches the shipped test `test_invalid_timezone_falls_back_to_utc_loudly_...` in spirit
(day-boundary correctness) though DST specifically wasn't in either pass's committed
test suite — recorded as verified-by-reasoning-and-trace, not pinned (property already
holds structurally from the `>=` comparison + `local_date`-keyed dedupe; no code change
needed).

## IDOR, rejected-write-nothing, notify() keyword-only — re-checked, hold

- IDOR: `get_current_user` resolves from a Bearer token via `parse_scaffold_token`,
  no `user_id` anywhere in `ReminderPreference` or the route signature — confirmed no
  spoof surface. `AT:U66`'s pin (`test_a_user_can_only_write_their_own_row`) still
  covers this; didn't find a way to defeat it.
- Rejected request writes nothing: bad-timezone check runs *before* `get_session()` is
  opened; out-of-range hour is rejected by Pydantic `ge=0, le=23` before the route body
  executes at all — confirmed no partial-write path exists.
- `notify(..., *, attempt_push: bool = True)` — confirmed keyword-only via the `*` in
  the signature; grepped every call site of `notify(` in `app/` (`price_alert_evaluator.py`
  and `daily_reminder.py` only) — none passes a 6th positional argument, none could
  collide with `attempt_push`. CR027's "notify() is the only writer, row write
  unconditional" guarantee holds for every existing caller.

## Pins added this round (all 3, plus the DEF141 guard update)

Written into the scratch worktree first (verified pass), then copied into the shared
checkout `backend/tests/unit/` and added to `MIGRATED_PINS` in
`test_def141_audit_pins_are_collected.py`:

```
$ cd "/Volumes/Extreme Pro/AMI_MarketApp/backend"
$ "/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest \
    tests/unit/test_cr095_concurrent_ticks_double_send_pin.py \
    tests/unit/test_cr095_timezone_change_double_send_pin.py \
    tests/unit/test_cr095_reminder_hour_omitted_disables_pin.py \
    tests/unit/test_def141_audit_pins_are_collected.py -v
5 passed in 1.13s
```

Full suite also re-run in the shared checkout after copying the 3 new files there:
`2618 passed, 13 warnings in 312.28s`. **Not cited as CR095 evidence** (DEF159) — by the
time it finished, a concurrent track-R session had landed uncommitted work in the same
shared tree (`git status` shows `app/middleware/version_gate.py`,
`app/schemas/client_release_floor.py`, `app/services/client_release_floor.py` +
modified `admin.py`/`config.py`/`db/models.py`/`main.py`, none of it CR095's or mine),
which accounts for the +6 over the scratch-worktree's `2612`. The scratch-worktree
number above (`2612 passed`, at the actual audited SHA `1520f50e`) is the evidence of
record. The 5-passed targeted run above, run against just the 3 new pin files + the
DEF141 guard, is unaffected by the concurrent tree state (those files don't touch
`client_release_floor`/`version_gate` code).

## Verdict

`AWAITING_FIXES (round 1)`. 3 MAJOR (1 corroborating `AT:U66`'s finding + 2 new: same-day
tz-change double-send, concurrent-tick double-send with no DB-level guard), 0 BLOCKER,
0 MINOR. Does not supersede `AT:U66`'s pass — folds into it; their finding and mine on
the omit-hour bug are the same bug found twice independently, and their "Everything
else" checks (restart-survival, unreachable-user counting, tz-degrade, notify()
contract, migration, compose parity) all independently re-confirmed here too.
