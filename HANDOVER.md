# Handover — AMI Trade build session

**Last updated:** 2026-05-19 (end of AT:R25 — Auth Phase 1 + Phase 1.5 + Alpha promote. Backend now enforces route-level auth via a `get_current_user` dependency (HMAC-signed `scaffold:<hex>:<sig>` Bearer tokens); routers carry ownership checks against the bearer-identified user. An adversarial audit ([docs/08_tech/auth_phase1_adversarial_audit.md](docs/08_tech/auth_phase1_adversarial_audit.md)) caught 9 deploy-blocking issues the self-audit missed — Phase 1.5 closed all of them: env=dev lockdown (legacy tokens, debug code, Apple verifier all gated to env=local only); `/v1/auth/anon` is no longer a token-minting oracle (mints fresh unless caller's Bearer matches the supplied device_user_id); magic-link routes require auth and bind the claim to `current_user.id` (body `user_id` field dropped); `/v1/auth/apple` returns 503 outside local until Phase 3 verification work lands; `/v1/lessons/activations/grant` removed; body/object ownership on every room, coach, 1-on-1 route. Flutter: Dio interceptor auto-attaches Bearer; `_AuthGate` splash waits for bootstrap so feature providers never fire pre-auth; SSE handshake now sends Bearer via a `_sseRequest` helper (was bypassing Dio); `DeviceUser` persists the bearer token to SharedPreferences and replays it on cold start so A2 doesn't orphan users on every launch. Deployed as `alpha-2026-05-19-2` after the first promote (`alpha-2026-05-19-1`, deleted) exposed a compose gap — `docker-compose.yml` was reading `${AMI_ENV:-local}` but had no `SECRET_KEY` mapping, so the lockdowns were inert; fixed in `12a5da8`. melehost env file now carries `AMI_ENV=staging` + `SECRET_KEY=<64-hex>`; all five lockdown curls verified live (401 unauth, 401 legacy, 503 apple, 405 grant, mint-fresh anon). 6 commits, **306 backend tests passing**, TestFlight `0.1.0+16` shipped + Internal-Testing smoke verified before promote.)

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **206 commits**, no remote yet |
| Latest commit | `12a5da8` — fix(compose): wire SECRET_KEY env var into api-alpha container |
| Alpha tags | `alpha-2026-05-13-{1..8}` + `alpha-2026-05-14-{1..9}` + `alpha-2026-05-15-{1..4}` + `alpha-2026-05-16-1` + `alpha-2026-05-17-{1..5}` + `alpha-2026-05-19-2` (latest `alpha-2026-05-19-2` — Phase 1.5 promote. `-1` was deleted after the compose-secret gap was caught.) |
| Backend tests | **306 passed, 0 failed** (was 275; +31 this session: `test_auth_dependency.py` covers `get_current_user`/`parse_scaffold_token` happy paths + 401/403, `test_auth_phase1_5_audit_fixes.py` covers each adversarial-audit finding) |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **312 i18n keys** (EN canonical; unchanged this session) |

```
$ git log --oneline | head -10
12a5da8 fix(compose): wire SECRET_KEY env var into api-alpha container
181cbd1 docs(silent_scout): reframe README — workspace is broader than the LoRA track
3d3c702 docs(silent_scout): Android test device selection — A16 5G for KSA Android dev rig
13140af chore(mobile): bump build 0.1.0+15 → 0.1.0+16 for TestFlight
48eb0d6 feat(auth): Phase 1 + 1.5 — route guards, HMAC tokens, audit fixes
4276487 docs(auth): Phase 1 self-audit + adversarial review
d97187b handover: wrap AT:R24 — 199 commits, 275 tests, TestFlight +15 live
9c464b7 chore(mobile): bump build 0.1.0+14 → 0.1.0+15 for TestFlight
bf2c83c chore(legal,website): canonical domain is agenticmarketintel.ai, not .com
764a6ea docs(legal): add doc-level versioning to Privacy + ToS
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
| Mac-side tests | `backend/.venv/bin/pytest backend/tests/unit/ -q` — **306 passed** (was 275; AT:R25 added `test_auth_dependency.py` + `test_auth_phase1_5_audit_fixes.py`). Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
| Env knobs (alpha) | `AMI_ENV=staging` + `SECRET_KEY=<64-hex>` in melehost `~/ami_trade/.env` (canonical at `infra/alpha.env` on Mac, gitignored). Without `SECRET_KEY` the backend refuses to start when env != local (boot check in `app/main.py`). |
| Auth | Phase 1.5 enforced: route-level `get_current_user` on `/v1/mandate`, `/v1/journal`, `/v1/watchlist`, `/v1/coach`, `/v1/agents/one_on_one`, `/v1/room`, plus per-route on user-specific `sim` + `lessons`. Bearer format `scaffold:<user_id_hex>:<hmac_sig>` (HMAC-SHA256 with `SECRET_KEY`). Legacy unsigned `scaffold:<hex>` accepted only in env=local. `/v1/auth/anon` mints fresh unless the caller's Bearer matches the supplied `device_user_id`. Magic-link routes require auth and bind to `current_user.id`. `/v1/auth/apple` returns 503 outside env=local (Phase 3 verification not yet shipped). |
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
| pubspec version | **`0.1.0+16`** (repo) — Phase 1 + 1.5 auth client. |
| TESTING IPHONE 13 install | release build of `+16` sideloaded via `scripts/install_iphone.sh` for the pre-promote smoke; same build path as the TestFlight upload. |
| TestFlight | **`0.1.0+16` is live on Internal Testing as of 2026-05-19.** Carries the Dio bearer interceptor, `_AuthGate` splash, `DeviceUser` token persistence, SSE auth helper, and the magic-link request shape change (no more body `user_id`). Smoke-tested on TESTING IPHONE 13 against the post-promote Alpha backend; Floor/Portfolio/Journal/Lessons load, Room SSE streams and writes a verdict to journal, 1-on-1 + Coach SSE both stream. No External Beta artefact yet — see carry-over. |
| Build commands | `scripts/install_iphone.sh` (dev sideload — now uses `flutter devices --machine` so it doesn't print iPhone 17 LAN-probe noise), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **First-time walkthrough (AT:R23):** per-section coach-mark tours fire automatically on first visit to each tab — Floor opens with an intro bottom sheet ("Take the tour / Skip for now"), then 5 spotlight steps narrating Concierge → analyst team → locked agents → daily challenge → Convene; Portfolio / Journal / Lessons each fire 3 steps. Convene step exposes a "Try it now →" CTA that closes the tour and opens the Convene sheet. Each section flag (`tour_{floor,portfolio,journal,lessons}_seen`) is in SharedPreferences; Settings → WALKTHROUGH → "Restart app tour" clears all four. **AT:R25 auth gate:** a brand-new `_AuthGate` splash blocks the home (Onboarding or HomeShell) until `AuthNotifier.bootstrap()` has populated `state.token`; without this, feature providers could fire API calls before the Dio interceptor had a Bearer. Journal filter chips: `ALL · ROOM · TRADE · 1-ON-1 · COACH · LESSONS · UNLOCKS` (ROOM + TRADE at positions 2/3). Journal has soft-delete with UNDO + 30-day Trash view + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green "✓ BUY 1 TSLA @ $X" pill once a sim_trade exists with `verdict_ref == runId`. Trade ticket sheet: live quote chip under the ticker field with `LIVE`/`MOCK` source pill + auto-suggested TP/SL at -6%/+13% of price; non-blocking "NO AI VERDICT" advisory at top when no verdict was convened. Ticker tape below bottom nav (Yahoo Finance, refreshes when watchlist changes). Settings → APPEARANCE is dark-only. Settings → COMPLIANCE labels are tappable. Bug-report sheet (long-press app-version chip) supports photo attachments, offers a `feature_request` category, and now scrolls correctly when the keyboard is open.

---

## What just landed (this session — AT:R25)

Single-track session: build, audit, and promote real authentication. 6 commits. Backend promoted to Alpha as `alpha-2026-05-19-2`, TestFlight `+16` shipped. Two audit docs written. Working tree clean throughout.

### Track A — Phase 1 (route guards + HMAC scaffold tokens)

`4276487` (docs) + `48eb0d6` (code) land the foundation. The dependency `app/api/dependencies.py::get_current_user` extracts a `Bearer` token from `Authorization`, hands it to `parse_scaffold_token()`, and returns the live `User` row (or raises 401). Token format moves from the legacy unsigned `scaffold:<hex>` to HMAC-signed `scaffold:<hex>:<sig>` (`_scaffold_token` in `auth_service.py`, signature is HMAC-SHA256 over `user_id.hex` with `SECRET_KEY`). The legacy form is still accepted but only when `env=local` — so a developer running the Mac unit tests offline doesn't have to set a key.

Routers swept: `mandate`, `journal`, `watchlist`, `coach`, `one_on_one`, `room` get a router-level `dependencies=[Depends(get_current_user)]`. `sim` + `lessons` mix public and user-specific routes, so the dependency is per-route. Every route that takes `user_id` in the path also asserts `current_user.id == user_id` and raises 403 on mismatch — `mandate.py`, `journal.py`, `watchlist.py`, `sim.py`, `lessons.py` use a local `_own(current_user, user_id)` helper for the check. Feedback's `_resolve_user_id` was migrated to call `parse_scaffold_token` (still returns None silently on bad/missing tokens — bug reports stay un-authed by design).

Flutter side of Phase 1: `mobile/lib/services/api/api_client.dart` gains a `_AuthInterceptor` (Dio) that attaches `Authorization: Bearer <token>` on every request once `_bearerToken` is non-null. `AuthNotifier.bootstrap()` + the magic-link verify + Apple sign-in handlers each call `api.setToken(r.token)` after they receive a fresh token.

12 unit tests in `backend/tests/unit/test_auth_dependency.py` cover `parse_scaffold_token` happy paths, forgery rejection, malformed input, and 401/403/200 on the mandate routes. 287 backend tests pass at end of this track.

### Track B — Adversarial audit + Phase 1.5 corrective work

`4276487` also lands the second audit doc: [docs/08_tech/auth_phase1_adversarial_audit.md](docs/08_tech/auth_phase1_adversarial_audit.md), produced by an external review of Phase 1. The reviewer caught 9 deploy-blocking issues the self-audit either missed or characterised as "accept for alpha" when they were actual bypasses of the new security layer. Same `48eb0d6` commit landed the fixes — they were intentionally bundled because Phase 1 alone was not promotable.

Findings closed:

- **A1.** `env=dev` accepted the legacy unsigned format AND returned the magic-link debug code in response bodies — both reachable via melehost's public Cloudflare Tunnel. Tightened: `parse_scaffold_token` accepts legacy only in `env=local`, `_is_dev_env()` returns True only in `local`, and `app/main.py` raises `RuntimeError` at boot if `env != local` and `SECRET_KEY` is still the default. A new env value `staging` is now the canonical alpha env (melehost runs as `AMI_ENV=staging`).
- **A2.** `/v1/auth/anon` was a token-minting oracle — POST `{device_user_id: <victim>}` returned a signed token for any UUID. Fixed in `auth_service.py::ensure_anonymous`: a supplied `device_user_id` is honoured only when the caller also presents a Bearer whose parsed `user_id` matches. Otherwise the row is minted fresh, ignoring the body. `api/auth.py::anon_session` parses the optional Bearer with `_user_id_from_token` and passes it through.
- **A3.** Magic-link verify trusted body `user_id`, letting any caller bind a captured email to a victim's row. Fixed: both `magic_link/start` and `magic_link/verify` require `get_current_user`, the `user_id` field was dropped from `MagicLinkStartRequest` and `MagicLinkVerifyRequest`, and the bind always goes to `current_user.id`. Debug code returns only in `env=local`.
- **A4.** `/v1/auth/apple` decoded the JWT without verifying Apple's signature — a forged 3-part JWT with any `sub` worked. Until Phase 3 ships real verification (PyJWT + Apple JWKS), the route returns 503 outside `env=local`.
- **A5.** `/v1/lessons/activations/grant` was completely unauthenticated. Removed (the underlying `lessons_service::grant_activation` stays; founder grants now happen via psql).
- **A6.** Body / object ownership added to `room.py::stream_room` + `get_room` (loads run, checks `run.user_id`), every coach route (`_own_body` for body `user_id`, `_own_session` for routes that load a session), and every 1-on-1 route. `_own_session` is strict — a session with `user_id=None` is rejected.
- **A7.** Flutter bootstrap was lazy (`Future.microtask(n.bootstrap)` fired only when something watched `authNotifierProvider`). Feature providers could call protected routes before the Dio interceptor had a token. Fixed: new `_AuthGate` widget wraps `home` in `app.dart` and watches `authNotifierProvider.token`; renders a splash until non-null. `DeviceUser` was extended to persist both the device_user_id AND the Bearer token to SharedPreferences (`getToken()`, `setIdAndToken()`, `clear()`), so cold starts replay the token and the backend recognises the returning user (otherwise A2 would orphan users on every launch).
- **A8.** SSE methods (`streamCoachMessage`, `streamOneOnOneMessage`, the room stream) used raw `http.Client()` and bypassed the Dio interceptor — they would 401 against the new backend. Fixed: a new `ApiClient::_sseRequest(uri, body)` helper builds an `http.Request` with `Authorization: Bearer $_bearerToken` and throws if the token is missing. All three SSE call sites use it.

15 + 4 new tests in `backend/tests/unit/test_auth_phase1_5_audit_fixes.py` — one per finding plus body-ownership variants for room/coach/1-on-1 routes. 306 backend tests pass total.

Two cleanup pieces also landed in the same commit: removed the dead `ApiClient::grantActivation()` Flutter method (no callers, route gone), and refreshed stale docstrings in `auth.py` + `auth_service.py` that still described the legacy token format.

### Track C — Alpha promote (the two-attempt story)

First promote (`alpha-2026-05-19-1`, tag deleted) tagged at `181cbd1` and rsync'd cleanly. `infra/alpha.env` had been updated locally to add `ENV=staging` + `SECRET_KEY=$(openssl rand -hex 32)`. Backend booted healthy, but `curl /v1/health` returned `"env":"local"` and `docker exec` showed `SECRET_KEY length: 0` — the container wasn't seeing either value. Root cause: `docker-compose.yml` had `ENV: ${AMI_ENV:-local}` (looking for `AMI_ENV`, not `ENV`) and no entry for `SECRET_KEY` at all. So the file shipped via `scp infra/alpha.env melehost:~/ami_trade/.env` was being read by docker-compose but the two new keys were ignored.

`12a5da8` (fix(compose)) added `SECRET_KEY: ${SECRET_KEY:-}` alongside the existing `ENV: ${AMI_ENV:-local}` mapping. `infra/alpha.env` was renamed `ENV=staging` → `AMI_ENV=staging` to match the compose convention. Second promote tagged `alpha-2026-05-19-2` at `12a5da8` ran cleanly:

```
$ curl -s https://api-alpha.agenticmarketintel.ai/v1/health
{"status":"ok","version":"0.1.0","env":"staging"}
```

Live verification of every adversarial-audit lockdown:

| Probe | Expected | Got |
|---|---|---|
| `GET /v1/mandate/<any-uuid>` with no token | 401 | 401 ✓ |
| `Authorization: Bearer scaffold:<hex>` (legacy unsigned) | 401 | 401 ✓ |
| `POST /v1/auth/apple` | 503 | 503 ✓ |
| `POST /v1/lessons/activations/grant` | 404/405 | 405 ✓ |
| `POST /v1/auth/anon` with arbitrary `device_user_id` | fresh UUID | fresh ✓ |

TestFlight `+16` was uploaded and on-device-verified BEFORE the backend promote, per the adversarial audit's recommendation — otherwise `+15` clients (which don't have the eager bootstrap, SSE auth, or token persistence) would have 401'd the moment the new backend went live. Smoke checklist (Floor / Portfolio / Journal / Lessons / Room / 1-on-1 / Coach / Bug report) verified on TESTING IPHONE 13 via `scripts/install_iphone.sh` against the post-promote backend; backend logs show 2 completed TSLA Room runs (~5.4 min each), all 4 journal entry types written (lesson_complete, one_on_one, room_run, sim_trade) in the smoke window.

Saiful's `325e0747` bug report ("check if the room is working async") was filed mid-smoke and resolved with the backend-evidence trail — async IS working; the room just legitimately takes ~5–6 min because 12 agents stream sequentially through on-prem vLLM.

### Operational footnotes worth surfacing

- `eeeb866f` (room run survives container restart) got a deferred-pre-beta note appended to `bug_reports.steps` early in the session: trigger = External Beta launch OR Cloud Run migration whichever first; Tier 1 (Celery+Redis full retry) is ~3–4 days, Tier 2 (+ LangGraph checkpoint resumption) is ~10–12 days.
- A residual L-1 finding the self-audit flagged but Phase 1.5 did NOT close: `OneOnOneStartRequest.user_id` is `UUID | None`. Sending null bypasses the FLOOR_PASS gate (`_own_body` no-ops on None). Limited damage — the resulting session has `user_id=None` and `_own_session` rejects it on subsequent calls — but worth tightening if 1-on-1 abuse becomes a concern.
- `http_audit` middleware (`backend/app/middleware/http_audit.py`) captures full request/response bodies, which means **every issued bearer token sits in `http_audit` rows** alongside magic-link codes and Apple JWTs. Adversarial audit flagged this as B4 (must-fix before External Beta); deferred this session.
- The Phase 1.5 work is on `main` and the worktree `claude/cranky-leavitt-99418b` was left untouched. The branch isolation pattern from earlier sessions was sidestepped because every `Read`/`Edit` used absolute paths to the main checkout. Not a bug for this session (promote rsyncs from CWD, which was main), but a pattern to either embrace or fix next session.

### Carry-overs for AT:R26

Counts audited against tree state at end of AT:R25.

1. **iPhone smoke against post-promote backend** — Saiful did the full checklist via the sideloaded build before promote. The TestFlight `+16` build is the same code; if any tester reinstalls `+16` after the promote and sees an unexpected 401, the first place to look is whether their feature provider somehow fires before `_AuthGate` lets the home render.
2. **`11fde6f6` floor hex agent style — re-open from AT:R24.** No movement this session.
3. **`eeeb866f` — room run survives container restart — open, deferred-pre-beta.** Note + estimate now in `bug_reports.steps`.
4. **`6fd4144d` bug-report close button — `pending_review`.** Still on `+15` (which is now superseded by `+16`). Verify on `+16` and flip to resolved.
5. **B-tier adversarial-audit findings (deferred to pre-External-Beta):** rate limiting on `/auth/anon` + LLM-heavy routes; magic-link attempt counter + per-IP throttle; feedback upload size enforced at the proxy + streaming read; `http_audit` middleware scrubbing of tokens + auth-route bodies.
6. **Phase 2 onwards from AT:R25's auth plan**:
   - **Phase 3** federated sign-in for both iOS (Apple) and Android (Google). Both blocked on Saiful setting up the credentials (Apple Dev portal "Sign in with Apple" capability for `ai.agenticmarketintel.amiTrade` under team `S7RBWM4879`; Google Cloud Console OAuth 2.0 client ID with SHA-1 fingerprint for the Android app). Backend endpoints `POST /v1/auth/apple` and `POST /v1/auth/google` need real signature verification (PyJWT + provider JWKS) — `auth_service.py::_decode_apple_sub` is the current scaffold to replace.
   - **Phase 4** sign-out (Flutter clears `_bearerToken` + calls `DeviceUser.clear()`; backend optional `DELETE /v1/auth/session` for completeness). Half a day.
7. **Resend account → `RESEND_API_KEY` in melehost `.env`** — magic-link in prod (A3 in the original PRD backlog).
8. **App Store Connect Privacy URL** — confirm it's set to `https://www.agenticmarketintel.ai/privacy/`. Blocks External Beta submission.
9. **External TestFlight launch** — Beta App Description + ~24h Apple review on first external build. Still no External Beta artefact in the repo.
10. **Animation production** — 15 `<Animation>` MDX tags in `content/lessons/` still render `AmiHexPlaceholder`. Lottie vs CustomPainter decision still open.
11. **A29 light-mode refactor** — v1.0 work.
12. **Two sibling worktrees with unmerged docs** — `claude/blissful-darwin-419097` (bug-pipeline spec + D-057) and `claude/exciting-shtern-aad051` (lessons-landing hex-cluster redesign). Still pending Saiful decision.
13. **Decide what to do with `claude/cranky-leavitt-99418b`** — the AT:R25 worktree is clean (all edits landed on main directly). It can be removed at any time or left as a marker.

### Watch items (not tasks)

- **First-promote-after-Phase-1.5 visibility window.** Existing TestFlight `+15` clients (anyone who hasn't updated to `+16`) WILL 401 against the new backend on any protected route. Only `+16` reliably sends `Authorization: Bearer` on every request. Watch the bug list for "everything broken" / "401" reports from anyone who skipped the update.
- **Apple endpoint 503.** Internal testers tapping the Apple Sign-In button on the sign-in screen will get a 503 (instead of the old scaffold's "happy path" with a forged JWT). Until Phase 3 lands, magic-link is the only working claim path on Alpha.
- **AT:R24's NVFP4 quantisation watch item still applies** — `ami-llm` (Gemma 4 31B NVFP4) occasionally emits space-split tokens. Not blocking.
- **Two `silent_scout` doc commits landed mid-session** (`3d3c702`, `181cbd1`). Saiful authored them; not part of the AMI Trade auth track but they're in the repo + history.

---

## How to start the next session

```
/start-fresh
```

The slash command reads HANDOVER.md + project plan, runs the Mac-side sanity-check curls, queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R26** (this is handover #25).

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
