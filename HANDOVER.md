# Handover — AMI Trade build session

**Last updated:** 2026-05-18 (end of AT:R24 — Bug-fix + legal docs + TestFlight `+15`. Three user-surfaced UX bugs fixed (`6fd4144d` bug-report sheet close `×`, `cb81a6d8` LessonsScreen back arrow when pushed from agent panel, `e2857081` lessons hex cluster proper edge-to-edge tiling). One bug attempted + reverted twice: `11fde6f6` floor hex agent style — initial honeycomb refactor + later style-only tweaks all rejected as ugly. Drafted Privacy Policy + Terms of Service (16 + 14 clauses) as canonical markdown in `docs/09_compliance/`, published as HTML at `agenticmarketintel.ai/{privacy,terms}/`, with doc-level versioning (meta tags + visible header + version-history footer) and a publishing playbook at `docs/09_compliance/VERSIONING.md`. Swept `.com` → `.ai` after discovering the live marketing site is on `.ai`. **199 commits, 275 tests**, pubspec `0.1.0+15` shipped to TestFlight Internal. No Alpha promotion — backend untouched.)

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **199 commits**, no remote yet |
| Latest commit | `9c464b7` — chore(mobile): bump build 0.1.0+14 → 0.1.0+15 for TestFlight |
| Alpha tags | `alpha-2026-05-13-{1..8}` + `alpha-2026-05-14-{1..9}` + `alpha-2026-05-15-{1..4}` + `alpha-2026-05-16-1` + `alpha-2026-05-17-{1..5}` (latest `alpha-2026-05-17-5` — unchanged this session; backend was untouched) |
| Backend tests | **275 passed, 0 failed** (unchanged — no backend code touched this session) |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **312 i18n keys** (EN canonical; unchanged this session) |

```
$ git log --oneline | head -10
9c464b7 chore(mobile): bump build 0.1.0+14 → 0.1.0+15 for TestFlight
bf2c83c chore(legal,website): canonical domain is agenticmarketintel.ai, not .com
764a6ea docs(legal): add doc-level versioning to Privacy + ToS
5761373 feat(website): publish alpha Privacy Policy + ToS at /privacy and /terms
9fbfe6a docs(legal): standalone Privacy Policy + ToS drafts (pending lawyer review)
24d0bc7 Revert "fix(bug:11fde6f6): match floor hex button style to lessons hex"
b070055 Revert "chore(floor): bump agent hex size 72→96 for more visual weight"
8fceb32 Revert "fix(floor): un-dim agent hexes — drop translucent border + use locked status"
902b5ff fix(floor): un-dim agent hexes — drop translucent border + use locked status
569ad06 chore(floor): bump agent hex size 72→96 for more visual weight
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
| pubspec version | **`0.1.0+15`** (repo) — pushed to TestFlight Internal this session. |
| TESTING IPHONE 13 install | release build of HEAD (`9c464b7`) sideloaded via `scripts/install_iphone.sh` (repeatedly through the session as bugs were fixed). Same code path as the TestFlight build. |
| TestFlight | **`0.1.0+15` is live on Internal Testing as of 2026-05-18.** Ships the AT:R23 walkthrough + the three AT:R24 bug fixes (`6fd4144d`, `cb81a6d8`, `e2857081`). No External Beta artefact yet — see carry-over. |
| Build commands | `scripts/install_iphone.sh` (dev sideload — now uses `flutter devices --machine` so it doesn't print iPhone 17 LAN-probe noise), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **First-time walkthrough (AT:R23):** per-section coach-mark tours fire automatically on first visit to each tab — Floor opens with an intro bottom sheet ("Take the tour / Skip for now"), then 5 spotlight steps narrating Concierge → analyst team → locked agents → daily challenge → Convene; Portfolio / Journal / Lessons each fire 3 steps. Convene step exposes a "Try it now →" CTA that closes the tour and opens the Convene sheet. Each section flag (`tour_{floor,portfolio,journal,lessons}_seen`) is in SharedPreferences; Settings → WALKTHROUGH → "Restart app tour" clears all four. Journal filter chips: `ALL · ROOM · TRADE · 1-ON-1 · COACH · LESSONS · UNLOCKS` (ROOM + TRADE at positions 2/3). Journal has soft-delete with UNDO + 30-day Trash view + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green "✓ BUY 1 TSLA @ $X" pill once a sim_trade exists with `verdict_ref == runId`. Trade ticket sheet: live quote chip under the ticker field with `LIVE`/`MOCK` source pill + auto-suggested TP/SL at -6%/+13% of price; non-blocking "NO AI VERDICT" advisory at top when no verdict was convened. Ticker tape below bottom nav (Yahoo Finance, refreshes when watchlist changes). Settings → APPEARANCE is dark-only. Settings → COMPLIANCE labels are tappable. Bug-report sheet (long-press app-version chip) supports photo attachments, offers a `feature_request` category, and now scrolls correctly when the keyboard is open.

---

## What just landed (this session — AT:R24)

Three-track session: (a) clear the bug queue from AT:R23's walkthrough release, (b) draft + publish the alpha-stage Privacy Policy and Terms of Service, (c) push `0.1.0+15` to TestFlight Internal. 19 commits. Backend untouched (no `/promote-to-alpha`).

### Track A — Bug queue: 3 fixed, 1 attempted-and-reverted

Used `/start-fresh` → bug list → `/fix-bugs` worktree (`.claude/worktrees/bug-fix-20260517-225716`, since cleaned up). All claimed atomically against melehost `bug_reports.assigned_branch`. Two of three saw both `pending_review` → `resolved` flips after Saiful verified on-device; the third is still `pending_review`.

**`af01328` — fix(bug:6fd4144d): add explicit close button to bug report sheet.** The sheet had only a swipe-down dismiss; added a `×` icon in the header row next to "Report a bug". File: `mobile/lib/screens/feedback/bug_report_sheet.dart`. **Status: pending_review** (committed + on-device + on TestFlight, awaiting Saiful's flip to resolved).

**`75ba23a` (amended) — fix(bug:cb81a6d8,e2857081): lessons screen back nav + hex cluster layout.** Two fixes in one file:

- `cb81a6d8` — `LessonsScreen._Header` now accepts a `showBack` parameter and renders an arrow when `Navigator.of(context).canPop()` is true. Fixes the no-exit trap when reached from the locked-agent "Go to Lessons" button (which pushes the screen standalone, outside the HomeShell IndexedStack where the bottom nav lives). **Status: resolved.**
- `e2857081` — `_HexCluster` geometry rewritten in `a51a75b`: 1+6 clock arrangement (N/NE/SE/S/SW/NW around centre) where every surrounding hex shares a full edge with the centre. Replaces the prior 3-cols × 2-rows grid that had FA/SB as same-row neighbours of FON — and for flat-top hexes, same-row means single-vertex contact only ("points meeting points" per Saiful). `hexW = maxWidth × 2/5` so the cluster fills available width; cluster bounding box is 2.5*hexW × 3*hexH (≈ 358×372 on iPhone 13 vs the prior 358×207 — plus no overlap). **Status: resolved.**

**`11fde6f6` — floor hex agent style — attempted, reverted, re-attempted, re-reverted.** Pattern worth noting for future sessions: Saiful's bug report said "the design used in 'floor' for the hex agents should be similar to the design used in the lessons hex." First interpretation went big (`497a2a1`: full edge-to-edge 4×3 staggered honeycomb of `HexAvatar`s, captions stripped, lock state moved to `HexAvatarStatus.locked`). Rejected: *"oh no. that was ugly. revert it."* Reverted in `52748ce`. Second interpretation, clarified by Saiful: only the BUTTON COLOUR matched. Added a `solid: false` flag to `HexAvatar` that mirrors `TrackHexButton`'s translucent fill (`color × 0.15` alpha + role-colour label, no border in the variant). Iterated through size bumps and border removal across three commits (`9a1c93d`, `569ad06`, `902b5ff`). All three reverted by user request: *"I am too tired to evaluate right now."* Bug **flipped back to open** for a future session. The `<adj>-<noun>-<hex>` worktree pattern + atomic `bug_reports` claim held throughout — no leaked state.

DB at end of session: `open=2 / pending_review=1 / resolved=26 / wont_fix=2`. The 2 open are `11fde6f6` (re-deferred above) and `eeeb866f` (room-restart, large, Beta-window).

### Track B — Privacy Policy + Terms of Service drafted, published, versioned

Picked up A22 part 2 from the carry-over list. Three commits.

**`9fbfe6a` — `docs/09_compliance/{privacy_policy,terms_of_service}.md`.** Assembled the clause-by-clause starter language from `legal_plan_ami_trade.md` into two standalone DRAFT documents lawyer review can act on (16 Privacy clauses + 14 ToS clauses + 2 placeholder subsections). Each clause keeps its "Inspired by" peer-source footnote inline so the lawyer can spot-check. Five lawyer-only items called out explicitly: ToS §2 (not investment advice), §11 (liability cap), §13 (governing law), §13.1 (arbitration), §15 (indemnity). ToS ends with a "Lawyer-only checklist" table.

**`5761373` — alpha HTML published at `/privacy/` and `/terms/`.** `website/privacy/index.html` and `website/terms/index.html`. URL convention chosen as directory layout (`/privacy/index.html`) so Apache serves them at clean URLs matching the existing `index.html` footer's `/privacy` and `/terms` links. Style: imports the existing `assets/css/site.css` tokens, with inline page-specific CSS in each file (one-off rather than a shared `legal.css` since only 2 pages). Alpha-stage adjustments vs the markdown drafts: "Inspired by" footnotes stripped, "DRAFT — pending lawyer review" softened to an amber "Alpha disclosure" callout, ToS §13 filled in with Malaysian law + non-exclusive jurisdiction + mandatory-consumer-rights carve-out (preliminary; lawyer adjusts at incorporation), §13.1 arbitration + §15 indemnity dropped for alpha. `sitemap.xml` updated with both URLs.

**`764a6ea` — doc-level versioning + publishing playbook (`docs/09_compliance/VERSIONING.md`).** Three layers identified: doc-level (this commit), URL-level (kicks in when v2 ships), app-level acceptance tracking (Beta+ work). Doc-level shipped: `<meta name="document-version">`, `<meta name="document-effective-date">`, `<meta name="document-status">` on each HTML; visible "Alpha · Version 1.0 · Effective 18 May 2026" in header; "Version history" `<section>` at the bottom (one entry now). Markdown sources synced with same Version + Effective + Published-HTML metadata. VERSIONING.md documents semver convention (major = material → 14-day notice; minor = clarification; patch = typos), material-vs-non-material gate (5 questions), step-by-step publish checklist (edit MD → mirror HTML → archive previous → bump meta → update sitemap → commit → FTP deploy → smoke-check), URL convention (canonical = self for archived versions, canonical = `/privacy/` for current), and a "What NEVER happens" footer.

**`bf2c83c` — sweep `.com` → `.ai`.** Saiful uploaded the HTMLs, then I curl-checked and discovered `agenticmarketintel.com` doesn't resolve — the live marketing site is on `.ai`. Saiful confirmed via AskUserQuestion: "`.ai` is canonical". Perl-replaced URL refs across 10 files (`docs/09_compliance/*`, `website/{WEBSITE.md, deploy_ftp.py, sitemap.xml, index.html, privacy/index.html, terms/index.html}`). Preserved untouched: the two `hello@agenticmarketintel.com` email refs in `index.html` (lines 701, 767) — email hosting is a separate concern. Saiful re-uploaded; URLs verified live at `https://www.agenticmarketintel.ai/{privacy,terms}/`.

### Track C — TestFlight `+15`

**`9c464b7` — pubspec bump 0.1.0+14 → +15.** `scripts/build_testflight.sh` ran cleanly: release build, signed with the same Distribution cert, uploaded via `altool`. Saiful confirms `+15` is live on TestFlight Internal. Ships the AT:R23 walkthrough (`+14` had it) + the three AT:R24 bug fixes above. No External Beta artefact yet (still a carry-over). App Store Connect → App Information → Privacy Policy URL should be set to `https://www.agenticmarketintel.ai/privacy/` per Saiful's confirmed canonical-domain answer.

### Carry-overs for AT:R25

Counts audited against tree state at end of AT:R24.

1. **`11fde6f6` floor hex agent style — re-open.** All this-session attempts reverted. Saiful's note before stopping: clarified that it was only the BUTTON COLOUR style he wanted to match (the lessons hex's translucent fill + colored text, not the cluster layout). Next session should try a fresh approach with that constraint clearer — possibly involving a `solid: false` variant of `HexAvatar` similar to what `902b5ff` shipped, but only after a design-only review (no commit-and-rebuild loops). All commit history is on main (in the revert pairs) if helpful.
2. **`eeeb866f` — room run survives container restart — still open/deferred (large).** Clean upgrade path (Celery + Redis broker; per-user FIFO) sketched in `docs/external/async_job_server_design_prompt.md`. Beta-window work.
3. **`6fd4144d` bug-report close button — `pending_review`.** Committed in `af01328`, on iPhone, on TestFlight. Saiful to flip to `resolved` once verified.
4. **Lawyer review of Privacy + ToS.** The published HTML at `agenticmarketintel.ai/{privacy,terms}/` is the alpha-stage version (clearly disclosed in amber banner). The canonical markdown at `docs/09_compliance/{privacy_policy,terms_of_service}.md` keeps the lawyer-only placeholders and "Inspired by" footnotes for review. Five clauses are jurisdiction-sensitive — see ToS' "Lawyer-only checklist" table at the bottom.
5. **App-side acceptance tracking** (the "version 14-day notice + re-accept" Beta+ work). Spec in `docs/09_compliance/VERSIONING.md` under "App-side acceptance tracking (Beta+ work)". Needs a `policy_acceptances` table + backend comparison logic + Flutter banner. Beta scope.
6. **App Store Connect Privacy Policy URL** — confirm in App Store Connect that it's set to `https://www.agenticmarketintel.ai/privacy/`. Critical before External Beta submission. Probably already correct from prior sessions but worth a glance.
7. **External TestFlight launch** — Beta App Description + ~24h Apple review on first external build. `scripts/build_testflight.sh` uploads to Internal only by default; no External Beta artefact in the repo yet.
8. **Animation production** — 15 `<Animation>` MDX tags in `content/lessons/`. All render `AmiHexPlaceholder`. See `memory/project_animations.md` for the Lottie vs CustomPainter decision.
9. **A29 light-mode refactor** — 125+ hardcoded `AmiColors.slate900`/`slate800` references across `mobile/lib/`. v1.0 work.
10. **Two sibling worktrees with unmerged docs** — `claude/blissful-darwin-419097` (one commit `f94ad0e` — bug-pipeline spec + D-057) and `claude/exciting-shtern-aad051` (one commit `ead7038` — lessons-landing hex-cluster redesign). Still pending Saiful decision: merge to main or discard. The hex-cluster redesign is especially worth a look now that `a51a75b` has changed how the lessons cluster is laid out — they may conflict or one may obsolete the other.

### Watch items (not tasks)

- **Domain mismatch hygiene.** The `.com` references in `index.html` for emails (`hello@agenticmarketintel.com` on lines 701 + 767) were deliberately preserved — email hosting is independent of web hosting. If Saiful's actual support email is on `.ai` now (the new legal docs use `privacy@.ai` and `legal@.ai`), those `hello@.com` refs become stale. Worth confirming his email setup and unifying.
- **Testers on `+15`** are the first to see the bug-fix release. Three things to watch for in new bug reports: (a) anyone failing to find the new `×` close on the bug-report sheet (unlikely but possible if iconography reads wrong at smaller screen sizes); (b) the back arrow on `LessonsScreen` showing in unexpected contexts (it triggers on `canPop()` — fine on the agent-panel push, but verify it doesn't appear inside the main HomeShell where it'd just close the tab); (c) the new lessons hex cluster size (3*hexH tall) crowding any tour overlay positioning that AT:R23 set up for the smaller 2*hexH cluster.
- **NVFP4 quantisation produces space-split tokens** — observed since day one. Not blocking alpha.

---

## How to start the next session

```
/start-fresh
```

The slash command reads HANDOVER.md + project plan, runs the Mac-side sanity-check curls, queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R25** (this is handover #24).

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
