# CR043 — Close the bug-report feedback loop

**Filed:** 2026-07-19 (AT:R60) · **Status:** in_progress

Saiful: *"how do we communicate to the user that reported an error? i want to 1. thanks
the user right after the report. 2. update the user once the error has been fixed."*

---

## The problem

A user files a bug into what is, from their side, a void. The loop is open at both ends.

**On submit, the user gets nothing.** `bug_report_sheet.dart:120-133` pops the sheet on
success — no toast, no dialog, no haptic. The *failure* path shows an inline red
"Failed to send — please try again" (`:253-259`), so the feedback is inverted: explicit
on failure, silent on success. The user cannot distinguish "sent" from "the sheet closed".

The reference exists on the wire and is thrown away. `POST /v1/feedback/bug` returns the
report UUID (`schemas/feedback.py:55-59`, set in `feedback_store.py:46-51`), but
`feedback_providers.dart:74` awaits `api.submitBugReport(...)` without assigning the
result. `FeedbackState.submitted` is written at `:85` and read by no widget.

**On fix, nothing reaches them.** `/v1/feedback` is POST-only: no GET route, no client
method, no "my reports" screen anywhere in `mobile/lib/`. **35 reports are `resolved` and
not one of those users was ever told.** The bug they took the trouble to report may have
been fixed months ago; from inside the app it is indistinguishable from ignored.

## Decisions (Saiful, AT:R60)

| Question | Decision |
|---|---|
| Channel | **Toast on next app open.** Not push, not email. |
| Trigger | **`status='resolved'`** — the merge-confirmation flip Saiful owns. |
| Scope | Thank-you on submit + resolution notification. |
| Deferred | Localisation sweep of the sheet; full CR002; a "My reports" screen. |

**Why not push:** absent at every layer — no SDK in `mobile/pubspec.yaml`, no
`aps-environment` in `Runner.entitlements`, no token column on `users` or `user_devices`.
`backend/app/api/room.py:125-129` logs `room_push_stub` and dispatches nothing. A15 is
already blocked on Saiful's cert work. Multi-day, and it would block this.

**Why not email:** Resend is live and keyed on Alpha (`email_service.py:44`), but it is
hard-wired to `send_magic_link(to, code)` and — decisively — the app is anonymous-first.
`POST /v1/auth/anon` creates users with `email=NULL`, so most of the population is
unreachable by email regardless of the send capability.

**Why toast-on-open works:** `HexToast.show` resolves `Overlay.maybeOf(context,
rootOverlay: true)` (`hex_toast.dart:22`), so it fires without a Scaffold — including
at app launch. Cold start is effectively the app's only sync point (there is no
`AppLifecycleState.resumed` hook and no `RouteAware` anywhere), which is exactly when we
want to check. No new infrastructure, no Apple capability, no email address required.

## Hard dependency — CR002 (minimal form)

`BugStatus = Literal["open","triaged","fixed","wont_fix"]` (`schemas/feedback.py:24`)
does not contain `resolved`, but the DB holds 35 of them. The create path always writes
`open`, so nothing breaks today — **the first read endpoint that serialises a resolved
row raises `ValidationError`.** `triaged` and `fixed` have never been written.

This CR lands only the minimum that unblocks it: canonicalise the Literal to the five
values actually in operational use and fold the one `closed` row. The rest of
[CR002](../CR002_bug_status_vocabulary/CR002_bug_status_vocabulary.md) stays `proposed`.

## Measured state (melehost, 2026-07-19)

| status | count | with `user_id` |
|---|---|---|
| `open` | 3 | 3 |
| `resolved` | **35** | **29** |
| `wont_fix` | 4 | 4 |
| `closed` | 1 | 0 |

**The 29 are the trap.** Ship the notifier without a backfill and 29 users get a burst of
historical "your bug is fixed" toasts on first launch after the deploy — for bugs they
filed and forgot months ago. The migration must stamp `acknowledged_at` on every
pre-existing terminal row so only *future* resolutions notify.

## Scope

### Phase 1 — thank-you on submit (client-only, ships independently)

- `feedback_providers.dart` — add `reportId` to `FeedbackState`; capture the discarded
  return value at `:74`.
- `bug_report_sheet.dart` — on success, `HexToast` with the 8-char ref, `hexGreen`.
  Capture the parent context **before** `pop()`.
- New copy goes into `app_en.arb` with context comments. The sheet's 12 pre-existing
  hardcoded strings stay — separate follow-up.

### Phase 2 — CR002 minimal

- `BugStatus` → `open · in_progress · pending_review · resolved · wont_fix`.
- `UPDATE bug_reports SET status='resolved' WHERE status='closed'` (1 row, no `user_id`,
  notifies nobody).

### Phase 3 — resolution notification (backend)

- Migration off head `a3b4c5d60017`: `resolved_at`, `resolution_note`,
  `acknowledged_at` on `bug_reports`, all nullable. **Backfill `acknowledged_at` for
  every `resolved`/`wont_fix` row.**
- `GET /v1/feedback/updates` — caller's `resolved` + unacknowledged reports.
- `POST /v1/feedback/{id}/ack` — stamps `acknowledged_at`, scoped to the caller's rows.
- Auth **required** on both, unlike the POST's deliberately lenient `_resolve_user_id`
  (`api/feedback.py:38-46`, "we'd rather lose the user_id than lose the report").
- Ack is server-side, not SharedPreferences, so "seen" survives reinstall.

### Phase 4 — client fetch + toast

- `api_client.dart` — `getFeedbackUpdates` + `ackFeedback`.
- A non-`autoDispose` `feedbackUpdatesProvider` (the existing `feedbackNotifierProvider`
  is `autoDispose`, scoped to the sheet's lifetime).
- Fetch on the cold-start path in `_AuthGate` (`app.dart:60-95`) after `auth.token !=
  null`, inside `HomeShell` so a root Overlay exists. Ack on display.

### Phase 5 — workflow

- `.claude/commands/fix-bugs.md` — rule 8 stands (`/fix-bugs` still stops at
  `pending_review`; Saiful owns the `resolved` flip). Add that the flip is now
  **user-visible** and should carry a plain-English `resolution_note` — the reporter
  reads it, so no jargon, no defect IDs, no file paths.

## Acceptance

1. Submitting a report shows a confirmation toast carrying an 8-char ref that matches a
   real `bug_reports` row.
2. Flipping a report to `resolved` causes exactly one toast on that user's next cold
   start, and none on the second.
3. `SELECT COUNT(*) FROM bug_reports WHERE status='resolved' AND acknowledged_at IS NULL`
   is **0** immediately post-migration — no historical burst.
4. A user cannot read or ack another user's report.
5. A `pending_review` report never notifies.
6. `pytest backend/tests/unit/ -q` green, including a `BugStatus` round-trip over all
   five canonical values.

## Out of scope

Localising the sheet's 12 hardcoded English strings (it stays English for MS/AR users);
a "My reports" list screen; **discoverability of the entry point** — the only way to file
a bug is a long-press on grey `slate600` version text in Settings
(`settings_screen.dart:969-989`), with no affordance, and no shake trigger despite
`BugReportRow`'s docstring claiming "shake / long-press"; the unwired
`HexAvatarStatus.attention` badge; the 28 raw-`$e` exception leaks across
`mobile/lib/state/`.
