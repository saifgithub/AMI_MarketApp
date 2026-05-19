# Handover — AMI Trade build session

**Last updated:** 2026-05-19 (end of AT:R26 — closed three carry-overs in one promote. Bug:a84361f6 (Apple sign-in 503 glitch) fixed in the Flutter `api_client.dart` — DioException with 503 now throws a readable "Apple sign-in isn't live in Alpha yet" message; sign-in screen surfaces it via the snackbar (stripping the `Exception: ` prefix) and a caption under the Apple button sets expectations before the tap. **B4 closed**: `http_audit` middleware scrubs request + response bodies for `/v1/auth/{anon,magic_link/start,magic_link/verify,apple,session}` — bearer tokens, magic-link codes, and Apple JWTs no longer sit in audit rows. **Phase 4 sign-out shipped**: `DELETE /v1/auth/session` (stateless 200, hooks future blocklist); Flutter `AuthNotifier.signOut()` clears the Dio token, wipes SharedPreferences via `DeviceUser.clear()`, resets state, and calls `bootstrap()` so `_AuthGate` re-mints a fresh anon session without hanging. Red "Sign out" button in Settings → Account, visible only when `!user.isAnonymous`. **SMTP magic-link email wired** via stdlib `smtplib` (no new dep): `email_service.send_magic_link()` is a no-op when `SMTP_HOST=""` (alpha debug-code fallback preserved) and never raises on send failure. Saiful added 5 SMTP keys to `infra/alpha.env` pointing at `mail.agenticmarketintel.ai:465` SSL — DNS still NXDOMAIN at session-end (Cloudflare gray-cloud A record visible in dashboard but not surfacing on lou/rihana NS), so real email delivery is still gated on that resolving. Deployed as `alpha-2026-05-19-3` at `07f0974`; TestFlight `0.1.0+17` uploaded. 6 commits this session (incl. merge + a Silent_Scout `07_voice/` research dir from Saiful). **318 backend tests passing** (+12 new: `test_http_audit_scrub.py` + `test_email_service.py`).)

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **215 commits**, no remote yet |
| Latest commit | `e04604b` — chore(mobile): bump build 0.1.0+16 → 0.1.0+17 for TestFlight |
| Alpha tags | `alpha-2026-05-13-{1..8}` + `alpha-2026-05-14-{1..9}` + `alpha-2026-05-15-{1..4}` + `alpha-2026-05-16-1` + `alpha-2026-05-17-{1..5}` + `alpha-2026-05-19-{2,3}` (latest `alpha-2026-05-19-3` — http_audit B4 scrub + Phase 4 sign-out + SMTP wiring) |
| Backend tests | **318 passed, 0 failed** (was 306; +12 this session: `test_http_audit_scrub.py` covers SCRUB_PATHS produce `[REDACTED]` bodies for auth routes; `test_email_service.py` covers SMTP_SSL on 465, STARTTLS on 587, no-op when host empty, no-raise on send failure, plus the sign-out endpoint 200/401 check) |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **312 i18n keys** (EN canonical; unchanged this session) |

```
$ git log --oneline | head -10
e04604b chore(mobile): bump build 0.1.0+16 → 0.1.0+17 for TestFlight
07f0974 docs(silent_scout): add 07_voice/ — on-device STT+TTS research track
c2ae379 feat(auth): Phase 4 sign-out — Flutter client clears token + re-bootstraps
f7b6214 feat(auth): http_audit scrubbing (B4) + sign-out endpoint + SMTP email
4edd0a1 Merge branch 'claude/bug-fix-20260519-140401' — fix(bug:a84361f6): Apple sign-in 503 glitch
cd4a3f2 fix(bug:a84361f6): Apple sign-in 503 glitch — friendly message + visual hint
4121eed docs(handover): sync HANDOVER table with post-wrap deviation-fix commits
9012e35 docs(promote): surface AMI_ENV + SECRET_KEY in alpha.env.example + preflight
c8b2bf0 handover: wrap AT:R25 — Phase 1 + 1.5 auth + Alpha promote
12a5da8 fix(compose): wire SECRET_KEY env var into api-alpha container
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
| Routes | `/v1/health`, `/v1/auth/*` (incl. `DELETE /v1/auth/session` — Phase 4 sign-out, AT:R26), `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/coach/*`, `/v1/journal/*` (incl. `/trash`, `/{id}/restore`), `/v1/lessons/*`, `/v1/llm/status`, `/v1/mandate/*`, `/v1/room/*`, `/v1/sim/*`, `/v1/watchlist/*`, `/v1/feedback/bug` (`multipart/form-data` with optional `file`) |
| Mac-side tests | `backend/.venv/bin/pytest backend/tests/unit/ -q` — **318 passed** (was 306; AT:R26 added `test_http_audit_scrub.py` + `test_email_service.py`). Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
| Env knobs (alpha) | `AMI_ENV=staging` + `SECRET_KEY=<64-hex>` + `SMTP_{HOST,PORT,USER,PASSWORD,FROM}` (the 5 SMTP vars added in AT:R26 for magic-link delivery). Canonical at `infra/alpha.env` on Mac, gitignored; shipped via `scp` in `/promote-to-alpha` step 4. Without `SECRET_KEY` the backend refuses to start when env != local (boot check in `app/main.py`). |
| Auth | Phase 1.5 + Phase 4 enforced: route-level `get_current_user` on `/v1/mandate`, `/v1/journal`, `/v1/watchlist`, `/v1/coach`, `/v1/agents/one_on_one`, `/v1/room`, plus per-route on user-specific `sim` + `lessons`. Bearer format `scaffold:<user_id_hex>:<hmac_sig>` (HMAC-SHA256 with `SECRET_KEY`). Legacy unsigned `scaffold:<hex>` accepted only in env=local. `/v1/auth/anon` mints fresh unless the caller's Bearer matches the supplied `device_user_id`. Magic-link routes require auth and bind to `current_user.id`; the start route now triggers `email_service.send_magic_link()` (SMTP via stdlib `smtplib`; no-op when `SMTP_HOST=""`). `/v1/auth/apple` returns 503 outside env=local (Phase 3 verification not yet shipped). `DELETE /v1/auth/session` (Phase 4) requires auth and returns `{"signed_out": true}` — stateless no-op now; hooks future token blocklist. `http_audit` middleware now scrubs request + response bodies for all `/v1/auth/*` routes (AT:R26 B4 close). |
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
| pubspec version | **`0.1.0+17`** (repo) — AT:R26 closes: Apple sign-in 503 graceful UX, Phase 4 sign-out button (Settings → Account, red OutlinedButton). |
| TESTING IPHONE 13 install | `+16` is the last sideloaded build (AT:R25); `+17` ships via TestFlight only. Use `scripts/install_iphone.sh` to install the dev build of `+17` if you want to test before App Store Connect finishes processing. |
| TestFlight | **`0.1.0+17` uploaded 2026-05-19 — processing.** Adds Apple-glitch fix (a84361f6) + Phase 4 sign-out + bug-report close button verification surface. `+16` was the last Phase 1.5 build. No External Beta artefact yet — see carry-over. |
| Build commands | `scripts/install_iphone.sh` (dev sideload — now uses `flutter devices --machine` so it doesn't print iPhone 17 LAN-probe noise), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **First-time walkthrough (AT:R23):** per-section coach-mark tours fire automatically on first visit to each tab — Floor opens with an intro bottom sheet ("Take the tour / Skip for now"), then 5 spotlight steps narrating Concierge → analyst team → locked agents → daily challenge → Convene; Portfolio / Journal / Lessons each fire 3 steps. Convene step exposes a "Try it now →" CTA that closes the tour and opens the Convene sheet. Each section flag (`tour_{floor,portfolio,journal,lessons}_seen`) is in SharedPreferences; Settings → WALKTHROUGH → "Restart app tour" clears all four. **AT:R25 auth gate:** a brand-new `_AuthGate` splash blocks the home (Onboarding or HomeShell) until `AuthNotifier.bootstrap()` has populated `state.token`; without this, feature providers could fire API calls before the Dio interceptor had a Bearer. **AT:R26 sign-out (Phase 4):** Settings → Account now shows a red "Sign out" OutlinedButton when the user is non-anonymous; tap calls `AuthNotifier.signOut()` which fires `DELETE /v1/auth/session`, wipes `DeviceUser` (SharedPreferences), resets `AuthState`, and re-runs `bootstrap()` so a fresh anonymous session is minted before `_AuthGate` releases the home. **AT:R26 Apple-glitch fix:** the sign-in screen now shows a "Coming in v1.0 — use email sign-in for now" caption under the Apple button; if the user taps it anyway, the 503 from the backend is caught in `api_client.dart::signInWithApple` and surfaced via a snackbar as a readable "Apple sign-in isn't live in Alpha yet — use email sign-in instead." (Exception prefix stripped). Journal filter chips: `ALL · ROOM · TRADE · 1-ON-1 · COACH · LESSONS · UNLOCKS` (ROOM + TRADE at positions 2/3). Journal has soft-delete with UNDO + 30-day Trash view + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green "✓ BUY 1 TSLA @ $X" pill once a sim_trade exists with `verdict_ref == runId`. Trade ticket sheet: live quote chip under the ticker field with `LIVE`/`MOCK` source pill + auto-suggested TP/SL at -6%/+13% of price; non-blocking "NO AI VERDICT" advisory at top when no verdict was convened. Ticker tape below bottom nav (Yahoo Finance, refreshes when watchlist changes). Settings → APPEARANCE is dark-only. Settings → COMPLIANCE labels are tappable. Bug-report sheet (long-press app-version chip) supports photo attachments, offers a `feature_request` category, and now scrolls correctly when the keyboard is open.

---

## What just landed (this session — AT:R26)

Closed three of the AT:R25 carry-overs in a single promote + TestFlight cycle: bug:a84361f6 (Apple-glitch UX), B4 (http_audit token leakage), and Phase 4 (sign-out). Also wired SMTP for real magic-link emails (delivery still gated on DNS resolution). 6 commits incl. one merge + a Silent_Scout `07_voice/` research dir Saiful authored mid-session. Backend promoted as `alpha-2026-05-19-3`, TestFlight `+17` uploaded.

### Track A — bug:a84361f6 Apple sign-in 503 glitch

Filed 2026-05-19 13:32, same day as the Phase 1.5 promote. The user tapped "Sign in with Apple" and saw a confusing "Apple sign-in failed." toast because the backend now returns 503 on `/v1/auth/apple` outside env=local (per A4) — the UI didn't explain that it was intentional.

Fix on `claude/bug-fix-20260519-140401` (commit `cd4a3f2`, merged via `4edd0a1`):
- `mobile/lib/services/api/api_client.dart::signInWithApple` wraps the Dio call in try/catch. On `DioException` with `response?.statusCode == 503`, throws `Exception("Apple sign-in isn\'t live in Alpha yet — use email sign-in instead.")`. Other status codes rethrow unchanged.
- `mobile/lib/screens/auth/sign_in_screen.dart::_signInWithAppleScaffold` now reads `ref.read(authNotifierProvider).error` after a failed sign-in and strips the leading `"Exception: "` prefix before showing it in the snackbar (falls back to the generic `signInAppleFailed` l10n string if state has no error).
- Same screen: caption added under the `_AppleButton` — *"Coming in v1.0 — use email sign-in for now"* (hardcoded English, AmiTypography.caption, textLow color, centered). Sets expectations before the tap. No l10n key added; this is alpha-only copy.

The bug-fix worktree was created via the `/fix-bugs` skill (atomic claim → commit → DB flip to `pending_review` → merge to main → worktree removed).

### Track B — http_audit scrubbing (adversarial audit B4 closed)

`f7b6214`. `backend/app/middleware/http_audit.py` gets a new `SCRUB_PATHS` set containing `/v1/auth/{anon, magic_link/start, magic_link/verify, apple, session}`. The dispatch loop sets `scrub = path in SCRUB_PATHS` early; when true, both `captured_request` and `captured_response` are forced to `b"[REDACTED]"` before being passed to `record_http`. Method, path, query, status code, latency, and IP are still recorded — only the bodies are scrubbed. No effect on SSE routes (none are in SCRUB_PATHS) or on the request body that downstream handlers see (the scrub is purely about what gets persisted to the audit table).

3 tests in `backend/tests/unit/test_http_audit_scrub.py`:
- Parametrised across all of `SCRUB_PATHS` — each path's request + response bodies must equal `b"[REDACTED]"` in the captured `record_http` call.
- Non-scrub path (`/v1/some/other/route`) — body must NOT be `[REDACTED]`, request body must contain its actual content (`b"AAPL"`).
- `/v1/health` — `record_http` must not be called at all (still in `SKIP_PATHS`).

### Track C — Phase 4 sign-out

`f7b6214` (backend) + `c2ae379` (Flutter).

**Backend** (`backend/app/api/auth.py`): `DELETE /v1/auth/session` — requires `Depends(get_current_user)`, returns `{"signed_out": True}`. No DB writes. The doc comment makes the design explicit: scaffold tokens are stateless HMAC so there is nothing to invalidate server-side now — this endpoint exists as a clean HTTP contract for a future Phase 5+ token blocklist. Auth dependency means it's covered by the existing audit suite — the path was added to `SCRUB_PATHS` in Track B so bearers don't leak via this route either.

**Flutter** (three files):
- `mobile/lib/services/api/api_client.dart::signOut()` — fires `DELETE /v1/auth/session` inside a try/catch (server response is irrelevant; client wipes its token regardless), then sets `_bearerToken = null`.
- `mobile/lib/state/auth_providers.dart::AuthNotifier.signOut()` — calls `api.signOut()`, then `DeviceUser.clear()` (wipes both the device_user_id AND the bearer token from SharedPreferences), resets `state = const AuthState()`, then `await bootstrap()` so a fresh anonymous session is minted before `_AuthGate` releases the splash. Without the final `bootstrap()` call the gate would hang waiting for a non-null token forever.
- `mobile/lib/screens/settings/settings_screen.dart::_AccountSection` — adds a red OutlinedButton labeled "Sign out" below the existing "Manage Account" button. Only visible when `claimed` is true (i.e. `auth.user != null && !auth.user!.isAnonymous`). Disabled while `auth.loading` is true. Uses `AmiColors.hexRed` for foreground + border so it reads as a destructive-tier action.

The route was added to the same SCRUB_PATHS set as the other auth routes (Track B) so the bearer in the inbound request doesn't end up in audit rows.

### Track D — SMTP magic-link email (carry-over #7 wired)

`f7b6214`. New file `backend/app/services/email_service.py` uses stdlib `smtplib` (no new pyproject dependency — `resend>=2.4` is already declared but unused). Single public function `send_magic_link(to, code)` builds a multipart message (plain + minimal dark-mode HTML), then picks the transport:
- `settings.smtp_port == 465` → `smtplib.SMTP_SSL` (implicit TLS)
- otherwise → `smtplib.SMTP` + `starttls()` (works for 587)

Logs `smtp_not_configured_skip_email` and returns when `settings.smtp_host` is empty (alpha debug-code-only mode preserved). Catches any send exception, logs `magic_link_email_failed`, returns — never raises. Magic-link still works in fallback (debug code visible in UI on `env=local`; on staging the code is only visible in the response if you hit the start endpoint directly, never to the client per A1 lockdown).

`backend/app/services/auth_service.py::start_magic_link` adds one line: `_send_magic_link_email(email, code)` after the DB write. `backend/app/core/config.py` adds 5 fields: `smtp_host`, `smtp_port=465`, `smtp_user`, `smtp_password`, `smtp_from` (all empty by default). `infra/alpha.env.example` updated with a commented placeholder block.

5 tests in `backend/tests/unit/test_email_service.py`:
- No-op when `smtp_host=""` (asserts `SMTP_SSL` never called).
- Port 465 → uses `SMTP_SSL`, logs in, sends to recipient with the 6-digit code in the body.
- Port 587 → uses `SMTP` + `starttls()` + login.
- ConnectionRefusedError from `SMTP_SSL` is swallowed (no raise).
- Plus the sign-out endpoint smoke (200 with valid Bearer / 401 without) — same file because it's a small one-off.

`infra/alpha.env` (gitignored, on Mac only) was populated by Saiful with `SMTP_HOST=mail.agenticmarketintel.ai`, `SMTP_PORT=465`, `SMTP_USER=ami.ai@agenticmarketintel.ai`, `SMTP_PASSWORD=<set>`, `SMTP_FROM=noreply@agenticmarketintel.ai`. **Real email delivery does NOT yet work end-to-end** because `mail.agenticmarketintel.ai` returns NXDOMAIN at every public resolver and at Cloudflare's authoritative NS (lou + rihana), despite the A record (`69.57.162.213`, gray cloud) being visible in the Cloudflare DNS dashboard. The underlying SMTP server IS reachable from Mac on ports 465/587/993 (confirmed via `nc -zv` against the IP directly), so the only thing blocking delivery is the DNS record actually surfacing on the authoritative nameservers. Once DNS resolves, the backend will start sending real emails on the next magic-link request — no further code change needed.

### Track E — Promote + TestFlight `+17`

`/promote-to-alpha` ran cleanly on the second try (first preflight blocked on Saiful's uncommitted Silent_Scout work, which he then asked me to commit as `07f0974` — see Track F):
- Tagged `alpha-2026-05-19-3` at `07f0974`.
- rsync ✓; 5 new SMTP keys verified set on melehost alongside the existing 6.
- `docker compose --profile tunnel up -d --build api-alpha` rebuilt the image, recreated only api-alpha (Postgres + Redis + tunnel kept running). Health check went to `healthy` in <10s.
- `alembic upgrade head` ran clean (no migration changes this session).
- Smoke: `/v1/health` → `env=staging`; `/v1/llm/status` → `vllm` active with all tiers routing to `ami-llm`; `/v1/sim/quote/AAPL` → $297.84 source=`yfinance` (real Yahoo); `DELETE /v1/auth/session` unauth → 401 (the new endpoint's auth guard fires).

`scripts/build_testflight.sh` then auto-bumped `0.1.0+16` → `0.1.0+17` (`e04604b`), built the IPA (25 MB), and uploaded via altool — Delivery UUID `bff0c97f-9561-4218-8d38-9115d422c84f`. App Store Connect processing takes ~15-30 min before the build is visible in Internal Testing.

### Track F — Silent_Scout 07_voice/ (Saiful authored, mid-session)

`07f0974`. Saiful added a new research-track folder for on-device STT + TTS investigation covering 5 languages (EN/AR/MS/zh/yue). Mirrors the LoRA-track structure: `01_constraints` (verbatim production-doc quotes as the boundary fence), `02_candidates` (STT + TTS datasheets), `03_coverage_matrix`, `04_eval` (methodology + datasets + results-README), `05_recommendation` (daily-brief + interactive + path-forward), `06_prototypes` (README scaffold). Top-level `Silent_Scout/README.md` was updated to add the new row in the active-tracks table and the path tree. 1697 insertions across 14 new files. Not part of the AMI Trade production track but in the repo + history. Referenced approved plan: `~/.claude/plans/you-are-working-on-stateless-sedgewick.md`.

### Operational footnotes worth surfacing

- **Bug `6fd4144d`** (bug-report close button) — fix `af01328` was already in main from a prior session (the bug-fix worktree `claude/bug-fix-20260517-225716` was confirmed during AT:R26 to have no commits ahead of main). DB status still `pending_review`; verify on TestFlight `+17` and flip to resolved.
- **Bug `a84361f6`** — DB status flipped to `pending_review` mid-session by `/fix-bugs`. Same verify-on-`+17`-then-flip-to-resolved pattern.
- **SMTP DNS — UNRESOLVED at session end. Resume here on AT:R27.**

  **State of evidence at end of session:**
  - Cloudflare DNS dashboard for `agenticmarketintel.ai` shows: `Type=A, Name=mail, Content=69.57.162.213, Proxy=DNS only (gray cloud), TTL=Auto`. Warning triangle next to the row is benign — just the standard "exposes origin IP" notice for gray-cloud A records.
  - But `dig +short mail.agenticmarketintel.ai @rihana.ns.cloudflare.com` AND `@lou.ns.cloudflare.com` (the two authoritative NS for the zone) both returned EMPTY. 1.1.1.1 and 8.8.8.8 returned NXDOMAIN. melehost's resolver returned SERVFAIL. **Authoritative NS empty means it's not a propagation delay — Cloudflare's nameservers genuinely don't see the record.**
  - The IP itself IS a real Namecheap-owned mail server: from Mac, `nc -G 5 -zv 69.57.162.213` connects on ports 465, 587, 993. From melehost, port 465 timed out (separate question — possible ISP block on outbound 465; check 587 next).
  - SMTP creds in `infra/alpha.env`: `SMTP_HOST=mail.agenticmarketintel.ai`, `SMTP_PORT=465`, `SMTP_USER=ami.ai@agenticmarketintel.ai`, `SMTP_PASSWORD=;hMo@u]n^{77`, `SMTP_FROM=noreply@agenticmarketintel.ai`. All 5 verified live on melehost via the promote step-4 `grep` (counted as `<set>`).
  - Backend code is wired + tested + promoted (`alpha-2026-05-19-3`). `email_service.send_magic_link()` is a no-op when `smtp_host=""` and never raises on send failure — so the rest of the app is safe.

  **What to try on AT:R27** (in order, escalating):
  1. **Re-query DNS first thing** — it might just have propagated overnight. `dig +short mail.agenticmarketintel.ai` from Mac. If non-empty, immediately re-run the SMTP smoke test from earlier in AT:R26 (use the IP directly to bypass DNS if needed — `openssl s_client -connect 69.57.162.213:465 -servername mail.agenticmarketintel.ai`).
  2. **If still NXDOMAIN**, ask Saiful to delete + re-add the Cloudflare record. Sometimes a saved-but-not-actually-persisted state happens — re-creating the row forces a clean propagation.
  3. **Check Namecheap's mail-server hostname** — the IP belongs to Namecheap; their Private Email service typically documents the SMTP hostname as e.g. `mail.privateemail.com`, NOT a custom-domain CNAME. Saiful might need to set `SMTP_HOST` to whatever Namecheap's mail dashboard documents (and the TLS cert will be issued for THAT hostname, not the custom domain).
  4. **Test outbound port 465 from melehost** — `ssh melehost "timeout 8 nc -zv mail.privateemail.com 465"` once DNS works. If the connection times out, try 587. If both time out, melehost's ISP may be blocking outbound SMTP; the workaround is to route through a different SMTP provider that listens on a non-standard port, or relay through Mailgun/Postmark.
  5. **Fallback**: Gmail SMTP. `smtp.gmail.com:587` + App Password from any Gmail account Saiful has 2FA enabled on. Drop-in — just update the 5 `SMTP_*` keys in `infra/alpha.env` and re-promote.

  **Until SMTP works, magic-link sign-in is broken for any external user.** Alpha testers don't see it because on `env=staging` the debug code is NOT returned in the API response (Phase 1.5 A1 lockdown) — so a tester who taps "Send Code" gets stuck at the "enter the code" step with nothing to type. **This is a real blocker for External TestFlight launch.**
- **L-1 residual** (from AT:R25 audit) still NOT closed: `OneOnOneStartRequest.user_id: UUID | None` lets a null body bypass `_own_body`. Limited blast radius (resulting session has `user_id=None`, `_own_session` rejects on subsequent calls) but worth tightening if 1-on-1 abuse becomes a real signal.
- **TestFlight `+17` is the same code as +16 plus the AT:R26 changes** — testers on +16 will still work against the new backend (no breaking API change; only the new `DELETE /v1/auth/session` route was added). Apple sign-in attempt on +16 still produces the old generic error; only +17 has the friendly snackbar + caption.

### Carry-overs for AT:R27

Counts audited against tree state at end of AT:R26.

1. **🚧 SMTP DNS — magic-link email is the External Beta blocker.** `mail.agenticmarketintel.ai` was NXDOMAIN at Cloudflare's authoritative NS at session-end despite the gray-cloud A record being visible in the dashboard. Backend code is wired + tested + promoted; only DNS surfacing blocks real email. **Full debug trail + escalation steps are in "Operational footnotes worth surfacing" above** — start by re-querying DNS on session resume; if still NXDOMAIN, try delete+re-add in Cloudflare, then Namecheap's documented mail hostname, then Gmail SMTP fallback.
2. **`6fd4144d` bug-report close button — `pending_review`.** Verify on TestFlight `+17` and flip to resolved.
3. **`a84361f6` Apple-sign-in 503 glitch — `pending_review`.** Verify on TestFlight `+17` and flip to resolved.
4. **`11fde6f6` floor hex agent style — re-open from AT:R24/R25.** No movement again this session (deferred per Saiful).
5. **`eeeb866f` — room run survives container restart — open, deferred-pre-beta.** Note + estimate still in `bug_reports.steps`.
6. **Apple sign-in Phase 3** — Saiful enabled "Sign in with Apple" capability in the Apple Developer portal at the bundle ID this session. Backend still returns 503 outside `env=local` — replace `auth_service.py::_decode_apple_sub` with real PyJWT + Apple JWKS verification. ~1 day.
7. **Google sign-in Phase 3** — explicit decision this session: **defer until Android v1.0**. Don't start the Flutter `google_sign_in` package wiring yet.
8. **B-tier adversarial-audit findings remaining** (deferred to pre-External-Beta): rate limiting on `/auth/anon` + LLM-heavy routes; magic-link attempt counter + per-IP throttle; feedback upload size enforced at the proxy + streaming read. (B4 token-scrubbing closed this session.)
9. **App Store Connect Privacy URL** — Saiful confirmed `https://www.agenticmarketintel.ai/privacy/` is live and added it in App Store Connect → App Information → Privacy Policy URL. Done this session, unblocks External Beta submission.
10. **External TestFlight launch** — still needs a Beta App Description from Saiful + ~24h Apple review on first external build. No External Beta artefact yet.
11. **Animation production** — 15 `<Animation>` MDX tags in `content/lessons/` still render `AmiHexPlaceholder`. Lottie vs CustomPainter decision still open.
12. **A29 light-mode refactor** — v1.0 work.
13. **Two sibling worktrees with unmerged docs** — `claude/blissful-darwin-419097` (bug-pipeline spec + D-057) and `claude/exciting-shtern-aad051` (lessons-landing hex-cluster redesign). Still pending Saiful decision.

### Watch items (not tasks)

- **SMTP delivery in production.** Once DNS surfaces, the very first magic-link request will go out via SMTP. If the SMTP server returns a bad-credentials or unknown-recipient error, `email_service.send_magic_link` swallows it and logs a warning — the user still gets their code via the next attempt OR (on env=local) via the debug chip. On staging there's no debug-code fallback visible to the user, so a silently failing SMTP will look like "magic link doesn't work" to testers. Worth checking the api-alpha logs for `magic_link_email_failed` entries after the first real email attempt.
- **Apple endpoint 503 still in effect on Alpha.** Phase 3 hasn't shipped, so any tester who taps "Sign in with Apple" still gets the 503 path — now with a friendly message (AT:R26 fix). Until Phase 3 lands, magic-link is the only working claim path on Alpha.
- **AT:R24's NVFP4 quantisation watch item still applies** — `ami-llm` (Gemma 4 31B NVFP4) occasionally emits space-split tokens. Not blocking.

---

## How to start the next session

```
/start-fresh
```

The slash command reads HANDOVER.md + project plan, runs the Mac-side sanity-check curls, queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R27** (this is handover #26).

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
