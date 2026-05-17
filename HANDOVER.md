# Handover — AMI Trade build session

**Last updated:** 2026-05-17 (end of AT:R22 — Room resilience overhaul: background-task pipeline + incremental checkpoint + dedup tiers + startup sweep + journal retry + cached-run replay. 5 bug fixes (incl. journal trade-dict, one-purchase-per-verdict, trade-success feedback, no-verdict advisory). 2 features: ROOM/TRADE journal filters + feature_request bug category; live quote anchor in trade ticket with auto-suggested TP/SL. Doc fix: melehost LAN IP corrected `.9` → `.59`. **174 commits, 275 tests**, pubspec `0.1.0+14` in repo, TESTING IPHONE 13 on release `0.1.0+14`. Alpha tags `alpha-2026-05-17-{1..5}` promoted.)

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **174 commits**, no remote yet |
| Latest commit | `6f78c8c` — chore(mobile): bump build 0.1.0+13 → 0.1.0+14 for TestFlight |
| Alpha tags | `alpha-2026-05-13-{1..8}` + `alpha-2026-05-14-{1..9}` + `alpha-2026-05-15-{1..4}` + `alpha-2026-05-16-1` + `alpha-2026-05-17-{1..5}` (latest `alpha-2026-05-17-5`) |
| Backend tests | **275 passed, 0 failed** |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, 264 i18n keys (EN canonical; AR + MS — `journalFilterRoom` / `journalFilterTrade` added this session) |

```
$ git log --oneline | head -8
6f78c8c chore(mobile): bump build 0.1.0+13 → 0.1.0+14 for TestFlight
9814e63 feat(trade-ticket): live price anchor + auto-suggested TP/SL on manual trade
5719cb8 chore(mobile): bump build 0.1.0+12 → 0.1.0+13 for TestFlight
adc3d11 feat(bug:1e645bca,feedback): ROOM + TRADE journal filters; feature_request category
5ea2441 chore(mobile): bump build 0.1.0+11 → 0.1.0+12 for TestFlight
a8ffafb fix(bug:d5717660): advise convening the Room before trading without a verdict
6234068 chore(mobile): bump build 0.1.0+10 → 0.1.0+11 for TestFlight
1e69052 fix(bug:9b3a6c2f): unambiguous trade-success feedback (snackbar + verdict pill)
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
| Routes | `/v1/health`, `/v1/auth/*`, `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/coach/*`, `/v1/journal/*` (incl. `/trash`, `/{id}/restore`), `/v1/lessons/*`, `/v1/llm/status`, `/v1/mandate/*`, `/v1/room/*`, `/v1/sim/*`, `/v1/watchlist/*`, `/v1/feedback/bug` (now `multipart/form-data` with optional `file`) |
| Mac-side tests | `pytest backend/tests/unit/ -q` — **275 passed**. Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
| Room env knobs | `ROOM_DEDUP_RUNNING_MINUTES=30` (in-flight dedup + startup-sweep cutoff) · `ROOM_DEDUP_COMPLETED_HOURS=24` (return prior verdict same day; design doc default was 5 days — we start tighter). Set completed_hours=0 to disable cached-run dedup. |
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

Tables: `users`, `auth_challenges`, `mandates`, `agent_activations`, `lessons_progress`, `journal_entries` (with `deleted_at`), `overlay_edit_counts`, `user_overlays`, `room_runs`, `sim_holdings`, `sim_portfolios`, `sim_trades`, `sim_watchlists`, `bug_reports` (with `assigned_branch`, `attachment_path`, `attachment_mime`), `llm_audit`, `http_audit`, `one_on_one_messages`, `alembic_version`. Latest migration on melehost: `b1c4e8d70007` (`bug_reports.attachment_path` + `attachment_mime`). `init_schema()` self-stamps Alembic on a fresh container, so `alembic upgrade head` is a no-op on first boot. Bug-report attachments live in the named docker volume `ami-trade-local_bug_attachments` mounted at `/data/bug_attachments` in the api-alpha container; review via `ssh melehost "sudo ls -la /var/lib/docker/volumes/ami-trade-local_bug_attachments/_data/"`.

### LLM gateway

- **vLLM** at `http://192.168.20.74:8000` serving `ami-llm` (Gemma 4 31B, NVFP4 quantized, 262k context — rebranded from `gemma-4-31b-it-nvfp4`). Gateway preference: `vllm > anthropic > mock`.
- Per-(plan, agent) tier routing in `app/services/tier_policy.py::pick_tier`.

### Market data

- `USE_REAL_MARKET_DATA=true` on melehost. Fallback stack: yfinance → 60s cache → `mock_walk` if Yahoo returns empty/error.
- Quote model: `Quote(price, source, change_pct, market_state)` — `source` is the LEAF that served (`yfinance` or `mock_walk`), not the stack name.

### Mobile app

| | |
|---|---|
| Bundle | `ai.agenticmarketintel.amiTrade` |
| pubspec version | **`0.1.0+14`** (repo) — `0.1.0+9..+14` all uploaded to TestFlight this session as bug fixes / features landed (`+9` first this session, `+10` carries duplicate-verdict guard testing context, `+11`/`+12`/`+13`/`+14` ship the post-resilience UX work). |
| TESTING IPHONE 13 install | release `0.1.0+14` (latest TestFlight upload — quote anchor in trade ticket). |
| TestFlight | `0.1.0+14` on device. Next upload auto-bumps to `+15`. Build `+7` was uploaded twice in error early in AT:R22 — Apple deduped, no harm. |
| Build commands | `scripts/install_iphone.sh` (dev sideload — now uses `flutter devices --machine` so it doesn't print iPhone 17 LAN-probe noise), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. Journal filter chips: `ALL · ROOM · TRADE · 1-ON-1 · COACH · LESSONS · UNLOCKS` (ROOM + TRADE added AT:R22, promoted to positions 2/3 because users review those most). Journal has soft-delete with UNDO + 30-day Trash view + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green "✓ BUY 1 TSLA @ $X" pill once a sim_trade exists with `verdict_ref == runId`. Trade ticket sheet: live quote chip under the ticker field with `LIVE`/`MOCK` source pill + auto-suggested TP/SL at -6%/+13% of price; non-blocking "NO AI VERDICT" advisory at top when no verdict was convened. Ticker tape below bottom nav (Yahoo Finance, refreshes when watchlist changes). Settings → APPEARANCE is dark-only. Settings → COMPLIANCE labels are tappable. Bug-report sheet (long-press app-version chip) supports photo attachments and now offers a `feature_request` category alongside the existing bug types.

---

## What just landed (this session — AT:R22)

Dense bug-fix + resilience session. 19 commits, **5 alpha promotions** (`alpha-2026-05-17-{1..5}`), test count 264 → **275**. Six TestFlight builds (`+9..+14`).

### Room resilience overhaul (`8a9f4da`, `b9050b9`, `7fca2c7`)

Three commits closing the resilience gaps the explore agent surfaced. The pipeline used to be SSE-coupled: client disconnect (phone sleep, LTE handoff, Cloudflare timeout) tore down the runner generator, partial transcript was persisted as CANCELLED, no verdict was reached.

- **Background task + queue (`8a9f4da`)** — runner now starts via `RoomRunner.start_run()`, which creates an `asyncio.Queue` keyed by `run_id`, fires `asyncio.create_task(_pump())`, and returns the `run_id` immediately. The SSE consumer reads from the queue via `runner.subscribe(run_id)`. Client disconnect kills the SSE consumer; the `_pump` keeps running to the verdict and the `on_complete` callback (journal write) always fires from the `finally` block. `X-Room-Run-Id` header carries the run_id to the client before any SSE body so a reconnecting client can `GET /v1/room/{run_id}` for the snapshot. Incremental transcript checkpoint after each agent. Dedup tier 1 (same user+ticker while running). Startup sweep marks abandoned `running` rows as `failed`. Journal retry on transient DB error. +5 tests.

- **Completed-run dedup (`b9050b9`)** — design-doc-style configurable lookback. New env knobs `ROOM_DEDUP_RUNNING_MINUTES=30` and `ROOM_DEDUP_COMPLETED_HOURS=24` (design doc default is 5 days; we start at 1 day so re-runs after the next-day open aren't blocked — raise via env to taste, 0 disables). Dedup tier 2 returns the prior verdict's `run_id` without spinning up a `_pump` — saves ~5 minutes of LLM time when the user double-taps "Convene the Room" or hits it again the same day. +2 tests.

- **Cached-run replay (`7fca2c7`)** — first version of tier-2 dedup made the client render "Room ended without a verdict" because `subscribe()` returned immediately on a cached `run_id` and the SSE emitted only the `done` event. Fix: `RoomRunner.is_active(run_id)` exposes whether there's a live queue; the API layer detects cached dedup, replays the persisted transcript as a compressed SSE stream (`started` → one `agent_token` + `agent_done` per agent → `phase: VERDICT` → `verdict`), and sets `X-Room-Cached: true` so a future client UI can show "cached analysis from earlier". +1 test.

### Five bug fixes (worked through one user-test cycle at a time)

| short_id | commit | summary |
|---|---|---|
| `698a0fe6` + `f7c4d7e0` | (resolved via the resilience work) | Validated on-device; flipped to resolved after the new background-task pipeline landed. |
| `6f9b5ebd` | `c9f682f` | Journal entry detail for sim_trade was dumping the raw Python-style dict. Added a typed render of horizon / status / opened-at / closed info / realised P&L / linked verdict_ref. |
| `ce7146c8` | `59acfe9` | Double-tap on the "Buy" button against the same verdict opened two identical trades. `SimEngine.submit()` now rejects when `(user_id, verdict_ref)` already has a trade (any status). Surfaces existing trade's short_id in the violation. `blocked_by` Literal gained `"duplicate_verdict"`. +2 tests. |
| `9b3a6c2f` | `1e69052` | Trade success was rendered with a slate800 snackbar — indistinguishable from the dark theme, drove the double-tap behind `ce7146c8`. Replaced with a green floating snackbar with check icon + haptic + 5s duration. Verdict card swaps the cyan "Open Trade Ticket" CTA for a green "✓ BUY 1 TSLA @ \$422.24" pill once a sim_trade exists for that verdict (watches `simNotifierProvider`). |
| `d5717660` | `a8ffafb` | When the user opens the trade ticket with no convened verdict, show a dismissible blue advisory: "Convene the Room first to get analysis from your 12 agents. Or proceed — this trade will be marked 'without advice'." Two buttons (Convene the Room / Proceed without). Journal detail shows `AI ADVICE: Without — manual trade` when `verdict_ref` is null. |

### Two features (`adc3d11`, `9814e63`)

- **ROOM + TRADE journal filter chips** (bug `1e645bca`) — promoted to positions 2/3 (right next to ALL) because users review those most. EN/AR/MS strings.
- **`feature_request` bug category** — Saiful's parallel ask. Backend `BugCategory` Literal extended; mobile dropdown picks it up. Retroactively recategorised `1e645bca`.
- **Live quote anchor in the trade ticket** (`9814e63`) — Saiful's quandary: "if I'm setting TP/SL, what do I base it on?" New `simQuoteDetail()` API method returns price + change% + source + market state. The trade ticket sheet debounces the ticker field (450ms), fetches the quote, renders a chip below the field (`$300.23  +1.20%  LIVE  CLOSED`), and pre-fills empty Stop / Target at -6% / +13% of the live price — same heuristic the Convene the Room Trader uses, so the anchor is consistent across both flows.

### Doc / infra: melehost LAN IP correction (`7c0f278`)

SSH config had `192.168.20.59` (correct) but every doc said `192.168.20.9` (wrong, never matched reality). Fixed across `CLAUDE.md`, `HANDOVER.md`, `infra/{cloudflared,local,systemd}/README.md`, `.claude/commands/promote-to-alpha.md`, `docs/10_delivery/promotion_protocol.md`, `docs/08_tech/hosting.md`. History.md left alone (snapshot of the past).

### Bug list at handover

| short_id | title | status |
|---|---|---|
| `eeeb866f` | Room run survives api-alpha container restart | **open — deferred (large)** |

DB-wide: `open=1 / pending_review=0 / resolved=24 / wont_fix=2`. Every bug surfaced this session is either resolved or closed (`7a9dd6b6` "journal needs a search facility" was a test feature-request — wont_fix, the search already exists). The one open item is the same Redis/worker architecture work that's been deferred since AT:R21 — see Beta upgrade path in the resilience plan.

### Carry-overs for AT:R23

Counts audited against tree state at end of AT:R22 — no stale figures.

1. **T&C + Privacy Policy (A22 part 2)** — research is in `docs/09_compliance/legal_plan_ami_trade.md`. Still needs (a) hosting at `agenticmarketintel.ai/legal/{privacy,terms}` and (b) lawyer review before App Store submission. Did NOT touch this session. (`A22` is still ⚡ partial in `docs/10_delivery/project_plan.md`.)
2. **`eeeb866f`** — room run survives container restart — open/deferred. The clean upgrade path (Celery + Redis broker; per-user FIFO) is sketched in `docs/external/async_job_server_design_prompt.md`. Beta-window work.
3. **External TestFlight launch** — Beta App Description + ~24h Apple review on first external build. Have not touched. `scripts/build_testflight.sh` uploads to Internal only by default; no External Beta artefact in the repo.
4. **Animation production** — **15 `<Animation>` MDX tags** in `content/lessons/` (verified by `grep -roh '<Animation [^>]*/>' content/lessons/ | wc -l`). All render `AmiHexPlaceholder` because the `AnimationRegistry` has no assets wired. See `memory/project_animations.md` for the Lottie vs CustomPainter decision.
5. **A29 light-mode refactor** — **125 hardcoded `AmiColors.slate900`/`slate800` references** across `mobile/lib/` (verified end-of-session). Heaviest concentrations: `screens/agent` (19), `screens/sim` (16), `screens/lessons` (15), `screens/journal` (14), `screens/room` (13). Earlier handovers said "37" — that was the in-`screens/` subset from an earlier audit; the real number is 3× larger. v1.0 work.
6. **Two sibling worktrees with unmerged docs** — `claude/blissful-darwin-419097` (one commit `f94ad0e` — bug-pipeline spec + D-057) and `claude/exciting-shtern-aad051` (one commit `ead7038` — lessons-landing hex-cluster redesign). Branches verified to exist; commits verified not in main. **Still pending Saiful decision: merge to main or discard.**

### Watch items (not tasks)

Worth knowing about for AT:R23, but no action item attached. Surfacing them separately so the carry-over list above stays actionable.

- **Room dedup window tuning** — `ROOM_DEDUP_COMPLETED_HOURS=24` in `infra/alpha.env`. Design doc default was 5 days. Raise if testers complain re-runs are blocked the same trading day for legitimate reasons; set to `0` to disable cached-run dedup entirely. The knob is live; no code change needed to retune.
- **NVFP4 quantisation produces space-split tokens** — observed since day one (e.g. "Consol idation", "NV DA"). Not a regression, not blocking alpha. If users start commenting on it, vLLM-side tuning would be the path.

---

## How to start the next session

```
/start-fresh
```

The slash command reads HANDOVER.md + project plan, runs the Mac-side sanity-check curls, queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R23** (this is handover #22).

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
