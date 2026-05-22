# Handover — AMI Trade build session

**Last updated:** 2026-05-22 (end of AT:R35 — i18n Tier 1 lands). **Tier 1 ARB translations done via on-prem vLLM Gemma 4 31B** (LAN-direct, bypassing CF Tunnel). 311/311 AR keys + 310/311 MS keys filled — was 302/302 with 65 AR + 79 MS identical-to-EN. **Total ~7 minutes wall time for 162 missing keys.** Also: diagnosed why both iPhones see different progress despite same Apple ID (sign-out clears local identity → new anon user; both phones are currently on different orphan anon accounts, not on `8f1e288a`). **+1 work commit + 1 wrap = 2 new commits. Backend tests still 424 (no backend changes). 0 Alpha promotes (no backend changes). Bug list still 0.** Tier 2 (glossary + ai_coach + daily_challenges) + Tier 3 (lessons) scripts shipped but NOT run — first attempt hit vLLM saturation under 4 concurrent jobs, Saiful paused. AT:R34 wrap is now in [history_R.md](history_R.md).

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **294 commits** (2 new this session — i18n pipeline + handover wrap), no remote yet |
| Latest work commit | `17b482c` — feat(i18n): on-prem vLLM translation pipeline + Tier 1 ARB AR/MS (AT:R35). |
| Alpha tags | **0 new promotes this session.** Still `alpha-2026-05-22-9` (AT:R34, mandate fallback). |
| Backend tests | **424 passed, 0 failed** — no backend changes this session. |
| Mobile pubspec | **`0.1.0+27`** — unchanged this session (no mobile changes). |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **312 i18n keys**. **Tier 1 ARB (UI strings) now translated to AR (311/311) + MS (310/311) via on-prem Gemma 4 31B.** Tier 2 + Tier 3 content remain EN-only. |

```
$ git log --oneline | head -12
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
efe6b79 feat(mandate): BL12 — GET /v1/mandate/{user_id}/audit (AT:R33)
9e1ce93 feat(auth): BL1 — device + build context on /v1/auth/anon (AT:R33)
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

## What just landed (this session — AT:R35)

**i18n Tier 1 done; Tiers 2 & 3 prepped but not yet run.** Translation infrastructure now ships LAN-direct to vLLM on `192.168.20.74:8000` via the OpenAI-compatible chat-completions API. Also diagnosed the "same Apple ID, different progress on each phone" question (it's a sign-out side-effect, not a sync bug). **1 work commit + 1 wrap = 2 new commits. 293 → 294 commits total. No backend changes; no Alpha promotes; tests still 424; bug list still 0.**

### How the session ran

Saiful opened with `/start-fresh R` (session name `AT:R35`). Plan-mode survey landed with the 15 deferred carry-overs from AT:R34 — no open bugs.

**First topic — the multi-phone observation.** Saiful: "I have the same Apple ID on two phones but different progress." Pulled the DB and found three relevant accounts: the Apple account `8f1e288a` (Siti Ahmad, 5 journal entries from earlier testing), a magic-link account `b747faf3` (saiful@atmmarketintel.com, from 3am today), and a fresh anon `0e0a9860` (iPhone 13 mini's current identity). Both phones HAVE been linked to `8f1e288a` in `user_devices` via earlier Apple Sign-In — but `signOut()` calls `DeviceUser.clear()` which wipes the persisted `(user_id, token)` pair, and the next `bootstrap()` mints a fresh anon user. After signing out, neither phone is on `8f1e288a` anymore — they're on different orphan anon accounts. Filed as: post-sign-out UX should prompt "sign back in to continue progress" rather than silently starting fresh. This is adjacent to BL16 (account merge) but cheaper to ship.

**Second topic — i18n prep.** Mapped the translation surface:
- Tier 1: 312 EN ARB keys, 10 missing in AR/MS + 65 AR / 79 MS identical-to-EN (tour walkthrough strings shipped post last translation run).
- Tier 2: 188 glossary terms, 280 AI coach Q&A, 183 daily challenges — all EN only.
- Tier 3: 270 lessons × ~283K words — all EN only.
- Agent prompts stay EN by design (LLM responds in `mandate.locale` at runtime).

**Tier 1 ran successfully.** First attempt went through `scripts/translate_arb.py` which defaults to the public CF Tunnel route (designed for worktree-sandbox portability). Cloudflare's ~100s proxy timeout chewed up the 40-key batches at 90+s each, returning 502 Bad Gateway. Saiful: "This is a crazy route". Wrote a sister script `scripts/translate_arb_lan.py` that hits vLLM's OpenAI-compatible `/v1/chat/completions` directly on the LAN. Ran in 7 minutes for 74 AR + 80 MS keys, zero timeouts. Final state: 311/311 AR keys filled, 310/311 MS keys filled (one MS placeholder dropped by Gemma → falls back to EN).

**Tier 2 + Tier 3 hit a saturation wall.** Wrote two more LAN-direct scripts (`translate_content_lan.py` for JSON-based content, `translate_lessons_lan.py` for MDX with Quiz/Term/ChatWith/Animation component parsing). Kicked all three in parallel (glossary, ai_coach, daily_challenges) plus a 2-lesson smoke test. vLLM saturated: every batch in every job timed out at 300s. The smoke-test lessons produced English-with-corrupted-frontmatter output. Saiful asked to pause; all jobs killed; partial outputs deleted; vLLM verified healthy (3s for small request after the kill drain). The lesson: vLLM continuous batching helps but doesn't scale a single H100-class GPU to 4 large concurrent generation streams without per-stream latency blowing past the 300s timeout.

### Commits in order

| Hash | What it does |
|---|---|
| `17b482c` | **i18n Tier 1: LAN-direct vLLM translation pipeline + AR/MS ARB.** Three new scripts under `scripts/translate_*_lan.py` — sister to the existing `translate_arb.py` (which is kept for worktree-sandbox portability). The LAN scripts call `http://192.168.20.74:8000/v1/chat/completions` directly with `model=ami-llm`. Tier 1 ARB outputs: `mobile/lib/l10n/app_ar.arb` 311/311, `app_ms.arb` 310/311. Also: ignore `.deliveryos/` (host-side sqlite tool memory). |

Plus the `chore(handover): wrap AT:R35` commit.

### What changed in the codebase

- `scripts/translate_arb_lan.py` (NEW) — Flutter ARB strings translator, OpenAI-compatible client.
- `scripts/translate_content_lan.py` (NEW) — glossary + ai_coach + daily_challenges translator, config-driven per content type. NOT YET RUN against the real corpora.
- `scripts/translate_lessons_lan.py` (NEW) — MDX lesson translator: frontmatter-aware, swaps MDX components for sentinels before translating prose, translates Quiz string attrs as structured JSON, reassembles. NOT YET RUN.
- `mobile/lib/l10n/app_ar.arb` — 311 keys filled (was 238 after stripping 64 identical-to-EN).
- `mobile/lib/l10n/app_ms.arb` — 310 keys filled (was 224 after stripping 78 identical-to-EN).
- `.gitignore` — `.deliveryos/` added.

### Carry-overs for AT:R36

Top-priority (new this session):

1. **Re-run Tier 2 sequentially.** vLLM can't take 4 concurrent large generation streams without each hitting timeout. Run `scripts/translate_content_lan.py --type glossary` alone, wait, then `--type ai_coach`, then `--type daily_challenges`. Glossary alone took ~50 min when last attempted (got killed mid-run). Total Tier 2 wall time sequentially: ~5 hours. Could maybe parallelize 2 jobs with deeper investigation — but 1-at-a-time is the safe path.
2. **Re-think Tier 3 (lessons) approach.** Sequential lessons = ~14 hours per locale, 28 hours total. Options: (a) per-lesson concurrency (still hits saturation), (b) bigger title/quiz batches across many lessons (reduces call count), (c) accept 28h over multiple sessions, (d) defer to v1.0 launch. Saiful's call.
3. **Backend loader changes** for `ai_coach_service.py` + `daily_challenge_service.py` to glob `<locale>/*.json` subdirectories. Glossary already supports locale natively via `terms.<locale>.json`. Without this change, Tier 2 outputs in `content/{ai_coach,daily_challenges}/{ar,ms}/` are dead weight on disk.
4. **Sign-out UX improvement.** When the user signs out, don't silently start a new anon session — show a "sign back in to continue" prompt. Adjacent to but cheaper than BL16 account-merge.

Carrying from AT:R34 (unchanged):

5. **TF `+27` cold-launch loading loop on iPhone 17 — watch item.** Not observed again this session (no device testing).
6. **External TestFlight launch.** Beta App Description from Saiful + ~24h Apple review. Closes the alpha→beta gate.
7. **B-tier adversarial-audit findings** — rate limiting on `/auth/anon` + LLM-heavy routes; magic-link attempt counter; feedback upload streaming.
8. **BL16** — Real account merge UX. Connect this with #4 (sign-out UX) — both touch the same auth surface.
9. **BL6** — Mandate resolve flow (Liquidate/Postpone/Override actions).
10. **BL11 — push + in-app trial-end UX.**
11. **BL4** — Arabic → Gemini routing. Now MORE relevant since Tier 1 AR is shipping in the next app build.
12. **BL7** — Agent metadata routes.
13. **BL8** — Room run cancel + replay.
14. **A6b — Google Sign-In on Android.**
15. **Animation production** — 15 `<Animation>` MDX tags.
16. **A29 light-mode refactor.**
17. **`claude/*` sibling worktrees on disk** — keep-or-delete decision.
18. **Credit consumption** — `credits_consumed` event type exists, no app code emits it.
19. **`OnboardingSession.claimed_user_id` Flutter wiring.**

### Watch items (not tasks)

- **vLLM saturation pattern.** A single H100-class GPU can comfortably serve 1-2 concurrent generation streams of long-form translation (1K+ output tokens), but 4 streams blow per-stream latency past the 300s client timeout. If parallelism is needed, raise the script's `DEFAULT_TIMEOUT_S` AND cap concurrency at 2. Better: run sequentially.
- **`scripts/translate_arb.py` (production path) still uses CF Tunnel.** Kept intentionally for worktree-sandbox portability. The LAN sister script is the right path when running from the Mac directly.
- **One MS string falls back to EN** (`tourJournal2Body`) because Gemma dropped a placeholder. To fix: `backend/.venv/bin/python scripts/translate_arb_lan.py --overwrite --locales ms` — but it would re-translate the other 310 keys too. Better: a one-key flag, not in scope this session.

---

## How to start the next session

```
/start-fresh R
```

The slash command reads `HANDOVER_R.md` + `docs/10_delivery/project_plan.md`, runs the configured sanity checks (Alpha health curl), queries the live bug list (currently **0 open**), then enters plan mode asking what to work on. Wait for direction — no bug to forcibly tackle.

Session name to use: **AT:R36** (this is handover #35).

If Alpha is down at session start, `/start-fresh` will surface that and tell you the melehost debug commands.

If the first message is a specific task ("fix this", "add that"), skip `/start-fresh` and just do the task — the slash command is for the "let's keep going" opening.

Quick-win candidates for next session (in priority order):

1. **Tier 2 sequential translation run** — kick `glossary` first (smallest, ~50 min), then `ai_coach`, then `daily_challenges`. Single foreground job; vLLM single-stream is reliable.
2. **Tier 3 (lessons) approach call** — decide on parallelism + batching strategy before committing 28 hours of GPU.
3. **Backend loader changes** for `ai_coach_service.py` + `daily_challenge_service.py` to glob `<locale>/*.json` subdirectories. Small, isolated diff; unlocks Tier 2 outputs once they exist.
4. **External TestFlight launch.** Beta App Description from Saiful + ~24h Apple review.
5. **Sign-out UX** (BL16-adjacent) — prompt "sign back in to continue progress" instead of silently minting a new anon user.
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
