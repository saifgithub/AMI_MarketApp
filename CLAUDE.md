# CLAUDE.md — Project guide for Claude Code sessions

Loaded into every Claude Code session in this project. High-level orientation, behaviour-critical rules, and pointers. Detail lives under `docs/`.

---

## What this project is

**AMI Trade** is a mobile-first, simulation-only AI trading-education app where the user is the CEO of a 12-agent analyst team. Built on the [TradingAgents](https://github.com/TauricResearch/TradingAgents) multi-agent LLM framework and the AMI "Hex-Reinforced Precision" design language.

Full spec under [`docs/`](docs/). Start with [`docs/00_overview/`](docs/00_overview/) and [`docs/01_product/core_loop_and_features.md`](docs/01_product/core_loop_and_features.md).

---

## Team reality

One founder (Saiful) + Claude. No engineers, no QA, no separate designer.

- **Sequential work.** One thing happens at a time.
- **Managed services over custom infra.** Supabase + RevenueCat + Cloudflare > rolling our own.
- **Quality bar:** "good enough to learn from real users." Stealth alpha first.
- **Saiful is the human-in-the-loop.** He reviews content, makes decisions, tests on devices, opens dev accounts, talks to lawyers. Don't ask him to do code.
- **Translation is not blocking.** Produce structured i18n string files with context comments; Saiful arranges translation externally.

Full split: [`docs/10_delivery/you_do_i_do.md`](docs/10_delivery/you_do_i_do.md).

---

## External dependencies (read-only mounts)

| Mount | Purpose |
|---|---|
| `/Volumes/Extreme Pro/AMI AI Design System/` | AMI hex design system. Tokens, fonts, components. |
| `/Volumes/Extreme Pro/TradingAgent/` | TradingAgents multi-agent framework. The 12 agents wire through this. |

Read-only — integrate against them, don't modify.

---

## Decision pointers

| Topic | Locked decision |
|---|---|
| Endpoint of the journey | **Simulation-only, advisory-only, forever.** No brokerage integration. |
| Markets | **US equities at MVP.** GCC/Tadawul + Bursa later. |
| Languages | **EN at alpha, AR + MS at v1.0.** Pluggable i18n. |
| Platforms | **iOS at alpha, Android-GMS at v1.0, Huawei AppGallery at v1.1.** |
| Tech stack | **Flutter** frontend, **Python (FastAPI)** backend, **GCP Cloud Run + Supabase**. |
| Design | **AMI "Hex-Reinforced Precision"** — see [`docs/05_design/ami_hex_in_flutter.md`](docs/05_design/ami_hex_in_flutter.md). |
| Brand voice | Confident, analyst-to-analyst, numbers > adjectives, no marketing puffery. |
| Pricing | Floor Pass (free, ads) / Trader $14.99 / Floor Manager $34.99 + credit packs. |
| Onboarding | **Anonymous-first.** Concierge runs a conversational interview; account claim at the end. |
| Coach Your Agent — safety floor | **PM mandate enforcement is uncoachable.** Hard floor in PM prompt + deterministic compliance check. |

Full decision log: [`docs/11_decisions/decision_log.md`](docs/11_decisions/decision_log.md).

---

## Conventions

Full style rules: [`docs/08_tech/coding_conventions.md`](docs/08_tech/coding_conventions.md).

Behaviour-critical rule that affects every session — **the AI is named AMI**:

- Code, route names, log keys, tests, internal docs → **LLM** is fine.
- Lesson content, agent prompts, error sentinels, app copy → **AMI** by name. Never say "the AI" anywhere a user might read.

Other essentials:

- File headers: every new file gets a docstring/library comment explaining what it is and why.
- Comments: default to none; write self-documenting code. Add comments only when the *why* is non-obvious.

---

## What to do when you start a session

1. Read this file (already loaded).
2. Read [`HANDOVER.md`](HANDOVER.md) for the freshest state + immediate next steps.
3. Skim [`docs/10_delivery/project_plan.md`](docs/10_delivery/project_plan.md) — the Alpha → Beta → MVP roadmap. Your task is almost always in there.
4. `git log --oneline` to verify the commit chain.
5. Find the topic-specific doc(s) in `docs/` for your task.
6. Ask Saiful what he wants to work on if it's not obvious. He decides priorities.

---

## What NOT to do

- Don't refactor for hypothetical future requirements.
- Don't add comments explaining what code does.
- Don't introduce new dependencies without flagging — the stack is intentionally lean.
- Don't try to be "helpful" by adding features Saiful didn't ask for.
- Don't write tests that test the framework; test our logic.
- Don't proactively run destructive commands (force push, reset hard, etc.).
- Don't bypass the safety floor design in Coach Your Agent.

---

## Tone with Saiful

Direct, terse, no fluff. Numbers and tradeoffs, not sales talk. Match his pace — he moves fast and decides quickly. Don't over-explain. Don't ask for confirmation he didn't ask for. Don't summarize what you just did unless he asks.

He calls Claude "buddy" sometimes. That's fine.

---

## Autonomy + handover rules

- **Inside this project folder, execute autonomously.** Don't ask "ready to commit?" — just do it. (See `memory/feedback_workflow.md`.)
- **Watch your context budget.** When usage hits **45%**:
  1. `git status` and commit any uncommitted work.
  2. Update `HANDOVER.md` with latest state + a recommended prompt for the next agent.
  3. Update `memory/project_ami_trade.md` if any decisions/state changed.
  4. Surface to Saiful: *"Context at 45% — handover docs updated. Recommend starting a fresh session."*
- **Never delete files outside the project folder.** Saiful's exact words: *"unless it is something you physically cannot do, just go ahead and do it. just dont go crazy and delete files outside of your project folders!"*
