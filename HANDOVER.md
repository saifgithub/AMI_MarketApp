# Handover — AMI Trade build session

**Last updated:** 2026-05-11 (end of W3 build session, after `97d675c`)

Read this file **first** in any new session. It captures runtime state, what just landed, and a copy-paste prompt to continue.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, 4 commits, no remote yet |
| Latest commit | `97d675c` W3: 12-agent 1-on-1 streaming |
| Lines on disk | ~16,500 (PRD ~14k, backend ~2k, Flutter ~1.5k, content ~900) |

```
$ git log --oneline
97d675c W3: 1-on-1 chat with 12 agents — backend + Flutter, end-to-end streaming
13349bf W2 onboarding flow: Concierge conversation, end-to-end iPhone-ready
96fbeaf Bootstrap Flutter project — iOS + Android scaffolding, fonts, lint clean
7063050 Day 1: PRD + backend foundation + Flutter shell + first 5 lessons
```

### Backend (running on Saiful's Mac)

| | |
|---|---|
| Process | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` |
| Logs | `tail -f /tmp/ami-backend.log` |
| Stop | `lsof -ti:8000 \| xargs kill -9` |
| Restart | `scripts/run_dev.sh backend` |
| LAN address | `http://192.168.20.9:8000` (iPhone-reachable) |
| Health check | `curl http://localhost:8000/v1/health` → `{"status":"ok","version":"0.1.0","env":"local"}` |
| Routes | `/v1/health`, `/v1/onboarding/*`, `/v1/agents/one_on_one/*` |
| Tests | `pytest backend/tests/unit/ -q` → 37 passed |

### Mobile app

| | |
|---|---|
| Installed on | `TESTING IPHONE 13` (id `00008110-000261101A22801E`, iOS 18.7.1) |
| Bundle | `ai.agenticmarketintel.amiTrade` v0.1.0+1 |
| Apple team | `S7RBWM4879` |
| Build flavor | iOS release, `AMI_API_URL=http://192.168.20.9:8000` baked in |
| Launch | Tap "AMI Trade" icon on TESTING IPHONE 13 home screen |
| Rebuild | `scripts/run_dev.sh` (one-shot: backend + Flutter dev with --dart-define) |

### LLM provider

`MockProvider` is active by default. Each of the 13 agents has a distinct canned response, streamed char-by-char so the UX feels real. To enable live Claude:

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." >> "/Volumes/Extreme Pro/AMI_MarketApp/backend/.env"
lsof -ti:8000 | xargs kill -9
cd "/Volumes/Extreme Pro/AMI_MarketApp" && ./scripts/run_dev.sh backend
```

The gateway will detect the key, register `AnthropicProvider`, and route by mandate tier:
- Floor Pass → Haiku 4.5
- Trader / Trial Trader → Sonnet 4.6
- Floor Manager → Opus 4.7

---

## What lands when Saiful taps the app

Full flow currently works:

1. Splash → loading spinner
2. **Concierge conversation** (8 steps, ~3 min)
3. **Mandate readback** with confirm CTA
4. **Floor placeholder** showing all 12 agents + Concierge as tappable hexes
5. **1-on-1 chat** with any agent — SSE streaming, role-coloured bubbles, mock or live LLM

Onboarding answers populate a structured `Mandate` object. The mandate is currently in-memory only (Phase: anonymous session). At Auth-implementation time (W5+), the session-id → user-id claim will persist mandates to Postgres.

---

## What's NOT yet built (W4 candidates)

Pick one for the next session. All are well-specced in `docs/`.

| Feature | Roughly | Spec doc |
|---|---|---|
| **Real LLM Concierge** | Replace deterministic onboarding state machine with LLM intent classification + adaptive follow-ups. Tone shifts on hesitation. Same 8-step flow, but Concierge feels actually intelligent. | `docs/03_onboarding/mandate_conversation.md`, `docs/02_agents/concierge.md` |
| **Coach Your Agent** | The flagship differentiator. User chats with any agent to edit its prompt. Diff card with Accept/Refine/Reject. Versioned overlays. Safety floor on PM stays locked. | `docs/02_agents/coach_your_agent.md`, `docs/02_agents/safety_floor.md` |
| **Decision Journal** | Capture every 1-on-1, future Room session, sim trade, mandate edit. Searchable, filterable, replayable. Floor Pass: 30-day cap; paid: unlimited. | `docs/01_product/core_loop_and_features.md` (Sim & Decision Journal section), `docs/08_tech/data_model.md` (`journal_entries` table) |
| **Convene the Room** | The showpiece — multi-agent debate visualizer. All 12 agents run on a ticker, Matrix Console streams reasoning, verdict card at end. Wraps TradingAgents framework. | `docs/02_agents/convene_the_room.md`, `docs/08_tech/tradingagent_integration.md` |
| **Anonymous → claim auth** | Supabase Auth integration. Apple Sign-In + Email magic-link. Persist mandate beyond session. 7-day Trader trial activates on claim. | `docs/03_onboarding/flow.md`, `docs/08_tech/auth.md` |
| **Cleanup: `datetime.utcnow()` deprecation** | 89 deprecation warnings in pytest output across 6 files. Replace with `datetime.now(timezone.utc)`. Low-risk housekeeping. | — |

My recommendation: **Coach Your Agent** next. It's the single most differentiating feature, the design is fully specced, and the 1-on-1 infrastructure we just built is exactly the foundation it needs.

---

## Prompt to paste at the start of the next session

```
We're picking up the AMI Trade build. Read `HANDOVER.md` at the project root
(/Volumes/Extreme Pro/AMI_MarketApp/HANDOVER.md) first — that's the latest
runtime + commit state. Read CLAUDE.md and the relevant `docs/` files for
the section we're working on. Then:

[ pick ONE of these, or say "you decide" ]

  1. Build Coach Your Agent — the flagship feature. Conversational prompt
     editing for any agent, with a diff card, accept/refine/reject, version
     history, safety-floor locking on PM. Spec: docs/02_agents/coach_your_agent.md.

  2. Build the Decision Journal — capture + replay every interaction.
     Postgres-backed, polymorphic entry types. Spec: docs/01_product/core_loop_and_features.md
     plus docs/08_tech/data_model.md.

  3. Build Convene the Room — the multi-agent debate visualizer.
     Wraps TradingAgents framework. Spec: docs/02_agents/convene_the_room.md.

  4. Replace the deterministic Concierge state machine with a real LLM-driven
     conversation. Spec: docs/02_agents/concierge.md.

  5. Anonymous → claim auth (Supabase Auth + Apple Sign-In + magic-link).
     Spec: docs/03_onboarding/flow.md + docs/08_tech/auth.md.

  6. Housekeeping: fix the 89 datetime.utcnow() deprecation warnings in
     pytest output. Quick win.

Default if no preference: option 1 (Coach Your Agent) — biggest differentiator,
foundation already in place from the 1-on-1 work.

Before you start writing code, run:
  cd "/Volumes/Extreme Pro/AMI_MarketApp"
  git status         # confirm clean working tree
  git log --oneline  # confirm HANDOVER.md describes the current head
  curl -s http://localhost:8000/v1/health  # confirm backend is reachable
                                            # (if not, ./scripts/run_dev.sh backend)
```

---

## Open questions / nothing-is-blocked items

- **Anthropic API key.** Saiful has not yet added one. Mock provider keeps the UX working in the meantime. Whenever he adds it, no code change is needed.
- **GCP migration.** Scheduled for W9 per timeline. Currently local-only on Mac.
- **Supabase.** Not yet provisioned. Used at W5+ for auth + persistent mandate.
- **Translation (AR + MS).** v1.0 work. i18n string structure ready but no content yet.
- **App icon.** Default Flutter icon still. Replace with AMI hex when we get to polish.

Nothing is blocking the next chunk of work. Just pick a direction.
