# Handover — AMI Trade build session

**Last updated:** 2026-05-11 (end of W8 persistence + auth scaffold session)

Read this file **first** in any new session. It captures runtime state, what just landed, and a copy-paste prompt to continue.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, 10 commits, no remote yet |
| Latest commit | (this session) W8: persistence migration + auth scaffold |
| Lines on disk | ~33,500 (PRD ~14k, backend ~7.5k, Flutter ~9.8k, content ~1.4k) |

```
$ git log --oneline
<new>   W8: persistence migration + Supabase-shaped auth scaffold
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
| Routes | `/v1/health`, **`/v1/auth/*`**, `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/coach/*`, `/v1/journal/*`, `/v1/lessons/*`, `/v1/room/*`, `/v1/sim/*`, `/v1/mandate/*` |
| Tests | `pytest backend/tests/unit/ -q` → **91 passed** (W7: 84, +7 auth) |

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

**The iPhone still has the W3 build.** Redeploy to see W4–W8.

### What the app does now

Bottom nav: Floor / Portfolio / Journal / Lessons / Settings (5 tabs).

1. Onboarding → Mandate readback.
2. Floor — Concierge + 12 agents + CONVENE THE ROOM CTA.
3. Portfolio — total value + P&L + cash + drawdown, holdings, trades.
4. Journal — every action with filter chips + detail screens.
5. Lessons — 12 lessons, 7 tracks; quiz pass unlocks agents.
6. Settings — Mandate editor + **NEW: ACCOUNT** section → SignInScreen.
7. **NEW: SignInScreen** — Apple button + email magic-link claim flow.

### The core loop is now closed AND durable

Convene → Verdict → Open trade ticket (pre-filled) → PM safety floor runs again on submit → Portfolio updates → Journal records every step. **All of this now survives a backend restart.**

---

## What's NOT yet built (W9 candidates)

| Feature | Spec doc |
|---|---|
| **Real Supabase plug-in** | Swap `app/services/auth_service.py` impl for supabase-py admin SDK; set `SUPABASE_URL`+`SUPABASE_SERVICE_KEY`. |
| **Real Apple Sign-In** | Wire `sign_in_with_apple` package in `sign_in_screen.dart`; pass real identity_token to backend. |
| **Real LLM Concierge** | Replace deterministic onboarding state machine. `docs/02_agents/concierge.md`. |
| **More lessons** | One Research Manager lesson + content for deeper tracks. |
| **Cleanup** | `datetime.utcnow()` deprecation in `concierge_engine.py` + a few other older files. |
| **Live LLM swap** | Single function in `room_runner.py` once `ANTHROPIC_API_KEY` is added. |
| **Real market data** | Swap `SimEngine.current_price()` for Polygon / Yahoo. |
| **RLS policies** | Re-enable RLS in Alembic migrations once Supabase auth is the source of `auth.uid()`. |

---

## Prompt to paste at the start of the next session

```
We're picking up the AMI Trade build. Read HANDOVER.md at the project root
(/Volumes/Extreme Pro/AMI_MarketApp/HANDOVER.md) first.

W8 (persistence + auth scaffold) is done. Pick one of the W9 candidates:

  A. Real Supabase plug-in. Saiful provisions a Supabase project, hands
     over SUPABASE_URL + SUPABASE_SERVICE_KEY. Swap auth_service to
     supabase-py admin; the route contracts don't change. Smoke test
     anon → email claim still works end-to-end.

  B. Real Apple Sign-In wiring. The flutter package `sign_in_with_apple`
     is already in pubspec. Replace the synthetic JWT in
     sign_in_screen.dart with a real Apple call. Verify on a real
     iPhone (test team set up via Apple Developer console).

  C. Live LLM swap. ANTHROPIC_API_KEY in backend/.env; flip
     LLMGateway provider. Then validate 1-on-1, Coach, Room produce
     real Anthropic reasoning rather than canned scripts.

  D. Real market data. Swap SimEngine.current_price() for a real feed
     (Polygon free tier is fine). The DB schema doesn't change.

  E. Cleanup pass. datetime.utcnow() deprecation, a Research Manager
     lesson, RLS migrations.

Saiful has granted full autonomy through MVP — execute, don't ask.
File-header rule: every new file gets a docstring/library comment
that explains what it is and why.

Before writing code:
  cd "/Volumes/Extreme Pro/AMI_MarketApp"
  git status
  git log --oneline
  docker ps --filter "name=ami_postgres" --format '{{.Names}}: {{.Status}}'
  curl -s http://localhost:8000/v1/health
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

- **Anthropic API key.** Still not added.
- **Supabase project.** Not yet provisioned by Saiful.
- **Apple Developer team setup.** Done for Team `S7RBWM4879` but Sign in with Apple capability needs to be added to the bundle id for real prod usage.
- **App Store, APNs, real market data** — still external.

Nothing is blocking the next chunk.
