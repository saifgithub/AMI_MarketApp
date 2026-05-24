# Handover — AMI Trade build session

**Last updated:** 2026-05-24 (end of AT:R40 — **Ticker Detail screen: v1 ships + grilling session designs Bundles 2-5 + Bundle 1 (UX restructure) lands**). Mobile-only session, no backend changes. First commit `5fa9037` introduced `HoldingDetailScreen` (tap a holding card on Portfolio → full detail view with position summary + agent quick-actions + per-ticker trade history + COMING SOON placeholder). Long `/grill-me` design pass then locked the full Ticker Detail design across 13 questions: one adaptive screen for held + watched + (rare) neither states; section order = Status → Chart → Actions → Earnings → News → Trades; adaptive chart (candlestick short / line long) + 6-button period selector (1D/1W/1M/3M/1Y/5Y, default 1M); fullscreen landscape chart route triggered by both expand-button AND device-rotation auto-push; actions row redesigned to primary full-width green button (TRADE / TRADE MORE adaptive) + secondary chip row (ASK / CONVENE / WATCH-toggle / CLOSE-conditional); yfinance-backed news (5 headlines, external Safari, 5-min cache) + earnings chip (date + EPS estimate, 90-day cutoff, 6h cache). Locked sequencing as Plan Y: Bundle 1 (UX restructure) this session, Bundle 2+3 (chart portrait + landscape) AT:R41, Bundle 4+5 (news + earnings) AT:R42. Second commit `a8b8523` shipped Bundle 1: rename HoldingDetail → TickerDetail, new `_WatchingCard` variant, primary-button + chip-row layout, watchlist row reroute (no longer opens `WatchlistSheet`; sheet stays alive for ticker-tape path), `SEE CHART` secondary button on the Room verdict card (shown in all 3 verdict states). 13 new `tickerDetail*` l10n keys + `roomVerdictSeeChart`. **+2 work commits + 1 wrap = 3 new commits. 308 → 311 commits. Backend tests unchanged at 485** (no backend code touched). **Bug list still 0.** No promote this session — Bundle 1 is mobile-only; no new Alpha tag. AT:R39 wrap rotated into [history_R.md](history_R.md). Plan file at `~/.claude/plans/r-partitioned-breeze.md` captures the full design.

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **311 commits** (2 work + 1 wrap = 3 new this session), no remote yet |
| Latest work commit | `a8b8523` — feat(mobile): TickerDetail Bundle 1 — rename + Watching card + actions row redesign + watchlist+verdict entry points (AT:R40) |
| Alpha tags | **No new tag this session** — Bundle 1 is mobile-only; chart/news/earnings (Bundles 2-5) ship next sessions. Last tag remains `alpha-2026-05-24-1` (AT:R39 promote carrying AT:R36+R37+R38). |
| Backend tests | **485 passed, 0 failed** — unchanged this session (no backend code touched). |
| Mobile pubspec | **`0.1.0+27`** — unchanged (build bump deferred to first real Play Store AAB upload). |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **342 i18n keys** (+13 `tickerDetail*` this session + `roomVerdictSeeChart`). **Tier 1 ARB AR + MS via on-prem Gemma 4 31B**; the new keys fall back to EN until next translate pass. Tier 2 + Tier 3 content remain EN-only; loaders are ready when translated subdirs land. |

```
$ git log --oneline | head -15
a8b8523 feat(mobile): TickerDetail Bundle 1 — rename + Watching card + actions row redesign + watchlist+verdict entry points (AT:R40)
5fa9037 feat(mobile): Holding Detail screen v1 — position summary + quick actions + per-ticker history (AT:R40)
1f0170c chore(handover): wrap AT:R39
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

## What just landed (this session — AT:R40)

**Ticker Detail screen — v1 ships, design grilling locks Bundles 2-5, Bundle 1 (UX restructure) lands.** Saiful opened with `/start-fresh R` and answered the plan-mode survey with "we need to look at what other functions a good stock trading app should have." That kicked off a gap analysis (see `~/.claude/plans/r-partitioned-breeze.md`) which recommended a Tier-1 "Holding Detail" bundle (holding-detail screen + chart + news/earnings) as the biggest unlock per session — each gives a previously-theatrical agent (Technician, News, Macro) actual data to talk over. Saiful approved, picked Tier 1, deferred push-alerts (BL11 gating). Session then shipped **two work commits + one wrap = 3 new commits, 308 → 311**. Backend untouched. No promote.

### How the session ran

Three phases:

**Phase 1 — Holding Detail v1 (commit `5fa9037`).** Built a full-screen detail view reachable by tapping any holding card on Portfolio. Lays out position summary (qty / avg cost / mark / value / unrealised P&L / opened) + 4-chip quick-actions row (TRADE MORE / ASK MARKET ANALYST / CONVENE / CLOSE POSITION with confirm dialog) + per-ticker trade history + COMING SOON placeholder. Extracted `TradeRow` widget (was `_TradeRow` private in portfolio_screen.dart) to `lib/widgets/trade_row.dart` so both Portfolio + Holding Detail render trades identically. 13 new `holdingDetail*` l10n keys with context comments.

**Phase 2 — `/grill-me` design pass.** Saiful asked "should be holding details or watch list ? or both ? how ro we change period?" and requested the grilling skill. Walked 13 questions one at a time, decision-tree style, each with a recommended answer and pushback. Locked decisions in order: Q1 Purpose=D (one screen, decision-support primary); Q2 Entry points=portfolio holdings + watchlist only (Room verdict added later as Q8); Q3 Section order = Status → Chart → Actions → Earnings → News → Trades; Q4 Chart=adaptive (candlestick 1D/1W/1M, line 3M/1Y/5Y) + volume bars + 220pt portrait + no indicators in v2; Q5 Landscape=A+C pattern (fullscreen route + expand button + device-rotation auto-push; main.dart's portraitUp lock relaxes per-route); Q6 Period selector=6 buttons (1D/1W/1M/3M/1Y/5Y, default 1M, per-session-only); Q7 Watching card variant=big price + day-change% + italic note + Added date; Q8 Room verdict=secondary "SEE CHART" button shown in all 3 verdict states; Q9+Q10 Actions row=primary full-width green button (TRADE / TRADE MORE adaptive) + secondary chip row (ASK/CONVENE/WATCH-toggle/CLOSE-conditional) — 5 chips wouldn't fit iPhone 13 mini width, so split primary/secondary; Q11 News=yfinance, 5 headlines, headline+publisher+relative-time, external Safari via url_launcher, hide-on-empty, 5-min server cache; Q12 Earnings=yfinance, date + EPS estimate, 90-day cutoff, no-tap inline amber pill, 6h server cache; Q13 Sequencing=Plan Y (Bundle 1 this session, Bundle 2+3 chart portrait+landscape AT:R41, Bundle 4+5 news+earnings AT:R42).

**Phase 3 — Bundle 1 (commit `a8b8523`).** UX restructure of v1, no chart/news/earnings yet. (a) `git mv` holding_detail_screen.dart → ticker_detail_screen.dart; rename class + all internal refs. (b) New `_WatchingCard` variant for watched-not-held tickers (amber accent, big price, italic note, "Added DATE"); `_PositionCard` wins when held (strictly more informative); `_EmptyStateCard` handles the rare mid-session "closed AND removed-from-watchlist" state. Priority: held > watched > neither. (c) Actions row redesigned as `_PrimaryAction` (full-width green ElevatedButton, TRADE/TRADE MORE adaptive) + `_SecondaryActions` (Wrap of 4 chips with short labels: ASK / CONVENE / WATCH / CLOSE-conditional). WATCH chip uses outlined-vs-filled star to signal state. (d) Portfolio `_WatchlistRow.onTap` now pushes `TickerDetailScreen` instead of `showWatchlistSheet`; ticker-tape still uses the sheet (intentional — Q2 lock). (e) Room verdict card gained `SEE CHART` OutlinedButton below the existing CTA (cyan-outlined, `Icons.show_chart`); pushes TickerDetail. (f) L10n: mechanical rename `holdingDetail*` → `tickerDetail*`, plus new keys for Watching card / short chip labels / chart-placeholder / SEE CHART. AR + MS auto-fall-back per i18n policy.

`flutter analyze` clean modulo the 2 pre-existing infos on `floor_placeholder_screen.dart`. `flutter test` green.

### Commits in order

| Hash | What it does |
|---|---|
| `5fa9037` | **Holding Detail screen v1.** New `mobile/lib/screens/sim/holding_detail_screen.dart` (later renamed to `ticker_detail_screen.dart` in Bundle 1) — full-screen detail view reachable from Portfolio holding cards. Position summary card + 4-chip quick-actions row (TRADE MORE / ASK / CONVENE / CLOSE) + per-ticker trade history + COMING SOON placeholder. Extracted `TradeRow` to `lib/widgets/trade_row.dart` (shared with Portfolio's trade list). 13 new `holdingDetail*` l10n keys. `_HoldingCard` on portfolio_screen.dart wraps in `InkWell` + chevron-right glyph + pushes to the new screen. |
| `a8b8523` | **TickerDetail Bundle 1 — UX restructure.** Pure UX work, no new content widgets yet. (1) Rename HoldingDetail → TickerDetail (file via `git mv`, class, l10n keys). (2) New `_WatchingCard` variant (amber, big price, day-change%, italic note, Added date) for watched-not-held users; `_PositionCard` priority on held; `_EmptyStateCard` for the rare mid-session neither state. (3) Actions row split into `_PrimaryAction` (full-width green ElevatedButton, TRADE / TRADE MORE adaptive) + `_SecondaryActions` (4-chip Wrap: ASK / CONVENE / WATCH-toggle / CLOSE-conditional). WATCH chip uses Icons.star vs Icons.star_border to signal current watchlist state. (4) `_WatchlistRow.onTap` on Portfolio reroutes to TickerDetailScreen instead of `showWatchlistSheet`; sheet stays alive (ticker_tape.dart:158 still uses it). (5) `_VerdictCard` on Room gained SEE CHART OutlinedButton below primary CTA, shown in all 3 verdict states (approve+no-trade, approve+traded, reject). (6) `holdingDetail*` l10n keys renamed to `tickerDetail*` + new keys for Watching card / short chip labels / chart-placeholder / `roomVerdictSeeChart`. |

Plus the `chore(handover): wrap AT:R40` commit. **No backend code, no migrations** authored this session — pure mobile UX work.

### What changed in the codebase

Repo-tracked (in addition to the Silent_Scout/* changes that landed in parallel and rode along on the wrap commit per Saiful's call):

| File | Change |
|---|---|
| `mobile/lib/screens/sim/ticker_detail_screen.dart` | NEW (renamed from `holding_detail_screen.dart`) — full TickerDetail screen with adaptive Status card (Position/Watching/Empty) + primary+secondary actions + chart placeholder + per-ticker trades + COMING SOON card |
| `mobile/lib/widgets/trade_row.dart` | NEW — extracted from portfolio_screen.dart's private `_TradeRow`. Shared by Portfolio + TickerDetail |
| `mobile/lib/screens/sim/portfolio_screen.dart` | `_HoldingCard` wraps in InkWell + chevron-right + pushes TickerDetail; `_WatchlistRow._showRowSheet` now pushes TickerDetail instead of calling showWatchlistSheet; import of watchlist_sheet.dart removed; duplicate `_TradeRow` deleted |
| `mobile/lib/screens/room/room_screen.dart` | Import TickerDetailScreen; `_VerdictCard.build` gained a SEE CHART OutlinedButton at the bottom of the Column (outside the `if (isApprove)` conditional → shown in all verdict states) |
| `mobile/lib/l10n/app_en.arb` | +13 `tickerDetail*` keys (mechanical rename from `holdingDetail*` + new ones for Watching card variant, short chip labels, chart placeholder) + `roomVerdictSeeChart`. AR/MS unchanged — auto-fall-back per i18n policy. |
| `mobile/lib/generated/l10n/app_localizations*.dart` | Regenerated via `flutter gen-l10n` |

Plus the Silent_Scout/* parallel-track files (11 new backlog directories under `Silent_Scout/0[89]_*` + `1[012345678]_*` mirroring the AT:R40 gap analysis; README updated). Per CLAUDE.md these are research-only and do not import from or affect production. Riding along on this wrap so the working tree is clean for AT:R41.

Plan file: `~/.claude/plans/r-partitioned-breeze.md` — full gap analysis + 13-question grilling decisions + Plan Y sequencing.

### Carry-overs for AT:R41

**Top-priority — finish the Ticker Detail surface (THE work track):**

1. **Bundle 2 — Chart portrait.** fl_chart 0.69.0 already in pubspec. Candlestick widget for 1D/1W/1M periods + line widget for 3M/1Y/5Y (adaptive switch in `_chartType(period)`). Volume bars below the price chart always. 220pt fixed height. Crosshair on touch-drag. Loading skeleton + "Chart unavailable" error state. Period selector = 6 pill chips (1D/1W/1M/3M/1Y/5Y), default 1M, per-session-only. New backend route `GET /v1/sim/history/{ticker}?period=1m` returning `[{ts, open, high, low, close, volume}]` with 60s server cache.
2. **Bundle 3 — Landscape fullscreen chart.** Paired with Bundle 2 (same session). New `ChartFullscreenScreen` widget, locked to `landscapeLeft + landscapeRight` via per-route `SystemChrome.setPreferredOrientations`. Expand button on the portrait chart card. Device-rotation auto-push (rotate to landscape on TickerDetail → push fullscreen; rotate back → pop). Dismiss via X button + swipe-down + system back. main.dart's `portraitUp` lock stays the default — only relaxes on this one route.
3. **Bundle 4 — Per-ticker news.** News section between Earnings chip and Trades on TickerDetail. yfinance Ticker.news, 5 headlines, headline + publisher + relative-time ("2h ago" / "Yesterday" / "3d ago"). Tap → external Safari via `url_launcher` (new dep). Hide-on-empty section. New backend route `GET /v1/sim/news/{ticker}?limit=5` with 5-min server cache.
4. **Bundle 5 — Earnings chip.** Inline amber pill between Actions and News on TickerDetail. yfinance Ticker.calendar. Format: "Q3 earnings · Jul 25 · est. EPS $2.04". 90-day cutoff (hide if next earnings > 90 days out). No-tap display-only. New backend route `GET /v1/sim/earnings/{ticker}` with 6h server cache.

**Saiful's external follow-ons** (do at his pace, all carried from AT:R39):

5. **Rotate the Android upload keystore password.** Original was shared in chat transcript — `keytool -storepasswd -keystore ~/.android-keys/ami-trade-upload.keystore`. Save new pw to 1Password.
6. **Write `~/.android-keys/keystore.properties`** with `storeFile` (absolute), `storePassword`, `keyAlias=upload`, `keyPassword`. Without this file, `scripts/build_playstore.sh` falls back to debug signing.
7. **Export `GOOGLE_OAUTH_WEB_CLIENT_ID`** in `~/.zshrc` (told him to in AT:R39; verify with `echo $GOOGLE_OAUTH_WEB_CLIENT_ID` next session).
8. **Confirm Play Console approval** (signup submitted AT:R39 — 1-48h SLA).

**Play-Console-approval-gated next work:**

9. **First Play Console AAB upload.** After items 5-8: `scripts/build_playstore.sh` produces signed AAB → manual upload via Play Console web UI (completes Play App Signing enrollment) → fill Data Safety + Content Rating + screenshots → add internal testers.
10. **Samsung A17 device validation** (~1 week out from delivery). First real-world Google Sign-In e2e test.
11. **Icons** (carry-over since AT:R36): 3 source PNGs at `mobile/assets/icon/`, then `flutter pub run flutter_launcher_icons`.

**Non-gated backend work** (pick based on energy):

12. **Credit consumption emission.** `credits_consumed` event type already exists in `subscription_events`; nothing emits it. Wire Room + 1-on-1.
13. **BL7 — Agent metadata routes.** API for client-side rendering of agent profiles.
14. **BL8 — Room run cancel + replay.** Backend: cancel an in-flight room run, replay a completed one.
15. **A29 light-mode refactor.** Settings → APPEARANCE is dark-only.

**BL16 followups** (deferred from AT:R38 — only land if/when users ask):

16. Per-bucket merge toggles · 17. Mandate-conflict UX · 18. Settings "Merged accounts" history · 19. KEEP-SEPARATE orphan cleanup TTL · 20. Admin merge endpoint · 21. Undo a merge within N hours.

**Carrying from AT:R35** (gated on decision):

22. Re-run Tier 2 sequentially (`scripts/translate_content_lan.py --type glossary` → `ai_coach` → `daily_challenges`, ~5h vLLM-blocking).
23. Re-think Tier 3 (lessons) approach. Sequential = ~28h GPU.

**Carrying from AT:R34 / earlier** (unchanged):

24. TF `+27` cold-launch loading loop on iPhone 17 — watch item. · 25. External TestFlight launch (needs Beta App Description). · 26. **BL6** — Mandate resolve flow. · 27. **BL11** — push (FCM/APNs) + in-app trial-end UX. · 28. **BL4** — Arabic → Gemini routing. · 29. **Animation production** — 15 `<Animation>` MDX tags.

(Net change vs. AT:R39 carry-overs: AT:R40 splits Bundles 2-5 (Ticker Detail follow-on work) out as items 1-4. Previous "Saiful Android setup" items 1-4 from AT:R39 demote to 5-8. AT:R39 had 25 items; AT:R40 has 29 — net +4 from the four Bundle items.)

### Watch items (not tasks)

- **TickerDetail v1 + Bundle 1 are iPhone-unverified.** Both commits ship structural changes (new screen + entry-point reroute) but neither has been built to device. Strong candidate for "build TestFlight + spot-check after Bundle 2+3 lands" — bundle the visual validation rather than rebuilding after each session.
- **`SEE CHART` button shown when verdict = REJECT.** Argued in Q8 as the *most* valuable state (no trade → research more). But it does mean the verdict card has a cyan button under an amber-rejection card; might read visually as "agents say no but go look anyway." Worth eyeing in real iPhone test.
- **Watchlist sheet split.** Portfolio watchlist rows now go to TickerDetail; ticker-tape rows still go to WatchlistSheet. Different entry points = different surface, intentional per Q2. May confuse users at first — they tap the same ticker from two surfaces and get two different UIs.
- **Adaptive TRADE / TRADE MORE label.** Held users see "TRADE MORE", watched-only see "TRADE". Right call linguistically but adds 1 more decision for the LLM (1-on-1 / Brief) to factor into screen-aware references.
- **CLOSE chip is conditional on `hasOpenTrades`.** Holdings with no open trade record (orphan position from an old migration?) would lose access to close. Existing positions all have trade records, so should be fine, but watch for edge cases.
- **`/v1/auth/google` is reachable but unreachable from clients today.** Backend route live; mobile Google button only shows on Android (D-057); no Android device until Samsung A17 arrives.
- **3 untranslated keys on AR, 4 on MS, plus the 13 new `tickerDetail*` + 1 `roomVerdictSeeChart` keys** (17 + 18 untranslated for AR/MS respectively as of this session). All fall back to EN automatically.
- **vLLM saturation pattern.** Single H100-class GPU comfortably serves 1-2 concurrent long-form generation streams; 4 streams blow per-stream latency past 300s.
- **Rate limiter is per-process.** When the backend scales beyond one container, the 10/3/5-per-minute caps become per-replica rather than global.
- **Saved worktree patches.** `.claude/worktree-salvage/exciting-shtern-lessons-landing-spec.patch` + `.claude/worktree-salvage/magical-edison-280-lesson-edits.diff` kept locally under gitignore.

---

## How to start the next session

```
/start-fresh R
```

The slash command reads `HANDOVER_R.md` + `docs/10_delivery/project_plan.md`, runs the configured sanity checks (Alpha health curl), queries the live bug list (currently **0 open**), then enters plan mode asking what to work on.

Session name to use: **AT:R41** (this is handover #40).

If Alpha is down at session start, `/start-fresh` will surface that and tell you the melehost debug commands.

If the first message is a specific task ("fix this", "add that"), skip `/start-fresh` and just do the task — the slash command is for the "let's keep going" opening.

Quick-win candidates for next session (in priority order):

1. **Bundles 2+3 — Chart portrait + landscape fullscreen** (#1+#2). The headline next move. Chart on the new TickerDetail screen + period selector + adaptive candlestick/line + volume bars + fullscreen-landscape route triggered by both expand button and device rotation. New backend route `/v1/sim/history` + 60s server cache. Tight coupling means ship together to avoid the "portrait-only chart" interim. Plan in `~/.claude/plans/r-partitioned-breeze.md`.
2. **TestFlight build + iPhone smoke** of v1 + Bundle 1 (and Bundle 2+3 if shipped same session) — magic-link / merge sheet / Holding-card → TickerDetail / Watchlist-row → TickerDetail / Room verdict → SEE CHART / actions row layout on iPhone 13 mini.
3. **Check Play Console approval status** + **confirm Saiful did the 3 follow-ons** (carry-overs 5-7): keystore password rotated, `keystore.properties` written, `GOOGLE_OAUTH_WEB_CLIENT_ID` exported in zshrc. Once clean we can build a real AAB.
4. **First Play Console AAB upload** (#9) — gated on Play Console approval + items in #3.
5. **Bundles 4+5 — News + Earnings** (#3+#4) — ship together; both yfinance-backed, similar backend pattern. Probably AT:R42.
6. **Credit consumption emission** (#12) — `credits_consumed` event type exists in `subscription_events`, nothing emits it. Wire Room + 1-on-1.
7. **Tier 2 sequential translation run** (#22) — loaders are ready. ~5h vLLM-blocking; own session.
8. **BL7 / BL8 / A29** — remaining backlog.

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
