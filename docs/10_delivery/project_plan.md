# Project plan — Alpha → Beta → MVP

Three phases. Each phase has an exit criterion, a concrete work list, and a who-does-what split. Supersedes the older `timeline.md` (kept for historical context).

Where we are right now (as of W15, 2026-05-12):
- 18 commits on `claude/magical-edison-18bf91` (not yet merged to main).
- iPhone has the W11 release build. Backend serves W13+ code via vLLM Gemma 4.
- 130/130 unit tests pass. Real Yahoo prices. AMI brand throughout user copy.
- Convene the Room is the last scripted surface — every other agent talks to vLLM.

---

## Phase 1 — Alpha (on-prem)

**Exit criterion:** 10–50 friendly testers can register with email + Apple, sign in, and use every feature of the app from outside the LAN via Cloudflare Tunnel. Backend, Postgres, and vLLM all stay on Saiful's hardware. Failure of any single piece must produce a graceful AMI fallback message rather than a 500.

**Why on-prem first:** burn rate is zero, latency is LAN-tight, the LLM is already humming there, and we discover real bugs before paying for managed services.

### Work items

| # | Item | Who | Est | Notes |
|---|---|---|---|---|
| **A1** | Convene the Room → AMI wiring. Each phase calls llm_gateway with a transcript-aware prompt; keep scripted fallback when `gateway.has_real_provider()` is False. | Claude | 1 session | Largest user-visible unlock. The Room is the marquee flow. |
| **A2** | Concierge (post-onboarding) → AMI. Wire through agent_runner so it actually answers questions and routes the user. Onboarding state machine stays deterministic. | Claude | 0.5 session | |
| **A3** | Email provider — Resend account + DKIM/SPF DNS records for the sending domain. | Saiful | external | Resend free tier covers alpha volume comfortably. |
| **A4** | Email-confirmation flow. New `/v1/auth/register` (email+password) → signed token → confirmation email → `/v1/auth/confirm`. Reuses W8 auth scaffold's session + claim flow. | Claude | 0.5 session | |
| **A5** | Flutter Register screen — email+password+confirm, "check your inbox" state, deep-link handler for the confirm URL. | Claude | 0.5 session | |
| **A6** | Real Apple Sign-In. Add Sign in with Apple capability to bundle id under team S7RBWM4879; replace synthetic JWT in `sign_in_screen.dart` with `sign_in_with_apple` package (already in pubspec). Verify on TESTING IPHONE 13. | Saiful (cap) + Claude (code) | 0.5 session + 5 min in Apple Dev | |
| **A7** | Cloudflare Tunnel — named tunnel, hostname (`api-alpha.<your-domain>`), Cloudflare Access policy (email list) for an extra gating layer. | Saiful | external | One-time setup; `cloudflared` runs as a service on the LAN box. |
| **A8** | Backend production launch on-prem — systemd unit, env file in `/etc/ami-trade.env`, log rotation, restart-on-fail. No more `nohup uvicorn`. | Claude | 0.5 session | |
| **A9** | Postgres backups — `pg_dump` cron, offsite copy (S3-compatible or Saiful's NAS), restore drill. | Claude | 0.25 session | |
| **A10** | Sentry SDK in backend (Python) + Flutter (Dart). Use `SENTRY_DSN` already in config. | Claude | 0.5 session | |
| **A11** | Privacy policy + ToS first draft. Simulation-only / educational disclaimer. | Saiful (+ Claude drafts copy) | external review | Required for App Store later anyway. |
| **A12** | Re-deploy iPhone release build pointing at the Cloudflare hostname (not the LAN IP). | Claude | 0.25 session | iPhone leaves the house. |
| **A13** | Tester onboarding — invite copy, alpha access list (10–50 emails), feedback channel (private Slack/Discord/email). | Saiful | external | |

**Claude effort:** ~4 sessions of dev. **Saiful effort:** Resend, Cloudflare, Apple capability, legal stub, testers. Mostly parallel.

**Explicit non-goals for Alpha:**
- No GCP. No Supabase. No Cloud SQL.
- No payments. No RevenueCat. Floor Pass for everyone during alpha.
- No App Store. TestFlight comes in Beta.
- No i18n. English only.
- No TTS / push / daily briefing.
- No Android. iOS only.

---

## Phase 2 — Beta (GCP migration)

**Exit criterion:** Backend lives on Cloud Run. Postgres on Cloud SQL. LLM still on-prem (reached via Cloudflare Tunnel back to the LAN box, or migrated to Vertex if costs/latency dictate). TestFlight build distributes to ~100–500 closed testers. Staging environment exists. CI/CD pipeline pushes to production.

**Why migrate now and not later:** as soon as testers exceed the LAN box's capacity or Saiful needs to be away from his hardware, the on-prem setup becomes a single point of failure. Beta is the moment to move.

### Work items

| # | Item | Who | Est | Notes |
|---|---|---|---|---|
| **B1** | Dockerize backend. Multi-stage build, slim runtime image, healthcheck endpoint. | Claude | 0.5 session | |
| **B2** | GCP project setup — billing, IAM, service accounts, gcloud CLI auth. | Saiful | external | |
| **B3** | Cloud SQL Postgres provision. Alembic migrations run against it. `pg_dump` from on-prem → restore script. | Claude | 1 session | Test the migration on a copy first. |
| **B4** | Cloud Run deploy. Cloud Build trigger from the GitHub repo (push to `main` → deploy). | Claude | 0.5 session | |
| **B5** | Secret Manager — every API key (Resend, Sentry, etc.) moves out of `.env` into Secret Manager; Cloud Run mounts as env vars. | Claude | 0.25 session | |
| **B6** | LLM connectivity decision. Option A: keep vLLM on-prem, reach it from Cloud Run via the existing Cloudflare Tunnel. Option B: move to Vertex Gemini. Pick based on latency + cost. | Saiful + Claude (decision) | decision call | |
| **B7** | Cloud Logging + Monitoring dashboards. Alert rules: 5xx rate, 99p latency, LLM error rate. | Claude | 0.5 session | |
| **B8** | CI/CD via GitHub Actions or Cloud Build. Run tests on PR; deploy on merge to main. | Claude | 0.5 session | |
| **B9** | Staging environment — separate Cloud Run service + Cloud SQL instance + DNS. | Claude | 0.5 session | |
| **B10** | TestFlight build. App Store Connect setup. Internal testing group → external testers. | Saiful + Claude | 0.5 session + external | First time the app goes through Apple's pipeline; iterate on metadata. |
| **B11** | Load test 1-on-1 streaming endpoint. k6 or locust script; baseline p95 latency at 10/50/100 concurrent streams. | Claude | 0.5 session | |
| **B12** | Sentry → cloud project; production alert rules. | Claude | 0.25 session | |
| **B13** | Promote a few Alpha testers into Beta; cut off direct LAN access. | Saiful | external | |

**Claude effort:** ~5 sessions of dev. **Saiful effort:** GCP setup, App Store Connect, TestFlight distribution, decisions.

**Explicit non-goals for Beta:**
- Still no payments.
- Still no Android.
- Still no i18n.
- Still no TTS / push / daily briefing.

---

## Phase 3 — MVP (public launch)

**Exit criterion:** App Store live (iOS). Play Store live (Android-GMS). Payments work. Pricing tiers (Floor Pass free / Trader $14.99 / Floor Manager $34.99). i18n shipped for AR + MS. Daily briefing flow ships. Customer-support inbox exists. Marketing landing page is up. Ready to start paid acquisition.

**Why these gates:** anything less than this isn't a product — it's a beta with a price tag.

### Work items

| # | Item | Who | Est | Notes |
|---|---|---|---|---|
| **M1** | RevenueCat integration. Pricing tiers wired to backend (mandate.plan transitions); receipt validation; entitlement checks on premium routes (1-on-1 with PM, Convene the Room). | Claude + Saiful | 1 session + RC config | |
| **M2** | App Store metadata — screenshots, app preview video, description copy, privacy nutrition labels, age rating. | Saiful (+ Claude drafts copy) | external | |
| **M3** | App Store submission + review iteration. Be ready for the simulation/educational positioning to take 1–3 review rounds. | Saiful | external | |
| **M4** | Android (GMS) release. Flutter build, Play Console setup, signing, closed beta → open beta → production. | Claude + Saiful | 1 session + external | |
| **M5** | i18n. AR + MS string files with context comments. Translator handoff. RTL pass for AR. | Claude (structure) + Saiful (external translators) | 0.5 session + external | |
| **M6** | TTS. Azure Speech or ElevenLabs. Voice picker per agent (or one per family). | Claude + Saiful | 1 session + provider account | |
| **M7** | Push notifications (OneSignal). | Claude + Saiful | 0.5 session + OneSignal config | |
| **M8** | Daily briefing flow. Background job assembles a 60-second audio brief tied to user's mandate + journal; delivered via push at user's chosen local time. | Claude | 1 session | |
| **M9** | PostHog analytics. Funnel events, cohort tracking, feature flags. | Claude + Saiful | 0.5 session + PostHog account | |
| **M10** | Marketing landing page. trade.agenticmarketintel.ai (or chosen domain). | Saiful or Claude | TBD | |
| **M11** | Customer support inbox + first-line response playbook. | Saiful | external | |
| **M12** | Compliance — regulatory copy review, jurisdiction-specific disclaimers (US, GCC, SEA at minimum). | Saiful + lawyer | external | |
| **M13** | DAU/MAU + cohort dashboards. Saiful's morning view: signups, activation, retention by cohort. | Claude | 0.5 session | |
| **M14** | Initial user-acquisition push. HN, Twitter, founder network, paid test ($500–2000). | Saiful | external | |

**Claude effort:** ~6 sessions of dev. **Saiful effort:** substantial — App Store reviews, translators, legal, marketing.

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
| Alpha | ~4 | Resend, Cloudflare, Apple cap, legal stub, testers | 1–2 weeks |
| Beta | ~5 | GCP, App Store Connect, TestFlight | 2–3 weeks |
| MVP | ~6 | App Store / Play / legal / translators / marketing | 4–8 weeks |
| **Total** | **~15 sessions** | (mostly parallel to Claude) | **7–13 weeks** |

A "session" here is a single coherent Claude work-chunk that lands one or two commits — typically 0.5–2 hours of Saiful-time.

---

## Phase-1 first move

The first item Claude can pick up autonomously: **A1 — Convene the Room → AMI wiring**. It's the largest user-visible unlock and unblocked by external dependencies.

In parallel, Saiful's first external task: **A3 — Resend account + DNS records**. Email confirmation can't ship until DKIM/SPF resolve.
