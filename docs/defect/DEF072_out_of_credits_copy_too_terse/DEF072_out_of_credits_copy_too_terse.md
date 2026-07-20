# DEF072 — Out-of-credits copy is too terse

**Source:** `bug:6566b5da` · **Reporter:** Platinum Anchor (`8f1e288a`, floor_pass, iOS `0.1.0+39`) · **Filed:** 2026-07-20 (AT:R63) · **Status:** resolved AT:R63 — `roomPaywallBody` softened, `roomWinzipBody` warmed; ships `0.1.0+41`.

## Symptom

Report (with screenshot of the "Out of Room credits" card): *"the message is terse. we
should use softer message (eg. we are sorry. you have run out of credit. it will be
replenished on `<date and time>`)."*

The card shows title **"Out of Room credits"** and body **"You've used your Room credits.
They reset on 2026-08-01."** Factually correct (the reset date is already present) but
curt — reads as a scold, not an apology.

## Not this DEF — the doubled apostrophe

The screenshot also renders **"You''ve"** (two apostrophes). That is a *separate,
already-fixed* issue — **DEF069** (`use-escaping` off → `''` rendered literally), fixed at
HEAD and shipping in `0.1.0+40`. The reporter is on `+39`, which predates the fix. **Do
not re-fix it here.** Once `+40` reaches the device the apostrophe is gone; only the
*tone* remains open for this DEF.

## Root cause

Copy choice. The strings are local ARB, not server-sent:
- `roomPaywallBody` — [`mobile/lib/l10n/app_en.arb:614`](../../../mobile/lib/l10n/app_en.arb#L614) —
  *"You've used your Room credits. They reset on {date}."*
- rendered at `room_screen.dart:495` (`l.roomPaywallBody(_resetDateStr())`).
- Sibling: `roomWinzipBody` (`app_en.arb:604`) — the soft-wall variant — worth the same tone pass.

The backend 402 (`room.py:181-196`) supplies `resets_at`; the client formats the date. No
server copy change needed.

## Fix plan

Rewrite `roomPaywallBody` (and review `roomWinzipBody`) into an apologetic register,
**keeping the reset date**. Proposed EN:

> **Out of Room credits** — "Sorry — you're out of Room credits for now. They'll refresh on {date}."

Update the `@roomPaywallBody` context comment and the AR/MS placeholders. Regenerate l10n.
Ships as the next build (`0.1.0+41`); backend untouched, no promote.

Scope: mobile l10n only. Nothing structural.
