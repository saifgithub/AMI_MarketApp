# API Design

FastAPI endpoint structure. Each resource has its own router. **This doc
mirrors the routes actually shipped in `backend/app/api/` — not the
aspirational MVP shape.** Routes that were specced but not yet built are
listed under "Not yet delivered" at the bottom; everything in the per-resource
tables below is live in Alpha.

## Conventions

- **Base URL** at Alpha: `https://api-alpha.agenticmarketintel.ai`
- **Base URL** at MVP (target): `https://api.amitrade.app` (or `https://api.agenticmarketintel.ai/trade`)
- **Versioning**: `/v1/...`
- **Auth**: Bearer JWT minted by `auth_service`. Most routers attach `Depends(get_current_user)` at the router level, so every route under that prefix requires a valid bearer. Public routers are called out per-section. Body-level ownership is also enforced where the request carries a `user_id` (the bearer must own it).
- **Content type**: JSON.
- **Errors**: `{ "error": "code", "message": "human-readable" }` with appropriate HTTP status. Error codes table at the bottom.
- **Pagination**: cursor-based (`?cursor=...&limit=...`) on list endpoints that emit it. Not every list route paginates yet — flagged per route.
- **Idempotency**: `Idempotency-Key` header is honoured on POSTs that mint resources (sim trades, account creation). Not yet wired on all create routes — flagged per route.
- **Streaming**: Server-Sent Events (SSE) is the only delivered streaming substrate today. Supabase Realtime channels are specced for MVP — see "Streaming endpoints" below.

## Endpoints by resource

### `/v1/auth`

Public — no bearer required to call. Returns a bearer for subsequent calls.

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/anon` | Bootstrap an anonymous user. Body: `{device_user_id?, locale?, timezone?}`. Returns `{user, token, is_new}`. Returning a previously-issued `device_user_id` only re-attaches to that user if the caller also presents the matching bearer (A2 audit fix); otherwise the call mints a fresh user. |
| POST | `/auth/magic_link/start` | Send a 6-digit code by email. In dev/local env the code is returned in the response body (`debug_code`) for copy-paste. |
| POST | `/auth/magic_link/verify` | Submit the 6-digit code. If the caller already had an anon session, the existing user is claimed (mandate + journal + portfolio survive). |
| POST | `/auth/apple` | Sign in with Apple. Verifies the Apple identity token via OIDC, then claims the caller's anon user or creates a new one. Persists `apple_id`, `email` (if released), and `display_name` (from `full_name` on first sign-in). |
| DELETE | `/auth/session` | Log out — invalidates the current bearer. |
| GET | `/auth/me` | Return the current user record. |

See [`auth.md`](auth.md) for the JWT structure and the anonymous-first claim flow.

### `/v1/onboarding`

Bearer required on all routes. The flow is owned by the **Concierge** — a scripted/LLM-guided interview that ends in a mandate snapshot.

| Method | Path | Purpose |
|---|---|---|
| POST | `/onboarding/start` | Begin a Concierge session. Returns `session_id` + the opening question. |
| GET | `/onboarding/{session_id}` | Resume — return the full session state (questions answered so far, current question, derived mandate-in-progress). |
| POST | `/onboarding/answer` | Submit an answer; advances the conversation. Returns the next question or the readback prompt when the interview is complete. |
| POST | `/onboarding/readback/confirm` | Confirm (or amend) the readback summary. On confirm, the mandate is persisted and the user is moved out of onboarding. |

**Claim path**: account claim happens via `/v1/auth/magic_link/verify` or `/v1/auth/apple` rather than a dedicated `/onboarding/claim` route. The Concierge session and the auth bearer reference the same anonymous user_id, so claiming the user implicitly claims the in-flight onboarding session.

### `/v1/mandate`

Bearer required. `user_id` in the path must match the bearer (403 otherwise).

| Method | Path | Purpose |
|---|---|---|
| GET | `/mandate/{user_id}` | Get the current mandate. Returns a default mandate if none stored. |
| PATCH | `/mandate/{user_id}` | Shallow-merge partial mandate. `compliance.*` merges by key. Bumps `version`, emits a `mandate_edit` journal entry with a full before/after snapshot in `payload`. |

Mandate-version replay relies on the `mandate_edit` journal entries; there is no dedicated versions/rollback API yet (see "Not yet delivered").

### `/v1/agents`

Bearer required. Owns the 1-on-1 conversational interface to each of the 12 agents + Concierge. Routes are scoped under `/v1/agents/one_on_one/*` rather than `/v1/agents/{id}/...`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/agents/one_on_one/start` | Open a 1-on-1 session with a named agent. Returns `OneOnOneSession`. |
| POST | `/agents/one_on_one/message` | Send a user message. Streams the agent's reply as SSE. |
| GET | `/agents/one_on_one/{session_id}` | Fetch a session by id (resume, audit). |

Agent metadata (list-all, single-agent details, past-call history) is sourced client-side from the 12-agent manifest today; backend metadata routes are not yet built (see "Not yet delivered").

### `/v1/brief`  *(legacy alias: `/v1/coach`)*

Bearer required. **Brief Your Agent** was renamed from Coach AT:R27; the legacy `/v1/coach/*` mount is a thin shim that logs a `deprecated_coach_route_used` warning and re-mounts the same handlers — old TestFlight builds keep working. Brief uses a 3-step propose/accept/reject flow with body-param routing (no `{agent_id}` in the path).

| Method | Path | Purpose |
|---|---|---|
| POST | `/brief/start` | Open a Brief session. Body: `{user_id, agent_id, mode, locale, mandate_override?}`. Returns `{session, current_overlay, opening_message}`. |
| POST | `/brief/message` | Stream the agent's reply to the user's message via SSE. Body: `{session_id, history, user_message}`. |
| POST | `/brief/propose` | Engine drafts a candidate overlay from the conversation. Returns a `BriefProposal` with `plain_english` + `overlay_addition`, or refuses (PM safety floor, off-role, mandate violation). |
| POST | `/brief/accept` | User confirms the proposal. Mints a new `UserOverlay` version + writes an `agent_coach` journal entry. Returns the new overlay, or a `BriefRefusal` if the safety floor still blocks. |
| POST | `/brief/reject` | User rejects the proposal. No overlay change. Returns `{ok}`. |
| POST | `/brief/rollback` | Roll the active overlay back to a prior version. Body: `{user_id, agent_id, to_version}`. |
| GET | `/brief/history/{user_id}/{agent_id}` | List overlay versions + edit-count + edits-remaining for the plan. |

**Floor Manager raw markdown editing** (`GET/PUT /brief/.../raw`) was specced but intentionally not built — Floor Manager users go through propose/accept like everyone else so the safety floor + audit trail stay uniform.

### `/v1/room`

Bearer required. Convene the Room — orchestrates the 12-agent debate flow.

| Method | Path | Purpose |
|---|---|---|
| POST | `/room/stream` | Start a Room run on a ticker. Returns the `run_id` in the `X-Room-Run-Id` response header, then streams agent tokens, phase changes, and the final verdict over SSE. The run executes as a background task — client disconnect (phone sleep, LTE handoff) does **not** cancel the run, and journal-write + push fire on completion regardless of SSE connectivity. |
| GET | `/room/{run_id}` | Get the full state of a Room run (poll for completion after reconnect; replay a finished run for the UI without re-running the LLM). |
| GET | `/room/user/{user_id}` | List recent Room runs for the user. |

Cancel and "regenerate visualisation only" replay routes are specced but not yet built (see "Not yet delivered").

### `/v1/sim`

Bearer required. **Single portfolio per user today** — multi-portfolio is a paid-tier feature deferred to MVP. Paths are scoped by `user_id`, not `portfolio_id`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/sim/portfolio/{user_id}` | Get the user's portfolio — cash, holdings, P&L, drawdown. |
| POST | `/sim/portfolio/{user_id}/reset` | Reset the portfolio to starting capital. |
| POST | `/sim/submit` | Submit a sim trade. Body: `{user_id, ticker, side, quantity, stop?, target?, horizon_days?}`. Runs the PM compliance check inline. |
| GET | `/sim/trades/{user_id}` | List trades (open + closed) for the user. |
| POST | `/sim/trades/{user_id}/evaluate` | Evaluate open trades against current quotes — flags stop/target hits without closing them. |
| POST | `/sim/trades/{user_id}/close` | Close a trade. Body: `{trade_id, verdict_ref?}`. Realises P&L. |
| GET | `/sim/quote/{ticker}` | Get a single quote (Yahoo via `yfinance`, with deterministic mock-walk fallback). |
| GET | `/sim/quotes` | Batch quotes — `?tickers=AAPL,MSFT,...`. |

Trade preview (pre-flight compliance + sizing) is currently rolled into `/sim/submit`; a dedicated `/preview` route was specced but not split out yet (see "Not yet delivered").

### `/v1/journal`

Bearer required. Soft-delete model: `DELETE` moves to trash, `restore` brings back, list endpoints exclude trash by default.

| Method | Path | Purpose |
|---|---|---|
| GET | `/journal/{user_id}` | List live entries with filter + pagination. |
| GET | `/journal/{user_id}/trash` | List soft-deleted entries (Floor Manager tier — restore UI). |
| GET | `/journal/{user_id}/entry/{entry_id}` | Get a single entry with the full `payload` snapshot. |
| POST | `/journal/{user_id}/entry/{entry_id}/note` | Update `user_note` and/or `tags`. |
| DELETE | `/journal/{user_id}/entry/{entry_id}` | Soft-delete an entry. |
| POST | `/journal/{user_id}/entry/{entry_id}/restore` | Restore a soft-deleted entry. |
| POST | `/journal` | Create a free-form journal entry (used by the mobile "add note" UI). |

Export (CSV / PDF) was specced for Floor Manager but not yet built (see "Not yet delivered").

### `/v1/lessons`

Bearer required. Owns the Academy lessons + 12-agent unlock progression. Was specced as `/v1/academy` in early docs — `/v1/lessons` is the shipped name.

| Method | Path | Purpose |
|---|---|---|
| GET | `/lessons` | List the lesson catalogue. |
| GET | `/lessons/{lesson_id}` | Get a single lesson — MDX body + metadata. |
| GET | `/lessons/progress/{user_id}` | Aggregate progress summary (lessons complete, current streak). |
| GET | `/lessons/progress/{user_id}/by_lesson` | Per-lesson status list. |
| GET | `/lessons/activations/{user_id}` | List which of the 12 agents the user has unlocked. |
| POST | `/lessons/start` | Mark a lesson as started. |
| POST | `/lessons/quiz` | Submit quiz answers — on pass, the lesson is marked complete and (if it's an agent-unlock lesson) the corresponding agent activates. |

There is no dedicated "complete lesson without quiz" route — completion is driven by `/lessons/quiz`. The Agent Academy modules (per-agent training tracks) live in the same lessons table tagged by agent; no separate `/academy/agents` namespace ships today.

### `/v1/daily_challenge`

Bearer required. Daily-challenge content — split into its own router rather than nested under `/academy`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/daily_challenge/today` | Today's challenge (server clock, respecting user timezone). |
| GET | `/daily_challenge/by_date/{ymd}` | Challenge for a specific date — `ymd` is `YYYY-MM-DD`. |
| GET | `/daily_challenge/by_id/{challenge_id}` | Single challenge by id. |
| GET | `/daily_challenge/all` | List all challenges (admin/debug). |

The submit/attempt endpoint is not yet built — clients capture daily-challenge results via the regular journal create route today (see "Not yet delivered").

### `/v1/ai_coach`

Bearer required. Knowledge-base Q&A service — pre-authored short answers across categories (FAQs, agent explainers, mandate guidance). **Distinct from `/v1/brief`**, which is the conversational overlay editor.

| Method | Path | Purpose |
|---|---|---|
| GET | `/ai_coach/search` | Search Q&A by free text. `?q=...&locale=...`. |
| GET | `/ai_coach/by_id/{qa_id}` | Single Q&A entry. |
| GET | `/ai_coach/by_category/{category}` | All entries in a category. |
| GET | `/ai_coach/categories` | List categories. |

### `/v1/glossary`

Bearer required. Localised glossary entries for in-line term tooltips.

| Method | Path | Purpose |
|---|---|---|
| GET | `/glossary/{locale}` | Full glossary catalogue for a locale (`en`, `ar`, `ms`). |
| GET | `/glossary/{locale}/{term_id}` | Single entry. |

### `/v1/watchlist`

Bearer required. User watchlist for the Floor surface.

| Method | Path | Purpose |
|---|---|---|
| GET | `/watchlist/{user_id}` | List tickers on the user's watchlist with current quote attached. |
| POST | `/watchlist` | Add a ticker. Body: `{user_id, ticker}`. |
| DELETE | `/watchlist/{user_id}/{ticker}` | Remove a ticker. |

### `/v1/feedback`

Public — accepts an optional bearer for owner attribution. Used by the in-app bug-report flow.

| Method | Path | Purpose |
|---|---|---|
| POST | `/feedback` | Submit a bug report / feedback note. Optional multipart attachment (screenshot, log dump). |

### `/v1/llm`

Bearer required. Operational endpoints for the LLM gateway.

| Method | Path | Purpose |
|---|---|---|
| GET | `/llm/status` | Return the active provider (vllm / anthropic / mock) and per-tier model mapping. |
| POST | `/llm/translate` | Translate a payload to a target locale (used by mobile for on-the-fly UI strings). |

### `/v1/admin`

Per-route admin auth — each handler depends on `get_admin`, which validates a separately-issued admin bearer. Operator back-office for the Alpha cohort.

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/users` | List users with summary cols (plan, trial state, last seen, device id). |
| GET | `/admin/users/{user_id}` | Full user record + recent events. |
| PATCH | `/admin/users/{user_id}/plan` | Move a user between plans (free / trader / floor manager). |
| POST | `/admin/users/{user_id}/trial` | Grant a 7-day Trader trial. Populates `users.trial_started_at` + `trial_expires_at`. |
| PATCH | `/admin/users/{user_id}/trial` | Extend / shorten an in-flight trial. |
| POST | `/admin/users/{user_id}/credits` | Grant or deduct credits. |
| POST | `/admin/users/{user_id}/suspend` | Suspend a user. |
| POST | `/admin/users/{user_id}/reinstate` | Un-suspend. |
| GET | `/admin/users/{user_id}/events` | Event timeline (auth events, plan changes, trial grants, suspensions). |

### `/v1/coach` *(deprecated alias — remove after two TestFlight cycles past AT:R27)*

Re-mounts the same handlers as `/v1/brief` and logs a `deprecated_coach_route_used` warning per call. Keeps old TestFlight builds (pre-AT:R27) working through the transition. Do not write new code against this prefix.

## Streaming endpoints

**Today: SSE only.** Supabase Realtime is specced for MVP but not wired yet — every long-running operation currently streams over an HTTP SSE connection.

### Server-Sent Events (SSE) — live today

Used by `/room/stream`, `/brief/message`, and `/agents/one_on_one/message`. Each event is a single `event: <type>\ndata: <payload>\n\n` block. Common event types:

```
event: token
data: <chunk text>

event: agent_token
data: {"agent_id": "bull_researcher", "content": "Strong fundamentals..."}

event: phase_change
data: {"phase": "researchers_to_manager"}

event: verdict
data: {"action": "long", "size_pct": 5, ...}

event: error
data: <short message>

event: done
data: {"chars": 1234}    # or {"run_id": "...", "credit_cost": 1}
```

Room runs additionally return `run_id` in the `X-Room-Run-Id` response header before the SSE body starts. The run executes as a background task, so a client disconnect does not cancel the run — clients resume by polling `GET /v1/room/{run_id}` after reconnect.

### Supabase Realtime — specced for MVP, not yet delivered

The MVP shape was: server publishes to `channel:room_run:{room_run_id}`; mobile subscribes and receives a typed stream:

```json
{ "type": "agent_token", "agent_id": "bull_researcher", "content": "..." }
{ "type": "agent_complete", "agent_id": "bull_researcher", "duration_ms": 4500 }
{ "type": "phase_change", "phase": "researchers_to_manager" }
{ "type": "verdict", "verdict": { ... } }
```

This shape stays in the doc as the target for MVP. Until it's wired, SSE is the only path.

## Rate limits

Per tier, per endpoint, per user. **Not yet enforced server-side** — currently advisory in the docs and respected by the client. Backend enforcement is in the backlog (see B-tier adversarial audit follow-up).

| Endpoint family | Floor Pass | Trader | Floor Manager |
|---|---|---|---|
| `/room/stream` POST | 5/hour | 20/hour | 50/hour |
| `/agents/one_on_one/message` | 60/hour | 300/hour | unlimited |
| `/brief/message` | 30/hour | 300/hour | unlimited |
| `/mandate/{user_id}` PATCH | 10/day | 50/day | unlimited |

Once enforced: returns 429 with `Retry-After` header on exceed.

## Error codes

| Code | Meaning |
|---|---|
| `auth_required` | 401 — no JWT |
| `auth_invalid` | 401 — invalid JWT |
| `forbidden` | 403 — auth OK but the bearer doesn't own the path/body `user_id` |
| `insufficient_credits` | 402 — not enough credits for operation; client should show buy-credits modal |
| `mandate_violation` | 422 — proposed action violates mandate |
| `rate_limited` | 429 — once rate-limiting is enforced |
| `provider_error` | 502 — LLM provider failure (transient; retry) |
| `not_found` | 404 |
| `validation_failed` | 422 — invalid input |
| `internal_error` | 500 |

## Observability

Every API request emits:
- `request_id` header (echoed in response)
- structured log line via `structlog`
- `llm_audit` row for routes that hit the LLM gateway (provider, tier, latency, tokens)
- `http_audit` row for sensitive routes (auth, admin, mandate edits)

Cloud Logging / OpenTelemetry / Sentry are specced for MVP — not wired in Alpha.

## Not yet delivered

Specced in earlier drafts of this doc but **not implemented in Alpha**. Each entry has either a backlog reference or a "deferred to phase X" note.

### Routes that exist on paper but not in code

| Specced route | Status | Note |
|---|---|---|
| `POST /onboarding/claim` | Replaced | Claim happens via `/auth/magic_link/verify` or `/auth/apple`; the anon user_id survives the claim, which implicitly claims the in-flight onboarding session. No dedicated route needed. |
| `POST /onboarding/abandon` | Dropped | Sessions expire on inactivity; no explicit abandon needed for Alpha. Re-evaluate at MVP. |
| `GET /agents` | Deferred to MVP | Mobile uses a client-side 12-agent manifest today. Server-side list needed once activation state varies per-user beyond what `/lessons/activations/{user_id}` provides. |
| `GET /agents/{agent_id}` | Deferred to MVP | Agent details (current overlay, past-calls count) are stitched client-side from `/brief/history/...` + journal queries. |
| `GET /agents/{agent_id}/past_calls` | Deferred to MVP | Filter on `/journal/{user_id}` with `agents_involved=<agent_id>` covers this today. |
| `GET /mandate/{user_id}/versions` | Deferred | `mandate_edit` journal entries carry full before/after payload — replay works without a dedicated versions route. |
| `GET /mandate/{user_id}/versions/{version}` | Deferred | Same — fetch the `mandate_edit` entry. |
| `POST /mandate/{user_id}/audit/resolve` | Deferred | Mandate-violation resolution flow is not yet a feature; mandates currently only emit warnings via the safety floor at trade-time. |
| `POST /mandate/{user_id}/rollback/{version}` | Deferred | Implementable via `PATCH /mandate/{user_id}` with the old snapshot — no dedicated rollback route yet. |
| `GET / PUT /brief/{agent_id}/raw` | Cut | Floor Manager users go through propose/accept like everyone else — uniform safety floor + audit trail. Decision: do not build. |
| `POST /room/{run_id}/cancel` | Deferred | Background-task cancellation needs Postgres-side signalling; not yet wired. Run is unkillable in Alpha. |
| `POST /room/{run_id}/replay` | Deferred | `GET /room/{run_id}` already returns the full transcript for re-render. A no-LLM replay route is unnecessary. |
| `POST /sim/portfolios/{id}/trade/preview` | Deferred | Inline compliance check inside `/sim/submit` covers preview today. Split into a separate `/preview` once mobile needs to show "would this be allowed?" before commit. |
| `POST /sim/portfolios` (create) | Deferred to MVP | Multi-portfolio is a Floor Manager feature; Alpha is single-portfolio-per-user. |
| `POST /journal/entries/{id}/export` | Deferred to MVP | Floor Manager CSV / PDF export. Not in Alpha scope. |
| `POST /lessons/{lesson_id}/complete` | Replaced | Completion is driven by `/lessons/quiz` (pass → complete). No separate "mark complete without quiz" route. |
| `GET / POST /academy/agents/*` | Deferred | Per-agent training modules live in the same lessons table tagged by agent. No separate namespace today. |
| `POST /daily_challenge/attempt` | Deferred | Attempts are captured via the regular journal create route today. Dedicated route to be added when daily-challenge tracking gets richer (streaks, leaderboards). |

### Entire namespaces specced for MVP

| Namespace | Status | Note |
|---|---|---|
| `/v1/concierge/*` (`/message`, `/thread`, `/tools/{name}`) | Deferred to MVP | Concierge runs today inside the onboarding flow (`/onboarding/*`) and inside 1-on-1 (`/agents/one_on_one/*` with `agent_id=concierge`). A separate Concierge namespace with persistent thread + tool-call hooks is MVP scope. |
| `/v1/billing/*` (`/plan`, `/credits`, `/credits/purchase`, `/webhook/revenuecat`, `/offers`) | Deferred to MVP | Plan + credits are read off the user record today (no dedicated billing API). RevenueCat webhook is wired in test mode but not exposed under this prefix. |
| `/v1/account/*` (`/account`, `/account/delete`, `/account/export`) | Deferred | `GET /auth/me` covers profile reads. Patch-display-name is done via `/mandate/{user_id}` patch (mandate carries `display_name`). Delete + GDPR/PDPL export are MVP scope. |

## Cross-references

- Data model: [`data_model.md`](data_model.md)
- Auth + JWT structure: [`auth.md`](auth.md)
- Architecture overview: [`architecture.md`](architecture.md)
- Backend modes (Alpha vs MVP): [`backend_modes.md`](backend_modes.md)
- Payment webhook details: [`payments.md`](payments.md) *(specced — see `/v1/billing` deferred)*
