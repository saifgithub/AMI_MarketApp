# Handover — AMI Trade build session

**Last updated:** 2026-05-15 (end of AT:R21 — room-runner LLM timeout fix + journal-entry improvement for failed runs, `ami-llm` model rebrand across all config/tests/docs, alpha-2026-05-15-4 promoted, LLM end-to-end tested with 3 agents. **152 commits, 264 tests**, pubspec `0.1.0+6` in repo, TESTING IPHONE 13 on release `0.1.0+7`.)

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **152 commits**, no remote yet |
| Latest commit | `e79c598` — chore(llm): rebrand model id gemma-4-31b-it-nvfp4 → ami-llm |
| Alpha tags | `alpha-2026-05-13-{1..8}` + `alpha-2026-05-14-{1..9}` + `alpha-2026-05-15-{1..4}` (latest `alpha-2026-05-15-4`) |
| Backend tests | **264 passed, 0 failed** |
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
| pubspec version | **`0.1.0+6`** (repo; `+7` build was produced externally and confirmed on-device) |
| TESTING IPHONE 13 install | release `0.1.0+7` (confirmed by Saiful at AT:R21 start — pre-existing TestFlight build). |
| TestFlight | `0.1.0+7` on device. Next upload via `scripts/build_testflight.sh` will auto-bump to `+8`. |
| Build commands | `scripts/install_iphone.sh` (dev sideload — now uses `flutter devices --machine` so it doesn't print iPhone 17 LAN-probe noise), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. Journal has soft-delete with UNDO + 30-day Trash view + server-side search. Room + 1-on-1 agent text now renders as Markdown (bold metrics, bullet lists). Ticker tape below bottom nav (Yahoo Finance, refreshes when watchlist changes). Settings → APPEARANCE is dark-only (light-mode toggle removed; the v1.0 refactor will reintroduce it). Settings → COMPLIANCE labels are tappable — each opens a plain-English bottom sheet explaining what that flag filters. Bug-report sheet (long-press app-version chip) now has an "Attach photo" affordance routing through the camera/library picker.

---

## What just landed (this session — AT:R21)

Focused session: 2 data commits + 1 handover, 1 alpha promotion (`alpha-2026-05-15-4`), test count 261 → **264**.

### Room-runner fix: per-agent LLM timeout + better journal entry (`eb1ef3c`)

Root cause of `698a0fe6` + `f7c4d7e0` (convene report not stored / room stuck waiting):

- **Timeout**: Added `_AGENT_LLM_TIMEOUT_S = 90.0`. `_speak_one_agent` and `_stream_pm_narration` now buffer via `asyncio.wait_for`; `TimeoutError` falls back to the scripted template so the run still finishes and produces a verdict instead of stalling indefinitely.  Live path now matches the existing PM-narration buffered pattern (all 12 agents: collect full response → restream via typewriter).
- **Journal**: Extracted `_build_journal_entry()` as a testable module-level function in `room.py`. Failed/aborted runs now write "Room on NVDA — failed · N of 12 agents completed — {error}" instead of "incomplete / no verdict". Replaced the silent `except: pass` with a structured `logger.warning`.
- +3 tests: hanging-gateway timeout fallback, completed-run journal entry, failed-run journal entry.
- Bugs `698a0fe6` + `f7c4d7e0` → `pending_review` on `main`. 6 AT:R20 `pending_review` bugs → `resolved`.

### ami-llm model rebrand (`e79c598`)

The on-prem vLLM host now serves under the model name `ami-llm` (same hardware — Gemma 4 31B, NVFP4 quantised). Updated everywhere: `backend/app/core/config.py`, `docker-compose.yml`, `infra/alpha.env`, `.env.example`, `infra/alpha.env.example`, `infra/systemd/ami-trade.env.example`, 8 occurrences in `test_llm_gateway.py`, `CLAUDE.md`, `HANDOVER.md`.

vLLM was already pre-configured to serve `ami-llm` as an alias — no server-side changes needed.

### LLM end-to-end test

Fired realistic user questions through 3 agents (Market Analyst, Fundamentals Analyst, Bear Researcher). All returned structured, numerically-grounded responses citing live yfinance fundamentals (NVDA P/E 48.1x, TSLA P/E 399x, net cash). Confirmed the AT:R20 fundamentals injection is working in production.

**Observation:** NVFP4 quantisation produces space-split tokens ("Consol idation", "NV DA"). Not a regression — it's been there since day one. Not blocking alpha but worth watching user feedback.

### Animations — documented and deferred

15 animation slots are already authored in lesson MDX files (all showing `AmiHexPlaceholder`). Two implementation paths discussed (Lottie files vs. custom Flutter `CustomPainter`). Decision deferred. See `memory/project_animations.md`.

### Bug list at handover

| short_id | title | status |
|---|---|---|
| `698a0fe6` | convene report not stored | pending_review (fix live on alpha-2026-05-15-4) |
| `f7c4d7e0` | screenshot (extension of 698a0fe6) | pending_review |
| `eeeb866f` | Room run survives container restart | open — deferred (large) |

DB-wide: `open=1 / pending_review=2 / resolved=16 / wont_fix=1`.

### Carry-overs for AT:R22

1. **T&C + Privacy Policy (A22 part 2)** — didn't start this session. Research is in `docs/09_compliance/legal_plan_ami_trade.md`. Needs (a) hosting at `agenticmarketintel.ai/legal/{privacy,terms}` and (b) lawyer review before App Store submission.
2. **Flip `698a0fe6` + `f7c4d7e0` → resolved** after on-device validation of the room timeout fix.
3. **`eeeb866f`** — room run survives container restart — still open/deferred (Redis-backed runner state or separate worker).
4. **External TestFlight launch** — Beta App Description + ~24h Apple review on first external build.
5. **Animation production** — deferred. See `memory/project_animations.md` for 15-slot design decision.
6. **A29 light-mode refactor** — 37 hardcoded `AmiColors.slate900`/`slate800` references. v1.0 work.
7. **Live fundamentals ticker extraction robustness** — watch bug reports for regex misfires in 1-on-1.
8. **Two sibling worktrees with unmerged docs** — `blissful-darwin-419097` (`docs(feedback): bug reporting pipeline spec + D-057 decision entry`) and `exciting-shtern-aad051` (`design(lessons): spec lessons landing page hex-cluster redesign`) — commits not in main. Need Saiful decision: merge to main or discard.

---

## How to start the next session

```
/start-fresh
```

The slash command reads HANDOVER.md + project plan, runs the Mac-side sanity-check curls, queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R22** (this is handover #21).

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
