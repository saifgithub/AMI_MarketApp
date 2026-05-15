# Handover — AMI Trade build session

**Last updated:** 2026-05-15 (end of AT:R20 — 6 bugs fixed across two `/fix-bugs` worktrees, live yfinance fundamentals now reach all 12 agents in both Convene + 1-on-1, in-app bug reporter accepts photo attachments, `flutter_markdown` → `flutter_markdown_plus` swap, `install_iphone.sh` quieted, legal-research docs landed under `docs/09_compliance/`. **149 commits, 261 tests**, 3 alpha promotions today (`alpha-2026-05-15-{1,2,3}`), pubspec at `0.1.0+6`, TESTING IPHONE 13 still on `+4` — a `+6` install is the first carry-over so on-device validation can begin.)

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **149 commits**, no remote yet |
| Latest commit | `6cd685a` — docs(compliance): legal sample research + AMI Trade ToS/Privacy plan |
| Alpha tags | `alpha-2026-05-13-{1..8}` + `alpha-2026-05-14-{1..9}` + `alpha-2026-05-15-{1..3}` (latest `alpha-2026-05-15-3`) |
| Backend tests | **261 passed, 0 failed** |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, 262 i18n keys (EN canonical; AR + MS auto-translated by Gemma 4) |

```
$ git log --oneline | head -5
6cd685a docs(compliance): legal sample research + AMI Trade ToS/Privacy plan
478ebf2 chore(ios): regen Podfile.lock for image_picker dep
7ab79e1 chore(mobile): bump build 0.1.0+5 → 0.1.0+6 for TestFlight
c3ab51b feat(feedback): attach a photo to in-app bug reports
1385f0d chore(mobile,scripts): swap to flutter_markdown_plus + quiet install_iphone.sh
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
| Routes | `/v1/health`, `/v1/auth/*`, `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/coach/*`, `/v1/journal/*` (incl. `/trash`, `/{id}/restore`), `/v1/lessons/*`, `/v1/llm/status`, `/v1/mandate/*`, `/v1/room/*`, `/v1/sim/*`, `/v1/watchlist/*`, `/v1/feedback/bug` (now `multipart/form-data` with optional `file`) |
| Mac-side tests | `pytest backend/tests/unit/ -q` — **261 passed**. Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
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
| pubspec version | **`0.1.0+6`** |
| TESTING IPHONE 13 install | release `0.1.0+4` (PRE-AT:R20; needs a `+6` install via `scripts/install_iphone.sh` to validate all 8 AT:R20 fixes + the photo-attachment bug reporter). |
| TestFlight | `0.1.0+4` uploaded 2026-05-14 via CLI. `+5` / `+6` not yet pushed. Build via `scripts/build_testflight.sh`. |
| Build commands | `scripts/install_iphone.sh` (dev sideload — now uses `flutter devices --machine` so it doesn't print iPhone 17 LAN-probe noise), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. Journal has soft-delete with UNDO + 30-day Trash view + server-side search. Room + 1-on-1 agent text now renders as Markdown (bold metrics, bullet lists). Ticker tape below bottom nav (Yahoo Finance, refreshes when watchlist changes). Settings → APPEARANCE is dark-only (light-mode toggle removed; the v1.0 refactor will reintroduce it). Settings → COMPLIANCE labels are tappable — each opens a plain-English bottom sheet explaining what that flag filters. Bug-report sheet (long-press app-version chip) now has an "Attach photo" affordance routing through the camera/library picker.

---

## What just landed (this session — AT:R20)

Bug-fix session that bled into substantial feature work. 18 commits, 3 alpha promotions (`alpha-2026-05-15-{1,2,3}`), one new schema migration (`b1c4e8d70007`), test count 220 → **261**.

### Bug fixes — two `/fix-bugs` worktrees

Saiful had 9 open bugs at the start. Triaged into 2 worktrees + 2 no-code closes:

| short_id | title | resolution |
|---|---|---|
| `a606436f` | fund agent report on AAPL (dup) | wont_fix — duplicate of `85469d8e` |
| `b6e8c505` | convene failed 502 | resolved — filed pre-AT:R19 SSE fix, no longer repros |
| `3ef7ca04` | Snackbar persists until backgrounded (`f0063d6`) | Capture `ScaffoldMessenger.of(context)` BEFORE `notifier.deleteEntry()` — the deleteEntry triggers a synchronous state rebuild that deactivates the itemBuilder context, so a later messenger lookup returns a detached state whose auto-dismiss timer never fires. |
| `278cbad8` | Stale `room_runs` cleanup (`49e88b0`) | Added an UPDATE to `trim_audit_tables()` in `app/services/audit.py` — any row stuck in `status='running'` for > 30 min flips to `aborted`. Runs nightly via the existing lifespan task. |
| `82cb07c6` | `kAppVersion` drifts from pubspec (`918111c`) | Added `package_info_plus ^9.0.1`; replaced the hand-maintained const with `appVersionProvider` (FutureProvider). Three call sites updated. |
| `85469d8e` | Fundamentals agent uses synthetic P/E (`4c59f61`, extended in `dcf3445`) | Room runner's `_profile_for_ticker` overlays real yfinance fundamentals (`trailingPE`, `revenueGrowth`, `profitMargins`, 52-wk range, `currentPrice`, `totalCash/Debt`) on the synthetic baseline when `settings.use_real_market_data`. Gated for test determinism. Profile carries a `data_source` flag; `_format_profile` labels live vs synthetic. Task framing tells the LLM to ONLY cite numbers from the data block, never training memory. Extended (`dcf3445`) to all 12 agents in the **1-on-1** path too via a new shared module `app/services/fundamentals.py` — `extract_tickers(user_message)` regex + blocklist of common English / acronyms, fetches per-ticker, appends a `LIVE MARKET DATA — <SYM>` block to the system prompt. Falls back to the last 3 turns of history if the current message has no ticker. |
| `90441819` | Compliance chips need tap-to-explain (`a9b3540`) | Each of the 6 toggles (Halal, ESG-lite, TAG, fossil-free, long-only, liquid-only) is now an `InkWell` with `info_outline` icon; tap → bottom sheet with a plain-English explanation. Toggle hit-target unchanged (right-side switch). |
| `2795baf2` | Agent response formatting (`b389b2f`) | Added `flutter_markdown ^0.7.7+1` (later swapped to `flutter_markdown_plus ^1.0.3` after upstream marked it discontinued). Replaced `Text()` in `_AgentLine` (room_screen.dart) and `ChatBubble` (chat_bubble.dart) with `MarkdownBody`. Room agent prompt instructed to lead with a one-sentence thesis, use bullets for evidence, **bold** for key metrics. |
| `eeeb866f` | Room run survives container restart | **deferred** — large; needs Redis-backed runner state or worker-process split. |

### Photo attachments in the in-app bug reporter (`c3ab51b`)

End-to-end vertical:
- Alembic `b1c4e8d70007` adds `bug_reports.attachment_path` + `attachment_mime` (both nullable).
- New `app/services/bug_attachments.py` — disk-backed storage. MIME allowlist (jpeg/png/heic/heif/webp/gif), 5 MB cap, files written with `O_EXCL` to refuse collisions, named-volume on melehost mounted at `/data/bug_attachments`. No public download endpoint — review via SSH.
- `POST /v1/feedback/bug` rewritten as `multipart/form-data`. 415 for bad MIME, 413 for oversized, empty file silently treated as no attachment (cancelled picker shouldn't bounce the whole report). DB write proceeds even if disk write fails (text > photo).
- Flutter: `image_picker ^1.2.2`, "Attach photo" outlined button → camera/library bottom sheet → 56px thumbnail preview with × clear. `api_client.submitBugReport` uses `FormData` with optional `MultipartFile`. iOS Info.plist gets `NSCameraUsageDescription` + `NSPhotoLibraryUsageDescription`.
- +18 tests across `test_bug_attachments.py` and `test_feedback_api.py` (storage helper + TestClient-based multipart round-trip).

### Honest follow-ups

- **`uv.lock` tracked** (`984b2a0`) — was previously untracked. Lock file should travel with the repo for reproducible dep resolution.
- **`scripts/install_iphone.sh` quieted** (`1385f0d`) — Flutter's text-mode device listing was probing the LAN for the paired-but-offline iPhone 17 and printing `Browsing on the local area network for Saiful's iPhone 17 … (code -27)`. Script's UDID was always TESTING IPHONE 13 (`00008110-000261101A22801E`). Switched to `flutter devices --machine` (JSON, no probe), resolves the friendly name for an unambiguous "▶ Target device : TESTING IPHONE 13 (UDID)" banner, and filters the known LAN-probe noise from build/install stderr.
- **`flutter_markdown` swap** (`1385f0d`) — upstream marked it discontinued; swapped to the maintained fork `flutter_markdown_plus`. Drop-in API, two import sites updated.
- **Legal research** (`6cd685a`) — research agent surveyed 5 peer apps + 2 vendor disclosures (Zoya, Wall Street Survivor/StockTrak, Public.com, Character.AI, OpenAI, RevenueCat, Sentry). Saved `docs/09_compliance/legal_samples.md` (quoted clauses by topic) + `docs/09_compliance/legal_plan_ami_trade.md` (clause-by-clause starter language, lawyer-only callouts, App Store MVP subset). Closes the writing-up half of A22; hosting + lawyer review remains on Saiful.

### Bug list at handover (3 open)

| short_id | title | bucket |
|---|---|---|
| `f7c4d7e0` | screenshot | filed during session, unclassified; check raw content |
| `698a0fe6` | convene report not stored | filed during session, needs triage |
| `eeeb866f` | Room run survives api-alpha container restart | large — deferred since AT:R19 |

DB-wide: `open=3 / pending_review=6 / resolved=10 / wont_fix=1`. The 6 `pending_review` are this session's fixes — they'll flip to `resolved` automatically once Saiful merges to main and on-device-validates. (They were merged this session; the flip-to-resolved is still manual.)

### Carry-overs for AT:R21

1. **Install `+6` on TESTING IPHONE 13** — `scripts/install_iphone.sh`. Validates all 8 AT:R20 fixes: snackbar auto-dismiss, app-version chip on Settings (should read `0.1.0+6` now), Markdown render in Room + 1-on-1, compliance tap-to-explain bottom sheets, "Attach photo" affordance in bug-report sheet.
2. **Push `+6` to TestFlight** — `scripts/build_testflight.sh` will auto-bump to `+7` and upload.
3. **Triage `f7c4d7e0` + `698a0fe6`** — two new open bugs filed mid-session. Run `/fix-bugs` next session.
4. **Flip the 6 `pending_review` bugs to `resolved`** — they're merged on main and live on alpha; just need the DB UPDATE.
5. **A22 part 2 — host the legal docs publicly + lawyer review.** Research is in `docs/09_compliance/legal_plan_ami_trade.md`. Needs (a) Saiful to send to a lawyer, (b) the polished output hosted at `agenticmarketintel.ai/legal/{privacy,terms}` before App Store submission.
6. **External TestFlight launch** — Beta App Description + ~24h Apple review on first external build.
7. **Animation production** — `AnimationRegistry` empty; pending Lottie art (external).
8. **A29 full light-mode refactor** — 37 hardcoded `AmiColors.slate900`/`slate800` references. v1.0 work.
9. **Live fundamentals — 1-on-1 ticker extraction robustness** — current regex is `\$?[A-Z]{1,5}\b` + a 47-word blocklist. Watch user-filed bug reports for cases where it misfires (false positives → spurious yfinance call; false negatives → agent quotes training memory). Strengthen as needed.

---

## How to start the next session

```
/start-fresh
```

The slash command reads HANDOVER.md + project plan, runs the Mac-side sanity-check curls, queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R21** (this is handover #20).

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
