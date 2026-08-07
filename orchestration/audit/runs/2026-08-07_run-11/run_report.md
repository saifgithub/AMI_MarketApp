# Run report — 2026-08-07_run-11

Item: CR095, round 2. SHA: `82fd43fd`. Verdict: **AWAITING_FIXES (round 2)**
— 0 BLOCKER, 1 MAJOR (confirmed from a concurrent `AT:U66` pass, now closed
by a committed pin — see reasoning below), 0 MINOR. Full findings in
`orchestration/audit/cr/CR095.auditor.md`'s ADDENDUM section (tail of file).

## Collision with a concurrent auditor pass

Dispatched to attack round 2's three named fixes. By the time this pass
finished, `AT:U66` had already pushed its own round-2 verdict (`ebde48ad`):
AWAITING_FIXES, 1 new MAJOR (the paid-path `was_duplicate` early-return
exists and is correct but had zero test coverage at `82fd43fd`). Read in
full before finishing. Independently reproduced the exact same underlying
claim via a different method (a real concurrent-race test rather than
delete-guard-and-rerun-suite), confirmed the production code is already
correct, and closed the coverage gap with a mutation-verified pin
(`test_cr095_round2_auditor_adversarial_pin.py::test_paid_tier_duplicate_does_not_fall_through_to_email`).
Did not self-certify COMPLETE on my own remediation — kept AWAITING_FIXES,
consistent with every other multi-instance collision today (CR121, CR131,
CR141, CR124, CR132): severity relaxes only on an independent NEXT pass.

## Worktree

`.claude/worktrees/audit-CR095-r2-u66` (DEF159 convention), reaped mid-session
by a concurrent track; continued in a second scratch worktree
(`<scratchpad>/wt_cr095`) at the identical SHA. Declared files: zero drift
`82fd43fd` → `main` (only intervening commit touching any of the 9 files is
CR121 round 3's unrelated `Query(ge=0)` hunk in `main.py`).

## Independent pytest

```
cd backend && "/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
```

- Baseline (my new pin file removed, parity check): **2675 passed** —
  exact match to both the architect's submission and `AT:U66`'s independent
  measurement.
- With `test_cr095_round2_auditor_adversarial_pin.py` added: **2686 passed**
  (2675 + 10 new tests + 1 free parametrized case from DEF225's per-file
  cwd-independence guard — verified by exact collected-ID diff, not assumed).
- Notification-surface filter (`-k "notif or price_alert or daily or
  reminder"`): 122 passed.

## Mutation proofs run this pass (all reverted, tree clean after each)

1. `if "daily_reminder_hour" in req.model_fields_set:` reverted to
   unconditional assign → the omit-hour case breaks again (reproduces
   round-1 MAJOR #1).
2. `UniqueConstraint("user_id", "type", "source_ref", ...)` removed from
   `NotificationRow` → `test_two_overlapping_ticks_both_send_no_db_guard`
   fails (`daily_reminder_sent` logged twice), and my own new
   `test_paid_tier_duplicate_does_not_fall_through_to_email` and
   `test_notify_same_alert_id_twice_degrades_to_duplicate_not_500` also
   fail (confirms the constraint is load-bearing for cases beyond the
   shipped pins too).
3. `created_at is not None: row.created_at = created_at` line removed from
   `notify()` → `test_the_next_days_reminder_still_fires` fails while the
   double-send pin stays green (the fix-shipped-broken-under-its-own-
   non-vacuity-check shape both prior passes found).
4. The paid-path `if result.was_duplicate: ...; return` guard (6 lines)
   removed → `test_paid_tier_duplicate_does_not_fall_through_to_email` fails
   with `2 fallback emails for one user` — the exact double-send `AT:U66`
   flagged as unpinned, now reproduced and closed.

## New adversarial coverage beyond both prior passes

1. Partial-update `{}` and unrelated-keys-only bodies — hold (Pydantic
   `extra="ignore"` default, `model_fields_set` empty either way).
2. DST — real `zoneinfo` transitions for `America/New_York` 2027
   (spring-forward 23h gap, fall-back 25h gap), no user-initiated timezone
   change. Both send correctly; the 20h window clears both with room, as
   the architect reasoned (binding constraint is the 24h ceiling, not the
   ~1h DST shift).
3. Exact 20h boundary math, isolated via direct `_already_reminded_today`
   calls: inclusive at exactly 20h, releases at 20h+1s.
4. **Real Postgres 16** (disposable local cluster, Homebrew `initdb`/
   `pg_ctl`), full alembic chain run from `e355c2468b2a` through
   `8c5b1a70f4d2`. Seeded 8 rows across 4 groups; the dedupe DELETE keeps
   exactly the earliest-per-group row (tie broken by `id`), NULL
   `source_ref` rows untouched, and the constraint then rejects a live
   duplicate insert and accepts two `NULL source_ref` rows. Both prior
   passes only read this SQL; this pass ran it.
5. `price_alert_evaluator.py` — the one other real `notify()` caller with a
   non-null `source_ref` (`str(alert.id)`). Confirmed safe: the evaluator's
   own atomic `WHERE status='active'` CAS means the same alert id can never
   legitimately reach `notify()` twice; direct calls confirm two different
   alert ids never collide and the same id twice degrades cleanly to
   `was_duplicate`, not a 500.

## Verdict reasoning

Zero new BLOCKER/MAJOR of my own. `AT:U66`'s 1 MAJOR reproduced and
confirmed real via an independent method; underlying code confirmed
correct; coverage gap closed with a committed, mutation-verified pin.
Verdict held at AWAITING_FIXES rather than self-certified COMPLETE — the
architect's round 3 should be near-immediate (accept the pin, bump round).
