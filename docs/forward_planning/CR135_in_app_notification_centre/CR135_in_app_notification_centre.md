# CR135 — In-app notification centre

**Status:** proposed · design stage, split out of CR027, nothing built.
**Filed:** 2026-07-31 · `AT:R65` · **Depends on:** [CR027](../CR027_price_alerts/CR027_price_alerts.md) (notification_service.py + `notifications` table), [CR133](../CR133_bottom_nav_restructure/CR133.md) (bottom-nav restructure — owns the shell real estate this CR needs a home in)

---

## 1. Why this is its own CR

CR027 originally specced a full "in-app notification centre" (bell, unread badge,
notification list screen, per-category preferences, a "notifications off" banner)
alongside the push/notification-service infrastructure. During CR027's build
kickoff (2026-07-31), Saiful cut it live:

> *"This is a push/in app notification CR. why do we have 'bell/badge'?"*

CR133 (bottom-nav restructure) is still design-stage — "no Flutter written" — and
is the CR that actually owns where a persistent icon like a notification bell
would live in the shell (`YOU` tab vs. a header slot, per CR133 §1). Building a
provisional bell now, ahead of CR133 landing, is exactly the kind of throwaway
chrome CR133 itself already warns against elsewhere in the nav. So: CR027 ships
the plumbing (durable `notifications` row + push delivery + a foreground toast
via `HexToast`), and this CR ships the actual screen a user opens to browse their
notification history — once there's a stable place to put its entry point.

**Not yet lanable** — blocked on CR133 shipping real Flutter (currently prototype
only), so the bell/badge has a real home instead of another provisional strip.

---

## 2. Scope (carried over verbatim from CR027 §3, the original spec)

- **Bell + unread-count badge** — home decided by CR133 (candidates were a
  Floor-header icon or a tab inside `YOU`; CR133 ultimately puts general settings
  content in `YOU`, so that's the likely home, but not decided here).
- **Notification list screen** — reverse-chronological, unread visually distinct,
  tap marks read + fires the deep link (reusing CR027's `DeepLinkDispatcher`),
  mark-all-read action. Empty state reuses `AmiEmptyState` (DEF098/CR134 class —
  no new bespoke empty-state widget).
- **Per-category preferences** — a section in Settings (or `YOU` post-CR133)
  toggling each notification `type` independently (`price_alert`,
  `daily_challenge`, `game_event`, `trial_end`, `room_verdict`), plus the
  OS-level "notifications are off, tap to fix" banner when permission was
  denied (reusing `sharia_verdict_banner.dart`'s visual shape).
- **Badge-count parity** — the OS app-icon badge count and the in-app bell's
  unread count both read from the same `notifications` table; no second
  counter to drift.
- **Retention** — CR027 wired the existing 90-day audit-trim job
  (`backend/app/services/audit.py::trim_audit_tables()`) to age out old rows;
  this CR should double check that window is still sensible once a real list
  screen exists to be affected by it (e.g. does 90 days ever visibly truncate a
  user's history in a way that matters), not leave it as an unquestioned
  backend default.

## 3. Backend surface needed (not built by CR027)

CR027 deliberately does **not** ship any `notifications` CRUD API or a
preferences table — there's no consumer for them until this CR exists. This CR
needs to add:
- `GET /v1/notifications/{user_id}` (list, reverse-chronological), `POST
  .../{id}/read`, `POST .../read_all`, `GET .../unread_count`.
- A `notification_preferences` table (`user_id, type, enabled, updated_at`) +
  `GET`/`PATCH /v1/notifications/{user_id}/preferences`.
- Corresponding `list_notifications`/`mark_read`/`mark_all_read`/`unread_count`
  functions on `notification_service.py` (CR027 only ships `notify()`).

## Scope — Out

- Anything CR027 already ships (the `notifications` table, `notify()`, OneSignal
  SDK integration, deep-link dispatcher, foreground toast, price alerts).
- Quiet hours / frequency-cap configuration — still deferred to CR109 per CR027.

## Acceptance

- The in-app notification list shows every row `notify()` has ever written,
  correctly marks read on tap, and navigates via the existing deep-link
  dispatcher; unread badge count matches between the OS icon and the in-app
  bell.
- Preferences toggles actually suppress push delivery for a disabled `type`
  (server-enforced, not just a client-side hide).
- The "notifications off" banner appears when OS permission is denied and
  disappears once the user re-enables it from the OS Settings deep link.

---

## Build note — backend half SHIPPED (2026-08-20, AT:R73)

The backend surface of §3 is built; the mobile half (bell/badge, list screen,
preferences UI, notifications-off banner) is deferred to after the current
AT:R73 batch merges, per the lane brief (shared YOU-tab real estate with the
in-flight CR102 mobile inbox).

What landed:

- **Routes** (`backend/app/api/notifications.py`, plain-`def` per DEF200,
  NOT yet wired into `main.py` — the orchestrator wires routers):
  `GET /v1/notifications/{user_id}` (paginated `limit`/`offset`, newest-first,
  returns `{items, total}`), `POST .../{notification_id}/read` (idempotent,
  cross-user 404 indistinguishable from nonexistent), `POST .../read_all`
  (returns `{updated}`), `GET .../unread_count`, `GET`/`PATCH
  .../preferences`. Path-user mismatch is 403 (price_alerts pattern).
- **Table** `notification_preferences` (composite PK `user_id`+`type`,
  `enabled`, `updated_at`) — migration `a135a000001f` off head
  `c102a000001e`. No row = enabled; only toggles write rows.
- **Service** (`notification_service.py`): `list_notifications` /
  `mark_read` / `mark_all_read` / `unread_count` / `get_preferences` /
  `set_preferences`, and **server-side enforcement**: `notify()` skips the
  OneSignal attempt (`push_status="pref_disabled"`) for a disabled type —
  the durable row is still written, so the in-app centre still shows it.
- **Vocabulary correction** — §2's type list (`price_alert`,
  `daily_challenge`, `game_event`, `trial_end`, `room_verdict`) was CR027-era
  speculation. The types the service ACTUALLY emits, now canonical in
  `app/schemas/notifications.py::NOTIFICATION_TYPES` (the anchor for the
  mobile lane's Dart-enum parity test, DEF210 class): `price_alert`,
  `daily_reminder`, `game_entries_closing`, `game_final_stretch`,
  `game_settled`, `game_rank_move`, `resting_order_filled`,
  `resting_order_triggered`, `resting_order_rejected`.
  `tests/unit/test_cr135_notifications_api.py` asserts emitter⇄vocabulary
  parity, so a new emitter type that skips the vocabulary fails the suite.
- **Retention sanity (§2 last bullet):** `trim_audit_tables()` trims
  `notifications` at 90 days — at alpha cadence (a handful of pushes/user/week,
  games policy-capped) a page of 50 never truncates visibly; revisit only if
  the list screen ships infinite scroll past ~500 rows.
