# Handover — AMI Trade build session

**Last updated:** 2026-05-12 (end of A2: Concierge → AMI wired on the Floor)

Read this file **first** in any new session. It captures runtime state, what just landed, and a copy-paste prompt to continue.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, 22 commits, no remote yet |
| Latest commit | (this session) A2: Concierge → AMI (post-onboarding, Floor tab) |
| Lines on disk | ~36,200 (PRD ~14.5k, backend ~9.4k, Flutter ~9.9k, content/docs ~2.4k) |

```
$ git log --oneline | head -12
<new>   A2: Concierge → AMI wiring (post-onboarding, Floor tab)
eaed813 Handover #9 — A1 landed, ready to pick up A2
08ab7d9 A1: Convene the Room → AMI wiring
4933b18 W18b: animations selective, tickers user-driven, quiz mandatory, watchlist + skip-to-quiz in Alpha
08c953f W18: curriculum map (Levels 1-8) + merged authoring prompt
9e9a6bf W17: authoring prompt for lessons + daily-challenge bank
b7a092c W16c: Beta = infra-only; TestFlight + everything else in Alpha
dce4954 W16b: pull i18n/TTS/push/daily briefing into Alpha
40929a9 W16: project plan — Alpha → Beta → MVP
496abff W15: slim CLAUDE.md — move conventions detail to docs/
5ad3182 W14b: the AI has a name — AMI
b13b752 W14a: "LLM" is internal-only; users see "AI"
a951499 W13: on-prem vLLM Gemma 4 — app is live
d332860 W12: tier_policy refactor — single source of truth for (plan, agent) → tier
d3acddc W11: Flutter LIVE/MOCK quote-source pill
04ff5ea W10: real market data via Yahoo
259d53d W9: LLM-swap prep + cleanup pass
667616e W8: persistence migration + Supabase-shaped auth scaffold
db89336 W7: Sim Trading + Mandate editor — close the core loop
5239353 W6: Convene the Room
0fcbfc8 W5: Decision Journal + Lessons + Earn Path
9da7f69 W4: Coach Your Agent
665135f Handover docs
97d675c W3: 1-on-1 chat
13349bf W2 onboarding flow
96fbeaf Bootstrap Flutter project
7063050 Day 1: PRD + backend foundation
```

### Backend

| | |
|---|---|
| Process | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` |
| Logs | `tail -f /tmp/ami-backend.log` |
| Restart | `scripts/run_dev.sh backend` |
| LAN | `http://192.168.20.9:8000` |
| Health | `curl http://localhost:8000/v1/health` |
| Routes | `/v1/health`, `/v1/auth/*`, `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/coach/*`, `/v1/journal/*`, `/v1/lessons/*`, **`/v1/llm/status`**, `/v1/mandate/*`, `/v1/room/*`, `/v1/sim/*` |
| Tests | `pytest backend/tests/unit/ -q` → **140 passed, 2 pre-existing failures** in `test_lessons_service` (W17/W18 added trader-callout lessons; the unlock tests' "only 004 has trader" assumption is now stale — spawned cleanup task). A1 + A2 total: +12 new tests, all passing. |

### Postgres + persistence (NEW this session)

| | |
|---|---|
| Container | `ami_postgres` (postgres:15-alpine) via `docker compose up -d postgres` |
| Host port | **5434** (5432/5433 were already taken on dev box) |
| DB | `ami_trade` (user `postgres`, pw `postgres`) |
| Connect | `docker exec -it ami_postgres psql -U postgres -d ami_trade` |
| Backend → DB | `DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5434/ami_trade` |
| Default (unset) | Sqlite file at `backend/.local.db` — fine for solo dev / first-launch sanity |
| Tests | Per-test sqlite tempfile (autouse fixture in `tests/conftest.py`) |

13 tables created by Alembic on first run:

```
agent_activations    auth_challenges     journal_entries
lessons_progress     mandates            overlay_edit_counts
room_runs            sim_holdings        sim_portfolios
sim_trades           user_overlays       users
alembic_version
```

Migrations live in `backend/alembic/versions/`. To run:

```bash
cd backend
source .venv/bin/activate
DATABASE_URL='postgresql+psycopg2://postgres:postgres@localhost:5434/ami_trade' \
  alembic upgrade head
```

Day-to-day, `init_schema()` in `app/db/session.py` runs `Base.metadata.create_all()` on the first DB-touch in solo dev + tests, so you don't have to remember Alembic during normal feature work.

### Auth scaffold (NEW this session)

Anonymous-first; Supabase-shaped so the swap-over is mostly mechanical.

| Route | What it does |
|---|---|
| `POST /v1/auth/anon` | Bootstrap or reuse anonymous session keyed by `device_user_id` from shared_preferences. Returns `scaffold:<hex>` token. |
| `POST /v1/auth/magic_link/start` | Send 6-digit code via email (in dev env the code is returned in the response for copy-paste). |
| `POST /v1/auth/magic_link/verify` | Consume the code, claim the user row (sets email, `claimed_at`). |
| `POST /v1/auth/apple` | Decode Apple identity JWT body (scaffold — no signature check), claim row with `apple_id=sub`. |
| `GET  /v1/auth/me` | Read current user from `Authorization: Bearer scaffold:<hex>` or `?token=`. |

Critical property: **the user_id never changes when an anonymous account claims**. Mandate, journal, and portfolio survive the claim because they're all keyed by `user_id`.

When real Supabase plugs in, swap the implementation of `app/services/auth_service.py` to call supabase-py admin functions. The route shapes don't change.

### Flutter side

- `lib/models/auth.dart` — AuthUser, AnonSession, MagicLink, AppleSignIn
- `lib/state/auth_providers.dart` — `authNotifierProvider` (auto-bootstraps anon on app launch)
- `lib/screens/auth/sign_in_screen.dart` — full claim UI: Apple button + email magic-link with debug-code surfacing in dev
- Settings → **ACCOUNT** section opens it (`MANAGE ACCOUNT` if claimed, `SIGN IN` if guest)

The Apple button currently uses a synthetic JWT to exercise the backend flow end-to-end. To wire real Apple Sign-In: replace `_signInWithAppleScaffold` in `sign_in_screen.dart` with a call to `package:sign_in_with_apple` (already in pubspec) and pass the real `identityToken` to `authNotifier.signInWithApple()`.

### What survives a backend restart now

Verified end-to-end against Postgres (W8 smoke test):

```
PATCH /v1/mandate/<u>  { compliance: {halal: true}, risk_score: 4 }
→ kill backend
→ relaunch
GET   /v1/mandate/<u>  → still halal:true, risk_score:4

POST  /v1/sim/submit   { ticker: AAPL, qty: 2 }
→ kill backend
→ relaunch
GET   /v1/sim/portfolio/<u>  → holding still there
GET   /v1/sim/trades/<u>      → trade still there
```

Everything keyed by `user_id` survives. The mock price walk does NOT — it's a deterministic in-memory simulator, reseeds from scratch on boot. Real market data feed is a future swap.

### Mobile app

| | |
|---|---|
| Bundle | `ai.agenticmarketintel.amiTrade` v0.1.0+1 |
| Installed on | `TESTING IPHONE 13` |
| Rebuild | `scripts/run_dev.sh` |

**The iPhone still has the W3 build.** Redeploy to see W4–W9.

### What the app does now

Bottom nav: Floor / Portfolio / Journal / Lessons / Settings (5 tabs).

1. Onboarding → Mandate readback.
2. Floor — Concierge + 12 agents + CONVENE THE ROOM CTA.
3. Portfolio — total value + P&L + cash + drawdown, holdings, trades.
4. Journal — every action with filter chips + detail screens.
5. Lessons — 13 lessons, 7 tracks; quiz pass unlocks agents.
6. Settings — Mandate editor + **NEW: ACCOUNT** section → SignInScreen.
7. **NEW: SignInScreen** — Apple button + email magic-link claim flow.

### The core loop is now closed AND durable

Convene → Verdict → Open trade ticket (pre-filled) → PM safety floor runs again on submit → Portfolio updates → Journal records every step. **All of this now survives a backend restart.**

---

## What just landed (A2 — Concierge → AMI, post-onboarding Floor tab)

The 13th agent stops being canned. When the user opens the Concierge from the Floor tab (1-on-1 chat), the LLM now answers and routes against a real picture of the user's situation — recent Journal entries, currently unlocked agents, the lesson catalogue, mandate snapshot. When no real provider is registered, a deterministic scripted reply takes over (it does NOT fall back to MockProvider's "I'm offline" line) and routes the user to the right tab/agent/lesson based on keyword intent.

The deterministic onboarding state machine in `concierge_engine.py` is untouched — the welcome interview / mandate readback stays scripted for reproducibility. A2 is strictly the post-onboarding Concierge on the Floor.

### How it's wired

- **New `backend/app/services/concierge_prompts.py`**:
  - `build_concierge_messages()` — composes the live system prompt. Starts from `build_agent_prompt(CONCIERGE, mandate, user_id)` (base + mandate overlay + user-coaching overlay + safety floor), then appends a "FLOOR CONCIERGE CONTEXT" block listing the mandate one-liner, the user's last ~6 Journal entries, the set of unlocked agents, the lesson catalogue (ID + title + track + level), and a "be specific — name the lesson ID, name the agent, do not invent" instruction.
  - `scripted_reply()` — keyword-intent classifier with five buckets (lesson / journal / mandate / Convene-the-Room / trading-advice). Names a real lesson ID, a real agent, or a real journal title from the supplied context so the fallback still feels useful instead of generic.
  - `load_concierge_context()` — best-effort puller for journal + activations + lesson catalogue; swallows DB exceptions so a data-layer hiccup never kills the chat stream.
- **`agent_runner.py` Concierge branch** — `stream_one_on_one_message` detects `agent_id == CONCIERGE` and dispatches to `_stream_concierge`, which:
  1. Loads the context via `load_concierge_context`.
  2. If `gateway.has_real_provider()` is False, yields the `scripted_reply` text in one chunk and returns. The LLM gateway is **not** called — same pattern A1 introduced for the Room.
  3. Otherwise, builds the enriched prompt and streams the LLM response. Any exception or empty response falls back to the scripted reply so the Floor never hangs.
- **Tier policy unchanged.** Concierge tier is picked via `pick_tier(plan, AgentId.CONCIERGE)` — Floor Manager drops to `mid` per W12's per-(plan, agent) override; everyone else gets the default for their plan.
- **Onboarding API untouched.** `/v1/onboarding/*` still routes through the deterministic `concierge_engine` state machine.

### Tests (+9, 142 total — see test-suite note above)

`backend/tests/unit/test_concierge_live.py`:

- `test_concierge_routes_to_gateway_when_real_provider_present` — fake live gateway records exactly one call; system prompt contains "FLOOR CONCIERGE CONTEXT" and the mandate snapshot.
- `test_concierge_prompt_carries_lesson_catalogue` — at least one real lesson appears under the "Available lessons" block.
- `test_concierge_prompt_lists_unlocked_agents_for_real_user` — grants the Market Analyst via `lessons_service.grant_activation`, asserts "Market Analyst" appears in the system prompt.
- `test_concierge_uses_scripted_fallback_when_no_real_provider` — fake gateway with `has_real_provider() = False` is **never called**; output contains the mandate snapshot from `scripted_reply`.
- `test_scripted_reply_routes_lesson_intent` — "teach me about risk" → names a real lesson ID.
- `test_scripted_reply_routes_to_unlocked_agent` — "can I talk to the market analyst?" → names Market Analyst.
- `test_scripted_reply_refuses_trading_advice` — "should I buy NVDA?" → routes to Market Analyst / Convene the Room without echoing or speculating.
- `test_scripted_reply_summarises_journal` — recent entries surface ticker tags in the reply.
- `test_build_concierge_messages_includes_all_context_blocks` — direct unit on the prompt builder: journal, unlocked agents, lesson catalogue, mandate, and base Concierge role all land in the system prompt; user message is the last `messages` entry.

### Live verification path (on-prem vLLM Gemma 4 31B)

`POST /v1/agents/one_on_one/start` with `agent_id=concierge` then `POST /v1/agents/one_on_one/message` streams real Concierge prose that references actual lesson IDs and the user's actual journal. Mock fallback exercised by running with `VLLM_BASE_URL` unset — Concierge still routes the user usefully (mandate-aware, lesson-aware) without ever calling the gateway.

---

## What just landed (A1 — Convene the Room → AMI wiring)

The marquee flow stops being scripted. Every agent in a Room run now speaks via the LLM gateway when a real provider is registered (today: on-prem vLLM Gemma 4). The deterministic safety floor is untouched — it still produces the verdict ACTION (APPROVE/REJECT); the LLM only writes the prose rationale around that fixed result.

### How it's wired

- **New `backend/app/services/room_prompts.py`** — composes the per-agent system prompt for a Room turn. Combines the agent's base prompt (already includes mandate overlay + safety floor where applicable) with a CONVENE THE ROOM addition: phase label, compact ticker fact-sheet (price/P/E/growth/RSI/range/catalysts/macro/sentiment) sourced from the existing `_profile_for_ticker()`, the running transcript so each agent builds on the debate, a per-agent length budget, and a "speak directly, no preamble" instruction.
- **Rewritten `room_runner.py::run()`** — flips between live and scripted via `gateway.has_real_provider()`. Each non-PM agent's tokens stream out as SSE `agent_token` events at the LLM's own pacing.
- **PM is special** — `_assemble_verdict()` runs the deterministic safety floor FIRST. Then `_stream_pm_narration` asks the LLM for prose with `pm_predetermined_action="APPROVE"` / `REJECT (violations)` in the system prompt and an explicit "do NOT contradict this action" instruction. The buffered PM text is restreamed at typewriter cadence so the UI pacing stays uniform.
- **Every LLM path catches all exceptions** and falls back to the scripted `_TEMPLATES`. The demo never breaks if vLLM is unreachable.
- **Per-agent tier via `pick_tier(plan, agent_id)`**. vLLM collapses all tiers to `gemma-4-31b-it-nvfp4` today; routing is correct for the future cloud-LLM cutover (Beta).

### Tests (+3, 133 total)

- `test_room_uses_gateway_for_every_agent_when_live` — fake gateway records 12 calls (one per agent), transcript grows by 12, verdict still APPROVE (deterministic).
- `test_room_safety_floor_still_fires_under_live_gateway` — liberal "APPROVE everything" LLM reply does NOT override the floor; halal user on a non-halal ticker still gets REJECT with `overridden_from_llm=True`.
- `test_room_transcript_grows_for_subsequent_agents` — first agent sees `(You are first to speak.)` marker; PM sees every prior agent's contribution in its prompt.

### Live verification (against on-prem vLLM Gemma 4 31B)

`POST /v1/room/stream` on NVDA with `risk_score=3` streams real per-agent analysis. Fundamentals Analyst opened with:

> *"NVDA maintains an exceptional quality-of-earnings profile, though valuation now demands flawless execution of the Blackwell ramp to justify a 50.7 P/E. Balance Sheet: Net cash of $38.9B provides significant optionality for R&D or buybacks, though capital expenditures are scaling to support next-gen architecture. Profitability: FCF margins of 22% are robust..."*

Real Blackwell architecture reference, real cash position, real FCF margin. The scripted demo is gone from the marquee flow.

---

## What just landed (W17 / W18 / W18b — project plan + curriculum + authoring)

Multiple planning artefacts landed this session before A1.

- **`docs/10_delivery/project_plan.md`** — three-phase plan (Alpha → Beta → MVP). Saiful's framing: Alpha = everything on-prem (full feature shakedown including i18n/TTS/push/daily briefing + TestFlight distribution). Beta = ONLY GCP + Supabase + cloud LLM migration; same feature surface, nothing user-visible changes. MVP = App Store + Play Store + payments + marketing.
- **`docs/04_education/curriculum_map.md`** — canonical Level 1–8 / Module 1–12 / ~77 lesson IDs. Each lesson tagged with `level`, `module`, `difficulty`, `track` (for agent-unlock routing), and `agent_callouts`. Existing 13 lessons re-mapped lazily. Animations are OPTIONAL — only ~15 specific lessons are flagged as "good animation candidates".
- **`content/_authoring/lesson_authoring_prompt.md`** — three self-contained prompts for any AI tool: (1) lesson MDX generator with the 7-part lesson template (short explanation → real-world example → "the trap" → ChatWith → quiz → action task → takeaway), (2) daily-challenge bank (one month per batch, 5 challenge types from `docs/04_education/daily_and_streaks.md`), (3) AI Coach Q&A Library (categorised knowledge base for the Concierge to retrieve from). Tickers are illustrative not exclusive (user watchlists are how the product actually serves the "their tickers" need). Every lesson MUST have a multi-choice quiz; users can skip the lesson body and jump to the quiz.

### Plan summary (current)

| Phase | Claude effort | Saiful external |
|---|---|---|
| **Alpha** (on-prem + TestFlight) | ~9.75 sessions | Resend, Cloudflare Tunnel, Apple cap × 2, Azure/ElevenLabs, OneSignal, App Store Connect, translators, legal stub |
| **Beta** (GCP + Supabase + cloud LLM) | ~5 sessions | GCP, Supabase, cloud LLM provider, DNS |
| **MVP** (public launch) | ~3 sessions | App Store / Play / RevenueCat / legal / marketing / analytics |

Alpha picked up A1 this session. Remaining Alpha items split into 5 streams (full table in `docs/10_delivery/project_plan.md`):

| Stream | Items | Status |
|---|---|---|
| 1 — Finish the AMI surface | A1, A2 | A1 ✓, A2 pending |
| 2 — Real auth + on-prem hardening | A3–A10 | unstarted (A3/A7 blocked on Saiful) |
| 3 — i18n / TTS / push / daily briefing | A11–A17 | unstarted |
| 4 — Product polish (watchlist, skip-to-quiz, lesson loader, animation registry) | A18–A21 | unstarted |
| 5 — Ship to offsite testers | A22–A28 | unstarted (App Store Connect blocked on Saiful) |

---

## What just landed (W13 — on-prem vLLM Gemma 4 — app is live)

Saiful pointed at his LAN-hosted vLLM box at `192.168.20.74:8000`
serving `gemma-4-31b-it-nvfp4` (Gemma 4 31B, NVFP4 quantized, 262k
context). Wired it through the existing gateway abstraction; the iPhone
build from W11 is now talking to a real LLM end-to-end.

### New `VLLMProvider` in `llm_gateway.py`

OpenAI-compatible streaming client (`/v1/chat/completions`, SSE with
`choices[0].delta.content` deltas). Same `LLMProvider` interface as the
Anthropic + Mock providers — drop-in. Optional bearer auth via
`VLLM_API_KEY` for hardened deployments; LAN-private servers leave it
unset.

### Gateway selection: vllm > anthropic > mock

`LLMGateway._PREFERENCE = ("vllm", "anthropic", "mock")`. Whichever is
registered first wins. Set `VLLM_BASE_URL` → vLLM serves every call.
Unset it → Anthropic if `ANTHROPIC_API_KEY` is set, otherwise mock.
`/v1/llm/status` now reports `active_provider: "vllm"` and every tier
in `tier_to_model` resolves to the single hosted model (vLLM hosts one
model at a time; the tier dimension collapses).

### Config additions

```ini
VLLM_BASE_URL=http://192.168.20.74:8000
VLLM_MODEL=gemma-4-31b-it-nvfp4
VLLM_API_KEY=          # optional
USE_REAL_MARKET_DATA=true
```

Lives in `app/core/config.py` + documented in `.env.example`.

### Verified end-to-end

Backend restarted under W13 worktree code with env vars set:

```
$ curl localhost:8000/v1/llm/status
{"providers_registered":["mock","vllm"],"active_provider":"vllm",
 "has_real_provider":true,
 "tier_to_model":{"cheap":"gemma-4-31b-it-nvfp4",
                  "mid":"gemma-4-31b-it-nvfp4",
                  "premium":"gemma-4-31b-it-nvfp4"}}
```

Then a 1-on-1 stream against `market_analyst`:

> "Daily/Weekly timeframe: Bullish trend continuation following a
>  successful retest of the 50-day SMA.
>  Setup: Long on dip to $115 (support), target $140, stop-loss $105
>  (approx 2.5:1 R:R)."

Structured analyst response, streamed token-by-token from the iPhone's
backend through tier_policy → vLLM → Gemma 4 → SSE back to the client.
Mock text is gone.

### Tests (+7 → 130 total)

- `test_vllm_provider_parses_openai_deltas` — happy path; verifies the system prompt is placed inside `messages` and the model name + max_tokens + stream flag land in the body.
- `test_vllm_provider_error_yields_inline_error` — HTTP 503 yields a sentinel error chunk.
- `test_vllm_provider_tolerates_empty_delta_chunks` — empty `delta` between content tokens doesn't crash.
- `test_vllm_provider_sends_bearer_when_api_key_set` / `test_vllm_provider_omits_bearer_without_api_key` — Authorization header behavior.
- `test_gateway_prefers_vllm_when_both_keys_set` — preference order is vllm > anthropic > mock.
- `test_gateway_status_with_only_vllm` — status surface when only vLLM is configured.

### Running stack (this terminal)

| Component | Where | How |
|---|---|---|
| Backend | PID 67193 | `uvicorn app.main:app --host 0.0.0.0 --port 8000` from the W13 worktree, env: `DATABASE_URL`, `USE_REAL_MARKET_DATA=true`, `VLLM_BASE_URL`, `VLLM_MODEL` |
| Postgres | docker `ami_postgres` | host port 5434 |
| vLLM | `192.168.20.74:8000` | on-prem, gemma-4-31b-it-nvfp4 |
| iPhone | TESTING IPHONE 13 | release build of W11 code, pointed at `http://192.168.20.9:8000` |

### Logs

```
tail -f /tmp/ami-backend.log
```

---

## What just landed (W12 — tier_policy refactor)

W9 shipped a `AGENT_MIN_TIER` map inside `llm_gateway.py` with a
"never-downgrade-from-plan" rule. Saiful asked for tighter semantics:
per-(plan, agent) decisions, in a dedicated module, not buried in the
gateway. Behaviour change: **Floor-Pass PM drops from `premium` → `mid`**,
**Floor-Manager Concierge drops from `premium` → `mid`**.

### New: `app/services/tier_policy.py`

Single source of truth for which model tier each agent runs at, given the
user's plan. Used by 1-on-1, Coach, and Room.

```python
pick_tier(Plan.FLOOR_PASS, AgentId.PORTFOLIO_MANAGER)  # → "mid"
pick_tier(Plan.TRADER,     AgentId.PORTFOLIO_MANAGER)  # → "premium"
pick_tier(Plan.FLOOR_MANAGER, AgentId.CONCIERGE)       # → "mid"
pick_tier(Plan.FLOOR_MANAGER, AgentId.TRADER)          # → "premium"
pick_tier(Plan.TRIAL_TRADER,  AgentId.BULL_RESEARCHER) # → "mid"  (default)
```

Special-cased agents: Concierge, Portfolio Manager, Trader. Everyone
else uses `_DEFAULT_BY_PLAN`.

### Call-site swaps

- **`agent_runner.py`** — local `PLAN_TO_TIER` dict gone; tier comes from `pick_tier(plan, agent_id)` in `stream_one_on_one_message`.
- **`coach_engine.py`** — local `PLAN_TO_TIER` + `_plan_tier` helper gone; both `stream_chat` paths (live chat and propose-as-JSON) call `pick_tier(_plan_from_mandate(mandate), agent_id)`.
- **`room_runner.py`** — run-level tier now `pick_tier(plan, AgentId.PORTFOLIO_MANAGER)` so the PM's tier drives credit cost (the PM is the lineup's max-tier agent). `from app.services.tier_policy import pick_tier` is imported for when Room is wired through the gateway later.
- **`llm_gateway.py`** — `AGENT_MIN_TIER`, `resolve_tier`, and the `_TIER_RANK` helper are gone. The gateway owns the tier→model alias map and provider selection; routing decisions live in `tier_policy.py`. `GET /v1/llm/status` no longer surfaces `agent_min_tier` (it was redundant once routing moved out).

### Tests

- **New `test_tier_policy.py`** — 11 parametrized cases covering Concierge, PM, Trader, default plan paths.
- **Trimmed `test_llm_gateway.py`** — removed 6 obsolete tier-routing cases. Kept AnthropicProvider SSE parsing + gateway status tests.
- Suite: **123 passed** (was 118; +11 / −6 net).

---

## What just landed (W11 — Flutter LIVE/MOCK quote-source pill)

W10's `price_source` field now reaches the iPhone. The Portfolio screen
header pulls a small green-dot "LIVE" pill when Yahoo quotes are active,
amber-dot "MOCK" when on the deterministic walk — so the demo speaks
honestly about what it's pricing.

- **Backend**: `PortfolioSnapshot` (`backend/app/api/sim.py`) gains a `price_source: str` field surfaced from `sim.price_source`. Default `"mock_walk"` keeps the response shape backward-compatible.
- **Flutter model**: `SimPortfolio` (`mobile/lib/models/sim.dart`) parses `price_source`, exposes `isLivePrice` (true when the source name contains `yahoo`).
- **Flutter UI**: `_QuoteSourcePill` widget in `mobile/lib/screens/sim/portfolio_screen.dart` — colored dot + monospace label next to TOTAL VALUE.
- 118 unit tests still pass; `flutter analyze` clean on the touched files.

This closes the W10 loop end-to-end: real prices in the backend, an honest indicator in the app. **Saiful: the iPhone still has the W3 build — needs a redeploy to see W4–W11.**

---

## What just landed (W10 — real market data via Yahoo)

The Sim Trading engine no longer lies — when `USE_REAL_MARKET_DATA=true`
quotes come from Yahoo's keyless public chart endpoint, with the legacy
random walk as fallback for unknown tickers and network errors.

### Market data — pluggable provider stack

- **`backend/app/services/market_data.py`** — new module owning all pricing.
  - `MarketDataProvider` protocol — `get_price(ticker) -> float | None`.
  - `MockWalkProvider` — the old deterministic random walk (now lives here, not on `SimEngine`).
  - `YahooQuoteProvider` — calls `https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m&range=1d` via the already-vendored `httpx`. Browser User-Agent header (Yahoo blocks the default httpx UA). Catches every error — `ConnectError`, non-200, malformed JSON, missing fields — and returns `None`.
  - `CachingProvider(inner, ttl_seconds=60)` — per-ticker TTL cache. Doesn't cache `None` (so a transient failure doesn't pin a missing price for 60s).
  - `FallbackProvider(primary, secondary)` — tries primary; falls through to secondary on `None`.
  - `get_market_data_provider()` returns the configured stack:
    - `USE_REAL_MARKET_DATA=true` → `FallbackProvider(CachingProvider(YahooQuoteProvider), MockWalkProvider)`
    - default → bare `MockWalkProvider`
  - `set_market_data_provider(p)` test hook.

### SimEngine refactor

- **`backend/app/services/sim_engine.py`** — no longer owns pricing logic. Takes a `MarketDataProvider` (defaults to `get_market_data_provider()`). New `sim.price_source` exposes the active provider name; `/v1/sim/quote/{ticker}` now returns `{"ticker", "price", "source"}` so the iPhone client can show "live" vs "mock".
- **`backend/tests/conftest.py`** — autouse fixture pins a fresh `MockWalkProvider` for every test so the suite stays deterministic regardless of `USE_REAL_MARKET_DATA`.

### Live verification

Hit Yahoo with the actual stack (env-gated, from the venv):

```
USE_REAL_MARKET_DATA=true python -c "from app.services.market_data import get_market_data_provider; ..."
stack: fallback(cache(yahoo)->mock_walk)
  AAPL: 190.09
  NVDA: 270.97
  BRK-B: 239.19
  NOTREAL: 200.44   ← fell through to mock as designed
```

### Tests (+15 → 118 total)

- `tests/unit/test_market_data.py` — 15 cases:
  - `MockWalkProvider`: stable + independent walks per ticker.
  - `CachingProvider`: hit, miss-on-different-ticker, never-cache-None, targeted invalidate.
  - `FallbackProvider`: primary hit, secondary fallback, both-fail.
  - `YahooQuoteProvider` (mocked httpx): success parse, non-200, network error, empty result, missing price field.
  - Full real-stack assembly: Yahoo 500 → cache pass-through → mock fires.
- All `test_sim_engine.py` tests still pass (one minor test update: the internal walk lives on the provider now, not on `SimEngine`).

### How to flip it on

```bash
# in backend/.env
USE_REAL_MARKET_DATA=true

# restart backend
scripts/run_dev.sh backend

# verify
curl -s http://localhost:8000/v1/sim/quote/AAPL
# → {"ticker":"AAPL","price":190.09,"source":"fallback(cache(yahoo)->mock_walk)"}
```

---

## What just landed (W9 — LLM-swap prep + cleanup)

The Anthropic key was NOT available this session, so option A's runtime
validation was deferred. What WAS done is everything that makes "drop
key → live" a single env-var change with zero code touches.

### LLM gateway — live-swap ready

- **`backend/app/services/llm_gateway.py`**
  - `TIER_TO_MODEL` map: `cheap=claude-haiku-4-5`, `mid=claude-sonnet-4-6`, `premium=claude-opus-4-7`.
  - `AGENT_MIN_TIER` per-agent floor (Portfolio Manager pinned to `premium` even for Floor-Pass users — the safety-floor enforcer never runs on a cheap brain).
  - `resolve_tier(plan_tier, agent_id)` takes the higher of the two. A Floor-Pass user 1-on-1 with PM → `premium`. A Floor-Manager Room run with the Concierge → `premium`.
  - `LLMGateway.status()` introspection — surfaced via the new endpoint.
- **`/v1/llm/status`** (`backend/app/api/llm.py`) — curl-checkable provider/model report. Does not call any provider; safe to ping cheaply.
- **`backend/scripts/llm_smoke.py`** — pings each tier with a one-token "PONG" prompt. After Saiful drops `ANTHROPIC_API_KEY` into `backend/.env`:
  ```bash
  cd backend && .venv/bin/python -m scripts.llm_smoke --quiet
  # → PASS (cheap,mid,premium)   ← the live flip is real
  ```
  Exits non-zero on any tier failure so it can be wired into a deploy gate.

### Tests (+12 new)

- `tests/unit/test_llm_gateway.py` — 12 cases covering:
  - Tier resolution (PM bump, concierge no-downgrade, unknown agent fallback).
  - `AGENT_MIN_TIER` coverage of every `AgentId`.
  - Gateway status with/without key (monkeypatched).
  - Mock provider canned routing.
  - `AnthropicProvider` SSE parsing (mocked `httpx.AsyncClient.stream`).
  - `AnthropicProvider` error path (HTTP 429 yields inline error chunk).
  - `AnthropicProvider` tolerance of empty lines / non-`data:` lines / junk JSON.
- Suite total: **103 passed** (was 91 at W8 end).
- Suite passes with `-W error::DeprecationWarning` — the entire `datetime.utcnow()` deprecation backlog is drained.

### Cleanup pass

- **`datetime.utcnow()` → `now_utc()`** (`backend/app/core/time.py` helper, returns naive UTC to match legacy semantics). Replaced 8 call sites across `schemas/onboarding.py`, `schemas/one_on_one.py`, `api/onboarding.py`, `services/agent_runner.py`, `services/session_store.py`, `services/concierge_engine.py`. Zero deprecation warnings remain.
- **Research Manager lesson** (`content/lessons/013_research_manager_synthesis.en.mdx`) — 5-min lesson on synthesis-vs-opinion, asymmetry arithmetic, "no trade" as a real output. Frontmatter `agent_callouts: ["research_manager"]` wires the unlock; completing this single lesson activates the RM agent via the Earn Path.
- **RLS Alembic migration** (`backend/alembic/versions/a4c7e9d10001_rls_policies.py`) — 23 policies across 13 user-scoped tables (mandates, user_overlays, journal_entries, lessons_progress, agent_activations, room_runs, sim_portfolios, sim_holdings, sim_trades, users, auth_challenges, overlay_edit_counts). All policies key on `current_setting('app.user_id', true)::uuid`. Applied to local Postgres (`docker exec ami_postgres psql ... -c "SELECT tablename, policyname FROM pg_policies"` shows all 23). Migration is no-op on SQLite (tests). Enforcement is dormant until the backend switches off `postgres` superuser — Saiful does that when real Supabase plugs in, by running the API under `authenticated` / `anon` roles.

### What's still NOT done

| Feature | Why deferred |
|---|---|
| **Live LLM validation** (1-on-1, Coach, Room actually producing real reasoning) | Needs `ANTHROPIC_API_KEY`. Code path is verified by tests; flip happens automatically when key lands. |
| **Real Supabase plug-in** | Needs Saiful to provision project + hand over keys. |
| **Real Apple Sign-In** | Needs Apple capability added to bundle id under team `S7RBWM4879`. |
| **Real LLM Concierge** | Deterministic onboarding state machine still drives W2. |
| **Room → LLM wiring** | `room_runner.py` still emits scripted text. Wiring it to the gateway is its own piece of work (per-agent prompts, transcript-aware context, fallback when no real provider). |

---

## Prompt to paste at the start of the next session

```
We're picking up the AMI Trade build. This is handover #10 — name the
session "AT:R11:".

Read HANDOVER.md at the project root first:
  /Volumes/Extreme Pro/AMI_MarketApp/HANDOVER.md

Then read docs/10_delivery/project_plan.md — your task is almost
always one of the A1-A28 items in there.

State: 22 commits in. 140 unit tests pass + 2 pre-existing failures
in test_lessons_service (W17/W18 added trader-callout lessons; the
"only 004 has trader" assumption is stale — separate spawned task
handles it). A1 + A2 both landed — every user-visible AMI surface
(Convene the Room, 1-on-1 with all 13 agents including Concierge on
the Floor) now streams from vLLM Gemma 4 with deterministic fallbacks
intact. The deterministic onboarding state machine is untouched and
stays scripted on purpose.

Alpha-stream pick-up (priority order — top is highest leverage):

  A18. User watchlist. NEW sim_watchlists table (user_id, ticker,
       added_at, notes); GET/POST/DELETE /v1/watchlist/{user_id}.
       Flutter section on Portfolio screen above HOLDINGS — each row
       shows ticker + live quote + day-change %; tap opens a sheet
       with quote + buttons (Add Trade, Ask Market Analyst, Convene).
       Tickers are free-form (any string Yahoo can quote). This is
       the "see THEIR stocks" loop Saiful wants for sim play. ~1
       session.

  A11. i18n structure. Extract every user-facing string in mobile/lib
       to ARB files via flutter_localizations + intl. Locale switcher
       in Settings. RTL pass for AR (Directionality, padding-inline).
       English content ships; AR/MS empty placeholders. ~0.5 session.

  A19. Lesson UX — Skip to quiz. Lessons screen lists each lesson with
       READ + QUIZ ONLY buttons. Quiz-only path renders just the
       <Quiz> blocks + miss-explanations and counts toward
       agent-unlock identically. ~0.5 session.

  A20. Lesson loader: parse new frontmatter fields (module,
       difficulty). Default to module:0, difficulty:level for legacy
       lessons. Unblocks generation runs from the lesson authoring
       prompt at content/_authoring/lesson_authoring_prompt.md.
       ~0.25 session.

  A8. Backend production launch — systemd unit, env file in
      /etc/ami-trade.env, log rotation, restart-on-fail. No more
      `nohup uvicorn`. ~0.5 session.

  A9. Postgres backups — pg_dump cron + offsite copy + restore drill.
      ~0.25 session.

  A10. Sentry SDK in backend + Flutter. ~0.5 session.

  A21. Animation MDX component — Flutter AnimationRegistry maps
       name → Lottie asset path; missing names render
       AmiHexPlaceholder. ~0.5 session.

Blocked on Saiful's external steps (unblock when ready):
  A3. Resend account + DKIM/SPF DNS — unblocks A4/A5 (email
      confirmation flow).
  A6. Sign in with Apple capability on bundle id under team
      S7RBWM4879 — unblocks A6 code.
  A7. Cloudflare Tunnel + named hostname + Access policy — unblocks
      A25 (iPhone leaves the LAN).
  A13. TTS provider account + key (Azure or ElevenLabs) — unblocks
       A14 (TTS integration).
  A15. OneSignal account + Dev APNs cert from Apple Dev — unblocks
       A16 (push notifications).
  A19. App Store Connect app record (bundle id
       ai.agenticmarketintel.amiTrade, SKU AMITRADE, English primary)
       + install Transporter from Mac App Store — unblocks
       A25/A26 (TestFlight upload).

Saiful has granted full autonomy through MVP — execute, don't ask.
File-header rule: every new file gets a docstring/library comment
that explains what it is and why.
Naming: code/internals → LLM is fine; user-visible copy → AMI by name
(never "the AI"). See docs/08_tech/coding_conventions.md.

Before writing code:
  cd "/Volumes/Extreme Pro/AMI_MarketApp"
  git status
  git log --oneline | head -10
  docker ps --filter "name=ami_postgres" --format '{{.Names}}: {{.Status}}'
  curl -s http://localhost:8000/v1/health
  curl -s http://localhost:8000/v1/llm/status
  curl -s http://localhost:8000/v1/sim/quote/AAPL

Backend may be on PID found via:
  pgrep -lf "uvicorn app.main"
If down, restart from this worktree:
  cd "/Volumes/Extreme Pro/AMI_MarketApp/.claude/worktrees/magical-edison-18bf91/backend"
  DATABASE_URL='postgresql+psycopg2://postgres:postgres@localhost:5434/ami_trade' \
  USE_REAL_MARKET_DATA=true \
  VLLM_BASE_URL=http://192.168.20.74:8000 \
  VLLM_MODEL=gemma-4-31b-it-nvfp4 \
  nohup /Volumes/Extreme\ Pro/AMI_MarketApp/.claude/worktrees/strange-meninsky-06db6d/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 >/tmp/ami-backend.log 2>&1 &
```

---

## How to run the W8 stack locally

```bash
# 1. Postgres
cd "/Volumes/Extreme Pro/AMI_MarketApp"
docker compose up -d postgres            # host port 5434

# 2. Backend (sqlite fallback works too — just unset DATABASE_URL)
cd backend && source .venv/bin/activate
DATABASE_URL='postgresql+psycopg2://postgres:postgres@localhost:5434/ami_trade' \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. App (separate terminal)
scripts/run_dev.sh
```

---

## Open questions / nothing-is-blocked items

- **Anthropic API key.** Still not added — and no longer needed: the on-prem vLLM at `192.168.20.74:8000` serves Gemma 4 31B for every agent today. Anthropic remains a hot-swappable fallback if `VLLM_BASE_URL` is unset.
- **Supabase project.** Not yet provisioned. RLS policies are live but dormant — they enforce once the backend stops connecting as `postgres`.
- **Apple Developer team setup.** Done for Team `S7RBWM4879` but Sign in with Apple capability needs to be added to the bundle id for real prod usage.
- **App Store, APNs** — still external. Market data is now real Yahoo when `USE_REAL_MARKET_DATA=true`.

Nothing is blocking the next chunk.
