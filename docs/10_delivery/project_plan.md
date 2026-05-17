# Project plan — Alpha → Beta → MVP

Three phases. Each phase has an exit criterion, a concrete work list, and a who-does-what split. Supersedes the older `timeline.md` (kept for historical context).

Where we are right now (as of 2026-05-17, end of AT:R22):
- 174 commits on `main`. 275 backend unit tests pass.
- Alpha live on melehost (Ubuntu LAN at `192.168.20.59`) via Cloudflare Tunnel.
- TestFlight has build `0.1.0+14`; TESTING IPHONE 13 has `0.1.0+14` installed.
- vLLM Gemma 4 31B (ami-llm) serving every agent. Room runner decoupled from SSE via background task + queue (AT:R22) — runs continue to verdict on client disconnect, dedup on same user+ticker (running + 24h-completed-cached windows), journal write retries.
- Real Yahoo prices via yfinance. AMI brand throughout user copy. 270 lessons, 188 glossary terms, 280 AI Coach Q&A, 183 daily challenges, 264 i18n keys.

## Delivery status — Alpha snapshot

Alpha (A1–A29):
- **✅ Done**: A1, A2, A7, A8, A9, A10, A11, A12, A18, A19, A20, A23, A25, A26, A27 — 15 items.
- **⚡ Partial**: A6, A17, A21, A22, A28, A29 — 6 items (mechanisms / drafts exist; finishing touches blocked on external assets, lawyer review, or v1.0 work).
- **⏳ Blocked on external**: A3, A13, A15 — 3 items (Resend, TTS provider, OneSignal+APNs).
- **◯ Unstarted**: A4, A5, A14, A16 — 4 items (all downstream of blocked externals).
- **✖ Superseded**: A24 — 1 item (CLI `altool` replaced Transporter).

**Alpha is ~70% complete.** The unblocked engineering surface (every `done` + `partial` Claude-only item) is wrapped. What's left of Alpha is mostly Saiful-external setup (email/TTS/push providers, legal copy) + downstream code that depends on it. Beta + MVP are mostly unstarted (M5 partial because i18n landed early in Alpha).

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
| **A3** | Email provider — Resend account + DKIM/SPF DNS records. | Saiful | external | ⏳ blocked (Resend account) | Resend free tier covers alpha. Blocks A4/A5. |
| **A4** | Email-confirmation flow. `/v1/auth/register` (email+password) → signed token → confirmation email → `/v1/auth/confirm`. Reuses W8 auth scaffold. | Claude | 0.5 session | ◯ unstarted (blocked on A3) | |
| **A5** | Flutter Register screen — email+password, "check your inbox" state, deep-link handler for the confirm URL. | Claude | 0.5 session | ◯ unstarted (blocked on A3) | |
| **A6** | Real Apple Sign-In. Add Sign in with Apple capability to bundle id under team S7RBWM4879; replace synthetic JWT in `sign_in_screen.dart` with `sign_in_with_apple` (already in pubspec). | Saiful (cap) + Claude (code) | 0.5 session + 5 min Apple Dev | ⚡ partial (scaffold JWT works; real `sign_in_with_apple` not wired) | |
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
| **A22** | Privacy policy + ToS first draft. Simulation-only / educational disclaimer. | Saiful (+ Claude drafts copy) | external review | ⚡ partial (AT:R20 — sample research + clause-by-clause plan landed in `docs/09_compliance/{legal_samples,legal_plan_ami_trade}.md`; lawyer review + public hosting at `agenticmarketintel.ai/legal/*` external) | App Store needs this anyway. |
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
- No Android. iOS only via TestFlight.
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
| **M4** | Android (GMS) release. Flutter build, Play Console setup, signing, closed beta → open beta → production. | Claude + Saiful | 1 session + external | ◯ unstarted (MVP phase) | |
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
