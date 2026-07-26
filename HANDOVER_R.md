# Handover — AMI Trade build session

**Last updated:** 2026-07-26 (end of **AT:R64** — Architect session under the CR052
dispatch/audit protocol. Drove **Wave 2 of the 2026-07-26 daily-review delivery plan**:
laned + spawned + root-re-verified + submitted to independent audit **CR026-BE**
(sector-concentration enforcement in `safety_floor.py`) and **CR090-BE** (live News/Social
feed credit surcharge; Saiful chose the surcharge-on-top pricing model). Earlier in the
session, **CR030-BE** (dividend fields) and **CR029-BE** (FIFO cost-basis lots) shipped
DIRECT to main. Filed **DEF110** (stop/target hit doesn't close the sim position — Saiful
ruled it should, + close via Alpaca). Full narrative: [`history/AT_R0064.md`](history/AT_R0064.md).

> ## ⚠️ CURRENT STATE — AT:R64 (2026-07-26) — this block supersedes the stale detail tables below
>
> **The "What's on disk" / route / migration / mobile tables further down are R58-era
> (2026-07-14) and were NOT reconciled this wrap — treat them as historical reference, not
> current truth.** HANDOVER_R.md went 12 days / ~470 commits without a wrap (R59–R64
> committed to `main` without running `/handover`), so those tables drifted. Accurate
> current state:
>
> - **Git:** `main` @ `57195e9`, **989 commits**, working tree clean, **8 ahead of origin**
>   (all clean `AT:architect` commits — a backup push to GitHub was offered but not yet
>   authorized at wrap). Full backend unit suite **1242 green on main** (`018fdf2` baseline).
> - **CR052 dispatch/audit protocol is LIVE.** Work is laned in `orchestration/dispatch/lanes/`
>   (`<ID>.assign.md` Architect-owned + `<ID>.<instance>.md` coder-owned) and gated by the
>   independent auditor handshake in `orchestration/audit/cr/` (`.architect.md` SUBMITTED →
>   `.auditor.md` VERDICT). The Architect spawns coders only, **NEVER the auditor** (track-U is
>   Saiful's self-respawning watcher). Active delivery plan:
>   [`orchestration/dispatch/DELIVERY_PLAN.md`](orchestration/dispatch/DELIVERY_PLAN.md).
>   ⚠️ **Lane files are stale as state** — ~15 read READY_FOR_AUDIT/OPEN but actually landed;
>   trust `git log`, not lane files. ~15 uncleaned worktrees under `.claude/worktrees/`.
> - **At the audit gate (awaiting track-U verdict — integrate on COMPLETE):**
>   **CR026-BE** (build `bb398bf` on `lane/CR026.coder.api`, 1262 green, migration `d1e2f3a40023`;
>   flags: touches coder.room files additively; market-order parity gap) and **CR090-BE**
>   (build `cd292d3` on `lane/CR090-BE.coder.api`, 1260 green, additive). Both D-5. Their lane
>   worktrees `coder.api-CR026`/`coder.api-CR090-BE` MUST be kept until integrated.
> - **Registers are GENERATED (CR081)** — never hand-edit `cr_list.md`/`def_list.md`; edit
>   `_registry/<ID>.row.md`, `./backend/.venv/bin/python scripts/registers/gen_registers.py
>   gen cr|def` + `verify`, commit both. Next new IDs: **DEF111 / CR091**.
> - **Blocked-on-Saiful:** DEF100 (RevenueCat keys — gates DEF099's live RC-alias hop), DEF104
>   (rotate the live plaintext IMAP/SMTP cred in `support_kb/scripts/ami_support.py`), CR027
>   (APNs/FCM certs).

Read this file **first** in any new session. It captures **current truth** + the carry-overs. Per-session narratives live in [`history/`](history/) — one file per /handover wrap, newest filename = newest session. The PRD-derived backlog (with delivery status) is at [`docs/initial_specs/10_delivery/project_plan.md`](docs/initial_specs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER_R.md = current state + carry-overs + Recent-sessions links. history/ = each session's wrap narrative as its own file. `/handover R` writes `history/AT_R<N>.md` per wrap; HANDOVER_R.md stays narrative-free.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **518 commits** (+wrap) — ⚠️ parallel sessions have committed to `main` before (R48, R50, G1) + the auditor track U interleaves `AT:U1` commits; this session also had **CR034 + DEF056 land from an unannounced parallel window under the same `AT:R58` tag** — always diff `git log <last-wrap-sha>..HEAD`, never rely on this conversation's own memory of what shipped. Pushed to GitHub: `https://github.com/saifgithub/AMI_MarketApp`, `origin/main` in sync. |
| Latest commit | `309b92a` — docs(audit): CR034/DEF056 verdicts COMPLETE, fix wrong tag citations, open DEF057 lane (AT:R58 CR034 DEF056 DEF057). |
| Alpha tags | **`alpha-2026-07-14-3`** (→ `7561635`) — latest promote, DEF056 (PM verdict driven by debate) live. Chain this session: `alpha-2026-07-13-1` (DEF051) → `alpha-2026-07-14-1` (DEF052-055) → `alpha-2026-07-14-2` (CR034) → `alpha-2026-07-14-3` (DEF056). **DEF057 (rng flakiness fix) not yet promoted** — test-hygiene fix, no user-facing urgency, will ride the next promotion. **No new migrations this session** — every fix is code-only. ❌ **Alpaca OAuth creds still NOT set** — API-key mode (AT:R47) is the working path. **DEF044 key derives from `SECRET_KEY`** — verify `infra/alpha.env` SECRET_KEY hash-matches melehost before every promote. |
| Backend tests | **742 passed, 0 failed** (673 → 742, +69 this session across DEF051/052/053/054/055/056/057 + CR034 — see `history/AT_R0058.md` for the per-item breakdown). ⚠️ Run via `source backend/.venv/bin/activate` first — a bare `pytest` can pick up system Python 3.14 with no project deps (`ModuleNotFoundError: structlog`), which looks like mass collection failure, not a real regression. |
| Mobile pubspec | **`0.1.0+38`** (AT:R54 — unchanged this session). DEF051 (`api_client.dart`) and DEF056 (4 files — PASS verdict's own visual treatment) touched mobile source but **no new build was cut** — these ship whenever Saiful next runs `scripts/build_testflight.sh`/`build_playstore.sh`. TestFlight: **`+38` uploaded + processing** (predates this session's mobile changes; benign objective_c.framework dSYM warning). APK: `+38` release-signed (66 MB, sent to Saiful). |
| Content corpus | 270 lessons (**CR018: numbered by id-prefix, badge in list + reader**), 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **356 i18n keys** (AT:R54 +2 watchlist remove/undo). **Tier 1 ARB AR + MS via on-prem Gemma 4 31B**; new keys fall back to EN until next translate pass. Tier 2 + Tier 3 remain EN-only; loaders ready when translated subdirs land. |

```bash
$ git log --oneline | head -8
309b92a docs(audit): CR034/DEF056 verdicts COMPLETE, fix wrong tag citations, open DEF057 lane (AT:R58 CR034 DEF056 DEF057)
b0c85a2 fix(room): seed profile rng off a stable hash, not PYTHONHASHSEED-randomized hash() (AT:R58 DEF057)
06baed0 chore(audit): CR034 round 1 verdict — COMPLETE (FOMC dates verified vs fed calendar) (AT:U1 CR005)
15b234a chore(audit): DEF056 round 1 verdict — COMPLETE (safety floor vetoes verified; 3 obs) (AT:U1 CR005)
deb653c chore(handover): wrap AT:R58
27adb46 docs(audit): open CR034/DEF056 architect lanes for track U (AT:R58 CR034 DEF056)
a2e836a docs(audit): DEF054/DEF055 round 1 COMPLETE — mark in INDEX, fix stale promoted-status notes (AT:R58 DEF054 DEF055)
7561635 docs(defect): flip DEF056 to resolved (AT:R58 DEF056)
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
| Routes | `/v1/alpaca/*` (**`POST /v1/alpaca/link`** — OAuth code exchange + token store; **`DELETE /v1/alpaca/unlink`**; **`GET /v1/alpaca/status`**; **`GET /v1/alpaca/portfolio`**; **`GET /v1/alpaca/positions`** — all require claimed user; AT:R45), `/v1/health`, `/v1/auth/*` (incl. `DELETE /v1/auth/session` — Phase 4 sign-out, AT:R26; **`POST /v1/auth/google`** — D-057, AT:R36; **`GET /v1/auth/merge/preview/{from}`** + **`POST /v1/auth/merge`** — BL16, AT:R38), `/v1/admin/*` (9 routes — AT:R27, see "Admin back-office" below), `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/brief/*` (was `/v1/coach/*` — renamed AT:R27; legacy `/v1/coach/*` kept as deprecated alias logging `deprecated_coach_route_used`), `/v1/journal/*` (incl. `/trash`, `/{id}/restore`), `/v1/lessons/*`, `/v1/llm/status`, `/v1/mandate/*` (now incl. **`/{u}/audit`** — BL12, **`/{u}/versions`** + **`/{u}/versions/{v}`** + **`POST /{u}/rollback/{v}`** — BL5, all AT:R33), `/v1/room/*`, `/v1/sim/*` (now incl. **`POST /sim/preview`** — BL9, AT:R33; **`GET /sim/history/{ticker}?period=`** — AT:R41 Bundle 2, public/no-auth, 6 periods 1d/1w/1m/3m/1y/5y, 60s cache, returns `{ticker, period, source, candles: [{t, o, h, l, c, v}]}`, 422 on invalid period; **`GET /sim/news/{ticker}?limit=5`** — AT:R42 Bundle 4, public/no-auth, 5-min cache, returns `[{title, link, publisher, pub_date}]`; **`GET /sim/earnings/{ticker}`** — AT:R42 Bundle 5, public/no-auth, 6h cache, 90-day forward window, returns `{ticker, next_earnings_date, estimated_eps, fiscal_quarter}`), `/v1/league/*` (**CR004, AT:R52** — `GET /standings` 404 `not_in_league` when unassigned · `GET /me` — mints the pseudonymous handle on first call, returns tier/reputation/week-points/rank/streak · `GET /history` · `PATCH /handle` — one regeneration, then 409 `already_regenerated`; all require auth), `/v1/daily_challenge/*` (now incl. **`POST /{cid}/attempt`** — BL10, AT:R33; **AT:R52 CR004:** persists to `daily_challenge_attempts` UNIQUE(user, challenge), duplicate returns stored result + `already_attempted: true`, awards reputation; `GET /today` gains `my_attempt` when authed), `/v1/watchlist/*`, `/v1/feedback/bug` (`multipart/form-data` with optional `file`). Plus a public HTML page at `/admin` (no auth required; the page itself asks for the `ADMIN_SECRET` bearer on first load + stores in localStorage). |
| Mac-side tests | `backend/.venv/bin/pytest backend/tests/unit/ -q` — **673 passed** (AT:R57 added +81). Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
| Env knobs (alpha) | `AMI_ENV=staging` + `SECRET_KEY=<64-hex>` + `ADMIN_SECRET=<64-hex>` (AT:R27, admin back-office bearer) + `SMTP_{HOST,PORT,USER,PASSWORD,FROM}` (5 vars, AT:R26 — now dormant) + **`RESEND_API_KEY=re_<…>`** (AT:R32, primary outbound mail route) + **`GOOGLE_AUDIENCES=<web_client_id_csv>`** (AT:R36, D-057 — **populated AT:R39 with the GCP OAuth Web client_id** `153141744056-03d6sa…`; ⚠️ was NOT actually reaching the container until **DEF038 fixed AT:R52** — compose omitted it from `environment:`; truly live since `alpha-2026-07-07-1`). Canonical at `infra/alpha.env` on Mac, gitignored; shipped via `scp` in `/promote-to-alpha` step 4. Without `SECRET_KEY` the backend refuses to start when env != local. **Email transport**: `email_service` prefers Resend (HTTP API, port 443 — bypasses melehost's ISP block on outbound 25/587) when `RESEND_API_KEY` is set; falls back to SMTP if `SMTP_HOST` is configured; falls back to no-op otherwise. Verified live: magic-link delivered to Gmail end-to-end. |
| Auth | Phase 1.5 + Phase 3 + Phase 4 enforced. Route-level `get_current_user` on `/v1/mandate`, `/v1/journal`, `/v1/watchlist`, `/v1/brief` (legacy `/v1/coach`), `/v1/agents/one_on_one`, `/v1/room`, plus per-route on user-specific `sim` + `lessons`. Bearer format `scaffold:<user_id_hex>:<hmac_sig>` (HMAC-SHA256 with `SECRET_KEY`). Legacy unsigned `scaffold:<hex>` accepted only in env=local. `/v1/auth/anon` mints fresh unless the caller's Bearer matches the supplied `device_user_id`. Magic-link routes require auth and bind to `current_user.id`. **Apple Sign-In Phase 3 (AT:R29):** `/v1/auth/apple` now lives in every env (no more 503 gate). `OIDCVerifier` in `app/services/oidc_verifier.py` fetches Apple's JWKS, RSA-verifies the identity token, validates `iss=https://appleid.apple.com`, `aud ∈ APPLE_AUDIENCES`, `exp`. On first auth: persists `email` + `full_name` (→ `users.display_name`). On subsequent auths or magic-link priors: preserves existing email/name (never overwritten). `DELETE /v1/auth/session` (Phase 4) requires auth and returns `{"signed_out": true}` — stateless no-op now. `http_audit` middleware scrubs request + response bodies for all `/v1/auth/*` routes (AT:R26 B4 close). **AT:R27 suspension enforcement:** `get_current_user` checks `users.suspended_at`; if set, raises `403 {"detail": "account_suspended"}`. **AT:R31 D-039 trial activation (BL3):** `_claim_or_create()` (magic-link) and `sign_in_with_apple()` (Apple) now populate `users.trial_started_at = now()` + `users.trial_expires_at = now() + 7d` on first claim. Guarded by `trial_started_at is None` so admin-granted trials are preserved. Downstream entitlement gate / expiry banner / conversion modal still TODO (BL11). **AT:R32 account-linking Phase 1:** `_claim_or_create()` now does email-lookup-FIRST (adopt existing identity), then user_id-fallback (promote anon). `sign_in_with_apple()` gained an email fallback between apple_sub and user_id lookups — magic-link-first + Apple-later (with same email) now attaches `apple_id` to the existing row instead of forking. Existing-row's email is never mutated by re-verify. Pre-claim anon rows are left orphan (ephemeral). Real merge UX deferred to BL16. **AT:R32 BL13 binding:** `/v1/auth/magic_link/verify` + `/v1/auth/apple` accept optional `onboarding_session_id`; route looks up `OnboardingSession` in `session_store` and stamps `claimed_user_id`. Both routes are now async. **AT:R32 L-1 cleanup:** `OneOnOneStartRequest.user_id` removed — `/v1/agents/one_on_one/start` sources user from Bearer only (audit A3 pattern, finally consistent). **AT:R33 BL1 device context:** `/v1/auth/anon` accepts optional `device_model`, `os_version`, `app_version`; backend persists onto `users` (refreshed on every bootstrap). **AT:R33 BL2 user_devices:** `/v1/auth/anon` also accepts optional `device_install_id` (mobile-generated UUID, never overwritten by claim). Backend upserts a `user_devices` row keyed by install_id; on claim adoption (`_claim_or_create` + `sign_in_with_apple`), the pre-claim anon's devices re-key to the adopting user so two phones on one Apple ID surface under one user. **AT:R33 BL11 entitlement gate:** `effective_plan(plan, trial_expires_at)` is now resolved at every `pick_tier()` callsite (brief_engine, agent_runner, room_runner) — when a trial lapses, LLM routing automatically drops to cheap-tier without admin intervention. **Admin auth:** `/v1/admin/*` uses `Authorization: Bearer <ADMIN_SECRET>`. Audit finding A4 CLOSED. **AT:R36 D-057 Google Sign-In:** `/v1/auth/google` mirrors `/v1/auth/apple` end-to-end. `GoogleOIDCVerifier` (in the same `oidc_verifier.py`) fetches `https://www.googleapis.com/oauth2/v3/certs`, RSA-verifies the ID token, accepts both Google issuers (`https://accounts.google.com` AND `accounts.google.com`), validates `aud ∈ GOOGLE_AUDIENCES`, `exp`. `OIDCVerifier.issuers` now a list (was `issuer: str`) with manual membership check, since python-jose only accepts a single string for the built-in `iss` check. `email_verified=false` guard drops the email on the floor (defends against unconfirmed-Google-account email squatting). Account-linking Phase 1 mirrors Apple: email-FIRST adoption of an existing magic-link/Apple row with the same email, then `google_sub`-fallback. Trial activation + BL2 device re-keying parallel Apple flow. Minimum-data policy (D-057, locked AT:R29 — "sub, name, email"): persist only `sub` → `users.google_id`, `email` → `users.email`, `name` → `users.display_name`; `picture`, `locale`, `hd`, `given_name`, `family_name` dropped. `AuthUser` schema gained `google_id`. `http_audit` SCRUB_PATHS includes `/v1/auth/google`. **AT:R37 B-tier audit close — magic-link brute-force lockout:** `verify_magic_link()` now finds the most recent active (unconsumed + unexpired) challenge for the target by `target` alone (not joined on `code_hash`), so a wrong-code attempt can bump `auth_challenges.attempts`. Once the counter hits `MAX_MAGIC_LINK_ATTEMPTS = 5` the row is force-consumed via `consumed_at = now()`, locking out even the correct code. The user always recovers by requesting a fresh code (mints a new row with `attempts=0`). **AT:R37 B-tier audit close — rate limiting:** new `app/services/rate_limit.py` ships an in-memory sliding-window `RateLimiter` dep applied to `/v1/auth/anon` (10/min/IP), `/v1/auth/magic_link/start` (3/min/IP — email cost), `/v1/room/stream` (5/min/IP — 12-agent LLM run cost). IP resolution: `cf-connecting-ip` → `x-forwarded-for` first hop → `request.client.host`. 429 with `Retry-After` header on overrun. Process-local — replaced by Redis-backed when we shard. **AT:R37 B-tier audit close — feedback upload streaming:** new `save_attachment_streaming()` reads UploadFile in 64KB chunks with a running byte counter; mid-stream cap overrun aborts + unlinks the partial file. MIME validated up-front so unsupported types never touch disk. **AT:R38 BL16 — adoption signal + merge endpoints:** `AuthVerifyResponse` gained `adopted_from_user_id: UUID | None`, populated by the 3 claim methods (`_claim_or_create`, `sign_in_with_apple`, `sign_in_with_google`) whenever the email/sub fallback returns a different `user_id` than the caller's bearer. Each adoption also writes a `subscription_events` row with `event_type=account_adoption`, which the new `GET /v1/auth/merge/preview/{from}` + `POST /v1/auth/merge` routes use as their authorisation proof (caller's bearer must match the `to_value`; 403 otherwise). The execute route delegates to `MergeService.execute()` — a single-transaction re-key of every per-user row from orphan → adopter, with per-table conflict rules; ends by `DELETE`-ing the orphan `users` row. |
| Room env knobs | `ROOM_DEDUP_RUNNING_MINUTES=30` (in-flight dedup + startup-sweep cutoff) · `ROOM_DEDUP_COMPLETED_HOURS=24` (return prior verdict same day; design doc default was 5 days — we start tighter). Set completed_hours=0 to disable cached-run dedup. **AT:R34 eeeb866f:** startup sweep auto-retries stuck `running` rows once (`MAX_AUTO_RETRIES=1`, hard-coded in `room_runner.py`) before marking them failed. Lifespan startup hook calls `runner.resume_pending_retries()` to spawn the retry tasks; journal write is replayed inside the retry's `_pump` since the original request's `on_complete` closure is gone after restart. |
| Push code to it | [`/promote-to-alpha`](.claude/commands/promote-to-alpha.md) — rsync + recreate + smoke. Deploy is rsync-only (melehost has no git remote); source also lives on GitHub `origin` → `saifgithub/AMI_MarketApp` — push `main` for versioning + multi-agent sync. |

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

Tables: `users` (with `suspended_at`, `trial_started_at`, `trial_expires_at` — AT:R27; `display_name` — AT:R29; `device_model`, `os_version`, `last_app_version` — AT:R33 BL1; **`alpaca_access_token`, `alpaca_refresh_token`** — AT:R45, **encrypted at rest AT:R53 DEF044** via `EncryptedString`/Fernet (transparent to ORM; DB stores `enc::v1::…` ciphertext); **`alpaca_linked_at`** — AT:R45; **`alpaca_auth_mode`** — AT:R47), `auth_challenges` (with **`attempts`** — AT:R37 B-tier audit), `mandates`, `agent_activations`, `lessons_progress`, `journal_entries` (with `deleted_at`), `overlay_edit_counts`, `user_overlays`, `room_runs` (with `retry_count` — AT:R34), `sim_holdings`, `sim_portfolios`, `sim_trades`, `sim_watchlists`, `bug_reports` (with `assigned_branch`, `attachment_path`, `attachment_mime`), `llm_audit`, `http_audit`, `one_on_one_messages`, `subscription_events` (AT:R27), `user_devices` (AT:R33 BL2), **`reputation_events`, `daily_challenge_attempts`, `leagues`, `league_members`** (CR004 — AT:R52; plus `users` +`handle` UNIQUE/`handle_regenerated_at`/`reputation`/`show_display_name`), `alembic_version`. Latest migration in repo: **`c3d4e5f60014`** (`reputation_league` — AT:R52; ✅ **applied on melehost via `alpha-2026-07-07-1`**). Prior: `b2c3d4e50013` (`alpaca_auth_mode` — AT:R47), `a1b2c3d40012` (`alpaca_credentials` — AT:R45), `f8b5d1c00011` (`auth_challenges.attempts` — AT:R37), `e7a4c5b00010` (`room_runs.retry_count` — AT:R34), `d5f2a3b00009` (`user_devices` — AT:R33 BL2), `c4e8f1a90008` (`users_device_info` — AT:R33 BL1). `init_schema()` self-stamps Alembic on a fresh container, so `alembic upgrade head` is a no-op on first boot. Bug-report attachments live in the named docker volume `ami-trade-local_bug_attachments` mounted at `/data/bug_attachments` in the api-alpha container.

### LLM gateway

- **vLLM** at `http://192.168.20.74:8000` serving `ami-llm` (`RedHatAI/Qwen3.6-35B-A3B-NVFP4`, 262k context — rebranded). CR077 caught the docs still saying "Gemma 4 31B"; corrected 2026-07-23 against `/v1/models`. Gateway preference: `vllm > anthropic > mock`.
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
| pubspec version | **`0.1.0+37`** (AT:R53). Carries the CR009–CR016 batch + DEF043 hex-nav fix. |
| TestFlight | **`0.1.0+37` uploaded** via `scripts/build_testflight.sh --no-bump` (DEF037 fix confirmed working — `xcodebuild -exportArchive destination:upload`, since Xcode 26.5 broke `altool`). The Apple Developer Agreement blocker cleared this session. Harmless upload warning: no dSYM for `objective_c.framework` (one plugin's crash frames won't symbolicate). |
| Android test devices | **Galaxy Note Fan (SM-N935F)** — `ce10171a8017590d01`. **Galaxy A17 (SM-A176B)** — `R5CY91AY99Y`. New APK `0.1.0+37` (68.9 MB) at `mobile/build/app/outputs/flutter-apk/app-release.apk`, release-signed. ⚠️ **Build APKs via `scripts/install_android.sh` (or replicate its `--dart-define` flags) — a bare `flutter build apk --release` bakes NO dart-defines, so the APK reaches NO backend.** (The `+36` APK had this bug; `+37` fixed.) |
| Play Console internal track | **CR048 (R64): fastlane automation landed; awaiting Saiful's first manual upload.** Keystore verified present (`~/.android-keys/keystore.properties` + `.keystore` — earlier "not yet written" note was stale). Fresh signed AAB built this session. **First upload is still manual** (Play App Signing enrollment, web-UI only): play.google.com/console → App → Testing → Internal testing → Create new release → upload `mobile/build/app/outputs/bundle/release/app-release.aab`. After that + a Play Console API service account (`~/.android-keys/play-service-account.json`), releases #2+ go via **`scripts/publish_playstore.sh`** (build + `fastlane internal`). Steps in `docs/forward_planning/CR048_playstore_internal_track_fastlane/`. |
| Build commands | `scripts/install_iphone.sh` (dev sideload, iOS), `scripts/install_android.sh` (dev sideload, Android — both known devices or one if only one plugged in; **AT:R44**), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number), **`scripts/build_playstore.sh`** (Play Console AAB, signed when `~/.android-keys/keystore.properties` exists). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). Android: Play App Signing (mandatory for new apps; Google holds the signing key); upload keystore at `~/.android-keys/ami-trade-upload.keystore` (referenced by `android/app/build.gradle.kts` via `~/.android-keys/keystore.properties`; debug-signing fallback when the props file is absent). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **AT:R27 Floor change:** tapping an unlocked agent no longer opens 1-on-1 directly — it now opens an `AgentActionSheet` bottom sheet with two big buttons: `[1-ON-1]` (talk to the agent) and `[BRIEF]` (modify how it thinks). Concierge skips the sheet — has no Brief surface, so 1-on-1 is the only path. The tune icon in the 1-on-1 header stays as a secondary route to Brief. **AT:R27 rename:** `CoachScreen` → `BriefScreen`, `BriefHistoryScreen`, `BriefNotifier`/`briefNotifierProvider`, `models/brief.dart`, `api_client.startBrief/streamBriefMessage/...`. The 33 l10n keys flipped from `coach*` to `brief*` (including the journal chips: `journalFilterCoach` → `journalFilterBrief`, value `COACH` → `BRIEF`; same for `journalEntryTypeCoach`). Journal filter chips now read: `ALL · ROOM · TRADE · 1-ON-1 · BRIEF · LESSONS · UNLOCKS`. **First-time walkthrough (AT:R23):** per-section coach-mark tours (still using `tutorial_coach_mark` package — unrelated to Brief feature) fire on first visit. **AT:R25 auth gate** + **AT:R26 sign-out (Phase 4)** + **AT:R26 Apple-glitch fix** still in place. **AT:R37 sign-out UX:** after the `signOut()` notifier completes (which still mints a fresh anon in the background via bootstrap, since the app gate needs *some* user), the Settings button now pushes `SignInScreen(showSignedOutBanner: true)` — the user lands on the sign-in screen with a subtle "You've been signed out." strip at the top and one-tap auth options. Back navigation returns to Settings as guest if they don't sign back in. **AT:R38 merge sheet (BL16):** after a successful claim, `SignInScreen` reads `AuthVerifyResponse.adoptedFromUserId` — when non-null (account-linking Phase 1 silently adopted an existing email/sub row over the caller's anon), it pushes `MergeSheet` showing the orphan's pluralised counts ("12 journal entries · 3 sim trades · 7 lessons started · mandate") with `[MERGE EVERYTHING]` / `[KEEP SEPARATE]`. Confirm hits `POST /v1/auth/merge`; backend re-keys the orphan's data into the adopting user in one transaction. `_AuthGate` also invalidates sim / journal / mandate / watchlist / lessons providers on every `user.id` change so the prior user's data doesn't render stale post-swap. Journal soft-delete + Trash + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green pill once a sim_trade exists. **AT:R58 DEF056:** the Verdict can now come back as `PASS` (debate concluded no trade fits, distinct from a mandate `REJECT`) — rendered with its own neutral slate/icon treatment (not amber+cancel like REJECT) in the verdict card, journal replay, and share card. Trade ticket sheet has live quote chip + auto-suggested TP/SL. Ticker tape below bottom nav. Settings → APPEARANCE is dark-only. Bug-report sheet (long-press app-version chip) supports photo attachments. **AT:R41 TickerDetail chart:** the COMING SOON placeholder is gone — `TickerChart` widget renders adaptive candlestick (1D/1W/1M) or line (3M/1Y/5Y) with volume bars in the bottom 1/4 and a touch-drag crosshair with date+price readout. 6 ChoiceChip periods, default 1M, per-session-only. Expand button (top-right, portrait only) pushes `ChartFullscreenScreen` — the ONE route that unlocks orientation. **AT:R42 TickerDetail Bundles 4+5:** `_EarningsPill` (amber chip, "Q3 · Jul 25 · est. EPS $2.04", 90-day cutoff, hide-on-empty) and `_NewsSection` (5 `_NewsRow` tiles, publisher + relative-time label, tap opens Safari via `LaunchMode.externalApplication`). Both sections hide when data is empty. `tickerNewsProvider` + `tickerEarningsProvider` FutureProviders; `simNews()` + `simEarnings()` API client methods; `SimNewsArticle` + `SimNews` + `SimEarnings` models in `sim.dart`.

---


## How to start the next session

```
/start-fresh R
```

The slash command reads `HANDOVER_R.md` + `docs/initial_specs/10_delivery/project_plan.md`, runs the configured sanity checks (Alpha health curl), queries the live bug list (currently **0 open**), then enters plan mode asking what to work on.

Session name to use: **AT:R65**. (AT:R64 wrapped here — see the CURRENT STATE block at
the top of this file. ⚠️ The round counter jumped R58→R64 because R59–R63 committed to
`main` without wrapping; governance track G + auditor track U also commit (AT:G1, AT:U1).
A later wrap of any un-wrapped parallel session must NOT reset this counter below R65.)

**CURRENT PRIORITIES (AT:R64 → next session):**
1. **Check the audit gate first.** `CR026-BE` + `CR090-BE` are SUBMITTED to track-U. Read
   `orchestration/audit/cr/CR026.auditor.md` + `CR090-BE.auditor.md` — on `VERDICT: COMPLETE`,
   integrate the lane branch to main + re-verify full suite + flip `DISPATCH: ACCEPTED`; on
   `AWAITING_FIXES`, the coder fixes + bumps round. Do NOT spawn the auditor.
2. **Wave 3 of the delivery plan:** CR028 (trailing stop — behind DEF094 which holds `sim.py`
   @ READY_FOR_AUDIT; integrate DEF094 first) + CR065 (streaks reconciliation — needs a recon
   pass first). See `orchestration/dispatch/DELIVERY_PLAN.md`.
3. **Deferred mobile (needs a device-test session):** CR029-MOBILE (per-lot cards), CR030-MOBILE
   (dividend sub-chip), CR026 donut chart, CR090-MOBILE (upgrade copy). Re-verify each `fromJson`
   vs live JSON before its own audit. Plus **CR090-ROOM** (coder.room: charge the surcharge +
   disclosure header's 3rd state — consumes CR090-BE's `LiveDataState` contract) and **DEF110**
   fix (D-5; core liquidate + a new `alpaca_service.close_position`).
4. **Housekeeping:** the register flips Saiful greenlit 2026-07-24 (CR007/8/19/20/21/37→done,
   CR036→started) are still owed; the ~15 stale lane files + worktrees want a cleanup pass;
   offer the origin backup push. **DEF104 rotating the live cred is independent/anytime.**

*(The numbered "Other priorities" list below is R58-era — CR032/CR021/CR020 etc. — kept as
historical reference; reconcile against the live registers before acting on any of it.)*

If Alpha is down at session start, `/start-fresh` will surface that and tell you the melehost debug commands.

If the first message is a specific task ("fix this", "add that"), skip `/start-fresh` and just do the task — the slash command is for the "let's keep going" opening.

**The roadmap is [CR004](docs/forward_planning/CR004_release_readiness/CR004_release_readiness.md)** (release-readiness umbrella; D-059–D-062 locked). The full **B3–C4 + E3/E4 batch is now delivered**: AT:R52 gave D0 + backend + B1; **AT:R53 gave B2/B3/B4/B5/B6 (CR009/010), C3 (CR011), C4 (CR012), the animation/motion bundle (CR013/014), and design-system D7/D8 (CR015/016)** — all COMPLETE through the audit handshake, on builds `+36`/`+37`.

**Silent_Scout is closed (AT:R55).** The directory no longer exists — everything of
value became CR023–CR032 (see below); don't look for it, don't `cd` into it.

**CR025 is done (AT:R56).** Watchlist day-change badge shipped end-to-end.

**CR023/CR024 (News/Social Analyst truthfulness) are `in_progress`, shipped
AT:R57** — real data now flows into both. News: Yahoo (free) combined with
Alpha Vantage (paid, sentiment-scored) when `ALPHA_VANTAGE_API_KEY` is set.
Social: Reddit-only aggregate sentiment via Adanos (free, 250 calls/month)
when `ADANOS_API_KEY` is set. Neither CR is `done`: News still lacks a
macro/earnings-calendar feed by design (disclosed, not fabricated), and
Social still has no Twitter/X/StockTwits/Google Trends/Discord coverage.
Full detail: `docs/forward_planning/CR023_news_analyst_live_feed/` and
`CR024_social_analyst_live_feed/`.

**DEF051-057 + CR034 all `resolved`/`done`, shipped AT:R58** — the full
12-agent truthfulness/wiring audit closed out, every item audited
**COMPLETE** by track U, zero BLOCKER/MAJOR findings across the whole
batch. DEF051 (Room's fake $100k/0%-drawdown compliance input,
safety-floor-relevant), DEF052 (Market Analyst real technicals), DEF053
(Fundamentals Analyst real valuation multiples/sector/dividends/consensus),
DEF054+DEF055 (Bull/Bear Researcher real Decision Journal history), DEF056
(the Room's structured Verdict now reflects the actual 12-agent debate
instead of a precomputed value set before any agent spoke — the
highest-stakes fix of the session), CR034 (Room's FOMC-date catalyst now
real). CR033 superseded by DEF052-055. DEF051-056 + CR034 promoted through
`alpha-2026-07-14-3`; DEF056's own audit independently reproduced the
safety-floor-override/fail-safe-to-PASS/size-clamp properties. Full detail
in each item's own `docs/defect/`/`docs/forward_planning/` folder and in
[`history/AT_R0058.md`](history/AT_R0058.md).

**DEF057 — also audited COMPLETE, nothing left open from this batch.**
Track U's DEF056 review caught a pre-existing bug (O2): `_profile_for_ticker`'s
rng seeded off Python's builtin `hash()`, randomized per process unless
pinned — contradicted the function's own "deterministic synthetic baseline"
docstring and caused a flaky test. Filed and fixed same-session (seed off
`zlib.crc32` instead — stable across processes); auditor independently
proved determinism across 5 hash seeds and proved the old code was
genuinely non-deterministic. Not yet promoted (test-hygiene fix, no
user-facing urgency — can ride the next promotion of substantive work).
**Every item from this session's audit batch (CR023/024/034, DEF051-057) is
now COMPLETE — nothing pending for next session from this thread.**

**Other priorities — Saiful hasn't picked between these yet:**

1. **CR032 needs Saiful's decision first, not code.** [CR032](docs/forward_planning/CR032_gb10_lora_finetuning_decision/CR032_gb10_lora_finetuning_decision.md) — the GB10 LoRA-fine-tuning research box turned out to be the exact same host serving production vLLM to all 13 live agents, a capacity conflict never addressed in 9 weeks of "active research." Continue (needs dedicated hardware or a maintenance-window protocol) or shelve (GTM mode's priority is real-data wiring, not model infra)?
2. **CR021 (context router) + CR020 (full_context mode)** — still the AT:R54 carry-over, untouched: [CR021](docs/forward_planning/CR021_concierge_context_router/CR021_concierge_context_router.md), [CR020](docs/forward_planning/CR020_concierge_full_context_mode/CR020_concierge_full_context_mode.md). `CONCIERGE_CONTEXT_MODE` flag (saver | full_context | embedding, default full_context) + the cheap compact lesson index. No new infra.

**Also filed, not yet started:** CR026 (sector
concentration enforcement — real compliance gap), CR027 (price alerts — hard-gated on
Saiful's A15 cert work), CR028/CR029 (trailing stop / cost-basis lots — Tier 3,
correctly deferred), CR030 (dividend fields — small), CR031 (voice STT/TTS benchmark —
zero external blocker, just needs the bench scripts run).

*All 9 R54 defects (DEF039/040/042/045/046/047/048/049/050) resolved + audited COMPLETE; DEF042/039/040/049 live on Alpha. CR018 lesson numbering done. App icon shipped — the old "native splash + app icon" deferral is now just native splash.*

**CR004 mobile deferrals (polish, not blocking):** native splash (branded launch screen — icon now exists to source from); C1 glass sheets (modal-geometry risk); the auth/merge SnackBar→HexToast sweep (~14 sites); Floor "unseen agent" unlocked-unvisited signal (needs new persistence); "show my real name" toggle (needs a backend `show_display_name` route). **Plan A verification** — device matrix + degradation drills when Saiful has device time ([build_verification_execution.md](docs/forward_planning/CR004_release_readiness/build_verification_execution.md)).

**CR017 (research, filed AT:R53)** — multi-provider LLM routing + per-provider caching. To *build* it: Saiful owes two decisions (free-tier placement: on-prem vLLM vs cheapest API; the 4-level free/pro/max/ultra → plan-SKU mapping), then it's prompt-prefix reordering (fixes the live 18.5% vLLM cache rate — provider-agnostic, highest leverage) + generalize `VLLMProvider` → `OpenAICompatibleProvider` + provider routing. Doc: [CR017](docs/forward_planning/CR017_multiprovider_llm_routing/CR017_multiprovider_llm_routing.md).

Saiful-external (any time):

- **[CR048] Get Android testers onto the Play Store internal track** (replaces sending APKs). One-time: (1) Play Console → Setup → API access → create a service account, grant "Release to testing tracks", download its JSON key to `~/.android-keys/play-service-account.json`; (2) upload the fresh AAB manually to Internal testing (enrolls Play App Signing); (3) add testers + share the opt-in link. Then release #2+ = `scripts/publish_playstore.sh`. Full checklist: `docs/forward_planning/CR048_playstore_internal_track_fastlane/`.
- **Register the Alpaca OAuth app** → creds into `infra/alpha.env` → promote (OAuth linking currently dead on Alpha; API-key mode works — Siti Ahmad's test account is linked in apikey mode).
- Confirm TestFlight `+38` finished processing (new app icon should show); validate Siti's Alpaca keys against the paper API.
- **LunarCrush plan upgrade — now optional, not blocking.** The API key Saiful provisioned mid-AT:R57 authenticates but every v4 endpoint returns `402 "Individual or higher subscription required"` — a bare signup isn't enough, needs a paid-tier upgrade. **Superseded**: CR024 pivoted to Adanos (Reddit-only, free 250 calls/month) instead and shipped real data the same session — see below. Revisit LunarCrush only if Twitter/X-specific coverage becomes worth the upgrade cost later.

Pre-CR004 backlog (BL7, BL8, credit-consumption emission, Tier 2 translation run) is unchanged, sequences after these.

**Android build note for next session:** `ANDROID_HOME=/Volumes/Extreme Pro/Android/sdk` has a space — always use `ANDROID_HOME=/Users/saiful/android-sdk` (symlink, no space) when running `flutter build appbundle`. The `apkanalyzer` `pwd -P` → `pwd` patch is in place on the local machine; if SDK is reinstalled it needs to be re-applied. Java 25 (system JVM) breaks KGP — always use `JAVA_HOME=/Applications/Android Studio.app/Contents/jbr/Contents/Home`.

### Recent sessions (newest first)

- [AT:R64](history/AT_R0064.md) — Architect / CR052 dispatch. Wave 2 of the 07-26 delivery plan: CR026-BE (sector-cap enforcement) + CR090-BE (live-feed surcharge, Saiful chose surcharge-on-top) built + root-verified + SUBMITTED to track-U; CR030-BE + CR029-BE shipped direct; DEF110 filed (stop/target doesn't close the sim position). ⚠️ HANDOVER was 12 days stale (R59–R63 never wrapped); this wrap re-baselined the marquee state only
- [AT:R58](history/AT_R0058.md) — closed the full 12-agent truthfulness/wiring audit: DEF051 (fake portfolio/drawdown) → DEF052 (Market Analyst technicals) → DEF053 (Fundamentals valuation) → DEF054/055 (Bull/Bear journal history) → DEF056 (Room verdict now reflects the actual debate) → CR034 (real FOMC date) → DEF057 (rng flakiness, minted from DEF056's audit); all 10 lanes audited COMPLETE round 1, zero BLOCKER/MAJOR; all promoted except DEF057 (test-hygiene only)
- [AT:R57](history/AT_R0057.md) — News + Social Media analysts made truthful (CR023/CR024); real headlines (Yahoo+Alpha Vantage) + real Reddit sentiment (Adanos, after LunarCrush needed a paid-tier upgrade); audited the rest of the roster → filed DEF051 (fake portfolio/drawdown, safety-floor-relevant) + CR033
- [AT:R56](history/AT_R0056.md) — implemented CR025 (watchlist day-change badge); session shipped but never wrapped, backfilled at the start of AT:R57
- [AT:R55](history/AT_R0055.md) — News/Social analyst live-feed gap → CR023/CR024; full Silent_Scout audit → closed + deprecated the workspace, filed CR025–032, migrated everything
- [AT:R54](history/AT_R0054.md) — defect burn (DEF039/040/042/045/046/047/048/049/050) + full audit handshake, app icon "Diagonal duo", build +38 (TestFlight+APK), CR018 lesson numbers, CR019–022 filed

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

- **Anthropic API key.** Not added — and not needed: on-prem vLLM at `192.168.20.74:8000` serves `ami-llm` (`Qwen3.6-35B-A3B-NVFP4`) for every agent. Anthropic remains a hot-swappable fallback if `VLLM_BASE_URL` is unset.
- **Supabase project.** Not yet provisioned. RLS policies live but dormant — they enforce once the backend stops connecting as `postgres`.
- **Apple Developer team.** Done (`S7RBWM4879`). Sign in with Apple capability enabled at the bundle ID (Saiful, AT:R26) + entitlements file in Xcode + provisioning profile regenerated (AT:R29). Phase 3 JWKS verification shipped AT:R29 — fully live end-to-end.
- **App Store + APNs** — external. Market data is real Yahoo when `USE_REAL_MARKET_DATA=true`.

Nothing is blocking the next chunk.
