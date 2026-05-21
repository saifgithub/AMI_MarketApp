# Handover — AMI Trade build session

**Last updated:** 2026-05-21 (end of AT:R29 — Apple Sign-In Phase 3 + bug-triage sweep + Android pulled into Alpha). **Apple Sign-In is live end-to-end:** `OIDCVerifier` fetches Apple's JWKS, RSA-verifies the identity token, checks iss/aud/exp. Saiful's user `8f1e288a` claimed with email + display_name. 4 bugs resolved (1 `wont_fix`); 1 open. **365 backend tests** (was 348 — +9 OIDC verifier tests + 7 Apple persistence tests + 1 A4 route test). 4 alpha promotes (`alpha-2026-05-21-{1..4}`). 5 TestFlight uploads (`+19`/`+20`/`+22`/`+23`/`+24` — `+21` revoked via revert). New `users.sh` ad-hoc user inspection script. New `users.display_name` column via migration `b3f9d2a80007`. Google Sign-In Android slice pulled forward from MVP M4 to new A6b (Alpha closeout) — waiting on Saiful's Google Cloud Console setup.

Read this file **first** in any new session. It captures **current truth** + this session's narrative + the carry-overs. Older sessions live in [history.md](history.md) — don't read unless you need historical context. The PRD-derived backlog (with delivery status) is at [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md).

> **Doc shape**: HANDOVER.md = current state + one session's wrap + carry-overs. history.md = everything older, newest-on-top. `/handover` rotates the previous "what just landed" section out of HANDOVER and into history.md before writing this session's narrative.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, **248 commits**, no remote yet |
| Latest work commit | `07a8879` — chore(skills): upstream sync — bug_list block + /rename step (AT:R29). Then this handover-wrap commit. |
| Alpha tags | All prior + `alpha-2026-05-21-{1..4}` (4 promotes this session). Latest `alpha-2026-05-21-4` = display_name migration + Apple Phase 3 + email persistence. |
| Backend tests | **365 passed, 0 failed** (+9 OIDC verifier tests, +7 Apple persistence tests, +1 A4 route test, replaced 1 503-gate test with a 400-rejection test). |
| Content corpus | 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, **312 i18n keys**. Lesson 269 edited this session to disambiguate Room vs 1-on-1. |

```
$ git log --oneline | head -10
07a8879 chore(skills): upstream sync — bug_list block + /rename step (AT:R29)
507b0ad chore(scripts+plan): users.sh shows device_user_id + add BL1/BL2 device backlog (AT:R29)
185e181 chore(scripts): add users.sh — ad-hoc user inspection (AT:R29)
ea3cda9 chore(mobile): bump build 0.1.0+23 → 0.1.0+24 for TestFlight
ff3fa0e feat(auth): persist Apple full_name as users.display_name + pin minimum-data policy (AT:R29)
c87f785 chore(mobile): bump build 0.1.0+22 → 0.1.0+23 for TestFlight
1430371 feat(auth): persist Apple email claim on first sign-in (AT:R29)
04b6f69 chore(mobile): bump build 0.1.0+21 → 0.1.0+22 for TestFlight
9aef407 fix(ios): add applesignin entitlement — Apple Sign-In was failing client-side (AT:R29)
15d5eac chore(mobile): bump build 0.1.0+20 → 0.1.0+21 for TestFlight
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

## What just landed (this session — AT:R29)

Long, multi-track session. **Two big landings:** Apple Sign-In Phase 3 (with Google-ready OIDC verifier abstraction) and a sweep of four user-reported bugs. Plus a `users.sh` inspection script + Android pulled forward to Alpha. **19 new commits, 358→365 backend tests, 4 TestFlight builds (`+19`/`+20`/`+22`/`+23`/`+24` — one was a revert), 4 alpha promotes.**

### Track A — Bug triage sweep

Four bugs filed by Saiful + me on `+18`/`+21`. All addressed; one re-opened then later marked `wont_fix` on Saiful's call.

| short_id | session resolution | how |
|---|---|---|
| `6fd4144d` (was pending_review) | ✅ resolved | Same fix as a19871c3 — collapsed into one |
| `a19871c3` (open → resolved) | ✅ resolved (`+19`) | Bug-report sheet close button was a `GestureDetector` wrapping a 20px icon — replaced with `IconButton` + 44×44 constraints + tooltip. Apple HIG minimum tap target. |
| `9b9d4790` (open → resolved) | ✅ resolved (alpha-2026-05-21-1) | Lesson 269 "trap" paragraph conflated Convene the Room (streamed batch readout) with 1-on-1 (interactive Q&A). Rewrote the paragraph to make Room = batch + 1-on-1 = interactive. Quiz + Try-It were already correct. |
| `11fde6f6` (open → resolved → reopened → wont_fix) | ⏸ wont_fix | Attempt 4 at "match Lessons hex style" — I shipped a 15%-alpha tinted fill + role-color label in `+19`. Saiful reverted in `+20` ("deferred and reverted twice"). Final call: mark `wont_fix` until explicit design direction. Do not auto-pick. |
| `e2a30a64` (filed `+21`, open → resolved) | ✅ resolved (`+22`) | "Apple sign in failed" — backend logs showed zero `/v1/auth/apple` requests. Root cause: no `Runner.entitlements` file at all in the Xcode project. Capability was enabled on the App ID in AT:R26 but never on the app itself. Created the entitlements + wired `CODE_SIGN_ENTITLEMENTS` into all 3 build configs + pre-warmed the provisioning profile via direct `xcodebuild -allowProvisioningUpdates` with the App Store Connect API key (Flutter's `build ipa` doesn't expose the flag). |
| `a84361f6` (pending_review → resolved) | ✅ resolved | Apple sign-in glitch — closed once `+22` confirmed end-to-end working. |

End-state bug list: **1 open** (`eeeb866f` room run survives container restart, pre-Beta) · **32 resolved** · **3 wont_fix**.

### Track B — Apple Sign-In Phase 3 (and Google-ready OIDC verifier)

The big landing. Audit finding A4 closed.

**`backend/app/services/oidc_verifier.py` (new)** — Generic `OIDCVerifier` class:
- JWKS fetch + TTL cache (1h default) + force-refresh on `kid` miss (handles Apple/Google key rotation automatically)
- python-jose for RSA signature verification (was already a dep — no new packages)
- Audience list support (iOS bundle ID now, future Web Services ID via comma-separated env)
- Injectable into `AuthService` for tests (test_oidc_verifier.py + a `_FakeAppleVerifier` in test_auth_service.py)

**`AuthService.sign_in_with_apple`** — calls `self._apple_verifier.verify()`, extracts `sub` + `email` + persists `full_name` (from request body) as `display_name`. Unverified `_decode_apple_sub` scaffold deleted. The `/v1/auth/apple` 503 gate is gone — route lives in every env.

**Mobile (`+21`)** — Replaced hardcoded synthetic JWT with native `SignInWithApple.getAppleIDCredential()`. Captures `givenName`/`familyName` (first-auth only per Apple's contract). Dropped "Coming in v1.0" caption. Dropped api_client 503 fallback.

**Persistence rules** (mirror users.email):
- First Apple auth → persist `email` + `full_name`.
- Subsequent auths (no email/name claim) → preserve.
- Magic-link real email + later Apple relay → real email **kept**, never overwritten.
- Whitespace `full_name` treated as None.

**New migration `b3f9d2a80007`** — adds `users.display_name` column (nullable). Applied on alpha; `init_schema()` picks it up on fresh containers.

**Settings** — `apple_audiences: list[str]` (default `["ai.agenticmarketintel.amiTrade"]`, comma-separated env). `google_audiences: list[str]` (empty, ready for A6b).

**Tests:** 9 in `test_oidc_verifier.py` (happy path, multi-aud, expired, wrong aud, wrong iss, unknown-kid + refresh-on-miss, tampered sig, malformed, missing-kid, JWKS rotation). 7 in `test_auth_service.py` for email + full_name persist + don't-overwrite rules. **365 backend tests passing** (was 348).

**Smoke verified end-to-end live on alpha:** backend fetched Apple's real JWKS (3 keys), `kid` rotation triggered refresh-on-miss, unknown kid rejected with proper 400. User `8f1e288a-...` claimed with `apple_id` + `email=saifulsaid@me.com` + `display_name=Siti Ahmad`.

### Track C — Android pulled forward to Alpha (new A6b)

Saiful's directive 2026-05-20: "Android in next week". Project plan updated:
- **A6** flipped from ⚡ partial to ✅ done (Phase 3 closed AT:R29).
- **New A6b row** — Google Sign-In on Android, pulled forward from MVP M4 to Alpha closeout. **Blocker:** Saiful needs to create the OAuth Web client_id in Google Cloud Console + register the Android SHA-1 signing fingerprint. Verifier abstraction (~50% of the work) already done.
- "No Android" Alpha non-goal struck through.
- M4 dropped to ⚡ partial (only production Play track remains there).
- Alpha completion: **70% → 73%**.

### Track D — Minimum-data policy (locked AT:R29)

Saiful's directive: "Just ask for sub, name and email."

Locked into project plan A6b row + audit doc:
- Apple: scopes = email + fullName. Persist sub, email, full_name. Nothing else.
- Google (A6b): scopes = openid email profile. Persist sub, email, name. **Throw away** picture, locale, given_name, family_name, hd. Never request People-API sensitive scopes (birthday, gender, phone, address).

### Track E — `scripts/users.sh` ad-hoc user inspection

Read-only postgres queries via SSH to melehost:

```
scripts/users.sh                       # dashboard: counts + last claimed + last anon
scripts/users.sh <query>               # substring search across id/email/apple_id/google_id/name/device_user_id
                                         + activity summary on single-match (journal, sim, room, oo, lessons, briefs, sub_events)
scripts/users.sh --recent [N]          # last N users by created_at
scripts/users.sh --anon [N]            # last N anonymous
scripts/users.sh --apple               # all apple-claimed
scripts/users.sh --google              # all google-claimed (ready for A6b)
scripts/users.sh --counts              # counts only
scripts/users.sh --events <id>         # subscription_events log
scripts/users.sh --help                # full help
```

Now shows `device_user_id` (first 8 chars) on every list. Search query also matches against device_user_id::text.

### Track F — Doc hygiene

- `docs/08_tech/auth_phase1_adversarial_audit.md` finding A4: marked **CLOSED (AT:R29)** with verbose status footer.
- `docs/10_delivery/project_plan.md`: A6 → ✅, new A6b row, M4 ⚡, new "Backlog — low priority" section with BL1 (device-info-on-anon) + BL2 (user_devices table).
- This handover wrap + history rotation.

### Operational footnotes worth surfacing

- **Saiful's anonymous user_id was preserved across the entire Apple flow.** Row `8f1e288a-b288-4b9e-942f-2003b88ba555` was anon → magic-link → Apple — same row throughout. All journal/lessons/oo data intact.
- **App Display Name "Ami Trade" in `Info.plist`** — lowercase 'mi'. Visible to users in iOS Settings → Sign-in with Apple → AMI Trade. Saiful flagged it as "the description was a bit odd" — should be "AMI Trade". Easy one-line fix, deferred to a follow-up build.
- **Provisioning-profile pre-warm friction** — `scripts/build_testflight.sh` doesn't pass `-allowProvisioningUpdates` to xcodebuild. When a new iOS capability is added (like Apple Sign In), the build fails until someone runs xcodebuild manually with the App Store Connect API key flags. **Spawned task** to bake this into the script.
- **`flutter pub get` flagged 59 packages with newer-incompatible versions.** Same as last build; no action needed.
- **SMTP still unchanged.** Carry-over #1 from AT:R28; still the External Beta blocker.

### Carry-overs for AT:R30

Counts audited against tree state at end of AT:R29.

1. **🚧 SMTP — pick a working route.** Unchanged from AT:R28. Gmail SMTP (5 min — Saiful provides App Password) or Resend HTTP API (~30 min — swap `email_service.send_magic_link` from smtplib to `resend` SDK). **External Beta blocker.**
2. **A6b — Google Sign-In on Android.** Pulled forward to Alpha per Saiful's "next week" timeline. Verifier abstraction already in place. **Blocker:** Saiful's Google Cloud Console setup (OAuth Web client_id + Android SHA-1 fingerprint). Then ~30min backend + ~1h mobile.
3. **`eeeb866f` room run survives container restart** — open, pre-Beta resilience. Untouched this session.
4. **B-tier adversarial-audit findings** — rate limiting on `/auth/anon` + LLM-heavy routes; magic-link attempt counter; feedback upload streaming. Deferred pre-External-Beta. (A4 closed this session.)
5. **L-1 residual** (from AT:R25 audit) — `OneOnOneStartRequest.user_id: UUID | None` lets a null body bypass `_own_body`. Tighten if 1-on-1 abuse becomes a real signal.
6. **External TestFlight launch** — Beta App Description from Saiful + ~24h Apple review on first external build. Still Internal-only.
7. **`CFBundleDisplayName` casing** — `Ami Trade` → `AMI Trade` in `mobile/ios/Runner/Info.plist`. One-line fix for the next build.
8. **Animation production** — 15 `<Animation>` MDX tags still render `AmiHexPlaceholder`.
9. **A29 light-mode refactor** — v1.0 work.
10. **Two sibling worktrees with unmerged docs** — `claude/blissful-darwin-419097` + `claude/exciting-shtern-aad051`. Still pending Saiful decision.
11. **Brief safety-floor terminology audit (deferred)** — "uncoachable" stays until product strategy decides.
12. **Credit consumption** — `credits_consumed` event type exists but no app code emits it.
13. **BL1 (low pri)** — Device info on `/v1/auth/anon` (model/OS/app_version).
14. **BL2 (low pri)** — `user_devices` table for multi-device tracking.
15. **Spawned task (chip): bake `-allowProvisioningUpdates` + ASC API key into build_testflight.sh.**

### Watch items (not tasks)

- **Apple Sign-In is now real.** Anyone who hits the button gets an Apple-signed JWT verified against Apple's JWKS. Bad tokens 400, good tokens claim. Watch the `oidc_jwks_refreshed` log lines on alpha — should be roughly hourly + one fetch per kid rotation.
- **`+24` is processing in App Store Connect at session end.** Saiful's revoke + re-sign-in already confirmed the persistence chain works on `+23`; `+24` adds display_name persistence. Both ride forward.
- **The `audit_http_write_failed` exception in api-alpha logs (NUL character in `/v1/feedback/bug` body)** — seen during e2a30a64 triage. Image attachment binary leaking into the audit string column. Not blocking — bug reports still get persisted, only the audit row write fails. Future cleanup.

---

## How to start the next session

```
/start-fresh
```

The slash command reads HANDOVER.md + project plan, runs the Mac-side sanity-check curls, queries the live bug list, then enters plan mode asking "bugs first or carry-over first?". Wait for direction.

Session name to use: **AT:R30** (this is handover #29).

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
