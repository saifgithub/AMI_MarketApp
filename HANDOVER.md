# Handover — AMI Trade build session

**Last updated:** 2026-05-11 (end of W6 Convene the Room build session)

Read this file **first** in any new session. It captures runtime state, what just landed, and a copy-paste prompt to continue.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, 8 commits, no remote yet |
| Latest commit | (this session) W6: Convene the Room + 7 more lessons |
| Lines on disk | ~26,500 (PRD ~14k, backend ~5.6k, Flutter ~6.4k, content ~1.4k) |

```
$ git log --oneline
<new>   W6: Convene the Room — 12-agent streaming debate, verdict card, +7 lessons
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
| Routes | `/v1/health`, `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/coach/*`, `/v1/journal/*`, `/v1/lessons/*`, **`/v1/room/*`** |
| Tests | `pytest backend/tests/unit/ -q` → **72 passed** (W5: 67, +5 new) |

### Convene the Room routes (new this session)

| Route | What it does |
|---|---|
| `POST /v1/room/stream` (SSE) | Run a full Room session on a ticker — streams `phase` / `agent_token` / `agent_done` / `verdict` / `done` events. |
| `GET  /v1/room/{run_id}` | Persisted snapshot — transcript + verdict + status + duration. |
| `GET  /v1/room/user/{user_id}` | Recent runs for a user, newest first. |

### The Room mechanic

`backend/app/services/room_runner.py` orchestrates the 6 spec'd phases:
1. ANALYSTS — Fundamentals / Market / News / Social
2. RESEARCHERS — Bull / Bear
3. SYNTHESIS — Research Manager
4. EXECUTION — Trader proposes a specific trade
5. RISK — Aggressive / Conservative / Neutral debators
6. VERDICT — Portfolio Manager

Every agent emits character-by-character SSE tokens. The PM verdict goes through the **same deterministic safety-floor function** used in 1-on-1 (`app/agents/safety_floor.check_mandate_compliance`). That means:
- A halal-flagged user running Convene on a non-halal ticker sees **REJECT** with `overridden_from_llm=true`.
- A blocklist hit, a single-name cap breach, or a drawdown breach all flip to REJECT regardless of the LLM-style narrative.
- `verdict.violations` lists what failed.

Mandate `risk_score` scales position size: 1 → ~1.5%, 3 → ~3%, 5 → ~4.5%. Profile per ticker is hash-seeded — same ticker produces a consistent set of numbers across runs (clean for demos).

### Journal hook

Every completed Room run appends an `entry_type=room_run` JournalEntry with full transcript + verdict in the payload. Outcome starts as `pending` — the user can mark it WIN / LOSS later from the entry detail screen.

### Lessons content

| Track | Count |
|---|---|
| Foundations | 5 |
| Fundamentals Analysis | 1 |
| Technical Analysis | 1 |
| News & Macro | 1 |
| Sentiment & Behaviour | 1 |
| Risk & Portfolio Construction | 2 |
| Edge & Process | 1 |
| **Total** | **12** |

Earn-Path coverage went from 1 agent (Trader) → 11 agents — only Research Manager is still missing a lesson. Floor Pass users now have a real ladder to climb.

### Mobile app

| | |
|---|---|
| Bundle | `ai.agenticmarketintel.amiTrade` v0.1.0+1 |
| Installed on | `TESTING IPHONE 13` |
| Rebuild | `scripts/run_dev.sh` |

**The iPhone still has the W3 build.** Redeploy to see W4 (Coach) + W5 (Journal + Lessons + Earn Path) + W6 (Convene the Room).

### What the app does now

1. Onboarding (Concierge) → Mandate readback.
2. Home shell: Floor / Journal / Lessons.
3. **Floor** — Concierge centerpiece, 12-agent grid with locked-agent overlays, **a new "CONVENE THE ROOM" CTA below the grid**.
4. Tap Convene → ticker picker sheet (curated suggestions + free-text) → **Room console screen**:
   - Phase banner (ANALYSTS / RESEARCHERS / SYNTHESIS / EXECUTION / RISK / VERDICT).
   - Agent feed with role-colour hex avatars, abbreviation labels, live pulse on the active speaker.
   - Per-agent contribution streams in character-by-character.
   - Final verdict card — green APPROVE with size/entry/stop/target/horizon, or amber REJECT with violation list. "SAFETY FLOOR" badge when the floor overrode the LLM.
   - "Saved to Journal" confirmation footer.
5. **Journal** detail now renders `room_run` payloads with full transcript + verdict block.
6. **Lessons** — 12 lessons across 7 tracks. Passing quizzes unlocks agents on the Floor.
7. **1-on-1** + **Coach** unchanged (Coach still has the tune-icon entry).

---

## What's NOT yet built (W7 candidates)

| Feature | Spec doc |
|---|---|
| **Sim Trading** | Accept the Room verdict as a real trade in the user's sim portfolio. P&L tracking. Outcome auto-flip from `pending` on stop/target hit. `docs/01_product/core_loop_and_features.md`. |
| **Settings + Mandate editor** | Edit mandate post-onboarding. The legitimate path to unblock Coach refusals + change compliance flags. |
| **Real LLM Concierge** | LLM-driven onboarding. `docs/02_agents/concierge.md`. |
| **Persistence migration** | docker-compose Postgres locally, store schemas mapped. `docs/08_tech/data_model.md`. |
| **Supabase auth scaffold** | Anonymous → Apple Sign-In or magic-link claim. `docs/08_tech/auth.md`. |
| **More lessons** | One Research Manager lesson + content for tracks beyond Foundations. |
| **Cleanup** | `datetime.utcnow()` deprecation in older code. |

**Plan toward MVP** (autonomy granted through MVP):

- **W7 — Sim Trading + Settings/Mandate editor.** Closes the core loop: Room verdict → trade → outcome → journaled with win/loss.
- **W8 — Persistence migration (Postgres + Supabase Auth scaffold) + more lessons.** Turns the demo into something that survives a restart and supports real users.

After W8 we have an MVP — every feature wired, persistent, multi-user-ready, on mock LLM. Adding the Anthropic key is a config change.

---

## Prompt to paste at the start of the next session

```
We're picking up the AMI Trade build. Read HANDOVER.md at the project root
(/Volumes/Extreme Pro/AMI_MarketApp/HANDOVER.md) first.

Default for W7: build Sim Trading + Settings/Mandate editor.

Sim Trading
  • Schema: SimPortfolio, SimHolding, SimTrade (already roughed in
    schemas/trade.py — Portfolio / Holding / ProposedTrade exist).
  • Service: sim_portfolio_store + tick simulator (random walk seeded
    per ticker, same idea as the Room profile). PM safety-floor runs
    on every submit.
  • API: open portfolio (default $10k), submit a trade (with verdict
    reference from a Room), list holdings, mark trade outcome.
  • Flutter: portfolio screen (cash + holdings + P&L), trade ticket
    sheet (size / entry / stop / target from the Room verdict),
    holdings list with current marks.
  • Journal capture: sim_trade entries on submit + outcome update.

Settings + Mandate editor
  • Flutter Settings tab in HomeShell (Floor / Journal / Lessons / Settings).
  • Read/write the mandate. Surface compliance flags as toggles.
  • Save → mandate_edit journal entry + emit refresh so overlays update.

Other options:
  1. Persistence migration (Postgres + Supabase auth).
  2. Real LLM Concierge.
  3. Author more lessons.

Saiful has granted full autonomy through MVP — execute, don't ask.
File-header rule: every new file gets a docstring/library comment that
explains what it is and why it exists.

Before writing code:
  cd "/Volumes/Extreme Pro/AMI_MarketApp"
  git status
  git log --oneline
  curl -s http://localhost:8000/v1/health
```

---

## Open questions / nothing-is-blocked items

- **Anthropic API key.** Still not added. The Room runs purely on canned templates today; live LLM swap is a single function in `room_runner.py` once a key lands.
- **Persistence.** Every store is in-memory; overlay + journal + lesson progress + activations + room runs all vanish on backend restart. W8 fixes it.
- **Locale enforcement.** The Room safety floor only checks `locale_allowed_universe` if the caller supplies a set; default is "no restriction." Right call for alpha (US equities only).
- **Multi-round Convene.** Floor Manager tier supports 3 rounds per spec; alpha runs only round 1. Easy add when real LLM is on.
- **Push notifications, real market data, App Store** — still require external setup (APNs, market-data account, App Store Connect).

Nothing is blocking the next chunk.
