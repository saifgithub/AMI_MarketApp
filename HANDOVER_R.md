# Handover — AMI Trade build session

**Last updated:** 2026-07-06 (end of AT:R49 — DEF037: TestFlight upload fix, `altool`→`xcodebuild -exportArchive` for Xcode 26.5. ⚠️ AT:R48/CR001 — docs reorg + CR/Defect governance — ran in a **parallel session** and may still be un-wrapped; see "How to start the next session"). Narratives in [`history/`](history/) — see "Recent sessions" below.

Read this file **first** in any new session. It captures **current truth** + the carry-overs. Per-session narratives live in [`history/`](history/) — one file per /handover wrap, newest filename = newest session. The PRD-derived backlog (with delivery status) is at [`docs/initial_specs/10_delivery/project_plan.md`](docs/initial_specs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER_R.md = current state + carry-overs + Recent-sessions links. history/ = each session's wrap narrative as its own file. `/handover R` writes `history/AT_R<N>.md` per wrap; HANDOVER_R.md stays narrative-free.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **345+ commits** — ⚠️ a **parallel Fable 5 session is still committing to `main`**; always `git log` to get the true count. This session (AT:R49): DEF037 build_testflight fix (`c079359` + `d40947c`). Parallel session: docs reorg `84792e5` + CR/Defect governance `58fbaf8` (AT:R48/CR001), plus `006e373` bug_reports-vocab reconcile (tagged AT:R49 CR002 — landed mid-wrap). GitHub: `https://github.com/saifgithub/AMI_MarketApp` (private, set AT:R45). |
| Latest commit | `d40947c` — docs(defect): register DEF037 (AT:R49). Latest **code** change: `c079359` — build_testflight `altool`→`xcodebuild` upload fix. |
| Alpha tags | **`alpha-2026-07-06-1`** (→ `b499513`) — latest promote; R45–R48 code reached Alpha on 2026-07-06. Supersedes the old `alpha-2026-06-02-2` / "R45–R47 not promoted" note (stale). ⚠️ **Not verified this session:** whether Alpaca OAuth creds are set on melehost and whether migrations `a1b2c3d40012` + `b2c3d4e50013` actually applied — confirm on next promote/debug. |
| Backend tests | **541 passed, 0 failed** (AT:R47 added +7 Alpaca apikey tests; AT:R48 added +2). |
| Mobile pubspec | **`0.1.0+34`** (three TestFlight build bumps AT:R47). TestFlight: **`0.1.0+34` IPA built** but NOT yet uploaded — blocked by pending Apple Developer Agreement. Last successfully uploaded: **`0.1.0+30`** (AT:R46). |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **354 i18n keys** (AT:R42 added 10 news/earnings keys). **Tier 1 ARB AR + MS via on-prem Gemma 4 31B**; new keys fall back to EN until next translate pass. Tier 2 + Tier 3 remain EN-only; loaders ready when translated subdirs land. |

```
$ git log --oneline | head -10
b499513 style(mobile): use textMed token for Alpaca connect labels (AT:R48)
190d253 feat(pm): classroom-exercise framing — verdict is a worked example (AT:R48)
57775b6 chore(mobile): bump build 0.1.0+33 → 0.1.0+34 for TestFlight
d6b6787 chore(mobile): bump build 0.1.0+32 → 0.1.0+33 for TestFlight
0e8a667 chore(mobile): bump build 0.1.0+31 → 0.1.0+32 for TestFlight
f66caba feat(alpaca): API key auth mode to bypass OAuth for testing (AT:R47)
309e76b chore(handover): wrap AT:R46
...
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
| Routes | `/v1/alpaca/*` (**`POST /v1/alpaca/link`** — OAuth code exchange + token store; **`DELETE /v1/alpaca/unlink`**; **`GET /v1/alpaca/status`**; **`GET /v1/alpaca/portfolio`**; **`GET /v1/alpaca/positions`** — all require claimed user; AT:R45), `/v1/health`, `/v1/auth/*` (incl. `DELETE /v1/auth/session` — Phase 4 sign-out, AT:R26; **`POST /v1/auth/google`** — D-057, AT:R36; **`GET /v1/auth/merge/preview/{from}`** + **`POST /v1/auth/merge`** — BL16, AT:R38), `/v1/admin/*` (9 routes — AT:R27, see "Admin back-office" below), `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/brief/*` (was `/v1/coach/*` — renamed AT:R27; legacy `/v1/coach/*` kept as deprecated alias logging `deprecated_coach_route_used`), `/v1/journal/*` (incl. `/trash`, `/{id}/restore`), `/v1/lessons/*`, `/v1/llm/status`, `/v1/mandate/*` (now incl. **`/{u}/audit`** — BL12, **`/{u}/versions`** + **`/{u}/versions/{v}`** + **`POST /{u}/rollback/{v}`** — BL5, all AT:R33), `/v1/room/*`, `/v1/sim/*` (now incl. **`POST /sim/preview`** — BL9, AT:R33; **`GET /sim/history/{ticker}?period=`** — AT:R41 Bundle 2, public/no-auth, 6 periods 1d/1w/1m/3m/1y/5y, 60s cache, returns `{ticker, period, source, candles: [{t, o, h, l, c, v}]}`, 422 on invalid period; **`GET /sim/news/{ticker}?limit=5`** — AT:R42 Bundle 4, public/no-auth, 5-min cache, returns `[{title, link, publisher, pub_date}]`; **`GET /sim/earnings/{ticker}`** — AT:R42 Bundle 5, public/no-auth, 6h cache, 90-day forward window, returns `{ticker, next_earnings_date, estimated_eps, fiscal_quarter}`), `/v1/daily_challenge/*` (now incl. **`POST /{cid}/attempt`** — BL10, AT:R33), `/v1/watchlist/*`, `/v1/feedback/bug` (`multipart/form-data` with optional `file`). Plus a public HTML page at `/admin` (no auth required; the page itself asks for the `ADMIN_SECRET` bearer on first load + stores in localStorage). |
| Mac-side tests | `backend/.venv/bin/pytest backend/tests/unit/ -q` — **512 passed** (was 500; AT:R42 added +12 across `test_sim_news_earnings.py` — news/earnings routes, mock stubs, cache TTL). Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
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

Tables: `users` (with `suspended_at`, `trial_started_at`, `trial_expires_at` — AT:R27; `display_name` — AT:R29; `device_model`, `os_version`, `last_app_version` — AT:R33 BL1; **`alpaca_access_token`, `alpaca_refresh_token`, `alpaca_linked_at`** — AT:R45; **`alpaca_auth_mode`** — AT:R47), `auth_challenges` (with **`attempts`** — AT:R37 B-tier audit), `mandates`, `agent_activations`, `lessons_progress`, `journal_entries` (with `deleted_at`), `overlay_edit_counts`, `user_overlays`, `room_runs` (with `retry_count` — AT:R34), `sim_holdings`, `sim_portfolios`, `sim_trades`, `sim_watchlists`, `bug_reports` (with `assigned_branch`, `attachment_path`, `attachment_mime`), `llm_audit`, `http_audit`, `one_on_one_messages`, `subscription_events` (AT:R27), `user_devices` (AT:R33 BL2), `alembic_version`. Latest migration in repo: **`b2c3d4e50013`** (`alpaca_auth_mode` — AT:R47; **not yet on melehost**). Prior: `a1b2c3d40012` (`alpaca_credentials` — AT:R45; **not yet on melehost**). Both apply together on next promote. Prior: `f8b5d1c00011` (`auth_challenges.attempts` — AT:R37), `e7a4c5b00010` (`room_runs.retry_count` — AT:R34), `d5f2a3b00009` (`user_devices` — AT:R33 BL2), `c4e8f1a90008` (`users_device_info` — AT:R33 BL1). `init_schema()` self-stamps Alembic on a fresh container, so `alembic upgrade head` is a no-op on first boot. Bug-report attachments live in the named docker volume `ami-trade-local_bug_attachments` mounted at `/data/bug_attachments` in the api-alpha container.

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
| pubspec version | **`0.1.0+34`** (three TestFlight build bumps during AT:R47; APK also at +34). Added `alpacaLinkApiKey` to API client, two-tab AlpacaConnectScreen (API Key + OAuth). |
| TestFlight | **`0.1.0+34` IPA built** (33.1 MB at `mobile/build/ios/ipa/ami_trade.ipa`) but **NOT uploaded** — blocked by pending Apple Developer Agreement. Accept at [appstoreconnect.apple.com/agreements](https://appstoreconnect.apple.com/agreements), then `scripts/build_testflight.sh --no-bump`. Last uploaded: `0.1.0+30` (AT:R46). **Note:** Xcode 26.5 breaks `xcrun altool --upload-app` (error 19); `build_testflight.sh` upload step needs updating to use `xcodebuild -exportArchive destination:upload`. |
| Android test devices | **Galaxy Note Fan (SM-N935F, Android 9)** — serial `ce10171a8017590d01`. **Galaxy A17 (SM-A176B)** — serial `R5CY91AY99Y`. Both have AMI Trade `0.1.0+29` APK installed via USB (AT:R44). New APK `0.1.0+34` built (68.3 MB) at `mobile/build/app/outputs/flutter-apk/app-release.apk` — ready to install via USB or WhatsApp. |
| Play Console internal track | **`0.1.0+31` AAB built (52.4 MB, signed). Awaiting manual upload.** Go to play.google.com/console → App → Testing → Internal testing → Create new release → upload `mobile/build/app/outputs/bundle/release/app-release.aab`. First upload also enrolls in Play App Signing (one-time, irreversible). |
| Build commands | `scripts/install_iphone.sh` (dev sideload, iOS), `scripts/install_android.sh` (dev sideload, Android — both known devices or one if only one plugged in; **AT:R44**), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number), **`scripts/build_playstore.sh`** (Play Console AAB, signed when `~/.android-keys/keystore.properties` exists). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). Android: Play App Signing (mandatory for new apps; Google holds the signing key); upload keystore at `~/.android-keys/ami-trade-upload.keystore` (referenced by `android/app/build.gradle.kts` via `~/.android-keys/keystore.properties`; debug-signing fallback when the props file is absent). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **AT:R27 Floor change:** tapping an unlocked agent no longer opens 1-on-1 directly — it now opens an `AgentActionSheet` bottom sheet with two big buttons: `[1-ON-1]` (talk to the agent) and `[BRIEF]` (modify how it thinks). Concierge skips the sheet — has no Brief surface, so 1-on-1 is the only path. The tune icon in the 1-on-1 header stays as a secondary route to Brief. **AT:R27 rename:** `CoachScreen` → `BriefScreen`, `BriefHistoryScreen`, `BriefNotifier`/`briefNotifierProvider`, `models/brief.dart`, `api_client.startBrief/streamBriefMessage/...`. The 33 l10n keys flipped from `coach*` to `brief*` (including the journal chips: `journalFilterCoach` → `journalFilterBrief`, value `COACH` → `BRIEF`; same for `journalEntryTypeCoach`). Journal filter chips now read: `ALL · ROOM · TRADE · 1-ON-1 · BRIEF · LESSONS · UNLOCKS`. **First-time walkthrough (AT:R23):** per-section coach-mark tours (still using `tutorial_coach_mark` package — unrelated to Brief feature) fire on first visit. **AT:R25 auth gate** + **AT:R26 sign-out (Phase 4)** + **AT:R26 Apple-glitch fix** still in place. **AT:R37 sign-out UX:** after the `signOut()` notifier completes (which still mints a fresh anon in the background via bootstrap, since the app gate needs *some* user), the Settings button now pushes `SignInScreen(showSignedOutBanner: true)` — the user lands on the sign-in screen with a subtle "You've been signed out." strip at the top and one-tap auth options. Back navigation returns to Settings as guest if they don't sign back in. **AT:R38 merge sheet (BL16):** after a successful claim, `SignInScreen` reads `AuthVerifyResponse.adoptedFromUserId` — when non-null (account-linking Phase 1 silently adopted an existing email/sub row over the caller's anon), it pushes `MergeSheet` showing the orphan's pluralised counts ("12 journal entries · 3 sim trades · 7 lessons started · mandate") with `[MERGE EVERYTHING]` / `[KEEP SEPARATE]`. Confirm hits `POST /v1/auth/merge`; backend re-keys the orphan's data into the adopting user in one transaction. `_AuthGate` also invalidates sim / journal / mandate / watchlist / lessons providers on every `user.id` change so the prior user's data doesn't render stale post-swap. Journal soft-delete + Trash + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green pill once a sim_trade exists. Trade ticket sheet has live quote chip + auto-suggested TP/SL. Ticker tape below bottom nav. Settings → APPEARANCE is dark-only. Bug-report sheet (long-press app-version chip) supports photo attachments. **AT:R41 TickerDetail chart:** the COMING SOON placeholder is gone — `TickerChart` widget renders adaptive candlestick (1D/1W/1M) or line (3M/1Y/5Y) with volume bars in the bottom 1/4 and a touch-drag crosshair with date+price readout. 6 ChoiceChip periods, default 1M, per-session-only. Expand button (top-right, portrait only) pushes `ChartFullscreenScreen` — the ONE route that unlocks orientation. **AT:R42 TickerDetail Bundles 4+5:** `_EarningsPill` (amber chip, "Q3 · Jul 25 · est. EPS $2.04", 90-day cutoff, hide-on-empty) and `_NewsSection` (5 `_NewsRow` tiles, publisher + relative-time label, tap opens Safari via `LaunchMode.externalApplication`). Both sections hide when data is empty. `tickerNewsProvider` + `tickerEarningsProvider` FutureProviders; `simNews()` + `simEarnings()` API client methods; `SimNewsArticle` + `SimNews` + `SimEarnings` models in `sim.dart`.

---


## How to start the next session

```
/start-fresh R
```

The slash command reads `HANDOVER_R.md` + `docs/initial_specs/10_delivery/project_plan.md`, runs the configured sanity checks (Alpha health curl), queries the live bug list (currently **0 open**), then enters plan mode asking what to work on.

Session name to use: **AT:R50**. (AT:R49 wrapped here. ⚠️ AT:R48/CR001 ran as a **parallel Fable 5 session** and may still be un-wrapped — if it wraps after this, it must NOT reset this counter back to R49, and should add `history/AT_R0048.md` to Recent sessions.)

If Alpha is down at session start, `/start-fresh` will surface that and tell you the melehost debug commands.

If the first message is a specific task ("fix this", "add that"), skip `/start-fresh` and just do the task — the slash command is for the "let's keep going" opening.

Quick-win candidates for next session (in priority order):

1. **Accept Apple Developer Agreement + upload TestFlight 0.1.0+34.** Go to [appstoreconnect.apple.com/agreements](https://appstoreconnect.apple.com/agreements), accept, then `scripts/build_testflight.sh --no-bump`. IPA is already built. ✅ **The `build_testflight.sh` altool→`xcodebuild -exportArchive destination=upload` fix landed AT:R49 (DEF037, `c079359`)** — the upload path is repaired but **unverified** (needs the agreement accepted to run end-to-end).
2. **Upload 0.1.0+31 AAB to Play Console.** AAB at `mobile/build/app/outputs/bundle/release/app-release.aab`. Manual: play.google.com/console → Internal testing → Create new release. First upload enrolls in Play App Signing.
3. **Verify the AT:R45–R48 Alpha promote.** A `alpha-2026-07-06-1` tag (→ `b499513`) shows a 07-06 promote landed that code on Alpha. **Unverified this session:** whether Alpaca OAuth creds (`ALPACA_CLIENT_ID` in build scripts; `ALPACA_CLIENT_SECRET` + `ALPACA_PAPER_BASE_URL` + `ALPACA_REDIRECT_URI` in `infra/alpha.env`) are set, and whether migrations `a1b2c3d40012` + `b2c3d4e50013` actually applied on melehost. Confirm via `ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -c 'select version_num from alembic_version;'"`.
4. **Alpaca API key smoke on device** — Settings → Connect Alpaca → API KEY tab → paste paper key+secret → CONNECT → status linked. Portfolio tab shows paper cash + positions.
5. **TestFlight external beta submission.** Submit `+34` to Apple's Beta App Review (once uploaded).
6. **Credit consumption emission** — `credits_consumed` event type exists in `subscription_events`, nothing emits it. Wire Room + 1-on-1.
7. **Tier 2 sequential translation run** — loaders are ready. ~5h vLLM-blocking; own session.
8. **Backlog — only BL7 + BL8 are unblocked-now.** BL7 (agent metadata routes, ~1 session, low urgency — mobile workaround fine). BL8 (Room `cancel`/`replay`, ~1.5 sessions — cancel is the real work, replay is sugar; unkillable Room burns a credit today). BL4 blocks on GoogleProvider; BL6 on MVP-scoped drift detection; A29 is v1.0 / marketing-held.

**Android build note for next session:** `ANDROID_HOME=/Volumes/Extreme Pro/Android/sdk` has a space — always use `ANDROID_HOME=/Users/saiful/android-sdk` (symlink, no space) when running `flutter build appbundle`. The `apkanalyzer` `pwd -P` → `pwd` patch is in place on the local machine; if SDK is reinstalled it needs to be re-applied. Java 25 (system JVM) breaks KGP — always use `JAVA_HOME=/Applications/Android Studio.app/Contents/jbr/Contents/Home`.

### Recent sessions (newest first)

- [AT:R49](history/AT_R0049.md)
- AT:R48 — parallel CR001 session (Fable 5); not yet wrapped, `history/AT_R0048.md` pending
- [AT:R47](history/AT_R0047.md)
- [AT:R46](history/AT_R0046.md)
- [AT:R45](history/AT_R0045.md)

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
