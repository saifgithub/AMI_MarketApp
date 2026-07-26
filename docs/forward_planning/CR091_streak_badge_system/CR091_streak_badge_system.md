# CR091 — Streak badge system

**Status:** proposed · **Session:** AT:R65 · **Date:** 2026-07-27
**Source:** CR065 drift item #3, verdict "build it" (Saiful, 2026-07-27).

## What

`daily_and_streaks.md`'s streak-reward table promises named badges ("Week One", "Month
Strong", "Centurion", "Marathoner") at each streak milestone. Today, streak milestones
already grant bonus credits (`STREAK_MILESTONES = (7, 30, 100)`,
`STREAK_CREDITS = {7: 5, 30: 25, 100: 100}` in `reputation_service.py`) but there is no
badge concept anywhere in the backend — no table, no model, no service, no read
endpoint. The credit grant fires silently; the badge never materializes.

**Scope note:** this CR covers only the streak-tied badges named in CR065's drift
table. The separate "## Badges" section further down `daily_and_streaks.md`
(Bear-Whisperer, Bull Run, Mandate Keeper, Convener, Briefer, Halal Veteran, Long Game,
Risk Manager, Polyglot) is a related but distinct gap — not flagged by CR065, not in
scope here, and not filed as its own CR yet (would need its own review pass).

## Why

Saiful's verdict on CR065 item #3 was "build it" — the badge system is user-visible
(profile display, per the spec) and currently a documented promise with zero backing.

## Design sketch (not yet detailed — needs a build-time pass)

- `badges` table: `id, user_id (FK users), badge_key (e.g. streak_week_one), earned_at,
  ref_type/ref_id (what triggered it — here, the streak-milestone event)`.
- Award hook: `reputation_service.py`'s existing `_grant_milestone()` call site is
  where the credit grant already fires per milestone — the badge award should be
  co-located there, same idempotency guarantee (DEF049's race-loss protection covers
  the milestone path already; a badge award must share it, not duplicate-fire).
- Read endpoint: `GET /v1/users/{id}/badges` or fold into an existing profile
  response — TBD at build time.
- Mobile: badge display on profile — separate `coder.mobile` sub-lane once the BE
  contract exists (cross-domain split per this repo's standard pattern).

## Scope

**In:** badge table/model/migration, award-on-milestone wiring for the 3 existing
streak milestones (7/30/100 → Week One/Month Strong/Centurion), read endpoint.
**Out:** the 365-day "Marathoner" milestone itself (doesn't exist yet — see CR092,
which DEPENDS-ON this CR for the badge plumbing) and the general achievement-badge
section (Bear-Whisperer etc., not in CR065's scope).

## Acceptance

- A user crossing the 7/30/100-day streak thresholds gets both the existing credit
  grant AND a persisted, readable badge record — same idempotency (no duplicate award
  on repeated milestone checks).
- Badge award doesn't regress the existing credit-grant test coverage.
