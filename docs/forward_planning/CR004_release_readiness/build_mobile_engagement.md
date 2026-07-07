# Build spec — mobile: celebrations, streaks, Room theatre, league, share cards (Plans B1/B3–B6/C3/C4)

Part of [CR004](CR004_release_readiness.md). Implementation commits tag `(AT:R<N> CR004)`.
New dependency to flag at implementation: `share_plus` (share cards). Everything else uses what's in `pubspec.yaml`.

---

## B1 — `mobile/lib/services/celebration.dart` (new)

```dart
class Celebrate {
  static micro(BuildContext)                    // HapticFeedback.lightImpact + 250ms accent flash on nearest AccentCard/panel
  static meso(BuildContext, {Color accent})     // HapticFeedback.mediumImpact + HexBurstOverlay
  static major(BuildContext, {required AgentMeta agent})  // push AgentUnlockedScreen
}
```

- `HexBurstOverlay` — `OverlayEntry` + `CustomPainter`: 10–14 small hexes (reuse `FlatTopRegularHexagon`, `theme/hex_clipper.dart`) radiating from origin, 600ms `easeOutCubic`, fade to 0. Colors from `agentFamilyColor`/role accents.
- `AgentUnlockedScreen` (new, `screens/agent/agent_unlocked_screen.dart`) — full-screen slate900: agent hex scales 0.6→1.0 with glow bloom (900ms), name + role line + one-sentence specialty from the agent manifest, `[MEET <NAME>]` `HexButton` → replaces route with `OneOnOneScreen`; text "later" → pop.

**Call-site wiring:**

| Moment | Site | Tier |
|---|---|---|
| Challenge correct | `floor/daily_challenge_card.dart` submit handler | micro |
| Room verdict lands | `room_screen.dart` `_VerdictCard` first build | micro |
| Watchlist add | ticker detail watch chip | micro |
| Lesson quiz pass | `lessons/lesson_reader_screen.dart` `_ResultPanel` (~:728) | meso |
| Streak milestone | streak provider detects `next_milestone` crossed | meso |
| League promotion | league provider sees `outcome=promoted` on history refresh | meso |
| Agent unlock | `lesson_reader_screen.dart:741` (replace static amber label path) | **major** |

Trade-submit keeps its existing snackbar (`trade_ticket_sheet.dart:207`) — already right.

## B2/B5 — Streaks + challenge persistence (server truth from the backend build spec)

- `api_client.dart`: `leagueMe()`, `leagueStandings()`, `leagueHistory()`, `regenerateHandle()`; extend `dailyChallengeToday()` model with `myAttempt`.
- `models/league.dart` (new): `LeagueMe`, `LeagueStandings`, `LeagueMemberRow`, `StreakInfo`.
- `state/league_providers.dart` (new): `leagueMeProvider`, `standingsProvider` — refresh on Floor visibility + after any awarding action completes.
- **Streak chip**: Floor header (`floor_placeholder_screen.dart`) — small hex chip `⬡ 12` with amber accent when today is still unfilled, green once filled; also on `DailyChallengeCard`.
- **Challenge card**: if `myAttempt != null` render answered state (result + explanation + countdown `next challenge in HH:MM:SS`, ticking `Timer` to local midnight in user tz). Remove the deliberate non-persistence note in `state/daily_challenge_providers.dart:4`.

## B3 — Room roster skeleton (`room_screen.dart`)

On `RoomState(streaming: true, transcript empty)`: render the 12-agent lineup from the agent manifest (same source the Floor honeycomb uses) as rows — dimmed `HexAvatar` + name + `STANDING BY` in `labelMono`. `room_providers.dart:103` (`agent_token` handler) already knows the active agent: flip that row to speaking (filled dot exists; add pulse once D3 lands), completed rows show ✓. Replaces the empty-body + footer-spinner wait (`room_screen.dart:568`). No backend change.

## B4 — Dead-end removal

| File | Change |
|---|---|
| `floor_placeholder_screen.dart:220` | Locked sheet: replace dead "UPGRADE TO SKIP — coming soon" with earn-path progress ("2/3 gateway lessons") + tap → next gateway lesson via `TrackLessonsScreen`. Rename file/class → `floor_screen.dart` / `FloorScreen` in the same commit (Plan A #9) |
| `daily_challenge_card.dart:201` | Related lesson → `LessonReaderScreen(lessonId)`; related agent → `AgentActionSheet` |
| `brief_screen.dart:125` | "Refine": keep diff visible, prefill composer with proposal text, focus input — do NOT call `.reject()` (file the Plan A DEF on pickup) |
| `ticker_detail_screen.dart:582` | Delete `_ComingSoonCard` + its l10n keys |
| `settings_screen.dart:671-688` | Plan D4: drop the coercing toggle → static "DARK — floor standard" row |

## B6 — Empty states

Pattern already good in Journal `_EmptyState` — reuse its shape (icon + title + one-liner + CTA) for: watchlist empty (`ADD TICKER` → search field focus), `portfolioNoTrades` (→ `TradeTicketSheet`), `tickerDetailNoTrades`, Alpaca no-positions. All copy through l10n (AMI voice, never "the AI").

## C3 — League surface

- **`LeagueCard`** (new widget, Floor, below `DailyChallengeCard`): tier chip + `RANK 7 / 30` + points-this-week + `ROLLS IN 2D 14H`. Unassigned state: "Your first league starts Monday — keep earning."
- **`LeagueScreen`** (new, `screens/league/league_screen.dart`): standings `ListView`, my row pinned + highlighted, top-5 zone tinted `hexGreen`/bottom-5 `hexRed` at low opacity, each row `HexAvatar` + handle (+ real name only when that user opted in) + points. Header: tier name + week countdown. AppBar action → history sheet (past weeks: tier, rank, outcome). Settings profile block gains handle + `show my real name` toggle (`PATCH` via existing settings plumbing) + reputation total.
- i18n: ~25 new keys, EN now, AR/MS fall back until next translate pass (standing rule).

## C4 — Share cards

- `widgets/share/share_card.dart` (new): `ShareCard(template, payload)` rendered **offscreen** at fixed 1080×1350 logical px inside `RepaintBoundary` → `toImage` → `share_plus` `Share.shareXFiles`.
- Templates (all slate900, hex mesh watermark, AMI wordmark, disclaimer strip `disclaimerShort` l10n key — "Educational simulation. Not investment advice."): `verdict` (ticker, stance, 2-line reasoning excerpt — **no prices/P&L**), `streak` (big hex + day count), `unlock` (agent hex + name), `promotion` (tier chip + week).
- Entry points: share icon on `_VerdictCard`, on streak-milestone celebration overlay, on `AgentUnlockedScreen`, on league history rows.

## Test/verify

`flutter analyze` clean; goldens optional-skip (no golden infra today — don't add). Manual pass per Plan A2 checklist addendum: each celebration tier observable on device; challenge answered-state survives force-quit; league renders with 1-member cohort (dev seed); share sheet produces image on iOS + Android.

## Sequencing (after backend spec lands on Alpha)

1. B1 celebrations + unlock screen (1 session)
2. B3 roster + B4 dead-ends + B6 empty states (1)
3. B2/B5 streak chip + challenge persistence (0.5)
4. C3 league card/screen + profile bits (1)
5. C4 share cards (0.5–1)
