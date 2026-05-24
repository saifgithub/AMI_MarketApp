# Handover — AMI Trade build session

**Last updated:** 2026-05-24 (end of AT:R39 — **Saiful registered as Google developer + the 3-session backend stack finally shipped**). Saiful did the external Google registrations end-to-end this session: GCP project + OAuth consent screen + Web client (`153141744056-03d6sa…`) + Android client (`153141744056-5aif1p…`, SHA-1 `91:B5:B7:DB:1F:AD:B9:79:9F:B6:57:84:FB:8B:18:3F:C6:09:9F:47`) all minted; Play Console individual signup submitted, pending Google's identity verification (1-48h). Android upload keystore created at `~/.android-keys/ami-trade-upload.keystore`. Web client_id landed in `infra/alpha.env` as `GOOGLE_AUDIENCES`. With audiences now populated, ran `/promote-to-alpha` → **`alpha-2026-05-24-1`** ships AT:R36 + AT:R37 + AT:R38 in one go. Migration `f8b5d1c00011` (auth_challenges.attempts) applied. All 6 smoke checks green: `/v1/health` 200, `/v1/llm/status` `active=vllm`, `/v1/sim/quote/AAPL` `source=yfinance`, `POST /v1/auth/google` 400 on malformed token, `POST /v1/auth/anon` 10×200 + 1×429 (rate limiter), `/v1/auth/merge` 401 unauth. **+1 work commit + 1 wrap = 2 new commits. Backend tests unchanged at 485** (no code changes this session — registrations + promote only). **Bug list still 0.** AT:R38 wrap is now in [history_R.md](history_R.md).

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **308 commits** (1 chore + 1 wrap = 2 new this session), no remote yet |
| Latest work commit | `d21b073` — chore: capture session-added permission allowlist entries (AT:R39). No production code changed; the session shipped registrations + promote. |
| Alpha tags | **NEW: `alpha-2026-05-24-1` shipped this session** — first promote since `alpha-2026-05-22-9` (AT:R34). Carries AT:R36 (`/v1/auth/google` + `GoogleOIDCVerifier`) + AT:R37 (lockout migration `f8b5d1c00011`, rate limiter, streaming uploads) + AT:R38 (merge service + 2 merge routes + `account_adoption` event + `adopted_from_user_id` response field). All 6 smoke checks green. |
| Backend tests | **485 passed, 0 failed** — unchanged this session (no backend code touched). |
| Mobile pubspec | **`0.1.0+27`** — unchanged (build bump deferred to first real Play Store AAB upload). |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **329 i18n keys**. **Tier 1 ARB AR (311/329) + MS (310/329) via on-prem Gemma 4 31B**; the 18 / 19 unfilled keys fall back to EN. Tier 2 + Tier 3 content remain EN-only; loaders are ready when translated subdirs land. |

```
$ git log --oneline | head -15
d21b073 chore: capture session-added permission allowlist entries (AT:R39)
4d913b9 chore(handover): wrap AT:R38
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
| Mac-side tests | `backend/.venv/bin/pytest backend/tests/unit/ -q` — **485 passed** (was 461; AT:R38 added +24 across `test_merge_service.py` + `test_merge_routes.py`). Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
| Env knobs (alpha) | `AMI_ENV=staging` + `SECRET_KEY=<64-hex>` + `ADMIN_SECRET=<64-hex>` (AT:R27, admin back-office bearer) + `SMTP_{HOST,PORT,USER,PASSWORD,FROM}` (5 vars, AT:R26 — now dormant) + **`RESEND_API_KEY=re_<…>`** (AT:R32, primary outbound mail route) + **`GOOGLE_AUDIENCES=<web_client_id_csv>`** (AT:R36, D-057 — **populated AT:R39 with the GCP OAuth Web client_id** `153141744056-03d6sa…`; live on melehost since `alpha-2026-05-24-1`). Canonical at `infra/alpha.env` on Mac, gitignored; shipped via `scp` in `/promote-to-alpha` step 4. Without `SECRET_KEY` the backend refuses to start when env != local. **Email transport**: `email_service` prefers Resend (HTTP API, port 443 — bypasses melehost's ISP block on outbound 25/587) when `RESEND_API_KEY` is set; falls back to SMTP if `SMTP_HOST` is configured; falls back to no-op otherwise. Verified live: magic-link delivered to Gmail end-to-end. |
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

## What just landed (this session — AT:R39)

**Saiful registered as Google developer + the 3-session backend stack finally shipped to Alpha.** Saiful opened with `/start-fresh R` → AT:R39 plan-mode survey landed (16 active carry-overs from AT:R38, 0 open bugs). Picked **carry-over #1 (Saiful Android setup)** — specifically "help me register as Google developer." Worked through GCP signup + OAuth client minting + Android upload keystore generation + populating `GOOGLE_AUDIENCES`. With audiences set, ran `/promote-to-alpha` → **`alpha-2026-05-24-1`** ships AT:R36 + AT:R37 + AT:R38 in one go. Migration `f8b5d1c00011` (auth_challenges.attempts) applied. All 6 smoke checks green. **+1 chore commit + 1 wrap = 2 new commits. 306 → 308 commits total. Backend tests unchanged at 485** (no backend code touched this session). **Bug list still 0.** Carry-over #2 (Promote backend, 3 stacked) **closed**; carry-over #1 (Saiful Android setup) **partially closed** (Play Console signup still pending Google's identity review; icons still pending).

### How the session ran

Saiful picked "help me register as Google developer" from the plan-mode survey. The session walked through, in order: (a) Play Console individual signup — initiated, paid, ID under Google's review; gated on a phone number, resolved by using iPhone SMS; (b) GCP Console — created project, configured OAuth consent screen (External, scopes `openid`/`email`/`profile`), minted Web client (`153141744056-03d6sa…`) + Android client (`153141744056-5aif1p…`) with package `ai.agenticmarketintel.amiTrade`; (c) Android upload keystore generated at `~/.android-keys/ami-trade-upload.keystore` (RSA-2048, 10000-day cert, CN=`saiful said`, OU/O=`ATM Market Intel` — typo in metadata, never user-visible, not regenerating); (d) SHA-1 fingerprint extracted (`91:B5:B7:DB:1F:AD:B9:79:9F:B6:57:84:FB:8B:18:3F:C6:09:9F:47`) and pasted into the GCP Android client; (e) `GOOGLE_AUDIENCES` line added to `infra/alpha.env`. Mid-session I caught a gap and almost spun up a third (iOS) GCP OAuth client — Saiful corrected: **D-057 platform segregation already locks Apple-iOS-only / Google-Android-only** (re-read the decision log; confirmed `sign_in_screen.dart:272-280` already gates by `Platform.isIOS`/`isAndroid` — no code change, no iOS GCP client needed). With audiences populated, ran `/promote-to-alpha`: preflight clean (485 pytest passes, flutter analyze clean modulo 2 pre-existing infos), committed the harness-side `.claude/settings.local.json` permission additions as a chore (`d21b073`), tagged `alpha-2026-05-24-1`, rsync'd + scp'd + recreated + ran migration `f8b5d1c00011` + ran 6 smoke checks (3 standard + AT:R36 verifier + AT:R37 rate-limit-burst + AT:R38 merge-routes-401). All green. Total promote: ~5 minutes.

### Commits in order

| Hash | What it does |
|---|---|
| `d21b073` | **chore: capture session-added permission allowlist entries (AT:R39).** Single touched file: `.claude/settings.local.json` — appends two Bash permission entries added during the session (`/remote-control` invocation + the rejected `echo R > .claude/active-track` attempt from step 0 of `/start-fresh`). Harness-side state only; no code, no infra, never ships to melehost (rsync excludes `.claude/`). Committed before the promote so the working tree was clean. |

Plus the `chore(handover): wrap AT:R39` commit. **No backend code, no Flutter code, no migrations** authored this session — pure registration + deployment work.

### What changed in the codebase

Repo-tracked:
- `.claude/settings.local.json` — +2 permission allowlist entries (`Bash(/remote-control)` and `Bash(echo "R" > .claude/active-track && cat .claude/active-track)`). Harness state.

Gitignored (real outputs of the session):
- `infra/alpha.env` — new `GOOGLE_AUDIENCES=153141744056-03d6sabmvita0a2civs6e0ngjoac54v7.apps.googleusercontent.com` line at line 68, under a new `# ── Google Sign-In (D-057, AT:R36) ──` section header. Shipped to `melehost:~/ami_trade/.env` via `/promote-to-alpha` step 4.

Outside the repo (Saiful's external artifacts):
- `~/.android-keys/ami-trade-upload.keystore` — NEW upload keystore (10000-day RSA-2048).
- `~/.android-keys/keystore.properties` — **not yet written**; gated on Saiful rotating the keystore password (the original was shared in chat transcript — instructed to rotate via `keytool -storepasswd` + write the properties file with the new password).
- `~/.zshrc` — **Saiful told to `export GOOGLE_OAUTH_WEB_CLIENT_ID=…`**; unverified whether he did.
- GCP project: new OAuth consent screen + Web client + Android client.
- Play Console: individual developer account signup submitted; **pending Google's identity verification (1-48h SLA)**.

### Carry-overs for AT:R40

**Saiful's external follow-ons from THIS session** (do at his pace):

1. **Rotate the keystore password.** The original was shared in chat transcript — `keytool -storepasswd -keystore ~/.android-keys/ami-trade-upload.keystore`. Save the new password to 1Password.
2. **Write `~/.android-keys/keystore.properties`** with `storeFile` (absolute), `storePassword`, `keyAlias=upload`, `keyPassword`. Without this file, `scripts/build_playstore.sh` falls back to debug signing (won't be accepted by Play Console).
3. **Export `GOOGLE_OAUTH_WEB_CLIENT_ID`** in `~/.zshrc` (told him to; verify with `echo $GOOGLE_OAUTH_WEB_CLIENT_ID` next session).
4. **Confirm Play Console approval** (1-48h after submission).

**Top-priority next-session work** (Play Console-approval-gated):

5. **First Play Console AAB upload.** After items 1-4 above: `scripts/build_playstore.sh` produces signed AAB → upload via Play Console web UI (mandatory-manual for Play App Signing enrollment) → fill Data Safety + Content Rating + screenshots → add internal testers → roll out.
6. **Samsung A17 device validation** (~1 week out from delivery): install internal-track build, smoke-test golden path (Concierge → Google Sign-In → claim → 1-on-1 / Brief / Floor → Sentry crash → RTL Arabic spot-check → bug report). **First real-world Google Sign-In e2e test** — until the A17 lands, AT:R36 backend is unreachable from any device Saiful has (iPhone doesn't show the Google button per D-057).
7. **Icons** (carry-over since AT:R36): 3 source PNGs at `mobile/assets/icon/` per prompt in `~/.claude/plans/giggly-knitting-harbor.md`, then `flutter pub run flutter_launcher_icons`.

**Non-gated backend work** (pick based on energy):

8. **Credit consumption emission.** `credits_consumed` event type already exists in `subscription_events`; nothing emits it. Wire Room + 1-on-1 to emit on completion. Probably gated on access-level design landing per back-office "Deferred" note.
9. **BL7 — Agent metadata routes.** API for client-side rendering of agent profiles.
10. **BL8 — Room run cancel + replay.** Backend: cancel an in-flight room run, replay a completed one.
11. **A29 light-mode refactor.** Settings → APPEARANCE is dark-only; the canonical theme already has a `light_*.dart` token sibling but the surfaces aren't switched.

**BL16 followups** (deferred from AT:R38's "out-of-scope" list — only land if/when users ask for them):

12. **Per-bucket merge toggles.** Today's sheet is all-or-nothing.
13. **Mandate-conflict UX.** Today target mandate wins silently when both have one; followup would show a side-by-side compare + pick.
14. **Settings "Merged accounts" history section.** Surface `account_adoption_merged` events so the user can audit + re-trigger a missed KEEP-SEPARATE.
15. **KEEP-SEPARATE orphan cleanup job.** Orphan stays in DB indefinitely; add a TTL.
16. **Admin merge endpoint.** Support flow would need `POST /v1/admin/users/{id}/merge`.
17. **Undo a merge within N hours.** Requires per-row audit log of original `user_id`.

**Carrying from AT:R35** (still gated on a decision):

18. **Re-run Tier 2 sequentially.** `scripts/translate_content_lan.py --type glossary` (~50 min), then `--type ai_coach`, then `--type daily_challenges`. ~5h vLLM-blocking. Loaders are ready since AT:R37.
19. **Re-think Tier 3 (lessons) approach.** Sequential = ~28h GPU. Options: per-lesson concurrency / bigger batches / accept 28h over multiple sessions / defer to v1.0. Saiful's call.

**Carrying from AT:R34 / earlier** (unchanged):

20. TF `+27` cold-launch loading loop on iPhone 17 — watch item.
21. External TestFlight launch (needs Beta App Description from Saiful + ~24h Apple review).
22. **BL6** — Mandate resolve flow (Liquidate/Postpone/Override). Needs a design pass first.
23. **BL11** — push (FCM/APNs) + in-app trial-end UX. Push gated on FCM/APNs config; in-app part doable solo.
24. **BL4** — Arabic → Gemini routing.
25. **Animation production** — 15 `<Animation>` MDX tags.

(Drops from AT:R38 carry-over list: **#2 Promote backend** — closed by `alpha-2026-05-24-1`. Carry-over **#1 partial close** — GCP + keystore + audiences done; Play Console approval + keystore.properties + icons split out as items 1-7 above. AT:R38 had 22 items; AT:R40 list has 25 — net +3 from the keystore/zshrc/Play-Console-confirm follow-ons.)

### Watch items (not tasks)

- **Keystore password lives in this session's transcript.** Saiful was told to `keytool -storepasswd` before writing `keystore.properties`. If he forgets, the password Google App Signing enrolls under is a known-leaked one — not catastrophic (the upload key only authenticates uploads, not end-user installs) but worth getting clean before first AAB upload.
- **Three sessions of backend stacked unshipped** — RESOLVED in `alpha-2026-05-24-1`. Watch the next 24h of melehost logs for AT:R36/R37/R38-specific error patterns: malformed Google token verifier errors (`google_audience_mismatch`, `invalid_signature`), rate-limit 429 spikes (means a client is hot-looping `/auth/anon`), merge route 403s (means an attacker is probing `/v1/auth/merge` without an `account_adoption` event).
- **`/v1/auth/google` is reachable but unreachable from clients today.** Backend route is live; mobile Google button only shows on Android (D-057); no Android device until Samsung A17 arrives. The route's first real client traffic will be from the A17 in ~1 week.
- **`MergeService.execute()` deletes the orphan `User` row at the end.** Intentional + final; no undo. Followup #17 tracks the undo gap.
- **`KEEP SEPARATE` leaves the orphan user_id forever.** One-shot offer at sign-in time; no rescue UI yet.
- **3 untranslated keys on AR, 4 on MS** (unchanged this session — no new ARB keys added). Fall back to EN automatically.
- **vLLM saturation pattern.** Single H100-class GPU comfortably serves 1-2 concurrent long-form generation streams; 4 streams blow per-stream latency past 300s.
- **Rate limiter is per-process.** When the backend scales beyond one container, the 10/3/5-per-minute caps become per-replica rather than global.
- **Saved worktree patches.** `.claude/worktree-salvage/exciting-shtern-lessons-landing-spec.patch` (lessons landing redesign spec) and `.claude/worktree-salvage/magical-edison-280-lesson-edits.diff` (280 lesson files with "training simulator" reframing) are kept locally under gitignore. Inspect if anything reads stale, then delete.

---

## How to start the next session

```
/start-fresh R
```

The slash command reads `HANDOVER_R.md` + `docs/10_delivery/project_plan.md`, runs the configured sanity checks (Alpha health curl), queries the live bug list (currently **0 open**), then enters plan mode asking what to work on.

Session name to use: **AT:R40** (this is handover #39).

If Alpha is down at session start, `/start-fresh` will surface that and tell you the melehost debug commands.

If the first message is a specific task ("fix this", "add that"), skip `/start-fresh` and just do the task — the slash command is for the "let's keep going" opening.

Quick-win candidates for next session (in priority order):

1. **Check Play Console approval status** + **confirm Saiful did the 3 follow-ons** (carry-overs 1-3): keystore password rotated, `keystore.properties` written, `GOOGLE_OAUTH_WEB_CLIENT_ID` exported in zshrc. Once those are clean we can build a real AAB.
2. **First Play Console AAB upload** (#5) — gated on Play Console approval + items in #1 above. `scripts/build_playstore.sh` produces signed AAB; manual upload completes Play App Signing enrollment.
3. **iPhone validation of yesterday's promote** — magic-link sign-in / merge sheet / sign-out / 1-on-1 / Brief on a real device against `alpha-2026-05-24-1`. Catches anything backend smoke missed.
4. **Credit consumption emission** (#8) — `credits_consumed` event type exists in `subscription_events`, nothing emits it. Wire Room + 1-on-1.
5. **Tier 2 sequential translation run** (#18) — loaders are ready (`bdea6e8`). `scripts/translate_content_lan.py --type glossary` (~50 min), then `--type ai_coach`, then `--type daily_challenges`. ~5h vLLM-blocking; own session.
6. **External TestFlight launch** (#21) — Beta App Description from Saiful + ~24h Apple review.
7. **BL7 / BL8 / A29** — remaining backlog. Each moderate scope.
8. **BL16 followups** (#12–#17) — per-bucket merge toggles, Settings "Merged accounts" history, KEEP-SEPARATE orphan TTL cleanup, etc. Only land if users actually ask.

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
