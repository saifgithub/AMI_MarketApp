# Handover — AMI Trade build session

**Last updated:** 2026-05-20 (end of AT:R27 — big session, 8 commits, 8 alpha tags). **Admin back-office foundation** shipped: `users.suspended_at` + `subscription_events` table (10 event types) + 9 endpoints at `/v1/admin/*` gated by static `ADMIN_SECRET` bearer + suspension enforcement in `get_current_user` + a single-file AMI-styled admin web UI at `/admin` (vanilla HTML/CSS/JS, no build step, usable from iPhone Safari). **Coach Your Agent → Brief Your Agent rename** complete end-to-end: backend (`/v1/brief/*` canonical, `/v1/coach/*` kept as deprecated alias logging `deprecated_coach_route_used`), Flutter (renamed `BriefScreen`/`BriefNotifier`/etc. + new `AgentActionSheet` widget on Floor with `[1-ON-1]` and `[BRIEF]` buttons fixing the discoverability gap), 33 l10n keys renamed across EN/AR/MS, 13+ content files swept (lessons, ai_meta Q&A, daily challenges, glossary definition), 27+ docs files swept, CLAUDE.md updated. Audit followup added 5 prompt-overlay regression tests and surfaced a real bug: **`room_runner.py` was hard-coding `user_id=None` when calling `build_room_messages`**, so user_overlays never reached the LLM during Convene the Room (1-on-1 was wired correctly). Fixed at lines 963 + 1040 with a source-level regression test that will catch any future revert. Also wired `ADMIN_SECRET` + the 5 `SMTP_*` env vars into `docker-compose.yml` (both were never being passed to the container — silent gaps). **348 backend tests passing** (was 318 — +5 prompt overlay regression + +25 admin tests + new test_brief_engine.py renamed from test_coach_engine.py).

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **226 commits**, no remote yet |
| Latest work commit | `9793c25` — chore(brief): audit sweep — close all user-facing Coach→Brief residuals (AT:R27). The actual HEAD is the handover-wrap commit immediately after; the count includes it. |
| Alpha tags | `alpha-2026-05-13-{1..8}` + `alpha-2026-05-14-{1..9}` + `alpha-2026-05-15-{1..4}` + `alpha-2026-05-16-1` + `alpha-2026-05-17-{1..5}` + `alpha-2026-05-19-{2,3}` + `alpha-2026-05-20-{1..8}` (latest `alpha-2026-05-20-8` — Brief rename audit sweep + LLM prompt header BRIEFING + journal filter chip rename) |
| Backend tests | **348 passed, 0 failed** (was 318; +30 net this session: +25 admin endpoints in `test_admin.py` covering all 9 routes + suspension enforcement, +5 prompt-overlay regression in `test_agent_prompts.py` covering build_agent_prompt overlay layering and the room_runner user_id=ctx.user_id source-level assertion. `test_coach_engine.py` was renamed to `test_brief_engine.py` with class renames inline.) |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **312 i18n keys** (EN canonical; 33 `coach*` keys renamed to `brief*` this session — same count, no new keys) |

```
$ git log --oneline | head -10
9793c25 chore(brief): audit sweep — close all user-facing Coach→Brief residuals (AT:R27)
cf56afe fix(brief): thread user_id through Convene the Room — overlays now apply (AT:R27)
2646971 feat(brief): rename Coach Your Agent → Brief Your Agent + Floor discoverability (AT:R27)
1baeed6 feat(admin): single-page admin UI at /admin (AT:R27)
28eb261 fix(compose): wire SMTP_* into api-alpha container env (AT:R27)
fdeb14b fix(compose): wire ADMIN_SECRET into api-alpha container env (AT:R27)
fbe1570 fix(migration): rebase admin_backoffice onto b1c4e8d70007 head
faf4958 feat(admin): back-office foundation — plan/trial/credit/suspend API (AT:R27)
453fbe4 docs(handover): elevate SMTP DNS blocker + drop worktree-pattern footnote
febc06b handover: wrap AT:R26 — bug:a84361f6 + B4 + Phase 4 + SMTP wired
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
| Mac-side tests | `backend/.venv/bin/pytest backend/tests/unit/ -q` — **348 passed** (was 318; AT:R27 added `test_admin.py` for the 9 admin endpoints + 5 prompt-overlay regression tests in `test_agent_prompts.py`; `test_coach_engine.py` renamed to `test_brief_engine.py` with class renames). Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
| Env knobs (alpha) | `AMI_ENV=staging` + `SECRET_KEY=<64-hex>` + `ADMIN_SECRET=<64-hex>` (AT:R27, admin back-office bearer) + `SMTP_{HOST,PORT,USER,PASSWORD,FROM}` (5 vars, AT:R26). Canonical at `infra/alpha.env` on Mac, gitignored; shipped via `scp` in `/promote-to-alpha` step 4. Without `SECRET_KEY` the backend refuses to start when env != local. **`SMTP_HOST` is currently empty by design** — the `email_service` no-op path fires so no connect-attempts hit the ISP-blocked outbound to `mail.agenticmarketintel.ai`. Restore by uncommenting the line in `infra/alpha.env` once a working SMTP route (Gmail / Resend) is configured. |
| Auth | Phase 1.5 + Phase 4 enforced: route-level `get_current_user` on `/v1/mandate`, `/v1/journal`, `/v1/watchlist`, `/v1/brief` (legacy `/v1/coach`), `/v1/agents/one_on_one`, `/v1/room`, plus per-route on user-specific `sim` + `lessons`. Bearer format `scaffold:<user_id_hex>:<hmac_sig>` (HMAC-SHA256 with `SECRET_KEY`). Legacy unsigned `scaffold:<hex>` accepted only in env=local. `/v1/auth/anon` mints fresh unless the caller's Bearer matches the supplied `device_user_id`. Magic-link routes require auth and bind to `current_user.id`. `/v1/auth/apple` returns 503 outside env=local (Phase 3 verification not yet shipped). `DELETE /v1/auth/session` (Phase 4) requires auth and returns `{"signed_out": true}` — stateless no-op now; hooks future token blocklist. `http_audit` middleware scrubs request + response bodies for all `/v1/auth/*` routes (AT:R26 B4 close). **AT:R27 suspension enforcement:** `get_current_user` now checks `users.suspended_at`; if set, raises `403 {"detail": "account_suspended"}` — applies to every authenticated route automatically. **Admin auth:** `/v1/admin/*` uses `Authorization: Bearer <ADMIN_SECRET>` via the `get_admin` dependency (constant-time compare); returns 403 on any mismatch and 503 when `ADMIN_SECRET` is unset. |
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

Tables: `users` (with `suspended_at`, `trial_started_at`, `trial_expires_at` — AT:R27), `auth_challenges`, `mandates`, `agent_activations`, `lessons_progress`, `journal_entries` (with `deleted_at`), `overlay_edit_counts`, `user_overlays`, `room_runs`, `sim_holdings`, `sim_portfolios`, `sim_trades`, `sim_watchlists`, `bug_reports` (with `assigned_branch`, `attachment_path`, `attachment_mime`), `llm_audit`, `http_audit`, `one_on_one_messages`, `subscription_events` (AT:R27), `alembic_version`. Latest migration on melehost: `a9d1c7e80006` (`admin_backoffice` — adds the 3 new user columns + `subscription_events` table). `init_schema()` self-stamps Alembic on a fresh container, so `alembic upgrade head` is a no-op on first boot. Bug-report attachments live in the named docker volume `ami-trade-local_bug_attachments` mounted at `/data/bug_attachments` in the api-alpha container.

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
| pubspec version | **`0.1.0+17`** (repo) — AT:R26 closes. **AT:R27 changes are in-tree but not yet built** — next TestFlight upload will be `+18` carrying Brief rename + new `AgentActionSheet` on Floor. |
| TESTING IPHONE 13 install | `+17` was the last TestFlight upload (AT:R26); `+18` not built yet. Use `scripts/install_iphone.sh` to install a dev build of the current tree if you want to smoke-test AT:R27 Flutter changes before TestFlight. |
| TestFlight | `0.1.0+17` uploaded 2026-05-19. **AT:R27 has not pushed a new build** — backend-only deployment via 8 alpha promotes; mobile changes (Brief rename + AgentActionSheet) sit at HEAD waiting for next `scripts/build_testflight.sh`. |
| Build commands | `scripts/install_iphone.sh` (dev sideload), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **AT:R27 Floor change:** tapping an unlocked agent no longer opens 1-on-1 directly — it now opens an `AgentActionSheet` bottom sheet with two big buttons: `[1-ON-1]` (talk to the agent) and `[BRIEF]` (modify how it thinks). Concierge skips the sheet — has no Brief surface, so 1-on-1 is the only path. The tune icon in the 1-on-1 header stays as a secondary route to Brief. **AT:R27 rename:** `CoachScreen` → `BriefScreen`, `BriefHistoryScreen`, `BriefNotifier`/`briefNotifierProvider`, `models/brief.dart`, `api_client.startBrief/streamBriefMessage/...`. The 33 l10n keys flipped from `coach*` to `brief*` (including the journal chips: `journalFilterCoach` → `journalFilterBrief`, value `COACH` → `BRIEF`; same for `journalEntryTypeCoach`). Journal filter chips now read: `ALL · ROOM · TRADE · 1-ON-1 · BRIEF · LESSONS · UNLOCKS`. **First-time walkthrough (AT:R23):** per-section coach-mark tours (still using `tutorial_coach_mark` package — unrelated to Brief feature) fire on first visit. **AT:R25 auth gate** + **AT:R26 sign-out (Phase 4)** + **AT:R26 Apple-glitch fix** still in place. Journal soft-delete + Trash + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green pill once a sim_trade exists. Trade ticket sheet has live quote chip + auto-suggested TP/SL. Ticker tape below bottom nav. Settings → APPEARANCE is dark-only. Bug-report sheet (long-press app-version chip) supports photo attachments.

---

## What just landed (this session — AT:R27)

Big session, 8 commits, 8 alpha tags (`alpha-2026-05-20-{1..8}`). Three discrete tracks: admin back-office foundation, Coach → Brief rename + discoverability fix, and an audit-driven `user_overlay` runtime fix. Backend tests went 343 → 348 (added admin endpoint coverage + prompt-overlay regression). No TestFlight build pushed — Flutter changes sit at HEAD for the next promote.

### Track A — Admin back-office foundation (carry-over from AT:R26 design grill)

Saiful grilled the design upfront (single-operator MVP with upgrade path to multi-user; CLI for Alpha, Flutter web admin app for Beta; static `ADMIN_SECRET` for Alpha → `admin_users` + JWT in Beta; access level = plan tier only + suspension as sole per-user override; `subscription_events` table for fee tracking + audit; admin tools only, credit-consumption deferred until access-level design done).

`faf4958` shipped:
- **Migration** `a9d1c7e80006_admin_backoffice.py` — adds `users.suspended_at`, `users.trial_started_at`, `users.trial_expires_at`, and creates `subscription_events` table. Initial commit had `down_revision="f7d9b2e60005"` which branched off the wrong head; fixed in `fbe1570` to point at `b1c4e8d70007`.
- **Schemas** `backend/app/schemas/admin.py` — request/response Pydantic models (`AdminPlanChangeRequest`, `AdminTrialGrantRequest`, `AdminTrialUpdateRequest`, `AdminCreditsRequest`, `AdminNoteRequest`, `AdminUserSummary`, `AdminUserDetail`, `SubscriptionEventOut`, `AdminEventsResponse`).
- **Router** `backend/app/api/admin.py` — 9 endpoints, `get_admin` dependency does constant-time HMAC compare on the bearer, 403 on mismatch, 503 when `ADMIN_SECRET` unset. Every write goes through `_record_event` helper → writes to `subscription_events`. Suspend/reinstate enforce 409 on no-op (already-suspended or not-suspended).
- **Suspension enforcement** added to `get_current_user` in `backend/app/api/auth.py`: if `user.suspended_at is not None`, raises 403 with `detail="account_suspended"`. Every authenticated route inherits the block.
- **Config** `ADMIN_SECRET: str = ""` in `Settings`; `infra/alpha.env.example` + `infra/alpha.env` populated.
- **Tests** `test_admin.py` covers all 9 endpoints + the suspension dependency (negative tests for missing/wrong bearer + 403/404/409 paths).

Two follow-up `fix(compose)` commits closed the runtime gap: `docker-compose.yml` was enumerating env vars explicitly and **had never wired `ADMIN_SECRET` or any of the `SMTP_*` vars** through to the api-alpha container. First promote (`alpha-2026-05-20-1`) deployed code but admin endpoints returned 503 because the container saw `ADMIN_SECRET=""`. `fdeb14b` added `ADMIN_SECRET: ${ADMIN_SECRET:-}` to compose; `28eb261` added the 5 SMTP vars at the same time. `SMTP_HOST` itself was blanked out in `infra/alpha.env` (original value preserved as a commented line) so the email_service no-op path keeps firing until a working SMTP route exists — no timeout traffic, no `magic_link_email_failed` log spam.

`1baeed6` added the admin web UI: a single 660-line HTML file at `backend/app/static/admin.html`, served at `/admin` via `HTMLResponse` from `app.main`. AMI palette mirrored from `mobile/lib/theme/ami_theme.dart`. Vanilla JS with `fetch` + localStorage for the bearer. Mobile-first responsive, PWA meta tags. Saiful can `Add to Home Screen` on iPhone Safari for a chromeless app-style entry.

### Track B — Coach Your Agent → Brief Your Agent rename + discoverability fix

`2646971` — the rename commit (64 files, +1908/−1423).

**Why:** "Coach" carried the wrong power dynamic (mentor/therapist), conflicted with the AI Coach Q&A library + the `tutorial_coach_mark` package, and obscured the actual mechanic. "Brief" is CEO-native — a CEO briefs their analysts.

**Discoverability bug surfaced same session:** Brief was buried behind a single unlabelled tune icon in the 1-on-1 header. Even Saiful couldn't find it. Fix: tapping an agent on the Floor now opens a new `AgentActionSheet` widget (`mobile/lib/widgets/agent_action_sheet.dart`) with two big buttons — `[1-ON-1]` (chat icon, hex-blue) and `[BRIEF]` (tune icon, hex-amber). Concierge skips the sheet (no Brief surface). The 1-on-1 header tune icon stays as a secondary route.

**Backend:** `schemas/brief.py`, `services/brief_engine.py`, `api/brief.py` are the new canonical modules. `/v1/brief/*` is the new path. The old `coach.py` files are now back-compat shims: schemas re-export `BriefX as CoachX`, services re-export `BriefEngine as CoachEngine + get_brief_engine as get_coach_engine + hydrate_brief_mandate as hydrate_coach_mandate`, and `api/coach.py` is a 150-line shim that re-mounts the brief routes under `/v1/coach` with a `_log_deprecation` dependency that logs `deprecated_coach_route_used` warning on every hit. TestFlight `+17` keeps working without rebuild.

**Flutter:** `git mv` + class renames + l10n key renames + Dart consumer updates. 33 `coach*` l10n keys flipped to `brief*` across EN/AR/MS via Python script (then `flutter gen-l10n` regenerated `AppLocalizations`). Journal filter chip "COACH" → "BRIEF" via `journalFilterCoach` → `journalFilterBrief` key rename + value update.

**Content + docs:** mechanical Python-script sweep across `content/lessons/*.mdx`, `content/ai_coach/*.json`, `content/daily_challenges/*.json`, `content/glossary/terms.en.json`, and `docs/**/*.md`. CLAUDE.md decision-row updated.

**Preserved as concept vocabulary:** the word "uncoachable" + "cannot be coached around" stays as the Portfolio Manager safety-floor's resistance label (lesson 273 is built on this term — established product vocabulary). `EntryType.AGENT_COACH = "agent_coach"` enum value stays as the DB-stored value (no migration needed for existing journal rows). Audit log identifiers `coach_chat` (audit flow tag) and `coach_overlay_saved` (log key) stay for log-query continuity. The glossary term ID `ami_coach_your_agent` stays (17 lesson files reference it via `<Term id="…" />`) — only the display name was updated to "Brief Your Agent". Lesson file `278_coaching_changes_style_not_floor.en.mdx` keeps its filename + frontmatter `id` field (cross-reference safety); body content was updated.

### Track C — `user_overlay` runtime audit + fix

Saiful asked for an explicit audit: does `user_overlay` actually flow into 1-on-1 + Convene the Room runtime, or does the Brief UI persist overlays that the LLM never sees?

**Finding:**
- **1-on-1: WIRED CORRECTLY.** `agent_runner.py:128` calls `build_agent_prompt(agent_id, mandate, user_id=session.user_id)`. In `agent_prompts.py:48-71`, when `user_id is not None`, `_append_user_overlay` calls `OverlayStore.get_active(user_id, agent_id)` and concatenates the overlay between mandate and safety_floor. Briefings actually shaped 1-on-1 conversations.
- **Convene the Room: BROKEN.** `room_runner.py:963` (regular agents) AND `1037` (PM narration) both hard-coded `user_id=None` when calling `build_room_messages`. `ctx.user_id` was right there on the same line (used for `audit_user_id`) but not threaded into the prompt composer. Result: **every agent in every Room run received `base + mandate + safety_floor`, no overlay.** Brief did nothing during Convene.

`cf56afe` fixed both call sites: `user_id=None` → `user_id=ctx.user_id`. Added 5 regression tests in `test_agent_prompts.py`:
- `test_build_agent_prompt_includes_user_overlay_when_user_id_provided` — saved overlay appears in composed prompt with `USER_OVERLAY_HEADER`.
- `test_build_agent_prompt_omits_overlay_when_user_id_is_none` — anonymous path stays clean.
- `test_build_agent_prompt_omits_overlay_when_user_has_no_overlay` — fresh users get base + mandate only.
- `test_pm_safety_floor_appended_after_user_overlay` — SAFETY FLOOR block stays last for PM.
- `test_room_runner_threads_user_id_through_to_overlay` — **source-level regression**: parses `room_runner.py`, asserts every `build_room_messages(...)` call site passes `user_id=ctx.user_id` (and not `user_id=None`). Verified to fail by `git stash` of the fix.

### Track D — Audit sweep follow-up (`9793c25`)

Saiful asked for a thorough double-check on the rename. The first-pass sub had targeted phrase "Coach Your Agent" + key-prefix `coach[A-Z]`; verb-form usages, suffix-position keys, and mid-string values slipped through. Audit caught 8 classes of gap (LLM-prompt header text, journal chip l10n keys, embedded "coaching" in values, MS translations, content verb forms, glossary definition, docs verb forms, internal docstrings). All fixed in a single commit (59 files, +429/−152). Final classified residual: 174 hits across known-keep categories (concept terms, internal identifiers, backwards-compat shim, third-party package, AI Coach Q&A library).

### Operational footnotes worth surfacing

- **SMTP — still blocked.** DNS resolved overnight (`mail.agenticmarketintel.ai` → `69.57.162.213`) but melehost's ISP blocks outbound to that IP on ports 465 AND 587 (TCP SYN succeeds, SSL/SMTP times out). `smtp.gmail.com` and `mail.privateemail.com` are both reachable from melehost. Carry-over: pick Gmail SMTP (Gmail App Password) or switch to Resend HTTP API (`resend>=2.4` already in pyproject.toml). Until resolved, magic-link sign-in delivers no emails. Compose plumbing for SMTP_* is now correct (was a silent gap pre-AT:R27); only `SMTP_HOST` value blocks the no-op path from triggering.
- **TestFlight `+18` not built yet.** All AT:R27 Flutter work (Brief rename, AgentActionSheet, journal chip relabel) is at HEAD but not yet uploaded. Next session should run `scripts/build_testflight.sh` if Saiful wants to test the new UI on TF.
- **17 anonymous users in the DB** (no claimed accounts yet — magic-link blocked by SMTP). Most recent: `b3bc18aa-3dca-48d7-beb4-803220b40b69` (2026-05-20 16:20). Safe to use for admin-endpoint smoke tests.
- **`AGENT_COACH` enum value preserved.** Journal entries created via Brief Accept still write `entry_type='agent_coach'` to keep existing rows valid. New row titles read "Briefed Bear Researcher → v3" instead of "Coached …" — old rows keep their "Coached …" titles as historical strings.
- **`alpha-2026-05-20-1` was a partial deploy** — schema didn't apply because the migration's `down_revision` was wrong. Caught + recovered mid-promote (no downtime, no rollback). `-2` shipped the migration fix; `-3` shipped the compose fix; `-4` blanked SMTP_HOST; `-5` added the admin UI; `-6` shipped the Brief rename; `-7` fixed the Room overlay bug; `-8` shipped the audit sweep. Don't be surprised by the count.

### Carry-overs for AT:R28

Counts audited against tree state at end of AT:R27.

1. **🚧 SMTP — pick a working route.** Gmail SMTP (5 min — Saiful provides App Password) or Resend HTTP API (~30 min — sign up + swap `email_service.send_magic_link` from smtplib to `resend` SDK). Without this, magic-link sign-in is broken for external testers = **External Beta blocker**. Compose plumbing + DNS + creds are all in place; only the route choice is left.
2. **TestFlight `+18` build** — `scripts/build_testflight.sh` to ship the Brief rename + AgentActionSheet + journal chip update. Auto-bumps build number from `+17`.
3. **`6fd4144d` bug-report close button** — `pending_review`. Verify on `+17` or wait for `+18` → flip to resolved.
4. **`a84361f6` Apple-sign-in 503 glitch** — `pending_review`. Same pattern.
5. **`11fde6f6` floor hex agent style** — open, deferred from AT:R24/R25/R26/R27. The AgentActionSheet wiring may have indirectly addressed this; verify on next build.
6. **`eeeb866f` room run survives container restart** — open, deferred pre-Beta.
7. **Apple sign-in Phase 3** — PyJWT + Apple JWKS verification (~1 day). No movement.
8. **Google sign-in Phase 3** — explicit defer until Android v1.0.
9. **B-tier adversarial-audit findings** — rate limiting on `/auth/anon` + LLM-heavy routes; magic-link attempt counter + per-IP throttle; feedback upload size enforced at proxy + streaming read. Deferred pre-External-Beta. (B4 token-scrubbing closed in AT:R26.)
10. **L-1 residual** (from AT:R25 audit) — `OneOnOneStartRequest.user_id: UUID | None` lets a null body bypass `_own_body`. Tighten if 1-on-1 abuse becomes a real signal.
11. **External TestFlight launch** — Beta App Description from Saiful + ~24h Apple review on first external build. Still no External Beta artefact.
12. **Animation production** — 15 `<Animation>` MDX tags in `content/lessons/` still render `AmiHexPlaceholder`. Lottie vs CustomPainter decision still open.
13. **A29 light-mode refactor** — v1.0 work.
14. **Two sibling worktrees with unmerged docs** — `claude/blissful-darwin-419097` (bug-pipeline spec + D-057) and `claude/exciting-shtern-aad051` (lessons-landing hex-cluster redesign). Still pending Saiful decision.
15. **Brief safety-floor terminology audit (deferred)** — the word "uncoachable" / "cannot be coached around" stays as the conceptual term for the PM's resistance to overlay-based modification. Renaming this concept (e.g. to "un-briefable") needs a broader product-design conversation and would touch lesson 273 + the entire safety-floor doc. Defer until product strategy explicitly decides.
16. **Credit consumption** — `credits_consumed` event type exists in `subscription_events` but no app code emits it yet. Wire `credit_balance -= 1` + event write in `room.py` and `one_on_one.py` once Saiful finishes the access-level design (per-tier credit allocation, what Floor Pass users get, etc.).

### Watch items (not tasks)

- **Brief overlay actually shaping LLM responses now.** Once a Brief is saved, every Convene the Room call applies it (previously did nothing). Tone changes will be more visible. Worth watching if any agent's briefed-up behavior crosses into territory you didn't expect.
- **`deprecated_coach_route_used` warning frequency** — once TF `+18` ships with `/v1/brief/*` paths, the `/v1/coach/*` alias should see traffic drop to zero. Grep api-alpha logs after the build is deployed; once clean for 2 sessions, the shim can be removed.
- **NVFP4 quantisation watch item still applies** — `ami-llm` occasionally emits space-split tokens. Not blocking.

---

## How to start the next session

```
/start-fresh
```

The slash command reads HANDOVER.md + project plan, runs the Mac-side sanity-check curls, queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R28** (this is handover #27).

If Alpha is down at session start, `/start-fresh` will surface that and tell you the melehost debug commands.

If the first message is a specific task ("fix this", "add that"), skip `/start-fresh` and just do the task — the slash command is for the "let's keep going" opening.

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
- **Apple Developer team.** Done (`S7RBWM4879`). Sign in with Apple capability enabled at the bundle ID (Saiful did this in AT:R26). Backend Phase 3 verification still pending (see carry-over #7).
- **App Store + APNs** — external. Market data is real Yahoo when `USE_REAL_MARKET_DATA=true`.

Nothing is blocking the next chunk.
