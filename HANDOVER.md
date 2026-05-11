# Handover — AMI Trade build session

**Last updated:** 2026-05-11 (end of W9: LLM-swap prep + cleanup pass)

Read this file **first** in any new session. It captures runtime state, what just landed, and a copy-paste prompt to continue.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, 11 commits, no remote yet |
| Latest commit | (this session) W9: LLM-swap prep + cleanup pass |
| Lines on disk | ~33,900 (PRD ~14k, backend ~7.8k, Flutter ~9.8k, content ~1.5k) |

```
$ git log --oneline
<new>   W9: LLM-swap prep + cleanup pass
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
| Tests | `pytest backend/tests/unit/ -q` → **103 passed** (W8: 91, +12 llm_gateway) |

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
| **Real market data** | SimEngine random walk still in use. Polygon free tier is the obvious swap. |
| **Real LLM Concierge** | Deterministic onboarding state machine still drives W2. |
| **Room → LLM wiring** | `room_runner.py` still emits scripted text. Wiring it to the gateway is its own piece of work (per-agent prompts, transcript-aware context, fallback when no real provider). |

---

## Prompt to paste at the start of the next session

```
We're picking up the AMI Trade build. This is handover #4 — name the
session "AT:R5:".

Read HANDOVER.md at the project root first:
  /Volumes/Extreme Pro/AMI_MarketApp/HANDOVER.md

W9 (LLM-swap prep + cleanup) is done. 11 commits in. 103 unit tests
pass. RLS policies live in Postgres but dormant (backend connects as
superuser locally). Per-agent tier routing in place; Research Manager
lesson live; datetime.utcnow() backlog drained.

W10 candidates (priority order):

  A. Live LLM swap (FINISH IT). Saiful adds ANTHROPIC_API_KEY to
     backend/.env. Then:
       cd backend && .venv/bin/python -m scripts.llm_smoke
     Expect PASS on all three tiers. Then exercise 1-on-1 with PM
     (premium) and Concierge (cheap) to confirm tier routing. Then
     decide whether to wire Room → gateway (currently scripted).

  B. Real Supabase plug-in. SUPABASE_URL + SUPABASE_SERVICE_KEY in
     backend/.env. Swap app/services/auth_service.py to supabase-py
     admin. Switch backend connection from postgres to anon /
     authenticated role so RLS policies start enforcing. Run the
     anon → email claim flow end-to-end.

  C. Real Apple Sign-In. Replace the synthetic JWT in
     mobile/lib/screens/auth/sign_in_screen.dart with sign_in_with_apple
     (already in pubspec). Verify on TESTING IPHONE 13. Add Sign in
     with Apple capability to bundle id under team S7RBWM4879.

  D. Real market data. Swap SimEngine.current_price() for Polygon
     (free tier). DB schema doesn't change.

  E. Room → LLM wiring. Currently room_runner.py emits scripted
     text. Wire each agent's speech through llm_gateway with a
     transcript-aware prompt. Keep scripted fallback when gateway
     reports no real provider.

Saiful has granted full autonomy through MVP — execute, don't ask.
File-header rule: every new file gets a docstring/library comment
that explains what it is and why.

Before writing code:
  cd "/Volumes/Extreme Pro/AMI_MarketApp"
  git status
  git log --oneline
  docker ps --filter "name=ami_postgres" --format '{{.Names}}: {{.Status}}'
  curl -s http://localhost:8000/v1/health
  curl -s http://localhost:8000/v1/llm/status
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

- **Anthropic API key.** Still not added. Gateway code is verified; smoke script ready. Drop key into `backend/.env` → restart → `python -m scripts.llm_smoke` → PASS = live.
- **Supabase project.** Not yet provisioned. RLS policies are live but dormant — they enforce once the backend stops connecting as `postgres`.
- **Apple Developer team setup.** Done for Team `S7RBWM4879` but Sign in with Apple capability needs to be added to the bundle id for real prod usage.
- **App Store, APNs, real market data** — still external.

Nothing is blocking the next chunk.
