# CR010 — B2/B5: streak chip + challenge server-truth + league API layer

**Status:** in_progress · **Session:** AT:R53 · **Date:** 2026-07-09
**Parent:** CR004 (implementation CR under the Engagement umbrella). Design home:
[`../CR004_release_readiness/build_mobile_engagement.md`](../CR004_release_readiness/build_mobile_engagement.md) §B2/B5.
**Source:** Saiful — "continue as much as you can autonomously" (CR004 E2 continuation, next after CR009).

## What

Surface the R52 reputation/league/streak backend in the app:

- **League API layer:** `api_client.dart` gains `leagueMe()`, `leagueStandings()`,
  `leagueHistory()`, `regenerateHandle()`. New `models/league.dart`
  (`LeagueMe`, `LeagueStandings`, `LeagueMemberRow`, `StreakInfo`). New
  `state/league_providers.dart` (`leagueMeProvider`, `standingsProvider`).
- **Challenge server-truth (B5):** the daily-challenge card grades LOCALLY today and
  loses state on a tab switch. Switch to server truth — `GET /today` carries
  `my_attempt`; render the answered state (result + explanation + a ticking countdown to
  the next challenge at local midnight) when `myAttempt != null`. Remove the deliberate
  non-persistence note in `state/daily_challenge_providers.dart`.
- **Streak chip (B2):** a small hex chip `⬡ N` on the Floor header and on the
  `DailyChallengeCard` — amber when today is still unfilled, green once filled. Streak
  comes from `leagueMe()`.

## Why

CR004 E1 shipped the reputation engine, weekly leagues, and streaks to Alpha, and CR009
shipped the celebration layer — but none of it is visible in the app yet. B2/B5 is the
thinnest slice that makes the backend real for the user, and it lays the league API layer
that C3 (league UI) builds on.

## Scope

`api_client.dart`, new `models/league.dart` + `state/league_providers.dart`,
`daily_challenge_card.dart`, `daily_challenge_providers.dart` + its model, and the Floor
header (`floor_screen.dart`). No backend change (routes exist since R52). New l10n keys
land EN-only (standing rule).

## Acceptance

- `flutter analyze` clean (pre-existing infos excepted); `flutter test` passes.
- Challenge card renders the answered state from `my_attempt` and survives a tab switch;
  countdown ticks to local midnight.
- Streak chip renders on Floor + challenge card, amber/green by today's fill state.
- League API methods + models + providers compile and parse the live route shapes.
- **NEEDS-DEVICE-CHECK:** runtime visuals + the countdown are Saiful's on-device test.

Routes through the audit handshake as its own lane (`audit/handshake/cr/CR010.*`).
depends-on: none (CR009 COMPLETE; backend live since R52).
