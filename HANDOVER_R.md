# Handover — AMI Trade build session

**Last updated:** 2026-05-22 (end of AT:R34 — `eeeb866f` close). **Bug closed end-to-end**: Room run survives api-alpha container restart. Startup sweep now auto-retries stuck runs once (claims the row, bumps a new `retry_count`, clears transcript, re-spawns the background task with the original run_id) instead of marking-failed-and-forcing-resubmit. Avoided the Celery+Redis path the bug originally scoped (3-4 days) by reusing the existing `asyncio.create_task` pattern. **+2 work commits + 1 handover wrap = 3 new commits. 424 tests passing (was 422 — +2 retry tests). 2 Alpha promotes (`-8` sweep+retry, `-9` mandate-fallback). Bug list now empty (was 1 open).** Verified live: seeded a synthetic stuck row on alpha, restarted container, watched `room_startup_sweep → room_startup_retry_respawned → room_completed APPROVE → room_startup_retry_journal_written` fire end-to-end with a journal entry landing. Also confirmed BL1+BL2 working on both phones via direct DB inspection (iPhone 17 `iPhone18,1` + iPhone 13 mini `iPhone14,4` both signed in with same Apple ID → 2 devices under user `8f1e288a`). AT:R33 wrap is now in [history_R.md](history_R.md).

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **291 commits** (3 new this session — sweep+retry, mandate fallback, handover wrap), no remote yet |
| Latest work commit | `3f4022a` — fix(room): retry path falls back to resolve_mandate when version row missing (AT:R34). |
| Alpha tags | **2 promotes this session.** Latest `alpha-2026-05-22-9` (mandate fallback). Earlier today: `alpha-2026-05-22-8` (sweep+retry). |
| Backend tests | **424 passed, 0 failed** (was 422 — +2 retry tests on top of an existing sweep test that was refactored to match the new claim-vs-fail policy). |
| Mobile pubspec | **`0.1.0+27`** — unchanged this session (no mobile changes). Uploaded to App Store Connect AT:R33; carries BL1 + BL2 (device_info_plus pod + device_install_id). |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **312 i18n keys**. Unchanged. |

```
$ git log --oneline | head -12
3f4022a fix(room): retry path falls back to resolve_mandate when version row missing (AT:R34)
8510436 fix(room): eeeb866f — startup auto-retry for runs killed by container restart (AT:R34)
1625e80 chore(handover): wrap AT:R33
19eb5d7 chore(mobile): Podfile.lock — pull device_info_plus pod (BL1)
ecea7bb chore(mobile): bump build 0.1.0+26 → 0.1.0+27 for TestFlight
d3cb451 feat(mandate): BL5 — mandate history API (AT:R33)
95e2337 feat(entitlements): BL11 — trial-end gate downgrades expired trials (AT:R33)
2d8a0d8 feat(auth): BL2 — user_devices multi-device tracking (AT:R33)
efe6b79 feat(mandate): BL12 — GET /v1/mandate/{user_id}/audit (AT:R33)
9e1ce93 feat(auth): BL1 — device + build context on /v1/auth/anon (AT:R33)
e5fbfc6 feat(daily_challenge): BL10 — POST /v1/daily_challenge/{cid}/attempt (AT:R33)
7e5aa9a feat(sim): BL9 — POST /v1/sim/preview pre-flight endpoint (AT:R33)
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
| Mac-side tests | `backend/.venv/bin/pytest backend/tests/unit/ -q` — **424 passed** (was 422; AT:R34 added +2 retry tests on top of a refactored sweep test). Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
| Env knobs (alpha) | `AMI_ENV=staging` + `SECRET_KEY=<64-hex>` + `ADMIN_SECRET=<64-hex>` (AT:R27, admin back-office bearer) + `SMTP_{HOST,PORT,USER,PASSWORD,FROM}` (5 vars, AT:R26 — now dormant) + **`RESEND_API_KEY=re_<…>`** (AT:R32, primary outbound mail route). Canonical at `infra/alpha.env` on Mac, gitignored; shipped via `scp` in `/promote-to-alpha` step 4. Without `SECRET_KEY` the backend refuses to start when env != local. **Email transport**: `email_service` prefers Resend (HTTP API, port 443 — bypasses melehost's ISP block on outbound 25/587) when `RESEND_API_KEY` is set; falls back to SMTP if `SMTP_HOST` is configured; falls back to no-op otherwise. Verified live: magic-link delivered to Gmail end-to-end. |
| Auth | Phase 1.5 + Phase 3 + Phase 4 enforced. Route-level `get_current_user` on `/v1/mandate`, `/v1/journal`, `/v1/watchlist`, `/v1/brief` (legacy `/v1/coach`), `/v1/agents/one_on_one`, `/v1/room`, plus per-route on user-specific `sim` + `lessons`. Bearer format `scaffold:<user_id_hex>:<hmac_sig>` (HMAC-SHA256 with `SECRET_KEY`). Legacy unsigned `scaffold:<hex>` accepted only in env=local. `/v1/auth/anon` mints fresh unless the caller's Bearer matches the supplied `device_user_id`. Magic-link routes require auth and bind to `current_user.id`. **Apple Sign-In Phase 3 (AT:R29):** `/v1/auth/apple` now lives in every env (no more 503 gate). `OIDCVerifier` in `app/services/oidc_verifier.py` fetches Apple's JWKS, RSA-verifies the identity token, validates `iss=https://appleid.apple.com`, `aud ∈ APPLE_AUDIENCES`, `exp`. On first auth: persists `email` + `full_name` (→ `users.display_name`). On subsequent auths or magic-link priors: preserves existing email/name (never overwritten). `DELETE /v1/auth/session` (Phase 4) requires auth and returns `{"signed_out": true}` — stateless no-op now. `http_audit` middleware scrubs request + response bodies for all `/v1/auth/*` routes (AT:R26 B4 close). **AT:R27 suspension enforcement:** `get_current_user` checks `users.suspended_at`; if set, raises `403 {"detail": "account_suspended"}`. **AT:R31 D-039 trial activation (BL3):** `_claim_or_create()` (magic-link) and `sign_in_with_apple()` (Apple) now populate `users.trial_started_at = now()` + `users.trial_expires_at = now() + 7d` on first claim. Guarded by `trial_started_at is None` so admin-granted trials are preserved. Downstream entitlement gate / expiry banner / conversion modal still TODO (BL11). **AT:R32 account-linking Phase 1:** `_claim_or_create()` now does email-lookup-FIRST (adopt existing identity), then user_id-fallback (promote anon). `sign_in_with_apple()` gained an email fallback between apple_sub and user_id lookups — magic-link-first + Apple-later (with same email) now attaches `apple_id` to the existing row instead of forking. Existing-row's email is never mutated by re-verify. Pre-claim anon rows are left orphan (ephemeral). Real merge UX deferred to BL16. **AT:R32 BL13 binding:** `/v1/auth/magic_link/verify` + `/v1/auth/apple` accept optional `onboarding_session_id`; route looks up `OnboardingSession` in `session_store` and stamps `claimed_user_id`. Both routes are now async. **AT:R32 L-1 cleanup:** `OneOnOneStartRequest.user_id` removed — `/v1/agents/one_on_one/start` sources user from Bearer only (audit A3 pattern, finally consistent). **AT:R33 BL1 device context:** `/v1/auth/anon` accepts optional `device_model`, `os_version`, `app_version`; backend persists onto `users` (refreshed on every bootstrap). **AT:R33 BL2 user_devices:** `/v1/auth/anon` also accepts optional `device_install_id` (mobile-generated UUID, never overwritten by claim). Backend upserts a `user_devices` row keyed by install_id; on claim adoption (`_claim_or_create` + `sign_in_with_apple`), the pre-claim anon's devices re-key to the adopting user so two phones on one Apple ID surface under one user. **AT:R33 BL11 entitlement gate:** `effective_plan(plan, trial_expires_at)` is now resolved at every `pick_tier()` callsite (brief_engine, agent_runner, room_runner) — when a trial lapses, LLM routing automatically drops to cheap-tier without admin intervention. **Admin auth:** `/v1/admin/*` uses `Authorization: Bearer <ADMIN_SECRET>`. Audit finding A4 CLOSED. |
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
| pubspec version | **`0.1.0+27`** (repo). Carries Apple Phase 3 (AT:R29) + entitlements + email+display_name persistence + BL1 device context + BL2 device_install_id (AT:R33). No mobile changes AT:R34. |
| TestFlight | **`0.1.0+27`** uploaded 2026-05-22 by Saiful. Verified live on both iPhone 17 (iPhone18,1, iOS 26.4.2) and iPhone 13 mini (iPhone14,4, iOS 18.7.1) — both signed in with same Apple ID, both device rows under user `8f1e288a` per direct DB check (AT:R34 BL1+BL2 verification). External Beta still pending (no external testers added). One observation: iPhone 17 first launch of `+27` got stuck on a loading loop briefly; recovered without intervention (no backend errors in logs); worth watching across more cold launches. |
| Build commands | `scripts/install_iphone.sh` (dev sideload), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **AT:R27 Floor change:** tapping an unlocked agent no longer opens 1-on-1 directly — it now opens an `AgentActionSheet` bottom sheet with two big buttons: `[1-ON-1]` (talk to the agent) and `[BRIEF]` (modify how it thinks). Concierge skips the sheet — has no Brief surface, so 1-on-1 is the only path. The tune icon in the 1-on-1 header stays as a secondary route to Brief. **AT:R27 rename:** `CoachScreen` → `BriefScreen`, `BriefHistoryScreen`, `BriefNotifier`/`briefNotifierProvider`, `models/brief.dart`, `api_client.startBrief/streamBriefMessage/...`. The 33 l10n keys flipped from `coach*` to `brief*` (including the journal chips: `journalFilterCoach` → `journalFilterBrief`, value `COACH` → `BRIEF`; same for `journalEntryTypeCoach`). Journal filter chips now read: `ALL · ROOM · TRADE · 1-ON-1 · BRIEF · LESSONS · UNLOCKS`. **First-time walkthrough (AT:R23):** per-section coach-mark tours (still using `tutorial_coach_mark` package — unrelated to Brief feature) fire on first visit. **AT:R25 auth gate** + **AT:R26 sign-out (Phase 4)** + **AT:R26 Apple-glitch fix** still in place. Journal soft-delete + Trash + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green pill once a sim_trade exists. Trade ticket sheet has live quote chip + auto-suggested TP/SL. Ticker tape below bottom nav. Settings → APPEARANCE is dark-only. Bug-report sheet (long-press app-version chip) supports photo attachments.

---

## What just landed (this session — AT:R34)

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

## How to start the next session

```
/start-fresh R
```

The slash command reads `HANDOVER_R.md` + `docs/10_delivery/project_plan.md`, runs the configured sanity checks (Alpha health curl), queries the live bug list (currently **0 open**), then enters plan mode asking what to work on. Wait for direction — no bug to forcibly tackle.

Session name to use: **AT:R35** (this is handover #34).

If Alpha is down at session start, `/start-fresh` will surface that and tell you the melehost debug commands.

If the first message is a specific task ("fix this", "add that"), skip `/start-fresh` and just do the task — the slash command is for the "let's keep going" opening.

Quick-win candidates for next session (in priority order):

1. **External TestFlight launch.** Beta App Description from Saiful + ~24h Apple review. Closes the alpha→beta gate. `+27` is uploaded and verified across both iPhones. This is the next clear alpha→beta lever now that `eeeb866f` is closed.
2. **iPhone 17 cold-launch loading loop watch.** Repro attempts + log capture on real device — likely client-side first-call slow path, not backend. Quick if it doesn't repro; depth-of-fix grows if it does.
3. **B-tier audit work** — pick one: rate limiting on `/auth/anon`, magic-link attempt counter, feedback upload streaming.
4. **`claude/*` sibling worktrees** — quick decision (keep or delete). Carries from AT:R32.
5. **BL16 design** — start the account-merge UX wireframes if Saiful wants to think product before code.
6. **BL6 / BL11-push / BL4 / BL7 / BL8** — the remaining BL backlog; each is a real session's worth of work.

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
