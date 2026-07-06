# Plan B — Playability (UX that makes the loop feel like play)

Part of [CR004](CR004_release_readiness.md). Goal: the daily loop (open app → hook → agent interaction → decision → reflection) should deliver feedback the user *feels*. Today it mostly doesn't: the AT:R51 audit found exactly **two** `HapticFeedback` call sites in the whole app (trade submit, journal swipe-delete) and zero celebratory animation anywhere.

Navigation is NOT the problem — every key action is ≤2 taps from the Floor. The problem is the **reward economy**: success moments render as static text.

**Estimated effort:** ~4–5 sessions (B2 is the big one; shares its backend with Plan C).

---

## B1 — Reward-moments system (~1 session)

One `CelebrationService` (new, `mobile/lib/services/`) with three tiers, applied consistently:

| Tier | Feedback | Wire to |
|---|---|---|
| micro | light haptic + accent color flash | challenge correct, Room verdict lands, watchlist add |
| meso | medium haptic + hex-burst overlay (~600ms CustomPainter particle burst, reuses `FlatTopRegularHexagon` from `mobile/lib/theme/hex_clipper.dart`) | lesson quiz pass, streak milestone, league promotion (Plan C) |
| major | full-screen takeover | **agent unlock** — the core progression event currently celebrated with a static amber label (`lesson_reader_screen.dart:741`). New `AgentUnlockedScreen`: agent hex scales in with glow, name + role line, "MEET <NAME>" CTA straight into 1-on-1 |

Keep what works: trade-submit snackbar (`trade_ticket_sheet.dart:207`), verdict-CTA→"trade placed" pill, LIVE/MOCK honesty pills.

## B2 — Streaks, live (~1.5 sessions incl. backend; foundation for Plan C)

Specced 🟢 Alpha in [daily_and_streaks.md](../../initial_specs/04_education/daily_and_streaks.md), zero code exists. Spec rules: streak counts **trying, not winning** — any day with a challenge attempt OR lesson progress OR agent interaction. No shaming on loss.

- **Backend:** `daily_challenge_attempts` table (Plan C migration 0014 — UNIQUE(user_id, challenge_id), correctness + created_at); streak computed from attempts ∪ lessons_progress ∪ journal activity days; `GET /v1/daily_challenge/streak` (or fold into an existing bootstrap payload). Milestone credit grants per spec (7d +5, 30d +25, 100d +100) written as `subscription_events` rows via the `_record_event` pattern (`backend/app/api/admin.py:71-92`).
- **Mobile:** streak flame/hex chip on the Floor header + on the daily-challenge card; milestone hits fire meso celebrations. No streak-freeze mechanics (paid perk, Phase 2 per spec).

## B3 — Room theatre (~0.5 session)

Convening the Room is the marquee moment, but it opens onto an **empty screen with a tiny footer spinner** until the first token arrives (`room_screen.dart:568`). Fix: on open, render the full 12-agent lineup as a skeleton roster — each agent's hex avatar dimmed with a "STANDING BY" status that flips to a live speaking state (filled dot already exists) as their tokens arrive. The wait becomes the team assembling instead of dead air. Zero backend change.

## B4 — Dead-end removal (~1 session)

| Dead end | Fix |
|---|---|
| "UPGRADE TO SKIP — coming soon" button that just closes the sheet (`floor_placeholder_screen.dart:220`) | Replace with earn-path progress: "2 of 3 gateway lessons done" + tap-through to the next lesson |
| Daily-challenge "Related lesson / Related agent" plain text (`daily_challenge_card.dart:201`) | Make tappable → lesson reader / agent sheet |
| Brief "Refine" = reject (`brief_screen.dart:125`) | Real refine: keep the diff, prefill the input with the proposal for edit (Plan A DEF) |
| `_ComingSoonCard` on every ticker detail (`ticker_detail_screen.dart:582`) | Remove; the screen already earns its keep (chart, news, earnings) |
| Appearance toggle that coerces back to dark (`settings_screen.dart:688`) | Plan D §D4 — replace with static row |

## B5 — Challenge persistence + tomorrow-hook (~0.5 session)

Attempt state is deliberately non-persistent today (`state/daily_challenge_providers.dart:4`) — resets on tab switch, silently allows re-answering. Once B2's attempts table exists: server is source of truth; an answered challenge renders its result + explanation all day, with a "next challenge in 07:14:33" countdown. The card becomes the app's return-tomorrow hook.

## B6 — Empty states with CTAs (~0.5 session)

Journal/Portfolio/1-on-1 empty states are good. Bare-caption ones get icon + one-line + CTA: watchlist empty (→ "ADD TICKER"), `portfolioNoTrades` (→ trade ticket), `tickerDetailNoTrades`, Alpaca "No open positions".

## Instrumentation note

Playability targets (time-to-first-action < 30s from cold start, D1 challenge-attempt rate, streak retention) can't be measured until PostHog lands (M7). Design events now, name them in each B-item's implementation CR, emit when M7 arrives.

## Acceptance

- Every success moment in the core loop fires a consistent celebration tier; agent unlock is a major moment.
- A streak survives app restarts and shows on the Floor; milestones grant credits per spec.
- Room open shows the 12-agent roster within one frame.
- Zero dead-end CTAs reachable in a release build.
