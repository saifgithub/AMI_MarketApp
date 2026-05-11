# CLAUDE.md — Project guide for Claude Code sessions

This file is loaded automatically into every Claude Code session in this project. It contains the high-level orientation, conventions, and pointers needed to work effectively on AMI Trade.

---

## What this project is

**AMI Trade** is a mobile-first, simulation-only AI trading-education app where the user is the CEO of a 12-agent analyst team. It is built on the [TradingAgents](https://github.com/TauricResearch/TradingAgents) multi-agent LLM framework and the AMI "Hex-Reinforced Precision" design language.

The full spec lives in [`docs/`](docs/). Start with [`docs/00_overview/`](docs/00_overview/) and [`docs/01_product/core_loop_and_features.md`](docs/01_product/core_loop_and_features.md) for orientation.

---

## Team reality (important context)

This product is being built by **one founder (Saiful) + AI coding partners (Claude)**. There is no team of engineers. There is no QA team. There is no separate designer.

Implications:
- **Assume sequential work.** No parallel teams. One thing happens at a time.
- **Trust managed services over custom infra.** Supabase + RevenueCat + Cloudflare > rolling our own.
- **Quality bar is "good enough to learn from real users."** Stealth alpha first, polish later.
- **Saiful is the human-in-the-loop.** He reviews content, makes decisions, tests on real devices, opens dev accounts, talks to lawyers. Don't ask him to do code.
- **Translation is not blocking.** Produce structured i18n string files with context comments; Saiful arranges translation externally.

See [`docs/10_delivery/you_do_i_do.md`](docs/10_delivery/you_do_i_do.md) for the full responsibility split.

---

## External dependencies (read-only mounts)

| Mount | Purpose |
|---|---|
| `/Volumes/Extreme Pro/AMI AI Design System/` | The AMI hex design system. Tokens, fonts, components, reference. Read [`README.md`](/Volumes/Extreme%20Pro/AMI%20AI%20Design%20System/README.md) for the full spec. |
| `/Volumes/Extreme Pro/TradingAgent/` | The TradingAgents multi-agent framework. Our 12 agents are wired through this. See [`README.md`](/Volumes/Extreme%20Pro/TradingAgent/README.md) and [`CLAUDE.md`](/Volumes/Extreme%20Pro/TradingAgent/CLAUDE.md). |

Both directories are read-only references. We integrate against them; we do not modify them.

---

## Decision pointers

| Topic | Locked decision |
|---|---|
| Endpoint of the journey | **Simulation-only, advisory-only, forever.** No brokerage integration. |
| Markets | **US equities at MVP.** GCC/Tadawul + Bursa later. |
| Languages | **EN at alpha, AR + MS at v1.0.** Pluggable i18n architecture. |
| Platforms | **iOS at alpha, Android-GMS at v1.0, Huawei AppGallery at v1.1.** |
| Tech stack | **Flutter** frontend, **Python (FastAPI)** backend, **GCP Cloud Run + Supabase**. |
| Design | **AMI "Hex-Reinforced Precision"** — read [`docs/05_design/ami_hex_in_flutter.md`](docs/05_design/ami_hex_in_flutter.md). |
| Brand voice | Confident, analyst-to-analyst, numbers > adjectives, no marketing puffery. See AMI design system README. |
| Pricing | Floor Pass (free, ads) / Trader $14.99 / Floor Manager $34.99 + credit packs. |
| Onboarding | **Anonymous-first.** Concierge runs a conversational interview; account claim at the end. |
| Coach Your Agent — safety floor | **Portfolio Manager's mandate enforcement is uncoachable.** Hard floor in PM prompt + deterministic compliance check function. |

Full decision log: [`docs/11_decisions/decision_log.md`](docs/11_decisions/decision_log.md).

---

## Coding conventions (when we get there)

### Flutter

- **Theme tokens** live in `lib/theme/` and mirror `colors_and_type.css` from the AMI design system.
- **Hex shapes** via `ClipPath` + `CustomPainter`. Flat-topped hexagons. Corner cuts ~10px on mobile.
- **Type ramp**: Inter for body, JetBrains Mono for numbers/labels/buttons (UPPERCASE 0.1em letter-spacing).
- **Dark only.** Canvas `#0f172a`. No light theme.
- **RTL-aware** from day one. `padding-inline`, `margin-inline`, `Directionality` widget tree.
- State management: **Riverpod**. (Decided in [`docs/08_tech/flutter_implementation.md`](docs/08_tech/flutter_implementation.md).)

### Python backend

- **FastAPI** for the API.
- **Pydantic** for schemas — match the Mandate, Agent, JournalEntry data-model definitions in [`docs/08_tech/data_model.md`](docs/08_tech/data_model.md).
- **Async-first.** All LLM and DB calls await.
- **TradingAgents integration**: wrap their `TradingAgentsGraph` in our own service layer (`agents/service.py`) that applies the mandate overlay before propagation.
- **No secrets in code.** Use GCP Secret Manager via env vars.

### Naming

- Code identifiers: `snake_case` Python, `camelCase` Dart/Flutter.
- Database tables: `snake_case`, plural (`users`, `mandates`, `agent_runs`).
- Agent IDs: `fundamentals_analyst`, `market_analyst`, ..., `portfolio_manager`. Lowercase snake.

### Comments

- Default to no comments. Write self-documenting code.
- Add comments only when the *why* is non-obvious (a subtle invariant, a workaround, a hidden constraint).
- Never explain *what* the code does — names should.

---

## What to do when you start a session

1. Read this file (already loaded).
2. Skim [`docs/00_overview/vision_and_positioning.md`](docs/00_overview/vision_and_positioning.md) if you haven't.
3. Find the topic-specific doc(s) in `docs/` for your current task.
4. Ask Saiful what he wants to work on if it's not obvious. He decides priorities.

## What NOT to do

- Don't refactor for hypothetical future requirements.
- Don't add comments explaining what code does.
- Don't introduce new dependencies without flagging — the stack is intentionally lean.
- Don't try to be "helpful" by adding features Saiful didn't ask for.
- Don't write tests that test the framework; test our logic.
- Don't proactively run destructive commands (force push, reset hard, etc.).
- Don't bypass the safety floor design in Coach Your Agent.

---

## Working in this repo

Current top-level structure:

```
AMI_MarketApp/
├── docs/                        ← PRD (12 sections, 69 files)
├── mobile/                      ← Flutter app (iOS + Android-GMS scaffolded)
│   ├── lib/                       theme, widgets/hex, widgets/chat, screens,
│   │                              services/api, state/, models/
│   ├── ios/                       generated by flutter create
│   ├── android/                   generated; activated at v1.0
│   └── pubspec.yaml
├── backend/                     ← Python 3.13 FastAPI service
│   ├── app/
│   │   ├── api/                   /v1/onboarding/* + /v1/agents/one_on_one/*
│   │   ├── agents/                overlay generator + safety floor (pure fns)
│   │   ├── services/              llm_gateway, agent_runner, concierge_engine,
│   │   │                          session_store, agent_prompts
│   │   ├── schemas/               Pydantic — Mandate, Agent, RoomRun, Verdict,
│   │   │                          OnboardingSession, ChatMessage
│   │   └── core/                  config (env-var driven), logging (structlog)
│   ├── tests/unit/                103 passing tests
│   └── .venv/                     python3.13 venv (auto-created by run_dev.sh)
├── content/                     ← Lessons (MDX), strings (JSON), agent prompts
│   ├── lessons/                   13 lessons across 7 tracks
│   ├── i18n/                      empty placeholder for v1.0
│   └── agents/                    13 base prompts (12 trading + Concierge)
├── infra/local/                 ← Docker Compose for local dev stack
├── scripts/                     ← bootstrap_mobile.sh, run_dev.sh
├── docker-compose.yml
├── HANDOVER.md                  ← latest session-end state (start here)
├── README.md
└── CLAUDE.md                    ← this file
```

## Current state (snapshot — git is source of truth)

- **13 commits in.** Latest: W11 (Flutter LIVE/MOCK quote-source pill).
- **Backend** runs locally via `scripts/run_dev.sh` on port 8000.
- **Postgres** at host port `5434` (`ami_postgres` container). RLS policies live but dormant under the superuser connection.
- **App** installed on iPhone `TESTING IPHONE 13` (device id `00008110-000261101A22801E`), bundle `ai.agenticmarketintel.amiTrade`, signed under Apple Team `S7RBWM4879`. Still showing the W3 build until redeployed.
- **LLM provider** auto-switches to Anthropic the moment `ANTHROPIC_API_KEY` lands in `backend/.env`. Validate with `cd backend && .venv/bin/python -m scripts.llm_smoke` — expect PASS on all three tiers. Per-agent tier routing is wired (`AGENT_MIN_TIER` in `llm_gateway.py`): PM always runs on `premium`, Concierge runs on `cheap`, analysts run on `mid`. Status: `GET /v1/llm/status`.
- **Market data** pluggable. `USE_REAL_MARKET_DATA=true` in `backend/.env` flips quotes from the deterministic mock walk to live Yahoo (with mock fallback for unknown tickers / network errors). `/v1/sim/quote/{ticker}` returns `{"ticker","price","source"}`.

Run `cat HANDOVER.md` at the start of any new session for the freshest state + immediate next steps. Run `git log --oneline` to verify commit chain hasn't moved past what HANDOVER.md describes.

---

## Tone with Saiful

Direct, terse, no fluff. Numbers and tradeoffs, not sales talk. Match his pace — he moves fast and makes decisions quickly. Don't over-explain. Don't ask for confirmation he didn't ask for. Don't summarize what you just did unless he asks.

He calls Claude "buddy" sometimes. That's fine.

## Autonomy + handover rules

- **Inside this project folder, execute autonomously.** Don't ask "ready to commit?" — just do it. (See `memory/feedback_workflow.md`.)
- **Watch your context budget.** When usage hits **45%**, proactively:
  1. Run `git status` and commit any uncommitted work.
  2. Update `HANDOVER.md` at project root with the latest state + a recommended prompt for the next agent.
  3. Update `memory/project_ami_trade.md` if any decisions/state changed since last update.
  4. Surface to Saiful: *"Context at 45% — handover docs updated. Recommend starting a fresh session for the next chunk."*
- **Never delete files outside the project folder.** Saiful's exact words: *"unless it is something you physically cannot do, just go ahead and do it. just dont go crazy and delete files outside of your project folders!"*
