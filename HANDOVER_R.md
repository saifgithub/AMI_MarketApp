# Handover — AMI Trade build session

**Last updated:** 2026-05-25 (end of AT:R41 — TickerDetail Bundles 2 + 3 ship: adaptive candlestick/line chart with volume + crosshair, landscape fullscreen route, new `/v1/sim/history` route, promoted to Alpha). Narrative in [`history/AT_R0041.md`](history/AT_R0041.md).

Read this file **first** in any new session. It captures **current truth** + the carry-overs. Per-session narratives live in [`history/`](history/) — one file per /handover wrap, newest filename = newest session. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER_R.md = current state + carry-overs + Recent-sessions links. history/ = each session's wrap narrative as its own file. `/handover R` writes `history/AT_R<N>.md` per wrap; HANDOVER_R.md stays narrative-free.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **319 commits** (3 work + 1 build-bump + 1 wrap = 5 new this session), no remote yet |
| Latest work commit | `3be83ee` — chore(mobile): bump build 0.1.0+27 → 0.1.0+28 for TestFlight |
| Alpha tags | **`alpha-2026-05-25-1`** (AT:R41 promote — backend Bundle 2 only: new `/v1/sim/history` route + provider chain; mobile changes don't ship via /promote-to-alpha). Last prior tag: `alpha-2026-05-24-1` (AT:R39 promote carrying AT:R36+R37+R38). |
| Backend tests | **500 passed, 0 failed** (was 485; AT:R41 added +15 across `test_sim_history.py` — route + provider determinism + cache hits). |
| Mobile pubspec | **`0.1.0+28`** — bumped by `scripts/build_testflight.sh` for the AT:R41 TestFlight upload (first device validation since TickerDetail landed). |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **344 i18n keys** (net +2 this session: dropped `tickerDetailChartComingSoon`, added `tickerDetailChartUnavailable` + `tickerDetailChartExpand` + `tickerDetailChartClose`). **Tier 1 ARB AR + MS via on-prem Gemma 4 31B**; the new keys fall back to EN until next translate pass. Tier 2 + Tier 3 content remain EN-only; loaders are ready when translated subdirs land. |

```
$ git log --oneline | head -15
3be83ee chore(mobile): bump build 0.1.0+27 → 0.1.0+28 for TestFlight
2c868da feat(mobile): TickerDetail chart swap-in + landscape fullscreen route (AT:R41 Bundle 3)
b7ccaf9 feat(mobile): TickerChart widget — adaptive candlestick/line + volume + crosshair (AT:R41 Bundle 2 mobile)
62b4eea feat(sim): /v1/sim/history route + Candle + provider chain history() (AT:R41 Bundle 2 backend)
7302397 chore(config): per-track history_path → history_dir (AT:R40)
2d5ec10 chore(history): migrate history_R.md monolith → per-session files in history/ (AT:R40)
18af9cd chore(skills): history-folder refactor — per-session files, HANDOVER becomes current-state only (AT:R29)
a63cc36 chore(handover): wrap AT:R40
a8b8523 feat(mobile): TickerDetail Bundle 1 — rename + Watching card + actions row redesign + watchlist+verdict entry points (AT:R40)
5fa9037 feat(mobile): Holding Detail screen v1 — position summary + quick actions + per-ticker history (AT:R40)
1f0170c chore(handover): wrap AT:R39
d21b073 chore: capture session-added permission allowlist entries (AT:R39)
4d913b9 chore(handover): wrap AT:R38
313179c feat(auth): BL16 mobile — detect adoption + merge sheet + cache invalidation (AT:R38)
f7a771a feat(auth): BL16 backend — adoption signal + /v1/auth/merge endpoints (AT:R38)
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
| Routes | `/v1/health`, `/v1/auth/*` (incl. `DELETE /v1/auth/session` — Phase 4 sign-out, AT:R26; **`POST /v1/auth/google`** — D-057, AT:R36; **`GET /v1/auth/merge/preview/{from}`** + **`POST /v1/auth/merge`** — BL16, AT:R38), `/v1/admin/*` (9 routes — AT:R27, see "Admin back-office" below), `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/brief/*` (was `/v1/coach/*` — renamed AT:R27; legacy `/v1/coach/*` kept as deprecated alias logging `deprecated_coach_route_used`), `/v1/journal/*` (incl. `/trash`, `/{id}/restore`), `/v1/lessons/*`, `/v1/llm/status`, `/v1/mandate/*` (now incl. **`/{u}/audit`** — BL12, **`/{u}/versions`** + **`/{u}/versions/{v}`** + **`POST /{u}/rollback/{v}`** — BL5, all AT:R33), `/v1/room/*`, `/v1/sim/*` (now incl. **`POST /sim/preview`** — BL9, AT:R33; **`GET /sim/history/{ticker}?period=`** — AT:R41 Bundle 2, public/no-auth, 6 periods 1d/1w/1m/3m/1y/5y, 60s cache, returns `{ticker, period, source, candles: [{t, o, h, l, c, v}]}`, 422 on invalid period), `/v1/daily_challenge/*` (now incl. **`POST /{cid}/attempt`** — BL10, AT:R33), `/v1/watchlist/*`, `/v1/feedback/bug` (`multipart/form-data` with optional `file`). Plus a public HTML page at `/admin` (no auth required; the page itself asks for the `ADMIN_SECRET` bearer on first load + stores in localStorage). |
| Mac-side tests | `backend/.venv/bin/pytest backend/tests/unit/ -q` — **500 passed** (was 485; AT:R41 added +15 across `test_sim_history.py` — route per-period validation, mock-walk determinism, history cache hit/invalidate). Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
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
- **AT:R41 Bundle 2:** new `Candle(t, o, h, low, c, v)` NamedTuple + `MarketDataProvider.history(ticker, period)` protocol method, impl'd on every provider. `_PERIOD_MAP` in `market_data.py` centralises period → (yfinance period, interval, mock_walk count, seconds-per-candle). `VALID_PERIODS = (1d, 1w, 1m, 3m, 1y, 5y)` exported for route validation. `CachingProvider` carries a parallel 60s history TTL dict keyed `"TICKER:period"`; `invalidate()` sweeps both quote + history. `SimEngine.current_history(ticker, period) -> (list[Candle], source)` mirrors `current_quote`'s never-raises contract. Backend route `GET /v1/sim/history/{ticker}?period=` consumes it.

### Mobile app

| | |
|---|---|
| Bundle | `ai.agenticmarketintel.amiTrade` |
| pubspec version | **`0.1.0+28`** (repo). Carries everything from `+27` (Apple Phase 3 + entitlements + email+display_name persistence + BL1 device context + BL2 device_install_id + AT:R36 Google Sign-In wiring + AT:R37 sign-out UX / BL13 onboarding-session threading + AT:R38 BL16 merge UX) **PLUS AT:R40 TickerDetail v1 + Bundle 1 (Holding/Watching/Empty Status card + primary green button + 4-chip secondary row + entry-point reroutes from Portfolio holding cards / Watchlist rows / Room verdict SEE CHART)** **PLUS AT:R41 TickerDetail Bundles 2 + 3 (`TickerChart` widget: adaptive candlestick/line + volume + crosshair + 6-chip period selector; `ChartFullscreenScreen` landscape route with per-route orientation unlock; `OrientationBuilder` auto-push from TickerDetail).** Build bumped this session by `scripts/build_testflight.sh`. |
| TestFlight | **`0.1.0+27`** uploaded 2026-05-22 by Saiful. Verified live on both iPhone 17 (iPhone18,1, iOS 26.4.2) and iPhone 13 mini (iPhone14,4, iOS 18.7.1) — both signed in with same Apple ID, both device rows under user `8f1e288a` per direct DB check (AT:R34 BL1+BL2 verification). **`+28` is the AT:R41 TestFlight currently being built by Saiful** — carries v1 + Bundle 1 + Bundles 2+3 (first device validation since TickerDetail landed). External Beta still pending (no external testers added). One observation: iPhone 17 first launch of `+27` got stuck on a loading loop briefly; recovered without intervention; watch whether `+28` reproduces. |
| Play Console internal track | **Not yet uploaded** — gates on Saiful's external work: Play Console account ($25, individual), keystore at `~/.android-keys/ami-trade-upload.keystore` (via `keytool`), GCP OAuth 2.0 Android + Web clients, 3 icon source PNGs at `mobile/assets/icon/`. Per [D-057](docs/11_decisions/decision_log.md#d-057--android-gms-pulled-forward-from-v10-to-alpha). Test device on order: Samsung Galaxy A17 8GB (Android 14, ~1 week out). |
| Build commands | `scripts/install_iphone.sh` (dev sideload, iOS), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number), **`scripts/build_playstore.sh`** (Play Console AAB, AT:R36, same monotonic `+N` as TestFlight, signed when `~/.android-keys/keystore.properties` exists). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). Android: Play App Signing (mandatory for new apps; Google holds the signing key); upload keystore at `~/.android-keys/ami-trade-upload.keystore` (referenced by `android/app/build.gradle.kts` via `~/.android-keys/keystore.properties`; debug-signing fallback when the props file is absent). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **AT:R27 Floor change:** tapping an unlocked agent no longer opens 1-on-1 directly — it now opens an `AgentActionSheet` bottom sheet with two big buttons: `[1-ON-1]` (talk to the agent) and `[BRIEF]` (modify how it thinks). Concierge skips the sheet — has no Brief surface, so 1-on-1 is the only path. The tune icon in the 1-on-1 header stays as a secondary route to Brief. **AT:R27 rename:** `CoachScreen` → `BriefScreen`, `BriefHistoryScreen`, `BriefNotifier`/`briefNotifierProvider`, `models/brief.dart`, `api_client.startBrief/streamBriefMessage/...`. The 33 l10n keys flipped from `coach*` to `brief*` (including the journal chips: `journalFilterCoach` → `journalFilterBrief`, value `COACH` → `BRIEF`; same for `journalEntryTypeCoach`). Journal filter chips now read: `ALL · ROOM · TRADE · 1-ON-1 · BRIEF · LESSONS · UNLOCKS`. **First-time walkthrough (AT:R23):** per-section coach-mark tours (still using `tutorial_coach_mark` package — unrelated to Brief feature) fire on first visit. **AT:R25 auth gate** + **AT:R26 sign-out (Phase 4)** + **AT:R26 Apple-glitch fix** still in place. **AT:R37 sign-out UX:** after the `signOut()` notifier completes (which still mints a fresh anon in the background via bootstrap, since the app gate needs *some* user), the Settings button now pushes `SignInScreen(showSignedOutBanner: true)` — the user lands on the sign-in screen with a subtle "You've been signed out." strip at the top and one-tap auth options. Back navigation returns to Settings as guest if they don't sign back in. **AT:R38 merge sheet (BL16):** after a successful claim, `SignInScreen` reads `AuthVerifyResponse.adoptedFromUserId` — when non-null (account-linking Phase 1 silently adopted an existing email/sub row over the caller's anon), it pushes `MergeSheet` showing the orphan's pluralised counts ("12 journal entries · 3 sim trades · 7 lessons started · mandate") with `[MERGE EVERYTHING]` / `[KEEP SEPARATE]`. Confirm hits `POST /v1/auth/merge`; backend re-keys the orphan's data into the adopting user in one transaction. `_AuthGate` also invalidates sim / journal / mandate / watchlist / lessons providers on every `user.id` change so the prior user's data doesn't render stale post-swap. Journal soft-delete + Trash + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green pill once a sim_trade exists. Trade ticket sheet has live quote chip + auto-suggested TP/SL. Ticker tape below bottom nav. Settings → APPEARANCE is dark-only. Bug-report sheet (long-press app-version chip) supports photo attachments. **AT:R41 TickerDetail chart:** the COMING SOON placeholder is gone — `TickerChart` widget renders adaptive candlestick (1D/1W/1M) or line (3M/1Y/5Y) with volume bars in the bottom 1/4 and a touch-drag crosshair with date+price readout. 6 ChoiceChip periods, default 1M, per-session-only. Expand button (top-right, portrait only) pushes `ChartFullscreenScreen` — the ONE route in the app that unlocks orientation via per-route `SystemChrome.setPreferredOrientations([landscapeLeft, landscapeRight])` + `SystemUiMode.immersiveSticky`, restoring portrait on dispose. `OrientationBuilder` on TickerDetail also pushes fullscreen if iOS ever delivers a landscape orientation event (probably no-op while portrait-locked — verify on `+28` device test). The custom `_CandlestickPainter` + `_VolumePainter` + fl_chart-free line variant live in `mobile/lib/widgets/ticker_chart.dart` (~500 LOC). Data source: `tickerHistoryProvider` `FutureProvider.autoDispose.family<SimHistory, TickerHistoryKey(ticker, period)>` hits `GET /v1/sim/history/{ticker}?period=` (60s server cache).

---


## How to start the next session

```
/start-fresh R
```

The slash command reads `HANDOVER_R.md` + `docs/10_delivery/project_plan.md`, runs the configured sanity checks (Alpha health curl), queries the live bug list (currently **0 open**), then enters plan mode asking what to work on.

Session name to use: **AT:R42** (this is handover #41).

If Alpha is down at session start, `/start-fresh` will surface that and tell you the melehost debug commands.

If the first message is a specific task ("fix this", "add that"), skip `/start-fresh` and just do the task — the slash command is for the "let's keep going" opening.

Quick-win candidates for next session (in priority order):

1. **TestFlight smoke of `+28`** on iPhone 13 mini + iPhone 17. First device validation of TickerDetail v1 + Bundle 1 + Bundles 2+3 stacked together. Spot-check: candlestick body widths on 4.7" mini, crosshair readout placement (auto-flip at edges), period chip taps, expand button → fullscreen → X round-trip, **device-rotation auto-push behaviour (probably no-op on iOS portrait-lock — see watch item in AT:R41 history)**, chart unavailable / retry on a delisted ticker, watchlist-row → TickerDetail / Room verdict → SEE CHART.
2. **Bundles 4+5 — News + Earnings.** Per AT:R40 Plan Y, AT:R42's main work. New backend routes `/v1/sim/news/{ticker}?limit=5` (5-min cache) + `/v1/sim/earnings/{ticker}` (6h cache), both yfinance-backed. Mobile: News section between Earnings and Trades (5 headlines + publisher + relative time, external Safari via `url_launcher` — new dep); Earnings inline amber pill between Actions and News ("Q3 earnings · Jul 25 · est. EPS $2.04", 90-day cutoff). Hide-on-empty for both.
3. **Check Play Console approval status** + **confirm Saiful did the 3 follow-ons** (carry-overs 4-6): keystore password rotated, `keystore.properties` written, `GOOGLE_OAUTH_WEB_CLIENT_ID` exported in zshrc.
4. **First Play Console AAB upload** — gated on Play Console approval + items in #3.
5. **Credit consumption emission** — `credits_consumed` event type exists in `subscription_events`, nothing emits it. Wire Room + 1-on-1.
6. **Tier 2 sequential translation run** — loaders are ready. ~5h vLLM-blocking; own session.
7. **BL7 / BL8 / A29** — remaining backlog.

### Recent sessions (newest first)

- [AT:R41](history/AT_R0041.md)
- [AT:R40](history/AT_R0040.md)
- [AT:R39](history/AT_R0039.md)
- [AT:R38](history/AT_R0038.md)
- [AT:R37](history/AT_R0037.md)

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
