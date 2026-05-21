# Handover — AMI Trade build session

**Last updated:** 2026-05-21 (end of AT:R32 — quick-wins close-out session). **Major closes:** SMTP swap → Resend HTTP API (live on Alpha; magic-link delivered end-to-end to Gmail). **`build_testflight.sh` rewrite chip** landed — staged Flutter + xcodebuild + exportArchive with `-allowProvisioningUpdates`. **TestFlight `+25` + `+26`** shipped (Saiful's hands; `+26` via the rewritten script). **Account-linking Phase 1** — `_claim_or_create` + `sign_in_with_apple` now adopt existing-identity users by email instead of forking parallel rows. **CFBundleDisplayName casing** (`Ami Trade` → `AMI Trade`). **BL13, BL14, BL15, L-1 residual** all closed. **375 tests passing** (was 367 — +8 across account-linking, BL13, L-1). **3 Alpha promotes**: `alpha-2026-05-22-1` (Resend), `alpha-2026-05-22-2` (account-linking), `alpha-2026-05-22-3` (BL13/L-1/etc). AT:R31 wrap is now in [history_R.md](history_R.md).

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **277 commits** (10 new this session — 9 AT:R32 work commits + 1 pubspec bump from the rewritten `build_testflight.sh` shipping `+26`), no remote yet |
| Latest work commit | `62b7c6d` — feat(auth): BL13 — bind OnboardingSession.claimed_user_id on claim (AT:R32). |
| Alpha tags | **3 promotes this session.** Latest `alpha-2026-05-22-3` (BL13 + L-1 + BL14 + BL15). Earlier today: `alpha-2026-05-22-1` (Resend swap), `alpha-2026-05-22-2` (account-linking Phase 1). |
| Backend tests | **375 passed, 0 failed** (was 367 — +4 account-linking Phase 1 + +2 BL13 + +2 misc; L-1 rewrote one test in place). |
| Mobile pubspec | **`0.1.0+26`** (was `+25` — bumped automatically by the rewritten `scripts/build_testflight.sh` when Saiful shipped `+26` to TestFlight). Both `+25` and `+26` are uploaded to App Store Connect; processing complete. **Note**: `+26` carries the AT:R32 backend + the CFBundleDisplayName casing fix; `+25` was shipped before that casing landed. |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **312 i18n keys**. Unchanged. |

```
$ git log --oneline | head -12
62b7c6d feat(auth): BL13 — bind OnboardingSession.claimed_user_id on claim
98edbd0 refactor(auth): L-1 — remove OneOnOneStartRequest.user_id (audit A3 pattern)
7b44110 fix(mobile): BL14 — parse Brief proposedAt/startedAt timestamps
e238f12 chore(schema): BL15 — delete dormant AgentActivation Pydantic class
1166cad feat(auth): account linking Phase 1 — adopt existing identity on claim
35a5181 build(testflight): rewrite as staged xcodebuild + add ExportOptions.plist
05ae2c3 chore(mobile): bump build 0.1.0+25 → 0.1.0+26 for TestFlight
f57d1a1 fix(mobile): CFBundleDisplayName casing — Ami Trade → AMI Trade
232e8c5 feat(email): swap SMTP for Resend HTTP API (SMTP_HOST ISP-blocked on melehost)
549799e chore(handover): wrap AT:R31
47c08a4 chore(schema+plan): drop dead User.deleted_at + file BL14/BL15 from post-audit sweep (AT:R31)
19a0617 revert(scripts): drop -allowProvisioningUpdates pass-through — flutter build ipa doesn't accept '--' xcodebuild args (AT:R31)
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
| Routes | `/v1/health`, `/v1/auth/*` (incl. `DELETE /v1/auth/session` — Phase 4 sign-out, AT:R26), `/v1/admin/*` (9 routes — AT:R27, see "Admin back-office" below), `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/brief/*` (was `/v1/coach/*` — renamed AT:R27; legacy `/v1/coach/*` kept as deprecated alias logging `deprecated_coach_route_used`), `/v1/journal/*` (incl. `/trash`, `/{id}/restore`), `/v1/lessons/*`, `/v1/llm/status`, `/v1/mandate/*`, `/v1/room/*`, `/v1/sim/*`, `/v1/watchlist/*`, `/v1/feedback/bug` (`multipart/form-data` with optional `file`). Plus a public HTML page at `/admin` (no auth required; the page itself asks for the `ADMIN_SECRET` bearer on first load + stores in localStorage). |
| Mac-side tests | `backend/.venv/bin/pytest backend/tests/unit/ -q` — **375 passed** (was 367; AT:R32 added +8: 4 account-linking Phase 1 cases in `test_auth_service.py`, 2 BL13 binding cases + 1 L-1-rewritten case in `test_auth_phase1_5_audit_fixes.py`). Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
| Env knobs (alpha) | `AMI_ENV=staging` + `SECRET_KEY=<64-hex>` + `ADMIN_SECRET=<64-hex>` (AT:R27, admin back-office bearer) + `SMTP_{HOST,PORT,USER,PASSWORD,FROM}` (5 vars, AT:R26 — now dormant) + **`RESEND_API_KEY=re_<…>`** (AT:R32, primary outbound mail route). Canonical at `infra/alpha.env` on Mac, gitignored; shipped via `scp` in `/promote-to-alpha` step 4. Without `SECRET_KEY` the backend refuses to start when env != local. **Email transport**: `email_service` prefers Resend (HTTP API, port 443 — bypasses melehost's ISP block on outbound 25/587) when `RESEND_API_KEY` is set; falls back to SMTP if `SMTP_HOST` is configured; falls back to no-op otherwise. Verified live: magic-link delivered to Gmail end-to-end. |
| Auth | Phase 1.5 + Phase 3 + Phase 4 enforced. Route-level `get_current_user` on `/v1/mandate`, `/v1/journal`, `/v1/watchlist`, `/v1/brief` (legacy `/v1/coach`), `/v1/agents/one_on_one`, `/v1/room`, plus per-route on user-specific `sim` + `lessons`. Bearer format `scaffold:<user_id_hex>:<hmac_sig>` (HMAC-SHA256 with `SECRET_KEY`). Legacy unsigned `scaffold:<hex>` accepted only in env=local. `/v1/auth/anon` mints fresh unless the caller's Bearer matches the supplied `device_user_id`. Magic-link routes require auth and bind to `current_user.id`. **Apple Sign-In Phase 3 (AT:R29):** `/v1/auth/apple` now lives in every env (no more 503 gate). `OIDCVerifier` in `app/services/oidc_verifier.py` fetches Apple's JWKS, RSA-verifies the identity token, validates `iss=https://appleid.apple.com`, `aud ∈ APPLE_AUDIENCES`, `exp`. On first auth: persists `email` + `full_name` (→ `users.display_name`). On subsequent auths or magic-link priors: preserves existing email/name (never overwritten). `DELETE /v1/auth/session` (Phase 4) requires auth and returns `{"signed_out": true}` — stateless no-op now. `http_audit` middleware scrubs request + response bodies for all `/v1/auth/*` routes (AT:R26 B4 close). **AT:R27 suspension enforcement:** `get_current_user` checks `users.suspended_at`; if set, raises `403 {"detail": "account_suspended"}`. **AT:R31 D-039 trial activation (BL3):** `_claim_or_create()` (magic-link) and `sign_in_with_apple()` (Apple) now populate `users.trial_started_at = now()` + `users.trial_expires_at = now() + 7d` on first claim. Guarded by `trial_started_at is None` so admin-granted trials are preserved. Downstream entitlement gate / expiry banner / conversion modal still TODO (BL11). **AT:R32 account-linking Phase 1:** `_claim_or_create()` now does email-lookup-FIRST (adopt existing identity), then user_id-fallback (promote anon). `sign_in_with_apple()` gained an email fallback between apple_sub and user_id lookups — magic-link-first + Apple-later (with same email) now attaches `apple_id` to the existing row instead of forking. Existing-row's email is never mutated by re-verify. Pre-claim anon rows are left orphan (ephemeral). Real merge UX deferred to BL16. **AT:R32 BL13 binding:** `/v1/auth/magic_link/verify` + `/v1/auth/apple` accept optional `onboarding_session_id`; route looks up `OnboardingSession` in `session_store` and stamps `claimed_user_id`. Both routes are now async. **AT:R32 L-1 cleanup:** `OneOnOneStartRequest.user_id` removed — `/v1/agents/one_on_one/start` sources user from Bearer only (audit A3 pattern, finally consistent). **Admin auth:** `/v1/admin/*` uses `Authorization: Bearer <ADMIN_SECRET>`. Audit finding A4 CLOSED. |
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

Tables: `users` (with `suspended_at`, `trial_started_at`, `trial_expires_at` — AT:R27; `display_name` — AT:R29), `auth_challenges`, `mandates`, `agent_activations`, `lessons_progress`, `journal_entries` (with `deleted_at`), `overlay_edit_counts`, `user_overlays`, `room_runs`, `sim_holdings`, `sim_portfolios`, `sim_trades`, `sim_watchlists`, `bug_reports` (with `assigned_branch`, `attachment_path`, `attachment_mime`), `llm_audit`, `http_audit`, `one_on_one_messages`, `subscription_events` (AT:R27), `alembic_version`. Latest migration on melehost: **`b3f9d2a80007`** (`users_display_name` — AT:R29, adds the `display_name` column for OIDC name persistence). `init_schema()` self-stamps Alembic on a fresh container, so `alembic upgrade head` is a no-op on first boot. Bug-report attachments live in the named docker volume `ami-trade-local_bug_attachments` mounted at `/data/bug_attachments` in the api-alpha container.

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

## What just landed (this session — AT:R32)

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

### Carry-overs for AT:R33

The remaining unblocked items + persistent external blockers:

1. **`eeeb866f` — Room run survives container restart.** Open bug, pre-Beta resilience. Carries from AT:R30+.
2. **B-tier adversarial-audit findings** — rate limiting on `/auth/anon` + LLM-heavy routes; magic-link attempt counter; feedback upload streaming.
3. **Docs reconciliation — `tradingagent_integration.md` + `flutter_implementation.md`.** Last two untested doc trees. ~60 min. Apply the AT:R30/R31 methodology.
4. **BL16** — Real account merge UX (filed this session).
5. **BL11** — Trial-end UX (push integration still missing even though SMTP closed).
6. **BL12** — Mandate audit on hard edits.
7. **A6b — Google Sign-In on Android.** Blocked on Google Cloud Console setup.
8. **External TestFlight launch.** Beta App Description from Saiful + ~24h Apple review. **`+26` is uploaded** + carries CFBundleDisplayName casing + AT:R32 backend changes.
9. **Animation production** — 15 `<Animation>` MDX tags still render `AmiHexPlaceholder`.
10. **A29 light-mode refactor** — v1.0 work.
11. **`claude/*` sibling worktrees on disk** — Saiful decision (keep or delete).
12. **Brief safety-floor terminology audit (deferred)** — "uncoachable" stays.
13. **Credit consumption** — `credits_consumed` event type exists but no app code emits it.
14. **BL1, BL2** (low pri) — Device info on `/v1/auth/anon`, `user_devices` table.
15. **BL4–BL10** (low pri) — AT:R30 audit deferrals.
16. **BL11–BL15** — AT:R31 audit deferrals. **BL13, BL14, BL15 closed this session.** BL11, BL12 remain.

### Watch items (not tasks)

- **3 users with same human, none linked.** Saiful's test data has 3 rows: `8f1e288a` (Apple, `saifulsaid@me.com`), `b747faf3` (magic-link, `saiful@atmmarketintel.com`), `d9e81e45` (orphan magic-link challenge, `saiful.mazli@gmail.com` — never verified). Phase 1 adopt-by-email logic is live but doesn't retroactively merge existing rows. Hand-merge later if you want one to be canonical, or just accept they're test artifacts.
- **Resend deliverability.** First production magic-link flowed cleanly to Gmail in <2s. Watch for spam-folder rate on the @atmmarketintel.com domain once volume picks up — Resend's free tier and verified-sender-domain setup may need attention before Beta.
- **TestFlight `+26` is the freshest build.** Carries CFBundleDisplayName casing + AT:R32 backend (via Alpha tag `alpha-2026-05-22-3`). If you reinstall TF before next build, you should see "AMI Trade" home-screen label.
- **`OnboardingSession.claimed_user_id` is now wireable but no Flutter client sends `onboarding_session_id` yet.** Backwards-compatible no-op until Flutter is updated. Update Flutter when something starts consuming the binding (cohort analytics dashboard, GDPR deletion path).

---

## How to start the next session

```
/start-fresh R
```

The slash command reads `HANDOVER_R.md` + `docs/10_delivery/project_plan.md`, runs the configured sanity checks (Alpha health curl), queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R33** (this is handover #32).

If Alpha is down at session start, `/start-fresh` will surface that and tell you the melehost debug commands.

If the first message is a specific task ("fix this", "add that"), skip `/start-fresh` and just do the task — the slash command is for the "let's keep going" opening.

Quick-win candidates for next session (in priority order):

1. **Docs reconciliation — `tradingagent_integration.md` + `flutter_implementation.md`.** Last two untested doc trees. ~60 min. Apply the AT:R30/R31 methodology (parallel Explore agents per file, triage with Saiful, commit one tree per pass).
2. **`eeeb866f` Room run survives container restart.** The one remaining open bug, pre-Beta resilience.
3. **B-tier audit work** — pick one: rate limiting on `/auth/anon`, magic-link attempt counter, feedback upload streaming.
4. **BL16 design** — start the account-merge UX wireframes if Saiful wants to think product before code.
5. **`claude/*` sibling worktrees** — quick decision (keep or delete).

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
