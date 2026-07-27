# CR102 — In-app messaging to beta testers (broadcast + reply)

**Filed:** 2026-07-27 (AT:R65) · **Status:** proposed — **design only, not built**

Saiful: *"I need a way to communicate to the beta testers directly on the app. Kind of an
in-app messaging. I think we have this capability already?"*

Deferred deliberately: *"this is documentation only! will be developed after a few more
critical CRs are done."* Nothing in this CR is implemented. This document is the spec to
build from when it comes up the queue.

---

## The problem

There is no way to say anything to a tester. Not "new build is up", not "known issue with
the Room today", not "what did you make of the Concierge?". The only outbound channel that
exists reaches one user about one thing: a bug they personally filed.

We half-had the capability, and it is the wrong half.

| Channel | State (verified 2026-07-27) |
|---|---|
| Push (APNs / FCM / OneSignal) | **Absent at every layer.** No SDK in `mobile/pubspec.yaml`; no `aps-environment` in `mobile/ios/Runner/Runner.entitlements`; no token column on `users` or `user_devices`. Two dead stubs only — `api/room.py:133` logs `room_push_stub`, `services/room_runner.py:1551` is a docstring. [CR027](../CR027_price_alerts/) designs it and is hard-gated on Saiful's external cert work (A15/A16). |
| Email | **Unusable at this population.** 102 users on Alpha; **5 have an email address**. Anonymous-first auth (`POST /v1/auth/anon`) leaves the rest `NULL`. Backend email is `send_magic_link(to, code)` and nothing else (`services/email_service.py`). |
| Server→user in-app | **Exactly one pipe, hard-scoped.** [CR043](../CR043_bug_feedback_loop/CR043_bug_feedback_loop.md) (`9373b9a`) shipped `GET /v1/feedback/updates` + `POST /v1/feedback/{id}/ack`, drained as `HexToast`s on cold start by `screens/feedback/bug_resolution_toasts.dart`, mounted at `app.dart:100`. It can only tell a reporter *their own* bug was fixed. No broadcast, no inbox, no reply, no way to address an arbitrary user. |
| Admin send-side | Exists, with zero messaging in it. `api/admin.py` (`/v1/admin/*`, static `ADMIN_SECRET` bearer) and a vanilla-JS SPA at `app/static/admin.html`, served at `GET /admin`. Its verbs are plan / trial / credits / suspend — all single-user, no "all users" selector. |

So in-app is not the *preferred* channel. At 5/102 reachable by email and 0/102 by push,
it is the **only** channel.

## Measured audience (melehost, 2026-07-27)

| Metric | Count |
|---|---|
| `users` rows, raw | 102 |
| **Real users** (after the synthetic + seed filter in `memory/feedback_user_report_exclusions.md`) | **79** |
| …of those, suspended | 0 |
| Users with a non-null `email` | 5 |
| Created in the last 30 days | 63 |
| Devices on current build `0.1.0+55` (all active ≤14 d) | 12 |
| Distinct `app_version` values across `user_devices` | 15+, back to `0.1.0+29` |

That last row is the case for build targeting: testers are scattered across a dozen builds
and "please update, the bug you're hitting is fixed" is a message we cannot currently send.

## Decisions (Saiful, AT:R65)

| Question | Decision |
|---|---|
| Shape | **Broadcast + reply thread** (two-way), not one-way |
| Surface | **Bell + inbox screen** with unread badge; `priority=high` *also* raises a toast on cold start |
| Targeting | everyone · by build/platform · by activity · one specific tester |
| Send side | admin API + `scripts/messages.sh` in this CR; admin-page compose tab deferred to **CR103** |
| Delivery | **Cold-start poll only.** No push — that stays CR027's problem. |

## Design

### Data model

Two tables, one Alembic migration. Models in `backend/app/db/models.py`, following the
existing `<Thing>Row` convention.

**`broadcasts`** — the ops record of an authored send.
`id`, `title`, `body`, `body_i18n` (nullable JSON `{ar,ms}`), `priority` (`normal|high`),
`audience_json`, `created_by`, `created_at`, `recipient_count`.

**`inbox_messages`** — the per-user delivered copy *and* the reply.
`id`, `user_id` (indexed), `broadcast_id` (nullable), `direction` (`out` = AMI→user,
`in` = user→AMI), `title` (nullable on replies), `body`, `reply_to_id` (nullable
self-ref), `created_at`, `read_at` (nullable), `toasted_at` (nullable).

**Fan-out happens at send time, not as a predicate evaluated at read time.** Three reasons:
`recipient_count` is then a measured number rather than an estimate; a reply threads
against a concrete row; and "everyone on build < 55" is a claim about who existed *when it
was sent* — someone who installs tomorrow should not receive it. At 79 users the fan-out is
one `INSERT … SELECT`.

**Audience resolution must exclude non-humans or the first `--to all` "reaches" 102 people
who are mostly fixtures.** One `resolve_audience()` function in the service, unit-tested,
never inlined at a call site. It applies:

- `suspended_at IS NULL`
- the synthetic + seed filter from `memory/feedback_user_report_exclusions.md`
  (`coalesce(last_app_version,'') <> 'room-benchmark'`, plus the 2026-05-24 05:10
  seed-burst predicate) — 23 rows today

### Backend

New `backend/app/api/messages.py` (user-facing) plus new routes appended to `api/admin.py`.
Register with one import + one `include_router` line in `main.py` (lines 11–32 / 185–206) —
there is no aggregator. Service `services/inbox_store.py`, modelled on
`services/feedback_store.py`. Schemas in `schemas/messages.py`.

**User routes** — auth via `get_current_user` (`api/dependencies.py`):

| Route | Behaviour |
|---|---|
| `GET /v1/messages` | Newest-first, both directions, each with `read_at`. The client derives the unread count; at these volumes a separate count endpoint is not worth a round trip. |
| `POST /v1/messages/{id}/read` | 204. **404 on another user's row** — same not-a-probe response as `api/feedback.py:154`. |
| `POST /v1/messages/{id}/reply` | Body ≤ 2000 chars; writes a `direction='in'` row with `reply_to_id`. |
| `POST /v1/messages/{id}/toasted` | Stamps `toasted_at` for the high-priority cold-start toast, so it fires exactly once and survives reinstall. CR043's server-side-ack rationale applies unchanged — a `SharedPreferences` flag would not. |

**Admin routes** — behind the existing `get_admin` / `ADMIN_SECRET` dependency:

| Route | Behaviour |
|---|---|
| `POST /v1/admin/messages/preview` | Resolves the audience, returns the count, **sends nothing**. The guard against a mistargeted blast; the CLI calls it first, always. |
| `POST /v1/admin/messages` | `{title, body, body_i18n?, priority, audience}` → resolve, fan out, return `{broadcast_id, recipient_count}`. |
| `GET /v1/admin/messages` | Broadcasts with reply counts. |
| `GET /v1/admin/messages/replies?since=` | Inbound feed. |

`audience` shapes:
`{"mode":"all"}` ·
`{"mode":"build","platform":"ios","app_version_lt":"0.1.0+55"}` ·
`{"mode":"activity","active_within_days":14}` or `{"dormant_beyond_days":30}` ·
`{"mode":"user","user_ids":[…]}`

Build and activity read `user_devices.app_version` / `.last_seen_at` — both populated today.
No new env vars, so no `test_config_compose_parity.py` exposure.

**Open question for build time — there is no `platform` column.** `users` and
`user_devices` carry `device_model` + `os_version` but nothing that says iOS vs Android
(`bug_reports.platform` exists, but only per report). Either infer from `device_model`
(`iPhone*`/`iPad*` → ios) — cheap but brittle — or add a `platform` column populated on
`/v1/auth/anon`, which is the honest fix. Decide before writing `resolve_audience()`;
`--to build` without `--platform` works either way, so this does not block the CR.

### Mobile

- **Model + client:** `mobile/lib/models/inbox_message.dart`; `ApiClient` methods
  (`services/api/api_client.dart`) next to the existing `feedbackUpdates()` at ~line 1175.
- **Providers:** `state/inbox_providers.dart`, following `state/league_providers.dart`
  (`FutureProvider` + `apiClientProvider`) and the fetch-then-ack contract in
  `state/feedback_providers.dart`. Add the new provider to the `ref.invalidate(...)` list
  in `_AuthGate` (`app.dart`) so it clears on identity change.
- **Bell:** `IconButton` + unread badge in the Floor header `Row`, between `Spacer()` and
  `StreakChip` — `screens/floor/floor_screen.dart:344-363`. Tab 0, first thing seen.
  `HexBottomNav` needs no change.
- **Inbox screen:** `screens/inbox/inbox_screen.dart` — `ListView` of `AccentCard`
  (`widgets/hex/accent_card.dart`; cyan = normal, amber = high), unread dot, tap → detail
  with a reply field. Detail marks read on open. Reuse `widgets/sheet_insets.dart` for the
  keyboard inset under the composer.
- **High-priority toast:** extend the existing drain loop in
  `screens/feedback/bug_resolution_toasts.dart` rather than adding a second overlay
  wrapper — one queue, same 1.2 s settle / 5 s / 600 ms cadence, so the two channels
  cannot fire over each other.

**Degrade loudly (CR040).** `feedback_providers.dart` swallows errors on purpose — right
for a toast, wrong for an inbox. The inbox screen must render a distinct **error + retry**
state; "couldn't load" must never look like "no messages". A silently-empty inbox is
precisely the DEF038 / DEF063 dark-feature class. The bell badge may be absent on error
(it has nothing to claim); the screen may not lie.

### Send side — `scripts/messages.sh`

Same shape as `scripts/users.sh`, but it talks to the **admin API over LAN-direct HTTP**
(`http://192.168.20.59:8001`, per `memory/feedback_lan_route.md`) rather than SSH + psql —
writes go through the API so validation and the audit record are not bypassed.

```
scripts/messages.sh send --to all --title "…" --body "…" [--priority high]
scripts/messages.sh send --to build --platform ios --version-lt 0.1.0+55 …
scripts/messages.sh send --to active --days 14 …
scripts/messages.sh send --to user --id <uuid> …
scripts/messages.sh replies [--since 7d]
scripts/messages.sh list
```

`send` always calls `/preview` first and prints `→ N recipients` for confirmation before
posting. `ADMIN_SECRET` from the environment, never a literal in the script.

### i18n

Chrome strings (screen title, "Reply", empty state, relative times) go in
`mobile/lib/l10n/app_en.arb` + `app_ar.arb` + `app_ms.arb` — the house rule stated in
`widgets/sharia_verdict_banner.dart`: strings come from the ARB, never from backend English.

The **message body is authored content**, not chrome. It ships from the server verbatim —
the same exception CR043 already makes for `resolution_note`. `body_i18n` lets Saiful supply
AR/MS when he has them; EN is the fallback. Per
`memory/feedback_content_change_flags_translation.md` the new ARB keys carry
`retranslate:[ar,ms]` on commit; no translation work happens inside this CR.

Copy rule: the sender is **AMI**. Never "the AI", never "the team".

## Acceptance

1. `POST /v1/admin/messages/preview` with `{"mode":"all"}` returns **79**, not 102 — the
   23 synthetic + seed rows are excluded, and so is any suspended user.
2. A broadcast to `--to user --id <uuid>` previews `→ 1 recipients`, and exactly one
   `inbox_messages` row is written.
3. On the next cold start that user's bell shows `1`; opening the inbox clears it; the
   count does not return on the following cold start.
4. A reply from the device appears in `scripts/messages.sh replies` with the correct
   `reply_to_id`.
5. `priority=high` raises a toast on the **next** cold start and **only** the next one,
   including across a reinstall (`toasted_at` is server-side).
6. A user cannot read, reply to, or ack another user's message — 404, indistinguishable
   from a nonexistent id.
7. Every admin route rejects a missing or wrong `ADMIN_SECRET`.
8. The inbox screen's error state is visually distinct from its empty state.
9. `pytest backend/tests/unit/ -q` green (1338 at the last merge); `cd mobile && flutter
   test` green.
10. `alembic upgrade head` on Alpha leaves a single migration head.

## Out of scope

- **Push.** Delivery is cold-start poll only, as with CR043. A tester learns of a message
  the next time they open the app. CR027 owns push.
- **CR043's bug-resolution toasts stay as they are.** Folding them into this inbox is the
  better end state and deserves its own CR — not this one.
- The admin-page compose tab → **CR103**.
- Attachments, rich text, scheduled sends, delivery/open analytics beyond read + reply
  counts.

## Build sequencing (when this comes off the shelf)

1. Models + migration + `resolve_audience()` + store, with units. *Largest single risk is
   the audience filters — that is where a mistargeted blast comes from.*
2. User routes + admin routes + `main.py` wiring, with units.
3. `scripts/messages.sh` — send/preview is verifiable against Alpha before any UI exists.
4. `ApiClient` + providers + inbox screen + bell + ARB keys, with widget tests.
5. High-priority toast folded into the existing drain loop.
6. Promote; run the acceptance list against the iPhone release build.

Note for step 1: `init_schema()` uses `create_all`, so a **missing migration passes on the
Mac and fails on deploy** — the CR043 commit hit exactly this. Verify `alembic upgrade
head` on Alpha post-promote, not locally.
