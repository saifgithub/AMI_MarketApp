# CR027 — Notification infrastructure (push + in-app) and price alerts

**Status:** proposed · **Session:** AT:architect · **Date:** 2026-07-12, scope expanded 2026-07-31
**Source:** migrated from `Silent_Scout/10_price_alerts/` as part of closing and
deprecating Silent_Scout; expanded per Saiful, 2026-07-31 — *"let's put in all
[that's] needed for a push notification capability, and an in-app notification
facility into this CR."*

## Scope expansion, 2026-07-31

Originally this CR was one feature (price alerts) built directly on OneSignal. Two
things changed that: (1) CR095 (daily challenge reminder) and CR109 (The Game's
notification matrix) both already depend on this CR for push rather than building
their own, and BL11 (trial-end push) and the Room's `TODO B1` verdict-push stub are
the same shape again — four separate features about to reinvent one integration; (2)
nothing in the repo today gives a user a durable, in-app record of a notification —
push is the *only* channel, so a missed/denied/silently-failed push is gone forever,
which is exactly the CR040 failure mode (a feature that works only when an external
service, permission and connectivity all cooperate, with no visible trace when they
don't). **This CR now owns the shared notification infrastructure — a generic
backend service + an in-app notification centre — with price alerts as its first
consumer**, not a one-off alert feature that happens to use OneSignal.

**Nothing here is built. Design stage.**

---

## 1. Prerequisites (external, before any of this can ship)

- **A15 — OneSignal account + Apple Dev APNs certificate (iOS).** Saiful, external.
  Blocked today.
- **A15b — Android/FCM credential for OneSignal. NEW, found during this expansion.**
  APNs is Apple-only; Android-GMS push goes through **Firebase Cloud Messaging**, a
  separate credential OneSignal also requires — `project_plan.md`'s original A15
  line named only the APNs half. Two options, Saiful's call:
  - **Bring your own Firebase project** — Server Key/Service Account JSON entered
    into the OneSignal dashboard, `google-services.json` bundled into
    `mobile/android/app/`. Own quota, own Firebase console visibility.
  - **OneSignal's auto-generated Firebase project** — zero external setup, shared
    quota. Recommended for alpha; revisit before Beta scale.
- **Platform runtime permission, not a cert but easy to miss:**
  - iOS: `UNUserNotificationCenter` authorization prompt. A cold OS prompt on first
    launch is a known bad pattern (declines are permanent without a Settings trip)
    — needs a soft in-app ask first, system prompt only after the user says yes.
  - **Android 13+ (API 33) requires runtime `POST_NOTIFICATIONS` permission** —
    changed from "on by default" in prior Android versions. Missing this silently
    means zero Android push with no error surfaced anywhere (CR040 shape again).

Once A15/A15b clear, A16 (below) is Claude's build — nothing else is externally
blocked.

---

## 2. Architecture — generic notification service (the new part)

**Backend.** A `notifications` table, one row per notification regardless of
delivery channel or outcome:

`id, user_id (FK), type (price_alert | daily_challenge | game_event | trial_end |
room_verdict | ...), title, body, deep_link (route + params, JSON), source_ref
(nullable — the alert/run/entry that generated it), read_at (nullable), created_at`.

A single `notification_service.py::notify(user_id, type, title, body, deep_link,
source_ref=None)` is the **only** write path — every feature that wants to notify a
user (price alerts, daily challenge, game events, trial-end, Room verdicts) calls
this, not OneSignal directly. `notify()`:

1. Writes the row unconditionally — this is what makes the in-app centre the
   durable source of truth, not push.
2. Attempts OneSignal delivery (respecting the caller's rate-limit/quiet-hours
   policy — CR109 §10 already specs ≤1/day, ≤4/week, quiet hours for its own
   events; this generalises the pattern rather than each feature reinventing it).
3. **Push failure never blocks step 1** — same principle CR027's original alert
   design already had (*"silent push failure is acceptable... never block the
   state transition on push delivery"*), now the default for every notification
   type instead of price alerts' own special case.

Device-token lifecycle: OneSignal `external_user_id` set to `user_id` at login,
cleared at logout (so a signed-out device stops receiving another user's push on a
shared phone); multi-device is native to OneSignal's model (one `external_user_id`,
many subscribed devices).

**Frontend.** OneSignal Flutter SDK initialises at app start, requests permission
per the soft-ask pattern above, registers the device. A single deep-link dispatcher
maps `deep_link.route` to a Flutter route (`open_holding_detail`,
`open_journal_entry`, `open_room_verdict`, `open_lesson`, `open_game_close`, ...) —
one table, not one `if` per feature.

---

## 3. In-app notification facility (the other new part)

Nothing like this exists today — confirmed zero notification UI anywhere in
`mobile/lib/`, no notification model in `backend/app/`. Scope:

- **Bell + unread-count badge**, home not yet decided — coordinate with CR133
  (bottom-nav restructure owns shell real estate); candidates are a Floor-header
  icon or a tab inside `YOU`. Flagged for whoever lanes this, not decided here.
- **Notification list screen** — reverse-chronological, unread visually distinct,
  tap marks read + fires the deep link, mark-all-read action. Empty state reuses
  `AmiEmptyState` (the DEF098/CR134 class — no new bespoke empty-state widget).
- **Per-category preferences** — a section in Settings (or `YOU` post-CR133) toggling
  each `type` independently, plus the OS-level "notifications are off, tap to fix"
  banner when permission was denied. Quiet hours and frequency caps are
  server-enforced defaults (§2), not user-configurable at MVP.
- **Badge-count parity** — the OS app-icon badge count and the in-app bell's unread
  count both read from the same `notifications` table; no second counter to drift.
- **Retention** — unbounded per-user growth is a real risk; cap or age out (e.g.
  keep last N / last 90 days) rather than leaving this unspecified.

---

## 4. Price alerts (original scope, now a consumer of §2/§3 rather than its own stack)

Alert feature that fires when a trade's stop/target or a manual price threshold is
crossed, with agent commentary in the notification. `SimTradeRow.stop` already
captures stop logic.

**Correction from the original design:** source docs named a "Risk Analyst" as the
agent generating commentary — that agent doesn't exist (see CR026's correction, same
fabricated citation, same root cause). Commentary routes through the **Portfolio
Manager** or **Concierge** instead.

### Data model — `price_alerts` table

`id, user_id (FK users), ticker, threshold_type (stop|target|manual_above|manual_below),
threshold_price, status (active|fired|cancelled), trade_ref (FK sim_trades, nullable),
created_at, fired_at, cancelled_at, agent_commentary (280 char)`. State machine:
`ACTIVE → FIRED` (threshold breach) or `ACTIVE → CANCELLED` (user cancels); terminal
states are read-only (audit trail). Indexes on `(user_id, status)`,
`(ticker, status)`, `fired_at`. `trade_ref` nullable — manual watchlist alerts don't
need a trade. Closing a trade does not delete its alert (audit trail).

### Evaluation loop

APScheduler job, 300s interval (matches the yfinance quote cache TTL used elsewhere in
this codebase). Fetch all `status=active` alerts grouped by ticker, one price fetch per
ticker (not per alert), evaluate each alert's threshold, fire on breach. Threshold
semantics: `stop`/`manual_below` fire when price falls below; `target`/`manual_above`
fire when price rises above. Price-fetch failure (timeout/rate-limit) → skip that
ticker for the cycle, never fire a false alert on missing data. Once `FIRED`, an alert
is skipped by subsequent cycles — no duplicate pushes.

**Mandate check before firing:** verify the alert doesn't imply a mandate violation
(e.g., a `target`-type alert implying a short position when the mandate disallows
shorting) — if non-compliant, log and leave `ACTIVE` rather than firing.

### Notification content

On fire, calls `notification_service.notify(user_id, type="price_alert", title=
"Price Alert: {TICKER}", body=<commentary, ≤280 chars>, deep_link=
{route: "open_holding_detail", ticker}, source_ref=alert_id)`. Commentary generation
(`generate_alert_commentary()`) branches on `threshold_type` — stop→risk-implication
framing, target→profit-taking framing, manual→neutral framing — sourced from
Portfolio Manager/Concierge context, not a Risk Analyst.

**Rate limiting:** max 1 alert push per user per minute, max 3 per hour, max 10
distinct active alerts per user (oldest auto-close past that) — via a Redis TTL cache
key, same pattern as the existing `rate_limit.py` sliding-window limiter.

---

## 5. Consumers (should route through §2, not build their own push)

- **CR095** (daily challenge reminder, push half) — depends on this CR already;
  should call `notification_service.notify(type="daily_challenge", ...)`.
- **CR109** (The Game) — its notification matrix (entries closing, run closing, a
  challenge received, results ready, dropped out of top 10) is the same shape;
  §10's ≤1/day, ≤4/week, quiet-hours rule becomes this service's default rather
  than a game-specific implementation.
- **BL11** (trial-end push, `project_plan.md`) — same integration, `type="trial_end"`.
- **Room verdict push** — `room.py:134`'s `TODO B1` stub becomes
  `notify(type="room_verdict", ...)`.

None of these are built here; this CR just becomes the place they all plug into
instead of each shipping a parallel OneSignal integration.

---

## Scope

**In:** `notifications` table + `notification_service.py` (generic service, §2); the
in-app notification centre — bell/badge, list screen, preferences, retention (§3);
OneSignal SDK integration + permission-priming UX (iOS soft-ask, Android
`POST_NOTIFICATIONS`) + deep-link dispatcher; `price_alerts` table + evaluation loop
plus rate limiting and mandate pre-check (§4), as the first consumer proving §2
works end-to-end.

**Out:** A15/A15b (OneSignal account, APNs cert, Android/FCM credential — Saiful,
external); actually wiring CR095/CR109/BL11/Room-verdict onto the service (their own
CRs' scope — this CR builds the service and one working consumer, not every
consumer); an Android-HMS push channel (v1.1, `platform_facade.md`).

## Acceptance

- Blocked until A15/A15b clear. Once unblocked:
- A price alert fires correctly on threshold breach, never duplicate-fires, never
  fires on missing price data; mandate-incompliant alerts don't fire.
- **Every** `notification_service.notify()` call writes a `notifications` row
  regardless of push outcome — push failure, denied permission, or OneSignal being
  unreachable never prevents the in-app record from existing.
- The in-app notification list shows the row, correctly marks read on tap, and
  navigates via the deep link; unread badge count matches between OS icon and
  in-app bell.
- iOS shows a soft in-app ask before the system permission prompt; Android requests
  `POST_NOTIFICATIONS` at the same point (API 33+) and the feature degrades
  visibly (not silently) when denied on either platform.
- Push commentary for price alerts is generated from a real agent context
  (Portfolio Manager or Concierge), not the original "Risk Analyst" framing.
- Rate limits and quiet hours enforced at the service layer, not per-consumer.
