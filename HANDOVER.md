# Handover — AMI Trade build session

**Last updated:** 2026-05-11 (end of W4 Coach Your Agent build session)

Read this file **first** in any new session. It captures runtime state, what just landed, and a copy-paste prompt to continue.

---

## What's on disk + what's running

### Repo

| | |
|---|---|
| Path | `/Volumes/Extreme Pro/AMI_MarketApp/` |
| Git state | Clean working tree, 6 commits, no remote yet |
| Latest commit | (this session) W4: Coach Your Agent — backend + Flutter, full diff-card / history flow |
| Lines on disk | ~19,000 (PRD ~14k, backend ~3.2k, Flutter ~3k, content ~900) |

```
$ git log --oneline
<new>   W4: Coach Your Agent — backend + Flutter
665135f Handover docs: HANDOVER.md + CLAUDE.md update with current state + 45%-context swap rule
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
| Routes | `/v1/health`, `/v1/onboarding/*`, `/v1/agents/one_on_one/*`, **`/v1/coach/*`** |
| Tests | `pytest backend/tests/unit/ -q` → **54 passed** |

### Coach Your Agent routes (new)

| Route | What it does |
|---|---|
| `POST /v1/coach/start` | Opens a Coach session for a (user, agent). Returns session, current overlay, opener. |
| `POST /v1/coach/message` (SSE) | Streams a coach-mode chat response. |
| `POST /v1/coach/propose` | Crystallises the conversation into a structured `CoachProposal` (plain English + overlay markdown). Refuses if it touches the PM safety floor or mandate. |
| `POST /v1/coach/accept` | Persists the proposal as a new `UserOverlay` version. Returns `{ok:true,overlay}` or `{ok:false,refusal}` (e.g. edit limit hit). |
| `POST /v1/coach/reject` | Discards the pending proposal. |
| `POST /v1/coach/rollback` | Rolls back to a specific version. |
| `GET  /v1/coach/history/{user_id}/{agent_id}` | All versions + active marker + edits remaining. |

### Mobile app

| | |
|---|---|
| Installed on | `TESTING IPHONE 13` (id `00008110-000261101A22801E`, iOS 18.7.1) |
| Bundle | `ai.agenticmarketintel.amiTrade` v0.1.0+1 |
| Apple team | `S7RBWM4879` |
| Build flavor | iOS release, `AMI_API_URL=http://192.168.20.9:8000` baked in |
| Launch | Tap "AMI Trade" icon on TESTING IPHONE 13 home screen |
| Rebuild | `scripts/run_dev.sh` (one-shot: backend + Flutter dev with --dart-define) |

**Important note:** The iPhone currently has the W3 build installed. To exercise Coach Your Agent on the device, you need to redeploy via `scripts/run_dev.sh` (or `flutter run -d <ipad-id> --release --dart-define=AMI_API_URL=http://192.168.20.9:8000`).

### LLM provider

`MockProvider` is active by default. The mock path also drives Coach: `propose` returns a deterministic canned proposal that summarises the user's last message as a coaching note. Add `ANTHROPIC_API_KEY` to `backend/.env` for live LLM-driven proposals.

---

## What lands when Saiful taps the app

1. Splash → loading spinner
2. **Concierge conversation** (8 steps, ~3 min)
3. **Mandate readback** with confirm CTA
4. **Floor placeholder** showing all 12 agents + Concierge as tappable hexes
5. **1-on-1 chat** with any agent — SSE streaming, role-coloured bubbles
6. **Coach Your Agent** *(NEW)* — tap the tune icon (top-right) in any agent's 1-on-1 to enter coach mode. Chat to negotiate a change → tap "PROPOSE CHANGE" → diff card with Accept/Refine/Reject. Accepted overlays persist across sessions via a device-stable `user_id` (shared_preferences).
7. **Coach history** *(NEW)* — tap the history icon in the Coach header to see all saved versions with active marker, plain-English summary, and one-tap rollback.

### Safety floor: visible + locked

When the user tries to propose something that would touch PM mandate enforcement, weaken compliance flags (halal/ESG/etc), or enable shorts under `long_only` — the backend refuses both at the LLM level (in the PROPOSE_SYSTEM_PROMPT) and at a defence-in-depth heuristic layer. The UI surfaces refusals as an amber banner with the "edit your Mandate" suggestion. Spec: `docs/02_agents/safety_floor.md`.

### Edit caps

Floor Pass: 3 lifetime edits per agent. Trader / Trial Trader / Floor Manager: unlimited. Hit the cap and `accept` returns a `CoachRefusal` with reason `edit_limit_reached`.

### Retention

Floor Pass keeps 5 versions per agent; Trader 20; Floor Manager unlimited. Oldest non-active versions are dropped on save.

### Prompt composition (now wired)

```
agent.final_prompt = base_prompt
                   + mandate_overlay
                   + user_overlay         ← from OverlayStore (Coach output)
                   + safety_floor         ← PM only, appended LAST
```

The composition is gated by `user_id`: pass it to `build_agent_prompt(agent_id, mandate, user_id=...)` to fold in the active overlay. 1-on-1 sessions now plumb `user_id` from the device through to the prompt, so changes coached in one session show up in the next chat with that agent.

---

## What's NOT yet built (W5 candidates)

Pick one for the next session. All are well-specced in `docs/`.

| Feature | Roughly | Spec doc |
|---|---|---|
| **Real LLM Concierge** | Replace deterministic onboarding state machine with LLM intent classification + adaptive follow-ups. | `docs/03_onboarding/mandate_conversation.md`, `docs/02_agents/concierge.md` |
| **Decision Journal** | Capture every 1-on-1, Coach session, future Room session, sim trade. Searchable, filterable, replayable. | `docs/01_product/core_loop_and_features.md`, `docs/08_tech/data_model.md` (`journal_entries`) |
| **Convene the Room** | The showpiece — multi-agent debate visualizer. Wraps TradingAgents framework. | `docs/02_agents/convene_the_room.md`, `docs/08_tech/tradingagent_integration.md` |
| **Anonymous → claim auth** | Supabase Auth + Apple Sign-In + Email magic-link. Persist mandate + overlays beyond device. | `docs/03_onboarding/flow.md`, `docs/08_tech/auth.md` |
| **Coach: from-past-calls mode** | Currently we ship "from-scratch" mode only. Past-calls mode requires the Decision Journal to exist first (it surfaces the last 5 agent contributions for thumb-up/down feedback). | `docs/02_agents/coach_your_agent.md#the-coach-from-past-calls-mode` |
| **Coach: Raw Mode (Floor Manager)** | Direct markdown editor for the overlay block. Plumbing exists; UI is not built. | `docs/02_agents/coach_your_agent.md#raw-mode-floor-manager-v10` |
| **Persist Coach across processes** | OverlayStore is in-memory; restart loses overlays. Postgres-back at W5+ alongside auth. | `docs/08_tech/data_model.md` |
| **Cleanup: `datetime.utcnow()` deprecation** | 89→100 deprecation warnings in pytest. New Coach code uses `datetime.now(timezone.utc)`; older code still uses `utcnow()`. | — |

**My recommendation:** **Anonymous → claim auth + persistent storage (Supabase)** next. Coach Your Agent now creates real user state (overlay versions per device) that vanishes on backend restart. Putting Postgres behind both `mandates` and `user_overlays` is the obvious next move, and it pairs naturally with Supabase Auth so the overlays survive across devices.

---

## Prompt to paste at the start of the next session

```
We're picking up the AMI Trade build. Read `HANDOVER.md` at the project root
(/Volumes/Extreme Pro/AMI_MarketApp/HANDOVER.md) first — that's the latest
runtime + commit state. Read CLAUDE.md and the relevant `docs/` files for
the section we're working on. Then:

[ pick ONE of these, or say "you decide" ]

  1. Anonymous → claim auth (Supabase Auth + Apple Sign-In + magic-link)
     + Postgres-back the mandate, overlay store, and journal.
     Spec: docs/03_onboarding/flow.md + docs/08_tech/auth.md.

  2. Build the Decision Journal — capture + replay every interaction
     (Coach proposals included). Postgres-backed, polymorphic entry types.
     Spec: docs/01_product/core_loop_and_features.md + docs/08_tech/data_model.md.

  3. Build Convene the Room — the multi-agent debate visualizer.
     Wraps TradingAgents framework. Spec: docs/02_agents/convene_the_room.md.

  4. Replace the deterministic Concierge state machine with a real LLM-driven
     conversation. Spec: docs/02_agents/concierge.md.

  5. Coach: from-past-calls mode + Raw Mode for Floor Manager.
     Spec: docs/02_agents/coach_your_agent.md.

  6. Housekeeping: fix the datetime.utcnow() deprecation warnings in
     pytest output. Quick win.

Default if no preference: option 1 — Coach overlays + mandates currently die
on backend restart; persistence is the obvious blocker for further work.

Before you start writing code, run:
  cd "/Volumes/Extreme Pro/AMI_MarketApp"
  git status         # confirm clean working tree
  git log --oneline  # confirm HANDOVER.md describes the current head
  curl -s http://localhost:8000/v1/health  # confirm backend is reachable
                                            # (if not, ./scripts/run_dev.sh backend)
```

---

## Open questions / nothing-is-blocked items

- **Anthropic API key.** Saiful has not yet added one. Mock provider keeps the full UX working (Coach included — proposals are seeded from the user's last message).
- **GCP migration.** Scheduled for W9.
- **Supabase.** Not yet provisioned. Used at W5+ for auth + persistent mandate + overlay store.
- **Translation (AR + MS).** v1.0 work.
- **App icon.** Default Flutter icon still.
- **Device user_id.** Stored in `shared_preferences` under `ami.device_user_id`. When auth lands, migrate this to the real user_id (one-time migration on first claim).

Nothing is blocking the next chunk of work. Just pick a direction.
