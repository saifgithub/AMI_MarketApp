# CR093 — Lifetime reputation tier (distinctly named from the weekly league tier)

**Status:** proposed · **Session:** AT:R65 · **Date:** 2026-07-27
**Source:** CR065 drift item #2, verdict "both stay, rename one" (Saiful, 2026-07-27).

## What

`daily_and_streaks.md` promises a reputation tier derived from **lifetime** point
totals (0–100 Apprentice → 10,000+ Floor Veteran). The shipped weekly league
(`league_service.py`, CR004) derives its tier from **weekly promote/relegate**
instead, using the **exact same five names** (`apprentice, analyst, trader, senior,
floor_veteran`) — so "Trader" means two different things depending on which system a
user (or a future session) is reading.

## Why

Saiful's verdict: **both mechanics stay** — the weekly league (shipped, live) and a
lifetime-total reputation tier (not yet built) — but they need visibly distinct
names so users never see the collision.

## Naming resolution

The weekly league is **shipped and live** (real users see it weekly); renaming it
means a user-facing string change on an existing surface. The lifetime-tier concept
is **not yet built** at all. Lower-risk path: **keep the weekly league's names as-is**
(`apprentice → analyst → trader → senior → floor_veteran`), and give the new
lifetime-total tier a **distinct ladder** when it's built.

Note the spec's existing "Trader (yes, same word as plan — intentional)" comment
referred to a *different*, still-valid pun (reputation tier echoing the **paid
subscription plan** name, Trader $14.99/mo) — that pun is orthogonal to this
collision and doesn't need to change. Only the lifetime-tier ↔ weekly-league name
overlap is being resolved here.

**Proposed distinct ladder for the lifetime tier (placeholder, confirm at build
time):** e.g. `Observer → Contributor → Specialist → Veteran Trader → Master` — or
whatever avoids reusing `apprentice/analyst/senior/floor_veteran` verbatim. Exact
names are a build-time decision, not locked by this filing.

## Scope

**In:** amend `daily_and_streaks.md`'s reputation-tier table to use the new,
distinct ladder (done as part of this CR's filing — see the doc diff). Build the
actual lifetime-point-total tier computation + read surface + mobile display.
**Out:** any change to the shipped weekly league's tier names.

## Acceptance

- The reputation-tier table in `daily_and_streaks.md` no longer shares any tier name
  with the shipped weekly league ladder.
- Lifetime-tier computation is a pure function of lifetime reputation total, entirely
  independent of weekly promote/relegate state.
