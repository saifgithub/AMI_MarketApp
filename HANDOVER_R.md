# Handover — AMI Trade build session

**Last updated:** 2026-05-24 (end of AT:R38 — **BL16 real account merge UX, end-to-end**). When account-linking Phase 1 silently adopts an existing email/sub row over the caller's anon, `AuthVerifyResponse.adopted_from_user_id` now carries the orphan's user_id back to the client. Flutter `SignInScreen` reads it and pushes `MergeSheet` with pluralised orphan counts + `[MERGE EVERYTHING]` / `[KEEP SEPARATE]`. New `MergeService` re-keys journal / sim / lessons / overlays / mandate / etc. from orphan to adopter in one transaction; new `GET /v1/auth/merge/preview/{from}` + `POST /v1/auth/merge` routes guarded by `account_adoption` `SubscriptionEventRow` lookup (the merge endpoint asserts the caller is the legitimate adopter). `_AuthGate` also invalidates per-user Riverpod caches (sim, journal, mandate, watchlist, lessons) on every `user.id` change. **+2 work commits + 1 wrap = 3 new commits. Backend tests now 485** (was 461; +24 across `test_merge_service`, `test_merge_routes`, and adoption-signal assertions retrofitted into `test_auth_service`). **0 Alpha promotes** — AT:R36 (`/v1/auth/google`) + AT:R37 (lockout, rate limit, streaming) + AT:R38 (merge stack) all sit on Mac awaiting `GOOGLE_AUDIENCES` in `infra/alpha.env`. **Bug list still 0.** AT:R37 wrap is now in [history_R.md](history_R.md).

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **306 commits** (2 work + 1 wrap = 3 new this session), no remote yet |
| Latest work commit | `313179c` — feat(auth): BL16 mobile — detect adoption + merge sheet + cache invalidation (AT:R38). |
| Alpha tags | **0 new promotes this session.** Still `alpha-2026-05-22-9` (AT:R34, mandate fallback). AT:R36 + AT:R37 + AT:R38 backend now three-deep on Mac; next promote ships Google auth route + lockout migration + rate limiter + streaming uploads + merge stack (all once `GOOGLE_AUDIENCES` is filled). |
| Backend tests | **485 passed, 0 failed** — +24 this session: 14 in `test_merge_service.py` (NEW), 10 in `test_merge_routes.py` (NEW), plus retrofits in `test_auth_service.py` adding adopted_from assertions (no net add to that file). |
| Mobile pubspec | **`0.1.0+27`** — unchanged (build bump deferred to first real Play Store AAB upload, which gates on Saiful's keystore). |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **329 i18n keys** (added 14 `mergeSheet*` keys this session). **Tier 1 ARB AR (311/329) + MS (310/329) via on-prem Gemma 4 31B**; the 18 / 19 unfilled keys fall back to EN. Tier 2 + Tier 3 content remain EN-only; loaders are ready when translated subdirs land. |

```
$ git log --oneline | head -15
313179c feat(auth): BL16 mobile — detect adoption + merge sheet + cache invalidation (AT:R38)
f7a771a feat(auth): BL16 backend — adoption signal + /v1/auth/merge endpoints (AT:R38)
5946df2 chore(handover): wrap AT:R37
e12d998 feat(audit): stream bug-report uploads to disk in 64KB chunks (AT:R37)
6a2ba97 feat(audit): in-memory rate limiter on /auth/anon + magic_link/start + room/stream (AT:R37)
eec3117 feat(auth): magic-link brute-force lockout — auth_challenges.attempts (AT:R37)
bdea6e8 feat(content): ai_coach + daily_challenge loaders glob <locale>/*.json (AT:R37)
73b9f0d feat(auth): wire OnboardingSession.id through Flutter claim paths (BL13, AT:R37)
88f8bbc chore: prune 24+ stale claude/* worktrees and branches (AT:R37)
9b28b5f feat(auth): sign-out navigates to sign-in screen with 'you've been signed out' banner (AT:R37)
5530228 chore(handover): wrap AT:R36
5b94681 feat(android): Android-GMS alpha foundation — Google Sign-In + signing + build (AT:R36, D-057)
91dce9c chore(handover): wrap AT:R35
17b482c feat(i18n): on-prem vLLM translation pipeline + Tier 1 ARB AR/MS (AT:R35)
f646706 chore(handover): wrap AT:R34
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
| Routes | `/v1/health`, `/v1/auth/*` (incl. `DELETE /v1/auth/session` — Phase 4 sign-out, AT:R26; **`POST /v1/auth/google`** — D-057, AT:R36; **`GET /v1/auth/merge/preview/{from}`** + **`POST /v1/auth/merge`** — BL16, AT:R38), `/v1/admin/*` (9 routes — AT:R27, see "Admin back-office" below), `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/brief/*` (was `/v1/coach/*` — renamed AT:R27; legacy `/v1/coach/*` kept as deprecated alias logging `deprecated_coach_route_used`), `/v1/journal/*` (incl. `/trash`, `/{id}/restore`), `/v1/lessons/*`, `/v1/llm/status`, `/v1/mandate/*` (now incl. **`/{u}/audit`** — BL12, **`/{u}/versions`** + **`/{u}/versions/{v}`** + **`POST /{u}/rollback/{v}`** — BL5, all AT:R33), `/v1/room/*`, `/v1/sim/*` (now incl. **`POST /sim/preview`** — BL9, AT:R33), `/v1/daily_challenge/*` (now incl. **`POST /{cid}/attempt`** — BL10, AT:R33), `/v1/watchlist/*`, `/v1/feedback/bug` (`multipart/form-data` with optional `file`). Plus a public HTML page at `/admin` (no auth required; the page itself asks for the `ADMIN_SECRET` bearer on first load + stores in localStorage). |
| Mac-side tests | `backend/.venv/bin/pytest backend/tests/unit/ -q` — **461 passed** (was 438; AT:R37 added +23 across Tier 2 loaders, magic-link lockout, rate limiter, and streaming uploads). Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
| Env knobs (alpha) | `AMI_ENV=staging` + `SECRET_KEY=<64-hex>` + `ADMIN_SECRET=<64-hex>` (AT:R27, admin back-office bearer) + `SMTP_{HOST,PORT,USER,PASSWORD,FROM}` (5 vars, AT:R26 — now dormant) + **`RESEND_API_KEY=re_<…>`** (AT:R32, primary outbound mail route) + **`GOOGLE_AUDIENCES=<web_client_id_csv>`** (AT:R36, D-057 — empty until Saiful creates the GCP OAuth Web client; verifier rejects every token at the audience check until populated). Canonical at `infra/alpha.env` on Mac, gitignored; shipped via `scp` in `/promote-to-alpha` step 4. Without `SECRET_KEY` the backend refuses to start when env != local. **Email transport**: `email_service` prefers Resend (HTTP API, port 443 — bypasses melehost's ISP block on outbound 25/587) when `RESEND_API_KEY` is set; falls back to SMTP if `SMTP_HOST` is configured; falls back to no-op otherwise. Verified live: magic-link delivered to Gmail end-to-end. |
| Auth | Phase 1.5 + Phase 3 + Phase 4 enforced. Route-level `get_current_user` on `/v1/mandate`, `/v1/journal`, `/v1/watchlist`, `/v1/brief` (legacy `/v1/coach`), `/v1/agents/one_on_one`, `/v1/room`, plus per-route on user-specific `sim` + `lessons`. Bearer format `scaffold:<user_id_hex>:<hmac_sig>` (HMAC-SHA256 with `SECRET_KEY`). Legacy unsigned `scaffold:<hex>` accepted only in env=local. `/v1/auth/anon` mints fresh unless the caller's Bearer matches the supplied `device_user_id`. Magic-link routes require auth and bind to `current_user.id`. **Apple Sign-In Phase 3 (AT:R29):** `/v1/auth/apple` now lives in every env (no more 503 gate). `OIDCVerifier` in `app/services/oidc_verifier.py` fetches Apple's JWKS, RSA-verifies the identity token, validates `iss=https://appleid.apple.com`, `aud ∈ APPLE_AUDIENCES`, `exp`. On first auth: persists `email` + `full_name` (→ `users.display_name`). On subsequent auths or magic-link priors: preserves existing email/name (never overwritten). `DELETE /v1/auth/session` (Phase 4) requires auth and returns `{"signed_out": true}` — stateless no-op now. `http_audit` middleware scrubs request + response bodies for all `/v1/auth/*` routes (AT:R26 B4 close). **AT:R27 suspension enforcement:** `get_current_user` checks `users.suspended_at`; if set, raises `403 {"detail": "account_suspended"}`. **AT:R31 D-039 trial activation (BL3):** `_claim_or_create()` (magic-link) and `sign_in_with_apple()` (Apple) now populate `users.trial_started_at = now()` + `users.trial_expires_at = now() + 7d` on first claim. Guarded by `trial_started_at is None` so admin-granted trials are preserved. Downstream entitlement gate / expiry banner / conversion modal still TODO (BL11). **AT:R32 account-linking Phase 1:** `_claim_or_create()` now does email-lookup-FIRST (adopt existing identity), then user_id-fallback (promote anon). `sign_in_with_apple()` gained an email fallback between apple_sub and user_id lookups — magic-link-first + Apple-later (with same email) now attaches `apple_id` to the existing row instead of forking. Existing-row's email is never mutated by re-verify. Pre-claim anon rows are left orphan (ephemeral). Real merge UX deferred to BL16. **AT:R32 BL13 binding:** `/v1/auth/magic_link/verify` + `/v1/auth/apple` accept optional `onboarding_session_id`; route looks up `OnboardingSession` in `session_store` and stamps `claimed_user_id`. Both routes are now async. **AT:R32 L-1 cleanup:** `OneOnOneStartRequest.user_id` removed — `/v1/agents/one_on_one/start` sources user from Bearer only (audit A3 pattern, finally consistent). **AT:R33 BL1 device context:** `/v1/auth/anon` accepts optional `device_model`, `os_version`, `app_version`; backend persists onto `users` (refreshed on every bootstrap). **AT:R33 BL2 user_devices:** `/v1/auth/anon` also accepts optional `device_install_id` (mobile-generated UUID, never overwritten by claim). Backend upserts a `user_devices` row keyed by install_id; on claim adoption (`_claim_or_create` + `sign_in_with_apple`), the pre-claim anon's devices re-key to the adopting user so two phones on one Apple ID surface under one user. **AT:R33 BL11 entitlement gate:** `effective_plan(plan, trial_expires_at)` is now resolved at every `pick_tier()` callsite (brief_engine, agent_runner, room_runner) — when a trial lapses, LLM routing automatically drops to cheap-tier without admin intervention. **Admin auth:** `/v1/admin/*` uses `Authorization: Bearer <ADMIN_SECRET>`. Audit finding A4 CLOSED. **AT:R36 D-057 Google Sign-In:** `/v1/auth/google` mirrors `/v1/auth/apple` end-to-end. `GoogleOIDCVerifier` (in the same `oidc_verifier.py`) fetches `https://www.googleapis.com/oauth2/v3/certs`, RSA-verifies the ID token, accepts both Google issuers (`https://accounts.google.com` AND `accounts.google.com`), validates `aud ∈ GOOGLE_AUDIENCES`, `exp`. `OIDCVerifier.issuers` now a list (was `issuer: str`) with manual membership check, since python-jose only accepts a single string for the built-in `iss` check. `email_verified=false` guard drops the email on the floor (defends against unconfirmed-Google-account email squatting). Account-linking Phase 1 mirrors Apple: email-FIRST adoption of an existing magic-link/Apple row with the same email, then `google_sub`-fallback. Trial activation + BL2 device re-keying parallel Apple flow. Minimum-data policy (D-057, locked AT:R29 — "sub, name, email"): persist only `sub` → `users.google_id`, `email` → `users.email`, `name` → `users.display_name`; `picture`, `locale`, `hd`, `given_name`, `family_name` dropped. `AuthUser` schema gained `google_id`. `http_audit` SCRUB_PATHS includes `/v1/auth/google`. **AT:R37 B-tier audit close — magic-link brute-force lockout:** `verify_magic_link()` now finds the most recent active (unconsumed + unexpired) challenge for the target by `target` alone (not joined on `code_hash`), so a wrong-code attempt can bump `auth_challenges.attempts`. Once the counter hits `MAX_MAGIC_LINK_ATTEMPTS = 5` the row is force-consumed via `consumed_at = now()`, locking out even the correct code. The user always recovers by requesting a fresh code (mints a new row with `attempts=0`). **AT:R37 B-tier audit close — rate limiting:** new `app/services/rate_limit.py` ships an in-memory sliding-window `RateLimiter` dep applied to `/v1/auth/anon` (10/min/IP), `/v1/auth/magic_link/start` (3/min/IP — email cost), `/v1/room/stream` (5/min/IP — 12-agent LLM run cost). IP resolution: `cf-connecting-ip` → `x-forwarded-for` first hop → `request.client.host`. 429 with `Retry-After` header on overrun. Process-local — replaced by Redis-backed when we shard. **AT:R37 B-tier audit close — feedback upload streaming:** new `save_attachment_streaming()` reads UploadFile in 64KB chunks with a running byte counter; mid-stream cap overrun aborts + unlinks the partial file. MIME validated up-front so unsupported types never touch disk. **AT:R38 BL16 — adoption signal + merge endpoints:** `AuthVerifyResponse` gained `adopted_from_user_id: UUID | None`, populated by the 3 claim methods (`_claim_or_create`, `sign_in_with_apple`, `sign_in_with_google`) whenever the email/sub fallback returns a different `user_id` than the caller's bearer. Each adoption also writes a `subscription_events` row with `event_type=account_adoption`, which the new `GET /v1/auth/merge/preview/{from}` + `POST /v1/auth/merge` routes use as their authorisation proof (caller's bearer must match the `to_value`; 403 otherwise). The execute route delegates to `MergeService.execute()` — a single-transaction re-key of every per-user row from orphan → adopter, with per-table conflict rules; ends by `DELETE`-ing the orphan `users` row. |
| Room env knobs | `ROOM_DEDUP_RUNNING_MINUTES=30` (in-flight dedup + startup-sweep cutoff) · `ROOM_DEDUP_COMPLETED_HOURS=24` (return prior verdict same day; design doc default was 5 days — we start tighter). Set completed_hours=0 to disable cached-run dedup. **AT:R34 eeeb866f:** startup sweep auto-retries stuck `running` rows once (`MAX_AUTO_RETRIES=1`, hard-coded in `room_runner.py`) before marking them failed. Lifespan startup hook calls `runner.resume_pending_retries()` to spawn the retry tasks; journal write is replayed inside the retry's `_pump` since the original request's `on_complete` closure is gone after restart. |
| Push code to it | [`/promote-to-alpha`](.claude/commands/promote-to-alpha.md) — rsync + recreate + smoke. No GitHub remote yet. |

Co-resident on melehost: **`api-website`** service (port 8001, builds from `./website_api/`, separate `ami_website` DB, CORS for `agenticmarketintel.ai`). The trade backend and marketing-site backend share zero code; waitlist is a website concern now.

### Admin back-office (AT:R27)

| | |
|---|---|
| Endpoints | `GET /v1/admin/users?email=&device_user_id=` (search) · `GET /v1/admin/users/{id}` (detail + last 20 events) · `PATCH /v1/admin/users/{id}/plan` (change plan tier) · `POST /v1/admin/users/{id}/trial` (grant trial, body: `{days, note?}`) · `PATCH /v1/admin/users/{id}/trial` (extend or revoke, body: `{action: "extend"|"revoke", days?, note?}`) · `POST /v1/admin/users/{id}/credits` (signed `delta`, body: `{delta, note?}`) · `POST /v1/admin/users/{id}/suspend` (sets `suspended_at = now()`) · `POST /v1/admin/users/{id}/reinstate` (clears `suspended_at`) · `GET /v1/admin/users/{id}/events?limit&offset` (paginated `subscription_events`) |
| Web UI | `https://api-alpha.agenticmarketintel.ai/admin` — single HTML file at `backend/app/static/admin.html` served by FastAPI as `HTMLResponse`. AMI Hex-Reinforced Precision palette mirrored from `mobile/lib/theme/ami_theme.dart`. Mobile-first: sticky topbar, big touch targets, safe-area padding, PWA meta tags so Saiful can "Add to Home Screen" on iPhone Safari. First load asks for `ADMIN_SECRET`, stores in `localStorage` on device. Vanilla HTML+CSS+JS — no build step. Replaced 1:1 by a Flutter web admin app in Beta (same URL, same API contract). |
| Event log | `subscription_events` table (12 event types): `plan_changed` · `trial_granted` · `trial_extended` · `trial_revoked` · `credits_added` · `credits_deducted` · `credits_consumed` (declared but no emitter yet) · `revenuecat_purchase` (declared but no emitter yet) · `user_suspended` · `user_reinstated` · **`account_adoption`** (BL16, AT:R38 — written when account-linking Phase 1 silently adopts an existing email/sub row over the caller's anon; `from_value=orphan_user_id`, `to_value=adopting_user_id`, `source=app`; the merge routes look this up to authorise the caller) · **`account_adoption_merged`** (BL16, AT:R38 — written when the user confirms the merge sheet; `note` is a JSON blob of per-table re-key counts). Schema: `id UUID PK, user_id UUID FK, event_type VARCHAR, from_value TEXT, to_value TEXT, source VARCHAR (admin_override\|app\|revenuecat), admin_id UUID NULL (placeholder for Beta admin_users), note TEXT NULL, created_at TIMESTAMP`. Every admin write produces a row with `source=admin_override`. |
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

Tables: `users` (with `suspended_at`, `trial_started_at`, `trial_expires_at` — AT:R27; `display_name` — AT:R29; `device_model`, `os_version`, `last_app_version` — AT:R33 BL1), `auth_challenges` (with **`attempts`** — AT:R37 B-tier audit; bumped on every wrong-code verify, force-consumes the row at 5), `mandates`, `agent_activations`, `lessons_progress`, `journal_entries` (with `deleted_at`), `overlay_edit_counts`, `user_overlays`, `room_runs` (with `retry_count` — AT:R34 eeeb866f; defaults 0, bumped by startup sweep on container-restart claim), `sim_holdings`, `sim_portfolios`, `sim_trades`, `sim_watchlists`, `bug_reports` (with `assigned_branch`, `attachment_path`, `attachment_mime`), `llm_audit`, `http_audit`, `one_on_one_messages`, `subscription_events` (AT:R27), `user_devices` (AT:R33 BL2 — per-install rows keyed by device_install_id, backfilled 24 rows from existing users.device_user_id), `alembic_version`. Latest migration in repo: **`f8b5d1c00011`** (`auth_challenges.attempts` — AT:R37 B-tier audit; not yet on melehost — ships next promote). Prior in chain: `e7a4c5b00010` (`room_runs.retry_count` — AT:R34), `d5f2a3b00009` (`user_devices` — AT:R33 BL2), `c4e8f1a90008` (`users_device_info` — AT:R33 BL1), `b3f9d2a80007` (`users_display_name` — AT:R29). `init_schema()` self-stamps Alembic on a fresh container, so `alembic upgrade head` is a no-op on first boot. Bug-report attachments live in the named docker volume `ami-trade-local_bug_attachments` mounted at `/data/bug_attachments` in the api-alpha container.

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
| pubspec version | **`0.1.0+27`** (repo). Carries Apple Phase 3 (AT:R29) + entitlements + email+display_name persistence + BL1 device context + BL2 device_install_id (AT:R33) + AT:R36 Google Sign-In wiring + AT:R37 sign-out UX / BL13 onboarding-session threading + **AT:R38 BL16 merge UX: new `MergeSheet`, new `previewMerge`/`executeMerge` API calls, `AuthVerifyResponse.adoptedFromUserId`, `ClaimOutcome` from the 3 claim notifier methods, `AuthState.previousUserId` + `_AuthGate` cache-invalidation listener (sim / journal / journalTrash / mandate / watchlist / lessons)**. Build bump deferred to first real Play Store AAB upload. |
| TestFlight | **`0.1.0+27`** uploaded 2026-05-22 by Saiful. Verified live on both iPhone 17 (iPhone18,1, iOS 26.4.2) and iPhone 13 mini (iPhone14,4, iOS 18.7.1) — both signed in with same Apple ID, both device rows under user `8f1e288a` per direct DB check (AT:R34 BL1+BL2 verification). External Beta still pending (no external testers added). One observation: iPhone 17 first launch of `+27` got stuck on a loading loop briefly; recovered without intervention (no backend errors in logs); worth watching across more cold launches. |
| Play Console internal track | **Not yet uploaded** — gates on Saiful's external work: Play Console account ($25, individual), keystore at `~/.android-keys/ami-trade-upload.keystore` (via `keytool`), GCP OAuth 2.0 Android + Web clients, 3 icon source PNGs at `mobile/assets/icon/`. Per [D-057](docs/11_decisions/decision_log.md#d-057--android-gms-pulled-forward-from-v10-to-alpha). Test device on order: Samsung Galaxy A17 8GB (Android 14, ~1 week out). |
| Build commands | `scripts/install_iphone.sh` (dev sideload, iOS), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number), **`scripts/build_playstore.sh`** (Play Console AAB, AT:R36, same monotonic `+N` as TestFlight, signed when `~/.android-keys/keystore.properties` exists). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). Android: Play App Signing (mandatory for new apps; Google holds the signing key); upload keystore at `~/.android-keys/ami-trade-upload.keystore` (referenced by `android/app/build.gradle.kts` via `~/.android-keys/keystore.properties`; debug-signing fallback when the props file is absent). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **AT:R27 Floor change:** tapping an unlocked agent no longer opens 1-on-1 directly — it now opens an `AgentActionSheet` bottom sheet with two big buttons: `[1-ON-1]` (talk to the agent) and `[BRIEF]` (modify how it thinks). Concierge skips the sheet — has no Brief surface, so 1-on-1 is the only path. The tune icon in the 1-on-1 header stays as a secondary route to Brief. **AT:R27 rename:** `CoachScreen` → `BriefScreen`, `BriefHistoryScreen`, `BriefNotifier`/`briefNotifierProvider`, `models/brief.dart`, `api_client.startBrief/streamBriefMessage/...`. The 33 l10n keys flipped from `coach*` to `brief*` (including the journal chips: `journalFilterCoach` → `journalFilterBrief`, value `COACH` → `BRIEF`; same for `journalEntryTypeCoach`). Journal filter chips now read: `ALL · ROOM · TRADE · 1-ON-1 · BRIEF · LESSONS · UNLOCKS`. **First-time walkthrough (AT:R23):** per-section coach-mark tours (still using `tutorial_coach_mark` package — unrelated to Brief feature) fire on first visit. **AT:R25 auth gate** + **AT:R26 sign-out (Phase 4)** + **AT:R26 Apple-glitch fix** still in place. **AT:R37 sign-out UX:** after the `signOut()` notifier completes (which still mints a fresh anon in the background via bootstrap, since the app gate needs *some* user), the Settings button now pushes `SignInScreen(showSignedOutBanner: true)` — the user lands on the sign-in screen with a subtle "You've been signed out." strip at the top and one-tap auth options. Back navigation returns to Settings as guest if they don't sign back in. **AT:R38 merge sheet (BL16):** after a successful claim, `SignInScreen` reads `AuthVerifyResponse.adoptedFromUserId` — when non-null (account-linking Phase 1 silently adopted an existing email/sub row over the caller's anon), it pushes `MergeSheet` showing the orphan's pluralised counts ("12 journal entries · 3 sim trades · 7 lessons started · mandate") with `[MERGE EVERYTHING]` / `[KEEP SEPARATE]`. Confirm hits `POST /v1/auth/merge`; backend re-keys the orphan's data into the adopting user in one transaction. `_AuthGate` also invalidates sim / journal / mandate / watchlist / lessons providers on every `user.id` change so the prior user's data doesn't render stale post-swap. Journal soft-delete + Trash + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green pill once a sim_trade exists. Trade ticket sheet has live quote chip + auto-suggested TP/SL. Ticker tape below bottom nav. Settings → APPEARANCE is dark-only. Bug-report sheet (long-press app-version chip) supports photo attachments.

---

## What just landed (this session — AT:R38)

**BL16 — Real account merge UX, end-to-end.** Saiful opened with `/start-fresh R` → AT:R38 plan-mode survey landed (16 active carry-overs from AT:R37, 0 open bugs). Picked **BL16** as the work, then the scope option "Full merge with data union" (over the safer "surface-only" alternative). Built backend + Flutter in one arc. **+2 work commits + 1 wrap = 3 new commits. 303 → 306 commits total. Backend tests 461 → 485 (+24). 0 Alpha promotes** — the AT:R36 + AT:R37 + AT:R38 backend stack still sits on Mac awaiting `GOOGLE_AUDIENCES` in `infra/alpha.env`. **Bug list still 0.** Carry-over #8 (BL16) **closed**.

### How the session ran

Plan-mode design ran through two `AskUserQuestion` prompts: (1) "what direction?" — picked BL16; (2) "how far this session?" — picked "Full merge with data union" over the surface-only and minimal-banner options, knowing the prompt itself flagged it as "multi-session scope; would spill." Backend landed first as one logical chunk (commit `f7a771a`), Flutter as a second chunk (commit `313179c`). No carry-over from AT:R37 worked on (Credit consumption, BL7, BL8, A29, Tier 2/3 translations, the gated Saiful-external items) — single-focus session.

### Commits in order

| Hash | What it does |
|---|---|
| `f7a771a` | **BL16 backend.** New `AuthVerifyResponse.adopted_from_user_id: UUID \| None` — populated when account-linking Phase 1 silently adopts a different user_id than the caller's bearer. New `account_adoption` `SubscriptionEventRow` written on every silent adoption (in magic-link / Apple / Google flows) — used by the merge routes as the authorisation proof. New `backend/app/services/merge_service.py` with `preview()` + `execute()`: single-transaction re-key across `journal_entries`, `sim_trades` + `sim_holdings` + `sim_portfolios`, `sim_watchlists`, `lessons_progress`, `agent_activations`, `one_on_one_messages`, `room_runs`, `bug_reports`, `mandates`, `user_overlays`, `overlay_edit_counts`, plus a tail re-key of any lingering `user_devices` and `DELETE` of the orphan user row. Conflict rules: target mandate wins on collision (orphan's dropped); if both have sim_portfolios keep target's + re-key orphan's trades into it; `LessonProgress`/`AgentActivation`/`SimWatchlist` skip dupes (target's row stays); `UserOverlay` keeps target's active version but re-keys orphan's overlays inactive; `OverlayEditCounter` sums on (user_id, agent_id) collision. New `app/api/auth.py` routes: `GET /v1/auth/merge/preview/{from_user_id}` + `POST /v1/auth/merge` — both gated on `_assert_adopter()` (looks up `account_adoption` event for caller; 403 otherwise) + orphan existence check (404 otherwise). Tests: new `test_merge_service.py` (14) + new `test_merge_routes.py` (10), plus retrofits in `test_auth_service.py` for the adopted_from assertion on 3 claim paths. The 3 claim methods' return type changed from `tuple[AuthUser, str]` to `tuple[AuthUser, str, UUID \| None]` — `test_auth_google.py` + `test_user_devices.py` got mechanical unpack fixes. |
| `313179c` | **BL16 mobile.** New `mobile/lib/models/merge.dart` with `MergePreview` + `MergeResult` mirroring the backend Pydantic shapes (including an `isEmpty` getter for the rare zero-row case). New `mobile/lib/screens/auth/merge_sheet.dart` — full-modal bottom sheet with the drag handle, "WELCOME BACK" title, pluralised bullet list ("12 journal entries · 3 sim trades · 1 mandate (yours stays)"), `[MERGE EVERYTHING]` (cyan FilledButton) + `[KEEP SEPARATE]` (outlined). Confirm hits `ApiClient.executeMerge()`; snackbar on success / failure. `ApiClient` gained `previewMerge(fromUserId)` + `executeMerge(fromUserId)`. `AuthVerifyResponse` gained `adoptedFromUserId: String?`. `AuthNotifier`'s 3 claim methods (`verifyMagicLink`, `signInWithApple`, `signInWithGoogle`) now return `ClaimOutcome { success, adoptedFromUserId }` instead of `bool` — `SignInScreen` routes all 3 success paths through a new `_afterClaim()` helper that conditionally pushes the merge sheet before popping. `AuthState` gained `previousUserId: String?` set transiently when `user.id` changes — `_AuthGate` listens via `ref.listen` and invalidates `simNotifierProvider`, `journalNotifierProvider`, `journalTrashNotifierProvider`, `mandateNotifierProvider`, `watchlistNotifierProvider`, `lessonsNotifierProvider` on every flip so per-user Riverpod caches don't render stale after a user_id swap. New centralised `_commitUserChange()` helper inside `AuthNotifier` writes `previousUserId` consistently. ARB +14 keys (`mergeSheet*`) including 5 pluralised counts. AR/MS auto-fall-back per i18n policy. `flutter analyze` clean (2 pre-existing infos in `floor_placeholder_screen.dart`, unrelated). |

Plus the `chore(handover): wrap AT:R38` commit.

### What changed in the codebase

Backend (services + routes):
- `backend/app/services/auth_service.py` — new `_log_adoption_event()`; 3 claim methods now return `(user, token, adopted_from)`; `_claim_or_create()` computes `adopted_from` from `pre_claim_uid` vs returned `user.id`.
- `backend/app/services/merge_service.py` (NEW) — `MergeService.preview()` + `execute()` + per-relation helpers (`_count`, `_count_holdings`, `_has_mandate`, `_rekey_all`, `_rekey_skipping_conflicts`, `_merge_overlay_counts`, `_rekey_user_overlays`).
- `backend/app/api/auth.py` — 3 claim routes unpack the new 3-tuple + populate `AuthVerifyResponse.adopted_from_user_id`; new `_assert_adopter()` + 2 merge routes (`GET preview/{from}`, `POST /merge`).
- `backend/app/schemas/auth.py` — `AuthVerifyResponse.adopted_from_user_id` (new field), `MergeAccountRequest`, `MergePreview`, `MergeResult` (NEW).

Backend (tests):
- `backend/tests/unit/test_merge_service.py` (NEW) — 14 tests covering preview counts, full execute, idempotency, mandate-conflict (both directions), sim-portfolio merge with conflict, lessons-progress dedup, overlay deactivation, overlay version collision, overlay-count summing, post-merge orphan cleanup.
- `backend/tests/unit/test_merge_routes.py` (NEW) — 10 tests covering adopted-from signal on Apple + magic-link (Google mirrors), preview happy path + 403 + 404 + 401, execute happy + 403 + 404. Uses a `_FakeAppleVerifier` test double swapped into the singleton.
- `backend/tests/unit/test_auth_service.py` + `test_auth_google.py` + `test_user_devices.py` — mechanical 2-tuple → 3-tuple unpack fixes (12 each in the first two files); one new assertion (`adopted == new_device_uid` in the adoption test).

Mobile:
- `mobile/lib/models/auth.dart` — `AuthVerifyResponse.adoptedFromUserId` field + JSON parsing.
- `mobile/lib/models/merge.dart` (NEW) — `MergePreview` + `MergeResult`.
- `mobile/lib/services/api/api_client.dart` — import `merge.dart`, `previewMerge()` + `executeMerge()`.
- `mobile/lib/state/auth_providers.dart` — `AuthState.previousUserId`, `ClaimOutcome`, `_commitUserChange()` helper, 3 claim methods now return `ClaimOutcome`.
- `mobile/lib/screens/auth/merge_sheet.dart` (NEW) — `showMergeSheet()` + `_MergeSheet` widget.
- `mobile/lib/screens/auth/sign_in_screen.dart` — import + `_afterClaim()` + all 3 success paths.
- `mobile/lib/app.dart` — imports for the 5 invalidated providers + `ref.listen<AuthState>` in `_AuthGate.build()`.
- `mobile/lib/l10n/app_en.arb` + regenerated `app_localizations_{en,ar,ms}.dart` — 14 new keys.

### Carry-overs for AT:R39

Top-priority (gated on Saiful's external Android setup — **unchanged from AT:R37 wrap**):

1. **Saiful Android setup** (parallelizable, days of real-world lead time):
   - Register Play Console account ($25, individual)
   - `keytool -genkey -v -keystore ~/.android-keys/ami-trade-upload.keystore -alias upload -keyalg RSA -keysize 2048 -validity 10000` → backup to 1Password → extract SHA-1
   - GCP Console: enable Google Sign-In API, create Android client (package + SHA-1), create Web client → put Web client_id into `infra/alpha.env` as `GOOGLE_AUDIENCES` + pass to build script as `GOOGLE_OAUTH_WEB_CLIENT_ID`
   - Produce 3 icon source PNGs (see prompt in `~/.claude/plans/giggly-knitting-harbor.md`), drop at `mobile/assets/icon/`, run `flutter pub run flutter_launcher_icons`
2. **Promote backend (now three sessions stacked).** Mac carries AT:R36 (`/v1/auth/google` + `GoogleOIDCVerifier`), AT:R37 (lockout migration `f8b5d1c00011`, rate limiter, streaming uploads), and AT:R38 (merge service + 2 merge routes + `account_adoption` event type + `adopted_from_user_id` response field) all unshipped. `/promote-to-alpha` ships everything in one go once `GOOGLE_AUDIENCES` is filled. Smoke-check ALL of it: 400 on malformed Google token, 429 on `/v1/auth/anon` after 11 calls, magic-link lockout after 5 wrong codes, `POST /v1/auth/merge` 403 from a non-adopter bearer.
3. **First Play Console AAB upload.** After keystore + GCP + Play Console account are live: `scripts/build_playstore.sh` produces signed AAB → upload via Play Console web UI (mandatory-manual for Play App Signing enrollment) → fill Data Safety form + Content Rating questionnaire + screenshots → add internal testers → roll out.
4. **Samsung A17 device validation** (~1 week out): install internal-track build, smoke-test golden path (Concierge → Google Sign-In → claim → 1-on-1 / Brief / Floor → Sentry crash → RTL Arabic spot-check → bug report).

Non-gated work (from the AT:R37 list, BL16 now removed):

5. **Credit consumption emission.** `credits_consumed` event type already exists in `subscription_events`; nothing emits it. Wire Room + 1-on-1 to emit on completion (probably after the access-level design lands per the back-office "Deferred" note).
6. **BL7 — Agent metadata routes.** API for client-side rendering of agent profiles.
7. **BL8 — Room run cancel + replay.** Backend: cancel an in-flight room run, replay a completed one.
8. **A29 light-mode refactor.** Settings → APPEARANCE is dark-only; the canonical theme already has a `light_*.dart` token sibling but the surfaces aren't switched.

BL16 followups (deferred from AT:R38's "out-of-scope" list — only land if/when users ask for them):

9. **Per-bucket merge toggles.** Today's sheet is all-or-nothing; followup would let the user toggle journal in, sim out, etc.
10. **Mandate-conflict UX.** Today the target mandate wins silently when both have one; followup would show a side-by-side compare + pick.
11. **Settings "Merged accounts" history section.** Surface the `account_adoption_merged` SubscriptionEventRows in Settings so the user can audit past merges + re-trigger a missed KEEP-SEPARATE.
12. **KEEP-SEPARATE orphan cleanup job.** When the user picks KEEP SEPARATE the orphan stays in the DB indefinitely; add a TTL deletion job.
13. **Admin merge endpoint.** Currently the merge is end-user-driven only; a support flow would need `POST /v1/admin/users/{id}/merge`.
14. **Undo a merge within N hours.** Requires a per-row audit log of original `user_id` — not landed today.

Carrying from AT:R35 (still gated on a decision):

15. **Re-run Tier 2 sequentially.** `scripts/translate_content_lan.py --type glossary` (~50 min), then `--type ai_coach`, then `--type daily_challenges`. ~5h vLLM-blocking. Loaders are now ready (AT:R37, `bdea6e8`) — landing the content is a single-script run, but it monopolises the GPU.
16. **Re-think Tier 3 (lessons) approach.** Sequential = ~28h GPU. Options: (a) per-lesson concurrency, (b) bigger batches across lessons, (c) accept 28h over multiple sessions, (d) defer to v1.0. Saiful's call.

Carrying from AT:R34 / earlier (unchanged):

17. TF `+27` cold-launch loading loop on iPhone 17 — watch item.
18. External TestFlight launch (needs Beta App Description from Saiful + ~24h Apple review).
19. **BL6** — Mandate resolve flow (Liquidate/Postpone/Override). Needs a design pass first.
20. **BL11** — push (FCM/APNs) + in-app trial-end UX. Push gated on FCM/APNs config; in-app part doable solo.
21. **BL4** — Arabic → Gemini routing.
22. **Animation production** — 15 `<Animation>` MDX tags.

(Drops from AT:R37 carry-over list this session: **#8 BL16 — Real account merge UX**. AT:R37 had 17 items; AT:R39 list is 16 active carry-overs + 6 BL16 followups.)

### Watch items (not tasks)

- **Three sessions of backend now stacked unshipped on Mac.** When `/promote-to-alpha` finally runs, it'll ship: AT:R36 (`/v1/auth/google` + `GoogleOIDCVerifier` + `OIDCVerifier.issuers` list refactor), AT:R37 (migration `f8b5d1c00011` for `auth_challenges.attempts`, rate-limit dep on 3 routes, streaming uploads on `/v1/feedback/bug`), AT:R38 (`MergeService`, 2 new merge routes, `account_adoption` event type, `adopted_from_user_id` response field). Smoke-check ALL of them, not just the marquee features.
- **`/v1/auth/google` still rejects every token until `GOOGLE_AUDIENCES` is populated** on melehost. Safe default — empty audiences fail the manual membership check inside `OIDCVerifier.verify()`.
- **No migration ships this session.** BL16 adds zero schema (all the merge logic operates on existing tables + writes a row to the existing `subscription_events` table with a new `event_type` string). Promotion is service + route + Pydantic shape only — `alembic upgrade head` is a no-op for AT:R38.
- **`MergeService.execute()` deletes the orphan `User` row at the end.** That's intentional + final; AT:R38 has no undo. Followup #14 tracks the undo gap.
- **Cache invalidation can fire on a fresh sign-out + sign-back-in too** — `_AuthGate` listens for any `previousUserId != null` tick, including sign-back-in-as-the-same-user (in which case nothing actually changed, so the invalidation just re-fetches per-user state from the same backend rows — wasted IO but correct). Cold app launches don't trigger it (initial state has `user == null`).
- **`KEEP SEPARATE` leaves the orphan user_id forever.** The user can't currently re-trigger the sheet later — it's a one-shot offer at sign-in time. If they accidentally tap KEEP SEPARATE they lose access to the prompt. Followup #11 (Settings history section) is the natural rescue UI.
- **3 untranslated keys on AR, 4 on MS** (was 2 / 3; added 14 `mergeSheet*` keys this session — AR + MS need 14 more). They fall back to EN automatically. Non-blocking per CLAUDE.md i18n policy.
- **vLLM saturation pattern.** A single H100-class GPU comfortably serves 1-2 concurrent long-form generation streams; 4 streams blow per-stream latency past 300s. Sequential is the safe path.
- **Rate limiter is per-process.** When the backend scales beyond one container, the 10/3/5-per-minute caps become per-replica rather than global. Either accept (means an attacker hitting N replicas gets N× the budget) or move state to Redis. Not urgent at alpha.
- **Saved worktree patches.** `.claude/worktree-salvage/exciting-shtern-lessons-landing-spec.patch` (lessons landing redesign spec) and `.claude/worktree-salvage/magical-edison-280-lesson-edits.diff` (280 lesson files with "training simulator" reframing) are kept locally under gitignore. Inspect if anything reads stale, then delete.

---

## How to start the next session

```
/start-fresh R
```

The slash command reads `HANDOVER_R.md` + `docs/10_delivery/project_plan.md`, runs the configured sanity checks (Alpha health curl), queries the live bug list (currently **0 open**), then enters plan mode asking what to work on.

Session name to use: **AT:R39** (this is handover #38).

If Alpha is down at session start, `/start-fresh` will surface that and tell you the melehost debug commands.

If the first message is a specific task ("fix this", "add that"), skip `/start-fresh` and just do the task — the slash command is for the "let's keep going" opening.

Quick-win candidates for next session (in priority order):

1. **Promote backend (now AT:R36 + AT:R37 + AT:R38 stacked).** Once Saiful has filled `GOOGLE_AUDIENCES` in `infra/alpha.env`, `/promote-to-alpha` ships in one go: `/v1/auth/google`, magic-link lockout migration `f8b5d1c00011`, rate limiter, streaming uploads, **BL16 merge stack (`MergeService` + 2 merge routes + `account_adoption` event + `adopted_from_user_id` response field)**. Smoke-check ALL of them: 400 on malformed Google token, 429 on `/v1/auth/anon` after 11 calls, magic-link rejected on the 5th wrong code, `POST /v1/auth/merge` returns 403 from a non-adopter bearer.
2. **First Play Console AAB** if Saiful has the keystore + GCP clients + Play Console account ready. `scripts/build_playstore.sh` produces the AAB; manual upload completes Play App Signing enrollment.
3. **Credit consumption emission** (#5) — `credits_consumed` event type exists, nothing emits it. Wire Room + 1-on-1.
4. **Tier 2 sequential translation run** (#15) — loaders are ready (`bdea6e8`). `scripts/translate_content_lan.py --type glossary` (~50 min), then `--type ai_coach`, then `--type daily_challenges`. ~5h vLLM-blocking; own session.
5. **External TestFlight launch** (#18) — Beta App Description from Saiful + ~24h Apple review.
6. **BL7 / BL8 / A29** — remaining backlog. Each is moderate scope; pick based on energy.
7. **BL16 followups** (#9–#14) — per-bucket merge toggles, Settings "Merged accounts" history, KEEP-SEPARATE orphan TTL cleanup, etc. Only land if users actually ask.

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
