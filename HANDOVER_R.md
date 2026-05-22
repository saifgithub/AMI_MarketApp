# Handover — AMI Trade build session

**Last updated:** 2026-05-22 (end of AT:R33 — BL-closeout sprint). **Closed 7 BL items**: BL9 sim preview, BL10 daily-challenge attempt, BL1 device info on /auth/anon, BL12 mandate audit on hard edits, BL2 user_devices multi-device tracking, BL11 trial-end entitlement gate, BL5 mandate history API. **Plus** reconciled the last two untested doc trees (`tradingagent_integration.md`, `flutter_implementation.md`) against actual codebase. **422 tests passing** (was 375 — +47 across the seven BLs). **4 Alpha promotes**: `alpha-2026-05-22-4` (BL9/10/1/12), `alpha-2026-05-22-5` (BL2 + migration), `alpha-2026-05-22-6` (BL11), `alpha-2026-05-22-7` (BL5). **TestFlight `+27` shipped** by Saiful — carries BL1 + BL2 mobile (device_info_plus + device_install_id). AT:R32 wrap is now in [history_R.md](history_R.md).

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **288 commits** (11 new this session — 1 docs reconciliation + 7 BL features + 1 pubspec bump + 1 Podfile.lock + 1 handover wrap), no remote yet |
| Latest work commit | `d3cb451` — feat(mandate): BL5 — mandate history API (AT:R33). |
| Alpha tags | **4 promotes this session.** Latest `alpha-2026-05-22-7` (BL5). Earlier today: `alpha-2026-05-22-4` (BL9/10/1/12), `-5` (BL2 + migration), `-6` (BL11). |
| Backend tests | **422 passed, 0 failed** (was 375 — +47 across the seven BLs: +3 BL9 +5 BL10 +4 BL1 +8 BL12 +5 BL2 +12 BL11 +10 BL5). |
| Mobile pubspec | **`0.1.0+27`** (was `+26` — bumped by `scripts/build_testflight.sh` when Saiful shipped `+27`). Uploaded to App Store Connect. Carries BL1 + BL2 mobile changes (device_info_plus pod + device_install_id) — first build where Saiful's two phones will surface as two devices under one user post-Apple-claim. |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **312 i18n keys**. Unchanged. |

```
$ git log --oneline | head -12
19eb5d7 chore(mobile): Podfile.lock — pull device_info_plus pod (BL1)
ecea7bb chore(mobile): bump build 0.1.0+26 → 0.1.0+27 for TestFlight
d3cb451 feat(mandate): BL5 — mandate history API (AT:R33)
95e2337 feat(entitlements): BL11 — trial-end gate downgrades expired trials (AT:R33)
2d8a0d8 feat(auth): BL2 — user_devices multi-device tracking (AT:R33)
efe6b79 feat(mandate): BL12 — GET /v1/mandate/{user_id}/audit (AT:R33)
9e1ce93 feat(auth): BL1 — device + build context on /v1/auth/anon (AT:R33)
e5fbfc6 feat(daily_challenge): BL10 — POST /v1/daily_challenge/{cid}/attempt (AT:R33)
7e5aa9a feat(sim): BL9 — POST /v1/sim/preview pre-flight endpoint (AT:R33)
eaa12ce docs(tech): reconcile tradingagent_integration + flutter_implementation (AT:R33)
011832e chore(handover): wrap AT:R32
62b7c6d feat(auth): BL13 — bind OnboardingSession.claimed_user_id on claim
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
| Routes | `/v1/health`, `/v1/auth/*` (incl. `DELETE /v1/auth/session` — Phase 4 sign-out, AT:R26), `/v1/admin/*` (9 routes — AT:R27, see "Admin back-office" below), `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/brief/*` (was `/v1/coach/*` — renamed AT:R27; legacy `/v1/coach/*` kept as deprecated alias logging `deprecated_coach_route_used`), `/v1/journal/*` (incl. `/trash`, `/{id}/restore`), `/v1/lessons/*`, `/v1/llm/status`, `/v1/mandate/*` (now incl. **`/{u}/audit`** — BL12, **`/{u}/versions`** + **`/{u}/versions/{v}`** + **`POST /{u}/rollback/{v}`** — BL5, all AT:R33), `/v1/room/*`, `/v1/sim/*` (now incl. **`POST /sim/preview`** — BL9, AT:R33), `/v1/daily_challenge/*` (now incl. **`POST /{cid}/attempt`** — BL10, AT:R33), `/v1/watchlist/*`, `/v1/feedback/bug` (`multipart/form-data` with optional `file`). Plus a public HTML page at `/admin` (no auth required; the page itself asks for the `ADMIN_SECRET` bearer on first load + stores in localStorage). |
| Mac-side tests | `backend/.venv/bin/pytest backend/tests/unit/ -q` — **422 passed** (was 375; AT:R33 added +47 across the seven BLs landed this session). Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
| Env knobs (alpha) | `AMI_ENV=staging` + `SECRET_KEY=<64-hex>` + `ADMIN_SECRET=<64-hex>` (AT:R27, admin back-office bearer) + `SMTP_{HOST,PORT,USER,PASSWORD,FROM}` (5 vars, AT:R26 — now dormant) + **`RESEND_API_KEY=re_<…>`** (AT:R32, primary outbound mail route). Canonical at `infra/alpha.env` on Mac, gitignored; shipped via `scp` in `/promote-to-alpha` step 4. Without `SECRET_KEY` the backend refuses to start when env != local. **Email transport**: `email_service` prefers Resend (HTTP API, port 443 — bypasses melehost's ISP block on outbound 25/587) when `RESEND_API_KEY` is set; falls back to SMTP if `SMTP_HOST` is configured; falls back to no-op otherwise. Verified live: magic-link delivered to Gmail end-to-end. |
| Auth | Phase 1.5 + Phase 3 + Phase 4 enforced. Route-level `get_current_user` on `/v1/mandate`, `/v1/journal`, `/v1/watchlist`, `/v1/brief` (legacy `/v1/coach`), `/v1/agents/one_on_one`, `/v1/room`, plus per-route on user-specific `sim` + `lessons`. Bearer format `scaffold:<user_id_hex>:<hmac_sig>` (HMAC-SHA256 with `SECRET_KEY`). Legacy unsigned `scaffold:<hex>` accepted only in env=local. `/v1/auth/anon` mints fresh unless the caller's Bearer matches the supplied `device_user_id`. Magic-link routes require auth and bind to `current_user.id`. **Apple Sign-In Phase 3 (AT:R29):** `/v1/auth/apple` now lives in every env (no more 503 gate). `OIDCVerifier` in `app/services/oidc_verifier.py` fetches Apple's JWKS, RSA-verifies the identity token, validates `iss=https://appleid.apple.com`, `aud ∈ APPLE_AUDIENCES`, `exp`. On first auth: persists `email` + `full_name` (→ `users.display_name`). On subsequent auths or magic-link priors: preserves existing email/name (never overwritten). `DELETE /v1/auth/session` (Phase 4) requires auth and returns `{"signed_out": true}` — stateless no-op now. `http_audit` middleware scrubs request + response bodies for all `/v1/auth/*` routes (AT:R26 B4 close). **AT:R27 suspension enforcement:** `get_current_user` checks `users.suspended_at`; if set, raises `403 {"detail": "account_suspended"}`. **AT:R31 D-039 trial activation (BL3):** `_claim_or_create()` (magic-link) and `sign_in_with_apple()` (Apple) now populate `users.trial_started_at = now()` + `users.trial_expires_at = now() + 7d` on first claim. Guarded by `trial_started_at is None` so admin-granted trials are preserved. Downstream entitlement gate / expiry banner / conversion modal still TODO (BL11). **AT:R32 account-linking Phase 1:** `_claim_or_create()` now does email-lookup-FIRST (adopt existing identity), then user_id-fallback (promote anon). `sign_in_with_apple()` gained an email fallback between apple_sub and user_id lookups — magic-link-first + Apple-later (with same email) now attaches `apple_id` to the existing row instead of forking. Existing-row's email is never mutated by re-verify. Pre-claim anon rows are left orphan (ephemeral). Real merge UX deferred to BL16. **AT:R32 BL13 binding:** `/v1/auth/magic_link/verify` + `/v1/auth/apple` accept optional `onboarding_session_id`; route looks up `OnboardingSession` in `session_store` and stamps `claimed_user_id`. Both routes are now async. **AT:R32 L-1 cleanup:** `OneOnOneStartRequest.user_id` removed — `/v1/agents/one_on_one/start` sources user from Bearer only (audit A3 pattern, finally consistent). **AT:R33 BL1 device context:** `/v1/auth/anon` accepts optional `device_model`, `os_version`, `app_version`; backend persists onto `users` (refreshed on every bootstrap). **AT:R33 BL2 user_devices:** `/v1/auth/anon` also accepts optional `device_install_id` (mobile-generated UUID, never overwritten by claim). Backend upserts a `user_devices` row keyed by install_id; on claim adoption (`_claim_or_create` + `sign_in_with_apple`), the pre-claim anon's devices re-key to the adopting user so two phones on one Apple ID surface under one user. **AT:R33 BL11 entitlement gate:** `effective_plan(plan, trial_expires_at)` is now resolved at every `pick_tier()` callsite (brief_engine, agent_runner, room_runner) — when a trial lapses, LLM routing automatically drops to cheap-tier without admin intervention. **Admin auth:** `/v1/admin/*` uses `Authorization: Bearer <ADMIN_SECRET>`. Audit finding A4 CLOSED. |
| Room env knobs | `ROOM_DEDUP_RUNNING_MINUTES=30` (in-flight dedup + startup-sweep cutoff) · `ROOM_DEDUP_COMPLETED_HOURS=24` (return prior verdict same day; design doc default was 5 days — we start tighter). Set completed_hours=0 to disable cached-run dedup. |
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

Tables: `users` (with `suspended_at`, `trial_started_at`, `trial_expires_at` — AT:R27; `display_name` — AT:R29; `device_model`, `os_version`, `last_app_version` — AT:R33 BL1), `auth_challenges`, `mandates`, `agent_activations`, `lessons_progress`, `journal_entries` (with `deleted_at`), `overlay_edit_counts`, `user_overlays`, `room_runs`, `sim_holdings`, `sim_portfolios`, `sim_trades`, `sim_watchlists`, `bug_reports` (with `assigned_branch`, `attachment_path`, `attachment_mime`), `llm_audit`, `http_audit`, `one_on_one_messages`, `subscription_events` (AT:R27), **`user_devices`** (AT:R33 BL2 — per-install rows keyed by device_install_id, backfilled 24 rows from existing users.device_user_id), `alembic_version`. Latest migration on melehost: **`d5f2a3b00009`** (`user_devices` — AT:R33 BL2). Prior in chain: `c4e8f1a90008` (`users_device_info` — AT:R33 BL1), `b3f9d2a80007` (`users_display_name` — AT:R29). `init_schema()` self-stamps Alembic on a fresh container, so `alembic upgrade head` is a no-op on first boot. Bug-report attachments live in the named docker volume `ami-trade-local_bug_attachments` mounted at `/data/bug_attachments` in the api-alpha container.

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
| pubspec version | **`0.1.0+24`** (repo). AT:R29 shipped `+19`/`+20`/`+22`/`+23`/`+24` — see TestFlight row below. `+24` carries Apple Phase 3 + entitlements + email+display_name persistence + hex revert. |
| TESTING IPHONE 13 install | `+18` uploaded to TestFlight 2026-05-20 15:02 UTC; processing in App Store Connect (~15–30 min). Once processed, install via TestFlight on device. For pre-TF dev smoke, use `scripts/install_iphone.sh`. |
| TestFlight | `0.1.0+24` uploaded 2026-05-21 (delivery UUID `2a4767c6-eb48-44d6-8a94-328e8d063095`). AT:R29 sequence: `+19` (bug-report close + Lessons-style hex tint) → `+20` (hex tint reverted, close button kept) → `+22` (entitlements + Apple Sign-In working) → `+23` (email persistence) → `+24` (display_name persistence). Saiful verified Apple Sign-In end-to-end on `+22`+`+23`. External Beta still pending (no external testers added). |
| Build commands | `scripts/install_iphone.sh` (dev sideload), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **AT:R27 Floor change:** tapping an unlocked agent no longer opens 1-on-1 directly — it now opens an `AgentActionSheet` bottom sheet with two big buttons: `[1-ON-1]` (talk to the agent) and `[BRIEF]` (modify how it thinks). Concierge skips the sheet — has no Brief surface, so 1-on-1 is the only path. The tune icon in the 1-on-1 header stays as a secondary route to Brief. **AT:R27 rename:** `CoachScreen` → `BriefScreen`, `BriefHistoryScreen`, `BriefNotifier`/`briefNotifierProvider`, `models/brief.dart`, `api_client.startBrief/streamBriefMessage/...`. The 33 l10n keys flipped from `coach*` to `brief*` (including the journal chips: `journalFilterCoach` → `journalFilterBrief`, value `COACH` → `BRIEF`; same for `journalEntryTypeCoach`). Journal filter chips now read: `ALL · ROOM · TRADE · 1-ON-1 · BRIEF · LESSONS · UNLOCKS`. **First-time walkthrough (AT:R23):** per-section coach-mark tours (still using `tutorial_coach_mark` package — unrelated to Brief feature) fire on first visit. **AT:R25 auth gate** + **AT:R26 sign-out (Phase 4)** + **AT:R26 Apple-glitch fix** still in place. Journal soft-delete + Trash + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green pill once a sim_trade exists. Trade ticket sheet has live quote chip + auto-suggested TP/SL. Ticker tape below bottom nav. Settings → APPEARANCE is dark-only. Bug-report sheet (long-press app-version chip) supports photo attachments.

---

## What just landed (this session — AT:R33)

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

### Carry-overs for AT:R34

The remaining unblocked items + persistent external blockers:

1. **`eeeb866f` — Room run survives container restart.** The one real open bug, pre-Beta resilience. Carries from AT:R30+.
2. **B-tier adversarial-audit findings** — rate limiting on `/auth/anon` + LLM-heavy routes; magic-link attempt counter; feedback upload streaming.
3. **BL16** — Real account merge UX (filed AT:R32, design-first).
4. **BL6** — Mandate resolve flow (Liquidate/Postpone/Override actions). Pre-req: drift detection (MVP scope). The audit half landed AT:R33 as BL12.
5. **BL11 — push + in-app trial-end UX.** Entitlement gate landed AT:R33; mobile modal + OneSignal push still pending (Beta).
6. **BL4** — Arabic → Gemini routing. Blocked on `GoogleProvider` class in llm_gateway.
7. **BL7** — Agent metadata routes. Mobile workaround sufficient until v1.0 Android port.
8. **BL8** — Room run cancel + replay. Cancel needs Postgres-side signalling (1.5 sessions, hard); replay is sugar.
9. **A6b — Google Sign-In on Android.** Blocked on Google Cloud Console setup.
10. **External TestFlight launch.** Needs Beta App Description from Saiful + ~24h Apple review. `+27` is uploaded.
11. **Animation production** — 15 `<Animation>` MDX tags still render `AmiHexPlaceholder`.
12. **A29 light-mode refactor** — v1.0 work.
13. **`claude/*` sibling worktrees on disk** — Saiful decision (keep or delete). Carries from AT:R32.
14. **Credit consumption** — `credits_consumed` event type exists but no app code emits it.
15. **`OnboardingSession.claimed_user_id` Flutter wiring** — backend accepts `onboarding_session_id` since AT:R32 BL13 but Flutter doesn't send it yet. Update when something consumes the binding.

### Watch items (not tasks)

- **Saiful is the cross-device tester.** `+27` is the first build with device_install_id wiring. Verification flow: install on both iPhones via TestFlight → sign in with Apple on each with the same Apple ID → check admin UI; expected `devices (2)` block, both phones listed under one user.
- **Test data: 3 users with same human, still none linked.** Saiful's pre-AT:R32 test data has 3 rows (`8f1e288a` Apple, `b747faf3` magic-link, `d9e81e45` orphan challenge). AT:R32 Phase 1 adopt-by-email logic prevents future forks but doesn't retroactively merge existing rows. Hand-merge later or accept as test artifacts.
- **Backfill seeded 24 user_devices rows** on melehost during the BL2 migration. Those rows use the existing `device_user_id` as the install_id approximation — fine for legacy users, but if you compare admin's device list against the new `+27` mobile, brand-new installs will get a fresh `device_install_id` UUID rather than reuse the device_user_id one.
- **Resend deliverability + `+27` TestFlight processing** — unchanged from AT:R32 wrap, watch over time.

---

## How to start the next session

```
/start-fresh R
```

The slash command reads `HANDOVER_R.md` + `docs/10_delivery/project_plan.md`, runs the configured sanity checks (Alpha health curl), queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R34** (this is handover #33).

If Alpha is down at session start, `/start-fresh` will surface that and tell you the melehost debug commands.

If the first message is a specific task ("fix this", "add that"), skip `/start-fresh` and just do the task — the slash command is for the "let's keep going" opening.

Quick-win candidates for next session (in priority order):

1. **`eeeb866f` Room run survives container restart.** The one remaining open bug, pre-Beta resilience. AT:R33 closed every BL alpha-needle item — this is the next clear alpha lever.
2. **TF `+27` verification on two phones.** If Saiful has tested BL1+BL2 on both iPhones, capture the result (or lack thereof) and decide if BL2 needs a fix-pass.
3. **External TestFlight launch.** Beta App Description from Saiful + ~24h Apple review. Closes the alpha→beta gate.
4. **B-tier audit work** — pick one: rate limiting on `/auth/anon`, magic-link attempt counter, feedback upload streaming.
5. **`claude/*` sibling worktrees** — quick decision (keep or delete). Carries from AT:R32.
6. **BL16 design** — start the account-merge UX wireframes if Saiful wants to think product before code.

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
