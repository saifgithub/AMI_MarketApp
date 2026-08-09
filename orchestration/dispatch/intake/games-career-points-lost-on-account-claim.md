# Intake — career points are not carried through an anonymous→claimed account merge

**Handle:** `games-career-points-lost-on-account-claim` (pre-triage; no `DEF###` minted —
the Architect is the single ID-minter and other tracks are live on this checkout).
**Found:** 2026-08-09, during CR109 slice 3 (AT:R66).
**Severity:** contained but user-visible. Nothing is deleted; rows are orphaned from the user.

## What

`merge_service.py` re-keys the tables CR109 slice 2 added — game portfolios, game trades,
`game_entries` (conflict-aware, via the existing `_rekey_skipping_conflicts` helper),
`game_queued_orders` and `portfolio_nav_daily`.

**`career_events` is not among them.** That table landed in slice 3, after the merge fix was
written, and nothing carried it forward.

So an anonymous player who claims an account mid-run **keeps their runs and loses their
Record**: the entries survive and re-key, but the career-point rows still point at the
abandoned anonymous `user_id`. `career_points_total()` sums `delta` for the *claimed*
user and returns zero.

## Why it matters more than it looks

Onboarding is **anonymous-first by design** — the account claim happens at the END of the
concierge interview. So this does not fire on an edge case; it fires on the *intended*
path for every player who plays before claiming. The moment a player has something worth
keeping is exactly the moment it is dropped.

CR109 already treats this class as load-bearing: the CR's own text calls out that
`merge_service.py` did not re-key `BadgeRow`/`StreakFreezeRow` and says **"this CR must fix
its own tables."** Slice 2 did that for the tables that existed then. `career_events` is the
same bug, one slice later.

## Fix sketch

Add `career_events` to the re-key set in `merge_service.py`, using the existing
`_rekey_skipping_conflicts` helper — its `UniqueConstraint(entry_id, reason)` and the partial
unique `(user_id, period_key)` on `finish_stipend` rows both need conflict-aware handling, so
the naive UPDATE will not do.

**Acceptance:** an anonymous user who finishes a scored run, then claims an account, has the
same career-point total before and after the claim — asserted against the ledger
(`SUM(delta)`), not a screen.

## Why it was not fixed inline

Out of the slice-3 brief's scope and file list, and `merge_service.py` had just been edited by
the slice-2 lane on a shared checkout. Deliberate hand-off rather than a silent bolt-on — the
conflict handling deserves its own tests, not a drive-by.
