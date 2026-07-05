# Pre-Alpha Checklist (what Saiful does before week 1)

The things only Saiful can do, that need to be done before I can start coding effectively.

## Critical (week 0 — before W1 of timeline)

Weeks 1–8 run on Saiful's own server, so most cloud accounts can wait. The critical pre-W1 list is much shorter:

| # | Task | Notes |
|---|---|---|
| 1 | Confirm server access + specs | Linux box (Ubuntu/Debian) with Docker, ≥8GB RAM, ≥50GB disk, public network. Or Mac with Docker Desktop as fallback. |
| 2 | Open Cloudflare account → add `agenticmarketintel.ai` DNS | Free tier. Also used for Cloudflare Tunnel (HTTPS to local dev). |
| 3 | Open OpenRouter account → fund $50 starter | https://openrouter.ai/ — for LLM routing |
| 4 | Get Anthropic API key | Required quality bar; ~$100–200 initial credit |
| 5 | (Optional) OpenAI + Google AI API keys | For fallback routing — can defer to W4 if budget tight |
| 6 | Open Sentry account → free tier | sentry.io |
| 7 | Open Resend account → free tier | resend.com |
| 8 | Open PostHog account → free tier | posthog.com |
| 9 | Decide subdomain structure | `trade.agenticmarketintel.ai` vs `agenticmarketintel.ai/trade` vs `amitrade.ai` (new registration). My recommendation: subdomain. |
| 10 | Create bundle ID in Apple Developer | Suggested: `com.agenticmarketintel.amitrade` |
| 11 | Create app record in App Store Connect (status: in dev — invisible to public) | Pre-reserved for TestFlight later |
| 12 | Choose 1 trusted finance-literate person to be a private alpha tester | Someone who will give honest feedback before Founders open up |

**Estimated time: 1–2 hours total.** Less than originally planned because GCP + Supabase Cloud + RevenueCat etc. all defer to W8–W9.

## Soon (weeks 1–4)

These can be done in parallel with engineering work; not blocking.

| # | Task | Notes |
|---|---|---|
| 13 | Open Twilio account (for SMS OTP at v1.0) | Free trial; production credit when needed |
| 14 | Get a lawyer on retainer or hourly | Should know consumer SaaS + at least one of (Saudi PDPL, Malaysia PDPA, GDPR) |
| 15 | Decide branding details | Logo treatment (use existing AMI hex), wordmark style |
| 16 | TestFlight setup in App Store Connect | Add the first 10 testers' Apple IDs |
| 17 | Decide app icon | We have the AMI hex; need a final icon variant. Claude can mock options. |

## Mid-step (week 7–10) — including GCP migration prep

| # | Task | Notes |
|---|---|---|
| 18 | Open Google Cloud Platform account with billing enabled | Needed by W8 — gives us a few days to set up before W9 migration |
| 19 | Create GCP project `ami-trade-alpha` | Single project for alpha |
| 20 | Open Supabase Cloud account → Pro plan ($25/mo) → create project in `europe-west-3` Frankfurt | Migration target |
| 21 | Lawyer reviews Privacy Policy + ToS + Disclaimer drafts | Claude drafts first; lawyer reviews. ~1–2 lawyer-hours. |
| 22 | Translate Privacy Policy + ToS into AR + MS (at v1.0) | Optional at alpha; required at v1.0 |
| 23 | Set up Founders cohort communication channel | Slack workspace or Discord server — Saiful's pick |
| 24 | Recruit the next 20 Founders | Personal network first; HN/Twitter post when build is stable |

## v1.0 prep (week 9–12)

| # | Task | Notes |
|---|---|---|
| 25 | Open RevenueCat account → connect Apple/Google/HMS apps | Free tier covers us until $10K MTR. Skippable at alpha (no billing). |
| 26 | Configure IAP products in App Store Connect / Play Console / AppGallery Connect (when ready) | Trader Monthly/Annual, Floor Manager Monthly/Annual, 3 credit packs |
| 27 | Open Google Play Console ($25 one-time fee) | When v1.0 Android prep begins |
| 28 | Open Huawei Developer account (free) | When v1.1 prep begins |
| 29 | Find AR translator + native QA reviewer | Recommended: a financial-translation specialist via Smartling, Lokalise, or local agency |
| 30 | Find MS translator + native QA reviewer | Same |
| 31 | Marketing landing-page review | Claude drafts; Saiful reviews + tweaks before going live |
| 32 | App Store listing screenshots + copy review | Same |
| 33 | Founders Pricing offer setup in RevenueCat | When billing infra is ready |
| 34 | Apple App Review submission notes (sandbox account, demo deep-link) | Drafted by Claude, Saiful reviews |
| 35 | Plan a "launch day" content schedule | HN post, Twitter/X thread, possibly r/algotrading post, friends/family announcement |

## After alpha launch (post-W12)

| # | Task | Notes |
|---|---|---|
| 36 | Monitor Founders feedback | Daily for first 2 weeks; weekly after |
| 37 | Triage critical bug reports | Saiful decides priority; Claude fixes |
| 38 | Run weekly "what we learned" sync (with self / with Claude) | Drive iteration cadence |
| 39 | Begin v1.0 build planning | Use what we learned to refine the next phase |

## What can I (Claude) NOT do without these?

| Task can't proceed | Without |
|---|---|
| Set up local dev stack | Server access + Docker installed |
| Set up LLM gateway | API keys exist (OpenRouter + at least Anthropic) |
| Set up Cloudflare Tunnel for HTTPS | Cloudflare account + domain DNS routed |
| Submit to TestFlight | Apple Developer account + bundle ID reserved |
| Send emails | Resend account exists |
| Capture errors | Sentry account exists |
| Track analytics | PostHog account exists |
| Migrate to GCP at W9 | GCP + Supabase Cloud accounts ready by W8 |
| Wire up SMS OTP | Twilio account exists (only needed at v1.0) |
| Charge money | RevenueCat + IAP products configured (only needed at v1.0) |

**Tasks 1–9 are the critical path before I can start meaningful work.** Saiful, expect to spend a 1–2 hour focused block on these.

## Cost — what Saiful pays upfront

Local-first development pulls most cloud cost into W9 onward:

| Item | Cost | When |
|---|---|---|
| Apple Developer (annual) | $99 | *already paid* |
| Google Play Console (one-time, at v1.0) | $25 | W14+ |
| Huawei Developer (free) | $0 | v1.1 |
| Saiful's server (assumed already owned) | $0 | W1+ |
| Cloudflare (incl. Tunnel) | $0 (free tier) | W1 |
| OpenRouter starter | $50 (consumed during dev) | W1 |
| Anthropic API initial credit | $100–200 | W1 |
| Resend | $0 (free tier) | W1 |
| Sentry | $0 (free tier) | W1 |
| PostHog | $0 (free tier) | W1 |
| GCP (pay-as-you-go) | ~$200/mo at MVP scale | W9+ |
| Supabase Cloud Pro | $25/mo | W9+ |
| Twilio (v1.0+) | $50–100/mo | W14+ |
| RevenueCat (v1.0+) | $0 (until $10K MTR) | W14+ |
| Azure Speech (v1.0+) | $20–50/mo | W14+ |
| Domain renewal (annual) | ~$20/yr | W1 |
| Lawyer initial retainer | $1,000–3,000 | W6–9 |
| **Estimated total pre-alpha (W1)** | **~$170–270** | upfront |
| **Estimated W1–W8 monthly burn (mostly LLM)** | **~$50–150/mo** | dev phase |
| **Estimated W9+ alpha-phase monthly burn (LLM + GCP + Supabase)** | **~$300–600/mo** | post-migration |
| **v1.0 launch additional ($ for translation, $ for marketing)** | **~$30–50K** | W14+ |

Net savings from local-first: **~$400–600** across the dev phase.

Numbers are illustrative — adjust to real provider quotes.

## Cross-references

- Tier 1 / Saiful-only tasks: [`you_do_i_do.md`](you_do_i_do.md)
- Timeline that depends on these: [`timeline.md`](timeline.md)
- What costs scale at growth: [`docs/initial_specs/08_tech/hosting.md`](../08_tech/hosting.md)
