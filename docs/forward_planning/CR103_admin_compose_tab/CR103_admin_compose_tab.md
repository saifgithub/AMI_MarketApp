# CR103 — Admin-page compose tab for in-app tester messages

**Status:** shipped (pending promotion) · **Registry row:** [`_registry/CR103.row.md`](../_registry/CR103.row.md) · **Parent:** [CR102](../CR102_in_app_messaging/CR102_in_app_messaging.md)

## What

A MESSAGES tab in the existing vanilla-JS admin SPA (`backend/app/static/admin.html`,
served at `GET /admin` behind the `ADMIN_SECRET` bearer). The send-side UI half of
CR102's tester messaging — one more view in the existing page, not a new surface.

Three cards:

- **COMPOSE** — title (≤200), body (≤4000), priority (`normal`/`high`), audience
  picker mirroring `scripts/messages.sh`'s five `--to` values: `all` / `build`
  (needs `app_version_lt` with a `+<build>` suffix) / `active` / `dormant`
  (both map to `mode:"activity"`) / `user` (whitespace-separated ids).
  PREVIEW → `POST /v1/admin/messages/preview`, SEND → `POST /v1/admin/messages`.
- **BROADCASTS** — `GET /v1/admin/messages`, display-only (no resend/edit; the API
  has no such routes).
- **REPLIES** — `GET /v1/admin/messages/replies`, optional last-N-days filter
  (`since` built via `toISOString()`, which ends in `Z` — a `+00:00` offset 422s
  because a raw `+` in a query string decodes as a space). Each reply's user id
  links into the existing user-detail view (`loadUser`).

## Why

CR102 shipped the API + CLI; Saiful sends from the Mac today where `messages.sh`
is faster. The page earns its keep when he wants to send from a phone — the admin
SPA is already mobile-styled and token-unlocked on his devices.

## Preview-before-send is structural, not advisory

The server never orders the preview/send calls — ordering is a client contract
(`messages.sh` previews first, always, and aborts on 0 recipients). The tab
enforces the same contract in the UI:

- SEND is disabled until a preview for the **current** form state returns a count.
- Any edit to any compose field invalidates the preview (state cleared, SEND
  disabled).
- The arm/disarm is keyed to `JSON.stringify(payload) === previewedPayload`, not a
  boolean — `msgSend()` re-builds the payload and refuses anything not
  byte-identical to what was previewed, so a missed invalidation event still
  cannot send a stale target.
- `recipient_count === 0` keeps SEND blocked (excluded/suspended ids preview as 0
  by design).

## Scope corrections vs the registry row

- The row says audience "build+platform" — **platform targeting does not exist**.
  It was deliberately deferred out of CR102 (`Audience` has no platform field;
  `extra="forbid"` 422s it — `backend/app/schemas/messages.py`, proven at
  `backend/tests/unit/test_cr102_admin_messages.py::test_unknown_audience_key_rejected_loudly`).
  The picker offers build-targeting only; platform arrives only if CR102's open
  question (platform column vs infer from `device_model`) is ever decided.
- `body_i18n` (`ar`/`ms`) textareas omitted — alpha is EN-only and
  `scripts/messages.sh` doesn't send them either (architect ruling).
- Past broadcasts are display-only — no resend/edit routes exist (architect ruling).

## Implementation notes

- One file changed: `backend/app/static/admin.html`. No backend code, no
  migration, no env var, no l10n keys. `main.py` reads the file per request, so
  the next `/promote-to-alpha` rsync ships it.
- Reuses the SPA's existing `api()` bearer helper, `.card`/`.row`/`.lbl`/`.btn`/
  `.badge`/`.ev`/`.empty`/toast patterns; adds a two-tab bar (USERS | MESSAGES)
  shown only when authed.
- `api()` extended: FastAPI 422 `detail` arrays are joined into readable text
  instead of rendering `[object Object]` (CR040 — degrade loudly).
- New `esc()` helper: broadcast titles/bodies and replies are interpolated into
  `innerHTML`; replies are **tester-typed** free text, so they are HTML-escaped —
  otherwise any tester could run script in the admin's authed context.
- Fetch errors render as red "Failed to load …" text, distinct from the empty
  state (CR040: error ≠ empty).

## Verification

`admin.html` has no committed JS harness and no backend test asserts on its
content. Verification for this CR:

- A scratchpad node `vm` harness (DOM-stubbed) drove the real `<script>` block:
  23 checks covering the preview-guard state machine, audience payload shapes
  (incl. no `platform` key ever), CR040 error-vs-empty rendering, reply-body
  escaping, and the `Z`-suffix `since` param. All green.
- Mutation-proven: four hand-broken variants (drop the send-time equality check;
  make invalidation a no-op; enable SEND on 0 recipients; drop `esc()` on reply
  bodies) each turned the relevant checks red; the restored file went green and
  was byte-identical.
- The harness is deliberately not committed — adding a JS test rig to the repo is
  a scope decision this CR doesn't make.
- `pytest backend/tests/unit/test_cr102_admin_messages.py backend/tests/unit/test_admin.py -q`
  green (nothing backend changed).
- End-to-end (real preview counts, a `mode:user` send to Saiful's own id) happens
  on Alpha after the next `/promote-to-alpha` — Saiful is the tester.

## Acceptance

- [x] MESSAGES tab renders behind the existing token gate; setup view unchanged.
- [x] Audience modes exactly as the API accepts them today (no platform).
- [x] SEND structurally impossible without a fresh preview of the identical payload.
- [x] 0-recipient previews keep SEND blocked, with the by-design explanation.
- [x] Broadcasts + replies views, error states distinct from empty states.
- [x] Reply user ids link into the existing user-detail view.
- [ ] Promoted to Alpha and exercised from a phone (Saiful, post-promotion).
