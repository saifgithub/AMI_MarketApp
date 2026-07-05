# Timeline — 12 weeks to Stealth Alpha

12 calendar weeks. Sequential by week, with parallel content workstream.

## Calendar

| Week | Engineering | Content / ops |
|---|---|---|
| **W1** | Project setup: Flutter shell, hex theme. **Local dev stack on Saiful's server** via Docker Compose (Postgres + self-hosted Supabase + FastAPI + TradingAgents + Redis). Cloudflare Tunnel for HTTPS callbacks. | Saiful: open Apple Dev (done), Cloudflare, OpenRouter, Anthropic/OpenAI/Google AI keys, Resend, Sentry, PostHog. Domain DNS routed through Cloudflare. Server access confirmed. |
| **W2** | Auth: anonymous-first session + self-hosted Supabase Auth + Apple Sign-In + Email magic-link. JWT validation middleware. | Begin lesson 1–10 draft (Foundations track). Saiful reviews drafts. |
| **W3** | Onboarding: Concierge conversation engine (cheap-tier LLM with structured outputs). Mandate schema + creation API. | Lessons 11–30. |
| **W4** | TradingAgents containerised. Mandate overlay generator wired. First end-to-end 1-on-1 working: user → Bear Researcher → response. | Lessons 31–50. Agent Academy module spec drafted (one per agent). |
| **W5** | All 12 agents responding via 1-on-1. Streaming responses via Supabase Realtime. Quick-1-on-1 bottom sheet. | Agent Academy modules 1–6 drafted. Lessons 51–70. |
| **W6** | Convene the Room v1: full TradingAgentsGraph orchestration. Matrix Console streaming. Verdict card. PM compliance check function. | Agent Academy modules 7–12 drafted. Lessons 71–90. |
| **W7** | Brief Your Agent: conversational + diff card + version save. Safety floor on PM (both prompt + deterministic check). | Lessons 91–100. Agent Academy modules 1–6 reviewed. |
| **W8** | Sim portfolio + trade ticket + PM compliance pre-check + Decision Journal (transcripts, search, replay). | Daily challenge generator. Agent Academy modules 7–12 reviewed. Saiful: open GCP, Supabase Cloud, RevenueCat (or defer). |
| **W9** | Concierge as personal assistant: tools (search_lessons, search_journal, schedule_briefing, set_reminder, mute_agent, route_to_agent). **GCP migration starts**: provision via Terraform (Cloud Run + Supabase Cloud project + Secret Manager + Cloud Scheduler). | Privacy Policy + ToS first draft. Halal screening universe data sourced. |
| **W10** | Floor home — static honeycomb with 12 agents + Concierge centre + briefing card + mandate health strip + watchlist signals. **GCP migration completes**: `pg_dump` → Supabase Cloud restore, backend deploy to Cloud Run, DNS cutover, smoke tests. Local stack stays warm as fallback. | Saiful: lawyer reviews legal docs. |
| **W11** | Agent Academy hub + lesson player + AI-tutor wrapper + daily challenges + streaks + reputation. Mandate Drift Alerts (daily email). | Polish: bug fixes, regression. Splash marketing page at trade.agenticmarketintel.ai. |
| **W12** | TestFlight build (pointing at GCP). App Store Connect submission (iOS app review). | Soft-launch comms to Founders cohort (10–20 personal invites first, then HN/Twitter post when stable). **ALPHA LAUNCH.** |

### Local-first development (W1–W8)

The first 8 weeks run entirely on Saiful's server with Cloudflare Tunnel exposing it at `api-dev.agenticmarketintel.ai` over HTTPS. This:
- Saves ~$400–600 in GCP burn during development
- Enables instant iteration (no deploy delays)
- Forces cloud-portability discipline (every interface must work locally + on GCP)
- Lets us validate the full stack architecturally before committing to managed services

External APIs (LLM providers, Resend, Sentry, etc.) are called from local just as they will be from Cloud Run. No code change required for the migration — only env-var swaps.

### GCP migration (W9–W10)

| Day | Task | Effort |
|---|---|---|
| 1 (W9) | Provision GCP via Terraform | 1d |
| 2 (W9) | `pg_dump` local → restore into Supabase Cloud. Verify row counts. | 1d |
| 3 (W9) | Deploy backend containers to Cloud Run. Smoke test via curl. | 1d |
| 4 (W10) | DNS cutover (Cloudflare flips from tunnel to Cloud Run) | 0.5d |
| 5 (W10) | Mobile build with updated `API_BASE_URL` → fresh TestFlight. Final smoke. | 0.5d |

Local stack stays running as fallback for 48 hours post-cutover. Founders never see your server — by week 12 they hit GCP, which is required for PDPL/GDPR compliance once real user data exists.

## Critical-path dependencies

```
W1: Accounts opened
   ↓
W1-2: Infrastructure ready
   ↓
W2-3: Auth + Onboarding (depends on infra)
   ↓
W4: First agent end-to-end (depends on auth + onboarding + TradingAgents)
   ↓
W5-6: All 12 agents + Convene (depends on first agent working)
   ↓
W7: Brief Your Agent (depends on agents)
   ↓
W8-10: Surface features — Sim, Journal, Concierge, Floor home
   ↓
W11: Polish + Drift + Streaks + Academy
   ↓
W12: Submission + Launch
```

## Parallel content workstream

Throughout weeks 2–11, Claude drafts lessons + Academy modules. Saiful reviews on a rolling basis. By end of W11, all 100 lessons + 12 modules are reviewed and integrated.

Lesson cadence target: **~10 lessons per week × 10 weeks = 100 lessons.** Each lesson is ~500 words. Average drafting time: 30 min per lesson. Review time: 15 min per lesson.

## Buffers & slack

- **W11 polish week** is the primary buffer. If we're behind by W10, we cut polish (e.g., simpler honeycomb), not features.
- **App Store review** typically takes 1–3 days for a finance-adjacent app. We submit W11 to give 2-week buffer before W12 launch.
- **If a week slips**: cut one thing from the Agent Academy modules (e.g., the Predict-the-Call exercise simplifies to a quiz) before cutting from Tier 1 (12 agents, Brief Your Agent, Convene).

## Daily rhythm (suggestion)

**Saiful's day** (rough): 1–2 hour-block focus sessions on reviews / decisions / account opens. Most days he can also tackle one ad-hoc bug or design call.

**Claude's day**: a focused build session per project area. We do not multi-task across the codebase — we work in chunks (e.g., "today I'm wiring up the trade ticket + PM compliance pre-check") and finish them.

Weekly sync (Saiful + Claude): review the week's progress, adjust priorities, surface blockers.

## What slips most often

Based on typical solo-founder builds:

| Risk | Likelihood |
|---|---|
| LLM provider API changes mid-build | Medium — mitigation: OpenRouter abstracts |
| App Store review delays | Medium — mitigation: submit W11, have backup TestFlight path |
| Lesson content backlog | Medium — mitigation: Claude can grind 20+ lessons in a focus day if needed |
| Hex animation polish takes longer than budgeted | Low — we ship static honeycomb at alpha anyway |
| Agent quality lower than expected on some prompts | Medium — mitigation: testing budget in W6 for prompt tuning |
| Supabase Realtime quirks | Low — SDK is mature |

## Post-alpha (week 13+)

See [`roadmap.md`](roadmap.md).

## Cross-references

- What's in alpha scope: [`stealth_alpha_scope.md`](stealth_alpha_scope.md)
- Solo + AI responsibility split: [`you_do_i_do.md`](you_do_i_do.md)
- Pre-W1 checklist: [`pre_alpha_checklist.md`](pre_alpha_checklist.md)
- Risks: [`risks.md`](risks.md)
