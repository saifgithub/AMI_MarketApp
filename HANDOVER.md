# Handover — AMI Trade build session

**Last updated:** 2026-05-17 (end of AT:R23 — First-time user walkthrough: per-section coach-mark tours (Floor 5 / Portfolio 3 / Journal 3 / Lessons 3) using `tutorial_coach_mark`, intro bottom sheet on first Floor visit, "Try it now" CTA on the Convene step, Settings → Restart app tour. Two follow-up fixes: scroll target into view before focus, switch top-aligned tooltips that overflowed off-screen to custom/bottom positioning. Bug-report sheet: form Column wrapped in `SingleChildScrollView` so photo + submit buttons stay reachable when the keyboard is open. **180 commits, 275 tests**, pubspec `0.1.0+14` in repo (no TestFlight push this session — release build sideloaded to TESTING IPHONE 13 for verification). No Alpha promotion — mobile-only change.)

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **180 commits**, no remote yet |
| Latest commit | `18ddf71` — fix: tour tooltip overflow + bug-report keyboard occlusion |
| Alpha tags | `alpha-2026-05-13-{1..8}` + `alpha-2026-05-14-{1..9}` + `alpha-2026-05-15-{1..4}` + `alpha-2026-05-16-1` + `alpha-2026-05-17-{1..5}` (latest `alpha-2026-05-17-5` — unchanged this session) |
| Backend tests | **275 passed, 0 failed** |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **312 i18n keys** (EN canonical; +37 tour keys this session for the walkthrough) |

```
$ git log --oneline | head -8
18ddf71 fix: tour tooltip overflow + bug-report keyboard occlusion
684b180 fix(tour): scroll target into view before coach mark focuses
462dafe feat(onboarding): per-section coach-mark walkthrough for first-time users
8c7777e docs(handover): audit + correct AT:R23 carry-overs
c397991 docs(handover): correct bug DB counts — 24 resolved / 2 wont_fix
ea35674 handover: wrap AT:R22 — 174 commits, 275 tests, alpha-2026-05-17-5
6f78c8c chore(mobile): bump build 0.1.0+13 → 0.1.0+14 for TestFlight
9814e63 feat(trade-ticket): live price anchor + auto-suggested TP/SL on manual trade
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
| pubspec version | **`0.1.0+14`** (repo) — unchanged this session. |
| TESTING IPHONE 13 install | release build of HEAD (`18ddf71`) sideloaded via `scripts/install_iphone.sh` for tour verification. Version chip still reads `0.1.0+14` because pubspec wasn't bumped. |
| TestFlight | Latest uploaded build is still `0.1.0+14` from AT:R22. No TestFlight push this session — Saiful chose handover-only on close. Next `scripts/build_testflight.sh` run will auto-bump to `+15` and ship the walkthrough. |
| Build commands | `scripts/install_iphone.sh` (dev sideload — now uses `flutter devices --machine` so it doesn't print iPhone 17 LAN-probe noise), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **First-time walkthrough (AT:R23):** per-section coach-mark tours fire automatically on first visit to each tab — Floor opens with an intro bottom sheet ("Take the tour / Skip for now"), then 5 spotlight steps narrating Concierge → analyst team → locked agents → daily challenge → Convene; Portfolio / Journal / Lessons each fire 3 steps. Convene step exposes a "Try it now →" CTA that closes the tour and opens the Convene sheet. Each section flag (`tour_{floor,portfolio,journal,lessons}_seen`) is in SharedPreferences; Settings → WALKTHROUGH → "Restart app tour" clears all four. Journal filter chips: `ALL · ROOM · TRADE · 1-ON-1 · COACH · LESSONS · UNLOCKS` (ROOM + TRADE at positions 2/3). Journal has soft-delete with UNDO + 30-day Trash view + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green "✓ BUY 1 TSLA @ $X" pill once a sim_trade exists with `verdict_ref == runId`. Trade ticket sheet: live quote chip under the ticker field with `LIVE`/`MOCK` source pill + auto-suggested TP/SL at -6%/+13% of price; non-blocking "NO AI VERDICT" advisory at top when no verdict was convened. Ticker tape below bottom nav (Yahoo Finance, refreshes when watchlist changes). Settings → APPEARANCE is dark-only. Settings → COMPLIANCE labels are tappable. Bug-report sheet (long-press app-version chip) supports photo attachments, offers a `feature_request` category, and now scrolls correctly when the keyboard is open.

---

## What just landed (this session — AT:R23)

Single-feature session: 3 commits implementing the first-time user walkthrough. Pure mobile work — backend untouched, no Alpha promotion. Triggered by Saiful's `/grill-me` session: *"the app is selling itself as a gamified 'education' utility. so yes, the trade, the user should have a walkthrough."*

### First-time walkthrough — 4 contextual coach-mark tours (`462dafe`)

Design decisions locked during the grill: per-section auto-pop tours (not one giant tour); `tutorial_coach_mark` package (not custom); 3–5 steps per section; "Try it now" CTA only on the Convene step; intro bottom sheet only for Floor; one global reset in Settings.

**Architecture:**

- **`mobile/lib/features/tour/`** — new package containing the whole feature.
  - `tour_service.dart` — `TourSection` enum (floor/portfolio/journal/lessons) + `TourService` with `hasSeen` / `markSeen` / `resetAll` backed by SharedPreferences keys `tour_{section}_seen`.
  - `tour_providers.dart` — `tourServiceProvider` (Riverpod) + `activeTabIndexProvider` (StateProvider<int>).
  - `tour_card.dart` — shared AMI-styled tooltip widget with title (cyan mono) / body / skip / next buttons. Supports an optional `tryNowLabel + onTryNow` pair for the Convene step.
  - `tour_intro_sheet.dart` — modal sheet shown before the Floor tour; returns `bool?` via `Navigator.pop`.
  - `{floor,portfolio,journal,lessons}_tour.dart` — `buildXxxTargets()` functions returning `List<TargetFocus>`.

- **`IndexedStack` gotcha:** `HomeShell` keeps all 5 tab widgets alive via `IndexedStack` so every screen's `initState` fires on app start regardless of which tab is visible. Naive trigger-from-initState would fire all 4 tours simultaneously over the Floor tab. Solved with `activeTabIndexProvider`: HomeShell writes the current tab into it on every `onTap`, and each screen uses `ref.listen(activeTabIndexProvider, ...)` in `build` to fire the tour only when its index becomes active. Floor (tab 0) additionally fires from `initState` since it's the entry tab.

- **GlobalKey wiring:** 4 screens converted from `ConsumerWidget` to `ConsumerStatefulWidget` to hold GlobalKey fields. Private widget constructors (`_Header`, `_ValueCard`, `_WatchlistSection`, `_FilterRow`, `_SearchBar`, `_SlimProgressBar`, `_HexCluster`) gained `super.key` so the key flows down to their RenderBox.

- **Floor tour (5 steps):** Concierge hex → first agent tile → another agent tile (locked) → daily challenge card (conditional — only included if the challenge's RenderObject has non-zero size) → Convene the Room button. Convene's `TourCard` shows the dual-button row "Skip tour / Try it now → / Got it". Tap "Try it now" → tour skipped → `ConveneSheet.show(context)` opens.

- **Portfolio / Journal / Lessons tours (3 steps each):** Portfolio = header / value card / watchlist. Journal = filter chips / search bar / list area. Lessons = header / progress bar / hex cluster.

- **Completion:** Each tour ends with a green/cyan/blue floating SnackBar ("Go convene your first Room.", "Try a trade — all simulation, no risk.", etc.).

- **i18n:** 37 new keys in `app_en.arb` under a `tour*` namespace (intro / 5×Floor / 3×Portfolio / 3×Journal / 3×Lessons / completion x4 / nav buttons / settings). Same set stubbed into `app_{ar,ms}.arb` with English values pending external translation.

- **Settings:** new `_WalkthroughSection` between Help and Account renders one "Restart app tour" tile that calls `tourService.resetAll()` and snackbars "Tour restarts next time you visit each section."

### Fix 1: scroll target into view before focus (`684b180`)

Convene step coach-mark fired against a button below the initial scroll fold — Saiful saw the spotlight halo over empty space. `TutorialCoachMark.beforeFocus` callback now calls `Scrollable.ensureVisible` on each target so the highlighted element is brought into view before the spotlight opens. Same pattern applied to Portfolio (ListView) and Lessons (SingleChildScrollView).

### Fix 2: tour tooltip overflow + bug-report keyboard occlusion (`18ddf71`)

Two observations during on-device verification:

- **Journal step 3** target = the `Expanded` list area, which fills most of the screen. `ContentAlign.top` math (`bottom = haloHeight + (screenHeight − targetCenterY)`) pushed the tooltip's top edge above the screen on tall targets. Switched to `ContentAlign.custom` with a fixed `top: 180` anchor below the search bar.
- **Lessons step 3** target = the hex cluster, positioned high enough that `ContentAlign.top` landed the tooltip behind the status bar. Switched to `ContentAlign.bottom` since the area below the cluster is empty space.
- **Bug-report sheet** — when the user tapped a text field, the keyboard pushed the form up but the photo + Send report buttons sat below the viewport. Wrapped the form's Column in `SingleChildScrollView` so the sheet can scroll under the keyboard inset.
- The `beforeFocus` callback now picks scroll alignment based on tooltip position: `0.85` (target near bottom) if the tooltip is `ContentAlign.top`, else `0.15` (target near top). Dynamic per-step rather than hardcoded.

### Bug list at handover

| short_id | title | status |
|---|---|---|
| `eeeb866f` | Room run survives api-alpha container restart | **open — deferred (large)** |

DB-wide unchanged this session: `open=1 / pending_review=0 / resolved=24 / wont_fix=2`. No new bug reports filed against the walkthrough during on-device verification — both surfaced issues (target overflow, keyboard) were fixed inline by Saiful's feedback.

### Carry-overs for AT:R24

Counts audited against tree state at end of AT:R23 — no stale figures.

1. **TestFlight push the walkthrough** — pubspec is still `0.1.0+14`; next `scripts/build_testflight.sh` run auto-bumps to `+15` and ships the walkthrough to Internal testers. Saiful explicitly chose handover-only on close this session.
2. **T&C + Privacy Policy (A22 part 2)** — research in `docs/09_compliance/legal_plan_ami_trade.md`. Still needs (a) hosting at `agenticmarketintel.ai/legal/{privacy,terms}` and (b) lawyer review before App Store submission. Not touched this session.
3. **`eeeb866f`** — room run survives container restart — open/deferred. Clean upgrade path (Celery + Redis broker; per-user FIFO) sketched in `docs/external/async_job_server_design_prompt.md`. Beta-window work.
4. **External TestFlight launch** — Beta App Description + ~24h Apple review on first external build. `scripts/build_testflight.sh` uploads to Internal only by default; no External Beta artefact in the repo yet.
5. **Animation production** — 15 `<Animation>` MDX tags in `content/lessons/` (verified by `grep -roh '<Animation [^>]*/>' content/lessons/ | wc -l`). All render `AmiHexPlaceholder`. See `memory/project_animations.md` for the Lottie vs CustomPainter decision.
6. **A29 light-mode refactor** — 125 hardcoded `AmiColors.slate900`/`slate800` references across `mobile/lib/`. Note that the walkthrough's `TourCard` adds 1 more (slate800 background) — recount before estimating effort. v1.0 work.
7. **Two sibling worktrees with unmerged docs** — `claude/blissful-darwin-419097` (one commit `f94ad0e` — bug-pipeline spec + D-057) and `claude/exciting-shtern-aad051` (one commit `ead7038` — lessons-landing hex-cluster redesign). Still pending Saiful decision: merge to main or discard.

### Watch items (not tasks)

- **Walkthrough field testing.** The 4 tours haven't been tested by anyone other than Saiful. Internal testers on `+15` will be the first to hit the auto-pop flow with their own state (e.g. some agents already unlocked from prior sessions). If a tester reports the target widget is invisible (e.g. challenge card hidden because there's no daily challenge that day) the conditional-step pattern in `buildFloorTargets` (`challengeKey.currentContext?.findRenderObject() != null` check) is the precedent to extend.
- **Room dedup window tuning** — `ROOM_DEDUP_COMPLETED_HOURS=24` in `infra/alpha.env`. Design doc default was 5 days; raise via env if testers complain about same-day re-runs being blocked. The knob is live; no code change needed.
- **NVFP4 quantisation produces space-split tokens** — observed since day one (e.g. "Consol idation", "NV DA"). Not a regression, not blocking alpha. vLLM-side tuning is the path if user-visible.

---

## How to start the next session

```
/start-fresh
```

The slash command reads HANDOVER.md + project plan, runs the Mac-side sanity-check curls, queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R24** (this is handover #23).

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
