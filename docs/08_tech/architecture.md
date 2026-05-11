# Architecture

System diagram, data flow, background jobs.

## System diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│  MOBILE (Flutter)                                                      │
│  iOS │ Android-GMS │ Android-HMS (v1.1)                                │
│                                                                        │
│  • Platform-service facade (AuthSvc, BillingSvc, PushSvc, AdsSvc)     │
│  • Riverpod state                                                      │
│  • Supabase client (auth, db reads via RLS, realtime subs)             │
│  • API client (REST to FastAPI)                                        │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                  ┌───────────────┴───────────────┐
                  │                               │
                  ↓ Bearer JWT                    ↓ Anon key (read-only)
┌──────────────────────────────┐    ┌──────────────────────────────────┐
│  FastAPI (Cloud Run)         │    │  Supabase Cloud                  │
│  ─ Auth middleware           │←──→│  • Postgres (RLS)                │
│  ─ Rate limits per tier      │    │  • Auth (Apple/Google/HMS/Email) │
│  ─ Credit ledger             │    │  • Storage (S3-compatible)       │
│  ─ Routes:                   │    │  • Realtime (websockets)         │
│    /agents/*  /mandate/*     │    │                                  │
│    /sim/*     /journal/*     │    │  Postgres tables:                │
│    /concierge/* /coach/*     │    │  users, mandates, agent_runs,    │
│    /lessons/*  /academy/*    │    │  journal_entries, user_overlays, │
│    /billing/webhook (RC)     │    │  credit_transactions, ...        │
└──────────────────────────────┘    └──────────────────────────────────┘
        │                  │
        │ (LLM orchestration)
        ↓                  ↓
┌────────────────────────────┐    ┌─────────────────────────────────┐
│  TradingAgents wrapper     │    │  Concierge service              │
│  (Python module in same    │    │  • Tool-use loop                │
│  Cloud Run service)        │    │  • Lesson search                │
│  • Mandate overlay applied │    │  • Journal queries (via DB)     │
│  • LangGraph orchestration │    │  • Schedule jobs (Cloud Sched)  │
│  • Streams via Realtime    │    │                                 │
└────────────────────────────┘    └─────────────────────────────────┘
        │
        ↓ via OpenRouter + direct keys
┌──────────────────────────────────────────────────────────────────────┐
│  LLM Providers                                                       │
│  • Anthropic (Claude Opus, Sonnet, Haiku)                            │
│  • OpenAI (GPT-5.4, mini, 4o-mini)                                   │
│  • Google AI (Gemini 3 Ultra, Pro, Flash)                            │
│  • DeepSeek, xAI (via OpenRouter)                                    │
└──────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  Background workers (Cloud Run Jobs)                                │
│  • Morning briefing generation (daily, batched per user cohort)     │
│  • Daily challenge generation (per locale, per day)                 │
│  • Mandate Drift detection (daily for paid; weekly for free)        │
│  • LLM cost reconciliation                                          │
│  • Lesson cache warmup                                              │
│  • Streak rollover (midnight per user's timezone)                   │
└─────────────────────────────────────────────────────────────────────┘
        ↑ triggered by Cloud Scheduler (cron) + Pub/Sub

┌─────────────────────────────────────────────────────────────────────┐
│  Third-party SaaS                                                   │
│  • RevenueCat — IAP receipt validation, entitlement state           │
│  • OneSignal — push notifications (wraps APNs/FCM/HMS Push)         │
│  • Twilio — SMS OTP                                                 │
│  • Resend — transactional email                                     │
│  • Azure Speech / ElevenLabs — TTS                                  │
│  • PostHog — product analytics + feature flags                      │
│  • Sentry — crash reporting (Flutter + Python)                      │
│  • Cloudflare — CDN, DNS, WAF                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Key data flows

### 1. Convene the Room

```
User taps "Convene" on NVDA
     ↓
Mobile → API: POST /convene { ticker: "NVDA" }
     ↓
API auth-check, credit pre-flight (8 credits available?)
     ↓
API creates RoomRun row (status: running, debit credits provisionally)
     ↓
API kicks off TradingAgentsGraph with:
  - ticker
  - mandate overlay (per-agent)
  - safety_floor on PM
     ↓
LangGraph runs:
  - 4 Analysts (parallel) — stream their reasoning to Realtime channel
  - Bull + Bear (parallel)
  - Research Manager
  - Trader
  - 3 Risk Debators (parallel)
  - Portfolio Manager
       ↓
     PM safety_floor check (deterministic compliance function)
       ↓
     LLM verdict potentially overridden if non-compliant
     ↓
API persists transcript + verdict to journal_entries table
     ↓
API commits credit debit (was provisional)
     ↓
Mobile receives final via Realtime; renders verdict card
     ↓
Mobile prompts: "Open trade ticket?" / "Save and dismiss"
```

### 2. Coach Your Agent

```
User opens Coach session for Bear Researcher
     ↓
Mobile → API: GET /coach/bear_researcher/session/start
     ↓
API returns:
  - Current base_prompt + mandate_overlay + user_overlay (composed)
  - Past 5 decisions involving Bear (for "Coach from past calls")
     ↓
User chats with Bear via streaming completions
     ↓
At end of session, Bear proposes overlay update (LLM-generated diff)
     ↓
Mobile shows diff card; user taps Accept/Refine/Reject
     ↓
On Accept → POST /coach/bear_researcher/overlay
  - Creates new UserOverlay row (version increment)
  - is_current = TRUE for new row, FALSE for previous
     ↓
Confirmation toast; next agent call uses new overlay
```

### 3. Anonymous-first onboarding

```
App splash → Mobile creates anonymous Supabase session (no user_id)
     ↓
Mobile → API: POST /onboarding/start → returns session_id (server-managed)
     ↓
User chats with Concierge; answers stored against session_id
     ↓
Mandate built incrementally on backend
     ↓
At end: user picks sign-in method
     ↓
Mobile → Supabase: sign in with Apple/Google/HMS/Email/Phone
     ↓
Mobile → API: POST /onboarding/claim
     ↓
API: link session_id → new user_id, promote mandate to permanent
     ↓
API: activate 7-day Trader trial
     ↓
Mobile navigates to Floor home
```

### 4. Morning briefing (overnight batch)

```
Cloud Scheduler fires at 02:00 UTC (well before any user's morning)
     ↓
Cloud Run Job: GenerateBriefings
     ↓
Query: all users with daily_briefing.enabled = TRUE
     ↓
For each user:
  - Compute their "morning" in their tz (e.g., 07:00 Asia/Riyadh = 04:00 UTC)
  - If their morning is within next 4 hours, generate briefing
  - Cache against (user_id, date)
     ↓
For each generated briefing:
  - Render TTS audio (if paid tier)
  - Store audio in Supabase Storage
  - Schedule push/email at user's local morning
     ↓
At user's local morning:
  - OneSignal fires push (if push enabled)
  - Resend fires email (if email enabled)
  - In-app: briefing card refreshes on next Floor view
```

### 5. Mandate Drift Alerts

```
Cloud Scheduler fires daily (for paid) / weekly (for free)
     ↓
Cloud Run Job: CheckDrift
     ↓
For each user, run check_mandate_drift(user, mandate, portfolio):
  - Compute drift signals (beta, concentration, risk-score mismatch, etc.)
  - Return list of triggered alerts
     ↓
If any triggers:
  - Persist DriftAlert rows
  - Surface in next morning briefing
  - Optionally push immediately (Floor Manager real-time threshold)
```

## Streaming agent responses (Realtime)

Convene the Room streams agent reasoning in real-time to the mobile client.

```
API receives Convene request
     ↓
API creates RealtimeChannel for this RoomRun (channel_id = room_run_id)
     ↓
Mobile subscribes to that channel via Supabase Realtime
     ↓
As each agent produces tokens, API publishes to the channel:
  {
    "agent_id": "bull_researcher",
    "type": "token",
    "content": "Strong fundamentals + technical break..."
  }
     ↓
Mobile renders incrementally in the Matrix Console widget
```

Supabase Realtime uses websockets. Falls back to long-poll if blocked.

## Background job catalog

| Job | Cadence | Purpose |
|---|---|---|
| `generate_daily_challenge` | Per locale, midnight | Pre-generate the daily challenge for each locale |
| `generate_briefings` | 02:00 UTC daily | Pre-generate next morning's briefings for all users with `daily_briefing.enabled` |
| `check_mandate_drift` | Daily 03:00 UTC (paid), Weekly (free) | Detect portfolio drift from mandate |
| `streak_rollover` | Per user's local midnight | End/extend streaks based on activity |
| `credit_refresh` | Per user's monthly anniversary | Reset monthly credit allowance |
| `cache_warmup_lessons` | Weekly | Pre-render common lesson wrappings |
| `llm_cost_reconciliation` | Hourly | Reconcile actual LLM bills vs estimated charges (auto-refund overages) |
| `cleanup_expired_anon_sessions` | Hourly | Delete `OnboardingSession` rows older than 24h that never converted |
| `cleanup_old_journal` | Daily (Floor Pass users only) | Trim journal entries older than 30 days for Floor Pass users |

All run on Cloud Run Jobs (containerised, triggered by Cloud Scheduler).

## Observability

- **Cloud Logging** — structured JSON logs from API and workers
- **Sentry** — Flutter crashes + Python exceptions
- **OpenTelemetry traces** — every Convene the Room run is a parent span with each agent call as a child span. Lets us pinpoint which agent is slow on a slow Room run.
- **PostHog** — funnel analytics (onboarding completion, Convene→sim trade conversion, etc.)
- **Custom dashboards** in PostHog or BigQuery (Phase 2) for product metrics

## Cross-references

- Hosting / regions: [`hosting.md`](hosting.md)
- TradingAgents integration internals: [`tradingagent_integration.md`](tradingagent_integration.md)
- DB schema: [`data_model.md`](data_model.md)
- API endpoints: [`api_design.md`](api_design.md)
