# CR121 — Client version gate: a server-driven minimum build, with a message per raise

**Filed:** 2026-07-29 (AT:R65) · **Status:** proposed — spec, not built

Saiful: *"research how I can force an update on the app on the users phone, or at least
force the user to do an update"* → then: *"Create a CR for the gate. Make it such that we
can send a message as well to the user when we ask them to update. Message will be added
for each time we move the bar."*

---

## The problem

There is no way to stop a user running an old build. Today a tester on `0.1.0+40` and a
tester on `0.1.0+57` hit the same live backend, and the backend serves both identically —
including builds whose bug we already fixed, whose API contract we already changed, or
whose LLM prompt we already corrected. The only thing that eventually removes an old iOS
build is TestFlight's 90-day expiry, which is passive, slow, and does not exist on Android.

The measured gap: **zero** hits for `min_version`, `minimum_version`, `force_update`,
`upgrade_required` or `client_version` across `backend/app/**/*.py` and
`mobile/lib/**/*.dart`. No gate exists at any layer.

## What "force" can actually mean

Nothing pushes a new binary to an iPhone without the user tapping. iOS has **no**
force-update API. So the honest ceiling for a gate is: *the app refuses to run below the
floor, and hands the user a one-tap route to the store*. That is what every bank app does
and it is the only mechanism that works on **both** platforms and on **every** channel we
use (TestFlight, Play internal/closed, App Store, Play production, cable install).

Two adjacent mechanisms exist and are **not** this CR:

- **Play In-App Updates, immediate flow** — Google's own fullscreen download-install-restart
  UI. Android-only, Play-installed-only, and `inAppUpdatePriority` is settable only via the
  Play Developer Publishing API at rollout (never the Console UI) and is unsupported on
  internal app sharing. It improves the Android tap that this CR already covers. Later.
- **Shorebird OTA code push** — genuinely silent, no user action, Dart-only (no assets, no
  native, no engine upgrade, no plugin native bindings). Free ≤5,000 patch installs, $20/mo
  for 50,000. Complementary, not a substitute — it cannot fix anything native, and it
  cannot make a user leave a build we want dead. Separate CR if we want it.

## What already exists (measured)

The client-version plumbing is **already half-built** — it just terminates in a database
column instead of a decision:

| Piece | Where | State |
|---|---|---|
| Client knows its own version | `mobile/lib/services/device_user.dart:46` — `'${p.version}+${p.buildNumber}'` → `"0.1.0+57"` | live |
| `package_info_plus` dependency | `mobile/pubspec.yaml:65` (`^9.0.1`) | live |
| Version reaches the server | `api_client.dart:980-992` → `schemas/auth.py:65` → `api/auth.py:119` | live, **bootstrap only** |
| Server stores it | `db/models.py:120` (`user_devices.last_app_version`), `:189` (`devices.app_version`), written at `auth_service.py:96-97,323-324` | live |
| Single request choke point | `api_client.dart:52-64` `_AuthInterceptor.onRequest` (adds the bearer) | live |
| Global response-code interceptor precedent | `api_client.dart:72-89` `_ServerErrorInterceptor` (DEF073, annotates 5xx) | live |
| Unauthenticated endpoint precedent | `backend/app/main.py:209` `/v1/health` | live |

**The build number is shared across platforms.** `mobile/pubspec.yaml` carries one
`version: <semver>+<build>` line; `scripts/build_testflight.sh:81-99` bumps it and
`scripts/publish_playstore.sh --no-bump` reuses the same `+N`. So the floor is **one
integer**, not a per-platform pair, and comparison is integer `>=` on the build number —
not semver parsing.

## The constraint that drives the sequencing

**A gate only binds builds that already contain it.** `0.1.0+57` and everything before it
does not ask the server for a floor, so no future config can ever block it. The installed
base at the moment this ships is permanently ungateable; every build from the gate forward
is controllable.

Consequence: this is worth doing *now*, while the tester base is small, not after Beta.
The one escape for legacy builds is that the backend can refuse `/v1/auth/device` below a
floor — but an old client has no update UI, so the user gets a generic auth failure. That
is a **brick, not a prompt**, and is reserved for a genuine emergency (see Out of scope).

---

## Design

### Data model — append-only, one row per raise

The requirement *"message will be added for each time we move the bar"* means the floor is
**not** a mutable setting. It is a log. Each raise is a new row carrying its own copy for
that raise, and the active floor is the row with the highest `min_build`.

New table `client_release_floors`:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID pk | |
| `min_build` | int, not null, unique | the floor. Client with `buildNumber < min_build` is **blocked** |
| `recommended_build` | int, nullable | soft nag threshold. `min_build <= b < recommended_build` → dismissible prompt |
| `headline` | str, not null | short title on the blocking screen, e.g. "Update required" |
| `body_en` | text, not null | Saiful's message for **this** raise — why they must update |
| `body_ar`, `body_ms` | text, nullable | EN fallback when null (see i18n) |
| `created_at` | tz-aware datetime | |
| `created_by` | str, nullable | operator note |
| `active` | bool, default true | lets a bad raise be retracted without deleting the history |

Append-only means the answer to *"what did we tell users when we killed +57?"* is a row,
not a memory. It also makes rollback a one-liner: flip `active=false` on the top row and
the previous floor governs again.

Alembic migration follows the existing `backend/alembic/versions/<hash>_<slug>.py` pattern.

### Backend

**1. Read endpoint — `GET /v1/client/release-floor`**

Unauthenticated (sibling of `/v1/health`, `main.py:209`) — it must answer *before* the app
has a session, because the block has to fire on a client too old to authenticate. Takes
`?build=<int>&locale=<en|ar|ms>` and returns:

```json
{
  "min_build": 58,
  "recommended_build": 61,
  "action": "block" | "nag" | "ok",
  "headline": "Update required",
  "body": "…the message authored for this raise…",
  "store_url": "https://…"
}
```

The server decides `action`, not the client — so the policy can change without a client
release. `body` is already locale-resolved server-side; the client renders a string, it
does not pick a language.

**2. Enforcement — `426 Upgrade Required`**

`X-App-Version: 0.1.0+57` added to every request (see Mobile), and a FastAPI dependency /
middleware rejects below-floor requests with `426` and the same JSON body. Client-side
checking alone is bypassable by a patched binary; at alpha this is belt-and-braces, but it
is cheap because the header is already there and it makes the gate real rather than polite.

Requests **exempt** from 426: `/v1/health`, `/v1/client/release-floor` itself, and the
feedback POST (a user on a blocked build must still be able to report that they are stuck).

**3. Write side — admin**

`POST /v1/admin/release-floor` behind the existing `ADMIN_SECRET` bearer
(`api/admin.py:54-63`, `Depends(get_admin)`), plus a row in `app/static/admin.html`'s SPA.
Body = the new floor + the message. A raise is one API call, no deploy, no container
recreate — which is the whole point of a DB table over an env var.

`scripts/release_floor.sh` mirrors the `users.sh` SSH + `docker exec psql` transport for
the CLI path.

### Mobile

**1. Send the header.** `X-App-Version` in `_AuthInterceptor.onRequest`
(`api_client.dart:52-64`) — one line, next to the bearer. Version comes from the existing
`DeviceContext.appVersion` (`device_user.dart:46`), so nothing new is computed.

**2. Catch the 426.** A `_VersionGateInterceptor` beside `_ServerErrorInterceptor`
(`api_client.dart:72-89`) — same shape as DEF073's, raises a typed
`UpgradeRequiredException` carrying the server's headline/body/store_url.

**3. Check on launch and on resume.** Call `GET /v1/client/release-floor` at startup and on
app-foreground (a session left open for days must not outlive a raise).

**4. The screen.** Non-dismissible full-screen route on `action: "block"` — headline, the
authored body, one primary CTA to the store, no back gesture, no system-back. On
`action: "nag"` — the same content in a dismissible sheet, shown at most once per app
session.

**5. Store URL.** Served by the backend, not hardcoded, because the two platforms differ
and one of them does not exist yet:

- Android: `https://play.google.com/store/apps/details?id=ai.agenticmarketintel.ami_trade`
  (`mobile/android/app/build.gradle.kts:38`).
- iOS: `https://apps.apple.com/app/id<APP_STORE_ID>` — **we do not have a numeric App Store
  ID**; nothing in the repo carries one. Until the App Store record exists, iOS falls back
  to the TestFlight join link. The gate still blocks correctly without it; only the jump
  target degrades. (Same provisioning dependency as DEF100 / CR084.)

Note the bundle identifiers are **not** the same string on both platforms —
`ai.agenticmarketintel.amiTrade` on iOS (`Runner.xcodeproj/project.pbxproj:504`) vs
`ai.agenticmarketintel.ami_trade` on Android. Anything deriving a store URL from a bundle
ID must not assume one value.

### i18n

The per-raise message is **operational copy authored at raise time**, not shipped content —
it cannot go through the normal ARB + external-translation cycle, because the whole value
of the mechanism is that Saiful can raise the bar in a minute.

Resolution: `body_ar` / `body_ms` are nullable and fall back to `body_en`. The admin form
shows all three fields with AR/MS optional. The *chrome* around the message (the CTA label,
the "Update required" default headline, the offline-retry text) **is** shipped copy and
gets proper `app_en.arb` / `app_ar.arb` / `app_ms.arb` keys like everything else —
`retranslate:[ar,ms]` on those keys only.

Flagging per the standing rule: this CR adds ~5 new ARB keys needing AR/MS.

### Fail-open, loudly

If `/v1/client/release-floor` is unreachable or malformed, the client **allows** the app to
run and logs it. This is a deliberate, documented exception to CLAUDE.md's *degrade loudly*
rule: a fail-closed gate turns any melehost outage into a simultaneous brick of every
installed client, which is a strictly worse failure than briefly serving a stale build. The
"loud" half is preserved — the failure is logged and surfaced in the admin config check
(`api/admin.py:209-219` pattern), never silently swallowed.

### The operational footgun

The floor blocks the app; it cannot install anything. **Never raise `min_build` above a
build that is actually downloadable on every channel simultaneously** — TestFlight *and*
Play *and* (later) the App Store. Raise it above what TestFlight has approved and every iOS
tester is bricked with nowhere to go.

Mitigation: the admin write path refuses a `min_build` greater than the highest build the
server has ever *seen* in `user_devices.last_app_version` (`models.py:120`) unless passed
an explicit `--force`. Cheap, and it uses data we already collect.

---

## Acceptance

1. A client at `build < min_build` is blocked on launch, sees the headline + the body
   authored for **that specific raise**, and cannot dismiss or navigate past the screen.
2. A client at `min_build <= build < recommended_build` sees a dismissible prompt with the
   same copy, at most once per session.
3. A client at `build >= recommended_build` sees nothing and makes no extra blocking call
   on the startup path.
4. Raising the floor takes effect on the next launch **and** the next foreground of an
   already-open session, with no client release and no container recreate.
5. Two successive raises each carry their own message; the older row is still readable in
   the table (append-only proved by test, not by convention).
6. `active=false` on the top row restores the previous floor and its previous message.
7. A below-floor request to a non-exempt route returns `426` with the same payload;
   `/v1/health`, `/v1/client/release-floor` and the feedback POST still answer.
8. With the endpoint unreachable, the app runs normally and logs the failure — no brick.
9. The admin write path refuses a floor above the highest observed installed build without
   an explicit force flag.
10. New ARB keys exist in `app_en.arb` and are listed for AR/MS translation.
11. `docker-compose.yml`'s `api-alpha` block forwards any new env var —
    `test_config_compose_parity.py` is the guard (CLAUDE.md, DEF038/DEF063).

## Out of scope

- **Play In-App Updates immediate flow** — Android-only polish on a tap this CR already
  handles. Separate CR when Play production exists.
- **Shorebird / OTA code push** — different mechanism, different tradeoffs, own CR.
- **Blocking the legacy installed base** (`<= 0.1.0+57`) by refusing `/v1/auth/device`.
  Technically available, produces an unexplained failure rather than a prompt. Documented
  here as an emergency lever; not built.
- **Push notification to prompt an update** — depends on CR027/CR095 push, not on this.
- **Per-user or per-cohort floors.** One global floor. Staged rollout is a Play/TestFlight
  concern, not ours.

## Build sequencing

Small and self-contained; no dependency on any in-flight lane. Natural split:

1. **Backend** — migration, table, read endpoint, 426 dependency, admin write + guard.
2. **Mobile** — header, interceptor, launch/resume check, blocking + nag screens, ARB keys.

The value only starts accruing from the first build that contains part 2, so both halves
should ship in the same build. Worth landing before the next TestFlight round so that
`0.1.0+58` is the first gateable build.
