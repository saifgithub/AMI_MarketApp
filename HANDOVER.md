# Handover — AMI Trade build session

**Last updated:** 2026-05-15 (end of AT:R19 — journal swipe-to-delete + search + soft-delete + Trash view; SSE middleware fixed; room reconnect-on-disconnect; /fix-bugs workflow + TestFlight scripts; **131 commits, 220 tests**, TestFlight `0.1.0+4` uploaded via CLI, TESTING IPHONE 13 on `0.1.0+4` (pre-Trash); a `+5` install + TestFlight push is the first carry-over)

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **131 commits**, no remote yet |
| Latest commit | `f688463` — handover: wrap AT:R19 |
| Alpha tags | `alpha-2026-05-13-{1..8}` + `alpha-2026-05-14-{1..9}` (latest `alpha-2026-05-14-9`) |
| Backend tests | **220 passed, 0 failed** |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, 262 i18n keys (EN canonical; AR + MS auto-translated by Gemma 4) |

```
$ git log --oneline | head -5
f688463 handover: wrap AT:R19 — 131 commits, 220 tests, alpha-2026-05-14-9
aca28ee chore(start-fresh): pull bug list at session start, ask bugs-vs-carry-over
b94adee feat(website-api): wire api-website service in compose + CORS rename
5ed72c0 feat(journal): Trash view — 30-day window of soft-deleted entries
99e6e0d feat(workflow): /fix-bugs slash command + bug_reports.assigned_branch
```

### Backend (lives on melehost — never the Mac)

| | |
|---|---|
| Where | `melehost` (Ubuntu Linux, LAN `192.168.20.9`) — Docker Compose stack at `~/ami_trade/` |
| Container | `ami_api_alpha` (built from `backend/Dockerfile`) — service name `api-alpha` in compose |
| Public hostname | `https://api-alpha.agenticmarketintel.ai` (Cloudflare Tunnel) |
| Health from outside the LAN | `curl https://api-alpha.agenticmarketintel.ai/v1/health` |
| Logs | `ssh melehost "docker logs ami_api_alpha --tail 50"` |
| Restart | `ssh melehost "cd ~/ami_trade && docker compose --profile tunnel up -d api-alpha"` |
| Routes | `/v1/health`, `/v1/auth/*`, `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/coach/*`, `/v1/journal/*` (incl. `/trash`, `/{id}/restore`), `/v1/lessons/*`, `/v1/llm/status`, `/v1/mandate/*`, `/v1/room/*`, `/v1/sim/*`, `/v1/watchlist/*`, `/v1/feedback/bug` |
| Mac-side tests | `pytest backend/tests/unit/ -q` — **220 passed**. Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
| Push code to it | [`/promote-to-alpha`](.claude/commands/promote-to-alpha.md) — rsync + recreate + smoke. No GitHub remote yet. |

Co-resident on melehost: **`api-website`** service (port 8001, builds from `./website_api/`, separate `ami_website` DB, CORS for `agenticmarketintel.ai`). The trade backend and marketing-site backend share zero code; waitlist is a website concern now.

### Postgres + persistence

| | |
|---|---|
| Where | `melehost` — container `ami_postgres` in the compose stack |
| DB | `ami_trade` (user `postgres`, pw `postgres`) |
| Connect from melehost | `ssh melehost "docker exec -it ami_postgres psql -U postgres -d ami_trade"` |
| Mac dev DB | **None.** Mac runs zero services. |
| Backend unit tests | Per-test sqlite tempfile (autouse fixture in `backend/tests/conftest.py`) |
| Backups | Nightly `pg_dump` via `infra/backups/ami-trade-pg-backup.timer` (systemd timer on melehost). Restore drill in `infra/backups/README.md`. |

Tables: `users`, `auth_challenges`, `mandates`, `agent_activations`, `lessons_progress`, `journal_entries` (now with `deleted_at`), `overlay_edit_counts`, `user_overlays`, `room_runs`, `sim_holdings`, `sim_portfolios`, `sim_trades`, `sim_watchlists`, `bug_reports` (now with `assigned_branch`), `llm_audit`, `http_audit`, `one_on_one_messages`, `alembic_version`. Latest migration on melehead: `a8e3c1b50006` (`bug_reports.assigned_branch`). `init_schema()` self-stamps Alembic on a fresh container, so `alembic upgrade head` is a no-op on first boot.

### LLM gateway

- **vLLM** at `http://192.168.20.74:8000` serving `gemma-4-31b-it-nvfp4` (Gemma 4 31B, NVFP4 quantized, 262k context). Gateway preference: `vllm > anthropic > mock`.
- Per-(plan, agent) tier routing in `app/services/tier_policy.py::pick_tier`.

### Market data

- `USE_REAL_MARKET_DATA=true` on melehost. Fallback stack: yfinance → 60s cache → `mock_walk` if Yahoo returns empty/error.
- Quote model: `Quote(price, source, change_pct, market_state)` — `source` is the LEAF that served (`yfinance` or `mock_walk`), not the stack name.

### Mobile app

| | |
|---|---|
| Bundle | `ai.agenticmarketintel.amiTrade` |
| pubspec version | **`0.1.0+4`** |
| TESTING IPHONE 13 install | release `0.1.0+4` (PRE-Trash; AT:R19 changes need a `+5` install — `scripts/install_iphone.sh` after waking the device) |
| TestFlight | `0.1.0+4` uploaded 2026-05-14 via CLI (App Manager API key `44VJ5WADL2`). Processing in App Store Connect ~15-30 min then visible in Internal testing. |
| Build commands | `scripts/install_iphone.sh` (dev sideload), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. Journal has soft-delete with UNDO + 30-day Trash view (entered via trash icon in the Journal header) + server-side search. Ticker tape below bottom nav (Yahoo Finance, refreshes when watchlist changes). Settings → APPEARANCE is dark-only (light-mode toggle removed; the v1.0 refactor will reintroduce it).

---

## What just landed (this session — AT:R19)

Heavy session: 29 commits, 6 alpha promotions (`alpha-2026-05-14-4` through `-9`), one TestFlight upload (`0.1.0+4`), and a meaningful uplift to the bug-fix workflow.

### Journal — swipe-to-delete, search, soft-delete + Trash view

The journal got a full data-lifecycle treatment.

- **Soft delete + restore** (`09358d3`, `5ed72c0`). New `journal_entries.deleted_at` column (Alembic `f7d9b2e60005`); `JournalStore.soft_delete()`/`restore()`; `DELETE /v1/journal/{u}/entry/{e}` + `POST .../restore`. All reads filter `deleted_at IS NULL`. Entry is never destroyed.
- **iOS-standard swipe** (`dc16910`): `Dismissible` threshold raised from 0.4 → 0.7 so half-swipes don't auto-fire; `HapticFeedback.mediumImpact` on commit; 4s snackbar with **UNDO** that calls the restore endpoint.
- **Search** (`09358d3`): `GET /v1/journal/{u}?q=` ILIKE on `title + summary`; Flutter search bar with 400 ms debounce + clear (×) button.
- **Trash view** (`5ed72c0`): new screen reached via trash icon in the Journal header; `GET /v1/journal/{u}/trash` returns soft-deleted entries from the **last 30 days only** (`TRASH_VISIBLE_DAYS=30` in `journal_store.py`). Each card has a green RESTORE button. Older soft-deleted rows stay in the DB but never surface in-app. Footer caption: "Older entries are auto-hidden after 30 days."

### SSE middleware bug — chat + room re-fixed

The biggest "wait, it never worked" find of the session.

- **Root cause:** `HTTPAuditMiddleware` (added in AT:R16, `30fdca1`) replaced `request._receive` with a synthetic that always returned `http.request`. Starlette's `_CachedRequest.wrapped_receive` polls receive during the streaming response to detect client disconnect, expecting only `http.disconnect`. It got `http.request` and raised `RuntimeError: Unexpected message received: http.request` AFTER status 200 was already sent — every SSE route (1-on-1, room stream, coach) silently broken since AT:R16.
- **Fix** (`79e1571`): drop the `request._receive` replacement entirely. `await request.body()` already caches in `_body`; `_CachedRequest.wrapped_receive` reads from that cache. The synthetic was actively harmful, not helpful.

### Room run survives sleep / reconnect on wake

- New `started` `RoomEvent` kind, yielded first by `runner.run()`, carries the `run_id` immediately so clients can poll even if disconnected mid-stream.
- On `(CancelledError | GeneratorExit)` in `event_stream`, spawn `asyncio.create_task(_drain_to_completion(run_id))` — runner finishes server-side and persists journal + verdict.
- Flutter `RoomNotifier` captures `run_id` from `started`, on stream error polls `GET /v1/room/{id}` every 3s up to 90s. Amber `_ReconnectingBanner` UI ("Connection lost. The room is still running…") + `RoomState.reconnecting` flag.
- **Caveat (filed as bug `eeeb866f`):** only covers client disconnect. Container restart still kills the runner. Persisting runner state to Redis between agent steps is the proper fix; deferred until real testers see it.

### Trade auto-adds to ticker tape (`dc16910`)

`sim.submit` idempotently adds the traded ticker to `sim_watchlists` on success. Flutter's `simSubmit` refreshes the watchlist after a successful trade; the ticker-tape provider listens on a sorted-comma-joined projection of watchlist tickers and silent-refreshes when that key changes. No 120s wait.

### Concierge prompt rewrite (`dc16910`)

`content/agents/concierge.md` used to promise "Want me to open it?" — the app had no mechanism. Concierge now gives explicit navigation: *"Try **Lesson 12: Order Types**. You'll find it under **Lessons → Foundations**."* Hard rule baked into the prompt that it can't navigate for the user.

### Light/dark mode — honest fix (`dc16910`)

The toggle was a lie: 37 screens hardcode `AmiColors.slate900`/`slate800`. Removed the broken radio group from Settings → APPEARANCE; replaced with a single info row: "Dark theme — Alpha is dark-only. Light + Follow System land in v1.0." Coerces `ThemeMode.dark` on render. Full refactor (37 files → theme-aware colors) is v1.0 work.

### Workflow + scripts

- **`/fix-bugs`** (`99e6e0d`) — spawn `.claude/worktrees/bug-fix-<ts>`, claim bugs atomically via `bug_reports.assigned_branch + status='in_progress'`, triage tiny/small/medium/large, fix up to 3 per session, commit each as `fix(bug:<short-id>):`, flip to `pending_review` (humans confirm `resolved` on merge). Hands-off file list keeps high-conflict files (main.py, alembic, pubspec, compose) routed through human review.
- **`bug_reports.assigned_branch`** column (Alembic `a8e3c1b50006`). Status vocabulary: `open → in_progress → pending_review → resolved` (or `wont_fix`).
- **`/start-fresh` updated** (`aca28ee`) — pulls `bug_reports` at session start, surfaces open + pending_review counts + 10 latest titles in the plan, asks "bugs first or carry-over first?" with a directive-mapping table.
- **`scripts/build_testflight.sh`** (`c14ce2a`) — auto-bumps pubspec build number, `flutter build ipa --release --export-method=app-store`, uploads via `xcrun altool` with the App Store Connect API key.
- **`scripts/install_iphone.sh`** (`c14ce2a`) — release build + install on TESTING IPHONE 13 (or `$1` device). Pre-flight checks the device is connected.

### CLI TestFlight unblocked

The AT:R18 carry-over. Saiful signed Xcode into the Apple Developer account; one manual archive export through Organizer landed the Distribution cert + provisioning profile in keychain. After that, CLI build IPA works. App Store Connect API key generation needed a second go (first key was Developer role → 401; App Manager key `44VJ5WADL2` works). `0.1.0+4` uploaded via `scripts/build_testflight.sh` — first end-to-end CLI push.

### Website backend split

- Waitlist endpoint removed from the trade backend (`306ef73`). Files deleted: `backend/app/api/waitlist.py`, `schemas/waitlist.py`, `services/waitlist_store.py`. `WaitlistRow` model removed.
- `api-website` service added to `docker-compose.yml` (`b94adee`). Port 8001, separate `ami_website` DB, CORS for `agenticmarketintel.ai` + www. `promote-to-alpha` excludes `website/` from rsync (`65fec8e`); `website_api/` is shipped (api-website's source).

### Bug-report drift fix (handover scan)

`mobile/lib/state/feedback_providers.dart` had `kAppVersion = '0.1.0+2'` hardcoded. 13 user-filed bug reports tagged stale. Updated to `'0.1.0+4'`; filed `82cb07c6` for `package_info_plus` proper fix.

### Bug list at handover (5 open)

| short_id | title | bucket |
|---|---|---|
| `3ef7ca04` | Entry removed snackbar persists until app backgrounded | small–medium |
| `278cbad8` | Stale `room_runs` cleanup job — mark long-running rows as aborted | small |
| `eeeb866f` | Room run survives api-alpha container restart | large |
| `82cb07c6` | app_version constant in bug reports drifts from pubspec.yaml | small |
| (Saiful's 03:45) | "convene failed — stream failed. error 502" | likely transient; mark resolved if doesn't repro |

### Carry-overs for AT:R20

1. **Install `+5` on TESTING IPHONE 13** — `scripts/install_iphone.sh` (after waking the device). On-device validation of trash view, snackbar UNDO, room reconnect banner, ticker-tape-on-trade.
2. **Push next build to TestFlight** — `scripts/build_testflight.sh` (auto-bumps).
3. **First `/fix-bugs` run** — 5 open bugs queued.
4. **Verify Concierge prompt rewrite works** on-device.
5. **A22 — Privacy policy + ToS public URL** (Saiful-external, legal, long-standing).
6. **External TestFlight launch** — Beta App Description + ~24h Apple review on first external build.
7. **Animation production** — `AnimationRegistry` empty; pending Lottie art (external).
8. **A29 full light-mode refactor** — 37 hardcoded `AmiColors.slate900`/`slate800` references. v1.0 work.

---

## How to start the next session

```
/start-fresh
```

The slash command reads HANDOVER.md + project plan, runs the Mac-side sanity-check curls, queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R20** (this is handover #19).

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
```

---

## Open questions / nothing-is-blocked items

- **Anthropic API key.** Not added — and not needed: on-prem vLLM at `192.168.20.74:8000` serves Gemma 4 31B for every agent. Anthropic remains a hot-swappable fallback if `VLLM_BASE_URL` is unset.
- **Supabase project.** Not yet provisioned. RLS policies live but dormant — they enforce once the backend stops connecting as `postgres`.
- **Apple Developer team.** Done (`S7RBWM4879`). Sign in with Apple capability still needs to be added to the bundle id for prod usage.
- **App Store + APNs** — external. Market data is real Yahoo when `USE_REAL_MARKET_DATA=true`.

Nothing is blocking the next chunk.
