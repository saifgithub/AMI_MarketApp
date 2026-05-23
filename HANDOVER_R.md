# Handover — AMI Trade build session

**Last updated:** 2026-05-23 (end of AT:R36 — Android-GMS pulled into alpha, [D-057](docs/11_decisions/decision_log.md#d-057--android-gms-pulled-forward-from-v10-to-alpha)). **Google Sign-In ships end-to-end in code**: backend `/v1/auth/google` route + `GoogleOIDCVerifier` (JWKS at `https://www.googleapis.com/oauth2/v3/certs`, accepts both Google issuers, `email_verified=false` guard); Flutter `sign_in_screen.dart` branches `Platform.isIOS` (Apple) vs `isAndroid` (Google); `google_sign_in: ^6.2.2` wired with `serverClientId` from Dart-define `GOOGLE_OAUTH_WEB_CLIENT_ID`. Android `build.gradle.kts` wired with Play App Signing config (graceful debug-signing fallback when `~/.android-keys/keystore.properties` absent) + `minSdk 28` / `targetSdk 35`. `scripts/build_playstore.sh` shipped (sibling of `build_testflight.sh`; shared monotonic `+N`). 10 docs updated (new entry **D-057**; D-006 amended; `platform_facade.md` banner rewritten — alpha-GMS ships via direct integration, facade is now HMS-only future work). `flutter_launcher_icons` dev dep + config in pubspec, awaits 3 source PNGs at `mobile/assets/icon/`. **+1 work commit + 1 wrap = 2 new commits. Backend tests now 438** (was 424; +14 tests in `test_auth_google.py`). **0 Alpha promotes** (backend changes ship once GCP OAuth Web client_id is configured next session). **Bug list still 0.** Saiful's remaining work is fully external + parallel-able: Play Console account, keystore generation, GCP OAuth clients, icon PNGs, Samsung Galaxy A17 arrives in ~1 week. AT:R35 wrap is now in [history_R.md](history_R.md).

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **296 commits** (2 new this session — Android-GMS alpha foundation + handover wrap), no remote yet |
| Latest work commit | `5b94681` — feat(android): Android-GMS alpha foundation — Google Sign-In + signing + build (AT:R36, D-057). |
| Alpha tags | **0 new promotes this session.** Still `alpha-2026-05-22-9` (AT:R34, mandate fallback). Next promote ships Google auth route + verifier once Saiful provides GCP OAuth Web client_id for `GOOGLE_AUDIENCES`. |
| Backend tests | **438 passed, 0 failed** — +14 tests in `backend/tests/unit/test_auth_google.py`. |
| Mobile pubspec | **`0.1.0+27`** — unchanged (build bump deferred to first real Play Store AAB upload, which gates on Saiful's keystore). |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **314 i18n keys** (added `signInWithGoogle` + `signInGoogleFailed` for Android). **Tier 1 ARB AR (311/314) + MS (310/314) via on-prem Gemma 4 31B**; the 2 new EN-only keys fall back to EN until next vLLM run. Tier 2 + Tier 3 content remain EN-only. |

```
$ git log --oneline | head -12
5b94681 feat(android): Android-GMS alpha foundation — Google Sign-In + signing + build (AT:R36, D-057)
91dce9c chore(handover): wrap AT:R35
17b482c feat(i18n): on-prem vLLM translation pipeline + Tier 1 ARB AR/MS (AT:R35)
f646706 chore(handover): wrap AT:R34
3f4022a fix(room): retry path falls back to resolve_mandate when version row missing (AT:R34)
8510436 fix(room): eeeb866f — startup auto-retry for runs killed by container restart (AT:R34)
1625e80 chore(handover): wrap AT:R33
19eb5d7 chore(mobile): Podfile.lock — pull device_info_plus pod (BL1)
ecea7bb chore(mobile): bump build 0.1.0+26 → 0.1.0+27 for TestFlight
d3cb451 feat(mandate): BL5 — mandate history API (AT:R33)
95e2337 feat(entitlements): BL11 — trial-end gate downgrades expired trials (AT:R33)
2d8a0d8 feat(auth): BL2 — user_devices multi-device tracking (AT:R33)
```

### Backend (lives on melehost — never the Mac)

| | |
|---|---|
| Where | `melehost` (Ubuntu Linux, LAN `192.168.20.59`) — Docker Compose stack at `~/ami_trade/` |
| Container | `ami_api_alpha` (built from `backend/Dockerfile`) — service name `api-alpha` in compose |
| Public hostname | `https://api-alpha.agenticmarketintel.ai` (Cloudflare Tunnel) |
| Health from outside the LAN | `curl https://api-alpha.agenticmarketintel.ai/v1/health` |
| Logs | `ssh melehost "docker logs ami_api_alpha --tail 50"` |
| Restart | `ssh melehost "cd ~/ami_trade && docker compose --profile tunnel up -d api-alpha"` |
| Routes | `/v1/health`, `/v1/auth/*` (incl. `DELETE /v1/auth/session` — Phase 4 sign-out, AT:R26; **`POST /v1/auth/google`** — D-057, AT:R36), `/v1/admin/*` (9 routes — AT:R27, see "Admin back-office" below), `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/brief/*` (was `/v1/coach/*` — renamed AT:R27; legacy `/v1/coach/*` kept as deprecated alias logging `deprecated_coach_route_used`), `/v1/journal/*` (incl. `/trash`, `/{id}/restore`), `/v1/lessons/*`, `/v1/llm/status`, `/v1/mandate/*` (now incl. **`/{u}/audit`** — BL12, **`/{u}/versions`** + **`/{u}/versions/{v}`** + **`POST /{u}/rollback/{v}`** — BL5, all AT:R33), `/v1/room/*`, `/v1/sim/*` (now incl. **`POST /sim/preview`** — BL9, AT:R33), `/v1/daily_challenge/*` (now incl. **`POST /{cid}/attempt`** — BL10, AT:R33), `/v1/watchlist/*`, `/v1/feedback/bug` (`multipart/form-data` with optional `file`). Plus a public HTML page at `/admin` (no auth required; the page itself asks for the `ADMIN_SECRET` bearer on first load + stores in localStorage). |
| Mac-side tests | `backend/.venv/bin/pytest backend/tests/unit/ -q` — **438 passed** (was 424; AT:R36 added +14 Google auth tests in `test_auth_google.py`). Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
| Env knobs (alpha) | `AMI_ENV=staging` + `SECRET_KEY=<64-hex>` + `ADMIN_SECRET=<64-hex>` (AT:R27, admin back-office bearer) + `SMTP_{HOST,PORT,USER,PASSWORD,FROM}` (5 vars, AT:R26 — now dormant) + **`RESEND_API_KEY=re_<…>`** (AT:R32, primary outbound mail route) + **`GOOGLE_AUDIENCES=<web_client_id_csv>`** (AT:R36, D-057 — empty until Saiful creates the GCP OAuth Web client; verifier rejects every token at the audience check until populated). Canonical at `infra/alpha.env` on Mac, gitignored; shipped via `scp` in `/promote-to-alpha` step 4. Without `SECRET_KEY` the backend refuses to start when env != local. **Email transport**: `email_service` prefers Resend (HTTP API, port 443 — bypasses melehost's ISP block on outbound 25/587) when `RESEND_API_KEY` is set; falls back to SMTP if `SMTP_HOST` is configured; falls back to no-op otherwise. Verified live: magic-link delivered to Gmail end-to-end. |
| Auth | Phase 1.5 + Phase 3 + Phase 4 enforced. Route-level `get_current_user` on `/v1/mandate`, `/v1/journal`, `/v1/watchlist`, `/v1/brief` (legacy `/v1/coach`), `/v1/agents/one_on_one`, `/v1/room`, plus per-route on user-specific `sim` + `lessons`. Bearer format `scaffold:<user_id_hex>:<hmac_sig>` (HMAC-SHA256 with `SECRET_KEY`). Legacy unsigned `scaffold:<hex>` accepted only in env=local. `/v1/auth/anon` mints fresh unless the caller's Bearer matches the supplied `device_user_id`. Magic-link routes require auth and bind to `current_user.id`. **Apple Sign-In Phase 3 (AT:R29):** `/v1/auth/apple` now lives in every env (no more 503 gate). `OIDCVerifier` in `app/services/oidc_verifier.py` fetches Apple's JWKS, RSA-verifies the identity token, validates `iss=https://appleid.apple.com`, `aud ∈ APPLE_AUDIENCES`, `exp`. On first auth: persists `email` + `full_name` (→ `users.display_name`). On subsequent auths or magic-link priors: preserves existing email/name (never overwritten). `DELETE /v1/auth/session` (Phase 4) requires auth and returns `{"signed_out": true}` — stateless no-op now. `http_audit` middleware scrubs request + response bodies for all `/v1/auth/*` routes (AT:R26 B4 close). **AT:R27 suspension enforcement:** `get_current_user` checks `users.suspended_at`; if set, raises `403 {"detail": "account_suspended"}`. **AT:R31 D-039 trial activation (BL3):** `_claim_or_create()` (magic-link) and `sign_in_with_apple()` (Apple) now populate `users.trial_started_at = now()` + `users.trial_expires_at = now() + 7d` on first claim. Guarded by `trial_started_at is None` so admin-granted trials are preserved. Downstream entitlement gate / expiry banner / conversion modal still TODO (BL11). **AT:R32 account-linking Phase 1:** `_claim_or_create()` now does email-lookup-FIRST (adopt existing identity), then user_id-fallback (promote anon). `sign_in_with_apple()` gained an email fallback between apple_sub and user_id lookups — magic-link-first + Apple-later (with same email) now attaches `apple_id` to the existing row instead of forking. Existing-row's email is never mutated by re-verify. Pre-claim anon rows are left orphan (ephemeral). Real merge UX deferred to BL16. **AT:R32 BL13 binding:** `/v1/auth/magic_link/verify` + `/v1/auth/apple` accept optional `onboarding_session_id`; route looks up `OnboardingSession` in `session_store` and stamps `claimed_user_id`. Both routes are now async. **AT:R32 L-1 cleanup:** `OneOnOneStartRequest.user_id` removed — `/v1/agents/one_on_one/start` sources user from Bearer only (audit A3 pattern, finally consistent). **AT:R33 BL1 device context:** `/v1/auth/anon` accepts optional `device_model`, `os_version`, `app_version`; backend persists onto `users` (refreshed on every bootstrap). **AT:R33 BL2 user_devices:** `/v1/auth/anon` also accepts optional `device_install_id` (mobile-generated UUID, never overwritten by claim). Backend upserts a `user_devices` row keyed by install_id; on claim adoption (`_claim_or_create` + `sign_in_with_apple`), the pre-claim anon's devices re-key to the adopting user so two phones on one Apple ID surface under one user. **AT:R33 BL11 entitlement gate:** `effective_plan(plan, trial_expires_at)` is now resolved at every `pick_tier()` callsite (brief_engine, agent_runner, room_runner) — when a trial lapses, LLM routing automatically drops to cheap-tier without admin intervention. **Admin auth:** `/v1/admin/*` uses `Authorization: Bearer <ADMIN_SECRET>`. Audit finding A4 CLOSED. **AT:R36 D-057 Google Sign-In:** `/v1/auth/google` mirrors `/v1/auth/apple` end-to-end. `GoogleOIDCVerifier` (in the same `oidc_verifier.py`) fetches `https://www.googleapis.com/oauth2/v3/certs`, RSA-verifies the ID token, accepts both Google issuers (`https://accounts.google.com` AND `accounts.google.com`), validates `aud ∈ GOOGLE_AUDIENCES`, `exp`. `OIDCVerifier.issuers` now a list (was `issuer: str`) with manual membership check, since python-jose only accepts a single string for the built-in `iss` check. `email_verified=false` guard drops the email on the floor (defends against unconfirmed-Google-account email squatting). Account-linking Phase 1 mirrors Apple: email-FIRST adoption of an existing magic-link/Apple row with the same email, then `google_sub`-fallback. Trial activation + BL2 device re-keying parallel Apple flow. Minimum-data policy (D-057, locked AT:R29 — "sub, name, email"): persist only `sub` → `users.google_id`, `email` → `users.email`, `name` → `users.display_name`; `picture`, `locale`, `hd`, `given_name`, `family_name` dropped. `AuthUser` schema gained `google_id`. `http_audit` SCRUB_PATHS includes `/v1/auth/google`. |
| Room env knobs | `ROOM_DEDUP_RUNNING_MINUTES=30` (in-flight dedup + startup-sweep cutoff) · `ROOM_DEDUP_COMPLETED_HOURS=24` (return prior verdict same day; design doc default was 5 days — we start tighter). Set completed_hours=0 to disable cached-run dedup. **AT:R34 eeeb866f:** startup sweep auto-retries stuck `running` rows once (`MAX_AUTO_RETRIES=1`, hard-coded in `room_runner.py`) before marking them failed. Lifespan startup hook calls `runner.resume_pending_retries()` to spawn the retry tasks; journal write is replayed inside the retry's `_pump` since the original request's `on_complete` closure is gone after restart. |
| Push code to it | [`/promote-to-alpha`](.claude/commands/promote-to-alpha.md) — rsync + recreate + smoke. No GitHub remote yet. |

Co-resident on melehost: **`api-website`** service (port 8001, builds from `./website_api/`, separate `ami_website` DB, CORS for `agenticmarketintel.ai`). The trade backend and marketing-site backend share zero code; waitlist is a website concern now.

### Admin back-office (AT:R27)

| | |
|---|---|
| Endpoints | `GET /v1/admin/users?email=&device_user_id=` (search) · `GET /v1/admin/users/{id}` (detail + last 20 events) · `PATCH /v1/admin/users/{id}/plan` (change plan tier) · `POST /v1/admin/users/{id}/trial` (grant trial, body: `{days, note?}`) · `PATCH /v1/admin/users/{id}/trial` (extend or revoke, body: `{action: "extend"|"revoke", days?, note?}`) · `POST /v1/admin/users/{id}/credits` (signed `delta`, body: `{delta, note?}`) · `POST /v1/admin/users/{id}/suspend` (sets `suspended_at = now()`) · `POST /v1/admin/users/{id}/reinstate` (clears `suspended_at`) · `GET /v1/admin/users/{id}/events?limit&offset` (paginated `subscription_events`) |
| Web UI | `https://api-alpha.agenticmarketintel.ai/admin` — single HTML file at `backend/app/static/admin.html` served by FastAPI as `HTMLResponse`. AMI Hex-Reinforced Precision palette mirrored from `mobile/lib/theme/ami_theme.dart`. Mobile-first: sticky topbar, big touch targets, safe-area padding, PWA meta tags so Saiful can "Add to Home Screen" on iPhone Safari. First load asks for `ADMIN_SECRET`, stores in `localStorage` on device. Vanilla HTML+CSS+JS — no build step. Replaced 1:1 by a Flutter web admin app in Beta (same URL, same API contract). |
| Event log | `subscription_events` table (10 event types): `plan_changed` · `trial_granted` · `trial_extended` · `trial_revoked` · `credits_added` · `credits_deducted` · `credits_consumed` · `revenuecat_purchase` · `user_suspended` · `user_reinstated`. Schema: `id UUID PK, user_id UUID FK, event_type VARCHAR, from_value TEXT, to_value TEXT, source VARCHAR (admin_override\|app\|revenuecat), admin_id UUID NULL (placeholder for Beta admin_users), note TEXT NULL, created_at TIMESTAMP`. Every admin write produces a row with `source=admin_override`. |
| Deferred | `admin_users` table + JWT auth (Beta); Flutter web admin app (Beta); credit-consumption deduction in Room + 1-on-1 (after access-level design lands); RevenueCat webhook → `revenuecat_purchase` events (MVP M1); aggregate revenue dashboard (post-launch). |

### Postgres + persistence

| | |
|---|---|
| Where | `melehost` — container `ami_postgres` in the compose stack |
| DB | `ami_trade` (user `postgres`, pw `postgres`) |
| Connect from melehost | `ssh melehost "docker exec -it ami_postgres psql -U postgres -d ami_trade"` |
| Mac dev DB | **None.** Mac runs zero services. |
| Backend unit tests | Per-test sqlite tempfile (autouse fixture in `backend/tests/conftest.py`) |
| Backups | Nightly `pg_dump` via `infra/backups/ami-trade-pg-backup.timer` (systemd timer on melehost). Restore drill in `infra/backups/README.md`. |

Tables: `users` (with `suspended_at`, `trial_started_at`, `trial_expires_at` — AT:R27; `display_name` — AT:R29; `device_model`, `os_version`, `last_app_version` — AT:R33 BL1), `auth_challenges`, `mandates`, `agent_activations`, `lessons_progress`, `journal_entries` (with `deleted_at`), `overlay_edit_counts`, `user_overlays`, `room_runs` (with **`retry_count`** — AT:R34 eeeb866f; defaults 0, bumped by startup sweep on container-restart claim), `sim_holdings`, `sim_portfolios`, `sim_trades`, `sim_watchlists`, `bug_reports` (with `assigned_branch`, `attachment_path`, `attachment_mime`), `llm_audit`, `http_audit`, `one_on_one_messages`, `subscription_events` (AT:R27), `user_devices` (AT:R33 BL2 — per-install rows keyed by device_install_id, backfilled 24 rows from existing users.device_user_id), `alembic_version`. Latest migration on melehost: **`e7a4c5b00010`** (`room_runs.retry_count` — AT:R34 eeeb866f). Prior in chain: `d5f2a3b00009` (`user_devices` — AT:R33 BL2), `c4e8f1a90008` (`users_device_info` — AT:R33 BL1), `b3f9d2a80007` (`users_display_name` — AT:R29). `init_schema()` self-stamps Alembic on a fresh container, so `alembic upgrade head` is a no-op on first boot. Bug-report attachments live in the named docker volume `ami-trade-local_bug_attachments` mounted at `/data/bug_attachments` in the api-alpha container.

### LLM gateway

- **vLLM** at `http://192.168.20.74:8000` serving `ami-llm` (Gemma 4 31B, NVFP4 quantized, 262k context — rebranded from `gemma-4-31b-it-nvfp4`). Gateway preference: `vllm > anthropic > mock`.
- Per-(plan, agent) tier routing in `app/services/tier_policy.py::pick_tier`.
- **AT:R27 prompt-composition fix:** `agent_runner.py:128` (1-on-1) AND `room_runner.py:963 + 1040` (Convene the Room) now both pass `user_id=ctx.user_id` (or `session.user_id`) to `build_agent_prompt` / `build_room_messages` so `_append_user_overlay` actually finds the user's active Brief overlay. Room runner was previously hard-coded to `user_id=None`, silently dropping every overlay. The user-overlay header text was also renamed: `USER COACHING OVERLAY` → `USER BRIEFING OVERLAY` (the literal text the LLM sees inside the prompt above the overlay block).

### Market data

- `USE_REAL_MARKET_DATA=true` on melehost. Fallback stack: yfinance → 60s cache → `mock_walk` if Yahoo returns empty/error.
- Quote model: `Quote(price, source, change_pct, market_state)` — `source` is the LEAF that served (`yfinance` or `mock_walk`), not the stack name.

### Mobile app

| | |
|---|---|
| Bundle | `ai.agenticmarketintel.amiTrade` |
| pubspec version | **`0.1.0+27`** (repo). Carries Apple Phase 3 (AT:R29) + entitlements + email+display_name persistence + BL1 device context + BL2 device_install_id (AT:R33) + **AT:R36 Google Sign-In wiring** (iOS-only Apple button + Android-only Google button via `Platform.is*`, `api_client.signInWithGoogle`, `authNotifier.signInWithGoogle`). Build bump deferred to first real Play Store AAB upload. |
| TestFlight | **`0.1.0+27`** uploaded 2026-05-22 by Saiful. Verified live on both iPhone 17 (iPhone18,1, iOS 26.4.2) and iPhone 13 mini (iPhone14,4, iOS 18.7.1) — both signed in with same Apple ID, both device rows under user `8f1e288a` per direct DB check (AT:R34 BL1+BL2 verification). External Beta still pending (no external testers added). One observation: iPhone 17 first launch of `+27` got stuck on a loading loop briefly; recovered without intervention (no backend errors in logs); worth watching across more cold launches. |
| Play Console internal track | **Not yet uploaded** — gates on Saiful's external work: Play Console account ($25, individual), keystore at `~/.android-keys/ami-trade-upload.keystore` (via `keytool`), GCP OAuth 2.0 Android + Web clients, 3 icon source PNGs at `mobile/assets/icon/`. Per [D-057](docs/11_decisions/decision_log.md#d-057--android-gms-pulled-forward-from-v10-to-alpha). Test device on order: Samsung Galaxy A17 8GB (Android 14, ~1 week out). |
| Build commands | `scripts/install_iphone.sh` (dev sideload, iOS), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number), **`scripts/build_playstore.sh`** (Play Console AAB, AT:R36, same monotonic `+N` as TestFlight, signed when `~/.android-keys/keystore.properties` exists). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). Android: Play App Signing (mandatory for new apps; Google holds the signing key); upload keystore at `~/.android-keys/ami-trade-upload.keystore` (referenced by `android/app/build.gradle.kts` via `~/.android-keys/keystore.properties`; debug-signing fallback when the props file is absent). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **AT:R27 Floor change:** tapping an unlocked agent no longer opens 1-on-1 directly — it now opens an `AgentActionSheet` bottom sheet with two big buttons: `[1-ON-1]` (talk to the agent) and `[BRIEF]` (modify how it thinks). Concierge skips the sheet — has no Brief surface, so 1-on-1 is the only path. The tune icon in the 1-on-1 header stays as a secondary route to Brief. **AT:R27 rename:** `CoachScreen` → `BriefScreen`, `BriefHistoryScreen`, `BriefNotifier`/`briefNotifierProvider`, `models/brief.dart`, `api_client.startBrief/streamBriefMessage/...`. The 33 l10n keys flipped from `coach*` to `brief*` (including the journal chips: `journalFilterCoach` → `journalFilterBrief`, value `COACH` → `BRIEF`; same for `journalEntryTypeCoach`). Journal filter chips now read: `ALL · ROOM · TRADE · 1-ON-1 · BRIEF · LESSONS · UNLOCKS`. **First-time walkthrough (AT:R23):** per-section coach-mark tours (still using `tutorial_coach_mark` package — unrelated to Brief feature) fire on first visit. **AT:R25 auth gate** + **AT:R26 sign-out (Phase 4)** + **AT:R26 Apple-glitch fix** still in place. Journal soft-delete + Trash + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green pill once a sim_trade exists. Trade ticket sheet has live quote chip + auto-suggested TP/SL. Ticker tape below bottom nav. Settings → APPEARANCE is dark-only. Bug-report sheet (long-press app-version chip) supports photo attachments.

---

## What just landed (this session — AT:R36)

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

### Carry-overs for AT:R37

Top-priority (gated on Saiful's external Android setup):

1. **Saiful Android setup** (parallelizable, days of real-world lead time):
   - Register Play Console account ($25, individual)
   - `keytool -genkey -v -keystore ~/.android-keys/ami-trade-upload.keystore -alias upload -keyalg RSA -keysize 2048 -validity 10000` → backup to 1Password → extract SHA-1
   - GCP Console: enable Google Sign-In API, create Android client (package + SHA-1), create Web client → put Web client_id into `infra/alpha.env` as `GOOGLE_AUDIENCES` + pass to build script as `GOOGLE_OAUTH_WEB_CLIENT_ID`
   - Produce 3 icon source PNGs (see prompt in `~/.claude/plans/giggly-knitting-harbor.md`), drop at `mobile/assets/icon/`, run `flutter pub run flutter_launcher_icons`
2. **Promote backend with `/v1/auth/google`.** Backend changes are committed but not yet on melehost. Once `GOOGLE_AUDIENCES` is filled in `infra/alpha.env`, run `/promote-to-alpha`. Smoke-check via curl with a real Google ID token (or just verify the route responds with 400 "google identity_token missing 'sub' claim" on a malformed token).
3. **First Play Console AAB upload.** After keystore + GCP + Play Console account are live: `scripts/build_playstore.sh` produces signed AAB → upload via Play Console web UI (mandatory-manual for Play App Signing enrollment) → fill Data Safety form + Content Rating questionnaire + screenshots → add internal testers → roll out.
4. **Samsung A17 device validation** (~1 week out): install internal-track build, smoke-test golden path (Concierge → Google Sign-In → claim → 1-on-1 / Brief / Floor → Sentry crash → RTL Arabic spot-check → bug report).

Carrying from AT:R35 (unchanged unless noted):

5. **Re-run Tier 2 sequentially.** `scripts/translate_content_lan.py --type glossary` alone (~50 min), then `--type ai_coach`, then `--type daily_challenges`. ~5h total wall time sequential.
6. **Re-think Tier 3 (lessons) approach.** Sequential = ~28h GPU. Options: (a) per-lesson concurrency, (b) bigger batches across lessons, (c) accept 28h over multiple sessions, (d) defer to v1.0.
7. **Backend loader changes** for `ai_coach_service.py` + `daily_challenge_service.py` to glob `<locale>/*.json` subdirectories. Small isolated diff; unlocks Tier 2 outputs.
8. **Sign-out UX improvement.** When the user signs out, show "sign back in to continue" rather than silently minting a new anon. Adjacent to BL16 but cheaper.

Carrying from AT:R34 / earlier (unchanged):

9. TF `+27` cold-launch loading loop on iPhone 17 — watch item.
10. External TestFlight launch (needs Beta App Description from Saiful + ~24h Apple review).
11. B-tier adversarial-audit findings — rate limiting on `/auth/anon` + LLM-heavy routes; magic-link attempt counter; feedback upload streaming.
12. **BL16** — Real account merge UX. Connect with #8 above.
13. **BL6** — Mandate resolve flow (Liquidate/Postpone/Override actions).
14. **BL11** — push + in-app trial-end UX.
15. **BL4** — Arabic → Gemini routing. Now MORE relevant since Tier 1 AR is shipping in the next app build.
16. **BL7** — Agent metadata routes.
17. **BL8** — Room run cancel + replay.
18. **Animation production** — 15 `<Animation>` MDX tags.
19. **A29 light-mode refactor.**
20. **`claude/*` sibling worktrees on disk** — 24 of them, keep-or-delete decision.
21. **Credit consumption** — `credits_consumed` event type exists, no app code emits it.
22. **`OnboardingSession.claimed_user_id` Flutter wiring.**

(Drops from AT:R35 carry-over list this session: A6b — closed as **partial** in the project plan; backend code shipped, awaiting GCP OAuth client_id.)

### Watch items (not tasks)

- **`/v1/auth/google` will reject every token until `GOOGLE_AUDIENCES` is populated** on melehost. That's the safe default — empty audiences fail the manual membership check inside `OIDCVerifier.verify()`. Don't be surprised when the first real Android sign-in attempt fails with a 400 on a pre-promote backend.
- **Google button is disabled in the Android UI** when `--dart-define GOOGLE_OAUTH_WEB_CLIENT_ID=` is empty (the build script warns about this). Defensive fallback in the handler also surfaces "Google Sign-In not configured for this build" snackbar if somehow the disabled-button check is bypassed.
- **`flutter_launcher_icons` is configured but not yet run.** The 3 source PNGs at `mobile/assets/icon/` don't exist yet. Running the generator before the PNGs land will fail loudly. Saiful generates the PNGs from the design tool first.
- **2 untranslated keys on AR, 3 on MS** (was 0 AR / 1 MS at end of AT:R35; the new `signInWithGoogle` + `signInGoogleFailed` + carry-over `tourJournal2Body` for MS). They fall back to EN automatically. Next vLLM translation run will fill them; non-blocking per CLAUDE.md i18n policy.
- **vLLM saturation pattern.** A single H100-class GPU comfortably serves 1-2 concurrent long-form generation streams; 4 streams blow per-stream latency past 300s. Sequential is the safe path.

---

## How to start the next session

```
/start-fresh R
```

The slash command reads `HANDOVER_R.md` + `docs/10_delivery/project_plan.md`, runs the configured sanity checks (Alpha health curl), queries the live bug list (currently **0 open**), then enters plan mode asking what to work on.

Session name to use: **AT:R37** (this is handover #36).

If Alpha is down at session start, `/start-fresh` will surface that and tell you the melehost debug commands.

If the first message is a specific task ("fix this", "add that"), skip `/start-fresh` and just do the task — the slash command is for the "let's keep going" opening.

Quick-win candidates for next session (in priority order):

1. **Promote the AT:R36 backend** if Saiful has filled `GOOGLE_AUDIENCES` in `infra/alpha.env`. `/promote-to-alpha` ships the `/v1/auth/google` route + verifier. Smoke-check with a malformed-token curl (expect 400).
2. **First Play Console AAB** if Saiful has the keystore + GCP clients + Play Console account ready. `scripts/build_playstore.sh` produces the AAB; manual upload completes Play App Signing enrollment.
3. **Tier 2 sequential translation run** — backend loader changes first (item 7 above), then `scripts/translate_content_lan.py --type glossary` (~50 min), then `--type ai_coach`, then `--type daily_challenges`.
4. **Sign-out UX** (#8) — small Flutter-only change, ships independently of all Android external setup.
5. **External TestFlight launch** (#10) — Beta App Description from Saiful + ~24h Apple review.
6. **B-tier audit work / BL6 / BL11-push / BL4 / BL7 / BL8** — remaining backlog.

---

## How to run the stack

```bash
# Backend lives on melehost. Normally already running — only re-run if needed.
ssh melehost "cd ~/ami_trade && docker compose --profile tunnel up -d"

# iPhone app — release build + install on TESTING IPHONE 13.
scripts/install_iphone.sh

# Push a build to TestFlight — bumps build number, builds, uploads.
scripts/build_testflight.sh

# Backend unit tests — sqlite tempfile via conftest. Mac-side.
pytest backend/tests/unit/ -q

# Admin UI (browser, including iPhone Safari)
# https://api-alpha.agenticmarketintel.ai/admin
# First-load asks for ADMIN_SECRET (from infra/alpha.env line 43)
```

---

## Open questions / nothing-is-blocked items

- **Anthropic API key.** Not added — and not needed: on-prem vLLM at `192.168.20.74:8000` serves Gemma 4 31B for every agent. Anthropic remains a hot-swappable fallback if `VLLM_BASE_URL` is unset.
- **Supabase project.** Not yet provisioned. RLS policies live but dormant — they enforce once the backend stops connecting as `postgres`.
- **Apple Developer team.** Done (`S7RBWM4879`). Sign in with Apple capability enabled at the bundle ID (Saiful, AT:R26) + entitlements file in Xcode + provisioning profile regenerated (AT:R29). Phase 3 JWKS verification shipped AT:R29 — fully live end-to-end.
- **App Store + APNs** — external. Market data is real Yahoo when `USE_REAL_MARKET_DATA=true`.

Nothing is blocking the next chunk.
