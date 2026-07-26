# CR092 — 365-day "Marathoner" streak milestone

**Status:** proposed · **Session:** AT:R65 · **Date:** 2026-07-27
**Source:** CR065 drift item #1, verdict "build it" (Saiful, 2026-07-27).
**Depends on:** CR091 (streak badge system — this milestone's badge award needs that
plumbing to exist first).

## What

`daily_and_streaks.md` promises a 365-day streak reward: "Marathoner" badge +
permanent profile flair + 500 bonus credits. None of it exists in code —
`STREAK_MILESTONES = (7, 30, 100)` in `reputation_service.py` has no 365 entry, so a
user with a full year's streak gets nothing beyond the 100-day reward.

## Why

Saiful's verdict on CR065 item #1 was "build it" — this is the single most
user-visible reward in the whole streak ladder (500 credits is 5x the next-largest
grant) and currently silently caps out at 100 days.

## Scope

**In:**
- Add `365` to `STREAK_MILESTONES`, `STREAK_CREDITS[365] = 500`.
- "Marathoner" badge award via CR091's badge plumbing.
- Permanent profile flair — needs a concept that doesn't exist yet even for badges;
  simplest shape is a boolean/flag on the badge record (`is_permanent_flair: true`) so
  the mobile profile can render it distinctly from a regular badge. Confirm this
  approach at build time rather than inventing a parallel flair table.

**Out:** the badge system itself (CR091, dependency) and the 1000-day tier ("Custom
hex profile mark and special status (we'll see)" — the spec's own hedge language
means it's explicitly not ready to be scoped as a CR yet).

## Acceptance

- A user crossing 365 consecutive activity days gets the 500-credit grant, the
  "Marathoner" badge, and the permanent-flair flag, with the same idempotency
  guarantee as the other milestones (DEF049 race-loss protection).
- Regression check: the 7/30/100-day milestones are unaffected by the new tier.
