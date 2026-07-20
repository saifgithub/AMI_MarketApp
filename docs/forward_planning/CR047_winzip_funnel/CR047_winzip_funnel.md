# CR047 — GTM Funnel Plan 1 "The Winzip": soft credit wall with cooldown reset

**Status:** in_progress
**Filed:** 2026-07-20 (AT:R63)
**Parent:** [CR045](../CR045_paywall_funnel_tactics/CR045_paywall_funnel_tactics.md) — paywall funnel tactic library. CR045 is the umbrella menu; its acceptance says *"each chosen plan then gets its own implementation CR."* This is Plan 1's implementation CR.
**Builds on:** [CR039](../CR039_room_credit_gate/CR039_room_credit_gate.md) — the Room credit gate + 402 wall this softens. Absorbs CR039's deferred mobile-half paywall ([CR039 doc line 85](../CR039_room_credit_gate/CR039_room_credit_gate.md): *"Typed `InsufficientCreditsException` … upgrade sheet on 402, EN l10n"* — backend shipped, mobile never did; today the 402 renders as a generic "Stream failed").

---

## Why

Diagnosis of a flood of HTTP 402s from a real device: the CR039 gate fires on an exhausted **Floor Pass** account. Floor Pass = 13 credits/month, a Room costs 8 → **1 Room/month**, then a hard 402 until the 1st, with **no IAP** to buy more. Across the live DB every account (expired trials + all anonymous) sits at that 1-Room/month floor; `http_audit` logged **147 × 402** on `/v1/room/stream` in three days. For an alpha whose whole point is people *using* the flagship Room, a hard wall after one convene is the wrong shape.

"The Winzip" (Saiful) turns the wall into a funnel: tell the user they hit a limit, **reset them anyway** the instant the 402 is sent, and ask them to come back in a few minutes — and it genuinely resets, no false promise (nagware psychology; the friction *is* the funnel, the user is never actually lost).

## Locked mechanics (Saiful, 2026-07-20)

- **Hard 5-min cooldown, enforced.** On Floor-Pass credit exhaustion: reset credits immediately, but block re-convene until `cooldown_until = now + WINZIP_COOLDOWN_MINUTES`. Retrying early re-shows the countdown.
- **Refill exactly 1 Room** (top balance up to the Room cost), **unlimited** over time → one free Room per cooldown.
- **Floor Pass only**, behind a `GTM_FUNNEL` config flag (values `none | winzip`) so funnels #2/#3 slot in later. Paid tiers keep today's behaviour. Unknown flag value fails loudly (boot refuses — `Literal` type), never silently falls back (CR040).
- **Live countdown** card in the Room; at 0, on-device **TTS** speaks *"Your Room is available now"* (AMI, female voice where available). **In-app only** for MVP; the card **suggests reviewing a Training session** while waiting.
- **Dogfood:** no manual credit top-up for Saiful's own account — he experiences Winzip like everyone.

## Behaviour (Floor Pass + `GTM_FUNNEL=winzip`)

The gate lives in `credit_service.spend()`. For a Floor Pass user under the winzip funnel, in order:

1. **Cooldown active** (`room_cooldown_until` in the future) → raise winzip `InsufficientCredits` carrying `cooldown_until`; no grant, no spend, regardless of balance. *(This is why the reset tops up to exactly `cost` and the cooldown is a separate gate — otherwise the topped-up balance would let the very next convene through and the wait would never bite.)*
2. **Balance ≥ cost** → normal spend (their free Room). Balance drops.
3. **Balance < cost** (exhaustion, no active cooldown) → set `credit_balance = cost`, `room_cooldown_until = now + cooldown`, log `credits_added` note `winzip_reset`, then raise winzip `InsufficientCredits` carrying the new `cooldown_until`.

Net loop: monthly allowance buys 1 Room → exhaustion resets +1 Room behind a 5-min wait → after the wait, 1 Room → exhaustion again → … Unlimited Rooms, paced one per cooldown. Non-winzip funnel or any non-Floor-Pass plan → unchanged CR039 behaviour.

## Scope

### Backend (ships via `/promote-to-alpha`)
- `config.py`: `gtm_funnel: Literal["none","winzip"] = "none"`, `winzip_cooldown_minutes: int = 5`. Forward both in `docker-compose.yml` `api-alpha` env (CR040 parity test). `GTM_FUNNEL=winzip` in melehost `.env` makes it live on Alpha.
- `models.py`: `users.room_cooldown_until` (nullable timestamptz) + alembic migration (down_revision `b4c5d6e70018`).
- `credit_service.py`: extend `InsufficientCredits` with `funnel`, `cooldown_until`; winzip branch in `spend()`.
- `api/room.py`: add `funnel`, `cooldown_until`, `retry_after_seconds` to the 402 `detail`.
- `api/mandate.py` + `schemas/mandate.py`: expose `room_cooldown_until` (for the client's pre-emptive gate).
- Tests: extend `test_cr039_room_credit_gate.py` with winzip cases.

### Mobile (ships via `flutter build ios --release`)
- New dep `flutter_tts` (voice line; `just_audio` can't TTS).
- `InsufficientCreditsException` (`services/api/api_exceptions.dart`) + parse the 402 in `streamRoom`.
- `RoomState.paywall` + catch in `RoomNotifier.start()`; `_WinzipCard` (amber `AccentCard`) with live countdown, "Review a Training session while you wait" → `LessonsScreen`, TTS at 0.
- `UserMandate.fromJson`: add `roomCost`, `creditsResetAt`, `creditAllowance`, `roomCooldownUntil`; optional pre-emptive gate on the convene entry.
- l10n `roomWinzip*` keys (AMI by name, never "the AI").

## Out of scope
- Background/local notification (app closed) → next round.
- Funnels #2/#3, referral "Share a Premium" (CR045 Plan 2), real IAP/upgrade.
- Any Floor Pass credit-number change — Winzip replaces the hard wall for alpha instead.

## Acceptance
1. Backend units green (winzip exhaustion → 402 carries `funnel`/`cooldown_until`, balance tops to `cost`; re-convene within cooldown → 402, no double-grant; after cooldown → success; paid/`none` → legacy 402; unknown flag → boot fails).
2. On Alpha, a floor_pass account drives the 402→reset→wait→success loop (verified in `http_audit` + `subscription_events`), not a dead wall.
3. On device, the Winzip countdown card renders with the Training CTA and the AMI TTS line at 0; convening during cooldown re-shows the countdown; after it, the Room runs.
