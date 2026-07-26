# CR094 — Paid-tier streak freezes

**Status:** proposed · **Session:** AT:R65 · **Date:** 2026-07-27
**Source:** CR065 drift item #4, verdict "build it" (Saiful, 2026-07-27).

## What

`daily_and_streaks.md` promises a Floor Manager ($34.99/mo) perk: 2 streak freezes
per year, each pausing the streak for a single day (e.g. travel). Not implemented —
`reputation_service.py`'s streak computation derives purely from activity-day runs,
with no freeze/pause concept.

## Why

Saiful's verdict: build it. A named, paid-tier retention perk currently doesn't
exist despite being advertised.

## Design sketch (not yet detailed — needs a build-time pass)

- A freeze record (table or a counter+dates column on `users`) tracking freezes used
  this calendar year, capped at 2, gated on `plan == floor_manager` (entitlement
  check mirrors the existing `effective_plan()` pattern already used for tier
  routing elsewhere).
- Streak computation (`_activity_days` / `_run_ending_at` in `reputation_service.py`)
  needs to treat a frozen day as a non-breaking gap — i.e. a day with no activity but
  an active freeze doesn't end the run.
- Interacts with the existing "App outage auto-extends streaks" rule
  (`daily_and_streaks.md`'s streak-loss table) — both are gap-tolerance mechanisms;
  confirm they compose cleanly (a frozen day during an outage shouldn't double-count).

## Scope

**In:** freeze grant/consumption, plan-gated (Floor Manager only), streak-computation
change to tolerate a frozen gap, freeze-count reset on the user's plan-year boundary.
**Out:** any UI for freeze selection (mobile follow-up once the BE contract exists).

## Acceptance

- A Floor Manager user can freeze exactly 2 days/year; a 3rd attempt is rejected.
- A frozen day does not end an in-progress streak; an unfrozen missed day still does.
- Non-Floor-Manager users cannot freeze (entitlement-gated, matches existing
  plan-check patterns).
