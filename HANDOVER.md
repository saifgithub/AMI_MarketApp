# Handover — AMI Trade build session

**Last updated:** 2026-05-11 (end of W5 Decision Journal + Lessons + Earn Path build)

Read this file **first** in any new session. It captures runtime state, what just landed, and a copy-paste prompt to continue.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, 7 commits, no remote yet |
| Latest commit | (this session) W5: Decision Journal + Lessons + Earn Path |
| Lines on disk | ~22,500 (PRD ~14k, backend ~4.5k, Flutter ~5k, content ~900) |

```
$ git log --oneline
<new>   W5: Decision Journal + Lessons + Earn Path
9da7f69 W4: Coach Your Agent — backend + Flutter, full diff-card / history flow
665135f Handover docs: HANDOVER.md + CLAUDE.md update
97d675c W3: 1-on-1 chat with 12 agents — backend + Flutter, end-to-end streaming
13349bf W2 onboarding flow: Concierge conversation, end-to-end iPhone-ready
96fbeaf Bootstrap Flutter project — iOS + Android scaffolding, fonts, lint clean
7063050 Day 1: PRD + backend foundation + Flutter shell + first 5 lessons
```

### Backend

| | |
|---|---|
| Process | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` |
| Logs | `tail -f /tmp/ami-backend.log` |
| Restart | `scripts/run_dev.sh backend` |
| LAN | `http://192.168.20.9:8000` |
| Health | `curl http://localhost:8000/v1/health` |
| Routes | `/v1/health`, `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, `/v1/coach/*`, **`/v1/journal/*`**, **`/v1/lessons/*`** |
| Tests | `pytest backend/tests/unit/ -q` → **67 passed** (W4: 54, +13 new) |

### Decision Journal routes (new this session)

| Route | What it does |
|---|---|
| `GET  /v1/journal/{user_id}` | Filter (entry_type / ticker) + paginate. Floor Pass capped at 30 days. |
| `GET  /v1/journal/{user_id}/entry/{entry_id}` | Single entry detail with full payload. |
| `POST /v1/journal/{user_id}/entry/{entry_id}/note` | Attach user note, tags, outcome. |
| `POST /v1/journal` | Append (used by capture hooks + free-form notes). |

Capture hooks now write entries automatically from:
- **1-on-1 message stream end** → `entry_type=one_on_one` with full transcript in payload.
- **Coach accept** → `entry_type=agent_coach` with version + overlay markdown.
- **Lesson quiz pass** → `entry_type=lesson_complete`.
- **Earn-Path unlock** → `entry_type=agent_unlock`.

### Lessons + Earn Path routes (new this session)

| Route | What it does |
|---|---|
| `GET  /v1/lessons` | Catalogue (track-grouped). Foundation track ships with 5 lessons. |
| `GET  /v1/lessons/{lesson_id}` | Full lesson — MDX parsed into structured blocks (markdown / quiz / chat_with). |
| `POST /v1/lessons/start` | Mark started. |
| `POST /v1/lessons/quiz` | Submit answers; returns score, per-question correctness + any newly unlocked agents. |
| `GET  /v1/lessons/progress/{user_id}` | Whole-app progress: lessons done/total, by-track breakdown, unlocked agents, next recommended lesson. |
| `GET  /v1/lessons/activations/{user_id}` | Activation records (earn_path / skip_path / trial / founder_grant). |
| `POST /v1/lessons/activations/grant` | Skip-path / founder-grant — instant unlock without quiz. |

### Earn Path mechanic (alpha rule)

An agent activates (`earn_path`) when the user passes the quiz on **every** lesson whose frontmatter `agent_callouts` lists that agent. With the current 5 alpha lessons:
- `004_market_order_vs_limit` → unlocks **Trader**.
- `001_what_is_a_stock` → unlocks **Fundamentals Analyst** (when its quiz lands).
- `002_what_is_a_market` → unlocks **Market Analyst** (when its quiz lands).
- `005_what_makes_a_price_move` → unlocks **Bull + Bear + Market** when their lesson quizzes land.

Other 12-agent activations require more lessons to ship (v1.0 hits the full Agent Academy).

### Agent gating

`POST /v1/agents/one_on_one/start` now returns **403** if a Floor Pass user tries to open a 1-on-1 with a locked agent. Concierge is always free. Paid tiers (`trader` / `floor_manager` / `trial_trader`) skip the gate.

### Mobile app

| | |
|---|---|
| Bundle | `ai.agenticmarketintel.amiTrade` v0.1.0+1 |
| Installed on | `TESTING IPHONE 13` (id `00008110-000261101A22801E`) |
| Build | iOS release, `AMI_API_URL=http://192.168.20.9:8000` baked in |
| Rebuild | `scripts/run_dev.sh` |

**Important:** the iPhone still has the W3 build. Redeploy with `scripts/run_dev.sh` to get W4 (Coach) + W5 (Journal + Lessons).

### What the app looks like now

1. Splash → Concierge onboarding (8 steps).
2. Mandate readback.
3. **Home shell (NEW)** — bottom nav: **Floor / Journal / Lessons**.
4. **Floor** — Concierge centerpiece + 12 agents. Locked agents are dimmed with a lock icon; tapping opens a "How to unlock" sheet that lists the required Earn-Path lessons.
5. **Journal** — every captured interaction in reverse-chronological order, with type filter chips (1-ON-1 / COACH / LESSONS / UNLOCKS). Tap any entry → detail with full transcript + note editor + outcome (win/loss/pending).
6. **Lessons** — track-grouped catalogue with progress card (X/N lessons + agents unlocked + next recommended), tap any lesson → reader with lightweight markdown rendering, inline multiple-choice quiz cards, submit, see per-question explanations, celebrate any agent unlocks.
7. **1-on-1** — unchanged, still has the Coach tune-icon, but now refuses if a Floor Pass user hits a locked agent.

---

## What's NOT yet built (W6 candidates)

| Feature | Spec doc |
|---|---|
| **Convene the Room** | Multi-agent debate visualizer. Wraps TradingAgents — `docs/02_agents/convene_the_room.md`. |
| **Sim Trading** | Paper portfolio + mock price feed + Trader agent → trade proposal → PM safety floor → journal entry. `docs/01_product/core_loop_and_features.md`. |
| **Settings + Mandate editor** | Editable mandate UI. The legitimate path to unblocking Coach refusals. |
| **Real LLM Concierge** | LLM-driven onboarding. `docs/02_agents/concierge.md`. |
| **Persistence migration** | docker-compose Postgres + Supabase auth scaffold. `docs/08_tech/data_model.md`. |
| **Cleanup** | `datetime.utcnow()` deprecation in older code. |

**Recommendation: Convene the Room next.** This is the showpiece — the visual proof that AMI Trade is a 12-agent product, not a chatbot. Built on top of the mock LLM, with a canned multi-agent script flowing into a verdict card. The PM safety-floor function (already in code) becomes the final gate, and the verdict lands in the Journal as `entry_type=room_run`. Then Sim Trading consumes Room verdicts. Persistence happens after the surface is complete and validated.

---

## Prompt to paste at the start of the next session

```
We're picking up the AMI Trade build. Read HANDOVER.md at the project root
(/Volumes/Extreme Pro/AMI_MarketApp/HANDOVER.md) first.

Default: build Convene the Room — the multi-agent debate visualizer.
Spec: docs/02_agents/convene_the_room.md.

  • Backend: room_runner orchestrates a deterministic 12-agent script
    in mock mode (real TradingAgents wrapper at W7+). PM safety-floor
    function gates the verdict. Append a `room_run` JournalEntry on
    completion with the full transcript in payload.
  • Flutter: a Matrix-style streaming console screen reachable from the
    Floor as a "CONVENE THE ROOM" CTA below the agent grid. Verdict
    card at the end with approve/reject + the agents involved.

Other options:
  1. Sim Trading scaffold (depends on Room verdicts → easier after Room).
  2. Settings + Mandate editor.
  3. Persistence migration (Postgres + Supabase auth).
  4. Real LLM Concierge.

Before writing code:
  cd "/Volumes/Extreme Pro/AMI_MarketApp"
  git status
  git log --oneline
  curl -s http://localhost:8000/v1/health
```

---

## Open questions / nothing-is-blocked items

- **Anthropic API key.** Still not added. Mock provider keeps everything working end-to-end (Coach, lessons, journal).
- **Persistence.** Overlays, journal entries, lesson progress, and activations all live in memory. Backend restart wipes them. This is fine for demo; W7 fixes it.
- **More lessons.** 5 lessons shipped; agent unlocks need more coverage before the Earn Path is genuinely playable end-to-end. Future Claude sessions can author lesson MDX files directly into `content/lessons/`.
- **App icon.** Still default Flutter icon.
- **Push notifications, real market data, App Store** — all need Saiful's external setup (APNs, Polygon/Yahoo account, App Store Connect).
- **Device user_id.** Still in `shared_preferences` under `ami.device_user_id`. Migrate on auth claim.

Nothing is blocking the next chunk. Just pick a direction.
