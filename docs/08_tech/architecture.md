# Architecture

System shape, data flows, services. **This doc mirrors the running Alpha
stack** — `melehost` (Ubuntu Linux on the LAN) running a Docker Compose
stack reached through a Cloudflare Tunnel. The Cloud Run + Supabase
shape that earlier drafts of this doc described is the **MVP target**
and is listed at the bottom under "Not yet delivered".

## What's running today

```
┌────────────────────────────────────────────────────────────────────────┐
│  MOBILE (Flutter)                                                      │
│  iOS Alpha (TestFlight, on-device build 0.1.0+24 as of AT:R29)         │
│                                                                        │
│  • Riverpod state                                                      │
│  • Locally-stored bearer (anonymous + claimed users)                   │
│  • REST + SSE client against api-alpha.agenticmarketintel.ai           │
│  • Sign in with Apple (real client wiring)                             │
└────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ↓ HTTPS / Bearer JWT
                ┌─────────────────────────────────────────┐
                │  Cloudflare Edge (TLS termination)      │
                │  api-alpha.agenticmarketintel.ai        │
                └─────────────────┬───────────────────────┘
                                  ↓ Cloudflare Tunnel
┌─────────────────────────────────────────────────────────────────────────┐
│  melehost — Ubuntu Linux, LAN 192.168.20.59                             │
│  Docker Compose stack in ~/ami_trade:                                   │
│  ┌────────────────────────┐  ┌────────────────────────┐                 │
│  │  ami_api_alpha         │  │  ami_postgres          │                 │
│  │  FastAPI + Uvicorn     │←→│  Postgres 16           │                 │
│  │  16 routers, 60+ routes│  │  18 tables (Alembic)   │                 │
│  └────────────────────────┘  └────────────────────────┘                 │
│  ┌────────────────────────┐  ┌────────────────────────┐                 │
│  │  ami_redis             │  │  ami_tunnel            │                 │
│  │  (idempotency, rate    │  │  Cloudflare connector  │                 │
│  │  limits — not yet      │  │  (token mode)          │                 │
│  │  enforced)             │  │                        │                 │
│  └────────────────────────┘  └────────────────────────┘                 │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ↓ HTTP (LAN)
┌─────────────────────────────────────────────────────────────────────────┐
│  vLLM host — Ubuntu Linux, LAN 192.168.20.74:8000                       │
│  Serving model `ami-llm` (Gemma 4 31B, NVFP4 quantized, 262k context)   │
│  Single hosted model — tier-routing is a no-op while vLLM is preferred  │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ↓ (fallback only — gateway preference order)
┌─────────────────────────────────────────────────────────────────────────┐
│  Anthropic API (fallback) — Claude (dated alias) per tier               │
│  Used only when vLLM is unreachable; deterministic mock provider sits   │
│  one level below as the final fallback                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

Code transport: rsync from Mac via [`/promote-to-alpha`](../../.claude/commands/promote-to-alpha.md). No Git remote on melehost; the Mac → melehost path is the only one. Container is rebuilt each promotion via the entrypoint.

## Backend services

Every shipped service lives in `backend/app/services/`. Top-of-file
docstrings are the canonical descriptions; this table is the directory.

| Service | File | Owns |
|---|---|---|
| **LLM Gateway** | `llm_gateway.py` | Provider-agnostic interface. Preference order `vllm > anthropic > mock`. SSE token streaming. Emits an `llm_audit` row per call. |
| **Tier Policy** | `tier_policy.py` | `pick_tier(plan, agent_id) → cheap|mid|premium`. PM is always premium regardless of plan (safety floor). Tier-to-model mapping is a no-op while vLLM serves a single model. |
| **Auth Service** | `auth_service.py` | Anonymous-first user creation, magic-link + Apple Sign-In claim flow. Mints the bearer JWT. Honours `device_user_id` only when the caller proves possession (A2 audit fix). |
| **OIDC Verifier** | `oidc_verifier.py` | Validates Apple identity tokens (JWKS fetch, signature, audience, nonce). |
| **Mandate Store** | `mandate_store.py` | Versioned read/patch on `mandates`. Each PATCH writes a new JSONB-snapshot row and emits a `mandate_edit` journal entry with before/after. |
| **Overlay Store** | `overlay_store.py` | Per-(user, agent) overlay versions on `user_overlays` + the `overlay_edit_counts` lifetime cap. |
| **Brief Engine** | `brief_engine.py` | The propose/accept/reject flow for Brief Your Agent. Enforces the PM safety floor + off-role sniff + mandate-compliance check **server-side** — the LLM can refuse, but the engine has the last word. |
| **Room Runner** | `room_runner.py` | The 12-agent debate orchestrator. Streams `AgentMessage` events as an async iterator. Runs as a background task — client disconnect does not cancel the run. Calls `check_mandate_compliance()` on the PM verdict before persistence. |
| **Sim Engine** | `sim_engine.py` | Postgres-backed portfolio + pluggable market-data provider. Delegates to the same `check_mandate_compliance()` as Brief and Room before trade execution. |
| **Concierge Engine** | `concierge_engine.py` | Drives the onboarding interview (V0 scripted today; LLM-driven swap-in noted in the file). Derives the initial mandate from session answers. |
| **Agent Runner** | `agent_runner.py` | 1-on-1 chat orchestration. Composes base prompt + mandate overlay + user overlay; streams agent reply via SSE. Persists each turn to `one_on_one_messages`. |
| **Journal Store** | `journal_store.py` | Append + list + soft-delete + restore on `journal_entries`. Used by Room (on completion), Brief (on accept), Sim (on trade), Mandate Store (on edit), and direct mobile writes. |
| **Lessons Service** | `lessons_service.py` | Lesson catalogue, per-(user, lesson) progress, quiz grading. Triggers agent activation when an agent-unlock lesson is passed. |
| **AI Coach Service** | `ai_coach_service.py` | Knowledge-base Q&A search (FAQs, agent explainers). **Distinct from Brief Engine** — this is a pre-authored content service, not the conversational overlay editor. |
| **Daily Challenge Service** | `daily_challenge_service.py` | Today's challenge, per-date, per-id, list. Static manifest today; DB-backed catalogue is deferred. |
| **Glossary Service** | `glossary_service.py` | Localised term tooltips per locale (`en`, `ar`, `ms`). |
| **Market Data + Fundamentals** | `market_data.py`, `fundamentals.py` | Yahoo via `yfinance` with deterministic mock-walk fallback. `USE_REAL_MARKET_DATA=true` on melehost. |
| **Watchlist Store** | `watchlist_store.py` | Per-user ticker watchlist + notes. |
| **Feedback Store + Bug Attachments** | `feedback_store.py`, `bug_attachments.py` | In-app bug reports + optional photo attachment; `assigned_branch` coordination for parallel `/fix-bugs` sessions. |
| **Audit** | `audit.py` | Middleware-level `http_audit` writer + gateway-level `llm_audit` helper. Auth headers scrubbed before the row is written. |
| **Session Store** | `session_store.py` | In-memory onboarding session state (lives for the duration of a session; no `OnboardingSession` table). |
| **Email Service** | `email_service.py` | Magic-link delivery — currently returns the code in the response body in dev mode so we can copy-paste without a real SMTP route. Production SMTP wiring is an open Alpha carry-over. |
| **Coach Engine** | `coach_engine.py` | Thin shim — re-exports `BriefEngine` symbols under the legacy `Coach*` names so the deprecated `/v1/coach/*` routes keep working. Slated for removal after two TestFlight cycles past AT:R27. |

## Key data flows

### 1. Convene the Room

```
User taps "Convene" on NVDA
     ↓
Mobile → POST /v1/room/stream  (Bearer in header; body: {user_id, ticker, locale})
     ↓
API verifies bearer; checks body_user_id == bearer.user_id (A6 audit fix)
     ↓
RoomRunner.start_run() creates a room_runs row (status='running') and
returns run_id immediately, set as X-Room-Run-Id response header
     ↓
SSE body opens; RoomRunner runs as a background task — client
disconnect does not cancel the run
     ↓
Background task executes (scripted V0 today; LLM-driven swap-in ready):
  • 4 Analysts (fundamental / sentiment / news / technical)
  • Bull + Bear researchers
  • Research Manager
  • Trader
  • 3 Risk Debators
  • Portfolio Manager (always premium tier; safety floor uncoachable)
     ↓
Each agent message → llm_audit row + SSE event:
   event: agent_token | phase_change | agent_complete
     ↓
PM verdict → check_mandate_compliance() (deterministic; never short-circuited)
     ↓
On terminal state (regardless of SSE connectivity):
  • room_runs.transcript + verdict + status persisted
  • journal_entries row appended (entry_type='room_run')
  • Push hook fires (TODO B1 — currently logs `room_push_stub`)
     ↓
Mobile renders progressively from SSE; on disconnect, GET /v1/room/{run_id}
to fetch final state
```

### 2. Brief Your Agent

```
User opens Brief for Bear Researcher
     ↓
Mobile → POST /v1/brief/start  {user_id, agent_id: 'bear_researcher', mode, locale}
     ↓
BriefEngine.open_session() composes:
  • The mandate-at-start snapshot (mandate_used)
  • The current active overlay version (if any) for {user, agent}
  • Opening message
     ↓
Returns BriefStartResponse {session, current_overlay, opening_message}
     ↓
User chats; Mobile → POST /v1/brief/message  (SSE stream of token events)
     ↓
When user is ready: Mobile → POST /v1/brief/propose
     ↓
BriefEngine.propose():
  • Drafts a candidate overlay_addition + plain_english summary
  • Runs PM-safety / off-role / mandate-compliance pre-checks
  • Returns BriefProposal or BriefRefusal (explicit, structured)
     ↓
Mobile shows diff card → user taps Accept / Reject
     ↓
On Accept → POST /v1/brief/accept  {session_id, proposal_id}
     ↓
BriefEngine.accept():
  • Re-runs safety-floor compliance (last word)
  • Mints a new UserOverlay version, bumps overlay_edit_counts.count
  • Appends journal_entries (entry_type='agent_coach') with overlay snapshot
  • Returns the new overlay
     ↓
Next call to bear_researcher (Room or 1-on-1) composes the new overlay
into its prompt
```

### 3. Anonymous-first onboarding + claim

```
First app launch
     ↓
Mobile → POST /v1/auth/anon  {device_user_id, locale, timezone}
     ↓
AuthService.ensure_anonymous() returns {user, token, is_new}
  • is_new=True if device_user_id was unknown OR caller didn't prove possession (A2 fix)
     ↓
Mobile stores bearer locally; → POST /v1/onboarding/start (Bearer attached)
     ↓
ConciergeEngine creates an in-memory session (no OnboardingSession table);
SessionStore holds {session_id → state}
     ↓
User answers questions via POST /v1/onboarding/answer
   • State machine advances; mandate-in-progress accumulates in memory
     ↓
At end → POST /v1/onboarding/readback/confirm
   • Mandate snapshot persisted to mandates table (version=1, is_current=TRUE)
   • User now has a real mandate
     ↓
Claim flow (any time after this point):
   Mobile → POST /v1/auth/apple  (Apple identity token)
            OR  /v1/auth/magic_link/{start,verify}
     ↓
   AuthService claims the SAME user_id (mandate + journal + portfolio
   survive). users.claimed_at set; users.email / apple_id / display_name
   populated from OIDC claims.
     ↓
   ** Trial activation on claim is NOT YET WIRED ** — D-039 promises a
   7-day Trader trial; users.trial_started_at/trial_expires_at remain
   NULL on the normal claim path. Admin grant route is the only path
   that populates them today. Backlog: project_plan.md BL3.
```

### 4. 1-on-1 with an agent

```
Mobile → POST /v1/agents/one_on_one/start  {agent_id, user_id}
     ↓
AgentRunner.open_one_on_one() composes:
  • Base agent prompt
  • Mandate overlay (from resolve_mandate)
  • User overlay (active version, if any)
     ↓
Returns OneOnOneSession (in-memory session; one_on_one_messages
captures durable turns)
     ↓
Mobile → POST /v1/agents/one_on_one/message  (SSE stream)
     ↓
For each turn:
  • User message → one_on_one_messages row (role='user')
  • LLM gateway call → llm_audit row
  • Agent reply streamed token-by-token via SSE
  • Final reply → one_on_one_messages row (role='agent')
     ↓
On session end (timeout or explicit close):
  • journal_entries row appended summarising the session
```

### 5. Sim trade

```
Mobile → POST /v1/sim/submit  {user_id, ticker, side, quantity, stop?, target?}
     ↓
SimEngine:
  • Quote check via market_data.py (Yahoo, mock fallback)
  • check_mandate_compliance() — same deterministic check used by Room + Brief
  • Refuse if violations; else create sim_trades row (status='open') + update
    sim_portfolios.current_cash and sim_holdings
     ↓
journal_entries row appended (entry_type='sim_trade')
     ↓
Later: GET /v1/sim/trades/{user_id}/evaluate flags trades whose stop/target
hit current quotes (without closing); POST /trades/{user_id}/close realises
P&L into sim_trades.realised_pnl + sim_portfolios.current_cash
```

## Streaming substrate

**SSE is the only delivered streaming substrate.** Every streaming
endpoint (`/v1/room/stream`, `/v1/brief/message`,
`/v1/agents/one_on_one/message`, `/v1/llm/translate`) opens a long-lived
HTTP response and emits `event: <type>\ndata: <payload>\n\n` blocks.

Room runs additionally return `run_id` in the `X-Room-Run-Id` header
before the SSE body starts, so a client that disconnects mid-stream
(phone sleep, LTE handoff, Cloudflare ~100s idle timeout) can reconnect
via `GET /v1/room/{run_id}` and pick up the final state.

Supabase Realtime is the **MVP target** — see "Not yet delivered".

## Observability

What actually fires in Alpha:

- **structlog** — structured log lines from API + workers. Visible via `docker logs ami_api_alpha`.
- **`llm_audit`** — every LLM gateway call (provider, tier, latency, prompt + response, error).
- **`http_audit`** — every inbound HTTP request (method, path, status, latency, truncated body). Auth headers scrubbed at middleware.
- **`subscription_events`** — plan / credit / trial / suspension audit trail.

Sentry / Cloud Logging / OpenTelemetry / PostHog are **MVP targets** —
see "Not yet delivered".

## Not yet delivered

Specced in earlier drafts of this doc but **not running in Alpha**.

### Hosting + infra

- **GCP Cloud Run + Supabase Cloud** — the migration target (timeline W9–10). Today: melehost Docker Compose.
- **Supabase Realtime channels** for Room run streaming. Today: SSE only.
- **Supabase RLS policies** — placeholder migration (`a4c7e9d10001`) exists but no policies are active. Today's backend runs single-trusted; RLS lands when Supabase plugs in.
- **Redis-backed rate limits + idempotency** — `ami_redis` is in the Compose stack but not yet wired into request handlers. Rate limits are advisory in `api_design.md`; backend enforcement is a B-tier follow-up.

### LLM provider variety

The MVP gateway spec called for OpenRouter aggregation across Anthropic + OpenAI + Google + DeepSeek + xAI. Today: on-prem vLLM Gemma 4 31B is the primary; Anthropic is the fallback; mock provider is the final fallback. **Arabic-to-Gemini routing (D-048) is specced but the GoogleProvider class doesn't exist yet** — `_pick_provider()` has the locale parameter but ignores it.

### Background jobs

None of these run in Alpha. Cloud Scheduler + Cloud Run Jobs are MVP scope.

| Specced job | Status |
|---|---|
| `generate_briefings` (morning briefing) | Deferred to MVP — see Stream 3 in project_plan.md |
| `check_mandate_drift` (daily for paid, weekly for free) | Deferred — drift detection is not wired |
| `streak_rollover` | Deferred — streaks derived on read from `lessons_progress` |
| `credit_refresh` (monthly anniversary) | Deferred — period-reset counters not yet on `users` |
| `cleanup_expired_anon_sessions` | Deferred — onboarding sessions are in-memory (no table) |
| `cleanup_old_journal` (Floor Pass 30-day retention) | Deferred — soft-deleted rows currently stay forever |
| `cache_warmup_lessons` | Deferred — lessons fit in memory at Alpha tester count |
| `llm_cost_reconciliation` | Deferred — vLLM is on-prem, costs are fixed |

### Third-party SaaS integrations

None of these are wired in Alpha — every line in the third-party
service list of earlier drafts is MVP scope.

| Specced integration | Status |
|---|---|
| RevenueCat | Test mode only; no webhook handler exposed under `/v1/billing` |
| OneSignal (push) | Deferred — push is a `room_push_stub` log line today |
| Twilio (SMS OTP) | Deferred — magic-link is email-only |
| Resend (email) | **Carry-over from AT:R29 — pick a working SMTP route (Gmail App Password or Resend HTTP) for external Beta.** Dev mode returns the code in-band today. |
| Azure Speech / ElevenLabs (TTS) | Deferred — daily briefing TTS is MVP |
| PostHog (analytics + feature flags) | Deferred — no event analytics yet |
| Sentry | Deferred — `structlog` covers Alpha triage |
| Cloudflare (WAF) | Deferred — Cloudflare Tunnel is the only CF piece wired today (TLS at edge, no WAF rules) |

### Specced features that haven't shipped

- **Morning briefings** — feature + delivery + TTS audio; deferred to MVP Stream 3.
- **Mandate drift alerts** — detection job + dedicated alerts table; deferred.
- **Streaks + leaderboards** — derived today; first-class infra is Beta+.
- **Promo offers + redemptions** — deferred to MVP billing.
- **GDPR/PDPL account deletion + export** — deferred to MVP.

## Cross-references

- Hosting / promotion protocol: [`hosting.md`](hosting.md), [`../10_delivery/promotion_protocol.md`](../10_delivery/promotion_protocol.md)
- LLM routing detail: [`llm_routing.md`](llm_routing.md)
- DB schema: [`data_model.md`](data_model.md)
- API endpoints: [`api_design.md`](api_design.md)
- Auth flow: [`auth.md`](auth.md)
- Backend modes (Alpha / Beta / MVP): [`backend_modes.md`](backend_modes.md)
- TradingAgents integration internals: [`tradingagent_integration.md`](tradingagent_integration.md)
- Project plan + backlog: [`../10_delivery/project_plan.md`](../10_delivery/project_plan.md)
