# Handover — AMI Trade build session

**Last updated:** 2026-05-11 (end of W7 Sim Trading + Mandate editor session)

Read this file **first** in any new session. It captures runtime state, what just landed, and a copy-paste prompt to continue.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, 9 commits, no remote yet |
| Latest commit | (this session) W7: Sim Trading + Settings/Mandate editor |
| Lines on disk | ~31,500 (PRD ~14k, backend ~6.7k, Flutter ~9.4k, content ~1.4k) |

```
$ git log --oneline
<new>   W7: Sim Trading + Mandate editor — close the core loop
5239353 W6: Convene the Room — 12-agent streaming debate + 7 more lessons
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
| Routes | `/v1/health`, `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/coach/*`, `/v1/journal/*`, `/v1/lessons/*`, `/v1/room/*`, **`/v1/sim/*`**, **`/v1/mandate/*`** |
| Tests | `pytest backend/tests/unit/ -q` → **84 passed** (W6: 72, +12) |

### Sim Trading routes (new this session)

| Route | What it does |
|---|---|
| `GET  /v1/sim/portfolio/{user_id}` | Snapshot: cash + holdings (with marks + unrealised P&L) + total value + drawdown |
| `POST /v1/sim/portfolio/{user_id}/reset` | Wipe and restart with $10k |
| `POST /v1/sim/submit` | Submit a trade — **PM safety floor runs server-side** (compliance, drawdown, single-name cap, halal, etc.) |
| `GET  /v1/sim/trades/{user_id}` | List trades (filter by status) |
| `POST /v1/sim/trades/{user_id}/evaluate` | Sweep open trades — flip won/lost on stop/target hit |
| `POST /v1/sim/trades/{user_id}/close` | Manual close |
| `GET  /v1/sim/quote/{ticker}` | Current mock mark |

### Mandate routes (new this session)

| Route | What it does |
|---|---|
| `GET   /v1/mandate/{user_id}` | Read current mandate (default-hydrated if none stored) |
| `PATCH /v1/mandate/{user_id}` | Shallow-merge updates; bumps version; writes `mandate_edit` journal entry |

### One unified mandate resolver

Every session endpoint (1-on-1, Coach, Room, Sim) now goes through `mandate_store.resolve_mandate(user_id, override, locale=...)`:
1. Stored mandate for `user_id` (set via Settings) takes priority.
2. Override dict (used by demo / tests) is next.
3. Hydrated defaults.

So flipping a compliance flag in Settings instantly changes how every agent reasons + how every trade is checked. No restart, no plumbing per endpoint.

### Mock price engine

`backend/app/services/sim_engine.py` runs a deterministic-per-ticker random walk (hash-seeded base price, per-second drift + volatility). Same ticker → same trajectory across the session, so the alpha demo feels coherent. Each refresh evaluates open trades against their stop/target and flips outcomes to `won` / `lost` with realised P&L computed.

A real market data feed (Polygon, Yahoo, IEX) is a swap for `SimEngine.current_price()` at W8+.

### Capture loops

Every action keeps writing to the Decision Journal automatically:
- **1-on-1** → `one_on_one`
- **Coach accept** → `agent_coach`
- **Lesson quiz pass** → `lesson_complete` + `agent_unlock`
- **Room run** → `room_run` (full transcript + verdict, outcome=pending)
- **Sim trade open** → `sim_trade` (outcome=pending)
- **Sim trade stop/target/manual close** → `sim_trade` (outcome=win/loss)
- **Mandate edit** → `mandate_edit` (with before/after diff)

The Journal detail screen renders all of these natively now — Room runs show the full 12-agent transcript, mandate edits show the diff.

### Mobile app

| | |
|---|---|
| Bundle | `ai.agenticmarketintel.amiTrade` v0.1.0+1 |
| Installed on | `TESTING IPHONE 13` |
| Rebuild | `scripts/run_dev.sh` |

**The iPhone still has the W3 build.** Redeploy to see W4–W7.

### What the app does now

**Bottom nav: Floor / Portfolio / Journal / Lessons / Settings** (5 tabs).

1. Onboarding → Mandate readback.
2. **Floor** — Concierge + 12 agents (locked dimmed with lock overlay + "How to unlock" sheet) + CONVENE THE ROOM CTA.
3. **Portfolio (NEW)** — total value + P&L + cash + drawdown card, holdings cards with unrealised P&L, trade list with status pills + manual close. Add-trade button opens the ticket sheet.
4. **Journal** — every action with full filter chips + detail screens for every entry type.
5. **Lessons** — 12 lessons, 7 tracks; quiz pass unlocks agents; "next recommended" surfaces.
6. **Settings (NEW)** — Mandate editor: Risk score slider (1–5), max drawdown picker (10/20/30/50/100), compliance toggles (halal / ESG-lite / no T/A/G / no fossil / long-only / liquid-only), read-only profile fields. Save bumps mandate version and refreshes everywhere.
7. **Convene the Room** — Matrix-style console, verdict card with **"OPEN TRADE TICKET"** button that pre-fills the trade ticket with size/entry/stop/target/horizon from the verdict. Safety floor reruns on submit.
8. **1-on-1** + **Coach** unchanged (Coach tune-icon in 1-on-1 header).

### The core loop is now closed

Convene → Verdict → Open trade ticket (pre-filled) → PM safety floor runs again on submit → Portfolio updates → As price walks, stop/target evaluation flips outcomes → Journal records every step (Room run + sim trade open + sim trade close + outcome).

---

## What's NOT yet built (W8 candidates — final MVP push)

| Feature | Spec doc |
|---|---|
| **Persistence migration** | docker-compose Postgres locally, migrate every in-memory store. `docs/08_tech/data_model.md` covers the schemas. |
| **Supabase auth scaffold** | Anonymous → Apple Sign-In / magic-link claim. `docs/08_tech/auth.md`. Migrate device_user_id → real user_id on claim. |
| **Real LLM Concierge** | Replace deterministic onboarding state machine. `docs/02_agents/concierge.md`. |
| **More lessons** | One Research Manager lesson + content for deeper tracks. |
| **Cleanup** | `datetime.utcnow()` deprecation in older code. |
| **Live LLM swap** | Single function in `room_runner.py` once `ANTHROPIC_API_KEY` is added. |

**W8 is MVP.** Persistence + Supabase scaffolding turn this from a demo that resets on backend restart into something a real user can actually use across days. After W8, adding the Anthropic key is a config change and everything flips to live reasoning.

---

## Prompt to paste at the start of the next session

```
We're picking up the AMI Trade build. Read HANDOVER.md at the project root
(/Volumes/Extreme Pro/AMI_MarketApp/HANDOVER.md) first.

Default for W8 — the MVP push:
  Persistence migration + Supabase auth scaffold.

Persistence
  • docker-compose up the local Postgres from infra/local/.
  • Use SQLAlchemy (async) + Alembic. Stack already has these
    available via pip — add if missing.
  • Migrate stores in this order (small → large blast radius):
    1. MandateStore   → mandates table
    2. OverlayStore   → user_overlays table
    3. JournalStore   → journal_entries table
    4. LessonsService → lessons_progress + agent_activations tables
    5. SimEngine      → sim_portfolios + sim_holdings + sim_trades
    6. RoomRunner     → room_runs table (+ jsonb transcript)
  • Each store keeps the same public API; only the storage backend
    changes. Tests stay valid.

Supabase auth scaffold
  • Just the wiring — don't require Saiful to provision Supabase yet.
    Use a local Postgres with a `users` table that mimics Supabase's
    `auth.users` schema. Real Supabase plugs in via env var swap later.
  • Anonymous flow: device_user_id from shared_preferences becomes the
    user_id; a 'claimed_at' column flips when the user signs in with
    Apple / email magic-link.
  • Apple Sign-In + email magic-link UI scaffolds. Real Supabase calls
    can be stubs that just store credentials locally — wire the real
    SDK when Saiful adds his Supabase project.

Saiful has granted full autonomy through MVP — execute, don't ask.
File-header rule: every new file gets a docstring/library comment
that explains what it is and why.

Before writing code:
  cd "/Volumes/Extreme Pro/AMI_MarketApp"
  git status
  git log --oneline
  curl -s http://localhost:8000/v1/health
```

---

## Open questions / nothing-is-blocked items

- **Anthropic API key.** Still not added. The whole product runs on mocks.
- **Persistence.** Everything in memory. Restart = wipe. W8 fixes it.
- **Mock price engine.** Random walk seeded per ticker; deterministic for the demo. Real feed at W8+.
- **App Store, APNs, real market data** — still external.

Nothing is blocking the next chunk.
