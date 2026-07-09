# CR009 — Mobile engagement bundle: B3 Room roster + B4 dead-end removal + B6 empty states

**Status:** in_progress · **Session:** AT:R53 · **Date:** 2026-07-09
**Parent:** CR004 (implementation CR — CR004's Acceptance section: "each workstream
bundle files its own implementation CR referencing CR004"). Design home:
[`../CR004_release_readiness/build_mobile_engagement.md`](../CR004_release_readiness/build_mobile_engagement.md) §B3/B4/B6.
**Source:** Saiful — "continue" (CR004 Engagement work order, next chunk after B1).

## What

Three mobile bundles from the build spec, one commit-group:

- **B3 — Room roster skeleton** (`room_screen.dart`): on `RoomState(streaming, empty
  transcript)`, render the 12-agent lineup (dimmed `HexAvatar` + name + `STANDING BY`)
  instead of the empty-body + footer spinner. Active agent → speaking; completed → ✓.
  Source of truth = the agent manifest the Floor honeycomb already uses. No backend change.
- **B4 — Dead-end removal:**
  - `floor_placeholder_screen.dart` locked sheet: replace dead "UPGRADE TO SKIP — coming
    soon" with earn-path progress + tap → next gateway lesson. **Rename file/class →
    `floor_screen.dart` / `FloorScreen`** (Plan A #9) in the same commit.
  - `daily_challenge_card.dart`: related lesson → `LessonReaderScreen`; related agent →
    `AgentActionSheet`.
  - `brief_screen.dart` "Refine": keep diff visible, prefill composer, focus input — stop
    calling `.reject()`. **File the Plan A #1 DEF on pickup.**
  - `ticker_detail_screen.dart`: delete `_ComingSoonCard` + its l10n keys.
  - `settings_screen.dart`: D-062/D4 — drop the coercing theme toggle → static
    "DARK — floor standard" row.
- **B6 — Empty states:** reuse Journal `_EmptyState` shape (icon + title + one-liner +
  CTA) for watchlist, `portfolioNoTrades`, `tickerDetailNoTrades`, Alpaca no-positions.
  All copy via l10n, AMI voice (never "the AI").

## Why

Objective (b) playability. The app today has 15 grey placeholders, a permanent "COMING
SOON" card, dead upgrade buttons, and blank waits — each a dead-end that reads as broken.
B3/B4/B6 close them so every surface either does something or explains itself.

## Scope

The files in the spec table above. No backend change. New l10n keys land EN-only (AR/MS
fall back until the next translate pass — standing rule).

## Acceptance

- `flutter analyze` clean (pre-existing infos excepted).
- Every dead-end in the B4 table removed; `FloorPlaceholderScreen` renamed with all refs
  repointed.
- Room roster renders during a live Room run with an empty transcript.
- Empty states reuse the Journal `_EmptyState` shape; all copy through l10n.
- **NEEDS-DEVICE-CHECK:** on-device manual pass (Room roster during a real run, empty
  states, brief refine flow) is Saiful's acceptance test — no physical iPhone in-session.

Routes through the audit handshake as its own lane (`audit/handshake/cr/CR009.*`).
