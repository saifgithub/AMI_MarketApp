# AMI Trade — session history

**Don't read this unless you need historical context.** Current state lives in [HANDOVER.md](HANDOVER.md).

This file accumulates the per-session "what just landed" narratives that
were once at the bottom of HANDOVER.md. Each session's `/handover`
protocol rotates the previous wrap into this file (newest on top) so
HANDOVER.md stays bounded to one session's narrative + current truth.

Sessions are AT:R\<N\> (Alpha Testing Round, after AT:R11 went live).
Earlier waves used W\<N\> (Week-N — pre-Alpha shakedown) and direct
phase IDs (A1, A2, A11, …) from `docs/10_delivery/project_plan.md`.

---

## AT:R37  (2026-05-23)

**Carry-over cleanup session — seven discrete items, no marquee feature.** Saiful opened with "lets work on all the non-gated items" from the AT:R36 carry-over list. Worked through them smallest-to-largest. **+7 work commits + 1 wrap = 8 new commits. 296 → 303 commits total. Backend tests 438 → 461 (+23). 0 Alpha promotes** — AT:R36 (`/v1/auth/google`) and AT:R37 backend changes (lockout migration `f8b5d1c00011`, rate limiter, streaming uploads) all sit on Mac awaiting `GOOGLE_AUDIENCES` configuration before promote. **Bug list still 0.** B-tier adversarial audit (all 3 findings from AT:R22) **fully closed**.

### How the session ran

Saiful opened `/start-fresh R` → AT:R37 plan-mode survey landed (22 carry-overs, 0 open bugs). He picked **sign-out UX improvement** first. After shipping that, asked "what were the other items for completion?" → I listed all 22. He asked "what's not gated?" → I filtered to 11 non-gated. He said: "lets work on all the non-gated items." We worked smallest-to-largest. Three items were deferred from execution to next session (Tier 2 translation runs blocking vLLM for 5h, BL6 design-first, Tier 3 strategy decision). Got through 7 of the 11 before hitting the 45%-context handover threshold; the remaining 4 (Credit consumption, BL7, BL8, BL16, A29) carry forward.

### Commits in order

| Hash | What it does |
|---|---|
| `9b28b5f` | **Sign-out UX.** Settings sign-out button is now async — awaits `signOut()`, then `Navigator.push(SignInScreen(showSignedOutBanner: true))`. New `SignInScreen.showSignedOutBanner` param renders a `glassChrome` strip with `settingsSignedOut` ARB key ("You've been signed out.") above the existing sign-in intro + auth buttons. The anon-on-bootstrap still happens in the background (`_AuthGate` needs *some* token), but the user no longer sees Settings silently flip to "Guest (anonymous)" without context. |
| `88f8bbc` | **Worktree sweep.** Pruned 24 stale `claude/*` worktrees under `.claude/worktrees/` + 6 dangling branches (5 `claude/bug-fix-*` + 1 `claude/sleepy-diffie-*`, all merged). Saved 2 patches locally under `.claude/worktree-salvage/` (now gitignored): `exciting-shtern-lessons-landing-spec.patch` (1 commit, lessons hex-cluster redesign spec) and `magical-edison-280-lesson-edits.diff` (280 lesson files with "training simulator" reframing). Working tree now lists only the main worktree. |
| `73b9f0d` | **BL13 mobile wiring** (backend has accepted this since AT:R32, finally connected). `DeviceUser` gains `setOnboardingSessionId` / `getOnboardingSessionId` / `clearOnboardingSessionId` (SharedPreferences key `ami.onboarding_session_id`). `OnboardingNotifier.start()` persists the `sessionId` from `StartOnboardingResponse` after `/v1/onboarding/start` succeeds. The three claim methods in `ApiClient` (`verifyMagicLink`, `signInWithApple`, `signInWithGoogle`) and their three `AuthNotifier` counterparts all gain an optional `onboardingSessionId` param, threaded into the request body. On successful claim the notifier calls `DeviceUser.clearOnboardingSessionId()` so the same session can't double-stamp. Survives app termination because it's in SharedPreferences. |
| `bdea6e8` | **Tier 2 content loaders + locale fallback.** `ai_coach_service.py` and `daily_challenge_service.py` were flat-EN-only; now they load EN from the root `*.json` plus every `<locale>/*.json` subdir. Internal storage shape: `self._by_locale: dict[str, dict[str, X]]` (locale → id → item). All public methods (`get_by_id`, `by_category`, `for_date`, `today`, `all_challenges`) gained optional `locale: str = "en"` with per-id EN fallback when a translation is missing. Existing call sites stay EN-only via the default. Search remains EN-only (pre-computed token sets) — BL4 / embedding pipeline at Beta. +8 tests covering load, locale hit, locale fallback, unknown-locale, by_category substitution, and for_date locale routing. **Unblocks the Tier 2 translation carry-over** — once `scripts/translate_content_lan.py --type ai_coach / --type daily_challenges` runs, the output lands at `content/<type>/<locale>/<file>.json` and the loader picks it up automatically. |
| `eec3117` | **B-tier audit close #1 — magic-link brute-force lockout.** Migration `f8b5d1c00011` adds `auth_challenges.attempts INTEGER NOT NULL DEFAULT 0`. `AuthService.verify_magic_link` now finds the most recent active (unconsumed + unexpired) challenge for the `target` *regardless of code_hash*; on hash mismatch it bumps `attempts` and force-consumes the row at `MAX_MAGIC_LINK_ATTEMPTS = 5`. The user can always recover by requesting a fresh code (mints a new row). Caps brute-force search at ~5e-6 per challenge against the 10^6 keyspace of the 6-digit code. +3 tests (lockout-after-N, counter-resets-with-new-challenge, correct-code-within-budget). |
| `6a2ba97` | **B-tier audit close #2 — in-memory rate limiter.** New `app/services/rate_limit.py` with an `RateLimiter` class (sliding window of deque[timestamps], `WINDOW_SECONDS=60`). Three module-level instances: `anon_rate_limit` (10/min on `/v1/auth/anon`), `magic_link_start_rate_limit` (3/min on `/v1/auth/magic_link/start`), `room_stream_rate_limit` (5/min on `/v1/room/stream`). IP resolution chain: `cf-connecting-ip` (Cloudflare authenticated) → `x-forwarded-for` first hop → `request.client.host`. 429 with `Retry-After` header on overrun, structured `rate_limit_hit` warning log. Process-local; will move to Redis when we shard. `conftest.py` autouse fixture calls `.reset()` on all three so tests don't trip the limit. +7 tests including end-to-end smoke against the real `/v1/auth/anon`. |
| `e12d998` | **B-tier audit close #3 — feedback upload streaming.** New `save_attachment_streaming(*, upload, mime, max_bytes=None)` in `bug_attachments.py`. Validates MIME up-front (no disk write on unsupported types), opens the target file once, then loops `await upload.read(64*1024)` into the file handle with a running byte counter. Mid-stream cap overrun raises `AttachmentRejected("...exceeds...")` and unlinks the partial file in the `except` branch. Empty body + disk-full paths also clean up. Refactored `/v1/feedback/bug` to use the streaming variant; old synchronous `save_attachment(content=bytes,...)` kept for existing test surface. +5 tests covering full-payload streaming, mid-stream cap abort, empty-body, unsupported-MIME-no-disk-touch, MIME→extension. |

Plus the `chore(handover): wrap AT:R37` commit.

### What changed in the codebase

Backend (services + routes):
- `backend/app/services/auth_service.py` — `verify_magic_link` refactored for the attempt-counter pattern (find-by-target → check hash → bump-or-consume); new module-level `MAX_MAGIC_LINK_ATTEMPTS = 5`.
- `backend/app/services/rate_limit.py` (NEW) — `RateLimiter` class + 3 module-level instances.
- `backend/app/services/ai_coach_service.py` — `_by_id: dict` → `_by_locale: dict[str, dict]`; loads root EN + every subdir; all public methods take optional `locale`.
- `backend/app/services/daily_challenge_service.py` — same locale refactor.
- `backend/app/services/bug_attachments.py` — new `save_attachment_streaming()` (async, chunked); `_STREAM_CHUNK_BYTES = 64*1024`.
- `backend/app/api/auth.py` — `dependencies=[Depends(anon_rate_limit)]` on `/v1/auth/anon`; `dependencies=[Depends(magic_link_start_rate_limit)]` on `/v1/auth/magic_link/start`.
- `backend/app/api/room.py` — `dependencies=[Depends(room_stream_rate_limit)]` on `/v1/room/stream`.
- `backend/app/api/feedback.py` — `/v1/feedback/bug` switched to `save_attachment_streaming(upload=file, mime=mime)`.

Backend (schema + migration):
- `backend/app/db/models.py` — `AuthChallengeRow.attempts: Mapped[int]` column added.
- `backend/alembic/versions/f8b5d1c00011_auth_challenges_attempts.py` (NEW).

Backend (tests):
- `backend/tests/unit/test_ai_coach_service.py` — +4 locale tests (subdir load, fallback to EN, unknown-locale fallback, by_category substitution).
- `backend/tests/unit/test_daily_challenge_service.py` — +4 locale tests (subdir load, fallback, for_date locale routing, for_date EN fallback).
- `backend/tests/unit/test_auth_service.py` — +3 lockout tests.
- `backend/tests/unit/test_rate_limit.py` (NEW) — 7 tests.
- `backend/tests/unit/test_bug_attachments.py` — +5 streaming tests; reuses `_FakeUpload` helper to mimic UploadFile.read(size) without TestClient.
- `backend/tests/conftest.py` — autouse fixture also resets the 3 module-level RateLimiter singletons.

Mobile:
- `mobile/lib/screens/auth/sign_in_screen.dart` — `SignInScreen.showSignedOutBanner: bool = false` param + banner widget.
- `mobile/lib/screens/settings/settings_screen.dart` — sign-out button awaits, then pushes `SignInScreen(showSignedOutBanner: true)`.
- `mobile/lib/services/device_user.dart` — `_kOnboardingSessionIdKey` + 3 helpers.
- `mobile/lib/services/api/api_client.dart` — all 3 claim methods accept `onboardingSessionId`.
- `mobile/lib/state/auth_providers.dart` — 3 claim notifier methods read + pass + clear the session id.
- `mobile/lib/state/onboarding_providers.dart` — `OnboardingNotifier.start()` persists `resp.sessionId` to DeviceUser.
- `mobile/lib/l10n/app_en.arb` + regenerated `app_localizations_{en,ar,ms}.dart` — `settingsSignedOut` key.

Repo hygiene:
- 24 dirs deleted under `.claude/worktrees/` + 6 branches.
- `.gitignore` — added `.claude/worktree-salvage/`.

### Carry-overs for AT:R38

Top-priority (gated on Saiful's external Android setup — **unchanged from AT:R36 wrap**):

1. **Saiful Android setup** (parallelizable, days of real-world lead time):
   - Register Play Console account ($25, individual)
   - `keytool -genkey -v -keystore ~/.android-keys/ami-trade-upload.keystore -alias upload -keyalg RSA -keysize 2048 -validity 10000` → backup to 1Password → extract SHA-1
   - GCP Console: enable Google Sign-In API, create Android client (package + SHA-1), create Web client → put Web client_id into `infra/alpha.env` as `GOOGLE_AUDIENCES` + pass to build script as `GOOGLE_OAUTH_WEB_CLIENT_ID`
   - Produce 3 icon source PNGs (see prompt in `~/.claude/plans/giggly-knitting-harbor.md`), drop at `mobile/assets/icon/`, run `flutter pub run flutter_launcher_icons`
2. **Promote backend.** Mac has TWO sessions of unshipped backend now: AT:R36 (`/v1/auth/google` + `GoogleOIDCVerifier`) AND AT:R37 (magic-link lockout migration `f8b5d1c00011`, rate limiter, streaming uploads). Once `GOOGLE_AUDIENCES` is filled in `infra/alpha.env`, `/promote-to-alpha` ships both in one go. Smoke-check: 400 on malformed Google token + 429 on `/v1/auth/anon` after 11 calls + magic-link lockout after 5 wrong codes.
3. **First Play Console AAB upload.** After keystore + GCP + Play Console account are live: `scripts/build_playstore.sh` produces signed AAB → upload via Play Console web UI (mandatory-manual for Play App Signing enrollment) → fill Data Safety form + Content Rating questionnaire + screenshots → add internal testers → roll out.
4. **Samsung A17 device validation** (~1 week out): install internal-track build, smoke-test golden path (Concierge → Google Sign-In → claim → 1-on-1 / Brief / Floor → Sentry crash → RTL Arabic spot-check → bug report).

Non-gated work that didn't fit this session (from the "do them all" run):

5. **Credit consumption emission.** `credits_consumed` event type already exists in `subscription_events`; nothing emits it. Wire Room + 1-on-1 to emit on completion (probably after the access-level design lands per the back-office "Deferred" note).
6. **BL7 — Agent metadata routes.** API for client-side rendering of agent profiles.
7. **BL8 — Room run cancel + replay.** Backend: cancel an in-flight room run, replay a completed one.
8. **BL16 — Real account merge UX.** Flutter. Connects to today's sign-out work (#8 from AT:R36 — now closed); when sign-back-in adopts an existing email-row, surface the merge.
9. **A29 light-mode refactor.** Settings → APPEARANCE is dark-only; the canonical theme already has a `light_*.dart` token sibling but the surfaces aren't switched.

Carrying from AT:R35 (still gated on a decision):

10. **Re-run Tier 2 sequentially.** `scripts/translate_content_lan.py --type glossary` (~50 min), then `--type ai_coach`, then `--type daily_challenges`. ~5h vLLM-blocking. Loaders are now ready (AT:R37, `bdea6e8`) — landing the content is a single-script run, but it monopolises the GPU.
11. **Re-think Tier 3 (lessons) approach.** Sequential = ~28h GPU. Options: (a) per-lesson concurrency, (b) bigger batches across lessons, (c) accept 28h over multiple sessions, (d) defer to v1.0. Saiful's call.

Carrying from AT:R34 / earlier (unchanged):

12. TF `+27` cold-launch loading loop on iPhone 17 — watch item.
13. External TestFlight launch (needs Beta App Description from Saiful + ~24h Apple review).
14. **BL6** — Mandate resolve flow (Liquidate/Postpone/Override). Needs a design pass first.
15. **BL11** — push (FCM/APNs) + in-app trial-end UX. Push gated on FCM/APNs config; in-app part doable solo.
16. **BL4** — Arabic → Gemini routing.
17. **Animation production** — 15 `<Animation>` MDX tags.

(Drops from AT:R36 carry-over list this session: **#8 sign-out UX**, **#11 B-tier audit findings** (all 3 closed), **#20 claude/* worktree sweep**, **#22 OnboardingSession.claimed_user_id Flutter wiring**, **#7 backend loader changes for Tier 2**. AT:R36 list went from 22 items to 16 active carry-overs.)

### Watch items (not tasks)

- **AT:R36 + AT:R37 backend changes both sit unshipped on Mac.** When `/promote-to-alpha` finally runs, it'll ship: `/v1/auth/google` route, `GoogleOIDCVerifier`, `OIDCVerifier.issuers` list refactor, **migration `f8b5d1c00011`** (auth_challenges.attempts), rate limiter dep on 3 routes, streaming uploads on `/v1/feedback/bug`. Smoke-check ALL of them, not just the Google route.
- **`/v1/auth/google` will reject every token until `GOOGLE_AUDIENCES` is populated** on melehost. That's the safe default — empty audiences fail the manual membership check inside `OIDCVerifier.verify()`.
- **Google button is disabled in the Android UI** when `--dart-define GOOGLE_OAUTH_WEB_CLIENT_ID=` is empty (the build script warns about this). Defensive fallback in the handler also surfaces "Google Sign-In not configured for this build" snackbar.
- **`flutter_launcher_icons` is configured but not yet run.** The 3 source PNGs at `mobile/assets/icon/` don't exist yet. Running the generator before the PNGs land will fail loudly.
- **3 untranslated keys on AR, 4 on MS** (was 2 / 3; added `settingsSignedOut` this session). They fall back to EN automatically. Non-blocking per CLAUDE.md i18n policy.
- **vLLM saturation pattern.** A single H100-class GPU comfortably serves 1-2 concurrent long-form generation streams; 4 streams blow per-stream latency past 300s. Sequential is the safe path.
- **Rate limiter is per-process.** When the backend scales beyond one container, the 10/3/5-per-minute caps become per-replica rather than global. Either accept (means an attacker hitting N replicas gets N× the budget) or move state to Redis. Not urgent at alpha.
- **Saved worktree patches.** `.claude/worktree-salvage/exciting-shtern-lessons-landing-spec.patch` (lessons landing redesign spec) and `.claude/worktree-salvage/magical-edison-280-lesson-edits.diff` (280 lesson files with "training simulator" reframing) are kept locally under gitignore. Inspect if anything reads stale, then delete.



## AT:R36  (2026-05-23)

**Android-GMS pulled into alpha, formalized as [D-057](docs/11_decisions/decision_log.md#d-057--android-gms-pulled-forward-from-v10-to-alpha).** Saiful: "I am moving the android support to alpha. I had read that the more I move forward without doing the android support, the harder it becomes." Every iOS-only assumption that creeps in compounds the eventual Android tax; closing that gap now is cheaper than retrofitting later. Closes backlog **A6b** (Google Sign-In on Android). **+1 work commit + 1 wrap = 2 new commits. 294 → 296 commits total. Backend tests 424 → 438 (+14 in `test_auth_google.py`). 0 Alpha promotes** (backend changes ship next session once Saiful provides the GCP OAuth Web client_id for `GOOGLE_AUDIENCES`). **Bug list still 0.**

### How the session ran

Saiful opened with `/start-fresh R` → AT:R36 plan-mode survey landed (15 carry-overs from AT:R35, 0 open bugs). Within the first minute he pivoted away from the carry-over menu: "I want to add the Android platform to the app." Then `/grill-me` — 9 rounds of one-question-at-a-time grilling on every Android decision branch (scope, distribution, auth, test device, toolchain, Play Console identity, keystore, SDK floor, build pipeline, deferrals). Plan file built incrementally at `~/.claude/plans/giggly-knitting-harbor.md`. Saiful approved + asked for doc updates → all 10 design docs amended, new decision **D-057** entered in the log. Then executed all code work in one pass.

**Architectural decisions locked in D-057** (every one was a deliberate pick after grilling, not a default):
- **Scope**: Android joins alpha, not v1.0 (was the previous target).
- **Distribution**: Google Play Console **internal testing track** (TestFlight equivalent — signed AAB, up to 100 testers, no review queue).
- **Auth**: Google Sign-In on Android (closes A6b). Apple stays iOS-only. Email magic-link cross-platform. Backend `/v1/auth/google` mirrors `/v1/auth/apple` end-to-end including account-linking-Phase-1 email-lookup-first.
- **Play Console account**: Individual registration ($25). The new-developer 14-day / 12-tester graduation gate only triggers on **production promotion** — internal track is unaffected, so this works for alpha. Future org migration possible once a D-U-N-S is acquired.
- **GCP**: existing GCP project reused. Two OAuth 2.0 clients required (a wrinkle that catches people): an **Android client** (package + SHA-1 binding for the device-side `google_sign_in` plugin) AND a separate **Web client** whose Client ID becomes the `aud` claim Google stamps into ID tokens returned to the Android client. Backend `GOOGLE_AUDIENCES` env = Web client ID.
- **Keystore**: Play App Signing (Google holds the signing key; we hold the upload key — upload key can be reset via Play Console if lost). Upload keystore at `~/.android-keys/ami-trade-upload.keystore`, **outside the repo** (so no `.gitignore` mishap can leak it; reusable for future projects). 1Password Secure Note attachment for both the file and the password. Acceptable single-source backup because Google can reset the upload key.
- **minSdk 28, targetSdk 35**: minSdk picked above the Flutter default (21) and the common floor (26) on the principle that test surface is one device (Samsung Galaxy A17, Android 14 / API 34) — anything below the test floor is a promise we can't verify, so narrower is safer. targetSdk 35 is mandated by Play policy for new apps. Saiful pushed back on the initial recommendation of 26 → I conceded 28 was actually cleaner.
- **Test device**: Samsung Galaxy A17 8GB, ordered, arrives ~1 week out.
- **Build script**: Manual upload via Play Console web UI for first ~5 builds (mandatory-manual on the very first AAB anyway, for Play App Signing enrollment). Move to `fastlane supply` when manual friction bites. Shared monotonic `+N` build number across iOS + Android in `pubspec.yaml`.
- **Privacy policy**: existing one reused (already at agenticmarketintel.ai).
- **Icons**: `flutter_launcher_icons` dev dep generates all density buckets + adaptive icon resources from three source PNGs (foreground, background, hi-res). Asset-generation prompt for the design tool lives in the plan file at `~/.claude/plans/giggly-knitting-harbor.md`.
- **Deferred (don't fork the platforms)**: Push notifications (FCM) — lands cross-platform with BL11. Payments (RevenueCat) — wired cross-platform later. Google Sign-In on iOS — iOS stays Apple-only.

**Existing scaffold paid off**. The Flutter project already had `android/` with namespace + applicationId correctly set, KTS Gradle, Java/Kotlin 17. Three Dart files already branched on `Platform.isAndroid` (`device_user.dart`, `feedback_providers.dart`, `api_client.dart`). The OIDCVerifier had a `build_google_verifier()` factory stubbed in AT:R29 for exactly this moment. `google_sign_in: ^6.2.2` was already in pubspec (declared but unused). `users.google_id` column already existed in the initial schema — so no migration needed (the plan's "add migration" step turned into a no-op once I checked the schema).

**One verifier refactor along the way**. `OIDCVerifier` took a single `issuer: str` field, which worked for Apple. Google issues tokens with `iss` as **either** `https://accounts.google.com` OR `accounts.google.com` (both valid per Google's OIDC docs). Refactored to `issuers: list[str]` with manual membership check (python-jose's built-in `iss` check only accepts a single string). Apple verifier updated to pass a 1-element list. One existing test file (`test_oidc_verifier.py`) needed two `issuer=` → `issuers=[...]` edits.

### Commits in order

| Hash | What it does |
|---|---|
| `5b94681` | **Android-GMS alpha foundation.** Backend: `/v1/auth/google` route mirroring `/v1/auth/apple` (email-lookup-first account-linking, trial activation, BL2 device re-keying); `GoogleOIDCVerifier` with both-issuers + email_verified guard; `OIDCVerifier.issuers` list refactor; `GoogleSignInRequest` schema; `AuthUser.google_id`; `http_audit` scrubs the route; 14 new tests. Android build: signing config + `minSdk 28` / `targetSdk 35` in `build.gradle.kts`. Flutter: sign_in_screen branches on `Platform.isIOS / isAndroid`, `_GoogleButton`, `_signInWithGoogle` handler, `api_client.signInWithGoogle`, `authNotifier.signInWithGoogle`. `scripts/build_playstore.sh` (sibling of `build_testflight.sh`). `flutter_launcher_icons` dev dep + config. l10n: `signInWithGoogle`, `signInGoogleFailed` in en.arb. 10 docs updated incl. D-057 entry, D-006 amended, `platform_facade.md` banner rewritten. `infra/alpha.env.example` gains `GOOGLE_AUDIENCES` + `APPLE_AUDIENCES` example slots. |

Plus the `chore(handover): wrap AT:R36` commit.

### What changed in the codebase

Backend:
- `backend/app/services/oidc_verifier.py` — `issuer: str` → `issuers: list[str]`; `build_google_verifier()` no longer a stub, accepts both Google `iss` values.
- `backend/app/services/auth_service.py` — constructor accepts `google_verifier`; new `sign_in_with_google()` method (mirrors `sign_in_with_apple` + `email_verified=false` guard + minimum-data policy).
- `backend/app/api/auth.py` — new `POST /v1/auth/google` endpoint; `whoami` returns `google_id` + `display_name`.
- `backend/app/schemas/auth.py` — `GoogleSignInRequest`; `AuthUser.google_id`.
- `backend/app/middleware/http_audit.py` — SCRUB_PATHS includes `/v1/auth/google`.
- `backend/tests/unit/test_auth_google.py` (NEW) — 14 tests covering happy path, email_verified guard, don't-overwrite, trial activation, account-linking.
- `backend/tests/unit/test_oidc_verifier.py` — 2 `issuer=` → `issuers=[...]` updates.

Mobile:
- `mobile/android/app/build.gradle.kts` — signing config from `~/.android-keys/keystore.properties` (debug fallback); minSdk 28; targetSdk 35.
- `mobile/lib/screens/auth/sign_in_screen.dart` — `Platform.isIOS / isAndroid` branch, `_GoogleButton`, `_signInWithGoogle` handler, Dart-define `GOOGLE_OAUTH_WEB_CLIENT_ID`.
- `mobile/lib/services/api/api_client.dart` — `signInWithGoogle({idToken, userId})`.
- `mobile/lib/state/auth_providers.dart` — `AuthNotifier.signInWithGoogle()`.
- `mobile/pubspec.yaml` — `flutter_launcher_icons: ^0.14.1` dev dep + config block pointing to `assets/icon/`.
- `mobile/lib/l10n/app_en.arb` + regenerated localizations — `signInWithGoogle`, `signInGoogleFailed`.

Infra + scripts:
- `infra/alpha.env.example` — added `APPLE_AUDIENCES` (commented, optional) + `GOOGLE_AUDIENCES` (empty until GCP Web client_id is provisioned).
- `scripts/build_playstore.sh` (NEW, executable) — bumps pubspec `+N`, `flutter build appbundle --release` with Dart defines, surfaces AAB path + manual-upload reminder.

Docs (10 files):
- `CLAUDE.md` (platforms row), `docs/11_decisions/decision_log.md` (new D-057, D-006 amended), `docs/08_tech/platform_facade.md` (status banner rewritten — alpha-GMS ships via direct integration, facade is now HMS-only future work), `docs/08_tech/auth.md` (Google Sign-In section parallel to Apple, dual OAuth client gotcha documented), `docs/08_tech/auth_audit.md` (L-6 severity tied to D-057), `docs/08_tech/stack.md` (tree comments updated), `docs/10_delivery/project_plan.md` (A6b status partial; D-057 reference), `docs/10_delivery/stealth_alpha_scope.md` (preamble + Tier 1 table + defer table), `docs/10_delivery/you_do_i_do.md` (Saiful's full Android setup checklist), `docs/01_product/core_loop_and_features.md` (Android platform status row).

---

## AT:R35  (2026-05-22)

**i18n Tier 1 done; Tiers 2 & 3 prepped but not yet run.** Translation infrastructure now ships LAN-direct to vLLM on `192.168.20.74:8000` via the OpenAI-compatible chat-completions API. Also diagnosed the "same Apple ID, different progress on each phone" question (it's a sign-out side-effect, not a sync bug). **1 work commit + 1 wrap = 2 new commits. 293 → 294 commits total. No backend changes; no Alpha promotes; tests still 424; bug list still 0.**

### How the session ran

Saiful opened with `/start-fresh R` (session name `AT:R35`). Plan-mode survey landed with the 15 deferred carry-overs from AT:R34 — no open bugs.

**First topic — the multi-phone observation.** Saiful: "I have the same Apple ID on two phones but different progress." Pulled the DB and found three relevant accounts: the Apple account `8f1e288a` (Siti Ahmad, 5 journal entries from earlier testing), a magic-link account `b747faf3` (saiful@atmmarketintel.com, from 3am today), and a fresh anon `0e0a9860` (iPhone 13 mini's current identity). Both phones HAVE been linked to `8f1e288a` in `user_devices` via earlier Apple Sign-In — but `signOut()` calls `DeviceUser.clear()` which wipes the persisted `(user_id, token)` pair, and the next `bootstrap()` mints a fresh anon user. After signing out, neither phone is on `8f1e288a` anymore — they're on different orphan anon accounts. Filed as: post-sign-out UX should prompt "sign back in to continue progress" rather than silently starting fresh. This is adjacent to BL16 (account merge) but cheaper to ship.

**Second topic — i18n prep.** Mapped the translation surface:
- Tier 1: 312 EN ARB keys, 10 missing in AR/MS + 65 AR / 79 MS identical-to-EN (tour walkthrough strings shipped post last translation run).
- Tier 2: 188 glossary terms, 280 AI coach Q&A, 183 daily challenges — all EN only.
- Tier 3: 270 lessons × ~283K words — all EN only.
- Agent prompts stay EN by design (LLM responds in `mandate.locale` at runtime).

**Tier 1 ran successfully.** First attempt went through `scripts/translate_arb.py` which defaults to the public CF Tunnel route (designed for worktree-sandbox portability). Cloudflare's ~100s proxy timeout chewed up the 40-key batches at 90+s each, returning 502 Bad Gateway. Saiful: "This is a crazy route". Wrote a sister script `scripts/translate_arb_lan.py` that hits vLLM's OpenAI-compatible `/v1/chat/completions` directly on the LAN. Ran in 7 minutes for 74 AR + 80 MS keys, zero timeouts. Final state: 311/311 AR keys filled, 310/311 MS keys filled (one MS placeholder dropped by Gemma → falls back to EN).

**Tier 2 + Tier 3 hit a saturation wall.** Wrote two more LAN-direct scripts (`translate_content_lan.py` for JSON-based content, `translate_lessons_lan.py` for MDX with Quiz/Term/ChatWith/Animation component parsing). Kicked all three in parallel (glossary, ai_coach, daily_challenges) plus a 2-lesson smoke test. vLLM saturated: every batch in every job timed out at 300s. The smoke-test lessons produced English-with-corrupted-frontmatter output. Saiful asked to pause; all jobs killed; partial outputs deleted; vLLM verified healthy (3s for small request after the kill drain). The lesson: vLLM continuous batching helps but doesn't scale a single H100-class GPU to 4 large concurrent generation streams without per-stream latency blowing past the 300s timeout.

### Commits in order

| Hash | What it does |
|---|---|
| `17b482c` | **i18n Tier 1: LAN-direct vLLM translation pipeline + AR/MS ARB.** Three new scripts under `scripts/translate_*_lan.py` — sister to the existing `translate_arb.py` (which is kept for worktree-sandbox portability). The LAN scripts call `http://192.168.20.74:8000/v1/chat/completions` directly with `model=ami-llm`. Tier 1 ARB outputs: `mobile/lib/l10n/app_ar.arb` 311/311, `app_ms.arb` 310/311. Also: ignore `.deliveryos/` (host-side sqlite tool memory). |

Plus the `chore(handover): wrap AT:R35` commit.

### What changed in the codebase

- `scripts/translate_arb_lan.py` (NEW) — Flutter ARB strings translator, OpenAI-compatible client.
- `scripts/translate_content_lan.py` (NEW) — glossary + ai_coach + daily_challenges translator, config-driven per content type. NOT YET RUN against the real corpora.
- `scripts/translate_lessons_lan.py` (NEW) — MDX lesson translator: frontmatter-aware, swaps MDX components for sentinels before translating prose, translates Quiz string attrs as structured JSON, reassembles. NOT YET RUN.
- `mobile/lib/l10n/app_ar.arb` — 311 keys filled (was 238 after stripping 64 identical-to-EN).
- `mobile/lib/l10n/app_ms.arb` — 310 keys filled (was 224 after stripping 78 identical-to-EN).
- `.gitignore` — `.deliveryos/` added.

### Watch items (not tasks)

- **vLLM saturation pattern.** A single H100-class GPU can comfortably serve 1-2 concurrent generation streams of long-form translation (1K+ output tokens), but 4 streams blow per-stream latency past the 300s client timeout. If parallelism is needed, raise the script's `DEFAULT_TIMEOUT_S` AND cap concurrency at 2. Better: run sequentially.
- **`scripts/translate_arb.py` (production path) still uses CF Tunnel.** Kept intentionally for worktree-sandbox portability. The LAN sister script is the right path when running from the Mac directly.
- **One MS string falls back to EN** (`tourJournal2Body`) because Gemma dropped a placeholder. To fix: `backend/.venv/bin/python scripts/translate_arb_lan.py --overwrite --locales ms` — but it would re-translate the other 310 keys too. Better: a one-key flag, not in scope this session.

---

## AT:R34  (2026-05-22)

**`eeeb866f` close.** The last open bug at session start was the deferred-pre-beta resilience item: "Room run survives api-alpha container restart." Closed end-to-end, verified live. **2 work commits + 1 wrap = 3 new commits. 424 tests passing (was 422 — +2 retry tests; existing sweep test refactored). 2 Alpha promotes (`-8`, `-9`). Bug list now empty.**

### How the session ran

Saiful opened with `/start-fresh R` (session name `AT:R34`). Plan-mode survey landed with the standard carry-over list — 1 open bug + 15 deferred items. He first asked how to test BL1+BL2 from the prior session's TestFlight `+27`; we walked through it via direct DB inspection (no need for admin UI / no token forging): both phones (`iPhone18,1` iPhone 17, `iPhone14,4` iPhone 13 mini) signed in with same Apple ID land 2 device rows under `8f1e288a` ✅. Flagged a brief loading-loop on iPhone 17 first launch of `+27` (recovered, no backend errors). Briefly considered Option-B synthetic test for BL11 effective_plan — auto-mode classifier denied bearer-forging (correctly: forging an HMAC for a real user is auth bypass on the wire). Saiful chose "don't weaken security" and moved on to `eeeb866f`.

Designed the fix as simplified Tier 1 — reuse the existing `asyncio.create_task` pattern instead of the bug's filed scope of Celery+Redis (3-4 days). Insight: the runner already checkpoints transcript after each agent, and the startup sweep already runs on boot. The missing piece was making the sweep **claim+respawn** instead of mark-fail. Shipped as commit `8510436` with a new `retry_count` column (migration `e7a4c5b00010`) capping auto-retries at 1. Promoted as `alpha-2026-05-22-8`.

First live test surfaced a real follow-up bug: the retry path called `get_mandate_store().get_version(user_id, mandate_version)` to rehydrate the mandate, but default-hydrated mandates (typical for users who never touched Brief Your Agent) aren't persisted to the `mandates` table — they're produced inline by `hydrate_brief_mandate`. So every default-mandate retry would have died with "auto_retry_failed: mandate version no longer exists" instead of actually retrying. Fixed in commit `3f4022a` with a `resolve_mandate` fallback (current stored OR default-hydrated). Promoted as `alpha-2026-05-22-9`.

End-to-end live verification: seeded a synthetic stuck row (`aaaaaaaa-...`) with `started_at = now - 2h`, restarted api-alpha, watched logs fire `room_startup_sweep queued_for_retry=1` → `room_startup_retry_mandate_fallback` (the second-fix branch firing as designed for a user with no stored mandate) → `room_startup_retry_respawned` → all 12 agents speak (~6 min) → `room_completed action=APPROVE` → `room_startup_retry_journal_written`. Row landed at `status=completed, retry_count=1`, journal entry created. Cleanup deleted the synthetic row + journal entry, then UPDATE on `bug_reports` flipped the status to `closed` with `assigned_branch='AT:R34 commit 3f4022a'`.

Network blipped mid-session: Mac↔melehost LAN dropped briefly between the two promotes. Public hostname stayed up via the Cloudflare Tunnel (outbound connection from melehost holds even when LAN routing fails); rsync resumed cleanly when LAN came back. Not a project bug — flagged for the next session as a watch item.

### Commits in order

| Hash | What it does |
|---|---|
| `8510436` | **eeeb866f — startup auto-retry for runs killed by container restart.** Migration `e7a4c5b00010` adds `room_runs.retry_count INTEGER NOT NULL DEFAULT 0`. Constant `MAX_AUTO_RETRIES = 1` in `room_runner.py`. Rewrote `_sweep_stuck_runs` to claim stuck `running` rows (bump retry_count, clear transcript+verdict, refresh started_at, queue on `self._pending_retry`) instead of marking them failed. Added `async def resume_pending_retries()` to drain the claim list and spawn retry tasks now that the event loop is live. Added `_respawn_run_from_row` private helper that uses the existing run_id, re-derives mandate from the version, replays the journal-write that the original request's `on_complete` would have done. Wired into FastAPI lifespan in `main.py`. Moved `_build_journal_entry` from `api/room.py` to `services/room_runner.py` as `build_journal_entry_for_run` (with back-compat re-export) so the retry path doesn't need an upward import. **+2 backend tests (sweep queues first stuck run, sweep fails after max retries); existing sweep test refactored to seed retry_count=1 since the policy now requires already-retried-once for the fail path.** |
| `3f4022a` | **Retry path falls back to `resolve_mandate` when version row missing.** Follow-up to `8510436` discovered during the first live promote: `get_version(user_id, 1)` returns None for any user who never customised their mandate (default-hydrated mandates are produced inline, never persisted). Without this fallback every such retry would mark itself failed with "mandate version no longer exists". Now falls back to `resolve_mandate(user_id, None)` which returns the current stored OR default-hydrated mandate. Logs `room_startup_retry_mandate_fallback` so we can spot drift cases later. |

Plus the `chore(handover): wrap AT:R34` commit.

### What changed in the codebase

**Backend** (`backend/app/`):
- `db/models.py` — `RoomRunRow.retry_count` column (commit `8510436`)
- `services/room_runner.py` — `MAX_AUTO_RETRIES` constant; `_PendingRetry` dataclass; `build_journal_entry_for_run` (moved from `api/room.py`); rewrote `_sweep_stuck_runs` to claim-or-fail; new `resume_pending_retries` + `_respawn_run_from_row`; journal_store / journal-schema imports added (commits `8510436`, `3f4022a`)
- `api/room.py` — imports `build_journal_entry_for_run` from `services/room_runner.py`; back-compat alias `_build_journal_entry = build_journal_entry_for_run` so existing tests still resolve (commit `8510436`)
- `main.py` — lifespan startup hook now awaits `get_room_runner().resume_pending_retries()`; logger import fixed at top (was used in `_nightly_audit_trim` without being imported — latent bug) (commit `8510436`)

**Migration** — `e7a4c5b00010_room_runs_retry_count.py` (room_runs.retry_count column).

**Tests** — 422 → 424 passing (+2 retry tests; `test_startup_sweep_marks_abandoned_run_failed` renamed/refactored to `test_startup_sweep_queues_first_stuck_run_for_retry` + `test_startup_sweep_marks_failed_after_max_retries` + new `test_resume_pending_retries_respawns_and_completes`).

**Bug DB** — `bug_reports.eeeb866f` updated: `status='closed'`, `assigned_branch='AT:R34 commit 3f4022a'`. Open bug count: 1 → 0.

### Carry-overs for AT:R35

The carry-over list shortened by one (`eeeb866f` is gone). Order shuffled to reflect what's now top-priority:

1. **TF `+27` cold-launch loading loop on iPhone 17 — watch item.** Recovered without intervention this session and didn't repro on iPhone 13 mini. If it shows up again, the next session should capture: how long until it cleared, repro rate, whether airplane-mode / Wi-Fi-only matters. Backend logs show 200s for every `auth/anon` from `+27`, so the hang is client-side (likely `device_info_plus` or `shared_preferences` first-call on iOS 26.4.2).
2. **External TestFlight launch.** Needs Beta App Description from Saiful + ~24h Apple review. `+27` is uploaded and verified across both phones. This is the alpha→beta gate.
3. **B-tier adversarial-audit findings** — rate limiting on `/auth/anon` + LLM-heavy routes; magic-link attempt counter; feedback upload streaming.
4. **BL16** — Real account merge UX (filed AT:R32, design-first).
5. **BL6** — Mandate resolve flow (Liquidate/Postpone/Override actions). Pre-req: drift detection (MVP scope). The audit half landed AT:R33 as BL12.
6. **BL11 — push + in-app trial-end UX.** Entitlement gate landed AT:R33; mobile modal + OneSignal push still pending (Beta).
7. **BL4** — Arabic → Gemini routing. Blocked on `GoogleProvider` class in llm_gateway.
8. **BL7** — Agent metadata routes. Mobile workaround sufficient until v1.0 Android port.
9. **BL8** — Room run cancel + replay. Cancel needs Postgres-side signalling (1.5 sessions, hard); replay is sugar.
10. **A6b — Google Sign-In on Android.** Blocked on Google Cloud Console setup.
11. **Animation production** — 15 `<Animation>` MDX tags still render `AmiHexPlaceholder`.
12. **A29 light-mode refactor** — v1.0 work.
13. **`claude/*` sibling worktrees on disk** — Saiful decision (keep or delete). Carries from AT:R32.
14. **Credit consumption** — `credits_consumed` event type exists but no app code emits it.
15. **`OnboardingSession.claimed_user_id` Flutter wiring** — backend accepts `onboarding_session_id` since AT:R32 BL13 but Flutter doesn't send it yet. Update when something consumes the binding.

### Watch items (not tasks)

- **Mid-run resumption stays deferred (Tier 2, 10-12 days).** AT:R34's fix retries the **whole run from scratch** — the checkpointed transcript is wiped on claim. If we ever want LangGraph-style continue-from-where-it-died, that's a separate piece of work. Tradeoff: AT:R34's retry pays for the LLM tokens twice when it fires, same cost as a user-initiated resubmit.
- **Multi-container claim race not handled.** If we ever run more than one api-alpha pod, two pods could try to retry the same stuck row simultaneously. Mitigated for now by single-container deployment. Future fix: DB-level claim with `UPDATE ... WHERE status='running' RETURNING`. Comment in `_sweep_stuck_runs` flags it.
- **Test data: 3 users with same human, still none linked.** `8f1e288a` Apple, `b747faf3` magic-link, `d9e81e45` orphan challenge. AT:R32 Phase 1 adopt-by-email logic prevents future forks but doesn't retroactively merge existing rows. Hand-merge later or accept as test artifacts.
- **Backfill seeded 24 user_devices rows** on melehost during the BL2 migration. Those rows use the existing `device_user_id` as the install_id approximation — fine for legacy users, but the new `+27` mobile generates a fresh `device_install_id` UUID on first launch rather than reuse the device_user_id one.
- **LAN connectivity to melehost was briefly flaky mid-session.** Two SSH timeouts during the AT:R34 promotes; recovered on retry. Public hostname stayed up the entire time (Cloudflare Tunnel outbound holds). Not a project bug; worth watching if it becomes a pattern.

---

## AT:R33  (2026-05-22)

**BL-closeout sprint.** Closed 7 BL items end-to-end + reconciled the last two untested doc trees. Every change shipped to Alpha; mobile-side changes (BL1 + BL2) are in TestFlight `+27` (uploaded by Saiful). **11 new commits this session. 422 tests passing (was 375 — +47). 4 Alpha promotes (`-4`, `-5`, `-6`, `-7`). 1 TestFlight build (`+27`).**

### How the session ran

Saiful opened with `/start-fresh R`. First task: docs reconciliation — two parallel Explore agents audited `tradingagent_integration.md` + `flutter_implementation.md` against actual code, surfaced ~12 stale claims and ~5 phantom widgets/dirs; rewrote both in place (commit `eaa12ce`). Then he said "build all that's ready to ship" — kicked off a tight BL closeout batch: BL9 → BL10 → BL1 → BL12 → /promote-to-alpha (`-4`). Then BL2 ("I have 2 phones") with a careful design for `device_install_id` separate from `device_user_id` → migration + re-keying on claim adoption + admin device list → `-5`. Then BL11 entitlement gate (real alpha-needle item: trials weren't actually downgrading anyone) → `-6`. Then BL5 history API (Saiful overruled the "needs UI mockup" deferral) → `-7`. Saiful pushed TF `+27` himself, then asked to wrap.

### Commits in order

| Hash | What it does |
|---|---|
| `eaa12ce` | **Docs reconciliation** — `tradingagent_integration.md` + `flutter_implementation.md`. Last two untested doc trees. Two parallel Explore agents audited each against the current code; ~12 stale claims fixed (file paths, class names like `AgentsService` → `RoomRunner`, function signatures, Honeycomb → FloorPlaceholderScreen, MatrixConsole → RoomScreen, ChatRole → ChatAuthor, go_router → MaterialApp named routes, Supabase Realtime → SSE). Added clear "alpha status: scripted RoomRunner, not TradingAgents graph yet" callout. **230 lines net + 291 deletions.** |
| `7e5aa9a` | **BL9 — sim trade preview.** `POST /v1/sim/preview` runs same compliance + cash/holdings pre-flight as `/submit` but never persists. Returns `{accepted, compliance, fill_price, notional, cash_available, held_quantity, price_source}` so the mobile trade ticket UI can render "would this trade be allowed?" + sizing context before commit. New `PreviewResult` dataclass + `SimEngine.preview()` method. **+3 sim_engine tests.** |
| `e5fbfc6` | **BL10 — daily challenge attempt.** `POST /v1/daily_challenge/{cid}/attempt` records the attempt + journals it. Returns `{correct, correct_option, explanation, related_lesson, related_agent}` so the mobile detail screen renders the result inline. Adds `EntryType.DAILY_CHALLENGE` (no DB migration — entry_type is free-form String). Best-effort journal write. **+5 route tests.** |
| `9e1ce93` | **BL1 — device + build context on /v1/auth/anon.** Mobile sends `device_model` + `os_version` + `app_version` (via `device_info_plus` + `package_info_plus`) on every bootstrap. Backend persists onto `users` (3 new nullable columns, migration `c4e8f1a90008`) and surfaces them in `/v1/admin/users/{id}` + the admin HTML. Refresh-on-rebootstrap so app upgrades are tracked. Backwards-compatible. Single-device-per-user assumption holds (multi-device split is BL2). **+4 backend tests.** |
| `efe6b79` | **BL12 — mandate audit on hard edits.** `GET /v1/mandate/{u}/audit` runs deterministic per-holding audit of current portfolio against current mandate. New `check_holdings_against_mandate()` evaluator in `safety_floor.py` (sibling to `check_mandate_compliance` — same dimensions: blocklist, halal, locale, single-name cap, plus portfolio-level drawdown breach). Returns `HoldingsAuditResult { passed, mandate_version, portfolio_value, current_drawdown_pct, drawdown_breach, violations[] }`. Pure read — no journal writes. Designed to be called by mobile right after `PATCH /mandate` so the resolve modal renders inline. **+8 tests.** |
| `2d8a0d8` | **BL2 — user_devices multi-device tracking.** New `user_devices` table keyed by `device_install_id` (mobile-generated UUID persisted once on first launch, NEVER overwritten by claim — unlike `device_user_id` which mobile overwrites with the adopted user's id on `setIdAndToken`). Migration `d5f2a3b00009` + backfill seeded 24 rows from existing `users.device_user_id`. `ensure_anonymous()` upserts the device row; `_claim_or_create` + `sign_in_with_apple` re-key the pre-claim anon's devices to the adopted user so two phones on one Apple ID surface as two device rows under one user. `AdminUserDetail.devices[]` + admin HTML list each device with model/OS/app_version/last_seen. Mobile adds `DeviceUser.getOrCreateInstallId()` + sends on bootstrap. **+5 backend tests including the full two-phones-one-Apple-ID flow.** users.device_user_id stays (still plays A2 role); drop is a follow-up. |
| `95e2337` | **BL11 — trial-end entitlement gate.** `effective_plan(plan, trial_expires_at)` pure helper with three branches: active trial → at least TRIAL_TRADER, expired trial + plan=TRIAL_TRADER → FLOOR_PASS, else unchanged. Covers both trial paths (auto-claim and admin-granted). Wired into all 7 `pick_tier()` callsites (brief_engine ×2, agent_runner ×2, room_runner ×3) so when a trial lapses the LLM routing drops to cheap-tier on the next call — no admin intervention or background job needed. Admin surface gains `effective_plan` + `trial_active` fields; admin.html renders `plan → effective_plan` (orange arrow) when they differ + ACTIVE/EXPIRED column. `users.plan` stays immutable except on explicit admin/conversion events. Skipped (Beta): in-app trial-ended modal, conversion screen, push. **+12 tests.** |
| `d3cb451` | **BL5 — mandate history API.** Three new routes (sugar over the existing versioned `mandates` table): `GET /v1/mandate/{u}/versions` (list newest-first, decorated with the matching `mandate_edit` journal entry's plain-English summary), `GET /v1/mandate/{u}/versions/{v}` (fetch a specific historical snapshot, 404 on miss), `POST /v1/mandate/{u}/rollback/{v}` (forward-only rollback: creates a new version mirroring v, writes a journal entry tagged `rollback` with `rolled_back_to_version` in payload). Store gains `list_versions` + `get_version` + `rollback_to`. **+10 route tests.** |
| `ecea7bb` | **pubspec `+26 → +27` bump** — auto-committed by `scripts/build_testflight.sh` when Saiful shipped `+27` carrying BL1 + BL2 mobile changes. |
| `19eb5d7` | **Podfile.lock — pull device_info_plus pod (BL1).** Auto-generated by pod install during the `+27` build. |

Plus the `chore(handover): wrap AT:R33` commit.

### What changed in the codebase

**Backend** (`backend/app/`):
- `services/sim_engine.py` — `PreviewResult` + `SimEngine.preview()` (commit `7e5aa9a`)
- `api/sim.py` — `POST /v1/sim/preview` route (commit `7e5aa9a`)
- `api/daily_challenge.py` — `POST /{cid}/attempt` route + response schemas (commit `e5fbfc6`)
- `schemas/journal.py` — `EntryType.DAILY_CHALLENGE` (commit `e5fbfc6`)
- `db/models.py` — `User.device_model/os_version/last_app_version` (commit `9e1ce93`); `UserDeviceRow` (commit `2d8a0d8`)
- `schemas/auth.py` — `AnonSessionRequest` gains 3 device fields (BL1) + `device_install_id` (BL2)
- `services/auth_service.py` — `ensure_anonymous` persists device context + upserts user_devices; `_claim_or_create` + `sign_in_with_apple` call `_rekey_devices_to`; new `_upsert_user_device` + `_rekey_devices_to` helpers (commits `9e1ce93`, `2d8a0d8`)
- `api/auth.py` — `/v1/auth/anon` passes new fields through (commits `9e1ce93`, `2d8a0d8`)
- `schemas/admin.py` — `AdminUserDetail` gains `device_model/os_version/last_app_version`, `devices[]`, `effective_plan`, `trial_active`; new `AdminUserDevice` (commits `9e1ce93`, `2d8a0d8`, `95e2337`)
- `api/admin.py` — `_user_detail` populates new fields; new `_load_devices` helper (same)
- `static/admin.html` — device list block + plan→effective_plan arrow + ACTIVE/EXPIRED trial column
- `agents/safety_floor.py` — `HoldingViolation` + `HoldingsAuditResult` + `check_holdings_against_mandate` (commit `efe6b79`)
- `api/mandate.py` — `/audit`, `/versions`, `/versions/{v}`, `/rollback/{v}` routes (commits `efe6b79`, `d3cb451`)
- `services/mandate_store.py` — `list_versions`, `get_version`, `rollback_to` (commit `d3cb451`)
- `services/entitlements.py` — new file: `effective_plan`, `is_trial_active`, `effective_plan_for_user` (commit `95e2337`)
- `services/brief_engine.py` + `services/agent_runner.py` + `services/room_runner.py` — all 7 `pick_tier` callsites resolve effective_plan from user_id (commit `95e2337`)

**Mobile** (`mobile/lib/`):
- `services/device_user.dart` — new `DeviceContext` class + `DeviceUser.getOrCreateInstallId()` (commits `9e1ce93`, `2d8a0d8`)
- `services/api/api_client.dart` — `bootstrapAnon` accepts new fields (BL1, BL2)
- `state/auth_providers.dart` — `bootstrap()` gathers + sends device context + install_id

**Mobile pubspec** — `device_info_plus: ^11.1.0` added; version bumped to `0.1.0+27` for TF.

**Migrations** — `c4e8f1a90008` (BL1: user device columns), `d5f2a3b00009` (BL2: user_devices table + backfill).

**Docs** (`docs/08_tech/`):
- `tradingagent_integration.md` — reconciled (commit `eaa12ce`)
- `flutter_implementation.md` — reconciled (same)

**Tests** — 375 → 422 passing.

---

## AT:R32  (2026-05-21)

**Quick-wins close-out session.** Tackled the entire AT:R31 carry-over chip list end-to-end. SMTP unblocked (Resend HTTP API), TestFlight pipeline rewritten (eliminates manual Xcode intervention), CFBundleDisplayName casing, account-linking Phase 1 (the multi-device fragmentation bug Saiful found mid-session got designed + tested + shipped), BL13/BL14/BL15/L-1 all closed. **9 AT:R32 work commits + 1 pubspec bump = 10 new commits. 375 tests passing (was 367). 3 Alpha promotes. 2 TestFlight builds shipped (`+25`, `+26`).**

### How the session ran

Saiful opened with `/start-fresh R` (this is AT:R32 = handover #32). I surfaced the carry-over list; he framed the session as "quick-wins close-out". First half: SMTP via Resend → magic-link verified end-to-end → `/promote-to-alpha` (carrying BL3 trial wiring from AT:R31 too) → CFBundleDisplayName casing. Mid-session he ran `scripts/build_testflight.sh --no-bump` to ship `+25` (uploaded successfully on the original script). Then we clicked the `build_testflight.sh` rewrite chip and shipped `+26` via the new staged pipeline. Saiful tested the magic-link flow on `+26` and noticed he'd ended up with three user rows for the same human (one Apple, two magic-link, different emails) — we designed + implemented + tested + promoted **account-linking Phase 1** (adopt-existing-identity-by-email) right there. Wrapped with a four-item batch: BL15 → BL14 → L-1 → BL13.

### Commits in order

| Hash | What it does |
|---|---|
| `232e8c5` | **SMTP swap → Resend HTTP API.** `backend/app/services/email_service.py` now prefers Resend (port 443, no ISP block) when `RESEND_API_KEY` is set; falls back to SMTP if `SMTP_HOST` is configured; falls back to no-op otherwise. `infra/alpha.env` got the API key. No new dependencies (uses `httpx` already in tree). Tests: `test_email_service.py` covers Resend success + failure paths. **Closes the External Beta SMTP blocker.** |
| `f57d1a1` | **CFBundleDisplayName casing.** `Ami Trade` → `AMI Trade` in `mobile/ios/Runner/Info.plist`. Brand convention is all-caps AMI. Visible on next TestFlight build. |
| `05ae2c3` | **pubspec `+25 → +26` bump.** Auto-committed by the rewritten `scripts/build_testflight.sh` when Saiful shipped `+26`. |
| `35a5181` | **`build_testflight.sh` rewrite + `ios/ExportOptions.plist`.** Closes the spawned-task chip from AT:R31. Splits the prior `flutter build ipa` one-shot into 4 stages: (1) `flutter build ios --release --no-codesign --dart-define=...` (framework only), (2) `xcodebuild -workspace Runner.xcworkspace -scheme Runner -configuration Release archive -allowProvisioningUpdates -authenticationKey*` (signs + auto-refreshes provisioning profile), (3) `xcodebuild -exportArchive -exportOptionsPlist ios/ExportOptions.plist` (App Store IPA), (4) `xcrun altool --upload-app`. The `-allowProvisioningUpdates` + `-authenticationKey*` flags finally land on xcodebuild where they apply — eliminates manual Xcode intervention on TestFlight uploads. Verified end-to-end via `+26` ship. |
| `1166cad` | **Account-linking Phase 1.** Resolves the 3-rows-per-human bug Saiful hit on `+26`. `_claim_or_create()` now tries email-lookup FIRST, falls back to fresh-anon user_id only when no identity match. `sign_in_with_apple()` gained an email-fallback between `apple_id` lookup and user_id fallback — magic-link-first + Apple-later (same email) attaches `apple_id` to the existing row instead of forking. Existing rows keep their original email (no mutation via re-verify). **4 new tests** in `test_auth_service.py` (369 → 373). Pre-claim anon rows orphaned by adopt are left as-is — real merge UX + conflict resolution deferred to **BL16**. |
| `e238f12` | **BL15 — delete dormant `AgentActivation` Pydantic class.** `can_use_now()` was never called, timestamp fields never written. Real activation lives in `lessons_service.py` via `AgentActivationRecord`. Dropped from `app/schemas/agents.py` + the re-export in `app/schemas/__init__.py`. Trimmed unused `UUID` import as side-effect. |
| `7b44110` | **BL14 — Mobile parses Brief `proposed_at` + `started_at`.** Added nullable `DateTime?` fields to `BriefProposal` + `BriefSession` Dart models. No UI consumer today; available for future audit-trail / replay / relative-time chip without a backend deploy. |
| `98edbd0` | **L-1 — remove `OneOnOneStartRequest.user_id`.** Audit A3 pattern, finally consistent. `/v1/agents/one_on_one/start` sources user from Bearer (`current_user.id`) exclusively; the `_own_body` check + the `req.user_id is None` mandate-defaults branch are unreachable + deleted. Flutter `startOneOnOne` no longer sends the field; `DeviceUser.getOrCreate()` call removed from `one_on_one_providers.dart`. |
| `62b7c6d` | **BL13 — bind `OnboardingSession.claimed_user_id` on claim.** Both `/v1/auth/magic_link/verify` and `/v1/auth/apple` accept optional `onboarding_session_id`; route looks up the matching session in `session_store` and stamps `claimed_user_id`. Routes converted to async (binding step awaits `session_store`). Backwards-compatible — old clients omit the field, binding silently skips. Enables cohort analysis, GDPR-clean deletion, onboarding replay. Bundles the L-1 test rewrite (same test file). **+2 tests** (373 → 375). |

Plus the `chore(handover): wrap AT:R32` commit.

### What changed in the codebase

**Backend** (`backend/app/`):
- `services/email_service.py` — new Resend HTTP path, SMTP demoted to fallback (commit `232e8c5`)
- `services/auth_service.py` — `_claim_or_create()` + `sign_in_with_apple()` reworked for identity-first lookup (commit `1166cad`)
- `schemas/agents.py` — `AgentActivation` + `ActivationMethod` removed (commit `e238f12`)
- `schemas/__init__.py` — re-export dropped
- `schemas/one_on_one.py` — `OneOnOneStartRequest.user_id` removed (commit `98edbd0`)
- `api/one_on_one.py` — `start_one_on_one` simplified (commit `98edbd0`)
- `schemas/auth.py` — `MagicLinkVerifyRequest` + `AppleSignInRequest` gained optional `onboarding_session_id` (commit `62b7c6d`)
- `api/auth.py` — `magic_link_verify` + `sign_in_with_apple` converted to async, gained `_bind_onboarding_session` helper (commit `62b7c6d`)

**Mobile** (`mobile/lib/`):
- `ios/Runner/Info.plist` — display name casing (commit `f57d1a1`)
- `ios/ExportOptions.plist` — new (commit `35a5181`)
- `models/brief.dart` — `proposedAt` + `startedAt` parsed (commit `7b44110`)
- `services/api/api_client.dart` — `startOneOnOne` drops `userId` param (commit `98edbd0`)
- `state/one_on_one_providers.dart` — drops `DeviceUser` import (commit `98edbd0`)

**Scripts/infra**:
- `scripts/build_testflight.sh` — full rewrite (commit `35a5181`)
- `infra/alpha.env` — `RESEND_API_KEY` added (commit `232e8c5`; gitignored, not in tree)

**Tests** — 367 → 375 passing.

### Backlog filed (AT:R32)

| ID | Item | Est | Status hook |
|---|---|---|---|
| **BL16** | **Account linking — real merge UX + anon-state migration.** Phase 1 (AT:R32, commit `1166cad`) adopts existing identity by email but discards the fresh-anon's pre-claim state. Once journal entries / sim trades / lessons-progress / onboarding mandate get written pre-claim, the discard becomes visible data loss. Beta-grade fix: when claim adopts an existing identity, surface a "you have two accounts, merge?" UX with conflict resolution (which mandate wins? union the lessons? newest-by-timestamp for journal entries?). Subscription-events audit row for legal/billing. | 1 session | AT:R32 deferred. Pre-req: identify which collections to merge + UX wireframes. |

### Watch items at AT:R32 wrap (now superseded)

- **3 users with same human, none linked.** Saiful's test data has 3 rows: `8f1e288a` (Apple, `saifulsaid@me.com`), `b747faf3` (magic-link, `saiful@atmmarketintel.com`), `d9e81e45` (orphan magic-link challenge, `saiful.mazli@gmail.com` — never verified). Phase 1 adopt-by-email logic is live but doesn't retroactively merge existing rows. Hand-merge later if you want one to be canonical, or just accept they're test artifacts.
- **Resend deliverability.** First production magic-link flowed cleanly to Gmail in <2s. Watch for spam-folder rate on the @atmmarketintel.com domain once volume picks up — Resend's free tier and verified-sender-domain setup may need attention before Beta.
- **TestFlight `+26` is the freshest build.** Carries CFBundleDisplayName casing + AT:R32 backend (via Alpha tag `alpha-2026-05-22-3`). If you reinstall TF before next build, you should see "AMI Trade" home-screen label.
- **`OnboardingSession.claimed_user_id` is now wireable but no Flutter client sends `onboarding_session_id` yet.** Backwards-compatible no-op until Flutter is updated. Update Flutter when something starts consuming the binding (cohort analytics dashboard, GDPR deletion path).

---

## AT:R31  (2026-05-21)

**First code-change session post-audit.** Tackled the AT:R30 carry-over chips end-to-end: BL3 trial activation wired (real backend code + tests), `build_testflight.sh` hardening attempted-then-reverted (flag-pass-through assumption broke; rewrite chip filed), `decision_log.md` + `docs/02_agents/` + `docs/03_onboarding/` reconciled against shipped code following the AT:R30 methodology, then a self-audit for similar-shape issues that filed BL11–BL15. **8 AT:R31 commits + 1 pubspec bump = 9 new commits. 367 tests passing (was 365). No Alpha promotes, no TestFlight upload (the bump landed but the build failed on the flag bug).**

### How the session ran

Saiful opened with "what's left on track R?" → picked carry-over items **3** (`build_testflight.sh` hardening — the spawned chip from AT:R29) and **6** (BL3 trial activation) for the first half. After those landed, switched to **continuing the docs-vs-code reconciliation** started in AT:R30 — this time focused on `docs/02_agents/` (high overlap with prompts + safety floor + Brief), `docs/03_onboarding/` (high overlap with onboarding engine + mandate + claim path), and `docs/11_decisions/decision_log.md` (spot-check). Methodology was the same: parallel Explore agents per tree, triage with Saiful, then commit one tree per pass. Wrapped with a separate "audit for similar-shape issues" pass that surfaced two more BL items and one dead Pydantic field worth dropping.

### Commits in order

| Hash | What it does |
|---|---|
| `4090453` | **build_testflight.sh hardening (carry-over chip).** Added `-allowProvisioningUpdates` + ASC API key auth flags assuming `flutter build ipa -- <xcodebuild args>` would pass through. It does not. **Reverted in 19a0617** (see below). |
| `e722dc5` | **BL3 — D-039 7-day trial activation on first claim.** `auth_service._claim_or_create()` (magic-link) + `sign_in_with_apple()` (Apple) now populate `users.trial_started_at = now()` + `users.trial_expires_at = now() + 7d` on first claim. Guard: `trial_started_at is None`, so admin-granted trials are preserved on re-auth. **2 new tests** (`test_claim_sets_trial_dates`, `test_reauth_does_not_reset_existing_trial`). 365→367 passing. Data plane only; downstream entitlement gate / expiry banner / conversion modal still TODO (BL11). |
| `9d403b7` | **decision_log.md spot-check.** D-022 annotated with the AT:R27 "Coach → Brief" rename; D-039 annotated with the AT:R31 data-plane wiring + remaining TODO layers; D-048 marked deferred (BL4) since `llm_gateway._pick_provider` accepts `locale` but doesn't yet route on it (blocked on GoogleProvider). |
| `a9a8d7a` | **docs/02_agents/ reconciliation + `coach_your_agent.md → brief_your_agent.md` rename.** 1 CRIT fix (Concierge tier — Floor Manager runs `mid`, not `cheap`), Coach→Brief residue swept across 7 spots in the body of the renamed file, 4 cross-refs updated (`safety_floor.md`, `README.md`, `twelve_agents.md`, `one_on_one.md`, `screen_inventory.md`). `mandate_overlays.md` file ref fixed (`overlays.py` → `overlay_generator.py`). `one_on_one.md` got an honest "actual schema" block (`one_on_one_messages` row shape) + a Not-yet-delivered tail; `twelve_agents.md` reframed activation as intended-end-state and got its own Not-yet-delivered tail (Agent Academy modules, live TradingAgents integration, `/v1/agents` route → BL7). |
| `5621c7b` | **docs/03_onboarding/ reconciliation + BL11/BL12/BL13 filed.** 5 critical doc-vs-code mismatches fixed: claim methods (only Apple + magic-link), session→user binding wrong field name (`converted_to_user` → `claimed_user_id`; and never assigned today — that's BL13), trial activation now atomic at claim (no separate step 6), Concierge tone calibration described as live but V0 is fully scripted (no LLM), storage example used non-existent fields. Plus reframed: trial-end UX (BL11), mandate audit on hard edits (BL12), Apple→magic-link auto-fallback (none exists), locale handling (English-only V0). `mandate_schema.md` Python example bumped from Pydantic v1 (`Config class`) to v2 (`ConfigDict`); `user_id: UUID` not `str`. |
| `7bcbe78` | **pubspec.yaml `+24 → +25` bump.** Saiful tried to ship `+25` via `scripts/build_testflight.sh` between commits; the script auto-bumped + committed before hitting the flag-pass-through error. Build failed; IPA never produced. To finish the upload: `scripts/build_testflight.sh --no-bump`. |
| `19a0617` | **Revert of 4090453.** `flutter build ipa` parses post-`--` tokens as Dart entrypoints, not as args to forward to xcodebuild — got `Target file "-allowProvisioningUpdates" not found.` Restored the working `flutter build ipa` invocation. **Followup chip spawned**: rewrite the script to split into `flutter build ios --no-codesign` + explicit `xcodebuild archive -allowProvisioningUpdates -authenticationKey*` + `xcodebuild -exportArchive`, so the API-key + provisioning-updates flags can land on the archive step where they belong. |
| `47c08a4` | **Post-audit cleanup.** Drop dead `User.deleted_at` from `backend/app/schemas/user.py` — declared in Pydantic but no matching SQLAlchemy column existed in `User`. Soft-delete on users was never wired; the field always read as None. Plus BL14 (mobile drops Brief `proposed_at` + `started_at` timestamps on the wire) + BL15 (`AgentActivation` Pydantic class is fully dormant — `can_use_now()` never called, fields never written; preferred resolution is delete the class). |

Plus the `chore(handover): wrap AT:R31` commit.

### Backlog filed (AT:R31)

| ID | Item | Est | Status hook |
|---|---|---|---|
| **BL3** | D-039 trial activation on claim | 0 (data plane done) | Wired AT:R31. Downstream layers still TODO — see BL11. |
| **BL11** | Trial-end UX (notif + email + summary + reactivation modal + entitlement gate) | 1.5 | Pre-req: SMTP route + push integration |
| **BL12** | Mandate audit on hard edits | 1 | Pre-req: holdings-vs-mandate evaluator (extract from `safety_floor.check_mandate_compliance`) |
| **BL13** | `OnboardingSession.claimed_user_id` binding on claim | 0.5 | Schema field never assigned; sessions go orphan |
| **BL14** | Mobile drops `BriefProposal.proposed_at` + `BriefSession.started_at` | 0.25 | Lossy round-trip; no UI consumer today |
| **BL15** | Delete the dormant `AgentActivation` Pydantic class | 0.25 | Preferred resolution: delete + rely on `lessons.activations()` |

---

## AT:R30  (2026-05-21)

**Documentation reconciliation session.** Single track: bring `docs/08_tech/*` and the Dart mandate models into line with shipped code so the next session reads ground truth, not aspiration. **8 commits, 0 alpha promotes, 0 TestFlight uploads, 0 test changes, 0 backend code touched.** Mobile changes are limited to Dart model expansions that are backward-compatible at runtime.

### How the session ran

Saiful's framing: "keep our official docs in synch with the code. any that deviate, discuss with me." Started with a 4-phase parallel audit via Explore agents (API routes / database schema / backend services / Flutter models) — surfaced **62 deviations** (40 critical / 16 warning / 6 minor). Triaged with Saiful; then worked tier-by-tier:

1. **First triage** (commit `0e2e961`): pick the cluster Saiful greenlit.
2. **Then a question:** "we have so many of this. have we broken anything?" — answer: no, runtime is fine; docs are debt. Saiful: "I want to make sure we are in synch and that the functions described are accurate and delivered." Switched to **systematic reconciliation** — rewrite each tech doc to match shipped code, mark deferred features explicitly.
3. **Six commits** later, every `docs/08_tech/*` doc is either ground truth or carries an explicit "design doc — not yet built" banner at the top.
4. **Final ask:** "we have a project_plan.md somewhere that has the backlog right?" — yes; filed 7 new backlog items (BL4–BL10) for concrete deferred work surfaced by the audit that doesn't naturally land in any Phase 2/3 roadmap stream.

### Commits in order

| Hash | Doc | What it does |
|---|---|---|
| `0e2e961` | `mobile/lib/models/{mandate,brief,journal,auth}.dart` + initial `api_design.md` mandate + `project_plan.md` BL3 | M2 mobile mandate expansion (TargetOutcome, RiskComponents, DailyBriefing + risk_quotes, trial_expires_at, created_at/updated_at on UserMandate; `mandate_used` + `pending_proposal` on BriefSession; `mandate_version` on JournalEntry; `display_name` on AuthUser). All `fromJson` calls default safely if backend omits a field — backward-compatible. **BL3 filed** for D-039 7-day trial activation on claim (deferred). |
| `875e4e1` | `docs/08_tech/api_design.md` | Full rewrite. 16 routers / 60+ routes from `backend/app/api/*.py` decorators. Per-resource tables list shipped routes only; "Not yet delivered" section lists specced-but-not-built routes with status (Replaced / Deferred / Cut). Added 8 sections that were undocumented (`/auth`, `/admin`, `/ai_coach`, `/daily_challenge`, `/glossary`, `/llm`, `/watchlist`, `/feedback`). Streaming section corrected: SSE-only. Rate limits relabelled "not yet enforced". |
| `b5c4858` | `docs/08_tech/data_model.md` | Full rewrite against `backend/app/db/models.py` + Alembic chain (10 migrations). 18 tables documented with current DDL. Mandates clarified as JSONB-snapshot (not normalized columns). Added the audit/operational tables (`bug_reports`, `auth_challenges`, `llm_audit`, `http_audit`, `one_on_one_messages`, `subscription_events`, `sim_watchlists`, `overlay_edit_counts`). Aspirational tables (`credit_transactions`, `llm_calls`, `daily_challenges`, `streaks`, `briefings`, `drift_alerts`, `brief_sessions`, `offers_redemptions`, `audit_log`, `academy_progress`, `one_on_one_sessions`) moved to "Not yet delivered" with replacement notes. |
| `d5550cf` | `docs/08_tech/architecture.md` | Full rewrite. System diagram: melehost Docker Compose + Cloudflare Tunnel + on-prem vLLM. 24 backend services tabled with files + responsibilities. 5 data flows rewritten to match shipped code (Convene the Room, Brief, Onboarding+claim, 1-on-1, Sim trade). Streaming: SSE-only with `X-Room-Run-Id` reconnect path. Background jobs (8 specced) moved to "Not yet delivered". Third-party SaaS (RC / OneSignal / Twilio / Resend / Sentry / PostHog) all flagged as MVP scope; SMTP carry-over surfaced. D-039 trial activation explicitly flagged in the onboarding+claim flow as not-wired with BL3 cross-ref. |
| `c7f0155` | `docs/08_tech/auth.md` + `llm_routing.md` + `stack.md` + design banners on `payments.md` + `platform_facade.md` | **auth.md** heavy rewrite — own `auth_service` reality, not Supabase; HS256 JWTs; A2 audit fix on `/auth/anon`; SMTP carry-over surfaced; HMS/Google/Phone-OTP all deferred. **llm_routing.md** heavy rewrite — preference order `vllm > anthropic > mock`; `TIER_TO_MODEL` table; `tier_policy.pick_tier()` matrix; OpenRouter+locale routing deferred; cache deferred. **stack.md** rewrite with new Status column (Alpha ✅ vs MVP-only per row); code-org tree refreshed. **payments.md** + **platform_facade.md** got status banners at top — both are design-only (RevenueCat SDK absent from pubspec; `mobile/lib/services/platform/` is empty). |
| `8599cd2` | `docs/10_delivery/project_plan.md` | Filed 7 new backlog items (BL4-BL10) for concrete deferrals surfaced by the audit that aren't already absorbed by Phase 2/3 roadmap streams. |

Plus the `chore(handover): wrap AT:R30` commit (`632518a`).

### Why so many deviations existed

Three patterns, all benign:
1. **Docs described the future, code shipped the present.** ~30% — 12 tables documented but never migrated were Beta/MVP features (`daily_challenges`, `briefings`, `drift_alerts`, `streaks`, …). Code is correct; docs were aspirational.
2. **Code evolved faster than docs.** ~50% — Brief got the propose/accept rewrite AT:R27, endpoint structure shifted to body params, mandates were denormalized to JSONB for fast iteration. Each was deliberate; nobody back-updated the markdown.
3. **Pragmatic additions never back-documented.** ~20% — `bug_reports`, audit tables, `auth_challenges`, `subscription_events`, trial date columns. Added because we needed them; nobody updated `data_model.md`.

Code is the source of truth — Postgres + FastAPI + Flutter all agree with each other today. Only the markdown was stale.

### Did the AT:R30 changes break anything?

No. Six edits, all backward-compatible. Docs only + low-risk Dart model expansion (new optional fields with safe `fromJson` defaults). `flutter analyze` clean. **365 backend tests still pass**.

### Backlog filed (AT:R30)

| ID | Item | Est | Trigger |
|---|---|---|---|
| **BL4** | Arabic→Gemini locale routing (D-048) | 0.5 | Blocked on `GoogleProvider` |
| **BL5** | Mandate history API (versions/rollback) | 1 | Replay works via journal today |
| **BL6** | Mandate audit/resolve flow | 1 | Needs drift detection first |
| **BL7** | Agent metadata routes (`/agents` list/details/past_calls) | 1 | Mobile uses client manifest |
| **BL8** | Room run cancel + replay endpoints | 1.5 | Room is unkillable mid-flight |
| **BL9** | Sim trade preview endpoint | 0.5 | Pre-flight extracted from `/sim/submit` |
| **BL10** | Daily challenge attempt endpoint | 0.5 | Useful when streaks ship |

### Where AT:R30 left the ground truth

| If you want to know… | Read |
|---|---|
| What endpoints exist + their shape + what hasn't shipped yet | `docs/08_tech/api_design.md` |
| What's in the database + what tables don't exist yet | `docs/08_tech/data_model.md` |
| How a Convene/Brief/Onboarding actually flows + what runs vs what's MVP target | `docs/08_tech/architecture.md` |
| The actual auth flow (own service, not Supabase yet) | `docs/08_tech/auth.md` |
| LLM tier mapping + provider preference order | `docs/08_tech/llm_routing.md` |
| The whole stack at a glance with Alpha / MVP status per row | `docs/08_tech/stack.md` |

`hosting.md`, `backend_modes.md`, `coding_conventions.md` verified already in sync — left untouched. `tradingagent_integration.md`, `flutter_implementation.md`, `auth_audit.md`, `auth_phase1_adversarial_audit.md` not swept (historical / audit docs that should stay as-of-date-of-writing).

### Bug list at end of AT:R30

**1 open** (`eeeb866f` room run survives container restart, pre-Beta) · **32 resolved** · **3 wont_fix**.

---

## AT:R29  (2026-05-21)

Long, multi-track session. **Two big landings:** Apple Sign-In Phase 3 (with Google-ready OIDC verifier abstraction) and a sweep of four user-reported bugs. Plus a `users.sh` inspection script + Android pulled forward to Alpha. **19 new commits, 358→365 backend tests, 4 TestFlight builds (`+19`/`+20`/`+22`/`+23`/`+24` — one was a revert), 4 alpha promotes.**

### Track A — Bug triage sweep

Four bugs filed by Saiful + me on `+18`/`+21`. All addressed; one re-opened then later marked `wont_fix` on Saiful's call.

| short_id | session resolution | how |
|---|---|---|
| `6fd4144d` (was pending_review) | ✅ resolved | Same fix as a19871c3 — collapsed into one |
| `a19871c3` (open → resolved) | ✅ resolved (`+19`) | Bug-report sheet close button was a `GestureDetector` wrapping a 20px icon — replaced with `IconButton` + 44×44 constraints + tooltip. Apple HIG minimum tap target. |
| `9b9d4790` (open → resolved) | ✅ resolved (alpha-2026-05-21-1) | Lesson 269 "trap" paragraph conflated Convene the Room (streamed batch readout) with 1-on-1 (interactive Q&A). Rewrote the paragraph to make Room = batch + 1-on-1 = interactive. Quiz + Try-It were already correct. |
| `11fde6f6` (open → resolved → reopened → wont_fix) | ⏸ wont_fix | Attempt 4 at "match Lessons hex style" — I shipped a 15%-alpha tinted fill + role-color label in `+19`. Saiful reverted in `+20` ("deferred and reverted twice"). Final call: mark `wont_fix` until explicit design direction. Do not auto-pick. |
| `e2a30a64` (filed `+21`, open → resolved) | ✅ resolved (`+22`) | "Apple sign in failed" — backend logs showed zero `/v1/auth/apple` requests. Root cause: no `Runner.entitlements` file at all in the Xcode project. Capability was enabled on the App ID in AT:R26 but never on the app itself. Created the entitlements + wired `CODE_SIGN_ENTITLEMENTS` into all 3 build configs + pre-warmed the provisioning profile via direct `xcodebuild -allowProvisioningUpdates` with the App Store Connect API key (Flutter's `build ipa` doesn't expose the flag). |
| `a84361f6` (pending_review → resolved) | ✅ resolved | Apple sign-in glitch — closed once `+22` confirmed end-to-end working. |

End-state bug list: **1 open** (`eeeb866f` room run survives container restart, pre-Beta) · **32 resolved** · **3 wont_fix**.

### Track B — Apple Sign-In Phase 3 (and Google-ready OIDC verifier)

The big landing. Audit finding A4 closed.

**`backend/app/services/oidc_verifier.py` (new)** — Generic `OIDCVerifier` class:
- JWKS fetch + TTL cache (1h default) + force-refresh on `kid` miss (handles Apple/Google key rotation automatically)
- python-jose for RSA signature verification (was already a dep — no new packages)
- Audience list support (iOS bundle ID now, future Web Services ID via comma-separated env)
- Injectable into `AuthService` for tests (test_oidc_verifier.py + a `_FakeAppleVerifier` in test_auth_service.py)

**`AuthService.sign_in_with_apple`** — calls `self._apple_verifier.verify()`, extracts `sub` + `email` + persists `full_name` (from request body) as `display_name`. Unverified `_decode_apple_sub` scaffold deleted. The `/v1/auth/apple` 503 gate is gone — route lives in every env.

**Mobile (`+21`)** — Replaced hardcoded synthetic JWT with native `SignInWithApple.getAppleIDCredential()`. Captures `givenName`/`familyName` (first-auth only per Apple's contract). Dropped "Coming in v1.0" caption. Dropped api_client 503 fallback.

**Persistence rules** (mirror users.email):
- First Apple auth → persist `email` + `full_name`.
- Subsequent auths (no email/name claim) → preserve.
- Magic-link real email + later Apple relay → real email **kept**, never overwritten.
- Whitespace `full_name` treated as None.

**New migration `b3f9d2a80007`** — adds `users.display_name` column (nullable). Applied on alpha; `init_schema()` picks it up on fresh containers.

**Settings** — `apple_audiences: list[str]` (default `["ai.agenticmarketintel.amiTrade"]`, comma-separated env). `google_audiences: list[str]` (empty, ready for A6b).

**Tests:** 9 in `test_oidc_verifier.py` (happy path, multi-aud, expired, wrong aud, wrong iss, unknown-kid + refresh-on-miss, tampered sig, malformed, missing-kid, JWKS rotation). 7 in `test_auth_service.py` for email + full_name persist + don't-overwrite rules. **365 backend tests passing** (was 348).

**Smoke verified end-to-end live on alpha:** backend fetched Apple's real JWKS (3 keys), `kid` rotation triggered refresh-on-miss, unknown kid rejected with proper 400. User `8f1e288a-...` claimed with `apple_id` + `email=saifulsaid@me.com` + `display_name=Siti Ahmad`.

### Track C — Android pulled forward to Alpha (new A6b)

Saiful's directive 2026-05-20: "Android in next week". Project plan updated:
- **A6** flipped from ⚡ partial to ✅ done (Phase 3 closed AT:R29).
- **New A6b row** — Google Sign-In on Android, pulled forward from MVP M4 to Alpha closeout. **Blocker:** Saiful needs to create the OAuth Web client_id in Google Cloud Console + register the Android SHA-1 signing fingerprint. Verifier abstraction (~50% of the work) already done.
- "No Android" Alpha non-goal struck through.
- M4 dropped to ⚡ partial (only production Play track remains there).
- Alpha completion: **70% → 73%**.

### Track D — Minimum-data policy (locked AT:R29)

Saiful's directive: "Just ask for sub, name and email."

Locked into project plan A6b row + audit doc:
- Apple: scopes = email + fullName. Persist sub, email, full_name. Nothing else.
- Google (A6b): scopes = openid email profile. Persist sub, email, name. **Throw away** picture, locale, given_name, family_name, hd. Never request People-API sensitive scopes (birthday, gender, phone, address).

### Track E — `scripts/users.sh` ad-hoc user inspection

Read-only postgres queries via SSH to melehost. Dashboard / search / `--recent` / `--anon` / `--apple` / `--google` / `--counts` / `--events` / `--help`. Now shows `device_user_id` (first 8 chars) on every list; search query matches against device_user_id::text.

### Track F — Doc hygiene

- `docs/08_tech/auth_phase1_adversarial_audit.md` finding A4: marked **CLOSED (AT:R29)** with verbose status footer.
- `docs/10_delivery/project_plan.md`: A6 → ✅, new A6b row, M4 ⚡, new "Backlog — low priority" section with BL1 (device-info-on-anon) + BL2 (user_devices table).
- This handover wrap + history rotation.

### Operational footnotes worth surfacing

- **Saiful's anonymous user_id was preserved across the entire Apple flow.** Row `8f1e288a-b288-4b9e-942f-2003b88ba555` was anon → magic-link → Apple — same row throughout. All journal/lessons/oo data intact.
- **App Display Name "Ami Trade" in `Info.plist`** — lowercase 'mi'. Visible to users in iOS Settings → Sign-in with Apple → AMI Trade. Saiful flagged it as "the description was a bit odd" — should be "AMI Trade". Easy one-line fix, deferred to a follow-up build.
- **Provisioning-profile pre-warm friction** — `scripts/build_testflight.sh` doesn't pass `-allowProvisioningUpdates` to xcodebuild. When a new iOS capability is added (like Apple Sign In), the build fails until someone runs xcodebuild manually with the App Store Connect API key flags. **Spawned task** to bake this into the script.
- **`flutter pub get` flagged 59 packages with newer-incompatible versions.** Same as last build; no action needed.
- **SMTP still unchanged.** Carry-over #1 from AT:R28; still the External Beta blocker.

---

## AT:R28  (2026-05-20)

Short, single-task session: ship the TestFlight `+18` build that had been the AT:R27 → AT:R28 carry-over. 2 commits, 0 alpha promotes, 0 test changes.

### Track A — TestFlight `0.1.0+18` upload

`scripts/build_testflight.sh` ran clean end-to-end:

- **Auto-bump** (`f22bf45`): `mobile/pubspec.yaml` `version: 0.1.0+17` → `0.1.0+18`. Script auto-commits the bump per its own protocol.
- **Build**: `flutter build ipa --release --export-method=app-store --dart-define=ALLOW_BACKEND_SWITCH=true --dart-define=AMI_API_URL_ALPHA=https://api-alpha.agenticmarketintel.ai`. Archived in 45.4s, IPA built in 6.0s, final size 25 MB (`build/ios/ipa/ami_trade.ipa`).
- **Upload**: `xcrun altool --upload-app --type ios` → `UPLOAD SUCCEEDED with no errors`. Delivery UUID `5b62b39f-b39f-4901-a1e9-4eb5b5fe00ca`, 25,994,051 bytes in 13.1s (2.0 MB/s). Confirmed at 15:02:05 UTC.

App Store Connect validation noted the usual two warnings (placeholder app icon + launch image) — pre-existing, deferred to brand-asset pass.

Build `+18` carries the **full AT:R27 Flutter payload** that had been sitting at HEAD with no TestFlight pickup:
- `CoachScreen` → `BriefScreen` + `BriefHistoryScreen` + `BriefNotifier`/`briefNotifierProvider` + `models/brief.dart` + all `api_client` method renames
- 33 `coach*` l10n keys flipped to `brief*` across EN / AR / MS
- New `AgentActionSheet` widget on Floor — tapping an unlocked agent now shows `[1-ON-1]` + `[BRIEF]` buttons (Concierge skips the sheet)
- Journal filter chip "COACH" → "BRIEF" (value + l10n key)

### Track B — Upstream skill protocol sync (`53532a7`)

Three project-local slash-command files received upstream updates from the harness during the session:
- `.claude/commands/handover-generic.md`
- `.claude/commands/session-setup.md`
- `.claude/commands/start-fresh-generic.md`

The new variant adds **multi-track support** — each generic skill now takes a track letter (e.g. `/start-fresh-generic R`, `/handover-generic M`) and reads a per-track block from `.claude/session-config.yml`. This project doesn't use the generic skills (it has bespoke `/start-fresh` and `/handover`), but the synced text is what the upstream now ships, so committing keeps the diff at zero.

Committed as `chore(skills): sync generic session protocols from upstream — multi-track variant` to keep the tree clean for handover. No behavioural impact on this project's actual flow.

### What didn't change

- **No backend code touched.** Test count still 348 passing.
- **No alpha promote.** Latest alpha tag stays `alpha-2026-05-20-8`.
- **No content corpus changes.** Lessons / glossary / Q&A / daily challenges / i18n counts unchanged.
- **No DB migrations.** Latest migration on melehost still `a9d1c7e80006` (admin_backoffice).
- **No bug-list movement.** 2 open + 2 pending_review at session start; same at session end.

### Operational footnotes worth surfacing

- **Build is processing in App Store Connect.** First-pass processing typically 15–30 min after upload.
- **`flutter pub get` flagged 59 packages with newer-incompatible versions.** Same as last build; no action needed.
- **SMTP unchanged.** Still no outbound mail route. `SMTP_HOST` blanked in `infra/alpha.env`; `email_service` no-op path firing.
- **iPhone 13 TestFlight install** — once Apple completes processing, install `+18` from TestFlight on device.

---

## AT:R27  (2026-05-20)

Big session, 8 commits, 8 alpha tags (`alpha-2026-05-20-{1..8}`). Three discrete tracks: admin back-office foundation, Coach → Brief rename + discoverability fix, and an audit-driven `user_overlay` runtime fix. Backend tests went 343 → 348 (added admin endpoint coverage + prompt-overlay regression). No TestFlight build pushed — Flutter changes sit at HEAD for the next promote.

### Track A — Admin back-office foundation (carry-over from AT:R26 design grill)

Saiful grilled the design upfront (single-operator MVP with upgrade path to multi-user; CLI for Alpha, Flutter web admin app for Beta; static `ADMIN_SECRET` for Alpha → `admin_users` + JWT in Beta; access level = plan tier only + suspension as sole per-user override; `subscription_events` table for fee tracking + audit; admin tools only, credit-consumption deferred until access-level design done).

`faf4958` shipped:
- **Migration** `a9d1c7e80006_admin_backoffice.py` — adds `users.suspended_at`, `users.trial_started_at`, `users.trial_expires_at`, and creates `subscription_events` table. Initial commit had `down_revision="f7d9b2e60005"` which branched off the wrong head; fixed in `fbe1570` to point at `b1c4e8d70007`.
- **Schemas** `backend/app/schemas/admin.py` — request/response Pydantic models (`AdminPlanChangeRequest`, `AdminTrialGrantRequest`, `AdminTrialUpdateRequest`, `AdminCreditsRequest`, `AdminNoteRequest`, `AdminUserSummary`, `AdminUserDetail`, `SubscriptionEventOut`, `AdminEventsResponse`).
- **Router** `backend/app/api/admin.py` — 9 endpoints, `get_admin` dependency does constant-time HMAC compare on the bearer, 403 on mismatch, 503 when `ADMIN_SECRET` unset. Every write goes through `_record_event` helper → writes to `subscription_events`. Suspend/reinstate enforce 409 on no-op (already-suspended or not-suspended).
- **Suspension enforcement** added to `get_current_user` in `backend/app/api/auth.py`: if `user.suspended_at is not None`, raises 403 with `detail="account_suspended"`. Every authenticated route inherits the block.
- **Config** `ADMIN_SECRET: str = ""` in `Settings`; `infra/alpha.env.example` + `infra/alpha.env` populated.
- **Tests** `test_admin.py` covers all 9 endpoints + the suspension dependency (negative tests for missing/wrong bearer + 403/404/409 paths).

Two follow-up `fix(compose)` commits closed the runtime gap: `docker-compose.yml` was enumerating env vars explicitly and **had never wired `ADMIN_SECRET` or any of the `SMTP_*` vars** through to the api-alpha container. First promote (`alpha-2026-05-20-1`) deployed code but admin endpoints returned 503 because the container saw `ADMIN_SECRET=""`. `fdeb14b` added `ADMIN_SECRET: ${ADMIN_SECRET:-}` to compose; `28eb261` added the 5 SMTP vars at the same time. `SMTP_HOST` itself was blanked out in `infra/alpha.env` (original value preserved as a commented line) so the email_service no-op path keeps firing until a working SMTP route exists — no timeout traffic, no `magic_link_email_failed` log spam.

`1baeed6` added the admin web UI: a single 660-line HTML file at `backend/app/static/admin.html`, served at `/admin` via `HTMLResponse` from `app.main`. AMI palette mirrored from `mobile/lib/theme/ami_theme.dart`. Vanilla JS with `fetch` + localStorage for the bearer. Mobile-first responsive, PWA meta tags. Saiful can `Add to Home Screen` on iPhone Safari for a chromeless app-style entry.

### Track B — Coach Your Agent → Brief Your Agent rename + discoverability fix

`2646971` — the rename commit (64 files, +1908/−1423).

**Why:** "Coach" carried the wrong power dynamic (mentor/therapist), conflicted with the AI Coach Q&A library + the `tutorial_coach_mark` package, and obscured the actual mechanic. "Brief" is CEO-native — a CEO briefs their analysts.

**Discoverability bug surfaced same session:** Brief was buried behind a single unlabelled tune icon in the 1-on-1 header. Even Saiful couldn't find it. Fix: tapping an agent on the Floor now opens a new `AgentActionSheet` widget (`mobile/lib/widgets/agent_action_sheet.dart`) with two big buttons — `[1-ON-1]` (chat icon, hex-blue) and `[BRIEF]` (tune icon, hex-amber). Concierge skips the sheet (no Brief surface). The 1-on-1 header tune icon stays as a secondary route.

**Backend:** `schemas/brief.py`, `services/brief_engine.py`, `api/brief.py` are the new canonical modules. `/v1/brief/*` is the new path. The old `coach.py` files are now back-compat shims: schemas re-export `BriefX as CoachX`, services re-export `BriefEngine as CoachEngine + get_brief_engine as get_coach_engine + hydrate_brief_mandate as hydrate_coach_mandate`, and `api/coach.py` is a 150-line shim that re-mounts the brief routes under `/v1/coach` with a `_log_deprecation` dependency that logs `deprecated_coach_route_used` warning on every hit. TestFlight `+17` keeps working without rebuild.

**Flutter:** `git mv` + class renames + l10n key renames + Dart consumer updates. 33 `coach*` l10n keys flipped to `brief*` across EN/AR/MS via Python script (then `flutter gen-l10n` regenerated `AppLocalizations`). Journal filter chip "COACH" → "BRIEF" via `journalFilterCoach` → `journalFilterBrief` key rename + value update.

**Content + docs:** mechanical Python-script sweep across `content/lessons/*.mdx`, `content/ai_coach/*.json`, `content/daily_challenges/*.json`, `content/glossary/terms.en.json`, and `docs/**/*.md`. CLAUDE.md decision-row updated.

**Preserved as concept vocabulary:** the word "uncoachable" + "cannot be coached around" stays as the Portfolio Manager safety-floor's resistance label (lesson 273 is built on this term — established product vocabulary). `EntryType.AGENT_COACH = "agent_coach"` enum value stays as the DB-stored value (no migration needed for existing journal rows). Audit log identifiers `coach_chat` (audit flow tag) and `coach_overlay_saved` (log key) stay for log-query continuity. The glossary term ID `ami_coach_your_agent` stays (17 lesson files reference it via `<Term id="…" />`) — only the display name was updated to "Brief Your Agent". Lesson file `278_coaching_changes_style_not_floor.en.mdx` keeps its filename + frontmatter `id` field (cross-reference safety); body content was updated.

### Track C — `user_overlay` runtime audit + fix

Saiful asked for an explicit audit: does `user_overlay` actually flow into 1-on-1 + Convene the Room runtime, or does the Brief UI persist overlays that the LLM never sees?

**Finding:**
- **1-on-1: WIRED CORRECTLY.** `agent_runner.py:128` calls `build_agent_prompt(agent_id, mandate, user_id=session.user_id)`. In `agent_prompts.py:48-71`, when `user_id is not None`, `_append_user_overlay` calls `OverlayStore.get_active(user_id, agent_id)` and concatenates the overlay between mandate and safety_floor. Briefings actually shaped 1-on-1 conversations.
- **Convene the Room: BROKEN.** `room_runner.py:963` (regular agents) AND `1037` (PM narration) both hard-coded `user_id=None` when calling `build_room_messages`. `ctx.user_id` was right there on the same line (used for `audit_user_id`) but not threaded into the prompt composer. Result: **every agent in every Room run received `base + mandate + safety_floor`, no overlay.** Brief did nothing during Convene.

`cf56afe` fixed both call sites: `user_id=None` → `user_id=ctx.user_id`. Added 5 regression tests in `test_agent_prompts.py`:
- `test_build_agent_prompt_includes_user_overlay_when_user_id_provided` — saved overlay appears in composed prompt with `USER_OVERLAY_HEADER`.
- `test_build_agent_prompt_omits_overlay_when_user_id_is_none` — anonymous path stays clean.
- `test_build_agent_prompt_omits_overlay_when_user_has_no_overlay` — fresh users get base + mandate only.
- `test_pm_safety_floor_appended_after_user_overlay` — SAFETY FLOOR block stays last for PM.
- `test_room_runner_threads_user_id_through_to_overlay` — **source-level regression**: parses `room_runner.py`, asserts every `build_room_messages(...)` call site passes `user_id=ctx.user_id` (and not `user_id=None`). Verified to fail by `git stash` of the fix.

### Track D — Audit sweep follow-up (`9793c25`)

Saiful asked for a thorough double-check on the rename. The first-pass sub had targeted phrase "Coach Your Agent" + key-prefix `coach[A-Z]`; verb-form usages, suffix-position keys, and mid-string values slipped through. Audit caught 8 classes of gap (LLM-prompt header text, journal chip l10n keys, embedded "coaching" in values, MS translations, content verb forms, glossary definition, docs verb forms, internal docstrings). All fixed in a single commit (59 files, +429/−152). Final classified residual: 174 hits across known-keep categories (concept terms, internal identifiers, backwards-compat shim, third-party package, AI Coach Q&A library).

### Operational footnotes worth surfacing

- **SMTP — still blocked.** DNS resolved overnight (`mail.agenticmarketintel.ai` → `69.57.162.213`) but melehost's ISP blocks outbound to that IP on ports 465 AND 587 (TCP SYN succeeds, SSL/SMTP times out). `smtp.gmail.com` and `mail.privateemail.com` are both reachable from melehost. Carry-over: pick Gmail SMTP (Gmail App Password) or switch to Resend HTTP API (`resend>=2.4` already in pyproject.toml). Until resolved, magic-link sign-in delivers no emails. Compose plumbing for SMTP_* is now correct (was a silent gap pre-AT:R27); only `SMTP_HOST` value blocks the no-op path from triggering.
- **TestFlight `+18` not built yet.** All AT:R27 Flutter work (Brief rename, AgentActionSheet, journal chip relabel) is at HEAD but not yet uploaded. Next session should run `scripts/build_testflight.sh` if Saiful wants to test the new UI on TF.
- **17 anonymous users in the DB** (no claimed accounts yet — magic-link blocked by SMTP). Most recent: `b3bc18aa-3dca-48d7-beb4-803220b40b69` (2026-05-20 16:20). Safe to use for admin-endpoint smoke tests.
- **`AGENT_COACH` enum value preserved.** Journal entries created via Brief Accept still write `entry_type='agent_coach'` to keep existing rows valid. New row titles read "Briefed Bear Researcher → v3" instead of "Coached …" — old rows keep their "Coached …" titles as historical strings.
- **`alpha-2026-05-20-1` was a partial deploy** — schema didn't apply because the migration's `down_revision` was wrong. Caught + recovered mid-promote (no downtime, no rollback). `-2` shipped the migration fix; `-3` shipped the compose fix; `-4` blanked SMTP_HOST; `-5` added the admin UI; `-6` shipped the Brief rename; `-7` fixed the Room overlay bug; `-8` shipped the audit sweep. Don't be surprised by the count.

---

## AT:R26  (2026-05-19)

Closed three of the AT:R25 carry-overs in a single promote + TestFlight cycle: bug:a84361f6 (Apple-glitch UX), B4 (http_audit token leakage), and Phase 4 (sign-out). Also wired SMTP for real magic-link emails (delivery still gated on DNS resolution). 6 commits incl. one merge + a Silent_Scout `07_voice/` research dir Saiful authored mid-session. Backend promoted as `alpha-2026-05-19-3`, TestFlight `+17` uploaded.

### Track A — bug:a84361f6 Apple sign-in 503 glitch

Filed 2026-05-19 13:32, same day as the Phase 1.5 promote. The user tapped "Sign in with Apple" and saw a confusing "Apple sign-in failed." toast because the backend now returns 503 on `/v1/auth/apple` outside env=local (per A4) — the UI didn't explain that it was intentional.

Fix on `claude/bug-fix-20260519-140401` (commit `cd4a3f2`, merged via `4edd0a1`):
- `mobile/lib/services/api/api_client.dart::signInWithApple` wraps the Dio call in try/catch. On `DioException` with `response?.statusCode == 503`, throws `Exception("Apple sign-in isn\'t live in Alpha yet — use email sign-in instead.")`. Other status codes rethrow unchanged.
- `mobile/lib/screens/auth/sign_in_screen.dart::_signInWithAppleScaffold` now reads `ref.read(authNotifierProvider).error` after a failed sign-in and strips the leading `"Exception: "` prefix before showing it in the snackbar (falls back to the generic `signInAppleFailed` l10n string if state has no error).
- Same screen: caption added under the `_AppleButton` — *"Coming in v1.0 — use email sign-in for now"* (hardcoded English, AmiTypography.caption, textLow color, centered). Sets expectations before the tap. No l10n key added; this is alpha-only copy.

The bug-fix worktree was created via the `/fix-bugs` skill (atomic claim → commit → DB flip to `pending_review` → merge to main → worktree removed).

### Track B — http_audit scrubbing (adversarial audit B4 closed)

`f7b6214`. `backend/app/middleware/http_audit.py` gets a new `SCRUB_PATHS` set containing `/v1/auth/{anon, magic_link/start, magic_link/verify, apple, session}`. The dispatch loop sets `scrub = path in SCRUB_PATHS` early; when true, both `captured_request` and `captured_response` are forced to `b"[REDACTED]"` before being passed to `record_http`. Method, path, query, status code, latency, and IP are still recorded — only the bodies are scrubbed. No effect on SSE routes (none are in SCRUB_PATHS) or on the request body that downstream handlers see (the scrub is purely about what gets persisted to the audit table).

3 tests in `backend/tests/unit/test_http_audit_scrub.py`:
- Parametrised across all of `SCRUB_PATHS` — each path's request + response bodies must equal `b"[REDACTED]"` in the captured `record_http` call.
- Non-scrub path (`/v1/some/other/route`) — body must NOT be `[REDACTED]`, request body must contain its actual content (`b"AAPL"`).
- `/v1/health` — `record_http` must not be called at all (still in `SKIP_PATHS`).

### Track C — Phase 4 sign-out

`f7b6214` (backend) + `c2ae379` (Flutter).

**Backend** (`backend/app/api/auth.py`): `DELETE /v1/auth/session` — requires `Depends(get_current_user)`, returns `{"signed_out": True}`. No DB writes. The doc comment makes the design explicit: scaffold tokens are stateless HMAC so there is nothing to invalidate server-side now — this endpoint exists as a clean HTTP contract for a future Phase 5+ token blocklist. Auth dependency means it's covered by the existing audit suite — the path was added to `SCRUB_PATHS` in Track B so bearers don't leak via this route either.

**Flutter** (three files):
- `mobile/lib/services/api/api_client.dart::signOut()` — fires `DELETE /v1/auth/session` inside a try/catch (server response is irrelevant; client wipes its token regardless), then sets `_bearerToken = null`.
- `mobile/lib/state/auth_providers.dart::AuthNotifier.signOut()` — calls `api.signOut()`, then `DeviceUser.clear()` (wipes both the device_user_id AND the bearer token from SharedPreferences), resets `state = const AuthState()`, then `await bootstrap()` so a fresh anonymous session is minted before `_AuthGate` releases the splash. Without the final `bootstrap()` call the gate would hang waiting for a non-null token forever.
- `mobile/lib/screens/settings/settings_screen.dart::_AccountSection` — adds a red OutlinedButton labeled "Sign out" below the existing "Manage Account" button. Only visible when `claimed` is true (i.e. `auth.user != null && !auth.user!.isAnonymous`). Disabled while `auth.loading` is true. Uses `AmiColors.hexRed` for foreground + border so it reads as a destructive-tier action.

The route was added to the same SCRUB_PATHS set as the other auth routes (Track B) so the bearer in the inbound request doesn't end up in audit rows.

### Track D — SMTP magic-link email (carry-over #7 wired)

`f7b6214`. New file `backend/app/services/email_service.py` uses stdlib `smtplib` (no new pyproject dependency — `resend>=2.4` is already declared but unused). Single public function `send_magic_link(to, code)` builds a multipart message (plain + minimal dark-mode HTML), then picks the transport:
- `settings.smtp_port == 465` → `smtplib.SMTP_SSL` (implicit TLS)
- otherwise → `smtplib.SMTP` + `starttls()` (works for 587)

Logs `smtp_not_configured_skip_email` and returns when `settings.smtp_host` is empty (alpha debug-code-only mode preserved). Catches any send exception, logs `magic_link_email_failed`, returns — never raises. Magic-link still works in fallback (debug code visible in UI on `env=local`; on staging the code is only visible in the response if you hit the start endpoint directly, never to the client per A1 lockdown).

`backend/app/services/auth_service.py::start_magic_link` adds one line: `_send_magic_link_email(email, code)` after the DB write. `backend/app/core/config.py` adds 5 fields: `smtp_host`, `smtp_port=465`, `smtp_user`, `smtp_password`, `smtp_from` (all empty by default). `infra/alpha.env.example` updated with a commented placeholder block.

5 tests in `backend/tests/unit/test_email_service.py`:
- No-op when `smtp_host=""` (asserts `SMTP_SSL` never called).
- Port 465 → uses `SMTP_SSL`, logs in, sends to recipient with the 6-digit code in the body.
- Port 587 → uses `SMTP` + `starttls()` + login.
- ConnectionRefusedError from `SMTP_SSL` is swallowed (no raise).
- Plus the sign-out endpoint smoke (200 with valid Bearer / 401 without) — same file because it's a small one-off.

`infra/alpha.env` (gitignored, on Mac only) was populated by Saiful with `SMTP_HOST=mail.agenticmarketintel.ai`, `SMTP_PORT=465`, `SMTP_USER=ami.ai@agenticmarketintel.ai`, `SMTP_PASSWORD=<set>`, `SMTP_FROM=noreply@agenticmarketintel.ai`. **Real email delivery does NOT yet work end-to-end** because `mail.agenticmarketintel.ai` returns NXDOMAIN at every public resolver and at Cloudflare's authoritative NS (lou + rihana), despite the A record (`69.57.162.213`, gray cloud) being visible in the Cloudflare DNS dashboard. The underlying SMTP server IS reachable from Mac on ports 465/587/993 (confirmed via `nc -zv` against the IP directly), so the only thing blocking delivery is the DNS record actually surfacing on the authoritative nameservers. Once DNS resolves, the backend will start sending real emails on the next magic-link request — no further code change needed.

### Track E — Promote + TestFlight `+17`

`/promote-to-alpha` ran cleanly on the second try (first preflight blocked on Saiful's uncommitted Silent_Scout work, which he then asked me to commit as `07f0974` — see Track F):
- Tagged `alpha-2026-05-19-3` at `07f0974`.
- rsync ✓; 5 new SMTP keys verified set on melehost alongside the existing 6.
- `docker compose --profile tunnel up -d --build api-alpha` rebuilt the image, recreated only api-alpha (Postgres + Redis + tunnel kept running). Health check went to `healthy` in <10s.
- `alembic upgrade head` ran clean (no migration changes this session).
- Smoke: `/v1/health` → `env=staging`; `/v1/llm/status` → `vllm` active with all tiers routing to `ami-llm`; `/v1/sim/quote/AAPL` → $297.84 source=`yfinance` (real Yahoo); `DELETE /v1/auth/session` unauth → 401 (the new endpoint's auth guard fires).

`scripts/build_testflight.sh` then auto-bumped `0.1.0+16` → `0.1.0+17` (`e04604b`), built the IPA (25 MB), and uploaded via altool — Delivery UUID `bff0c97f-9561-4218-8d38-9115d422c84f`. App Store Connect processing takes ~15-30 min before the build is visible in Internal Testing.

### Track F — Silent_Scout 07_voice/ (Saiful authored, mid-session)

`07f0974`. Saiful added a new research-track folder for on-device STT + TTS investigation covering 5 languages (EN/AR/MS/zh/yue). Mirrors the LoRA-track structure: `01_constraints` (verbatim production-doc quotes as the boundary fence), `02_candidates` (STT + TTS datasheets), `03_coverage_matrix`, `04_eval` (methodology + datasets + results-README), `05_recommendation` (daily-brief + interactive + path-forward), `06_prototypes` (README scaffold). Top-level `Silent_Scout/README.md` was updated to add the new row in the active-tracks table and the path tree. 1697 insertions across 14 new files. Not part of the AMI Trade production track but in the repo + history. Referenced approved plan: `~/.claude/plans/you-are-working-on-stateless-sedgewick.md`.

### Operational footnotes worth surfacing

- **Bug `6fd4144d`** (bug-report close button) — fix `af01328` was already in main from a prior session (the bug-fix worktree `claude/bug-fix-20260517-225716` was confirmed during AT:R26 to have no commits ahead of main). DB status still `pending_review`; verify on TestFlight `+17` and flip to resolved.
- **Bug `a84361f6`** — DB status flipped to `pending_review` mid-session by `/fix-bugs`. Same verify-on-`+17`-then-flip-to-resolved pattern.
- **SMTP DNS — UNRESOLVED at session end. Resume here on AT:R27.**

  **State of evidence at end of session:**
  - Cloudflare DNS dashboard for `agenticmarketintel.ai` shows: `Type=A, Name=mail, Content=69.57.162.213, Proxy=DNS only (gray cloud), TTL=Auto`. Warning triangle next to the row is benign — just the standard "exposes origin IP" notice for gray-cloud A records.
  - But `dig +short mail.agenticmarketintel.ai @rihana.ns.cloudflare.com` AND `@lou.ns.cloudflare.com` (the two authoritative NS for the zone) both returned EMPTY. 1.1.1.1 and 8.8.8.8 returned NXDOMAIN. melehost's resolver returned SERVFAIL. **Authoritative NS empty means it's not a propagation delay — Cloudflare's nameservers genuinely don't see the record.**
  - The IP itself IS a real Namecheap-owned mail server: from Mac, `nc -G 5 -zv 69.57.162.213` connects on ports 465, 587, 993. From melehost, port 465 timed out (separate question — possible ISP block on outbound 465; check 587 next).
  - SMTP creds in `infra/alpha.env`: `SMTP_HOST=mail.agenticmarketintel.ai`, `SMTP_PORT=465`, `SMTP_USER=ami.ai@agenticmarketintel.ai`, `SMTP_PASSWORD=;hMo@u]n^{77`, `SMTP_FROM=noreply@agenticmarketintel.ai`. All 5 verified live on melehost via the promote step-4 `grep` (counted as `<set>`).
  - Backend code is wired + tested + promoted (`alpha-2026-05-19-3`). `email_service.send_magic_link()` is a no-op when `smtp_host=""` and never raises on send failure — so the rest of the app is safe.

  **What to try on AT:R27** (in order, escalating):
  1. **Re-query DNS first thing** — it might just have propagated overnight. `dig +short mail.agenticmarketintel.ai` from Mac. If non-empty, immediately re-run the SMTP smoke test from earlier in AT:R26 (use the IP directly to bypass DNS if needed — `openssl s_client -connect 69.57.162.213:465 -servername mail.agenticmarketintel.ai`).
  2. **If still NXDOMAIN**, ask Saiful to delete + re-add the Cloudflare record. Sometimes a saved-but-not-actually-persisted state happens — re-creating the row forces a clean propagation.
  3. **Check Namecheap's mail-server hostname** — the IP belongs to Namecheap; their Private Email service typically documents the SMTP hostname as e.g. `mail.privateemail.com`, NOT a custom-domain CNAME. Saiful might need to set `SMTP_HOST` to whatever Namecheap's mail dashboard documents (and the TLS cert will be issued for THAT hostname, not the custom domain).
  4. **Test outbound port 465 from melehost** — `ssh melehost "timeout 8 nc -zv mail.privateemail.com 465"` once DNS works. If the connection times out, try 587. If both time out, melehost's ISP may be blocking outbound SMTP; the workaround is to route through a different SMTP provider that listens on a non-standard port, or relay through Mailgun/Postmark.
  5. **Fallback**: Gmail SMTP. `smtp.gmail.com:587` + App Password from any Gmail account Saiful has 2FA enabled on. Drop-in — just update the 5 `SMTP_*` keys in `infra/alpha.env` and re-promote.

  **Until SMTP works, magic-link sign-in is broken for any external user.** Alpha testers don't see it because on `env=staging` the debug code is NOT returned in the API response (Phase 1.5 A1 lockdown) — so a tester who taps "Send Code" gets stuck at the "enter the code" step with nothing to type. **This is a real blocker for External TestFlight launch.**
- **L-1 residual** (from AT:R25 audit) still NOT closed: `OneOnOneStartRequest.user_id: UUID | None` lets a null body bypass `_own_body`. Limited blast radius (resulting session has `user_id=None`, `_own_session` rejects on subsequent calls) but worth tightening if 1-on-1 abuse becomes a real signal.
- **TestFlight `+17` is the same code as +16 plus the AT:R26 changes** — testers on +16 will still work against the new backend (no breaking API change; only the new `DELETE /v1/auth/session` route was added). Apple sign-in attempt on +16 still produces the old generic error; only +17 has the friendly snackbar + caption.

### Carry-overs for AT:R27

Counts audited against tree state at end of AT:R26.

1. **🚧 SMTP DNS — magic-link email is the External Beta blocker.** `mail.agenticmarketintel.ai` was NXDOMAIN at Cloudflare's authoritative NS at session-end despite the gray-cloud A record being visible in the dashboard. Backend code is wired + tested + promoted; only DNS surfacing blocks real email. **Full debug trail + escalation steps are in "Operational footnotes worth surfacing" above** — start by re-querying DNS on session resume; if still NXDOMAIN, try delete+re-add in Cloudflare, then Namecheap's documented mail hostname, then Gmail SMTP fallback.
2. **`6fd4144d` bug-report close button — `pending_review`.** Verify on TestFlight `+17` and flip to resolved.
3. **`a84361f6` Apple-sign-in 503 glitch — `pending_review`.** Verify on TestFlight `+17` and flip to resolved.
4. **`11fde6f6` floor hex agent style — re-open from AT:R24/R25.** No movement again this session (deferred per Saiful).
5. **`eeeb866f` — room run survives container restart — open, deferred-pre-beta.** Note + estimate still in `bug_reports.steps`.
6. **Apple sign-in Phase 3** — Saiful enabled "Sign in with Apple" capability in the Apple Developer portal at the bundle ID this session. Backend still returns 503 outside `env=local` — replace `auth_service.py::_decode_apple_sub` with real PyJWT + Apple JWKS verification. ~1 day.
7. **Google sign-in Phase 3** — explicit decision this session: **defer until Android v1.0**. Don't start the Flutter `google_sign_in` package wiring yet.
8. **B-tier adversarial-audit findings remaining** (deferred to pre-External-Beta): rate limiting on `/auth/anon` + LLM-heavy routes; magic-link attempt counter + per-IP throttle; feedback upload size enforced at the proxy + streaming read. (B4 token-scrubbing closed this session.)
9. **App Store Connect Privacy URL** — Saiful confirmed `https://www.agenticmarketintel.ai/privacy/` is live and added it in App Store Connect → App Information → Privacy Policy URL. Done this session, unblocks External Beta submission.
10. **External TestFlight launch** — still needs a Beta App Description from Saiful + ~24h Apple review on first external build. No External Beta artefact yet.
11. **Animation production** — 15 `<Animation>` MDX tags in `content/lessons/` still render `AmiHexPlaceholder`. Lottie vs CustomPainter decision still open.
12. **A29 light-mode refactor** — v1.0 work.
13. **Two sibling worktrees with unmerged docs** — `claude/blissful-darwin-419097` (bug-pipeline spec + D-057) and `claude/exciting-shtern-aad051` (lessons-landing hex-cluster redesign). Still pending Saiful decision.

### Watch items (not tasks)

- **SMTP delivery in production.** Once DNS surfaces, the very first magic-link request will go out via SMTP. If the SMTP server returns a bad-credentials or unknown-recipient error, `email_service.send_magic_link` swallows it and logs a warning — the user still gets their code via the next attempt OR (on env=local) via the debug chip. On staging there's no debug-code fallback visible to the user, so a silently failing SMTP will look like "magic link doesn't work" to testers. Worth checking the api-alpha logs for `magic_link_email_failed` entries after the first real email attempt.
- **Apple endpoint 503 still in effect on Alpha.** Phase 3 hasn't shipped, so any tester who taps "Sign in with Apple" still gets the 503 path — now with a friendly message (AT:R26 fix). Until Phase 3 lands, magic-link is the only working claim path on Alpha.
- **AT:R24's NVFP4 quantisation watch item still applies** — `ami-llm` (Gemma 4 31B NVFP4) occasionally emits space-split tokens. Not blocking.

---

## AT:R25  (2026-05-19)

Single-track session: build, audit, and promote real authentication. 6 commits. Backend promoted to Alpha as `alpha-2026-05-19-2`, TestFlight `+16` shipped. Two audit docs written. Working tree clean throughout.

### Track A — Phase 1 (route guards + HMAC scaffold tokens)

`4276487` (docs) + `48eb0d6` (code) land the foundation. The dependency `app/api/dependencies.py::get_current_user` extracts a `Bearer` token from `Authorization`, hands it to `parse_scaffold_token()`, and returns the live `User` row (or raises 401). Token format moves from the legacy unsigned `scaffold:<hex>` to HMAC-signed `scaffold:<hex>:<sig>` (`_scaffold_token` in `auth_service.py`, signature is HMAC-SHA256 over `user_id.hex` with `SECRET_KEY`). The legacy form is still accepted but only when `env=local` — so a developer running the Mac unit tests offline doesn't have to set a key.

Routers swept: `mandate`, `journal`, `watchlist`, `coach`, `one_on_one`, `room` get a router-level `dependencies=[Depends(get_current_user)]`. `sim` + `lessons` mix public and user-specific routes, so the dependency is per-route. Every route that takes `user_id` in the path also asserts `current_user.id == user_id` and raises 403 on mismatch — `mandate.py`, `journal.py`, `watchlist.py`, `sim.py`, `lessons.py` use a local `_own(current_user, user_id)` helper for the check. Feedback's `_resolve_user_id` was migrated to call `parse_scaffold_token` (still returns None silently on bad/missing tokens — bug reports stay un-authed by design).

Flutter side of Phase 1: `mobile/lib/services/api/api_client.dart` gains a `_AuthInterceptor` (Dio) that attaches `Authorization: Bearer <token>` on every request once `_bearerToken` is non-null. `AuthNotifier.bootstrap()` + the magic-link verify + Apple sign-in handlers each call `api.setToken(r.token)` after they receive a fresh token.

12 unit tests in `backend/tests/unit/test_auth_dependency.py` cover `parse_scaffold_token` happy paths, forgery rejection, malformed input, and 401/403/200 on the mandate routes. 287 backend tests pass at end of this track.

### Track B — Adversarial audit + Phase 1.5 corrective work

`4276487` also lands the second audit doc: [docs/08_tech/auth_phase1_adversarial_audit.md](docs/08_tech/auth_phase1_adversarial_audit.md), produced by an external review of Phase 1. The reviewer caught 9 deploy-blocking issues the self-audit either missed or characterised as "accept for alpha" when they were actual bypasses of the new security layer. Same `48eb0d6` commit landed the fixes — they were intentionally bundled because Phase 1 alone was not promotable.

Findings closed:

- **A1.** `env=dev` accepted the legacy unsigned format AND returned the magic-link debug code in response bodies — both reachable via melehost's public Cloudflare Tunnel. Tightened: `parse_scaffold_token` accepts legacy only in `env=local`, `_is_dev_env()` returns True only in `local`, and `app/main.py` raises `RuntimeError` at boot if `env != local` and `SECRET_KEY` is still the default. A new env value `staging` is now the canonical alpha env (melehost runs as `AMI_ENV=staging`).
- **A2.** `/v1/auth/anon` was a token-minting oracle — POST `{device_user_id: <victim>}` returned a signed token for any UUID. Fixed in `auth_service.py::ensure_anonymous`: a supplied `device_user_id` is honoured only when the caller also presents a Bearer whose parsed `user_id` matches. Otherwise the row is minted fresh, ignoring the body. `api/auth.py::anon_session` parses the optional Bearer with `_user_id_from_token` and passes it through.
- **A3.** Magic-link verify trusted body `user_id`, letting any caller bind a captured email to a victim's row. Fixed: both `magic_link/start` and `magic_link/verify` require `get_current_user`, the `user_id` field was dropped from `MagicLinkStartRequest` and `MagicLinkVerifyRequest`, and the bind always goes to `current_user.id`. Debug code returns only in `env=local`.
- **A4.** `/v1/auth/apple` decoded the JWT without verifying Apple's signature — a forged 3-part JWT with any `sub` worked. Until Phase 3 ships real verification (PyJWT + Apple JWKS), the route returns 503 outside `env=local`.
- **A5.** `/v1/lessons/activations/grant` was completely unauthenticated. Removed (the underlying `lessons_service::grant_activation` stays; founder grants now happen via psql).
- **A6.** Body / object ownership added to `room.py::stream_room` + `get_room` (loads run, checks `run.user_id`), every coach route (`_own_body` for body `user_id`, `_own_session` for routes that load a session), and every 1-on-1 route. `_own_session` is strict — a session with `user_id=None` is rejected.
- **A7.** Flutter bootstrap was lazy (`Future.microtask(n.bootstrap)` fired only when something watched `authNotifierProvider`). Feature providers could call protected routes before the Dio interceptor had a token. Fixed: new `_AuthGate` widget wraps `home` in `app.dart` and watches `authNotifierProvider.token`; renders a splash until non-null. `DeviceUser` was extended to persist both the device_user_id AND the Bearer token to SharedPreferences (`getToken()`, `setIdAndToken()`, `clear()`), so cold starts replay the token and the backend recognises the returning user (otherwise A2 would orphan users on every launch).
- **A8.** SSE methods (`streamCoachMessage`, `streamOneOnOneMessage`, the room stream) used raw `http.Client()` and bypassed the Dio interceptor — they would 401 against the new backend. Fixed: a new `ApiClient::_sseRequest(uri, body)` helper builds an `http.Request` with `Authorization: Bearer $_bearerToken` and throws if the token is missing. All three SSE call sites use it.

15 + 4 new tests in `backend/tests/unit/test_auth_phase1_5_audit_fixes.py` — one per finding plus body-ownership variants for room/coach/1-on-1 routes. 306 backend tests pass total.

Two cleanup pieces also landed in the same commit: removed the dead `ApiClient::grantActivation()` Flutter method (no callers, route gone), and refreshed stale docstrings in `auth.py` + `auth_service.py` that still described the legacy token format.

### Track C — Alpha promote (the two-attempt story)

First promote (`alpha-2026-05-19-1`, tag deleted) tagged at `181cbd1` and rsync'd cleanly. `infra/alpha.env` had been updated locally to add `ENV=staging` + `SECRET_KEY=$(openssl rand -hex 32)`. Backend booted healthy, but `curl /v1/health` returned `"env":"local"` and `docker exec` showed `SECRET_KEY length: 0` — the container wasn't seeing either value. Root cause: `docker-compose.yml` had `ENV: ${AMI_ENV:-local}` (looking for `AMI_ENV`, not `ENV`) and no entry for `SECRET_KEY` at all. So the file shipped via `scp infra/alpha.env melehost:~/ami_trade/.env` was being read by docker-compose but the two new keys were ignored.

`12a5da8` (fix(compose)) added `SECRET_KEY: ${SECRET_KEY:-}` alongside the existing `ENV: ${AMI_ENV:-local}` mapping. `infra/alpha.env` was renamed `ENV=staging` → `AMI_ENV=staging` to match the compose convention. Second promote tagged `alpha-2026-05-19-2` at `12a5da8` ran cleanly: health returned `env=staging`, every adversarial-audit lockdown verified live (401 unauth, 401 legacy, 503 apple, 405 grant, fresh anon UUID).

TestFlight `+16` was uploaded and on-device-verified BEFORE the backend promote, per the adversarial audit's recommendation — otherwise `+15` clients (which don't have the eager bootstrap, SSE auth, or token persistence) would have 401'd the moment the new backend went live. Smoke checklist verified on TESTING IPHONE 13; backend logs show 2 completed TSLA Room runs (~5.4 min each), all 4 journal entry types written in the smoke window.

### Operational footnotes worth surfacing

- `eeeb866f` (room run survives container restart) got a deferred-pre-beta note appended to `bug_reports.steps` early in the session: trigger = External Beta launch OR Cloud Run migration whichever first; Tier 1 (Celery+Redis full retry) is ~3–4 days, Tier 2 (+ LangGraph checkpoint resumption) is ~10–12 days.
- A residual L-1 finding the self-audit flagged but Phase 1.5 did NOT close: `OneOnOneStartRequest.user_id` is `UUID | None`. Sending null bypasses the FLOOR_PASS gate (`_own_body` no-ops on None). Limited damage — the resulting session has `user_id=None` and `_own_session` rejects it on subsequent calls — but worth tightening if 1-on-1 abuse becomes a concern.
- `http_audit` middleware captures full request/response bodies, which means **every issued bearer token sits in `http_audit` rows** alongside magic-link codes and Apple JWTs. Adversarial audit flagged this as B4 (must-fix before External Beta); deferred this session. **[Closed in AT:R26.]**

---

## AT:R24  (2026-05-18)

Three-track session: (a) clear the bug queue from AT:R23's walkthrough release, (b) draft + publish the alpha-stage Privacy Policy and Terms of Service, (c) push `0.1.0+15` to TestFlight Internal. 19 commits. Backend untouched (no `/promote-to-alpha`).

### Track A — Bug queue: 3 fixed, 1 attempted-and-reverted

Used `/start-fresh` → bug list → `/fix-bugs` worktree (`.claude/worktrees/bug-fix-20260517-225716`, since cleaned up). All claimed atomically against melehost `bug_reports.assigned_branch`. Two of three saw both `pending_review` → `resolved` flips after Saiful verified on-device; the third is still `pending_review`.

**`af01328` — fix(bug:6fd4144d): add explicit close button to bug report sheet.** The sheet had only a swipe-down dismiss; added a `×` icon in the header row next to "Report a bug". File: `mobile/lib/screens/feedback/bug_report_sheet.dart`. **Status: pending_review** (committed + on-device + on TestFlight, awaiting Saiful's flip to resolved).

**`75ba23a` (amended) — fix(bug:cb81a6d8,e2857081): lessons screen back nav + hex cluster layout.** Two fixes in one file:

- `cb81a6d8` — `LessonsScreen._Header` now accepts a `showBack` parameter and renders an arrow when `Navigator.of(context).canPop()` is true. Fixes the no-exit trap when reached from the locked-agent "Go to Lessons" button (which pushes the screen standalone, outside the HomeShell IndexedStack where the bottom nav lives). **Status: resolved.**
- `e2857081` — `_HexCluster` geometry rewritten in `a51a75b`: 1+6 clock arrangement (N/NE/SE/S/SW/NW around centre) where every surrounding hex shares a full edge with the centre. Replaces the prior 3-cols × 2-rows grid that had FA/SB as same-row neighbours of FON — and for flat-top hexes, same-row means single-vertex contact only ("points meeting points" per Saiful). `hexW = maxWidth × 2/5` so the cluster fills available width; cluster bounding box is 2.5*hexW × 3*hexH (≈ 358×372 on iPhone 13 vs the prior 358×207 — plus no overlap). **Status: resolved.**

**`11fde6f6` — floor hex agent style — attempted, reverted, re-attempted, re-reverted.** Pattern worth noting for future sessions: Saiful's bug report said "the design used in 'floor' for the hex agents should be similar to the design used in the lessons hex." First interpretation went big (`497a2a1`: full edge-to-edge 4×3 staggered honeycomb of `HexAvatar`s, captions stripped, lock state moved to `HexAvatarStatus.locked`). Rejected: *"oh no. that was ugly. revert it."* Reverted in `52748ce`. Second interpretation, clarified by Saiful: only the BUTTON COLOUR matched. Added a `solid: false` flag to `HexAvatar` that mirrors `TrackHexButton`'s translucent fill (`color × 0.15` alpha + role-colour label, no border in the variant). Iterated through size bumps and border removal across three commits (`9a1c93d`, `569ad06`, `902b5ff`). All three reverted by user request: *"I am too tired to evaluate right now."* Bug **flipped back to open** for a future session. The `<adj>-<noun>-<hex>` worktree pattern + atomic `bug_reports` claim held throughout — no leaked state.

DB at end of session: `open=2 / pending_review=1 / resolved=26 / wont_fix=2`. The 2 open are `11fde6f6` (re-deferred above) and `eeeb866f` (room-restart, large, Beta-window).

### Track B — Privacy Policy + Terms of Service drafted, published, versioned

Picked up A22 part 2 from the carry-over list. Three commits.

**`9fbfe6a` — `docs/09_compliance/{privacy_policy,terms_of_service}.md`.** Assembled the clause-by-clause starter language from `legal_plan_ami_trade.md` into two standalone DRAFT documents lawyer review can act on (16 Privacy clauses + 14 ToS clauses + 2 placeholder subsections). Each clause keeps its "Inspired by" peer-source footnote inline so the lawyer can spot-check. Five lawyer-only items called out explicitly: ToS §2 (not investment advice), §11 (liability cap), §13 (governing law), §13.1 (arbitration), §15 (indemnity). ToS ends with a "Lawyer-only checklist" table.

**`5761373` — alpha HTML published at `/privacy/` and `/terms/`.** `website/privacy/index.html` and `website/terms/index.html`. URL convention chosen as directory layout (`/privacy/index.html`) so Apache serves them at clean URLs matching the existing `index.html` footer's `/privacy` and `/terms` links. Style: imports the existing `assets/css/site.css` tokens, with inline page-specific CSS in each file (one-off rather than a shared `legal.css` since only 2 pages). Alpha-stage adjustments vs the markdown drafts: "Inspired by" footnotes stripped, "DRAFT — pending lawyer review" softened to an amber "Alpha disclosure" callout, ToS §13 filled in with Malaysian law + non-exclusive jurisdiction + mandatory-consumer-rights carve-out (preliminary; lawyer adjusts at incorporation), §13.1 arbitration + §15 indemnity dropped for alpha. `sitemap.xml` updated with both URLs.

**`764a6ea` — doc-level versioning + publishing playbook (`docs/09_compliance/VERSIONING.md`).** Three layers identified: doc-level (this commit), URL-level (kicks in when v2 ships), app-level acceptance tracking (Beta+ work). Doc-level shipped: `<meta name="document-version">`, `<meta name="document-effective-date">`, `<meta name="document-status">` on each HTML; visible "Alpha · Version 1.0 · Effective 18 May 2026" in header; "Version history" `<section>` at the bottom (one entry now). Markdown sources synced with same Version + Effective + Published-HTML metadata. VERSIONING.md documents semver convention (major = material → 14-day notice; minor = clarification; patch = typos), material-vs-non-material gate (5 questions), step-by-step publish checklist (edit MD → mirror HTML → archive previous → bump meta → update sitemap → commit → FTP deploy → smoke-check), URL convention (canonical = self for archived versions, canonical = `/privacy/` for current), and a "What NEVER happens" footer.

**`bf2c83c` — sweep `.com` → `.ai`.** Saiful uploaded the HTMLs, then I curl-checked and discovered `agenticmarketintel.com` doesn't resolve — the live marketing site is on `.ai`. Saiful confirmed via AskUserQuestion: "`.ai` is canonical". Perl-replaced URL refs across 10 files (`docs/09_compliance/*`, `website/{WEBSITE.md, deploy_ftp.py, sitemap.xml, index.html, privacy/index.html, terms/index.html}`). Preserved untouched: the two `hello@agenticmarketintel.com` email refs in `index.html` (lines 701, 767) — email hosting is a separate concern. Saiful re-uploaded; URLs verified live at `https://www.agenticmarketintel.ai/{privacy,terms}/`.

### Track C — TestFlight `+15`

**`9c464b7` — pubspec bump 0.1.0+14 → +15.** `scripts/build_testflight.sh` ran cleanly: release build, signed with the same Distribution cert, uploaded via `altool`. Saiful confirms `+15` is live on TestFlight Internal. Ships the AT:R23 walkthrough (`+14` had it) + the three AT:R24 bug fixes above. No External Beta artefact yet (still a carry-over). App Store Connect → App Information → Privacy Policy URL should be set to `https://www.agenticmarketintel.ai/privacy/` per Saiful's confirmed canonical-domain answer.

### Carry-overs for AT:R25

Counts audited against tree state at end of AT:R24.

1. **`11fde6f6` floor hex agent style — re-open.** All this-session attempts reverted. Saiful's note before stopping: clarified that it was only the BUTTON COLOUR style he wanted to match (the lessons hex's translucent fill + colored text, not the cluster layout). Next session should try a fresh approach with that constraint clearer — possibly involving a `solid: false` variant of `HexAvatar` similar to what `902b5ff` shipped, but only after a design-only review (no commit-and-rebuild loops). All commit history is on main (in the revert pairs) if helpful.
2. **`eeeb866f` — room run survives container restart — still open/deferred (large).** Clean upgrade path (Celery + Redis broker; per-user FIFO) sketched in `docs/external/async_job_server_design_prompt.md`. Beta-window work.
3. **`6fd4144d` bug-report close button — `pending_review`.** Committed in `af01328`, on iPhone, on TestFlight. Saiful to flip to `resolved` once verified.
4. **Lawyer review of Privacy + ToS.** The published HTML at `agenticmarketintel.ai/{privacy,terms}/` is the alpha-stage version (clearly disclosed in amber banner). The canonical markdown at `docs/09_compliance/{privacy_policy,terms_of_service}.md` keeps the lawyer-only placeholders and "Inspired by" footnotes for review. Five clauses are jurisdiction-sensitive — see ToS' "Lawyer-only checklist" table at the bottom.
5. **App-side acceptance tracking** (the "version 14-day notice + re-accept" Beta+ work). Spec in `docs/09_compliance/VERSIONING.md` under "App-side acceptance tracking (Beta+ work)". Needs a `policy_acceptances` table + backend comparison logic + Flutter banner. Beta scope.
6. **App Store Connect Privacy Policy URL** — confirm in App Store Connect that it's set to `https://www.agenticmarketintel.ai/privacy/`. Critical before External Beta submission. Probably already correct from prior sessions but worth a glance.
7. **External TestFlight launch** — Beta App Description + ~24h Apple review on first external build. `scripts/build_testflight.sh` uploads to Internal only by default; no External Beta artefact in the repo yet.
8. **Animation production** — 15 `<Animation>` MDX tags in `content/lessons/`. All render `AmiHexPlaceholder`. See `memory/project_animations.md` for the Lottie vs CustomPainter decision.
9. **A29 light-mode refactor** — 125+ hardcoded `AmiColors.slate900`/`slate800` references across `mobile/lib/`. v1.0 work.
10. **Two sibling worktrees with unmerged docs** — `claude/blissful-darwin-419097` (one commit `f94ad0e` — bug-pipeline spec + D-057) and `claude/exciting-shtern-aad051` (one commit `ead7038` — lessons-landing hex-cluster redesign). Still pending Saiful decision: merge to main or discard. The hex-cluster redesign is especially worth a look now that `a51a75b` has changed how the lessons cluster is laid out — they may conflict or one may obsolete the other.

### Watch items (not tasks)

- **Domain mismatch hygiene.** The `.com` references in `index.html` for emails (`hello@agenticmarketintel.com` on lines 701 + 767) were deliberately preserved — email hosting is independent of web hosting. If Saiful's actual support email is on `.ai` now (the new legal docs use `privacy@.ai` and `legal@.ai`), those `hello@.com` refs become stale. Worth confirming his email setup and unifying.
- **Testers on `+15`** are the first to see the bug-fix release. Three things to watch for in new bug reports: (a) anyone failing to find the new `×` close on the bug-report sheet (unlikely but possible if iconography reads wrong at smaller screen sizes); (b) the back arrow on `LessonsScreen` showing in unexpected contexts (it triggers on `canPop()` — fine on the agent-panel push, but verify it doesn't appear inside the main HomeShell where it'd just close the tab); (c) the new lessons hex cluster size (3*hexH tall) crowding any tour overlay positioning that AT:R23 set up for the smaller 2*hexH cluster.
- **NVFP4 quantisation produces space-split tokens** — observed since day one. Not blocking alpha.


---

## AT:R23  (2026-05-17)

Single-feature session: 3 commits implementing the first-time user walkthrough. Pure mobile work — backend untouched, no Alpha promotion. Triggered by Saiful's `/grill-me` session: *"the app is selling itself as a gamified 'education' utility. so yes, the trade, the user should have a walkthrough."*

### First-time walkthrough — 4 contextual coach-mark tours (`462dafe`)

Design decisions locked during the grill: per-section auto-pop tours (not one giant tour); `tutorial_coach_mark` package (not custom); 3–5 steps per section; "Try it now" CTA only on the Convene step; intro bottom sheet only for Floor; one global reset in Settings.

**Architecture:**

- **`mobile/lib/features/tour/`** — new package containing the whole feature.
  - `tour_service.dart` — `TourSection` enum (floor/portfolio/journal/lessons) + `TourService` with `hasSeen` / `markSeen` / `resetAll` backed by SharedPreferences keys `tour_{section}_seen`.
  - `tour_providers.dart` — `tourServiceProvider` (Riverpod) + `activeTabIndexProvider` (StateProvider<int>).
  - `tour_card.dart` — shared AMI-styled tooltip widget with title (cyan mono) / body / skip / next buttons. Supports an optional `tryNowLabel + onTryNow` pair for the Convene step.
  - `tour_intro_sheet.dart` — modal sheet shown before the Floor tour; returns `bool?` via `Navigator.pop`.
  - `{floor,portfolio,journal,lessons}_tour.dart` — `buildXxxTargets()` functions returning `List<TargetFocus>`.

- **`IndexedStack` gotcha:** `HomeShell` keeps all 5 tab widgets alive via `IndexedStack` so every screen's `initState` fires on app start regardless of which tab is visible. Naive trigger-from-initState would fire all 4 tours simultaneously over the Floor tab. Solved with `activeTabIndexProvider`: HomeShell writes the current tab into it on every `onTap`, and each screen uses `ref.listen(activeTabIndexProvider, ...)` in `build` to fire the tour only when its index becomes active. Floor (tab 0) additionally fires from `initState` since it's the entry tab.

- **GlobalKey wiring:** 4 screens converted from `ConsumerWidget` to `ConsumerStatefulWidget` to hold GlobalKey fields. Private widget constructors (`_Header`, `_ValueCard`, `_WatchlistSection`, `_FilterRow`, `_SearchBar`, `_SlimProgressBar`, `_HexCluster`) gained `super.key` so the key flows down to their RenderBox.

- **Floor tour (5 steps):** Concierge hex → first agent tile → another agent tile (locked) → daily challenge card (conditional — only included if the challenge's RenderObject has non-zero size) → Convene the Room button. Convene's `TourCard` shows the dual-button row "Skip tour / Try it now → / Got it". Tap "Try it now" → tour skipped → `ConveneSheet.show(context)` opens.

- **Portfolio / Journal / Lessons tours (3 steps each):** Portfolio = header / value card / watchlist. Journal = filter chips / search bar / list area. Lessons = header / progress bar / hex cluster.

- **Completion:** Each tour ends with a green/cyan/blue floating SnackBar ("Go convene your first Room.", "Try a trade — all simulation, no risk.", etc.).

- **i18n:** 37 new keys in `app_en.arb` under a `tour*` namespace (intro / 5×Floor / 3×Portfolio / 3×Journal / 3×Lessons / completion x4 / nav buttons / settings). Same set stubbed into `app_{ar,ms}.arb` with English values pending external translation.

- **Settings:** new `_WalkthroughSection` between Help and Account renders one "Restart app tour" tile that calls `tourService.resetAll()` and snackbars "Tour restarts next time you visit each section."

### Fix 1: scroll target into view before focus (`684b180`)

Convene step coach-mark fired against a button below the initial scroll fold — Saiful saw the spotlight halo over empty space. `TutorialCoachMark.beforeFocus` callback now calls `Scrollable.ensureVisible` on each target so the highlighted element is brought into view before the spotlight opens. Same pattern applied to Portfolio (ListView) and Lessons (SingleChildScrollView).

### Fix 2: tour tooltip overflow + bug-report keyboard occlusion (`18ddf71`)

Two observations during on-device verification:

- **Journal step 3** target = the `Expanded` list area, which fills most of the screen. `ContentAlign.top` math (`bottom = haloHeight + (screenHeight − targetCenterY)`) pushed the tooltip's top edge above the screen on tall targets. Switched to `ContentAlign.custom` with a fixed `top: 180` anchor below the search bar.
- **Lessons step 3** target = the hex cluster, positioned high enough that `ContentAlign.top` landed the tooltip behind the status bar. Switched to `ContentAlign.bottom` since the area below the cluster is empty space.
- **Bug-report sheet** — when the user tapped a text field, the keyboard pushed the form up but the photo + Send report buttons sat below the viewport. Wrapped the form's Column in `SingleChildScrollView` so the sheet can scroll under the keyboard inset.
- The `beforeFocus` callback now picks scroll alignment based on tooltip position: `0.85` (target near bottom) if the tooltip is `ContentAlign.top`, else `0.15` (target near top). Dynamic per-step rather than hardcoded.

### Bug list at handover

| short_id | title | status |
|---|---|---|
| `eeeb866f` | Room run survives api-alpha container restart | **open — deferred (large)** |

DB-wide unchanged this session: `open=1 / pending_review=0 / resolved=24 / wont_fix=2`. No new bug reports filed against the walkthrough during on-device verification — both surfaced issues (target overflow, keyboard) were fixed inline by Saiful's feedback.

---

## AT:R22  (2026-05-17)

Dense bug-fix + resilience session. 19 commits, **5 alpha promotions** (`alpha-2026-05-17-{1..5}`), test count 264 → **275**. Six TestFlight builds (`+9..+14`).

### Room resilience overhaul (`8a9f4da`, `b9050b9`, `7fca2c7`)

Three commits closing the resilience gaps the explore agent surfaced. The pipeline used to be SSE-coupled: client disconnect (phone sleep, LTE handoff, Cloudflare timeout) tore down the runner generator, partial transcript was persisted as CANCELLED, no verdict was reached.

- **Background task + queue (`8a9f4da`)** — runner now starts via `RoomRunner.start_run()`, which creates an `asyncio.Queue` keyed by `run_id`, fires `asyncio.create_task(_pump())`, and returns the `run_id` immediately. The SSE consumer reads from the queue via `runner.subscribe(run_id)`. Client disconnect kills the SSE consumer; the `_pump` keeps running to the verdict and the `on_complete` callback (journal write) always fires from the `finally` block. `X-Room-Run-Id` header carries the run_id to the client before any SSE body so a reconnecting client can `GET /v1/room/{run_id}` for the snapshot. Incremental transcript checkpoint after each agent. Dedup tier 1 (same user+ticker while running). Startup sweep marks abandoned `running` rows as `failed`. Journal retry on transient DB error. +5 tests.

- **Completed-run dedup (`b9050b9`)** — design-doc-style configurable lookback. New env knobs `ROOM_DEDUP_RUNNING_MINUTES=30` and `ROOM_DEDUP_COMPLETED_HOURS=24` (design doc default is 5 days; we start at 1 day so re-runs after the next-day open aren't blocked — raise via env to taste, 0 disables). Dedup tier 2 returns the prior verdict's `run_id` without spinning up a `_pump` — saves ~5 minutes of LLM time when the user double-taps "Convene the Room" or hits it again the same day. +2 tests.

- **Cached-run replay (`7fca2c7`)** — first version of tier-2 dedup made the client render "Room ended without a verdict" because `subscribe()` returned immediately on a cached `run_id` and the SSE emitted only the `done` event. Fix: `RoomRunner.is_active(run_id)` exposes whether there's a live queue; the API layer detects cached dedup, replays the persisted transcript as a compressed SSE stream (`started` → one `agent_token` + `agent_done` per agent → `phase: VERDICT` → `verdict`), and sets `X-Room-Cached: true` so a future client UI can show "cached analysis from earlier". +1 test.

### Five bug fixes (worked through one user-test cycle at a time)

| short_id | commit | summary |
|---|---|---|
| `698a0fe6` + `f7c4d7e0` | (resolved via the resilience work) | Validated on-device; flipped to resolved after the new background-task pipeline landed. |
| `6f9b5ebd` | `c9f682f` | Journal entry detail for sim_trade was dumping the raw Python-style dict. Added a typed render of horizon / status / opened-at / closed info / realised P&L / linked verdict_ref. |
| `ce7146c8` | `59acfe9` | Double-tap on the "Buy" button against the same verdict opened two identical trades. `SimEngine.submit()` now rejects when `(user_id, verdict_ref)` already has a trade (any status). Surfaces existing trade's short_id in the violation. `blocked_by` Literal gained `"duplicate_verdict"`. +2 tests. |
| `9b3a6c2f` | `1e69052` | Trade success was rendered with a slate800 snackbar — indistinguishable from the dark theme, drove the double-tap behind `ce7146c8`. Replaced with a green floating snackbar with check icon + haptic + 5s duration. Verdict card swaps the cyan "Open Trade Ticket" CTA for a green "✓ BUY 1 TSLA @ \$422.24" pill once a sim_trade exists for that verdict (watches `simNotifierProvider`). |
| `d5717660` | `a8ffafb` | When the user opens the trade ticket with no convened verdict, show a dismissible blue advisory: "Convene the Room first to get analysis from your 12 agents. Or proceed — this trade will be marked 'without advice'." Two buttons (Convene the Room / Proceed without). Journal detail shows `AI ADVICE: Without — manual trade` when `verdict_ref` is null. |

### Two features (`adc3d11`, `9814e63`)

- **ROOM + TRADE journal filter chips** (bug `1e645bca`) — promoted to positions 2/3 (right next to ALL) because users review those most. EN/AR/MS strings.
- **`feature_request` bug category** — Saiful's parallel ask. Backend `BugCategory` Literal extended; mobile dropdown picks it up. Retroactively recategorised `1e645bca`.
- **Live quote anchor in the trade ticket** (`9814e63`) — Saiful's quandary: "if I'm setting TP/SL, what do I base it on?" New `simQuoteDetail()` API method returns price + change% + source + market state. The trade ticket sheet debounces the ticker field (450ms), fetches the quote, renders a chip below the field (`$300.23  +1.20%  LIVE  CLOSED`), and pre-fills empty Stop / Target at -6% / +13% of the live price — same heuristic the Convene the Room Trader uses, so the anchor is consistent across both flows.

### Doc / infra: melehost LAN IP correction (`7c0f278`)

SSH config had `192.168.20.59` (correct) but every doc said `192.168.20.9` (wrong, never matched reality). Fixed across `CLAUDE.md`, `HANDOVER.md`, `infra/{cloudflared,local,systemd}/README.md`, `.claude/commands/promote-to-alpha.md`, `docs/10_delivery/promotion_protocol.md`, `docs/08_tech/hosting.md`. History.md left alone (snapshot of the past).

---

## AT:R21  (2026-05-15)

Focused session: 2 data commits + 1 handover, 1 alpha promotion (`alpha-2026-05-15-4`), test count 261 → **264**.

### Room-runner fix: per-agent LLM timeout + better journal entry (`eb1ef3c`)

Root cause of `698a0fe6` + `f7c4d7e0` (convene report not stored / room stuck waiting):

- **Timeout**: Added `_AGENT_LLM_TIMEOUT_S = 90.0`. `_speak_one_agent` and `_stream_pm_narration` now buffer via `asyncio.wait_for`; `TimeoutError` falls back to the scripted template so the run still finishes and produces a verdict instead of stalling indefinitely.  Live path now matches the existing PM-narration buffered pattern (all 12 agents: collect full response → restream via typewriter).
- **Journal**: Extracted `_build_journal_entry()` as a testable module-level function in `room.py`. Failed/aborted runs now write "Room on NVDA — failed · N of 12 agents completed — {error}" instead of "incomplete / no verdict". Replaced the silent `except: pass` with a structured `logger.warning`.
- +3 tests: hanging-gateway timeout fallback, completed-run journal entry, failed-run journal entry.
- Bugs `698a0fe6` + `f7c4d7e0` → `pending_review` on `main`. 6 AT:R20 `pending_review` bugs → `resolved`.

### ami-llm model rebrand (`e79c598`)

The on-prem vLLM host now serves under the model name `ami-llm` (same hardware — Gemma 4 31B, NVFP4 quantised). Updated everywhere: `backend/app/core/config.py`, `docker-compose.yml`, `infra/alpha.env`, `.env.example`, `infra/alpha.env.example`, `infra/systemd/ami-trade.env.example`, 8 occurrences in `test_llm_gateway.py`, `CLAUDE.md`, `HANDOVER.md`.

vLLM was already pre-configured to serve `ami-llm` as an alias — no server-side changes needed.

### LLM end-to-end test

Fired realistic user questions through 3 agents (Market Analyst, Fundamentals Analyst, Bear Researcher). All returned structured, numerically-grounded responses citing live yfinance fundamentals (NVDA P/E 48.1x, TSLA P/E 399x, net cash). Confirmed the AT:R20 fundamentals injection is working in production.

**Observation:** NVFP4 quantisation produces space-split tokens ("Consol idation", "NV DA"). Not a regression — it's been there since day one. Not blocking alpha but worth watching user feedback.

### Animations — documented and deferred

15 animation slots are already authored in lesson MDX files (all showing `AmiHexPlaceholder`). Two implementation paths discussed (Lottie files vs. custom Flutter `CustomPainter`). Decision deferred. See `memory/project_animations.md`.

### Bug list at handover

| short_id | title | status |
|---|---|---|
| `698a0fe6` | convene report not stored | pending_review (fix live on alpha-2026-05-15-4) |
| `f7c4d7e0` | screenshot (extension of 698a0fe6) | pending_review |
| `eeeb866f` | Room run survives container restart | open — deferred (large) |

DB-wide: `open=1 / pending_review=2 / resolved=16 / wont_fix=1`.

### Carry-overs for AT:R22

1. **T&C + Privacy Policy (A22 part 2)** — didn't start this session. Research is in `docs/09_compliance/legal_plan_ami_trade.md`. Needs (a) hosting at `agenticmarketintel.ai/legal/{privacy,terms}` and (b) lawyer review before App Store submission.
2. **Flip `698a0fe6` + `f7c4d7e0` → resolved** after on-device validation of the room timeout fix.
3. **`eeeb866f`** — room run survives container restart — still open/deferred (Redis-backed runner state or separate worker).
4. **External TestFlight launch** — Beta App Description + ~24h Apple review on first external build.
5. **Animation production** — deferred. See `memory/project_animations.md` for 15-slot design decision.
6. **A29 light-mode refactor** — 37 hardcoded `AmiColors.slate900`/`slate800` references. v1.0 work.
7. **Live fundamentals ticker extraction robustness** — watch bug reports for regex misfires in 1-on-1.
8. **Two sibling worktrees with unmerged docs** — `blissful-darwin-419097` (`docs(feedback): bug reporting pipeline spec + D-057 decision entry`) and `exciting-shtern-aad051` (`design(lessons): spec lessons landing page hex-cluster redesign`) — commits not in main. Need Saiful decision: merge to main or discard.

---

## AT:R20  (2026-05-15)

Bug-fix session that bled into substantial feature work. 18 commits, 3 alpha promotions (`alpha-2026-05-15-{1,2,3}`), one new schema migration (`b1c4e8d70007`), test count 220 → **261**.

### Bug fixes — two `/fix-bugs` worktrees

Saiful had 9 open bugs at the start. Triaged into 2 worktrees + 2 no-code closes:

| short_id | title | resolution |
|---|---|---|
| `a606436f` | fund agent report on AAPL (dup) | wont_fix — duplicate of `85469d8e` |
| `b6e8c505` | convene failed 502 | resolved — filed pre-AT:R19 SSE fix, no longer repros |
| `3ef7ca04` | Snackbar persists until backgrounded (`f0063d6`) | Capture `ScaffoldMessenger.of(context)` BEFORE `notifier.deleteEntry()` — the deleteEntry triggers a synchronous state rebuild that deactivates the itemBuilder context, so a later messenger lookup returns a detached state whose auto-dismiss timer never fires. |
| `278cbad8` | Stale `room_runs` cleanup (`49e88b0`) | Added an UPDATE to `trim_audit_tables()` in `app/services/audit.py` — any row stuck in `status='running'` for > 30 min flips to `aborted`. Runs nightly via the existing lifespan task. |
| `82cb07c6` | `kAppVersion` drifts from pubspec (`918111c`) | Added `package_info_plus ^9.0.1`; replaced the hand-maintained const with `appVersionProvider` (FutureProvider). Three call sites updated. |
| `85469d8e` | Fundamentals agent uses synthetic P/E (`4c59f61`, extended in `dcf3445`) | Room runner's `_profile_for_ticker` overlays real yfinance fundamentals on the synthetic baseline. Extended to all 12 agents in the 1-on-1 path via `app/services/fundamentals.py`. |
| `90441819` | Compliance chips need tap-to-explain (`a9b3540`) | Each of the 6 toggles is now an `InkWell`; tap → bottom sheet with plain-English explanation. |
| `2795baf2` | Agent response formatting (`b389b2f`) | Replaced `Text()` with `MarkdownBody` in room + 1-on-1. `flutter_markdown` → `flutter_markdown_plus`. |
| `eeeb866f` | Room run survives container restart | **deferred** — large; needs Redis-backed runner state or worker-process split. |

### Photo attachments in the in-app bug reporter (`c3ab51b`)

Alembic `b1c4e8d70007` adds `bug_reports.attachment_path` + `attachment_mime`. New `app/services/bug_attachments.py`. `POST /v1/feedback/bug` rewritten as `multipart/form-data`. Flutter: `image_picker ^1.2.2`, camera/library picker, 56px thumbnail preview. +18 tests.

### Honest follow-ups

- **`uv.lock` tracked** (`984b2a0`).
- **`scripts/install_iphone.sh` quieted** (`1385f0d`) — switched to `flutter devices --machine`.
- **`flutter_markdown` swap** (`1385f0d`) — maintained fork `flutter_markdown_plus`.
- **Legal research** (`6cd685a`) — `docs/09_compliance/legal_samples.md` + `docs/09_compliance/legal_plan_ami_trade.md`. Closes the writing-up half of A22.

---

## AT:R19  (2026-05-14)

Heavy session: 29 commits, 6 alpha promotions (`alpha-2026-05-14-4` through `-9`), one TestFlight upload (`0.1.0+4`), and a meaningful uplift to the bug-fix workflow.

### Journal — swipe-to-delete, search, soft-delete + Trash view

The journal got a full data-lifecycle treatment.

- **Soft delete + restore** (`09358d3`, `5ed72c0`). New `journal_entries.deleted_at` column (Alembic `f7d9b2e60005`); `JournalStore.soft_delete()`/`restore()`; `DELETE /v1/journal/{u}/entry/{e}` + `POST .../restore`. All reads filter `deleted_at IS NULL`. Entry is never destroyed.
- **iOS-standard swipe** (`dc16910`): `Dismissible` threshold raised from 0.4 → 0.7 so half-swipes don't auto-fire; `HapticFeedback.mediumImpact` on commit; 4s snackbar with **UNDO** that calls the restore endpoint.
- **Search** (`09358d3`): `GET /v1/journal/{u}?q=` ILIKE on `title + summary`; Flutter search bar with 400 ms debounce + clear (×) button.
- **Trash view** (`5ed72c0`): new screen reached via trash icon in the Journal header; `GET /v1/journal/{u}/trash` returns soft-deleted entries from the **last 30 days only** (`TRASH_VISIBLE_DAYS=30` in `journal_store.py`). Each card has a green RESTORE button. Older soft-deleted rows stay in the DB but never surface in-app. Footer caption: "Older entries are auto-hidden after 30 days."

### SSE middleware bug — chat + room re-fixed

The biggest "wait, it never worked" find of the session.

- **Root cause:** `HTTPAuditMiddleware` (added in AT:R16, `30fdca1`) replaced `request._receive` with a synthetic that always returned `http.request`. Starlette's `_CachedRequest.wrapped_receive` polls receive during the streaming response to detect client disconnect, expecting only `http.disconnect`. It got `http.request` and raised `RuntimeError: Unexpected message received: http.request` AFTER status 200 was already sent — every SSE route (1-on-1, room stream, coach) silently broken since AT:R16.
- **Fix** (`79e1571`): drop the `request._receive` replacement entirely. `await request.body()` already caches in `_body`; `_CachedRequest.wrapped_receive` reads from that cache. The synthetic was actively harmful, not helpful.

### Room run survives sleep / reconnect on wake

- New `started` `RoomEvent` kind, yielded first by `runner.run()`, carries the `run_id` immediately so clients can poll even if disconnected mid-stream.
- On `(CancelledError | GeneratorExit)` in `event_stream`, spawn `asyncio.create_task(_drain_to_completion(run_id))` — runner finishes server-side and persists journal + verdict.
- Flutter `RoomNotifier` captures `run_id` from `started`, on stream error polls `GET /v1/room/{id}` every 3s up to 90s. Amber `_ReconnectingBanner` UI ("Connection lost. The room is still running…") + `RoomState.reconnecting` flag.
- **Caveat (filed as bug `eeeb866f`):** only covers client disconnect. Container restart still kills the runner. Persisting runner state to Redis between agent steps is the proper fix; deferred until real testers see it.

### Trade auto-adds to ticker tape (`dc16910`)

`sim.submit` idempotently adds the traded ticker to `sim_watchlists` on success. Flutter's `simSubmit` refreshes the watchlist after a successful trade; the ticker-tape provider listens on a sorted-comma-joined projection of watchlist tickers and silent-refreshes when that key changes. No 120s wait.

### Concierge prompt rewrite (`dc16910`)

`content/agents/concierge.md` used to promise "Want me to open it?" — the app had no mechanism. Concierge now gives explicit navigation: *"Try **Lesson 12: Order Types**. You'll find it under **Lessons → Foundations**."* Hard rule baked into the prompt that it can't navigate for the user.

### Light/dark mode — honest fix (`dc16910`)

The toggle was a lie: 37 screens hardcode `AmiColors.slate900`/`slate800`. Removed the broken radio group from Settings → APPEARANCE; replaced with a single info row: "Dark theme — Alpha is dark-only. Light + Follow System land in v1.0." Coerces `ThemeMode.dark` on render. Full refactor (37 files → theme-aware colors) is v1.0 work.

### Workflow + scripts

- **`/fix-bugs`** (`99e6e0d`) — spawn `.claude/worktrees/bug-fix-<ts>`, claim bugs atomically via `bug_reports.assigned_branch + status='in_progress'`, triage tiny/small/medium/large, fix up to 3 per session, commit each as `fix(bug:<short-id>):`, flip to `pending_review` (humans confirm `resolved` on merge). Hands-off file list keeps high-conflict files (main.py, alembic, pubspec, compose) routed through human review.
- **`bug_reports.assigned_branch`** column (Alembic `a8e3c1b50006`). Status vocabulary: `open → in_progress → pending_review → resolved` (or `wont_fix`).
- **`/start-fresh` updated** (`aca28ee`) — pulls `bug_reports` at session start, surfaces open + pending_review counts + 10 latest titles in the plan, asks "bugs first or carry-over first?" with a directive-mapping table.
- **`scripts/build_testflight.sh`** (`c14ce2a`) — auto-bumps pubspec build number, `flutter build ipa --release --export-method=app-store`, uploads via `xcrun altool` with the App Store Connect API key.
- **`scripts/install_iphone.sh`** (`c14ce2a`) — release build + install on TESTING IPHONE 13 (or `$1` device). Pre-flight checks the device is connected.

### CLI TestFlight unblocked

The AT:R18 carry-over. Saiful signed Xcode into the Apple Developer account; one manual archive export through Organizer landed the Distribution cert + provisioning profile in keychain. After that, CLI build IPA works. App Store Connect API key generation needed a second go (first key was Developer role → 401; App Manager key `44VJ5WADL2` works). `0.1.0+4` uploaded via `scripts/build_testflight.sh` — first end-to-end CLI push.

### Website backend split

- Waitlist endpoint removed from the trade backend (`306ef73`). Files deleted: `backend/app/api/waitlist.py`, `schemas/waitlist.py`, `services/waitlist_store.py`. `WaitlistRow` model removed.
- `api-website` service added to `docker-compose.yml` (`b94adee`). Port 8001, separate `ami_website` DB, CORS for `agenticmarketintel.ai` + www. `promote-to-alpha` excludes `website/` from rsync (`65fec8e`); `website_api/` is shipped (api-website's source).

### Bug-report drift fix (handover scan)

`mobile/lib/state/feedback_providers.dart` had `kAppVersion = '0.1.0+2'` hardcoded. 13 user-filed bug reports tagged stale. Updated to `'0.1.0+4'`; filed `82cb07c6` for `package_info_plus` proper fix.

---

## What just landed (previous session — AT:R17)

Two commits, no backend changes, no alpha promotion. Pure Flutter session.

### Lessons tab — hex-cluster landing (`9555e8d`)

The flat 270-lesson scroll is gone. The Lessons tab is now two zones:

- **Zone A — slim progress bar.** Replaced the verbose `_ProgressCard` with a compact two-stat row: `"X / Y lessons"` + `"X / 12"` agents unlocked. "Next up" hint removed — the hex cluster handles discovery.
- **Zone B — 7-hex honeycomb.** Foundations (centre) + 6 surrounding tracks in a tight flat-top tessellation. Each hex: track label + doughnut progress ring (accent colour, 8dp stroke, slate700 background ring) + 15%-alpha tinted fill. Uses `FlatTopRegularHexagon` clipper — same geometry as the Floor home agent avatars.

New files:
- `mobile/lib/widgets/hex/track_hex_button.dart` — the tinted hex widget with `_DoughnutPainter` (CustomPainter arc via `dart:math`)
- `mobile/lib/screens/lessons/track_lessons_screen.dart` — per-track lesson list; lessons in catalogue order (three-tier in-progress → never-started → completed sort needs per-lesson API data, documented in `_sorted()` as a TODO)
- `mobile/lib/widgets/lessons/lesson_tile.dart` — extracted from `lessons_screen.dart` as a shared public widget so both screens can use it without duplication

Design spec that drove this: `docs/05_design/lessons_landing_redesign.md` (committed by the `exciting-shtern-aad051` worktree team as `ead7038`; that commit is on that branch, not on main).

**Release build gotcha surfaced this session:** `flutter build ios --release` without `--dart-define=AMI_API_URL_ALPHA=...` produces a build with an empty backend URL. The app defaults to prod mode → no traffic to Alpha. Always use:
```bash
flutter build ios --release \
  --dart-define=ALLOW_BACKEND_SWITCH=true \
  --dart-define=AMI_API_URL_ALPHA=https://api-alpha.agenticmarketintel.ai
```
`scripts/run_dev.sh` already does this for `flutter run`; it just wasn't being used for release builds. Permanently fixed: just remember to pass the flags (or add a `build_release.sh` script).

### Ticker tape — `e9e7f41` (from `exciting-shtern-aad051` worktree team)

Live Yahoo Finance scrolling ticker tape now sits below the bottom nav bar. Also fixed a pre-existing compile bug in `ticker_tape.dart`: `import 'dart:ui' show TextDirection` conflicted with `package:flutter/material.dart` in Flutter 3.41.x — on a full Dart kernel rebuild (triggered by dart-define changes), the compiler couldn't resolve `.ltr`/`.rtl` enum members. Fix: remove the `dart:ui` import; `TextDirection` is available via `flutter/material.dart`.

### iPhone state at handover

TESTING IPHONE 13 has **one** AMI Trade install:
- Release build `c8af8f4` with `AMI_API_URL=https://api-alpha.agenticmarketintel.ai` baked in
- Backend `alpha-2026-05-14-3` live; all AT:R18 fixes installed
- Onboarding completed + persisted (`ami_onboarding_done=true` in SharedPreferences) — next launch goes straight to Floor

### Carry-overs for AT:R19

- **`docs/05_design/lessons_landing_redesign.md` in a worktree** — spec is in `claude/exciting-shtern-aad051` (`ead7038`), not on main; merge or cherry-pick if next session needs it
- **Watchlist add shortcut** — users can only add tickers to the tape via Portfolio → `+` button; no shortcut from the tape itself. Consider long-press tape item → "Watch"
- **A22 privacy policy + ToS public URL** (legal — Saiful-external)
- **External TestFlight** — Beta App Description + ~24h Apple Beta App Review; Saiful-external
- **Animation production** — `AnimationRegistry` empty; pending Lottie art (external)
- **Sign Xcode into Apple ID + cache Distribution cert** — unblocks CLI `flutter build ipa`

---

## What just landed (this session — AT:R18)

12 commits (`c228633` → `c8af8f4`). Promotions: `alpha-2026-05-14-2` (features) + `alpha-2026-05-14-3` (ticker tape fix). Tests: 212 → 214.

### Per-lesson status API + three-tier sort (`c228633`)

New `GET /v1/lessons/progress/{user_id}/by_lesson` endpoint delegates to the existing `LessonsService.list_status()` (already had the data, just needed the route). Flutter: `LessonStatus` Dart model, `lessonStatusByLesson()` API call, `Map<String,LessonStatus>` added to `LessonsState`, `LessonTile` gains optional status badge (blue in-progress dot, green check + COMPLETED label). `TrackLessonsScreen._sortedWithStatus()` sorts: in-progress → never-started → completed within each track. +1 test (213 total).

**Gotcha:** original implementation used `Future.wait([4 futures])` — Dart erases mixed return types to `Object?`; the `as T` casts throw `TypeError` at runtime, caught silently → lessons screen blank. Fixed in `b028aea` by reverting to sequential `await` calls (typed, no casting).

### A29 light-mode register (`c228633`)

`AmiColorsLight` token set in `ami_theme.dart` (canvas `#F1F5F9`, panel white, AA-safe accent-text variants). `amiLightTheme()` factory. `themeModeProvider` (Riverpod, SharedPreferences-backed, defaults `ThemeMode.system`). `app.dart`: `theme: amiLightTheme(), darkTheme: amiTheme(), themeMode: provider`. Settings → APPEARANCE section with three radio options (Follow System / Always Dark / Always Light).

**Side-effect caught this session:** `ChoiceChip` in Flutter 3.41 M3 ignores color on `label: Text(style:...)` for state-aware rendering; fixed in `2224f73` by moving `color` to `labelStyle` on the chip widget itself (Settings drawdown, Journal filter, Journal outcome chips).

### Nightly audit retention trim (`e9b9dfc`)

`trim_audit_tables(days=90)` in `backend/app/services/audit.py` — batch-deletes rows older than 90 days from `llm_audit`, `http_audit`, `one_on_one_messages`. Wired into `main.py` as an `asyncio` background task (sleeps 24h, runs, logs counts). +1 test (214 total). Closes the unbounded-table TODO from AT:R16.

### Ticker tape fixed on device (`2baa3e6`)

The tape was blank because Flutter's direct Yahoo Finance v7 call had no `User-Agent` — Yahoo blocks it, returns empty, tape collapses. Two-layer fix:
1. Added iOS browser UA header to `YahooFinanceService` Dio client
2. `tickerTapeProvider._fetch()` falls back to `/v1/sim/quotes?symbols=...` if direct call returns empty
3. Backend: `Quote` NamedTuple gains `change_pct: float = 0.0` and `market_state: str = "CLOSED"` (extracted from Yahoo v8 chart API meta). New `GET /v1/sim/quotes` batch endpoint runs quotes in parallel via `ThreadPoolExecutor`.

**How to add tickers to the tape:** Portfolio tab → `+` icon → type symbol → Add. User's watchlist tickers lead the tape; US defaults fill to 10 minimum.

### Bug fixes batch

| Commit | Bug | Fix |
|---|---|---|
| `ebd077d` | Onboarding repeats every cold start | `main()` reads `ami_onboarding_done` from SharedPreferences; `AmiTradeApp(startOnFloor:)` sets `initialRoute` conditionally |
| `ebd077d` | "Restart onboarding" does nothing | `OnboardingNotifier.reset()` clears SharedPreferences flag + resets state to `notStarted`; floor button calls it before navigating |
| `0d1b9be` | Long-press version chip → nothing | `GoRouterState.of(context)` threw (app uses `MaterialApp` named routes, not GoRouter); replaced with `ModalRoute.of(context)?.settings.name` |
| `0d1b9be` | Version chip shows "0.1.0+1" | Bumped `kAppVersion` to `0.1.0+2` in `feedback_providers.dart` |
| `2224f73` | ChoiceChip selected text unreadable | Moved `color` from `label: Text(style:)` to `labelStyle:` on chip; adapts per selection state |
| `c8af8f4` | Gap between bottom nav and ticker tape | `BottomNavigationBar` internally absorbs `MediaQuery.padding.bottom`; fixed with `MediaQuery.removePadding(removeBottom:true)` |

### Alpha promotions

- `alpha-2026-05-14-2` — per-lesson API + light mode + audit trim (backend + Flutter)
- `alpha-2026-05-14-3` — ticker tape backend batch endpoint + Quote model

Flutter-only fixes after `-3` (lessons blank, onboarding, bug report, chip text, ticker gap) were installed directly on device (`xcrun devicectl`) — no new backend promotion needed.

---

## What just landed (this session — AT:R16)

Three meaty wins in one session: (1) the design-v2 changes from AT:R15 made it onto the iPhone via a release build + Alpha promotion; (2) the full A22-A28 TestFlight chain walked end-to-end for the first time — AMI Trade now installs on a phone with no Mac cable; (3) comprehensive audit logging shipped (HTTP / LLM / 1-on-1 chats persisted to Postgres). 3 new commits, 8 new tests (204 → 212), 2 new alpha tags.

### Design v2 → device + first promotion (`alpha-2026-05-13-8`)

The AT:R15 design v2 commits (`29cdcfb`, `94e50ea`) and the playbook fix (`e3bc47b`) were sitting on disk but not on the iPhone. Built `flutter build ios --release` (53.8s Xcode build), installed via `xcrun devicectl device install app --device 7178EB26-3444-5D6E-BB78-6454EB5D5455`. IBM Plex fonts, HexMeshOverlay on Floor, AccentCard daily-challenge, HexButton Convene CTA, HexChip status pills — all live on TESTING IPHONE 13. Then ran `/promote-to-alpha` end-to-end: 204 tests pass, flutter analyze clean, infra/alpha.env auto-sourced from main worktree (`e3bc47b` fix in action — the worktree-side promotion was the trigger), 4/4 critical env keys verified, container healthy on first poll. Smoke: vllm active, AAPL $295.55 source=yfinance.

### A22-A28 TestFlight chain — first end-to-end install (`dbba4a2`)

Marketing greenlit keeping the standard bottom nav (no hex nav swap). Saiful registered the App Store Connect record with bundle id `ai.agenticmarketintel.amiTrade`, capabilities Sign in with Apple + Push Notifications. First Xcode-Organizer Distribute → Upload surfaced two real blockers we now have permanent fixes for:

- **ITMS-90683: NSMicrophoneUsageDescription missing.** `audio_session.framework` references `requestRecordPermission` (transitive — not actually used by app code, but Apple's static binary scan flags it). Added `NSMicrophoneUsageDescription = "AMI Trade does not use the microphone."` to `mobile/ios/Runner/Info.plist`. Verified across the binary scan that this was the ONLY sensitive API ref in the build — no camera/photos/location/contacts hits.
- **Export compliance form on every first-time upload.** Added `ITSAppUsesNonExemptEncryption=false` so future uploads skip the form (HTTPS via URLSession + Keychain via flutter_secure_storage are exempt encryption per US export rules).

Build bumped `0.1.0+1 → 0.1.0+2` (Apple rejects duplicate CFBundleVersion). Second Organizer upload succeeded → Apple processing → Internal Testing group `AMI Team` created → Saiful added as tester → invite email → TestFlight app on iPhone → AMI Trade installed. **First time AMI Trade reached the test device without a USB cable.**

CLI `flutter build ipa --release --export-method app-store` still fails on `exportArchive` with `No Accounts` because xcodebuild doesn't see Xcode's signed-in Apple ID context. Workaround for now: build the archive via CLI, distribute via Xcode Organizer GUI. To unblock CLI-only releases, sign Xcode into the Apple ID + cache an `Apple Distribution` cert (one-time GUI action — see the section "If you want CLI builds" in `docs/08_tech/testflight.md` if/when we add it).

A22-A28 carry-overs that remain:
- **A22** — privacy policy + ToS public URL (legal review external)
- **A28** — tester onboarding kit (invite copy, feedback channel) — though the in-app bug reporter (AT:R15) already covers part of this

### Comprehensive audit logging — every HTTP, every LLM, every chat (`30fdca1`, `alpha-2026-05-14-1`)

Saiful's directive: *"i want to log everything right now since we are only just starting, we should know every thinng"*. Built three new Postgres tables (Alembic `d8a3e9f40004`) and wired them into every relevant code path:

- **`llm_audit`** — one row per `LLMGateway.stream_chat` call. Full system prompt, full messages JSON, full response_text (truncated at 200k chars), provider, tier, locale, latency_ms, agent_id, flow, user_id. Written in the gateway's `finally` block so errors and partial streams also persist (verified with a test that raises mid-stream — the `partial` response + `RuntimeError` both land).
- **`http_audit`** — one row per inbound HTTP request. Method, path, query, status, request_body (≤64KB), response_body (≤64KB, skipped for SSE), latency_ms, client_ip (X-Forwarded-For honored), user_id (parsed from path params). `/v1/health` is skipped at the middleware level (CF tunnel healthcheck noise — would otherwise dominate the table). Authorization / Cookie headers never reach the audit service.
- **`one_on_one_messages`** — durable record of every 1-on-1 chat turn keyed by `session_id + user_id + agent_id`. Closes the gap where `agent_runner.stream_one_on_one_message` streamed via SSE with no server-side record. User message persists BEFORE the LLM call (survives gateway failures), assistant message persists AFTER the stream completes.

Wired into every LLM call site by passing `audit_user_id` + `audit_agent_id` + `audit_flow` kwargs: `agent_runner` (1-on-1 + Concierge), `room_runner` (per-agent + PM narration), `coach_engine` (chat), `api/llm.translate`. Each call site labels its flow (`one_on_one` / `concierge_floor` / `room` / `room_pm` / `coach_chat` / `translate`) so psql queries can filter cleanly. `_RoomContext` gained a `user_id` field so the room flow can attribute audit rows.

All audit writes are best-effort: `record_*` catches every exception and logs via `logger.exception` — they cannot break the request that triggered them.

**Verified live on Alpha** post-`alpha-2026-05-14-1`:
- Three tables exist in `ami_trade` DB on melehost
- Two unrelated smoke calls (`/v1/llm/status` + `/v1/sim/quote/AAPL`) landed in `http_audit` with correct method/path/status/latency
- `POST /v1/llm/translate {"system_prompt": "Translate to French only...", "user_message": "The market is rising."}` returned `"Le marché est à la hausse."` from vllm — corresponding `llm_audit` row captured `provider=vllm, tier=cheap, flow=translate, locale=en, latency_ms=1205, response_text="Le marché est à la hausse."` verbatim.

Test doubles (`_FakeGateway` / `_CaptureGateway` in `test_concierge_live.py` + `test_room_runner.py`) updated to absorb the new `audit_*` kwargs via `**_audit`. Suite: 204 → 212 pass.

**Retention policy:** unbounded for now. Add a nightly trim job (eg. `DELETE WHERE created_at < now() - interval '90 days'`) or monthly partitioning before tester count grows past a few dozen — TODO is in `backend/app/services/audit.py`.

**Useful queries** (drop into a future `docs/08_tech/audit_queries.md` when there's reason):
```sql
-- every prompt Gemma received from user X today
SELECT created_at, agent_id, flow, left(response_text, 100)
FROM llm_audit WHERE user_id = '<uuid>' AND created_at > now() - interval '1 day'
ORDER BY created_at DESC;

-- replay a Concierge conversation
SELECT created_at, role, content FROM one_on_one_messages
WHERE session_id = '<uuid>' ORDER BY created_at;

-- slowest endpoints in the last hour
SELECT path, count(*), avg(latency_ms)::int AS avg_ms, max(latency_ms)
FROM http_audit WHERE created_at > now() - interval '1 hour'
GROUP BY path ORDER BY avg_ms DESC;
```

### iPhone state at handover

- **TESTING IPHONE 13** has TWO AMI Trade installs:
  1. Cabled release build from earlier in the session (29.4 MB, design v2 fully painted)
  2. TestFlight build 0.1.0+2 (the canonical "ships like a real app" path)
- Both point at `https://api-alpha.agenticmarketintel.ai` which is now serving `alpha-2026-05-14-1` with audit logging on every request. Every tap on either install lands rows in `http_audit` + `llm_audit` + `one_on_one_messages`.

### Carry-overs for AT:R17

- **A22 privacy policy + ToS public URL** (legal review — Saiful external)
- **A28 tester onboarding kit** — invite copy, feedback channel, bug-report template; in-app bug reporter covers part of this
- **External TestFlight** — needs Beta App Description + first ~24h Apple Beta App Review. Internal Testing covers Saiful + small inner circle today.
- **Animation production** — `AnimationRegistry` empty; pending Lottie art (external)
- **A29 light-mode register** — unblocked now that hex nav is off the table; sized 0.5 session in the project plan
- **Sign Xcode into Apple ID + cache Distribution cert** — would unblock pure-CLI `flutter build ipa` for future releases. Current workflow goes through Organizer GUI.
- **Audit retention trim job** — before tester count grows; today the tables are unbounded
- **Followups from AT:R13/15 that remain:** hex bottom-nav swap is now decisively OFF the table per marketing; iOS-only Android shelved per project plan; B-phase migration to GCP/Supabase still future.

### Alpha tags this session

- `alpha-2026-05-13-8` — Flutter design v2 / TestFlight build chain (backend unchanged from -7; this tag covers the docs + playbook auto-source fix landing on Alpha)
- `alpha-2026-05-14-1` — audit logging tables live; smoke-verified `http_audit` + `llm_audit` populated by real traffic

---

## What just landed (AT:R15)

Big session. The work order Saiful set covered four product carry-overs from AT:R13, then expanded into a full design-system v2 pass after marketing surfaced gaps in the hex language. 14 new commits, 28 new tests, one alpha tag.

### Carry-over batch (items 2–5)

- **Inline `<Term>` rendering — `a015b82`.** `<Term id="X"/>` MDX tags used to extract as standalone blocks, shredding paragraphs into vertical "prose / term / prose / term" lists. The backend now substitutes them to `{{term:X}}` inline tokens BEFORE block extraction; the Flutter markdown renderer's `_inline()` regex picks them up and emits a `WidgetSpan` with an inline `_InlineTermChip`. Tap still opens the same bottom sheet — refactored `term_block.dart` to expose `showTermSheet(context, termId, {locale})` as the single source of truth for the modal. +2 net tests.
- **Daily-challenge ingestion service — `37a84fd`.** 183 challenges sitting on disk (`content/daily_challenges/2026_06..2026_11.json`) now serve via `DailyChallengeService` (singleton + RLock + eager-load), with `GET /v1/daily_challenge/{today, by_date/YMD, by_id, all}`. `today()` resolves in `Asia/Kuala_Lumpur`. Flutter side: `DailyChallengeCard` (amber-accented) on the Floor tab; tap opens a full-screen attempt with A–D options + Submit + CORRECT/INCORRECT + explanation + related-lesson/agent links. 404 on `/today` is the expected state right now — corpus starts 2026-06-01; the card hides gracefully. +7 tests.
- **AI Coach Q&A retrieval — `1bf2136`.** 280 Q&A across 6 categories (ai_meta/beginner/intermediate/platform/psychology/scam) load into `AICoachService` with pre-computed token sets per entry. `GET /v1/ai_coach/{search?q, by_id, by_category, categories}`. The `top_hit(min_score=2)` helper wires into Concierge `scripted_reply` as a last-resort fallback BEFORE the generic "AMI is offline" message — so when the LLM is unreachable, a relevant short_answer surfaces instead. Flutter: `AICoachScreen` (Settings → Help → AI Coach) with debounced search, per-category-tinted hit tiles, bottom-sheet long-answer view with related-lesson/agent pills. +10 tests.
- **Earn-path gateway cap — `daaffb2`.** Most-referenced agents (market_analyst, fundamentals_analyst) had 71 callout lessons each post-content-drop — unlock was unreachable. New `UNLOCK_REQUIRED_PER_AGENT = 3` constant + `_gateway_lessons_for_agent(agent_id)` helper restricts the unlock requirement to the first N lessons (sorted by id) that callout the agent. Behaviour-identical for agents with ≤3 callouts. Flutter `_showLockedSheet` mirrors the cap so the locked-agent sheet shows the actual 3 gates instead of the full 70+ enrichment set. +1 test.

### Bug reporter (item 7 / AT:R13 carry-over from a parallel worktree)

- **In-app bug reporter — `4ef1a4f`.** Imported the design from worktree `claude/blissful-darwin-419097` (`docs/08_tech/bug_reporting.md`) and shipped Alpha tier end-to-end. `POST /v1/feedback/bug` writes to `bug_reports` (Alembic `c7f2a1d30003`); user_id nullable so anon sessions can file before claim; scaffold token Bearer extraction. Flutter: `BugReportSheet` modal triggered by long-pressing the "AMI Trade v0.1.0+1" chip at the bottom of Settings (shake-gesture trigger held — would need new package). Category chip picker + title + steps + spinner + error state. +9 tests.

### Design v2 pass (after marketing audit)

Saiful fetched the updated AMI AI Design System bundle (the v2 archive at the `api.anthropic.com/v1/design/h/…` share URL). Audit surfaced gaps vs the prior in-repo mount — most important: **we'd been authoring against Inter + JetBrainsMono, which the v2 README explicitly names as fallbacks NOT to author against. Canonical is IBM Plex Sans + IBM Plex Mono.**

- **IBM Plex fonts — `29cdcfb`.** Added `google_fonts: ^6.2.1` to pubspec. `AmiTypography.*` converted from `static const TextStyle` to `static final` built from `GoogleFonts.ibmPlexSans()` / `ibmPlexMono()`. Inter + JetBrainsMono still bundled for cold-paint fallback. Three const-Text call sites in `dev_preview_screen.dart` + theme.dart adjusted accordingly. h1 weight 700 → 800; labelMono letter-spacing 1.3 → 1.8 (~0.15em per spec).
- **Color tokens to spec — `29cdcfb`.** `slate800` #1E293B → #111827 (`--panel-bg-solid`); `slate700` #334155 → #374151 (`--border-color`); `hexPurple` #A855F7 → #8B5CF6 (`--accent-purple`); `textHigh` white → #F3F4F6; `textMed` → #94A3B8 (`--text-muted`); `textLow` → #64748B (`--text-dim`); added `hexBlue600`, `cardBg`, `cardBgAlt`, `hexGlow`.
- **New widgets — `29cdcfb`:**
  - `lib/widgets/hex/accent_card.dart` — glass panel + **2px colored top-stripe** (mobile-spec variant; desktop is 3px). Optional `onTap` with Material InkWell ripple. `ClipRRect` so the stripe sits flush with the rounded corners.
  - `lib/widgets/hex/hex_mesh_overlay.dart` — 3% opacity SVG (`assets/hex_mesh.svg`, already in pubspec) tiled via `flutter_svg`. `IgnorePointer` so taps fall through.
- **HexChip tinted variant — `94e50ea`.** `HexChipVariant` enum: `filled` (existing default), `outlined` (existing), `tinted` (new — 14%-alpha accent fill + colored text + no border). New `showDot: bool` for LIVE/MOCK/OFFLINE/WARN status pills. Backwards-compat via `HexChip.legacy(filled: bool)` factory.

### Where the design changes land on screen

| Surface | Change |
|---|---|
| **Whole app** | Type system flips to IBM Plex on first launch (after one-time `google_fonts` cache; Inter/JetBrains paints during the wait) |
| **Floor tab** | `HexMeshOverlay` sits behind the scaffold; Convene the Room CTA swapped from `ElevatedButton.icon` → existing `HexButton(color: hexGreen)` — flat-top hex pill |
| **Daily-challenge card** | Now `AccentCard(accent: hexAmber)` with 2px top-stripe instead of full 1px border. Submit button on the attempt screen also `HexButton` |
| **AI Coach (Settings → Help)** | Hit tiles now `AccentCard` per-category tinted (red=scam, pink=psychology, purple=ai_meta, cyan=platform, green=beginner, blue=default). Category labels on tiles + answer sheet are now `HexChip(tinted)` hex-clipped pills |
| **Portfolio header** | LIVE/MOCK quote-source pill now `HexChip(tinted, showDot)` with the hex silhouette — same green/amber semantic |

### `/promote-to-alpha` auto-source — `e3bc47b`

The promotion playbook used to fail step 4 ("infra/alpha.env missing") when run from a worktree, because the canonical env file is gitignored and lives only in the main worktree. Fixed: when the local file is missing, the playbook now `cp`s it from the main worktree path discovered via `git worktree list --porcelain` (with `cut -d' ' -f2-` so the space in `/Volumes/Extreme Pro/...` doesn't truncate). Behaviour-preserving from the main worktree.

### A29 — light-mode register (documented, not built)

`docs/10_delivery/project_plan.md` gained `A29` in Stream 4 Product polish. Sized 0.5 session. Intent per the spec README: *"bright/outdoor mobile conditions triggered by the ambient light sensor — not as a default visual register."* Held pending marketing's read on the hex bottom-nav swap (a separate v2 item Saiful is discussing with marketing — when that direction is set, the two land together).

### Alpha tag this session

- `alpha-2026-05-13-7` — batch deploy after the 5 carry-overs (bug reporter + Term + daily-challenge + AI Coach + earn-path cap). Cloudflare tunnel needed a manual restart post-rsync (cached the old api-alpha container IP after `docker compose up -d --build`) — surfaced as a 502 on first smoke; resolved by `docker compose restart cloudflared`. Add to the `/promote-to-alpha` playbook as a known recovery if it happens again.

The design v2 commits (`29cdcfb`, `94e50ea`) and the playbook fix (`e3bc47b`) are **NOT yet promoted to Alpha** — they're Flutter / docs / playbook changes; the backend hasn't moved. Both iOS installs on TESTING IPHONE 13 are pointing at the live `alpha-2026-05-13-7` backend.

### iPhone state

Release build with all of this installed on **TESTING IPHONE 13** (UDID `7178EB26-3444-5D6E-BB78-6454EB5D5455`). Bundle ID `ai.agenticmarketintel.amiTrade`. App points at `https://api-alpha.agenticmarketintel.ai`.

### Carry-overs (deferred / blocked)

- **Animation production** — `AnimationRegistry` built, empty. Blocked on Lottie art (Saiful-external).
- **TestFlight (A22-A28)** — blocked on App Store Connect provisioning (Saiful-external).
- **A29 light-mode register** — documented; held pending marketing alignment on the hex bottom-nav swap.
- **Hex bottom-nav swap** — open with marketing. If they want it, that's the v2 mobile UI kit's signature element (5 hex pills, center "Ask AMI" purple→blue with glow). Significant rework — touches every screen because the nav shape changes.
- **Shake gesture trigger** for bug reporter — current trigger is long-press only. Adding shake would need the `shake` Flutter package; deliberately deferred to keep the dep stack lean. Long-press alone is sufficient for Alpha-tier feedback volumes.

---

## What just landed (AT:R13)

Four commits. The LIVE / MOCK pill was lying to users (Yahoo's been
429-ing for at least 28 hours but the API reported the stack name
`fallback(cache(yahoo)->mock_walk)` which contains "yahoo" — Flutter's
`isLivePrice` substring-matched and showed LIVE). Fixed structurally:
each provider now returns `Quote(price, source)` with the leaf name,
and the snapshot aggregates honestly. **Plus** /promote-to-alpha was
exercised for the first time end-to-end and surfaced two real playbook
bugs.

### Truthful `price_source` — `83d32a7`

- New `Quote = NamedTuple("Quote", [price, source])` in `app/services/market_data.py`.
- Each provider exposes `quote(ticker) -> Quote | None`. Mock returns `source="mock_walk"`, Yahoo returns `source="yahoo"`, `CachingProvider` preserves the inner's source on hit, `FallbackProvider` forwards the leg that actually served.
- `SimEngine.current_quote()` + `SimEngine.aggregate_source(tickers)` — snapshot reports "yahoo" only when 100% of marks came from Yahoo; any fall-through to mock downgrades to "mock_walk".
- `/v1/sim/quote/{ticker}` reports the per-call leaf source. `/v1/sim/portfolio` reports the aggregate.
- Flutter: zero changes. `SimPortfolio.isLivePrice` already substring-matches "yahoo"; with the backend honest the pill flips correctly.
- Tests: +7 (Quote source per provider, cache hit preservation, fallback leg forwarding, aggregate downgrade on mixed marks, sim_engine wiring).

### Lesson-id rot — `af4d054`

Seven `test_lessons_service.py` tests had been failing silently on `main` since some renumbering pass: `LEGACY_MARKET_ORDER_LESSON = "283_market_order_vs_limit"` pointed at the FILENAME slug, but `LessonsService` keys by frontmatter `id` (still `"004_market_order_vs_limit"`). One-character fix unblocks the promotion playbook (which aborts on any pytest red). Test suite: 155 → 162 passed.

### First real /promote-to-alpha — surfaced two playbook bugs — `f46c901`

- **rsync wiped melehost's `.env`.** Playbook claimed it was "excluded by default rsync filter" — that's not how rsync works. Mac side had a near-empty `.env` (only `CF_TUNNEL_TOKEN` on the canonical root); rsync overwrote melehost's populated one and alpha dropped to `active_provider=mock` for ~3 minutes until I restored `VLLM_BASE_URL` / `VLLM_MODEL` / `USE_REAL_MARKET_DATA` from the documented values in CLAUDE.md. Added explicit `--exclude='.env'` + a post-rsync grep check + `--exclude='Silent_Scout/'`.
- **`alembic upgrade head` failed with "No 'script_location' key".** `backend/Dockerfile` only COPYs `app/` and `tests/` — not `alembic.ini` or the `alembic/` directory. Fixed by adding both COPYs.
- Both bugs were dormant: every prior deploy was direct rsync without using the slash command, so the playbook gaps never bit anyone until today.
- After the Dockerfile fix, alembic itself works but `init_schema()` runs `create_all()` at boot, so a fresh DB has every table but no `alembic_version` row → `upgrade head` errors with `DuplicateTable`. Worked around today with `alembic stamp head` once. Followup task spawned to reconcile the boot order (option 2 — self-stamp from `init_schema()` — is probably the right answer).

### Alpha tags

- `alpha-2026-05-13-1` — the truthful-source deploy (before playbook fixes; `.env` got wiped here)
- `alpha-2026-05-13-2` — re-deploy on the fixed playbook (`.env` survives; alembic in image)

Public smoke (post-deploy):

```
GET /v1/llm/status        → active_provider=vllm, has_real_provider=true
GET /v1/sim/quote/AAPL    → {"price": 294.8,  "source": "yahoo"}     ← LIVE for real
GET /v1/sim/quote/NVDA    → {"price": 348.28, "source": "mock_walk"} ← honestly MOCK
GET /v1/sim/quote/MSFT    → {"price": 113.58, "source": "mock_walk"} ← honestly MOCK
```

Yahoo's 429-ing is per-ticker (or stochastic) — AAPL came back live mid-session but NVDA/MSFT didn't. The fix means the iPhone pill now reports each ticker's honest source rather than a blanket lie. Aggregate logic ensures the portfolio-level pill stays MOCK whenever any holding falls through.

### What this means for next time

- `/promote-to-alpha` is now battle-tested. Future runs should be smooth modulo the alembic boot-order followup.
- The promotion's edge case of "the canonical Mac `.env` overwrites melehost's" can't happen again — explicit `--exclude='.env'` plus the verification grep are baked in.

### What's still NOT done (carry-overs)

- yfinance migration. Today's fix is honesty about Yahoo's failures; it doesn't make Yahoo more reliable. Migrating from the keyless `query1.finance.yahoo.com/v8/finance/chart/...` to `yfinance` (which has anti-rate-limit logic) is a separate session. Without it, alpha will show mostly MOCK most of the time — honest but not impressive.
- i18n string-extraction sweep (A11 scaffold landed; ~1 session of grinding through every `Text(...)` call).
- Animation production — `AnimationRegistry` is empty; pending art.
- The init_schema + alembic boot-order collision (followup task spawned this session).
- Backend `Dockerfile` CMD uses `--reload` — dev flag, should be `--workers N` for the alpha host. Touched in the followup task.

### Mac-canonical per-env files (`513d851`)

Followup to the `.env` wipe incident. Mac now holds the source of truth at `infra/<env>.env` (gitignored); promotion `scp`s it to the target host's `~/ami_trade/.env`. The host's `.env` is treated as derivative — never edited in-place.

- `infra/alpha.env` (gitignored) — seeded from melehost; canonical for alpha.
- `infra/{alpha,beta,prod}.env.example` (committed) — shape, no values.
- `infra/README.md` — model + recovery + rotation.
- `/promote-to-alpha` step 4 now does `scp infra/alpha.env melehost:~/ami_trade/.env` with an abort-if-missing guard and post-`scp` grep verification of the four critical keys.
- `/promote-to-beta` + `/promote-to-prod` design docs updated to inherit the pattern (the .env file feeds GCP Secret Manager at B8, separate projects so prod ≠ beta).

End-to-end smoke-tested today — scp lands, keys verify, container healthy, `active_provider=vllm`.

### magical-edison-18bf91 content drop merged (`03c55f4` + `ab71957`)

Imported the parallel content pass from worktree `claude/magical-edison-18bf91`. **No code change.** 285 file changes, all under `content/` + `docs/`. Two thematic commits.

- **Lessons corpus: 13 → 270.** New 001-077 (M1-M12 foundations), 100-279 (Expansion / deep-dive companions), and the original 13 reparented to 280-292 ("Legacy bonus", still on `track: foundations`). Frontmatter ids now match filenames again — `LEGACY_MARKET_ORDER_LESSON` updated to `"283_market_order_vs_limit"` in the test (was `"004_*"` post-AT:R13 fix; the content pass realigned them).
- **Regulatory reframe is now load-bearing across the corpus.** AMI is a training simulator, not a licensed advisor. CLAUDE.md decision-pointer was already aligned; this pass threads the framing through every M12 lesson (072-077, 268-279) and scrubs `ai_meta.json`'s 50 entries. Linguistic substitutions are consistent corpus-wide ("AMI recommends X" → "AMI's training output suggests X"; "act on the Verdict in your real brokerage" → "use the training scenario to practice evaluating multi-agent analyst output").
- **New content surfaces** (static JSON files, no service yet):
  - `content/daily_challenges/2026_06..2026_11.json` — 183 entries, six monthly batches.
  - `content/ai_coach/{ai_meta,platform,psychology,scam}.json` — 4 new files, 280 entries total across 6 categories.
  - `content/glossary/terms.en.json` — 188 entries, 13 categories. i18n design: `terms.<locale>.json`, id stable across locales.
- **342 inline `<Term id="..."/>` references** across 258 lessons. The MDX parser passes them through unchanged today (only Quiz / ChatWith / Animation get extracted). Flutter renders them as raw text until the `<Term>` component lands. First-mention-only per lesson per term.
- **Verification:** 163 unit tests pass (was 162 + 1 skipped; the skip flipped to pass with the bigger lesson corpus). `lessons_loaded count=270` on boot. Catalogue: 7 tracks (foundations 16, fundamentals_analysis 66, technical_analysis 45, news_macro 19, sentiment_behaviour 10, risk_portfolio 16, edge_process 98).

### Follow-up engineering work flagged by the content drop

Three tasks spawned (chips in the UI):

1. **Backend `GlossaryService`** — load `content/glossary/terms.*.json`, expose `/v1/glossary/{locale}` + `/v1/glossary/{locale}/{id}`. Mirror `LessonsService` shape. Locale fallback en → 404.
2. **`<Term>` MDX component** — backend `_TERM_RE` extractor + Flutter `TermRegistry` analogous to `AnimationRegistry`. Tap-to-show-definition. Bundled-asset fallback until the backend route lands.
3. **`<Animation>` extractor finish** — the `_ANIMATION_RE` regex exists in `lessons_service.py` but isn't actually emitted as a block in the body walker (only Quiz + ChatWith get fully extracted). Finish the wiring so the Flutter `AnimationRegistry` (already built at A21) starts receiving data.

Also still on the deck:

- LessonMeta surfacing `module` + `difficulty` fields end-to-end. A20 reads them; check whether they make it into the API response shape and the Flutter `LessonMeta` model.
- Daily-challenge + AI-Coach ingestion services — Alpha A17 / Beta work; content is sitting on disk.

---

## What just landed (AT:R13 extended pass — iPhone build, content mount, yfinance, Glossary, i18n)

After the content drop merged, the iPhone build round surfaced a real gap and the session kept going through four substantial follow-ups. Final tally: 71 commits, 176 tests, five alpha tags.

### The iPhone build round

- `flutter run` from terminal couldn't trigger the Xcode debug-session attach — known macOS automation-permission issue. Worked around with `xcrun devicectl device install app --device <UDID> mobile/build/ios/iphoneos/Runner.app` after a clean `flutter run --release` build (60.6s Xcode build). The .app on the phone is verifiably release-grade (App.framework is a 7.0M Mach-O native binary — AOT-compiled, not the tiny Dart kernel snapshot debug builds ship).
- The build pointed at `https://api-alpha.agenticmarketintel.ai` and worked standalone (cable disconnected fine post-install).

### content/ never reached the container (`88aa0da`)

Quiet bug since the api-alpha service first ran on melehost: `LessonsService._reload()` was logging `lessons_loaded count=0` on every boot because the Dockerfile only COPYs `app` + `tests` and `docker-compose.yml` only mounted `./backend/app` + `./backend/tests`. No content/, no lessons. Path resolution from inside the container is `/content/lessons` (NOT `/app/content`), so:

```yaml
- ./content:/content:ro
```

Live verification post-deploy: `/v1/lessons` → 270 lessons across 7 tracks. Same fix unblocks the GlossaryService + daily_challenges + ai_coach data automatically — they read from the same mount.

### `init_schema()` self-stamps Alembic (`1f30025`)

Resolves the AT:R13 `DuplicateTable` carry-over. On a fresh DB, `init_schema()` now detects a missing `alembic_version` table and stamps Alembic to `head` after `create_all()`. So `alembic upgrade head` in `/promote-to-alpha` step 6 is a clean no-op rather than an explosion. Best-effort wrapper — never breaks boot if alembic.ini is missing (slim test image).

### YfinanceProvider — LIVE prices flow (`c838082`)

The keyless `query1.finance.yahoo.com/v8/finance/chart/...` path was 429ing persistently. `yfinance` handles the UA rotation + cookie/crumb session Yahoo started requiring in 2024, plus backoff. Drop-in replacement at the head of the stack:

```
FallbackProvider(
  primary=CachingProvider(YfinanceProvider, ttl=60s),   # new
  secondary=MockWalkProvider,
)
```

Smoke against alpha post-deploy: AAPL $294.80, NVDA $220.78, MSFT $407.77 — all `source: "yfinance"`. Flutter's `isLivePrice` switched from substring `"yahoo"` to negative check (`!= mock_walk && != unavailable`) so adding a new live provider at Beta won't require a Flutter rebuild to flip the pill.

Tradeoff: pulls pandas + numpy (~100MB image bloat). Irrelevant on melehost; will inform the Beta cold-start cutover where we may swap to a paid provider with a slimmer client.

### GlossaryService + `<Term>` MDX component (`ee80fa7` + `30c6014`)

Built by a subagent in an isolated worktree, merged clean (fast-forward).

- **Backend**: `app/services/glossary_service.py` (singleton, RLock, locale fallback en→404), `app/api/glossary.py` (`GET /v1/glossary/{locale}` + `GET /v1/glossary/{locale}/{id}`), `app/schemas/glossary.py` (GlossaryEntry / Category / Catalogue).
- **MDX parser** extended in `lessons_service.py` — `<Term id="..."/>` now emits a typed block (kind=term). Same pass added test coverage for the existing `<Animation>` block, which closes another open chip.
- **Flutter**: `TermRegistry` bundled-asset reader at `mobile/assets/glossary/terms.en.json` (copied at build time from `content/glossary/terms.en.json`). `Term` widget renders an inline chip; tap → bottom sheet with definition + see-also + related lessons. Unknown id falls back to bold plain text.
- **Discovery**: actual `<Term>` tag count in the corpus is **672 across 270 lessons** (not the 342 quoted in the content-drop handover — the magical-edison-18bf91 report undercounted). 15 unique term ids referenced, all in the `platform` category. Every reference resolves; zero broken refs.
- **Known cosmetic**: Term blocks render at the same nesting level as markdown paragraphs, so a sentence with two `<Term>` tags renders as 5 separate vertical blocks (prose / term / prose / term / prose). Reads like a list, not inline prose. Followup: inline tokenization in the markdown view via a `{{term:id}}` substitution token — quick fix if it looks bad on device.
- **8 new backend tests** (load, lookup, unknown, category grouping, locale fallback variants).

### i18n sweep + Gemma 4 auto-translation (`9a7f1c3`, `bea81f3`, `240e524`, merged `aaca100`)

Built by a second subagent in parallel.

- **Pass 1 — string extraction** (`9a7f1c3`): every user-visible literal `Text(...)` / label / tooltip / button across `mobile/lib/screens/**` + `mobile/lib/widgets/**` wrapped in `AppLocalizations.of(context)!.<key>`. `app_en.arb` grew from ~20 keys to **256** translatable keys + ~47 `@key` description blocks. 13+ screens touched. Dev-preview screen, agent-tagline-data, log keys, asset paths, SharedPreferences keys all deliberately skipped.
- **Pass 2 — Gemma 4 translation pipeline** (`bea81f3`):
  - `backend/app/api/llm.py` — new `POST /v1/llm/translate` route: thin non-streaming pass-through to the LLM gateway. Inherits the `vllm > anthropic > mock` preference, lands on Gemma 4 31B on Alpha.
  - `scripts/translate_arb.py` — CLI that batches keys, prompts Gemma to emit a JSON object preserving `{placeholder}` syntax + brand "AMI", validates per-batch, retries once, exits non-zero on unresolved batches. Flags `--locales`, `--batch-size`, `--overwrite`, `--dry-run`. Preserves manually-translated entries.
  - **Cloudflare Tunnel timeout discovery**: batch=30 → 70s+ per call → 502s. Batch=10 fits comfortably under ~75s timeout. Documented in the script's batch-size flag default.
- **Pass 3 — docs** (`240e524`): `mobile/lib/l10n/README.md` covers add-a-string workflow, script invocation, RTL notes (Directionality handles flip; ticker symbols stay LTR inside Arabic sentences; `$<digits>` renders LTR mid-RTL — move concat-sensitive substrings into `{placeholder}` slots).
- **Merge conflict** on `mobile/lib/screens/lessons/lesson_reader_screen.dart` — Agent A had converted it to ConsumerStatefulWidget (for the TermRegistry async load in initState) while Agent B added i18n wraps to its build method. Resolved by keeping Agent A's stateful structure and applying Agent B's `l = AppLocalizations.of(context)` + wrapped literals inside it. flutter analyze clean post-resolution.

### Five alpha tags this session

- `alpha-2026-05-13-1` — truthful price_source (Quote.source = leaf provider)
- `alpha-2026-05-13-2` — playbook bug fixes (rsync .env exclusion, alembic in Docker image)
- `alpha-2026-05-13-3` — content/ mounted, 270 lessons + glossary surfaced
- `alpha-2026-05-13-4` — alembic self-stamp + yfinance LIVE prices
- `alpha-2026-05-13-5` — Glossary endpoints + Term blocks + /v1/llm/translate + i18n

### What's testable on iPhone right now

| Surface | Behaviour |
|---|---|
| Lessons tab | 270 lessons, 7 tracks. `<Term>` taps open a definition sheet for the 15 platform terms referenced (672 inline tags). `<Animation>` placeholders render. |
| Floor / Concierge | Live Gemma 4 wired (A2). |
| Portfolio | LIVE/MOCK pill is honest. Watchlist supports any Yahoo-quotable ticker. AAPL/NVDA/MSFT all return LIVE via yfinance. |
| Settings → Language | Locale picker triggers `app_ar.arb` / `app_ms.arb` (Gemma 4 auto-translated). RTL flips automatically for AR. |
| Settings → Developer | alpha / beta / prod toggle. Beta + Prod show "not in this build" (URLs unset). |
| Sign In | Apple-button (synthetic JWT) + email magic-link (dev returns the code in the response). |

### Open follow-ups (revised)

Closed this session: GlossaryService chip, `<Term>` chip, `<Animation>` extractor chip (covered by Agent A's pass), init_schema/alembic carry-over.

Still open:
- **Inline `<Term>` rendering** — current block-level renders Term tags as vertical-list-style breaks. Tokenize into prose stream for tighter inline reading.
- **Animation production** — `AnimationRegistry` is built but empty; pending Lottie art.
- **Daily-challenge ingestion service** — 183 challenges on disk, no backend service or Flutter surface yet.
- **AI Coach Q&A retrieval** — 280 Q&A on disk; could ship a substring/keyword retriever today for canned answers when LLM unavailable; full embedding pipeline is Beta-era.
- **TestFlight distribution** (A22-A28) — depends on App Store Connect, Saiful-external.
- **Earn Path coverage extension** — A2 wires unlock against a smaller subset of "required" lessons; the new 257 lessons aren't routed into agent unlocks yet.

---

## What just landed (AT:R11 — Alpha live + promotion protocol + Mac pure editor)

(Previously the lead section — moved down now that AT:R13 has landed.)

## What just landed (A7 — Cloudflare Tunnel wiring)

Saiful provisioned the named tunnel + Access policy in the Cloudflare
dashboard and surfaced the connector token. This commit wires the
connector into both delivery paths (docker compose for dev / ad-hoc,
systemd for the prod host) and bakes the security runbook into the
repo so the token stays out of git.

- `infra/cloudflared/ami-trade-tunnel.service` — systemd unit. Runs
  the connector as a dedicated `cloudflared` user, depends on
  `ami-trade-backend.service`, reads the token from
  `/etc/ami-trade-tunnel.env` (mode 0600). Restart-on-failure with 5s
  backoff.
- `infra/cloudflared/ami-trade-tunnel.env.example` — token slot
  (empty in git on purpose).
- `infra/cloudflared/README.md` — install runbook (token-mode tunnel
  setup, dashboard pointers, Access policy shape, CORS / Flutter
  build interaction with A25).
- `docker-compose.yml` — cloudflared service comment now references
  the systemd path; `depends_on` uses `service_healthy` (the backend
  has a healthcheck since W8) so the tunnel only starts after the
  backend is actually answering.
- `.env.example` (worktree) — the placeholder slot now carries an
  explicit "never paste real token here, this file is committed" note
  plus a pointer to the dashboard + rotation runbook.
- `infra/systemd/ami-trade.env.example` — new `AMI_PUBLIC_API_URL`
  slot so prod operators have the public hostname consolidated next
  to `CORS_ORIGINS`.

**Heads-up for Saiful:** the real token is currently in the working
tree of the root checkout's `.env.example` (uncommitted on `main`).
It's not in git history yet, so no rotation is required — but move
it to `.env` (gitignored) before you ever `git commit .env.example`.
Token belongs in `.env` locally and `/etc/ami-trade-tunnel.env` on
the prod host; the `.env.example` slot stays empty in git forever.

This unblocks A22-A28 — the public hostname is now the URL that
goes into `--dart-define=AMI_API_URL=...` on the TestFlight build.

---

## What just landed (this session — AT:R11)

Eleven commits on top of the previous handover. The headline: **Alpha is live, public, and serving from melehost**. Promotion protocol + slash commands in place. The Mac stopped running services entirely.

### Alpha is live (A7 — Cloudflare Tunnel)

- **Public hostname**: `https://api-alpha.agenticmarketintel.ai` — backed by token-mode Cloudflare Tunnel, dashboard-managed ingress.
- **Connector**: cloudflared container on melehost (Connector ID `406f3d06-28a6-44ca-bc2e-4dc065c60149`), 4 healthy connections to jed03 + mrs06 edges. Latency ~220ms cold from outside the LAN.
- **Stack on melehost**: `ami_postgres` + `ami_redis` + `ami_api_alpha` + `ami_tunnel`. All healthy under `~/ami_trade/` (rsync'd from Mac). vLLM Gemma 4 reachable via LAN at `192.168.20.74:8000`; Yahoo market data active.
- **Token hygiene**: `CF_TUNNEL_TOKEN` lives in `.env` (gitignored). `.env.example` slot stays empty in git forever. Working-tree-only on the Mac root checkout; no commit history exposure. Move to `/etc/ami-trade-tunnel.env` for the systemd path when that lands.
- **CF dashboard ingress**: Service URL = `http://api-alpha:8000` (Compose service-DNS, both containers in `ami-trade-local_default` network).
- **Compose service renamed** `backend` → `api-alpha` (matches public hostname end-to-end). Container = `ami_api_alpha`.
- **`extra_hosts: host.docker.internal:host-gateway`** added to cloudflared service so the same dashboard ingress works on Docker Engine (melehost) as on Docker Desktop — Engine doesn't provide that name for free.

Detailed runbook + decommission-at-Beta plan in [`infra/cloudflared/README.md`](infra/cloudflared/README.md).

### Mac is pure editor — no Mac backend / DB

Stopped + removed the Mac uvicorn (PID 38964) and `ami_postgres` container. Mac volumes kept (cheap, reversible). New rule: **the Mac runs zero services**. Every change ships to Alpha via [`/promote-to-alpha`](.claude/commands/promote-to-alpha.md) to be exercised.

- Backend unit tests on the Mac still work (`pytest backend/tests/unit/ -q` uses sqlite tempfile via the conftest fixture).
- `scripts/run_dev.sh` rewritten — pure `flutter run` pointing at the Alpha hostname, no backend startup. Bakes alpha/beta/prod URLs via dart-define so the Settings → Developer toggle is live.
- Memory updated ([feedback_mac_is_pure_editor.md](/Users/saiful/.claude/projects/-Volumes-Extreme-Pro-AMI-MarketApp/memory/feedback_mac_is_pure_editor.md)) so future sessions don't quietly resurrect the Mac backend path.

### Three backend modes (Flutter) — Alpha / Beta / Prod

Pre-MVP TestFlight builds bake all three hostnames and expose a Settings → Developer radio. MVP / App Store builds compile that out entirely (`ALLOW_BACKEND_SWITCH=false`); only `AMI_API_URL_PROD` reaches the binary. A tester upgrading from TestFlight to App Store gets force-clamped to prod on first launch and any stored override is wiped from SharedPreferences.

Full design + build commands in [`docs/08_tech/backend_modes.md`](docs/08_tech/backend_modes.md).

### Promotion protocol — Mac → Alpha → Beta → Prod

[`docs/10_delivery/promotion_protocol.md`](docs/10_delivery/promotion_protocol.md) is the design doc. Mac is canonical (commits originate); melehost / GCP Beta / GCP Prod are derivative. Tags walk the chain: `alpha-YYYY-MM-DD-N` → `beta-*` → `prod-*` (Saiful's `Asia/Kuala_Lumpur` timezone). Never skip a layer; tags are permanent; rollback re-deploys the previous tag with the failing tag preserved.

Slash commands under [`.claude/commands/`](.claude/commands/):
- `/promote-to-alpha`, `/rollback-alpha` — **live today**.
- `/promote-to-beta`, `/rollback-beta` — stubs; unblock at B1-B8.
- `/promote-to-prod`, `/rollback-prod` — stubs; unblock at MVP-phase items.

### Docs aligned with the new model

- [`docs/08_tech/hosting.md`](docs/08_tech/hosting.md) — top-of-file "melehost — the Alpha host" section (Ubuntu Linux server, specs, LAN IP, role). Other docs link here instead of restating.
- [`infra/cloudflared/README.md`](infra/cloudflared/README.md), [`infra/systemd/README.md`](infra/systemd/README.md), [`infra/local/README.md`](infra/local/README.md), [`docker-compose.yml`](docker-compose.yml) — all explicit about Ubuntu + Docker Engine vs Docker Desktop. No more "Saiful's server" hand-wave.
- The compose backend env now passes `VLLM_BASE_URL` / `VLLM_MODEL` / `USE_REAL_MARKET_DATA` through from `.env` (was missing — fresh-composed backends used to silently fall back to mock provider).

### Test state

Backend: **152 passed, 0 failed**. The two pre-existing `test_lessons_service` failures (stale lesson IDs vs W17/W18 renumbering) got pinned to a stable `LEGACY_MARKET_ORDER_LESSON = "283_market_order_vs_limit"` handle. flutter analyze still clean across touched files.

---

## What just landed (previous session — A2, A20, A19, A21, A18, A8, A9, A10, A11)

Saiful granted full autonomy through MVP — "build it all part by part". Eight Alpha items shipped across Streams 1, 2, 3, 4 of the project plan. The full Stream-4 product polish lane is done; Stream 2 hardening is done modulo the Saiful-blocked items (A3 / A6 / A7); Stream 3 lands its first chunk (A11 scaffold). 152 unit tests passing, flutter analyze clean on every touched file.

### Stream 1 — finish the AMI surface
- **A2** (`68475ce`) — Concierge → AMI wired on the Floor tab. Live path uses a new `concierge_prompts.py` that enriches the base prompt with the user's recent Journal entries, unlocked agents, lesson catalogue, and mandate snapshot — so the LLM names real lesson IDs and routes to real agents instead of speculating. Scripted fallback (when `has_real_provider()` is False) uses a keyword classifier rather than MockProvider's canned text. Deterministic onboarding state machine in `concierge_engine.py` stays untouched.
- 9 new tests in `test_concierge_live.py`.

### Stream 4 — product polish
- **A20** (`a1dcf90`) — Lesson loader reads `module` + `difficulty` frontmatter (W18 fields). Legacy lessons default `module=0` and `difficulty=level`. Backend + Flutter `LessonMeta` both gain the fields. **Also fixed** the 2 pre-existing `test_lessons_service` failures (W17/W18 added trader callouts to lessons 014/015/016; tests now isolate via a helper).
- **A19** (`3c97ee0`) — Lesson UX skip-to-quiz. Each lesson tile shows two buttons — **READ** (green) and **QUIZ ONLY** (amber). Quiz-only mode hides markdown + chat_with blocks and counts toward agent unlocks identically. Wrong-answer explanations are the teaching surface for skippers.
- **A21** (`29a1aa8`) — `<Animation name="..." />` MDX component. Backend parses it; Flutter `AnimationRegistry` resolves names to Lottie assets (empty map for now — none bundled). Missing names render `AmiHexPlaceholder` so lessons referencing not-yet-bundled animations still ship. Lottie playback deferred until the first asset lands.
- **A18** (`433f38f`) — User watchlist (the "see *their* tickers" loop). New `sim_watchlists` table with Alembic migration. Backend routes `GET / POST / DELETE /v1/watchlist/{user_id}`. Tickers are free-form (anything market_data can quote), idempotent on add, upper-cased, ordered by added_at DESC. Flutter portfolio screen has a new **WATCHLIST** section above HOLDINGS — each row shows ticker + notes + live quote, tap opens a sheet with **Open Trade Ticket / Ask the Market Analyst / Convene the Room / Remove**. Pull-to-refresh now refreshes both the portfolio and the watchlist. 7 new tests.

### Stream 2 — on-prem hardening
- **A8 + A9** (`d69045e`) — Production launch + Postgres backups. Files under `infra/systemd/` (unit, env file template, logrotate, README) and `infra/backups/` (pg-backup.sh, service, timer, README). Replaces the dev-only `nohup uvicorn &` pattern. Restart-on-failure with 30s graceful shutdown for in-flight SSE. Nightly pg_dump at 02:30 UTC, 14-day retention, optional offsite rsync/rclone, **restore drill** documented (the only thing that matters — run on install and quarterly).
- **A10** (`89183aa`) — Sentry SDK on both sides. Backend `app/core/observability.py` reads `SENTRY_DSN`; idempotent; no DSN → fully offline. Flutter `main.dart` wraps `runApp` in `SentryFlutter.init` when `--dart-define=SENTRY_DSN=...` is passed. Both scrub Authorization / Cookie / x-api-key headers in `beforeSend`. `traces_sample_rate=0.1` in prod, 0 elsewhere.

### Stream 3 — i18n
- **A11** (`54b0936`) — i18n scaffold. `mobile/l10n.yaml` (gen-l10n config), ARB files for `en` (populated for the surfaces touched recently — tab labels, A18 watchlist, A19 buttons, A11 language picker), `ar` and `ms` (placeholders; missing keys fall back to English). `lib/i18n/locale_provider.dart` persists the override via SharedPreferences; null = follow system. `lib/app.dart` wires `localizationsDelegates` + `supportedLocales`. Settings → **LANGUAGE** section gives the user a radio picker. RTL kicks in automatically for `ar`. The full string-extraction sweep across every screen is deliberately out of scope — Saiful's plan calls i18n "structural plumbing now, full sweep later" and partial translation is fine for Alpha.

### Pre-existing W17/W18 content not yet committed

> **ABSORBED — this generation pass landed in the magical-edison-18bf91 content drop at AT:R13 end.** As of commit `03c55f4` the corpus is 270 lessons, IDs aligned with filenames again, including a fully-built `014_position_sizing_basics` etc. The "pre-existing untracked" framing below is from before that drop.

`content/lessons/014_..` through `162_..` and `100_..` through `170_..` were generated by the W18 authoring prompt but never committed (still untracked on disk). They DO get loaded by the running lessons service (count=82+ on this branch's disk state), which is why A20's frontmatter parsing matters now and why the earn-path tests needed the isolation helper. Decide whether to commit them in a future content-only pass; A20 is forward-compatible either way.

---

## What just landed (A2 — Concierge → AMI, post-onboarding Floor tab)

The 13th agent stops being canned. When the user opens the Concierge from the Floor tab (1-on-1 chat), the LLM now answers and routes against a real picture of the user's situation — recent Journal entries, currently unlocked agents, the lesson catalogue, mandate snapshot. When no real provider is registered, a deterministic scripted reply takes over (it does NOT fall back to MockProvider's "I'm offline" line) and routes the user to the right tab/agent/lesson based on keyword intent.

The deterministic onboarding state machine in `concierge_engine.py` is untouched — the welcome interview / mandate readback stays scripted for reproducibility. A2 is strictly the post-onboarding Concierge on the Floor.

### How it's wired

- **New `backend/app/services/concierge_prompts.py`**:
  - `build_concierge_messages()` — composes the live system prompt. Starts from `build_agent_prompt(CONCIERGE, mandate, user_id)` (base + mandate overlay + user-coaching overlay + safety floor), then appends a "FLOOR CONCIERGE CONTEXT" block listing the mandate one-liner, the user's last ~6 Journal entries, the set of unlocked agents, the lesson catalogue (ID + title + track + level), and a "be specific — name the lesson ID, name the agent, do not invent" instruction.
  - `scripted_reply()` — keyword-intent classifier with five buckets (lesson / journal / mandate / Convene-the-Room / trading-advice). Names a real lesson ID, a real agent, or a real journal title from the supplied context so the fallback still feels useful instead of generic.
  - `load_concierge_context()` — best-effort puller for journal + activations + lesson catalogue; swallows DB exceptions so a data-layer hiccup never kills the chat stream.
- **`agent_runner.py` Concierge branch** — `stream_one_on_one_message` detects `agent_id == CONCIERGE` and dispatches to `_stream_concierge`, which:
  1. Loads the context via `load_concierge_context`.
  2. If `gateway.has_real_provider()` is False, yields the `scripted_reply` text in one chunk and returns. The LLM gateway is **not** called — same pattern A1 introduced for the Room.
  3. Otherwise, builds the enriched prompt and streams the LLM response. Any exception or empty response falls back to the scripted reply so the Floor never hangs.
- **Tier policy unchanged.** Concierge tier is picked via `pick_tier(plan, AgentId.CONCIERGE)` — Floor Manager drops to `mid` per W12's per-(plan, agent) override; everyone else gets the default for their plan.
- **Onboarding API untouched.** `/v1/onboarding/*` still routes through the deterministic `concierge_engine` state machine.

### Tests (+9, 142 total — see test-suite note above)

`backend/tests/unit/test_concierge_live.py`:

- `test_concierge_routes_to_gateway_when_real_provider_present` — fake live gateway records exactly one call; system prompt contains "FLOOR CONCIERGE CONTEXT" and the mandate snapshot.
- `test_concierge_prompt_carries_lesson_catalogue` — at least one real lesson appears under the "Available lessons" block.
- `test_concierge_prompt_lists_unlocked_agents_for_real_user` — grants the Market Analyst via `lessons_service.grant_activation`, asserts "Market Analyst" appears in the system prompt.
- `test_concierge_uses_scripted_fallback_when_no_real_provider` — fake gateway with `has_real_provider() = False` is **never called**; output contains the mandate snapshot from `scripted_reply`.
- `test_scripted_reply_routes_lesson_intent` — "teach me about risk" → names a real lesson ID.
- `test_scripted_reply_routes_to_unlocked_agent` — "can I talk to the market analyst?" → names Market Analyst.
- `test_scripted_reply_refuses_trading_advice` — "should I buy NVDA?" → routes to Market Analyst / Convene the Room without echoing or speculating.
- `test_scripted_reply_summarises_journal` — recent entries surface ticker tags in the reply.
- `test_build_concierge_messages_includes_all_context_blocks` — direct unit on the prompt builder: journal, unlocked agents, lesson catalogue, mandate, and base Concierge role all land in the system prompt; user message is the last `messages` entry.

### Live verification path (on-prem vLLM Gemma 4 31B)

`POST /v1/agents/one_on_one/start` with `agent_id=concierge` then `POST /v1/agents/one_on_one/message` streams real Concierge prose that references actual lesson IDs and the user's actual journal. Mock fallback exercised by running with `VLLM_BASE_URL` unset — Concierge still routes the user usefully (mandate-aware, lesson-aware) without ever calling the gateway.

---

## What just landed (A1 — Convene the Room → AMI wiring)

The marquee flow stops being scripted. Every agent in a Room run now speaks via the LLM gateway when a real provider is registered (today: on-prem vLLM Gemma 4). The deterministic safety floor is untouched — it still produces the verdict ACTION (APPROVE/REJECT); the LLM only writes the prose rationale around that fixed result.

### How it's wired

- **New `backend/app/services/room_prompts.py`** — composes the per-agent system prompt for a Room turn. Combines the agent's base prompt (already includes mandate overlay + safety floor where applicable) with a CONVENE THE ROOM addition: phase label, compact ticker fact-sheet (price/P/E/growth/RSI/range/catalysts/macro/sentiment) sourced from the existing `_profile_for_ticker()`, the running transcript so each agent builds on the debate, a per-agent length budget, and a "speak directly, no preamble" instruction.
- **Rewritten `room_runner.py::run()`** — flips between live and scripted via `gateway.has_real_provider()`. Each non-PM agent's tokens stream out as SSE `agent_token` events at the LLM's own pacing.
- **PM is special** — `_assemble_verdict()` runs the deterministic safety floor FIRST. Then `_stream_pm_narration` asks the LLM for prose with `pm_predetermined_action="APPROVE"` / `REJECT (violations)` in the system prompt and an explicit "do NOT contradict this action" instruction. The buffered PM text is restreamed at typewriter cadence so the UI pacing stays uniform.
- **Every LLM path catches all exceptions** and falls back to the scripted `_TEMPLATES`. The demo never breaks if vLLM is unreachable.
- **Per-agent tier via `pick_tier(plan, agent_id)`**. vLLM collapses all tiers to `gemma-4-31b-it-nvfp4` today; routing is correct for the future cloud-LLM cutover (Beta).

### Tests (+3, 133 total)

- `test_room_uses_gateway_for_every_agent_when_live` — fake gateway records 12 calls (one per agent), transcript grows by 12, verdict still APPROVE (deterministic).
- `test_room_safety_floor_still_fires_under_live_gateway` — liberal "APPROVE everything" LLM reply does NOT override the floor; halal user on a non-halal ticker still gets REJECT with `overridden_from_llm=True`.
- `test_room_transcript_grows_for_subsequent_agents` — first agent sees `(You are first to speak.)` marker; PM sees every prior agent's contribution in its prompt.

### Live verification (against on-prem vLLM Gemma 4 31B)

`POST /v1/room/stream` on NVDA with `risk_score=3` streams real per-agent analysis. Fundamentals Analyst opened with:

> *"NVDA maintains an exceptional quality-of-earnings profile, though valuation now demands flawless execution of the Blackwell ramp to justify a 50.7 P/E. Balance Sheet: Net cash of $38.9B provides significant optionality for R&D or buybacks, though capital expenditures are scaling to support next-gen architecture. Profitability: FCF margins of 22% are robust..."*

Real Blackwell architecture reference, real cash position, real FCF margin. The scripted demo is gone from the marquee flow.

---

## What just landed (W17 / W18 / W18b — project plan + curriculum + authoring)

Multiple planning artefacts landed this session before A1.

- **`docs/10_delivery/project_plan.md`** — three-phase plan (Alpha → Beta → MVP). Saiful's framing: Alpha = everything on-prem (full feature shakedown including i18n/TTS/push/daily briefing + TestFlight distribution). Beta = ONLY GCP + Supabase + cloud LLM migration; same feature surface, nothing user-visible changes. MVP = App Store + Play Store + payments + marketing.
- **`docs/04_education/curriculum_map.md`** — canonical Level 1–8 / Module 1–12 / ~77 lesson IDs. Each lesson tagged with `level`, `module`, `difficulty`, `track` (for agent-unlock routing), and `agent_callouts`. Existing 13 lessons re-mapped lazily. Animations are OPTIONAL — only ~15 specific lessons are flagged as "good animation candidates".
- **`content/_authoring/lesson_authoring_prompt.md`** — three self-contained prompts for any AI tool: (1) lesson MDX generator with the 7-part lesson template (short explanation → real-world example → "the trap" → ChatWith → quiz → action task → takeaway), (2) daily-challenge bank (one month per batch, 5 challenge types from `docs/04_education/daily_and_streaks.md`), (3) AI Coach Q&A Library (categorised knowledge base for the Concierge to retrieve from). Tickers are illustrative not exclusive (user watchlists are how the product actually serves the "their tickers" need). Every lesson MUST have a multi-choice quiz; users can skip the lesson body and jump to the quiz.

### Plan summary (current)

| Phase | Claude effort | Saiful external |
|---|---|---|
| **Alpha** (on-prem + TestFlight) | ~9.75 sessions | Resend, Cloudflare Tunnel, Apple cap × 2, Azure/ElevenLabs, OneSignal, App Store Connect, translators, legal stub |
| **Beta** (GCP + Supabase + cloud LLM) | ~5 sessions | GCP, Supabase, cloud LLM provider, DNS |
| **MVP** (public launch) | ~3 sessions | App Store / Play / RevenueCat / legal / marketing / analytics |

Alpha picked up A1 this session. Remaining Alpha items split into 5 streams (full table in `docs/10_delivery/project_plan.md`):

| Stream | Items | Status |
|---|---|---|
| 1 — Finish the AMI surface | A1, A2 | A1 ✓, A2 pending |
| 2 — Real auth + on-prem hardening | A3–A10 | unstarted (A3/A7 blocked on Saiful) |
| 3 — i18n / TTS / push / daily briefing | A11–A17 | unstarted |
| 4 — Product polish (watchlist, skip-to-quiz, lesson loader, animation registry) | A18–A21 | unstarted |
| 5 — Ship to offsite testers | A22–A28 | unstarted (App Store Connect blocked on Saiful) |

---

## What just landed (W13 — on-prem vLLM Gemma 4 — app is live)

Saiful pointed at his LAN-hosted vLLM box at `192.168.20.74:8000`
serving `gemma-4-31b-it-nvfp4` (Gemma 4 31B, NVFP4 quantized, 262k
context). Wired it through the existing gateway abstraction; the iPhone
build from W11 is now talking to a real LLM end-to-end.

### New `VLLMProvider` in `llm_gateway.py`

OpenAI-compatible streaming client (`/v1/chat/completions`, SSE with
`choices[0].delta.content` deltas). Same `LLMProvider` interface as the
Anthropic + Mock providers — drop-in. Optional bearer auth via
`VLLM_API_KEY` for hardened deployments; LAN-private servers leave it
unset.

### Gateway selection: vllm > anthropic > mock

`LLMGateway._PREFERENCE = ("vllm", "anthropic", "mock")`. Whichever is
registered first wins. Set `VLLM_BASE_URL` → vLLM serves every call.
Unset it → Anthropic if `ANTHROPIC_API_KEY` is set, otherwise mock.
`/v1/llm/status` now reports `active_provider: "vllm"` and every tier
in `tier_to_model` resolves to the single hosted model (vLLM hosts one
model at a time; the tier dimension collapses).

### Config additions

```ini
VLLM_BASE_URL=http://192.168.20.74:8000
VLLM_MODEL=gemma-4-31b-it-nvfp4
VLLM_API_KEY=          # optional
USE_REAL_MARKET_DATA=true
```

Lives in `app/core/config.py` + documented in `.env.example`.

### Verified end-to-end

Backend restarted under W13 worktree code with env vars set:

```
$ curl localhost:8000/v1/llm/status
{"providers_registered":["mock","vllm"],"active_provider":"vllm",
 "has_real_provider":true,
 "tier_to_model":{"cheap":"gemma-4-31b-it-nvfp4",
                  "mid":"gemma-4-31b-it-nvfp4",
                  "premium":"gemma-4-31b-it-nvfp4"}}
```

Then a 1-on-1 stream against `market_analyst`:

> "Daily/Weekly timeframe: Bullish trend continuation following a
>  successful retest of the 50-day SMA.
>  Setup: Long on dip to $115 (support), target $140, stop-loss $105
>  (approx 2.5:1 R:R)."

Structured analyst response, streamed token-by-token from the iPhone's
backend through tier_policy → vLLM → Gemma 4 → SSE back to the client.
Mock text is gone.

### Tests (+7 → 130 total)

- `test_vllm_provider_parses_openai_deltas` — happy path; verifies the system prompt is placed inside `messages` and the model name + max_tokens + stream flag land in the body.
- `test_vllm_provider_error_yields_inline_error` — HTTP 503 yields a sentinel error chunk.
- `test_vllm_provider_tolerates_empty_delta_chunks` — empty `delta` between content tokens doesn't crash.
- `test_vllm_provider_sends_bearer_when_api_key_set` / `test_vllm_provider_omits_bearer_without_api_key` — Authorization header behavior.
- `test_gateway_prefers_vllm_when_both_keys_set` — preference order is vllm > anthropic > mock.
- `test_gateway_status_with_only_vllm` — status surface when only vLLM is configured.

### Running stack (this terminal)

| Component | Where | How |
|---|---|---|
| Backend | PID 67193 | `uvicorn app.main:app --host 0.0.0.0 --port 8000` from the W13 worktree, env: `DATABASE_URL`, `USE_REAL_MARKET_DATA=true`, `VLLM_BASE_URL`, `VLLM_MODEL` |
| Postgres | docker `ami_postgres` | host port 5434 |
| vLLM | `192.168.20.74:8000` | on-prem, gemma-4-31b-it-nvfp4 |
| iPhone | TESTING IPHONE 13 | release build of W11 code, pointed at `http://192.168.20.9:8000` |

### Logs

```bash
# Current path (AT:R11+): live logs from melehost
ssh melehost "docker logs ami_api_alpha --tail 50 -f"

# At W13 this was `tail -f /tmp/ami-backend.log` on the Mac —
# retired when Mac stopped running services.
```

---

## What just landed (W12 — tier_policy refactor)

W9 shipped a `AGENT_MIN_TIER` map inside `llm_gateway.py` with a
"never-downgrade-from-plan" rule. Saiful asked for tighter semantics:
per-(plan, agent) decisions, in a dedicated module, not buried in the
gateway. Behaviour change: **Floor-Pass PM drops from `premium` → `mid`**,
**Floor-Manager Concierge drops from `premium` → `mid`**.

### New: `app/services/tier_policy.py`

Single source of truth for which model tier each agent runs at, given the
user's plan. Used by 1-on-1, Coach, and Room.

```python
pick_tier(Plan.FLOOR_PASS, AgentId.PORTFOLIO_MANAGER)  # → "mid"
pick_tier(Plan.TRADER,     AgentId.PORTFOLIO_MANAGER)  # → "premium"
pick_tier(Plan.FLOOR_MANAGER, AgentId.CONCIERGE)       # → "mid"
pick_tier(Plan.FLOOR_MANAGER, AgentId.TRADER)          # → "premium"
pick_tier(Plan.TRIAL_TRADER,  AgentId.BULL_RESEARCHER) # → "mid"  (default)
```

Special-cased agents: Concierge, Portfolio Manager, Trader. Everyone
else uses `_DEFAULT_BY_PLAN`.

### Call-site swaps

- **`agent_runner.py`** — local `PLAN_TO_TIER` dict gone; tier comes from `pick_tier(plan, agent_id)` in `stream_one_on_one_message`.
- **`coach_engine.py`** — local `PLAN_TO_TIER` + `_plan_tier` helper gone; both `stream_chat` paths (live chat and propose-as-JSON) call `pick_tier(_plan_from_mandate(mandate), agent_id)`.
- **`room_runner.py`** — run-level tier now `pick_tier(plan, AgentId.PORTFOLIO_MANAGER)` so the PM's tier drives credit cost (the PM is the lineup's max-tier agent). `from app.services.tier_policy import pick_tier` is imported for when Room is wired through the gateway later.
- **`llm_gateway.py`** — `AGENT_MIN_TIER`, `resolve_tier`, and the `_TIER_RANK` helper are gone. The gateway owns the tier→model alias map and provider selection; routing decisions live in `tier_policy.py`. `GET /v1/llm/status` no longer surfaces `agent_min_tier` (it was redundant once routing moved out).

### Tests

- **New `test_tier_policy.py`** — 11 parametrized cases covering Concierge, PM, Trader, default plan paths.
- **Trimmed `test_llm_gateway.py`** — removed 6 obsolete tier-routing cases. Kept AnthropicProvider SSE parsing + gateway status tests.
- Suite: **123 passed** (was 118; +11 / −6 net).

---

## What just landed (W11 — Flutter LIVE/MOCK quote-source pill)

W10's `price_source` field now reaches the iPhone. The Portfolio screen
header pulls a small green-dot "LIVE" pill when Yahoo quotes are active,
amber-dot "MOCK" when on the deterministic walk — so the demo speaks
honestly about what it's pricing.

- **Backend**: `PortfolioSnapshot` (`backend/app/api/sim.py`) gains a `price_source: str` field surfaced from `sim.price_source`. Default `"mock_walk"` keeps the response shape backward-compatible.
- **Flutter model**: `SimPortfolio` (`mobile/lib/models/sim.dart`) parses `price_source`, exposes `isLivePrice` (true when the source name contains `yahoo`).
- **Flutter UI**: `_QuoteSourcePill` widget in `mobile/lib/screens/sim/portfolio_screen.dart` — colored dot + monospace label next to TOTAL VALUE.
- 118 unit tests still pass; `flutter analyze` clean on the touched files.

This closes the W10 loop end-to-end: real prices in the backend, an honest indicator in the app. **Saiful: the iPhone still has the W3 build — needs a redeploy to see W4–W11.**

---

## What just landed (W10 — real market data via Yahoo)

The Sim Trading engine no longer lies — when `USE_REAL_MARKET_DATA=true`
quotes come from Yahoo's keyless public chart endpoint, with the legacy
random walk as fallback for unknown tickers and network errors.

### Market data — pluggable provider stack

- **`backend/app/services/market_data.py`** — new module owning all pricing.
  - `MarketDataProvider` protocol — `get_price(ticker) -> float | None`.
  - `MockWalkProvider` — the old deterministic random walk (now lives here, not on `SimEngine`).
  - `YahooQuoteProvider` — calls `https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d` via the already-vendored `httpx`. Browser User-Agent header (Yahoo blocks the default httpx UA). Catches every error — `ConnectError`, non-200, malformed JSON, missing fields — and returns `None`.
  - `CachingProvider(inner, ttl_seconds=60)` — per-ticker TTL cache. Doesn't cache `None` (so a transient failure doesn't pin a missing price for 60s).
  - `FallbackProvider(primary, secondary)` — tries primary; falls through to secondary on `None`.
  - `get_market_data_provider()` returns the configured stack:
    - `USE_REAL_MARKET_DATA=true` → `FallbackProvider(CachingProvider(YahooQuoteProvider), MockWalkProvider)`
    - default → bare `MockWalkProvider`
  - `set_market_data_provider(p)` test hook.

### SimEngine refactor

- **`backend/app/services/sim_engine.py`** — no longer owns pricing logic. Takes a `MarketDataProvider` (defaults to `get_market_data_provider()`). New `sim.price_source` exposes the active provider name; `/v1/sim/quote/{ticker}` now returns `{"ticker", "price", "source"}` so the iPhone client can show "live" vs "mock".
- **`backend/tests/conftest.py`** — autouse fixture pins a fresh `MockWalkProvider` for every test so the suite stays deterministic regardless of `USE_REAL_MARKET_DATA`.

### Live verification

Hit Yahoo with the actual stack (env-gated, from the venv):

```
USE_REAL_MARKET_DATA=true python -c "from app.services.market_data import get_market_data_provider; ..."
stack: fallback(cache(yahoo)->mock_walk)
  AAPL: 190.09
  NVDA: 270.97
  BRK-B: 239.19
  NOTREAL: 200.44   ← fell through to mock as designed
```

### Tests (+15 → 118 total)

- `tests/unit/test_market_data.py` — 15 cases:
  - `MockWalkProvider`: stable + independent walks per ticker.
  - `CachingProvider`: hit, miss-on-different-ticker, never-cache-None, targeted invalidate.
  - `FallbackProvider`: primary hit, secondary fallback, both-fail.
  - `YahooQuoteProvider` (mocked httpx): success parse, non-200, network error, empty result, missing price field.
  - Full real-stack assembly: Yahoo 500 → cache pass-through → mock fires.
- All `test_sim_engine.py` tests still pass (one minor test update: the internal walk lives on the provider now, not on `SimEngine`).

### How to flip it on

Already on in Alpha — `USE_REAL_MARKET_DATA=true` is in melehost's
`~/ami_trade/.env`, set during the AT:R11 wrap. For reference, the
toggle today is:

```bash
# On melehost — edit env + recreate the api-alpha container
ssh melehost "cd ~/ami_trade && \
    grep -q USE_REAL_MARKET_DATA .env || echo 'USE_REAL_MARKET_DATA=true' >> .env && \
    docker compose --profile tunnel up -d api-alpha"

# Verify through the public tunnel
curl -s https://api-alpha.agenticmarketintel.ai/v1/sim/quote/AAPL
# → {"ticker":"AAPL","price":..., "source":"fallback(cache(yahoo)->mock_walk)"}
# NB: AT:R13 (commit 83d32a7) switched `source` to the leaf provider
# name — "yahoo" or "mock_walk", not the stack name above.
```

The original W10 dev path was `scripts/run_dev.sh backend` on the
Mac (Mac-local uvicorn talking to Mac-local Postgres on port 5434).
That dev pattern was retired at AT:R11 when we made the Mac
pure-editor — see the AT:R11 section near the top of this doc and
`docs/10_delivery/promotion_protocol.md`.

---

## What just landed (W9 — LLM-swap prep + cleanup)

The Anthropic key was NOT available this session, so option A's runtime
validation was deferred. What WAS done is everything that makes "drop
key → live" a single env-var change with zero code touches.

### LLM gateway — live-swap ready

- **`backend/app/services/llm_gateway.py`**
  - `TIER_TO_MODEL` map: `cheap=claude-haiku-4-5`, `mid=claude-sonnet-4-6`, `premium=claude-opus-4-7`.
  - `AGENT_MIN_TIER` per-agent floor (Portfolio Manager pinned to `premium` even for Floor-Pass users — the safety-floor enforcer never runs on a cheap brain).
  - `resolve_tier(plan_tier, agent_id)` takes the higher of the two. A Floor-Pass user 1-on-1 with PM → `premium`. A Floor-Manager Room run with the Concierge → `premium`.
  - `LLMGateway.status()` introspection — surfaced via the new endpoint.
- **`/v1/llm/status`** (`backend/app/api/llm.py`) — curl-checkable provider/model report. Does not call any provider; safe to ping cheaply.
- **`backend/scripts/llm_smoke.py`** — pings each tier with a one-token "PONG" prompt. After Saiful drops `ANTHROPIC_API_KEY` into `backend/.env`:
  ```bash
  cd backend && .venv/bin/python -m scripts.llm_smoke --quiet
  # → PASS (cheap,mid,premium)   ← the live flip is real
  ```
  Exits non-zero on any tier failure so it can be wired into a deploy gate.

### Tests (+12 new)

- `tests/unit/test_llm_gateway.py` — 12 cases covering:
  - Tier resolution (PM bump, concierge no-downgrade, unknown agent fallback).
  - `AGENT_MIN_TIER` coverage of every `AgentId`.
  - Gateway status with/without key (monkeypatched).
  - Mock provider canned routing.
  - `AnthropicProvider` SSE parsing (mocked `httpx.AsyncClient.stream`).
  - `AnthropicProvider` error path (HTTP 429 yields inline error chunk).
  - `AnthropicProvider` tolerance of empty lines / non-`data:` lines / junk JSON.
- Suite total: **103 passed** (was 91 at W8 end).
- Suite passes with `-W error::DeprecationWarning` — the entire `datetime.utcnow()` deprecation backlog is drained.

### Cleanup pass

- **`datetime.utcnow()` → `now_utc()`** (`backend/app/core/time.py` helper, returns naive UTC to match legacy semantics). Replaced 8 call sites across `schemas/onboarding.py`, `schemas/one_on_one.py`, `api/onboarding.py`, `services/agent_runner.py`, `services/session_store.py`, `services/concierge_engine.py`. Zero deprecation warnings remain.
- **Research Manager lesson** (`content/lessons/013_research_manager_synthesis.en.mdx`) — 5-min lesson on synthesis-vs-opinion, asymmetry arithmetic, "no trade" as a real output. Frontmatter `agent_callouts: ["research_manager"]` wires the unlock; completing this single lesson activates the RM agent via the Earn Path.
- **RLS Alembic migration** (`backend/alembic/versions/a4c7e9d10001_rls_policies.py`) — 23 policies across 13 user-scoped tables (mandates, user_overlays, journal_entries, lessons_progress, agent_activations, room_runs, sim_portfolios, sim_holdings, sim_trades, users, auth_challenges, overlay_edit_counts). All policies key on `current_setting('app.user_id', true)::uuid`. Applied to local Postgres (`docker exec ami_postgres psql ... -c "SELECT tablename, policyname FROM pg_policies"` shows all 23). Migration is no-op on SQLite (tests). Enforcement is dormant until the backend switches off `postgres` superuser — Saiful does that when real Supabase plugs in, by running the API under `authenticated` / `anon` roles.

### What's still NOT done

| Feature | Why deferred |
|---|---|
| **Live LLM validation** (1-on-1, Coach, Room actually producing real reasoning) | Needs `ANTHROPIC_API_KEY`. Code path is verified by tests; flip happens automatically when key lands. |
| **Real Supabase plug-in** | Needs Saiful to provision project + hand over keys. |
| **Real Apple Sign-In** | Needs Apple capability added to bundle id under team `S7RBWM4879`. |
| **Real LLM Concierge** | Deterministic onboarding state machine still drives W2. |
| **Room → LLM wiring** | `room_runner.py` still emits scripted text. Wiring it to the gateway is its own piece of work (per-agent prompts, transcript-aware context, fallback when no real provider). |

---
