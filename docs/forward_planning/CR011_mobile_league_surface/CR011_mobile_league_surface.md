# CR011 — C3: League surface (card + screen + Settings profile)

**Status:** in_progress · **Session:** AT:R53 · **Date:** 2026-07-09
**Parent:** CR004 (impl CR under the Engagement umbrella). Design home:
[`../CR004_release_readiness/build_mobile_engagement.md`](../CR004_release_readiness/build_mobile_engagement.md) §C3.
**Source:** Saiful — "continue as much as you can autonomously" (E2 continuation, after CR010).
**depends-on:** CR010 (the league API layer: `leagueMe`/`leagueStandings`/`leagueHistory`/`regenerateHandle` + `models/league.dart`).

## What

- **`LeagueCard`** (new widget, Floor, below `DailyChallengeCard`): tier chip + `RANK 7 / 30`
  + points-this-week + `ROLLS IN 2D 14H` countdown. Unassigned state: "Your first league
  starts Monday — keep earning."
- **`LeagueScreen`** (new, `screens/league/league_screen.dart`): standings `ListView`, my
  row pinned + highlighted, top-5 tinted `hexGreen` / bottom-5 `hexRed` at low opacity, each
  row `HexAvatar` + handle (+ real name only when opted in) + points. Header: tier + week
  countdown. AppBar action → history sheet (past weeks: tier, rank, outcome).
- **Settings profile block**: handle (+ regenerate, one-shot) + reputation total + a
  `show my real name` toggle.
- i18n: ~25 new keys, EN now (AR/MS fall back — standing rule).

## Scope contingency (resolve at build)

The `show my real name` toggle needs a backend route to persist `users.show_display_name`.
**If no such PATCH route exists**, this CR ships the league card/screen + handle display +
regenerate, and **defers the toggle** to a follow-up (a small backend route + promote) rather
than pull a backend change + `/promote-to-alpha` into this mobile lane. Decided from the
mapping.

## Why

C3 is the visible competition surface — it turns the reputation/league backend (E1) into the
leaderboard the user actually competes on. Builds directly on CR010's league API.

## Acceptance

- `flutter analyze` clean; `flutter test` passes.
- LeagueCard renders assigned + unassigned states; LeagueScreen renders standings with my-row
  highlight + zone tints + history sheet; Settings shows handle + reputation (+ toggle if the
  route exists).
- **NEEDS-DEVICE-CHECK:** runtime visuals are Saiful's on-device test.

Routes through the audit handshake as its own lane (`audit/handshake/cr/CR011.*`).
