# Project plan — Alpha → Beta → MVP

Three phases. Each phase has an exit criterion, a concrete work list, and a who-does-what split. Supersedes the older `timeline.md` (kept for historical context).

Where we are right now (as of 2026-05-22, end of AT:R35):
- 294 commits on `main`. 424 backend unit tests pass. **Zero open bugs.**
- **AT:R35 i18n Tier 1 landed.** Translation pipeline ships LAN-direct to on-prem vLLM Gemma 4 31B (`192.168.20.74:8000`) via OpenAI-compatible chat-completions; bypasses CF Tunnel that the legacy `scripts/translate_arb.py` uses. Three new scripts in `scripts/translate_*_lan.py`. `mobile/lib/l10n/app_ar.arb` now 311/311 keys filled, `app_ms.arb` 310/311 (one MS placeholder dropped → EN fallback). Tier 2 (glossary/ai_coach/daily_challenges) + Tier 3 (lessons) scripts shipped but not yet run — first parallel attempt saturated vLLM; carry-over to run sequentially in AT:R36.
- Alpha live on melehost (Ubuntu LAN at `192.168.20.59`) via Cloudflare Tunnel. AT:R34 added container-restart resilience to Room runs: startup sweep auto-retries stuck `running` rows once before marking failed (migration `e7a4c5b00010` adds `room_runs.retry_count`; commits `8510436` + `3f4022a`). Closed the last open bug `eeeb866f`.
- TestFlight has build `0.1.0+27` uploaded 2026-05-22 (AT:R33). **Verified live on both iPhone 17 + iPhone 13 mini with same Apple ID** (AT:R34): 2 device rows under one user via `device_install_id` re-keying on Apple Sign-In. Carries the BL1 + BL2 mobile slice: device_info_plus + device_install_id sent to `/v1/auth/anon` on every bootstrap. Plus the AT:R32 backend (account-linking Phase 1, Resend HTTP, BL13/BL14/BL15) + AT:R33 backend (BL9 sim preview, BL10 daily-challenge attempt, BL1 device columns + admin surface, BL12 mandate-audit, BL2 user_devices + re-keying, BL11 effective_plan, BL5 mandate history).
- Alpha-stage Privacy Policy + ToS published at `https://www.agenticmarketintel.ai/{privacy,terms}/` with doc-level versioning (AT:R24). Lawyer review still pending; publishing playbook at `docs/09_compliance/VERSIONING.md`.
- vLLM Gemma 4 31B (ami-llm) serving every agent. Room runner decoupled from SSE via background task + queue (AT:R22) — runs continue to verdict on client disconnect, dedup on same user+ticker (running + 24h-completed-cached windows), journal write retries.
- First-time user walkthrough (AT:R23) — 4 per-section coach-mark tours fire automatically on first visit to each tab; resettable from Settings → WALKTHROUGH.
- Real Yahoo prices via yfinance. AMI brand throughout user copy. 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, 312 i18n keys.

## Delivery status — Alpha snapshot

Alpha (A1–A29, plus A6b pulled forward from MVP M4):
- **✅ Done**: A1, A2, **A6**, A7, A8, A9, A10, A11, A12, A18, A19, A20, A23, A25, A26, A27 — 16 items (A6 closed AT:R29 with Phase 3 JWKS verification).
- **⚡ Partial**: A3, A17, A21, A22, A28, A29 — 6 items (A3 SMTP wired but DNS pending; others: mechanisms / drafts exist; finishing touches blocked on external assets, lawyer review, or v1.0 work).
- **⏳ Blocked on external**: A13, A15, **A6b** — 3 items (TTS, OneSignal+APNs, **Google Cloud OAuth client_id for Android**).
- **◯ Unstarted**: A4, A5, A14, A16 — 4 items (all downstream of A3/A13/A15).
- **✖ Superseded**: A24 — 1 item (CLI `altool` replaced Transporter).

**Alpha is ~73% complete.** The unblocked engineering surface (every `done` + `partial` Claude-only item) is wrapped. What's left of Alpha is mostly Saiful-external setup (email/TTS/push providers, Google OAuth, legal copy) + downstream code that depends on it. Beta + MVP are mostly unstarted (M5 partial because i18n landed early in Alpha; M4 partial because Android slice pulled forward).

**Status legend** (used in every table below): `✅ done` · `⚡ partial` · `⏳ blocked` · `◯ unstarted` · `✖ superseded`. AT:R\<N\> tags in the status cell point to the session that delivered it — cross-reference with [HANDOVER.md](../../HANDOVER.md) / [history.md](../../history.md).

---

## Phase 1 — Alpha (on-prem)

**Exit criterion:** 10–50 friendly testers can register with email + Apple, sign in, and use **every feature** of the app from outside the LAN via Cloudflare Tunnel. Backend, Postgres, and vLLM all stay on Saiful's hardware. i18n / TTS / push / daily briefing all work end-to-end — Saiful wants a full shakedown before scaling. Failure of any single piece must produce a graceful AMI fallback rather than a 500.

**Why on-prem first:** burn rate is zero, latency is LAN-tight, the LLM is already humming there, and we discover real bugs in every feature before paying for managed services. Better to find integration issues with the friendly group than at MVP launch.

### Work items

Grouped by stream. Engineering items (Claude) are sized in sessions; external items (Saiful) are mostly parallel.

#### Stream 1 — Finish the AMI surface

| # | Item | Who | Est | Status | Notes |
|---|---|---|---|---|---|
| **A1** | Convene the Room → AMI wiring. Each phase calls llm_gateway with a transcript-aware prompt; keep scripted fallback when `gateway.has_real_provider()` is False. | Claude | 1 session | ✅ done (AT:R11) | Largest user-visible unlock. The Room is the marquee flow. |
| **A2** | Concierge (post-onboarding) → AMI. Wire through agent_runner so it actually answers questions and routes the user. Onboarding state machine stays deterministic. | Claude | 0.5 session | ✅ done (AT:R11) | |

#### Stream 2 — Real auth + on-prem hardening

| # | Item | Who | Est | Status | Notes |
|---|---|---|---|---|---|
| **A3** | Email provider — SMTP (`email_service.send_magic_link` via stdlib `smtplib`); 5 `SMTP_*` env vars on melehost. | Saiful + Claude | 0.25 session | ⚡ partial (AT:R26: code wired + tested + promoted; Saiful added `mail.agenticmarketintel.ai` A record but DNS still NXDOMAIN at session-end — real delivery blocked on DNS surfacing) | Switched from Resend to direct SMTP. Magic-link still works via debug-code-only fallback when SMTP_HOST is empty or DNS fails. |
| **A4** | Email-confirmation flow. `/v1/auth/register` (email+password) → signed token → confirmation email → `/v1/auth/confirm`. Reuses W8 auth scaffold. | Claude | 0.5 session | ◯ unstarted (blocked on A3) | |
| **A5** | Flutter Register screen — email+password, "check your inbox" state, deep-link handler for the confirm URL. | Claude | 0.5 session | ◯ unstarted (blocked on A3) | |
| **A6** | Real Apple Sign-In. Add Sign in with Apple capability to bundle id under team S7RBWM4879; replace synthetic JWT in `sign_in_screen.dart` with `sign_in_with_apple` (already in pubspec); add Apple JWKS signature verification in `auth_service.py::sign_in_with_apple`. | Saiful (cap) + Claude (code) | 0.5 session | ✅ done (AT:R29) | Phase 3 closed AT:R29 — `OIDCVerifier` in `backend/app/services/oidc_verifier.py` does JWKS fetch + cache, RSA-signature verification, iss/aud/exp checks. Audit finding A4 closed. Same verifier shape reused for Google on Android — see **A6b** below. |
| **A6b** | **Google Sign-In on Android** — **formalized AT:R36 as [D-057](../11_decisions/decision_log.md#d-057--android-gms-pulled-forward-from-v10-to-alpha)**. Mobile: `google_sign_in` package already in pubspec, render Google button on the sign-in screen on Android (Platform.isAndroid branch; Apple stays iOS-only), pipe the returned id_token into `POST /v1/auth/google`. Backend: `GoogleOIDCVerifier` (mirrors Apple verifier, JWKS at `https://www.googleapis.com/oauth2/v3/certs`, audiences = `GOOGLE_AUDIENCES` env var = OAuth Web client_id), add `/v1/auth/google` route + service method (mirrors `sign_in_with_apple` including account-linking-Phase-1 email-lookup-first). Schema (`GoogleSignInRequest`). New migration adds `users.google_sub VARCHAR NULL UNIQUE`. `users.display_name` added in AT:R29 (migration `b3f9d2a80007`). Tests: claim → user-row glue + verifier tests mirroring `test_oidc_verifier.py`.<br><br>**Minimum-data policy (locked AT:R29 — Saiful: "Just ask for sub, name and email"):** request only `openid email profile` (no `picture`/`locale`/`hd`/extended-scopes like birthday/gender/phone). Persist only `sub` → `users.google_sub`, `email` → `users.email`, `name` → `users.display_name`. Throw away `picture`, `locale`, `given_name`/`family_name`, and never request the People-API sensitive scopes. Same rule on Apple. | Saiful (Google Cloud Console + keystore SHA-1) + Claude (code) | 0.5 session + external setup | ⚡ partial (AT:R36 code landing; awaits GCP OAuth client_id) | **Saiful's remaining work:** generate upload keystore at `~/.android-keys/`, register Android client + Web client in GCP Console, hand over Web client_id for `GOOGLE_AUDIENCES`. |
| **A7** | Cloudflare Tunnel — named tunnel, hostname (`api-alpha.<your-domain>`), Cloudflare Access policy (email allowlist). | Saiful | external | ✅ done (AT:R11) | Blocks A12. |
| **A8** | Backend production launch — systemd unit, env file in `/etc/ami-trade.env`, log rotation, restart-on-fail. | Claude | 0.5 session | ✅ done | |
| **A9** | Postgres backups — `pg_dump` cron, offsite copy, restore drill. | Claude | 0.25 session | ✅ done | |
| **A10** | Sentry SDK in backend + Flutter. | Claude | 0.5 session | ✅ done | |

#### Stream 3 — i18n + voice + push + daily briefing (Saiful's full-shakedown ask)

| # | Item | Who | Est | Status | Notes |
|---|---|---|---|---|---|
| **A11** | i18n structure. Extract every user-facing string in `mobile/lib/` to ARB files via `flutter_localizations` + `intl`. Locale switcher in Settings. RTL pass for AR (`Directionality`, padding-inline already in conventions). English content ships; AR/MS files start as empty placeholders. | Claude | 0.5 session | ✅ done | |
| **A12** | AR + MS translations. Saiful arranges external translators with the ARB files + context comments. Drop-in when ready. | Saiful | external | ✅ done (auto-translated by Gemma 4) | Doesn't block Alpha launch — partial/empty translations are fine; falls back to English. |
| **A13** | TTS provider — Azure Speech account + key OR ElevenLabs account + key. Decide based on Arabic voice quality (Azure stronger for AR; ElevenLabs stronger for English emotion). | Saiful | external | ⏳ blocked (Azure/ElevenLabs account) | Blocks A14. |
| **A14** | TTS integration. `app/services/tts_gateway.py` (mirrors `llm_gateway` shape) with `AzureSpeechProvider` or `ElevenLabsProvider`. Voice per agent family (analyst / researcher / risk / manager / concierge). Tap-to-listen on agent messages — not auto-play (keeps cost sane). Server-side caching by message hash. | Claude | 1 session | ◯ unstarted (blocked on A13) | |
| **A15** | OneSignal account + Dev APNs certificate from Apple Dev console. | Saiful | external | ⏳ blocked (OneSignal + Dev APNs cert) | Blocks A16. |
| **A16** | Push notifications. OneSignal SDK in Flutter, server-side `POST /notifications` endpoint, deep-link routing (open the specific Journal entry / Room verdict / lesson on tap). | Claude | 0.5 session | ◯ unstarted (blocked on A15) | |
| **A17** | Daily briefing flow. Background job (`apscheduler` on-prem; Cloud Scheduler at Beta) assembles a 60-second audio brief per user — pulls mandate + recent journal + open positions; renders via TTS; sends push with audio attachment URL. Delivered at user's chosen local time from their mandate. | Claude | 1 session | ⚡ partial (daily-challenge service AT:R15; full TTS-audio briefing not built) | Depends on A14 + A16. |

#### Stream 4 — Product polish (watchlist, lessons UX, animations)

| # | Item | Who | Est | Status | Notes |
|---|---|---|---|---|---|
| **A18** | User watchlist. New `sim_watchlists` table (user_id, ticker, added_at, notes). `GET/POST/DELETE /v1/watchlist/{user_id}`. Flutter section on Portfolio screen above HOLDINGS: each watchlist row shows ticker, live quote, day change %, and a tap-target opening a sheet with quote + buttons (Add Trade, Ask Market Analyst, Convene the Room). Tickers free-form — any string Yahoo can quote. | Claude | 1 session | ✅ done | The "I want to see *my* stocks" loop. Curriculum lessons cite tickers illustratively; the user populates their own watchlist for daily use. |
| **A19** | Lesson UX — "Skip to quiz". Lessons screen lists each lesson with a "READ" button + a "QUIZ ONLY" button. Quiz-only path renders just the `<Quiz>` blocks, the explanations on miss, and counts toward the agent-unlock the same as a full read+pass. Wrong-answer explanations are the teaching surface for skippers. | Claude | 0.5 session | ✅ done | |
| **A20** | Lesson loader: parse new frontmatter fields (`module`, `difficulty`). Default to `module: 0, difficulty: <level>` for legacy lessons. | Claude | 0.25 session | ✅ done | Unblocks generation runs from the lesson authoring prompt. |
| **A21** | Animation MDX component — Flutter `AnimationRegistry` maps name → Lottie asset path; missing names render `AmiHexPlaceholder`. Bundle whatever animations exist; lessons referencing missing names still display. | Claude | 0.5 session | ⚡ partial (`AnimationRegistry` shipped; Lottie assets pending external) | Decouples content delivery from animation production. |
| **A29** | Light-mode register. The v2 design system ships a light token set (slate-100 canvas, white panels, slate-900 ink) plus AA-safe accent-text tokens (`--accent-cyan-text`, `--accent-amber-text`, etc.). Intent per the spec README: *"bright/outdoor mobile conditions triggered by the ambient light sensor — not as a default visual register."* Work: light-mode `ThemeData` factory in `mobile/lib/theme/ami_theme.dart`, a Riverpod provider that listens to ambient brightness (start with `MediaQuery.platformBrightness` as a simpler proxy, ambient-sensor plugin later), contrast-verify every accent token, run every screen in light-mode in the dev_preview pass. | Claude | 0.5 session | ⚡ partial (theme built AT:R18; UI toggle removed AT:R19 — 37-screen refactor pending, v1.0 work) | Lower priority than feature work but real outdoor-use value. Held pending marketing alignment on hex bottom-nav swap (a separate v2 item being discussed). |

#### Stream 5 — Ship to offsite testers + observe

| # | Item | Who | Est | Status | Notes |
|---|---|---|---|---|---|
| **A22** | Privacy policy + ToS first draft. Simulation-only / educational disclaimer. | Saiful (+ Claude drafts copy) | external review | ⚡ partial (AT:R20 — sample research + clause-by-clause plan in `docs/09_compliance/legal_plan_ami_trade.md`; AT:R24 — standalone drafts `privacy_policy.md` + `terms_of_service.md` assembled, alpha HTML published at `agenticmarketintel.ai/{privacy,terms}/` with doc-level versioning + publishing playbook `VERSIONING.md`. Lawyer review of 5 jurisdiction-sensitive clauses still pending.) | App Store needs this anyway. |
| **A23** | App Store Connect — create the app record (bundle id `ai.agenticmarketintel.amiTrade`, SKU `AMITRADE`, English primary). One-time, 5-min web form. | Saiful | external | ✅ done (TestFlight uploaded) | Blocks A25. |
| **A24** | Install Transporter (Apple's free Mac upload tool) from the Mac App Store. | Saiful | external | ✖ superseded (we use CLI `xcrun altool` — `scripts/build_testflight.sh`) | Blocks A26. |
| **A25** | Switch Flutter build to Distribution signing + App Store export. `flutter build ipa --release --export-method app-store --dart-define=AMI_API_URL=<cloudflare-hostname>`. Xcode auto-manages the Distribution cert + App Store provisioning profile once the app exists in App Store Connect. Produces `build/ios/ipa/Runner.ipa`. | Claude | 0.5 session | ✅ done (AT:R19 — `scripts/build_testflight.sh`) | |
| **A26** | Upload to App Store Connect via Transporter (drag the .ipa, click upload). | Saiful | external | ✅ done (AT:R19 — first end-to-end CLI upload, `0.1.0+4`) | ~5 min. |
| **A27** | Add testers in TestFlight. Internal (≤100, Apple Dev team members, instant) or External (≤10k, anyone via email, first build needs a one-time Beta App Review ~24h). | Saiful | external | ✅ done (Internal Testing group `AMI Team`) | |
| **A28** | Tester onboarding — invite copy, feedback channel (private Slack/Discord/email), bug-report template. | Saiful | external | ⚡ partial (bug-report mechanism live with photo attachments AT:R20; invite copy / public feedback channel external) | |

**Claude effort:** ~9.75 sessions of dev (7.5 from streams 1–3 + 2.25 from new Stream 4: watchlist + skip-to-quiz + frontmatter fields + animation registry). **Saiful effort:** Resend, Cloudflare, Apple capability (×2 — Sign in with Apple + Dev APNs cert), Azure/ElevenLabs, OneSignal, legal stub, translators, App Store Connect app record, Transporter, tester invites. Mostly parallel to Claude.

**Explicit non-goals for Alpha (everything else is in scope):**
- No GCP. No Cloud Run. No Cloud SQL.
- No Supabase yet — local Postgres + the W8 auth scaffold serves Alpha. Supabase swap is the headline Beta item.
- No payments. No RevenueCat. Floor Pass for everyone during alpha.
- Cloud LLM stays Beta. On-prem vLLM Gemma 4 keeps serving Alpha.
- ~~No Android.~~ **Android-GMS pulled into Alpha — formalized AT:R36 as [D-057](../11_decisions/decision_log.md#d-057--android-gms-pulled-forward-from-v10-to-alpha).** Internal-track testers join the Alpha cohort via Google Sign-In + Play Console internal testing. iOS still on TestFlight. Locked sub-decisions in D-057: individual Play Console registration, Play App Signing, `minSdk 28` / `targetSdk 35`, Samsung Galaxy A17 as test device, push + payments stay deferred (same as iOS). See A6b.
- No App Store production release (that's MVP).
- No marketing / public launch.

---

## Phase 2 — Beta (cloud migration, infra only)

**Exit criterion:** Backend runs on Cloud Run. Postgres + Auth on Supabase. LLM served from a cloud provider (Vertex AI Gemini, Anthropic, or both). On-prem hardware no longer in the request path. Same feature surface as Alpha — *nothing new ships*. Same testers, same app build (just pointed at the new backend hostname).

**Why this phase exists:** Saiful's LAN box is a single point of failure. The moment we need 24/7 uptime, hardware redundancy, or to scale beyond ~50 concurrent streams, the on-prem stack stops being good enough. Beta is the boring-but-essential infra cutover. Nothing user-visible changes.

### Work items

| # | Item | Who | Est | Status | Notes |
|---|---|---|---|---|---|
| **B1** | GCP project setup — billing, IAM, service accounts, gcloud CLI auth. | Saiful | external | ◯ unstarted (Beta phase) | |
| **B2** | Dockerize backend. Multi-stage build, slim runtime image, healthcheck endpoint. | Claude | 0.5 session | ◯ unstarted (Beta phase) | |
| **B3** | Cloud Run deploy. Cloud Build trigger from the GitHub repo (push to `main` → deploy). | Claude | 0.5 session | ◯ unstarted (Beta phase) | |
| **B4** | Supabase project provision. | Saiful | external | ◯ unstarted (Beta phase) | Blocks B5/B6. |
| **B5** | Supabase Auth swap. Replace `app/services/auth_service.py` impl with `supabase-py` admin SDK. Route contracts unchanged. Migrate the email-confirmation flow to Supabase's hosted version (drop our Resend integration here — Supabase handles confirmation emails). | Claude | 1 session | ◯ unstarted (Beta phase) | |
| **B6** | Postgres → Supabase migration. `pg_dump` from on-prem → restore into Supabase Postgres. Switch backend connection from `postgres` superuser to `authenticated`/`anon` roles → RLS policies start enforcing. | Claude | 1 session | ◯ unstarted (Beta phase) | Test the migration on a copy first. |
| **B7** | Cloud LLM cutover. Pick a provider for production:<br>• **Vertex Gemini** — same Google ecosystem, lowest latency to Cloud Run, comparable quality to on-prem Gemma 4.<br>• **Anthropic Claude** — strongest quality tier, higher cost.<br>• **Both** — Anthropic primary, Gemini fallback (or vice-versa) via `LLMGateway._PREFERENCE`.<br>Update `tier_to_model` for the new provider's model IDs. On-prem vLLM stays available as a dev fallback. | Saiful + Claude | decision + 0.5 session | ◯ unstarted (Beta phase) | |
| **B8** | Secret Manager — every API key (Resend / Supabase / LLM provider / Sentry / etc.) moves out of `.env` into GCP Secret Manager; Cloud Run mounts as env vars. | Claude | 0.25 session | ◯ unstarted (Beta phase) | |
| **B9** | Cloud Logging + Monitoring dashboards. Alert rules: 5xx rate, p99 latency, LLM error rate, Supabase auth failure rate. | Claude | 0.5 session | ◯ unstarted (Beta phase) | |
| **B10** | CI/CD via GitHub Actions or Cloud Build. Run tests on PR; deploy on merge to main. | Claude | 0.5 session | ◯ unstarted (Beta phase) | |
| **B11** | Staging environment — separate Cloud Run service + separate Supabase project (or schema) + DNS. | Claude | 0.5 session | ◯ unstarted (Beta phase) | |
| **B12** | Load test 1-on-1 streaming endpoint. k6 or locust script; baseline p95 latency at 10/50/100 concurrent streams against the cloud stack. | Claude | 0.5 session | ◯ unstarted (Beta phase) | |
| **B13** | DNS cutover. Point the Alpha Cloudflare hostname (or a new `api.<domain>`) at the Cloud Run service. The same Alpha iPhone TestFlight build now talks to GCP. | Saiful + Claude | 0.25 session + DNS | ◯ unstarted (Beta phase) | |
| **B14** | Decommission on-prem. Keep the LAN box as a hot dev fallback, but offsite testers no longer reach it. | Saiful | external | ◯ unstarted (Beta phase) | |

**Claude effort:** ~5 sessions of dev. **Saiful effort:** GCP project, Supabase project, cloud LLM provider account, decisions, DNS.

**Explicit non-goals for Beta:**
- No new features. Anything that wasn't in Alpha stays out of Beta. *Nothing user-visible changes.*
- No payments. No App Store production. No Play Store.
- TestFlight build is the same iOS app; just rebuild it once at the end of Beta with the new hostname baked in.

---

## Phase 3 — MVP (public launch)

**Exit criterion:** App Store live (iOS). Play Store live (Android-GMS). Payments work. Pricing tiers (Floor Pass free / Trader $14.99 / Floor Manager $34.99). AR + MS translations dropped in (i18n plumbing landed in Alpha). Customer-support inbox exists. Marketing landing page is up. Ready to start paid acquisition.

**Why these gates:** anything less than this isn't a product — it's a beta with a price tag. Most of the *features* shipped in Alpha; MVP is "make it sellable + make it shippable + make it discoverable."

### Work items

| # | Item | Who | Est | Status | Notes |
|---|---|---|---|---|---|
| **M1** | RevenueCat integration. Pricing tiers wired to backend (mandate.plan transitions); receipt validation; entitlement checks on premium routes (1-on-1 with PM, Convene the Room). | Claude + Saiful | 1 session + RC config | ◯ unstarted (MVP phase) | |
| **M2** | App Store metadata — screenshots, app preview video, description copy, privacy nutrition labels, age rating. | Saiful (+ Claude drafts copy) | external | ◯ unstarted (MVP phase) | |
| **M3** | App Store submission + review iteration. Be ready for the simulation/educational positioning to take 1–3 review rounds. | Saiful | external | ◯ unstarted (MVP phase) | |
| **M4** | Android (GMS) release. Flutter build, Play Console setup, signing, closed beta → open beta → production. | Claude + Saiful | 1 session + external | ⚡ partial (AT:R29: Android slice pulled forward to Alpha — see A6b. MVP M4 now reduces to the Play Console **production** track + open-beta promotion; closed-beta + Google Sign-In land in Alpha.) | |
| **M5** | Drop in AR + MS translations from the translators (i18n structure already shipped in Alpha A11). | Saiful | external | ⚡ partial (i18n plumbing landed in A11; AR + MS translations dropped in via Gemma 4 already — re-evaluate at MVP) | |
| **M6** | Production APNs certificate from Apple Dev (Dev cert was used in Alpha). Push notifications cut over to production. | Saiful + Claude | 0.25 session + Apple Dev | ◯ unstarted (MVP phase) | |
| **M7** | PostHog analytics. Funnel events, cohort tracking, feature flags. | Claude + Saiful | 0.5 session + PostHog account | ◯ unstarted (MVP phase) | |
| **M8** | Marketing landing page. trade.agenticmarketintel.ai (or chosen domain). | Saiful or Claude | TBD | ◯ unstarted (MVP phase) | |
| **M9** | Customer support inbox + first-line response playbook. | Saiful | external | ◯ unstarted (MVP phase) | |
| **M10** | Compliance — regulatory copy review, jurisdiction-specific disclaimers (US, GCC, SEA at minimum). | Saiful + lawyer | external | ◯ unstarted (MVP phase) | |
| **M11** | DAU/MAU + cohort dashboards. Saiful's morning view: signups, activation, retention by cohort. | Claude | 0.5 session | ◯ unstarted (MVP phase) | |
| **M12** | Initial user-acquisition push. HN, Twitter, founder network, paid test ($500–2000). | Saiful | external | ◯ unstarted (MVP phase) | |

**Claude effort:** ~3 sessions of dev. **Saiful effort:** substantial — App Store reviews, translators (drop-in), legal, marketing, analytics setup.

---

## Backlog — low priority

Nice-to-haves not blocking any phase exit. Pick up only when current
work runs out.

| # | Item | Est | Notes |
|---|---|---|---|
| **BL1** | **Device info on `/v1/auth/anon`.** ✅ **Closed AT:R33** (commit `9e1ce93`). Mobile sends `device_model` + `os_version` + `app_version` via `device_info_plus` + `package_info_plus` on every bootstrap. Backend persists onto `users` (migration `c4e8f1a90008` adds 3 nullable columns) and refreshes on every re-bootstrap. Surfaced in `/v1/admin/users/{id}` + admin HTML. Backwards-compatible. +4 tests. | ✅ Done | AT:R33. |
| **BL2** | **`user_devices` table for multi-device tracking.** ✅ **Closed AT:R33** (commit `2d8a0d8`). New `user_devices` table keyed by `device_install_id` (mobile-generated UUID persisted once, never overwritten by claim — separate from `device_user_id` because the latter gets overwritten by setIdAndToken on claim adoption). Migration `d5f2a3b00009` + backfill seeded 24 rows from existing `users.device_user_id`. `_claim_or_create` + `sign_in_with_apple` re-key the pre-claim anon's devices to the adopted user so two phones on one Apple ID surface as two device rows under one user. Mobile `DeviceUser.getOrCreateInstallId()` + sends on bootstrap. Admin surface lists each device with model/OS/app_version/last_seen. +5 tests. | ✅ Done | AT:R33. |
| **BL3** | **D-039 trial activation on claim (7-day Trader trial) — data plane wired AT:R31, downstream still TODO.** Decision D-039 promises every new user 7 days of Trader features upon account claim. **Data plane (AT:R31, commit `e722dc5`):** `auth_service._claim_or_create()` + `sign_in_with_apple()` now populate `users.trial_started_at = now()` and `users.trial_expires_at = now() + 7d` on first claim. Two tests in `backend/tests/unit/test_auth_service.py` lock the behaviour (`test_claim_sets_trial_dates`, `test_reauth_does_not_reset_existing_trial`). **Still TODO before the promise lands end-to-end:** entitlement gate that reads these columns (today nothing reads them), expiry banner in mobile, conversion modal at expiry. See BL11 for the trial-end UX layer. | 0.5 session (downstream only) | Re-priority once Saiful is ready for Founders cohort. |
| **BL4** | **Arabic → Gemini locale routing (D-048).** `llm_gateway._pick_provider(locale, model_tier)` accepts a `locale` parameter and records it on the `llm_audit` row, but never uses it for provider selection. D-048 requires Arabic queries to prefer Gemini over Claude (Google has invested heavily in Arabic; empirically more natural Arabic finance output). Blocked on `GoogleProvider` class existing — `llm_gateway.py:13` lists it as "Coming later (W4+)." Once GoogleProvider lands, the wire-up is ~3 lines: `if locale == "ar" and "google" in self._providers: return self._providers["google"]` before the default preference loop. | 0.5 session | AT:R30 deferred. Surfaced by docs-vs-code audit ([SV2-ARABIC-ROUTING]). Blocking dependency: GoogleProvider. |
| **BL5** | **Mandate history API.** ✅ **Closed AT:R33** (commit `d3cb451`). Three new routes — sugar over the existing versioned `mandates` table: `GET /v1/mandate/{u}/versions` (list newest-first, decorated with the matching `mandate_edit` journal entry's plain-English summary), `GET /v1/mandate/{u}/versions/{v}` (fetch a specific historical snapshot), `POST /v1/mandate/{u}/rollback/{v}` (forward-only rollback: creates a new version mirroring v, writes a journal entry tagged `rollback`). Store gains list_versions + get_version + rollback_to methods. +10 tests. UI mockup pre-req overruled — API shape is the canonical CRUD-history pattern. | ✅ Done | AT:R33. |
| **BL6** | **Mandate audit/resolve flow.** `POST /mandate/{u}/audit/resolve` to handle mandate-violation actions (liquidate / postpone / override). Today the safety floor only warns at trade-time; there's no flow for "your portfolio is now out of compliance with your mandate — what do you want to do?" Depends on drift detection shipping first (currently deferred to MVP — see `architecture.md` background jobs). | 1 session | AT:R30 deferred. Pre-req: mandate-drift detection job (currently MVP scope). |
| **BL7** | **Agent metadata routes.** `GET /v1/agents` (list 12 agents + per-user activation state), `GET /v1/agents/{agent_id}` (single agent details + current overlay), `GET /v1/agents/{agent_id}/past_calls` (list past contributions to journal entries). Mobile currently uses a client-side 12-agent manifest + stitches `past_calls` from `GET /v1/journal/{u}` with `agents_involved=<id>` filtering — works fine for Alpha. Routes become necessary if activation state varies per-user beyond what `/v1/lessons/activations/{u}` already provides, or if past-calls list needs pagination/server-side aggregation. | 1 session | AT:R30 deferred. Surfaced by docs-vs-code audit ([A1-AGENTS]). Mobile workaround is sufficient until v1.0 Android port. |
| **BL8** | **Room run cancel + replay endpoints.** `POST /v1/room/{run_id}/cancel` and `POST /v1/room/{run_id}/replay`. Cancel needs Postgres-side signalling between the inbound request and the background task running the Room — non-trivial. Replay is essentially a no-op today (`GET /v1/room/{run_id}` already returns the full transcript for re-render without re-invoking the LLM). Cancel is the real ask; replay is sugar. | 1.5 sessions | AT:R30 deferred. Surfaced by docs-vs-code audit ([A2-ROOM-4/5]). Today the Room run is unkillable mid-flight — if a tester taps Convene and immediately backgrounds the app, the LLM keeps running and the credit is consumed. Add when external Beta testers report it as friction. |
| **BL9** | **Sim trade preview endpoint.** ✅ **Closed AT:R33** (commit `7e5aa9a`). `POST /v1/sim/preview` runs the same compliance + cash/holdings pre-flight as `/submit` but never persists. New `SimEngine.preview()` + `PreviewResult` dataclass. Returns `{accepted, compliance, fill_price, notional, cash_available, held_quantity, price_source}`. +3 tests. | ✅ Done | AT:R33. |
| **BL10** | **Daily challenge attempt endpoint.** ✅ **Closed AT:R33** (commit `e5fbfc6`). `POST /v1/daily_challenge/{cid}/attempt` records the attempt + journals it (best-effort). Returns correctness + correct_option + explanation + related_lesson/agent. Adds `EntryType.DAILY_CHALLENGE` (no DB migration — entry_type is free-form String). +5 tests. | ✅ Done | AT:R33. |
| **BL11** | **Trial-end UX layer (D-039, post-BL3).** ⚡ **Entitlement gate closed AT:R33** (commit `95e2337`). `effective_plan(plan, trial_expires_at)` resolves at every `pick_tier()` callsite (brief_engine, agent_runner, room_runner) — when a trial lapses the LLM routing drops to cheap-tier automatically. Admin surfaces `effective_plan` + `trial_active`. +12 tests. **Still TODO (Beta):** in-app "trial ended" summary screen, conversion modal (Floor Pass vs Trader), push notification at expiry (needs OneSignal). | ⚡ Partial | AT:R33 closed the entitlement gate. Push + modal stay Beta-scoped. |
| **BL12** | **Mandate-audit on hard edits.** ✅ **Audit half closed AT:R33** (commit `efe6b79`). `GET /v1/mandate/{u}/audit` runs deterministic per-holding audit of current portfolio against current mandate. New `check_holdings_against_mandate()` evaluator in `safety_floor.py` (sibling to `check_mandate_compliance`). Returns per-holding `HoldingViolation`s + portfolio-level `drawdown_breach`. Pure read — no journal writes. +8 tests. **Resolve actions** (Liquidate/Postpone/Override) are tracked separately as BL6. | ✅ Done | AT:R33. |
| **BL13** | **OnboardingSession → claimed_user_id binding.** ✅ **Closed AT:R32** (commit `62b7c6d`). Both `/v1/auth/magic_link/verify` and `/v1/auth/apple` now accept optional `onboarding_session_id` in the body; route looks up the matching session in `session_store` and stamps `claimed_user_id`. Routes converted to async. Backwards-compatible (old clients omit the field, binding silently skips). +2 tests. Flutter wiring (sending the session_id) deferred until something consumes the binding. | ✅ Done | AT:R32. |
| **BL14** | **Mobile drops Brief timestamps.** ✅ **Closed AT:R32** (commit `7b44110`). Added nullable `DateTime? proposedAt` to `BriefProposal` + `DateTime? startedAt` to `BriefSession`; both parsed from snake_case keys in `fromJson`. No UI consumer today; available for future audit-trail / replay chip without backend redeploy. | ✅ Done | AT:R32. |
| **BL15** | **AgentActivation Pydantic class is dormant — delete or wire.** ✅ **Closed AT:R32** (commit `e238f12`). Deleted `AgentActivation` + `ActivationMethod` enum from `app/schemas/agents.py` + dropped re-export from `app/schemas/__init__.py`. Real activation logic remains in `lessons_service.py` via `AgentActivationRecord` (unaffected). Unused `UUID` import trimmed. | ✅ Done | AT:R32. |
| **BL16** | **Account linking — real merge UX + anon-state migration.** Phase 1 landed AT:R32 (commit `1166cad`): `_claim_or_create()` + `sign_in_with_apple()` now adopt existing-identity users by email instead of forking parallel rows. Pre-claim anon row is silently orphaned. Beta-grade fix: when claim adopts an existing identity AND the anon row has meaningful pre-claim state (journal entries, sim trades, lessons progress, onboarding mandate), surface a "you have two accounts, merge?" UX with conflict resolution (which mandate wins? union the lessons? newest-by-timestamp for journal entries?). Subscription-events audit row for legal/billing. | 1 session | AT:R32 filed. Today's silent-discard is fine because pre-claim state is minimal — the longer this defers, the more visible data-loss becomes once journal/sim writes happen pre-claim. |

---

## Cross-cutting commitments

These rules hold across every phase:

1. **The safety floor is sacred.** The PM's deterministic compliance check function is uncoachable, untouchable, and never short-circuited regardless of plan/agent/tier. Any code change near `app/agents/safety_floor.py` triggers a re-read of `docs/02_agents/safety_floor.md`.
2. **AMI is the brand.** Users never see "the AI" or "LLM" or model names. Internals stay LLM. (See `docs/08_tech/coding_conventions.md`.)
3. **Mandate is the user's protection.** Coaching changes style; only mandate edits change limits. Visible diffs on every mandate update.
4. **Stealth alpha first.** No public announcement until Phase 3 ships.

---

## Rough sizing

| Phase | Claude sessions | Saiful external effort | Calendar |
|---|---|---|---|
| Alpha | ~9.75 | Resend, Cloudflare, Apple cap, Dev APNs cert, Azure/ElevenLabs, OneSignal, App Store Connect, Transporter, translators, legal stub, testers | 3–4 weeks |
| Beta | ~5 | GCP, Supabase, cloud LLM provider, DNS | 2–3 weeks |
| MVP | ~3 | App Store / Play / translators drop-in / legal / marketing / analytics | 3–6 weeks |
| **Total** | **~17.75 sessions** | (mostly parallel to Claude) | **8–13 weeks** |

A "session" here is a single coherent Claude work-chunk that lands one or two commits — typically 0.5–2 hours of Saiful-time.

What changed from the previous draft: TestFlight distribution moved to Alpha (it's distribution, not infra — backend can stay on-prem behind Cloudflare Tunnel while testers install via TestFlight). Beta is now strictly **GCP + Supabase + cloud LLM**, no new product surface. Nothing user-visible changes between Alpha and Beta.

---

## Phase-1 first move

The first item Claude can pick up autonomously: **A1 — Convene the Room → AMI wiring**. Largest user-visible unlock; unblocked by external dependencies.

In parallel, Saiful's external setup queue (do in this order — each unblocks specific work items):

1. **Resend account + DKIM/SPF DNS records** → unblocks A4/A5 (email confirmation).
2. **Sign in with Apple capability** on bundle id under team `S7RBWM4879` → unblocks A6.
3. **Cloudflare Tunnel + named hostname + Access policy** → unblocks A22 (TestFlight build needs the cloud-reachable URL baked in).
4. **TTS provider (Azure or ElevenLabs) account + API key** → unblocks A14.
5. **OneSignal account + Dev APNs cert** from Apple Dev → unblocks A16.
6. **App Store Connect app record** (`ai.agenticmarketintel.amiTrade`, SKU `AMITRADE`) + install **Transporter** from Mac App Store → unblocks A21/A22.
7. **Tester list** (10–50 emails) + feedback channel → ready when Alpha is.
8. **Translators for AR + MS** — non-blocking; drop in any time.
9. **Privacy policy + ToS draft (lawyer review)** — non-blocking; needed for the Beta App Review submission anyway.
