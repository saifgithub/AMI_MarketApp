# API Design

FastAPI endpoint structure. Each resource has its own router.

## Conventions

- **Base URL** at MVP: `https://api.amitrade.app` (or `https://api.agenticmarketintel.ai/trade`)
- **Versioning**: `/v1/...`
- **Auth**: Bearer JWT from Supabase. Validated via middleware on every request.
- **Content type**: JSON.
- **Errors**: `{ "error": "code", "message": "human-readable" }` with appropriate HTTP status.
- **Pagination**: `?cursor=...&limit=...` (cursor-based, not offset).
- **Idempotency**: `Idempotency-Key` header on POSTs that create resources.
- **Streaming**: Server-Sent Events (SSE) or Supabase Realtime channel for long-running operations.

## Endpoints by resource

### `/v1/onboarding`

| Method | Path | Purpose |
|---|---|---|
| POST | `/onboarding/start` | Begin anonymous onboarding; returns session_id |
| POST | `/onboarding/answer` | Submit an answer to a question; advances conversation |
| GET | `/onboarding/state` | Get current onboarding state for resuming |
| POST | `/onboarding/readback` | Get the readback summary |
| POST | `/onboarding/claim` | Convert anonymous session to a claimed user (triggers trial activation) |
| POST | `/onboarding/abandon` | Mark session abandoned |

### `/v1/mandate`

| Method | Path | Purpose |
|---|---|---|
| GET | `/mandate` | Get current mandate (full object) |
| GET | `/mandate/versions` | List version history |
| GET | `/mandate/versions/{version}` | Get a specific past version |
| PATCH | `/mandate` | Edit mandate fields. Body: partial mandate. Triggers audit if hard fields touched. |
| POST | `/mandate/audit/resolve` | Resolve audit violations (liquidate / postpone / override) |
| POST | `/mandate/rollback/{version}` | Rollback to a previous version |

### `/v1/agents`

| Method | Path | Purpose |
|---|---|---|
| GET | `/agents` | List all 12 agents + activation state |
| GET | `/agents/{agent_id}` | Get one agent's details + current overlay |
| POST | `/agents/{agent_id}/one_on_one` | Open a 1-on-1 session |
| POST | `/agents/{agent_id}/one_on_one/{session_id}/message` | Send a message; returns SSE stream |
| GET | `/agents/{agent_id}/past_calls` | List past contributions to journal entries |

### `/v1/coach`

| Method | Path | Purpose |
|---|---|---|
| POST | `/coach/{agent_id}/session/start` | Start a Coach Your Agent session |
| POST | `/coach/{agent_id}/session/{session_id}/message` | Chat with the agent for coaching |
| POST | `/coach/{agent_id}/overlay` | Save a new overlay version |
| GET | `/coach/{agent_id}/overlays` | List version history |
| POST | `/coach/{agent_id}/overlays/{version}/rollback` | Rollback to a version |
| GET | `/coach/{agent_id}/raw` | Get raw overlay markdown (Floor Manager only) |
| PUT | `/coach/{agent_id}/raw` | Update raw overlay markdown (Floor Manager only) |

### `/v1/convene`

| Method | Path | Purpose |
|---|---|---|
| POST | `/convene` | Start a Convene the Room run. Returns `room_run_id`. Server streams via Supabase Realtime. |
| GET | `/convene/{room_run_id}` | Get full state of a Room run |
| POST | `/convene/{room_run_id}/cancel` | Cancel an in-progress run |
| POST | `/convene/{room_run_id}/replay` | Replay a past run (regenerate visualisation; no LLM cost) |
| GET | `/convene/recent` | Recent Room runs for the user |

### `/v1/sim`

| Method | Path | Purpose |
|---|---|---|
| GET | `/sim/portfolios` | List user's sim portfolios |
| POST | `/sim/portfolios` | Create a new portfolio (paid tiers only beyond 1) |
| GET | `/sim/portfolios/{id}` | Get portfolio state — holdings, P&L, drawdown |
| POST | `/sim/portfolios/{id}/trade/preview` | Pre-check a trade — runs PM compliance |
| POST | `/sim/portfolios/{id}/trade` | Submit a sim trade |
| GET | `/sim/portfolios/{id}/trades` | Trade ledger |
| POST | `/sim/portfolios/{id}/reset` | Reset portfolio to starting capital |

### `/v1/journal`

| Method | Path | Purpose |
|---|---|---|
| GET | `/journal/entries` | List with filter, search, pagination |
| GET | `/journal/entries/{id}` | Full transcript |
| PATCH | `/journal/entries/{id}` | Update tags / user_note |
| POST | `/journal/entries/{id}/export` | Export (CSV / PDF) (Floor Manager) |

### `/v1/concierge`

| Method | Path | Purpose |
|---|---|---|
| POST | `/concierge/message` | Send a message to Concierge; returns SSE stream + tool calls |
| GET | `/concierge/thread` | Get the persistent thread (paginated) |
| POST | `/concierge/tools/{tool_name}` | Call a Concierge tool directly (e.g., schedule_briefing) |

### `/v1/academy`

| Method | Path | Purpose |
|---|---|---|
| GET | `/academy/lessons` | List lessons, filter by track / topic / status |
| GET | `/academy/lessons/{id}` | Get a lesson (rendered with AI-tutor wrapper) |
| POST | `/academy/lessons/{id}/complete` | Mark lesson complete |
| POST | `/academy/lessons/{id}/quiz` | Submit quiz answers |
| GET | `/academy/agents` | List the 12 Agent Academy modules |
| GET | `/academy/agents/{agent_id}` | Get one module |
| POST | `/academy/agents/{agent_id}/complete` | Mark module complete → activates agent for Earn Path |
| GET | `/academy/daily` | Get today's daily challenge |
| POST | `/academy/daily/attempt` | Submit attempt |

### `/v1/billing`

| Method | Path | Purpose |
|---|---|---|
| GET | `/billing/plan` | Current plan + entitlements |
| GET | `/billing/credits` | Credit balance + transaction history |
| POST | `/billing/credits/purchase` | (Triggers RevenueCat IAP — actual purchase happens in app) |
| POST | `/billing/webhook/revenuecat` | RevenueCat webhook for subscription events |
| GET | `/billing/offers` | List available offers for this user |

### `/v1/account`

| Method | Path | Purpose |
|---|---|---|
| GET | `/account` | User profile, plan, credits |
| PATCH | `/account` | Update profile (display_name, locale, timezone) |
| POST | `/account/delete` | Request account deletion (30-day GDPR/PDPL flow) |
| GET | `/account/export` | Export all user data (JSON) |

## Streaming endpoints

For long-running operations (Convene the Room, 1-on-1 messages, Coach sessions), responses stream via either:

### Supabase Realtime (preferred for multi-segment streams)

Used for Convene the Room. Mobile subscribes to `channel:room_run:{room_run_id}` and receives:

```json
{
  "type": "agent_token",
  "agent_id": "bull_researcher",
  "content": "Strong fundamentals + technical break..."
}

{
  "type": "agent_complete",
  "agent_id": "bull_researcher",
  "duration_ms": 4500
}

{
  "type": "phase_change",
  "phase": "researchers_to_manager"
}

{
  "type": "verdict",
  "verdict": { ... }
}
```

### Server-Sent Events (for single-stream operations)

Used for 1-on-1 and Coach messages.

```
event: token
data: {"content": "Strong"}

event: token
data: {"content": " fundamentals"}

event: done
data: {"message_id": "...", "credit_cost": 1}
```

## Rate limits

Per tier, per endpoint, per user:

| Endpoint family | Floor Pass | Trader | Floor Manager |
|---|---|---|---|
| `/convene` POST | 5/hour | 20/hour | 50/hour |
| `/agents/.../one_on_one/.../message` | 60/hour | 300/hour | unlimited |
| `/concierge/message` | 60/hour | 300/hour | unlimited |
| `/coach/.../message` | 30/hour | 300/hour | unlimited |
| `/mandate` PATCH | 10/day | 50/day | unlimited |

Returns 429 with `Retry-After` header on exceed.

## Error codes

| Code | Meaning |
|---|---|
| `auth_required` | 401 — no JWT |
| `auth_invalid` | 401 — invalid JWT |
| `forbidden` | 403 — auth OK but RLS forbids |
| `insufficient_credits` | 402 — not enough credits for operation; client should show buy-credits modal |
| `mandate_violation` | 422 — proposed action violates mandate |
| `rate_limited` | 429 |
| `provider_error` | 502 — LLM provider failure (transient; retry) |
| `not_found` | 404 |
| `validation_failed` | 422 — invalid input |
| `internal_error` | 500 |

## Observability

Every API request emits:
- `request_id` header (echoed in response)
- Cloud Logging structured log line
- OpenTelemetry trace
- Sentry breadcrumb on error

## Cross-references

- Data model: [`data_model.md`](data_model.md)
- Auth + JWT structure: [`auth.md`](auth.md)
- Architecture overview: [`architecture.md`](architecture.md)
- Payment webhook details: [`payments.md`](payments.md)
