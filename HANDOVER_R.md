# Handover — AMI Trade build session

**Last updated:** 2026-05-20 (end of AT:R28 — short, single-task session). **TestFlight `0.1.0+18` uploaded** (`✓ uploaded 0.1.0+18`, delivery UUID `5b62b39f-b39f-4901-a1e9-4eb5b5fe00ca`). Build carries the full AT:R27 Flutter payload that had been sitting at HEAD: Brief rename (`BriefScreen`/etc. + 33 l10n keys), new `AgentActionSheet` widget on Floor with `[1-ON-1]` + `[BRIEF]` buttons, journal filter chip "COACH" → "BRIEF". Backend unchanged this session — no migrations, no test changes (still 348 passing), no alpha promote. 2 commits: `f22bf45` (auto-bump `+17 → +18`) + `53532a7` (chore: sync upstream skill definitions for `start-fresh-generic` / `handover-generic` / `session-setup` — multi-track variant). Build is processing in App Store Connect (~15–30 min after 15:02 UTC); internal testers see it instantly once processed.

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **229 commits**, no remote yet |
| Latest work commit | `f22bf45` — chore(mobile): bump build 0.1.0+17 → 0.1.0+18 for TestFlight (AT:R28). Then `53532a7` skills sync, then this handover-wrap commit. Total commit count includes the wrap. |
| Alpha tags | `alpha-2026-05-13-{1..8}` + `alpha-2026-05-14-{1..9}` + `alpha-2026-05-15-{1..4}` + `alpha-2026-05-16-1` + `alpha-2026-05-17-{1..5}` + `alpha-2026-05-19-{2,3}` + `alpha-2026-05-20-{1..8}` (latest `alpha-2026-05-20-8` — Brief rename audit sweep + LLM prompt header BRIEFING + journal filter chip rename). **No alpha promote this session** — AT:R28 was a TestFlight-only build cycle, backend on melehost still at the AT:R27 state. |
| Backend tests | **348 passed, 0 failed** (unchanged this session — no backend code touched in AT:R28; counts carry over from AT:R27 admin + prompt-overlay additions). |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **312 i18n keys** (unchanged this session). |

```
$ git log --oneline | head -10
53532a7 chore(skills): sync generic session protocols from upstream — multi-track variant
f22bf45 chore(mobile): bump build 0.1.0+17 → 0.1.0+18 for TestFlight
1ef8724 docs(handover): rotate AT:R26 to history + write AT:R27 wrap
9793c25 chore(brief): audit sweep — close all user-facing Coach→Brief residuals (AT:R27)
cf56afe fix(brief): thread user_id through Convene the Room — overlays now apply (AT:R27)
2646971 feat(brief): rename Coach Your Agent → Brief Your Agent + Floor discoverability (AT:R27)
1baeed6 feat(admin): single-page admin UI at /admin (AT:R27)
28eb261 fix(compose): wire SMTP_* into api-alpha container env (AT:R27)
fdeb14b fix(compose): wire ADMIN_SECRET into api-alpha container env (AT:R27)
fbe1570 fix(migration): rebase admin_backoffice onto b1c4e8d70007 head
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
| pubspec version | **`0.1.0+18`** (repo) — AT:R28 bumped + uploaded. Carries all AT:R27 Flutter work (Brief rename + `AgentActionSheet` on Floor + journal chip relabel). |
| TESTING IPHONE 13 install | `+18` uploaded to TestFlight 2026-05-20 15:02 UTC; processing in App Store Connect (~15–30 min). Once processed, install via TestFlight on device. For pre-TF dev smoke, use `scripts/install_iphone.sh`. |
| TestFlight | `0.1.0+18` uploaded 2026-05-20 (delivery UUID `5b62b39f-b39f-4901-a1e9-4eb5b5fe00ca`). Internal testers see it once processing finishes; External requires Beta App Review (still no external testers added — see carry-over #11). |
| Build commands | `scripts/install_iphone.sh` (dev sideload), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **AT:R27 Floor change:** tapping an unlocked agent no longer opens 1-on-1 directly — it now opens an `AgentActionSheet` bottom sheet with two big buttons: `[1-ON-1]` (talk to the agent) and `[BRIEF]` (modify how it thinks). Concierge skips the sheet — has no Brief surface, so 1-on-1 is the only path. The tune icon in the 1-on-1 header stays as a secondary route to Brief. **AT:R27 rename:** `CoachScreen` → `BriefScreen`, `BriefHistoryScreen`, `BriefNotifier`/`briefNotifierProvider`, `models/brief.dart`, `api_client.startBrief/streamBriefMessage/...`. The 33 l10n keys flipped from `coach*` to `brief*` (including the journal chips: `journalFilterCoach` → `journalFilterBrief`, value `COACH` → `BRIEF`; same for `journalEntryTypeCoach`). Journal filter chips now read: `ALL · ROOM · TRADE · 1-ON-1 · BRIEF · LESSONS · UNLOCKS`. **First-time walkthrough (AT:R23):** per-section coach-mark tours (still using `tutorial_coach_mark` package — unrelated to Brief feature) fire on first visit. **AT:R25 auth gate** + **AT:R26 sign-out (Phase 4)** + **AT:R26 Apple-glitch fix** still in place. Journal soft-delete + Trash + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green pill once a sim_trade exists. Trade ticket sheet has live quote chip + auto-suggested TP/SL. Ticker tape below bottom nav. Settings → APPEARANCE is dark-only. Bug-report sheet (long-press app-version chip) supports photo attachments.

---

## What just landed (this session — AT:R28)

Short, single-task session: ship the TestFlight `+18` build that had been the AT:R27 → AT:R28 carry-over. 2 commits, 0 alpha promotes, 0 test changes.

### Track A — TestFlight `0.1.0+18` upload

`scripts/build_testflight.sh` ran clean end-to-end:

- **Auto-bump** (`f22bf45`): `mobile/pubspec.yaml` `version: 0.1.0+17` → `0.1.0+18`. Script auto-commits the bump per its own protocol.
- **Build**: `flutter build ipa --release --export-method=app-store --dart-define=ALLOW_BACKEND_SWITCH=true --dart-define=AMI_API_URL_ALPHA=https://api-alpha.agenticmarketintel.ai`. Archived in 45.4s, IPA built in 6.0s, final size 25 MB (`build/ios/ipa/ami_trade.ipa`).
- **Upload**: `xcrun altool --upload-app --type ios` → `UPLOAD SUCCEEDED with no errors`. Delivery UUID `5b62b39f-b39f-4901-a1e9-4eb5b5fe00ca`, 25,994,051 bytes in 13.1s (2.0 MB/s). Confirmed at 15:02:05 UTC.

App Store Connect validation noted the usual two warnings (placeholder app icon + launch image) — pre-existing, deferred to brand-asset pass.

Build `+18` carries the **full AT:R27 Flutter payload** that had been sitting at HEAD with no TestFlight pickup:
- `CoachScreen` → `BriefScreen` + `BriefHistoryScreen` + `BriefNotifier`/`briefNotifierProvider` + `models/brief.dart` + all `api_client` method renames
- 33 `coach*` l10n keys flipped to `brief*` across EN / AR / MS
- New `AgentActionSheet` widget on Floor — tapping an unlocked agent now shows `[1-ON-1]` + `[BRIEF]` buttons (Concierge skips the sheet)
- Journal filter chip "COACH" → "BRIEF" (value + l10n key)

### Track B — Upstream skill protocol sync (`53532a7`)

Three project-local slash-command files received upstream updates from the harness during the session:
- `.claude/commands/handover-generic.md`
- `.claude/commands/session-setup.md`
- `.claude/commands/start-fresh-generic.md`

The new variant adds **multi-track support** — each generic skill now takes a track letter (e.g. `/start-fresh-generic R`, `/handover-generic M`) and reads a per-track block from `.claude/session-config.yml`. This project doesn't use the generic skills (it has bespoke `/start-fresh` and `/handover`), but the synced text is what the upstream now ships, so committing keeps the diff at zero.

Committed as `chore(skills): sync generic session protocols from upstream — multi-track variant` to keep the tree clean for handover. No behavioural impact on this project's actual flow.

### What didn't change

- **No backend code touched.** Test count still 348 passing.
- **No alpha promote.** Latest alpha tag stays `alpha-2026-05-20-8`.
- **No content corpus changes.** Lessons / glossary / Q&A / daily challenges / i18n counts unchanged.
- **No DB migrations.** Latest migration on melehost still `a9d1c7e80006` (admin_backoffice).
- **No bug-list movement.** 2 open + 2 pending_review at session start; same at session end. The `pending_review` rows (`6fd4144d`, `a84361f6`) can be verified on `+18` once Apple finishes processing — flag for AT:R29 cleanup.

### Operational footnotes worth surfacing

- **Build is processing in App Store Connect.** First-pass processing typically 15–30 min after upload. Internal testers (the `apptest` group) see it instantly once processed; External Beta still needs the Beta App Review pass — see carry-over #11.
- **`flutter pub get` flagged 59 packages with newer-incompatible versions.** Same as last build; no action needed.
- **SMTP unchanged.** Still no outbound mail route. `SMTP_HOST` blanked in `infra/alpha.env`; `email_service` no-op path firing. Carry-over #1 still the External Beta blocker.
- **iPhone 13 TestFlight install** — once Apple completes processing, install `+18` from TestFlight on device to smoke-test the AgentActionSheet + Brief rename in real conditions. The two `pending_review` bug fixes ride on this build.

### Carry-overs for AT:R29

Counts audited against tree state at end of AT:R28.

1. **🚧 SMTP — pick a working route.** Gmail SMTP (5 min — Saiful provides App Password) or Resend HTTP API (~30 min — sign up + swap `email_service.send_magic_link` from smtplib to `resend` SDK). Without this, magic-link sign-in is broken for external testers = **External Beta blocker**. Compose plumbing + DNS + creds are all in place; only the route choice is left.
2. **Verify `+18` on iPhone, flip pending_review bugs to resolved.** Once Apple finishes processing (~15–30 min after 15:02 UTC), install `+18` via TestFlight and confirm: (a) `6fd4144d` — bug-report screen has a working close-without-submit path, (b) `a84361f6` — Apple sign-in shows the friendly "Coming in v1.0" copy + caption instead of a confusing 503. If both verify, run `UPDATE bug_reports SET status='resolved' WHERE id::text LIKE '6fd4144d%' OR id::text LIKE 'a84361f6%'` on melehost.
3. **`11fde6f6` floor hex agent style** — open, deferred from AT:R24/R25/R26/R27. The AgentActionSheet wiring on `+18` may have indirectly addressed this; verify on device.
4. **`eeeb866f` room run survives container restart** — open, deferred pre-Beta.
5. **Apple sign-in Phase 3** — PyJWT + Apple JWKS verification (~1 day). No movement.
6. **Google sign-in Phase 3** — explicit defer until Android v1.0.
7. **B-tier adversarial-audit findings** — rate limiting on `/auth/anon` + LLM-heavy routes; magic-link attempt counter + per-IP throttle; feedback upload size enforced at proxy + streaming read. Deferred pre-External-Beta. (B4 token-scrubbing closed in AT:R26.)
8. **L-1 residual** (from AT:R25 audit) — `OneOnOneStartRequest.user_id: UUID | None` lets a null body bypass `_own_body`. Tighten if 1-on-1 abuse becomes a real signal.
9. **External TestFlight launch** — Beta App Description from Saiful + ~24h Apple review on first external build. `+18` is uploaded but still Internal-only.
10. **Animation production** — 15 `<Animation>` MDX tags in `content/lessons/` still render `AmiHexPlaceholder`. Lottie vs CustomPainter decision still open.
11. **A29 light-mode refactor** — v1.0 work.
12. **Two sibling worktrees with unmerged docs** — `claude/blissful-darwin-419097` (bug-pipeline spec + D-057) and `claude/exciting-shtern-aad051` (lessons-landing hex-cluster redesign). Still pending Saiful decision.
13. **Brief safety-floor terminology audit (deferred)** — the word "uncoachable" / "cannot be coached around" stays as the conceptual term for the PM's resistance to overlay-based modification. Renaming this concept (e.g. to "un-briefable") needs a broader product-design conversation and would touch lesson 273 + the entire safety-floor doc. Defer until product strategy explicitly decides.
14. **Credit consumption** — `credits_consumed` event type exists in `subscription_events` but no app code emits it yet. Wire `credit_balance -= 1` + event write in `room.py` and `one_on_one.py` once Saiful finishes the access-level design (per-tier credit allocation, what Floor Pass users get, etc.).

### Watch items (not tasks)

- **Brief overlay actually shaping LLM responses now.** Once a Brief is saved on `+18`, every Convene the Room call applies it (previously did nothing on `+17`). Tone changes will be more visible. Worth watching if any agent's briefed-up behavior crosses into territory you didn't expect.
- **`deprecated_coach_route_used` warning frequency** — `+18` ships with `/v1/brief/*` paths, so `/v1/coach/*` alias traffic should drop to zero from this device. Grep api-alpha logs once `+18` is installed on iPhone; once clean for 2 sessions, the shim can be removed.
- **NVFP4 quantisation watch item still applies** — `ami-llm` occasionally emits space-split tokens. Not blocking.

---

## How to start the next session

```
/start-fresh
```

The slash command reads HANDOVER.md + project plan, runs the Mac-side sanity-check curls, queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R29** (this is handover #28).

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
