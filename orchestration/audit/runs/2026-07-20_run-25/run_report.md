<!--
Auditor run report — run-25 (2026-07-20, session AT:U1). Round-1 audit of CR047
"The Winzip" — soft Floor-Pass credit wall + 5-min cooldown reset (GTM funnel
Plan 1 under CR045). Head 67dcbe3 (== origin/main). Verdict COMPLETE. Owner: AUDITOR.
-->

# run-25 (round 1) — CR047 "The Winzip" (soft credit wall + cooldown reset) → COMPLETE

- **Auditor session:** AT:U1 (track U), 2026-07-20
- **Audited SHA:** `67dcbe3` (== `HEAD` == `origin/main`). `git diff 67dcbe3 -- backend/ mobile/`
  empty → the main checkout is byte-identical to the committed SHA (only the
  architect's own untracked lane files are dirty). Tests run in place.
- **Backend suite reproduced:** **861 passed** (1 pre-existing FastAPI HTTP_422
  deprecation warning, unrelated). Matches the architect's claim exactly.
- **Independent loop driver (my own assertions, 5 cooldown cycles):** 6 Rooms
  delivered (1 free + 5 paced), exactly one per cooldown; 15 during-cooldown
  re-taps never granted; paid-plan bypass + default-off both hard-wall.
- **Mobile:** `flutter analyze lib/` → 4 issues, **all 4 pre-existing** (main.dart:69
  ×2, floor_screen.dart:73/289), **zero in any CR047 file** → 0 new.
- **Verdict:** COMPLETE — zero BLOCKER / zero MAJOR. One non-blocking OUT-OF-SCOPE
  observation (pre-existing concurrency, informational). Live-Alpha loop + device
  render legitimately deferred (not promoted / no device — Mac is pure editor).

---

## What CR047 does

Softens CR039's hard Floor-Pass credit wall (13 credits ÷ 8/Room = 1 Room/month,
no IAP → 147 × 402 on `/v1/room/stream` in 3 days, whole cohort stuck at the floor)
into a nagware funnel. On Floor-Pass exhaustion under `GTM_FUNNEL=winzip`: reset the
balance to **exactly one Room** the instant the 402 is sent, but enforce a 5-min
cooldown before the next convene. Unlimited Rooms, paced one per cooldown — the user
is never actually lost. Default `none` = legacy CR039 hard wall, byte-identical.

## Why it's correct — verified, not trusted

### Backend (fully reproduced on the Mac)

| Dimension | Result |
|---|---|
| **The load-bearing ordering** (`spend()` cooldown-before-balance) | Confirmed by source read + my own driver. After a reset, `balance == cost == 8` and cooldown is active; a balance-first check would let the very next convene straight through and the wait would never bite. Code checks the winzip cooldown branch FIRST (credit_service.py:237), so it holds. |
| **Independent 5-cycle driver** (not the CR047 tests) | Fresh sqlite DB, armed winzip, walked exhaust→reset→3 impatient re-taps→wait→spend across 5 windows. Result: **6 rooms (1 free + 5 paced), one per cooldown; 15 during-cooldown taps blocked with NO double-grant and cooldown never extended; `winzip_reset` events == 5; `credits_spent` == 6.** Then paid-plan (trader, balance 3) → hard wall, no funnel, no top-up; `GTM_FUNNEL=none` → hard wall, no re-grant, no cooldown. |
| **No double-grant** | Reset uses `credit_balance = cost` (SET, not increment). During cooldown the block branch returns without re-granting. Even a hypothetical concurrent double-exhaustion is bounded — SET caps the balance at `cost`, never accumulates. |
| **Deferred-raise contract** | The +1-Room re-grant is committed inside the session; the 402 is raised AFTER the `with` block, so the grant persists across the refusal (same pattern CR039 relies on). Pinned + reproduced. |
| **Migration** | `c5d6e7f80019` → down `b4c5d6e70018`. Verified **single head** (22 revisions, one leaf) via script; alembic stamps it cleanly onto a fresh DB in my driver run. Nullable, no server_default, no backfill → every existing row reads NULL = no cooldown, and `_as_utc(None)` handles it. |
| **402 body** (room.py:179-196) | Lands BEFORE the StreamingResponse (a refusal mid-stream can't set status). Carries `funnel`/`cooldown_until`/`retry_after_seconds`; `retry_after_seconds = max(0, int(remaining))` guards negatives. Endpoint shape reproduced by `test_stream_402_carries_the_winzip_cooldown` (861 suite). |
| **CR040 degrade-loudly** | `gtm_funnel: Literal["none","winzip"]` → typo fails boot (`Settings(gtm_funnel="bogus", _env_file=None)` raises ValidationError — reproduced). `GTM_FUNNEL`/`WINZIP_COOLDOWN_MINUTES` both forwarded in `docker-compose.yml` api-alpha env → config-compose parity holds (the twice-burned DEF038/DEF063 class). |
| **Never-raises** | Winzip path is pure `datetime`/`timedelta` arithmetic + integer compares — no NaN/div, no DEF052 class. `_as_utc` normalizes the SQLite-naive / Postgres-aware split, same as `_ensure_period`. |
| **Floor-Pass-only gate** | `amount is None AND eff == FLOOR_PASS AND settings.gtm_funnel == "winzip"`. Paid plans + 1-on-1 fixed-price spends fall to the unchanged legacy branch. Reproduced (paid trader → hard wall). |
| **Mandate exposure** | `schemas/mandate.py` + `api/mandate.py` surface `room_cooldown_until` for the client's pre-emptive gate. Additive, nullable. |

### Mobile (static-verified; device render deferred)

| Dimension | Result |
|---|---|
| Typed exception parse | `InsufficientCreditsException.fromJson` is null-safe on every field (`(x as num?)?.toInt() ?? 0`, `parseDt` tolerates non-string/empty/unparseable), tolerates wrapped `{detail:{…}}` or flat body → a malformed 402 cannot crash the client. |
| streamRoom 402 | On `statusCode == 402`, reads the body, `jsonDecode` in try/catch → typed throw; decode failure → generic `Exception` (graceful). |
| Provider catch ordering | `on InsufficientCreditsException catch (e)` is placed BEFORE the generic `catch (e)` — Dart evaluates `on`-clauses in order, so the paywall wins and never degrades to "Stream failed". |
| `_PaywallCard` | `_remaining` clamps negatives to zero; timer runs only when >0, cancels + announces once (`_announced` guard), disposed in `dispose()`; already-elapsed renders ready with no chime; Convene shown only when ready (re-calls `start()`, self-heals a boundary re-block). |
| TTS fail-open | `_announceReady` + `_preferFemaleVoice` both wrapped in `try/catch (_) {}` — "the voice is a delight, never load-bearing"; a device with no usable engine still shows Convene + countdown. |
| Disclosure / naming | Copy uses **AMI** by name ("AMI's topping you up"), no "the AI" anywhere in the new keys; the reset is genuine (server already re-granted), so the countdown is honest — no false promise. |

## OUT-OF-SCOPE (non-blocking, informational)

- **O1 — pre-existing `spend()` concurrency, NOT introduced by CR047.** Two exactly-
  simultaneous `spend()` calls at `balance >= cost` could bill one charge for two
  runs (no row-lock); this is a CR039 property of the whole credit path, unchanged
  by CR047. CR047's winzip reset is actually *more* race-robust than an increment
  would be (SET caps the balance at `cost`, so concurrent exhaustions can't hand out
  infinite credit — worst case is an extra logged `winzip_reset` with the balance
  still pinned to 8). Real exposure is low for a single-user sequential mobile client
  (same-user+ticker also collapses via Room dedup). No DEF recommended; noted for the
  register's awareness. Architect mints if it's ever worth a row-lock.

## NEEDS-DEVICE-CHECK / live (legitimately deferred by the architect)

- **Device:** `_PaywallCard` countdown, the `flutter_tts` voice line, and the Training
  CTA are unexercised on a physical iPhone (no device in-session; Mac is pure editor).
  Covered by Saiful's acceptance test (Acceptance #3). A ≤1s client/server clock-skew
  at the cooldown boundary self-heals (a Convene tap re-blocks with a fresh short
  countdown, never a crash or a lie).
- **Live Alpha (Acceptance #2):** the 402→reset→wait→success loop on melehost is
  reproducible only after `/promote-to-alpha` AND setting `GTM_FUNNEL=winzip` in the
  live `.env` — an arming/go-live config call for Saiful, not part of this self-test.
  The handshake COMPLETE correctly precedes promotion on risky work; the backend logic
  is fully reproduced at code level (861 suite + my independent driver).

## Definition-of-Done disposition

| Architect row | Auditor disposition |
|---|---|
| Scope (backend funnel gate + typed-402 paywall/countdown, Floor-Pass-only behind `GTM_FUNNEL`) | OK — verified against CR047 spec Scope/Acceptance. |
| Tests (861; +7 winzip) | **Reproduced** (861 passed) + **independently re-derived** the loop with my own 5-cycle driver. |
| Manual verification (units + TestClient) | OK — backend reproduced; live-Alpha + device correctly carried to NEEDS-DEVICE-CHECK / post-promote (see above). |
| Docs (CR047 doc + register + CR045 cross-link + config/migration comments) | OK. |
| Commit tag `(AT:R63 CR047)` on `67dcbe3` | OK. |
| Register `in_progress` → `done` on this COMPLETE | OK — architect flips on COMPLETE. |
| Scope discipline (only CR047 files staged; CR045/CR046 carried, not authored here) | OK — the `67dcbe3` diff is CR047-only; the noted pre-existing commits are prior local-only work carried to origin. |

---

## Verdicts

| Item | SHA | Verdict |
|---|---|---|
| CR047 | `67dcbe3` | **COMPLETE (round 1)** — winzip cooldown-before-balance ordering correct + independently re-derived (6 rooms/5 cooldowns, no double-grant across 15 taps, paid-bypass + default-off hard-wall); migration single-head, nullable/no-backfill, stamps clean; 402 body + Literal boot-fail + compose parity (CR040) reproduced; mobile 402 flow null-safe, typed-catch ordered, TTS fail-open, AMI-named honest copy; 861 suite + `flutter analyze` 0-new reproduced. 1 non-blocking pre-existing-concurrency obs; device + live-Alpha legitimately deferred. |

OUT-OF-SCOPE: O1 (pre-existing `spend()` concurrency — informational, CR047 doesn't worsen it).
