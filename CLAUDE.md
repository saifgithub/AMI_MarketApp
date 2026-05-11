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

Current state: empty project. Setup happens in month 1.

When code lands, expect this top-level structure:

```
AMI_MarketApp/
├── docs/                        ← PRD (this folder)
├── mobile/                      ← Flutter app
│   ├── lib/
│   ├── ios/
│   ├── android/
│   └── pubspec.yaml
├── backend/                     ← Python (FastAPI) service
│   ├── app/
│   ├── tests/
│   └── pyproject.toml
├── content/                     ← Lessons (MDX), strings (JSON), agent prompts
│   ├── lessons/
│   ├── i18n/
│   └── agents/
├── infra/                       ← Terraform / IaC
│   └── gcp/
├── README.md
└── CLAUDE.md                    ← this file
```

---

## Tone with Saiful

Direct, terse, no fluff. Numbers and tradeoffs, not sales talk. Match his pace — he moves fast and makes decisions quickly. Don't over-explain. Don't ask for confirmation he didn't ask for. Don't summarize what you just did unless he asks.

He calls Claude "buddy" sometimes. That's fine.
