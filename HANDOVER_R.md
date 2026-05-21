# Handover — AMI Trade build session

**Last updated:** 2026-05-21 (end of AT:R30 — full docs-vs-code reconciliation sweep). **`docs/08_tech/*` is now ground truth** — every shipped route, table, service, and flow documented; every deferred feature explicitly flagged. 8 commits, no code touched outside mobile model expansions, **365 backend tests still passing** (no changes), no alpha promotes, no TestFlight uploads. 7 new backlog entries (BL4–BL10) filed against the audit findings. Earlier AT:R29 wrap (Apple Sign-In Phase 3 + bug sweep + Android-to-Alpha) is in [history_R.md](history_R.md).

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **258 commits** (8 new this session), no remote yet |
| Latest work commit | `8599cd2` — docs(plan): file 7 new backlog items from AT:R30 audit (BL4-BL10). All 8 AT:R30 commits are docs-only (one touches `mobile/lib/models/*.dart` to expand Dart mandate fields against backend Pydantic). No backend code changed. |
| Alpha tags | Unchanged from AT:R29. Latest still `alpha-2026-05-21-4`. **No promotes this session** — docs-only work. |
| Backend tests | **365 passed, 0 failed** — unchanged. No backend code touched. |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **312 i18n keys**. Unchanged. |

```
$ git log --oneline | head -10
8599cd2 docs(plan): file 7 new backlog items from AT:R30 audit (BL4-BL10)
c7f0155 docs(tech): reconcile auth/llm_routing/stack + flag payments/platform_facade as design-only (AT:R30)
d5550cf docs(arch): architecture.md reconciled — Alpha reality, not MVP aspiration (AT:R30)
b5c4858 docs(schema): data_model.md reconciled against models.py + Alembic chain (AT:R30)
875e4e1 docs(api): full reconciliation — api_design.md now mirrors shipped routes (AT:R30)
0e2e961 docs+mobile: sync code-vs-docs deviations from audit (AT:R30)
8a10c76 chore(skills): handover/start-fresh/session-setup audit pass (AT:R29)
c8dd6cf docs(handover): post-wrap count refresh — 248 → 250 (AT:R29)
46320a7 docs(handover): rotate AT:R28 to history_R + write AT:R29 wrap
4004b3d chore(skills+docs): adopt multi-track skills as canonical, delete legacy un-suffixed handover docs (AT:R29)
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
| Mac-side tests | `backend/.venv/bin/pytest backend/tests/unit/ -q` — **365 passed** (was 348; AT:R29 added `test_oidc_verifier.py` (9 cases) + 7 Apple persistence cases in `test_auth_service.py` + 1 A4 route test, replaced the 503-gate test with a 400-rejection test). Uses sqlite tempfile fixture in `tests/conftest.py`, no real DB needed. Only backend execution that happens on the Mac. |
| Env knobs (alpha) | `AMI_ENV=staging` + `SECRET_KEY=<64-hex>` + `ADMIN_SECRET=<64-hex>` (AT:R27, admin back-office bearer) + `SMTP_{HOST,PORT,USER,PASSWORD,FROM}` (5 vars, AT:R26). Canonical at `infra/alpha.env` on Mac, gitignored; shipped via `scp` in `/promote-to-alpha` step 4. Without `SECRET_KEY` the backend refuses to start when env != local. **`SMTP_HOST` is currently empty by design** — the `email_service` no-op path fires so no connect-attempts hit the ISP-blocked outbound to `mail.agenticmarketintel.ai`. Restore by uncommenting the line in `infra/alpha.env` once a working SMTP route (Gmail / Resend) is configured. |
| Auth | Phase 1.5 + Phase 3 + Phase 4 enforced. Route-level `get_current_user` on `/v1/mandate`, `/v1/journal`, `/v1/watchlist`, `/v1/brief` (legacy `/v1/coach`), `/v1/agents/one_on_one`, `/v1/room`, plus per-route on user-specific `sim` + `lessons`. Bearer format `scaffold:<user_id_hex>:<hmac_sig>` (HMAC-SHA256 with `SECRET_KEY`). Legacy unsigned `scaffold:<hex>` accepted only in env=local. `/v1/auth/anon` mints fresh unless the caller's Bearer matches the supplied `device_user_id`. Magic-link routes require auth and bind to `current_user.id`. **Apple Sign-In Phase 3 (AT:R29):** `/v1/auth/apple` now lives in every env (no more 503 gate). `OIDCVerifier` in `app/services/oidc_verifier.py` fetches Apple's JWKS, RSA-verifies the identity token, validates `iss=https://appleid.apple.com`, `aud ∈ APPLE_AUDIENCES`, `exp`. On first auth: persists `email` + `full_name` (→ `users.display_name`). On subsequent auths or magic-link priors: preserves existing email/name (never overwritten). `DELETE /v1/auth/session` (Phase 4) requires auth and returns `{"signed_out": true}` — stateless no-op now. `http_audit` middleware scrubs request + response bodies for all `/v1/auth/*` routes (AT:R26 B4 close). **AT:R27 suspension enforcement:** `get_current_user` checks `users.suspended_at`; if set, raises `403 {"detail": "account_suspended"}`. **Admin auth:** `/v1/admin/*` uses `Authorization: Bearer <ADMIN_SECRET>`. Audit finding A4 CLOSED. |
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

Tables: `users` (with `suspended_at`, `trial_started_at`, `trial_expires_at` — AT:R27; `display_name` — AT:R29), `auth_challenges`, `mandates`, `agent_activations`, `lessons_progress`, `journal_entries` (with `deleted_at`), `overlay_edit_counts`, `user_overlays`, `room_runs`, `sim_holdings`, `sim_portfolios`, `sim_trades`, `sim_watchlists`, `bug_reports` (with `assigned_branch`, `attachment_path`, `attachment_mime`), `llm_audit`, `http_audit`, `one_on_one_messages`, `subscription_events` (AT:R27), `alembic_version`. Latest migration on melehost: **`b3f9d2a80007`** (`users_display_name` — AT:R29, adds the `display_name` column for OIDC name persistence). `init_schema()` self-stamps Alembic on a fresh container, so `alembic upgrade head` is a no-op on first boot. Bug-report attachments live in the named docker volume `ami-trade-local_bug_attachments` mounted at `/data/bug_attachments` in the api-alpha container.

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
| pubspec version | **`0.1.0+24`** (repo). AT:R29 shipped `+19`/`+20`/`+22`/`+23`/`+24` — see TestFlight row below. `+24` carries Apple Phase 3 + entitlements + email+display_name persistence + hex revert. |
| TESTING IPHONE 13 install | `+18` uploaded to TestFlight 2026-05-20 15:02 UTC; processing in App Store Connect (~15–30 min). Once processed, install via TestFlight on device. For pre-TF dev smoke, use `scripts/install_iphone.sh`. |
| TestFlight | `0.1.0+24` uploaded 2026-05-21 (delivery UUID `2a4767c6-eb48-44d6-8a94-328e8d063095`). AT:R29 sequence: `+19` (bug-report close + Lessons-style hex tint) → `+20` (hex tint reverted, close button kept) → `+22` (entitlements + Apple Sign-In working) → `+23` (email persistence) → `+24` (display_name persistence). Saiful verified Apple Sign-In end-to-end on `+22`+`+23`. External Beta still pending (no external testers added). |
| Build commands | `scripts/install_iphone.sh` (dev sideload), `scripts/build_testflight.sh` (App Store upload, auto-bumps build number). |
| Signing | iOS Distribution cert in keychain (`C184E839…`, team `S7RBWM4879`). App Store Connect API key at `~/.appstoreconnect/private_keys/AuthKey_44VJ5WADL2.p8` (App Manager role; issuer `289e6201-8fc9-44a3-abde-59e8e278527c`). |
| Markdown render | `flutter_markdown` was discontinued by Google upstream; AT:R20 swapped to `flutter_markdown_plus ^1.0.3`. Drop-in API. |

App surface: bottom nav Floor / Portfolio / Journal / Lessons / Settings. Concierge + 12 agents on Floor. **AT:R27 Floor change:** tapping an unlocked agent no longer opens 1-on-1 directly — it now opens an `AgentActionSheet` bottom sheet with two big buttons: `[1-ON-1]` (talk to the agent) and `[BRIEF]` (modify how it thinks). Concierge skips the sheet — has no Brief surface, so 1-on-1 is the only path. The tune icon in the 1-on-1 header stays as a secondary route to Brief. **AT:R27 rename:** `CoachScreen` → `BriefScreen`, `BriefHistoryScreen`, `BriefNotifier`/`briefNotifierProvider`, `models/brief.dart`, `api_client.startBrief/streamBriefMessage/...`. The 33 l10n keys flipped from `coach*` to `brief*` (including the journal chips: `journalFilterCoach` → `journalFilterBrief`, value `COACH` → `BRIEF`; same for `journalEntryTypeCoach`). Journal filter chips now read: `ALL · ROOM · TRADE · 1-ON-1 · BRIEF · LESSONS · UNLOCKS`. **First-time walkthrough (AT:R23):** per-section coach-mark tours (still using `tutorial_coach_mark` package — unrelated to Brief feature) fire on first visit. **AT:R25 auth gate** + **AT:R26 sign-out (Phase 4)** + **AT:R26 Apple-glitch fix** still in place. Journal soft-delete + Trash + server-side search. Room + 1-on-1 agent text renders as Markdown. Verdict card flips its "Open Trade Ticket" button into a green pill once a sim_trade exists. Trade ticket sheet has live quote chip + auto-suggested TP/SL. Ticker tape below bottom nav. Settings → APPEARANCE is dark-only. Bug-report sheet (long-press app-version chip) supports photo attachments.

---

## What just landed (this session — AT:R30)

**Documentation reconciliation session.** Single track: bring `docs/08_tech/*` and the Dart mandate models into line with shipped code so the next session reads ground truth, not aspiration. **8 commits, 0 alpha promotes, 0 TestFlight uploads, 0 test changes, 0 backend code touched.** Mobile changes are limited to Dart model expansions that are backward-compatible at runtime.

### How the session ran

Saiful's framing: "keep our official docs in synch with the code. any that deviate, discuss with me." Started with a 4-phase parallel audit via Explore agents (API routes / database schema / backend services / Flutter models) — surfaced **62 deviations** (40 critical / 16 warning / 6 minor). Triaged with Saiful; then worked tier-by-tier:

1. **First triage** (commit `0e2e961`): pick the cluster Saiful greenlit.
2. **Then a question:** "we have so many of this. have we broken anything?" — answer: no, runtime is fine; docs are debt. Saiful: "I want to make sure we are in synch and that the functions described are accurate and delivered." Switched to **systematic reconciliation** — rewrite each tech doc to match shipped code, mark deferred features explicitly.
3. **Six commits** later, every `docs/08_tech/*` doc is either ground truth or carries an explicit "design doc — not yet built" banner at the top.
4. **Final ask:** "we have a project_plan.md somewhere that has the backlog right?" — yes; filed 7 new backlog items (BL4–BL10) for concrete deferred work surfaced by the audit that doesn't naturally land in any Phase 2/3 roadmap stream.

### Commits in order

| Hash | Doc | What it does |
|---|---|---|
| `0e2e961` | `mobile/lib/models/{mandate,brief,journal,auth}.dart` + initial `api_design.md` mandate + `project_plan.md` BL3 | M2 mobile mandate expansion (TargetOutcome, RiskComponents, DailyBriefing + risk_quotes, trial_expires_at, created_at/updated_at on UserMandate; `mandate_used` + `pending_proposal` on BriefSession; `mandate_version` on JournalEntry; `display_name` on AuthUser). All `fromJson` calls default safely if backend omits a field — backward-compatible. **BL3 filed** for D-039 7-day trial activation on claim (deferred). |
| `875e4e1` | `docs/08_tech/api_design.md` | Full rewrite. 16 routers / 60+ routes from `backend/app/api/*.py` decorators. Per-resource tables list shipped routes only; "Not yet delivered" section lists specced-but-not-built routes with status (Replaced / Deferred / Cut). Added 8 sections that were undocumented (`/auth`, `/admin`, `/ai_coach`, `/daily_challenge`, `/glossary`, `/llm`, `/watchlist`, `/feedback`). Streaming section corrected: SSE-only. Rate limits relabelled "not yet enforced". |
| `b5c4858` | `docs/08_tech/data_model.md` | Full rewrite against `backend/app/db/models.py` + Alembic chain (10 migrations). 18 tables documented with current DDL. Mandates clarified as JSONB-snapshot (not normalized columns). Added the audit/operational tables (`bug_reports`, `auth_challenges`, `llm_audit`, `http_audit`, `one_on_one_messages`, `subscription_events`, `sim_watchlists`, `overlay_edit_counts`). Aspirational tables (`credit_transactions`, `llm_calls`, `daily_challenges`, `streaks`, `briefings`, `drift_alerts`, `brief_sessions`, `offers_redemptions`, `audit_log`, `academy_progress`, `one_on_one_sessions`) moved to "Not yet delivered" with replacement notes. |
| `d5550cf` | `docs/08_tech/architecture.md` | Full rewrite. System diagram: melehost Docker Compose + Cloudflare Tunnel + on-prem vLLM. 24 backend services tabled with files + responsibilities. 5 data flows rewritten to match shipped code (Convene the Room, Brief, Onboarding+claim, 1-on-1, Sim trade). Streaming: SSE-only with `X-Room-Run-Id` reconnect path. Background jobs (8 specced) moved to "Not yet delivered". Third-party SaaS (RC / OneSignal / Twilio / Resend / Sentry / PostHog) all flagged as MVP scope; SMTP carry-over surfaced. D-039 trial activation explicitly flagged in the onboarding+claim flow as not-wired with BL3 cross-ref. |
| `c7f0155` | `docs/08_tech/auth.md` + `llm_routing.md` + `stack.md` + design banners on `payments.md` + `platform_facade.md` | **auth.md** heavy rewrite — own `auth_service` reality, not Supabase; HS256 JWTs; A2 audit fix on `/auth/anon`; SMTP carry-over surfaced; HMS/Google/Phone-OTP all deferred. **llm_routing.md** heavy rewrite — preference order `vllm > anthropic > mock`; `TIER_TO_MODEL` table; `tier_policy.pick_tier()` matrix; OpenRouter+locale routing deferred; cache deferred. **stack.md** rewrite with new Status column (Alpha ✅ vs MVP-only per row); code-org tree refreshed. **payments.md** + **platform_facade.md** got status banners at top — both are design-only (RevenueCat SDK absent from pubspec; `mobile/lib/services/platform/` is empty). |
| `8599cd2` | `docs/10_delivery/project_plan.md` | Filed 7 new backlog items (BL4-BL10) for concrete deferrals surfaced by the audit that aren't already absorbed by Phase 2/3 roadmap streams. See "Backlog reference" below. |

Plus this `chore(handover): wrap AT:R30` commit.

### Why so many deviations existed

Three patterns, all benign:
1. **Docs described the future, code shipped the present.** ~30% — 12 tables documented but never migrated were Beta/MVP features (`daily_challenges`, `briefings`, `drift_alerts`, `streaks`, …). Code is correct; docs were aspirational.
2. **Code evolved faster than docs.** ~50% — Brief got the propose/accept rewrite AT:R27, endpoint structure shifted to body params, mandates were denormalized to JSONB for fast iteration. Each was deliberate; nobody back-updated the markdown.
3. **Pragmatic additions never back-documented.** ~20% — `bug_reports`, audit tables, `auth_challenges`, `subscription_events`, trial date columns. Added because we needed them; nobody updated `data_model.md`.

Code is the source of truth — Postgres + FastAPI + Flutter all agree with each other today. Only the markdown was stale.

### Did the AT:R30 changes break anything?

No. Six edits, all backward-compatible:

| File | Risk | Why safe |
|---|---|---|
| `api_design.md` + `data_model.md` + `architecture.md` + `auth.md` + `llm_routing.md` + `stack.md` + `payments.md` + `platform_facade.md` + `project_plan.md` | 0 | Docs only — runtime ignores |
| `mobile/lib/models/mandate.dart` | Low | New `TargetOutcome` / `RiskComponents` / `DailyBriefing` classes + 7 new fields; constructor adds `required this.riskComponents` + `required this.dailyBriefing` but **all consumers go through `UserMandate.fromJson`** which defaults safely if the backend omits a field. `grep -rn "UserMandate(" mobile/lib/ --include="*.dart" \| grep -v fromJson` returns only the model file itself. |
| `mobile/lib/models/{brief,journal,auth}.dart` | 0 | `mandateUsed`, `pendingProposal`, `mandateVersion`, `displayName` all optional with defaults. `fromJson` tolerates missing keys. |

`flutter analyze` clean on changed files (only 2 pre-existing infos in `floor_placeholder_screen.dart`, unrelated). No backend code touched; **365 backend tests still pass**.

### Backlog reference

Existing BL1 + BL2 + BL3 untouched. New items filed this session:

| ID | Item | Est | Trigger |
|---|---|---|---|
| **BL4** | Arabic→Gemini locale routing (D-048) | 0.5 | Blocked on `GoogleProvider` |
| **BL5** | Mandate history API (versions/rollback) | 1 | Replay works via journal today |
| **BL6** | Mandate audit/resolve flow | 1 | Needs drift detection first |
| **BL7** | Agent metadata routes (`/agents` list/details/past_calls) | 1 | Mobile uses client manifest |
| **BL8** | Room run cancel + replay endpoints | 1.5 | Room is unkillable mid-flight |
| **BL9** | Sim trade preview endpoint | 0.5 | Pre-flight extracted from `/sim/submit` |
| **BL10** | Daily challenge attempt endpoint | 0.5 | Useful when streaks ship |

Bigger items (Supabase migration, RevenueCat, OneSignal, Sentry, server-side rate limits, journal retention jobs, etc.) are already absorbed by Phase 2 / Phase 3 roadmap streams — not duplicated in the BL list.

### Where to read the new ground truth

| If you want to know… | Read |
|---|---|
| What endpoints exist + their shape + what hasn't shipped yet | `docs/08_tech/api_design.md` |
| What's in the database + what tables don't exist yet | `docs/08_tech/data_model.md` |
| How a Convene/Brief/Onboarding actually flows + what runs vs what's MVP target | `docs/08_tech/architecture.md` |
| The actual auth flow (own service, not Supabase yet) | `docs/08_tech/auth.md` |
| LLM tier mapping + provider preference order | `docs/08_tech/llm_routing.md` |
| The whole stack at a glance with Alpha / MVP status per row | `docs/08_tech/stack.md` |

`hosting.md`, `backend_modes.md`, `coding_conventions.md` verified already in sync — left untouched. `tradingagent_integration.md`, `flutter_implementation.md`, `auth_audit.md`, `auth_phase1_adversarial_audit.md` not swept (historical / audit docs that should stay as-of-date-of-writing).

### Bug list at end of session

Unchanged from AT:R29: **1 open** (`eeeb866f` room run survives container restart, pre-Beta) · **32 resolved** · **3 wont_fix**.

### Carry-overs for AT:R31

All carry-overs from AT:R29 are still live (nothing was actively worked on outside docs):

1. **🚧 SMTP — pick a working route.** Unchanged. Gmail SMTP (5 min — Saiful provides App Password) or Resend HTTP API (~30 min). **External Beta blocker.** Now also surfaced in `auth.md` + `stack.md` + `architecture.md` as the explicit Alpha gap.
2. **A6b — Google Sign-In on Android.** Verifier abstraction in place; blocker: Saiful's Google Cloud Console setup (OAuth Web client_id + Android SHA-1).
3. **`eeeb866f` room run survives container restart** — open, pre-Beta resilience.
4. **B-tier adversarial-audit findings** — rate limiting on `/auth/anon` + LLM-heavy routes; magic-link attempt counter; feedback upload streaming.
5. **L-1 residual** — `OneOnOneStartRequest.user_id: UUID | None` tighten.
6. **External TestFlight launch** — Beta App Description from Saiful + ~24h Apple review.
7. **`CFBundleDisplayName` casing** — `Ami Trade` → `AMI Trade` one-liner in `Info.plist`.
8. **Animation production** — 15 `<Animation>` MDX tags still render `AmiHexPlaceholder`.
9. **A29 light-mode refactor** — v1.0 work.
10. **Two sibling worktrees with unmerged docs** — `claude/blissful-darwin-419097` + `claude/exciting-shtern-aad051`. (Note: 25 `claude/*` worktrees exist on disk; not the `agent-*` pattern that `/handover` cleans automatically. Saiful decision.)
11. **Brief safety-floor terminology audit (deferred)** — "uncoachable" stays.
12. **Credit consumption** — `credits_consumed` event type exists but no app code emits it.
13. **BL1 (low pri)** — Device info on `/v1/auth/anon` (model/OS/app_version).
14. **BL2 (low pri)** — `user_devices` table for multi-device.
15. **BL3 (low pri)** — D-039 7-day trial activation on claim (filed AT:R30).
16. **BL4–BL10 (low pri)** — Audit-surfaced concrete deferrals filed AT:R30. See "Backlog reference" above.
17. **Spawned task (chip): bake `-allowProvisioningUpdates` + ASC API key into build_testflight.sh.**

### Watch items (not tasks)

- **Docs are now testable.** Every claim in `docs/08_tech/*` can be checked against a specific file in `backend/app/` or `mobile/lib/`. If a next-session edit drifts a doc out of sync, it shows up immediately — and the "Not yet delivered" sections are the canonical place to add new aspirational features so the boundary stays clean.
- **Mobile mandate fields are richer.** Anything reading `UserMandate.targetOutcome` / `riskComponents` / `dailyBriefing` will now get real data when the backend includes it (since AT:R20+ the backend has been emitting these). If a screen renders these and crashes on null, it's a mobile bug to fix — not a backend question.
- **The 25 `claude/*` sibling worktrees** in `.claude/worktrees/` are not from this session. `/handover` cleans `agent-*` pattern worktrees per `session-config.yml`; the `claude/*` ones are residue from prior subagent spawns across many sessions. Cleanup is a Saiful decision (some may have unmerged work).

---

## How to start the next session

```
/start-fresh
```

The slash command reads HANDOVER.md + project plan, runs the Mac-side sanity-check curls, queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R31** (this is handover #30).

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
- **Apple Developer team.** Done (`S7RBWM4879`). Sign in with Apple capability enabled at the bundle ID (Saiful, AT:R26) + entitlements file in Xcode + provisioning profile regenerated (AT:R29). Phase 3 JWKS verification shipped AT:R29 — fully live end-to-end.
- **App Store + APNs** — external. Market data is real Yahoo when `USE_REAL_MARKET_DATA=true`.

Nothing is blocking the next chunk.
