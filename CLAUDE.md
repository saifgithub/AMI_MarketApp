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

## In-repo sub-project: `Silent_Scout/` — aware, not engaged

`Silent_Scout/` is part of this repo but on a **different roadmap**: it's the research-only workspace for fine-tuning the 13 AMI Trade agents (Concierge first). Its README opens with *"Does not import from the production app. Does not ship."* — see `Silent_Scout/README.md`.

**Rule:** be aware it exists; **do not pay attention to it unless you're specifically assigned to it.** A session working on AMI Trade backend / Flutter / docs / promotion / infra should treat `Silent_Scout/` as out of scope:

- Don't include it in greps or scans for AMI Trade work (e.g., use `git grep -- ':!Silent_Scout/'` if a global grep would otherwise pick it up).
- Don't treat its code as authoritative for production — the production app doesn't import from it and isn't supposed to.
- Don't refactor across the boundary. The cross-references go one way only (Silent_Scout reads from `backend/app/services/llm_gateway.py` and `backend/app/agents/overlay_generator.py` to mirror their shapes — never the other direction).

If Saiful explicitly says *"work on Silent_Scout"* or names a Silent_Scout file, then go. Otherwise stay in the production tree.

The boundary protects two things: production stays trained on the live LLM through the gateway (not on local weights), and the research workspace can iterate freely without breaking running Alpha testers.

---

## Runtime state (read before assuming anything)

The system is **live** and serving today. Read this before assuming
the backend is on the Mac or that the LLM is mocked.

| Component | Where | Notes |
|---|---|---|
| **Mac** (this workstation) | Pure editor. **NO backend, NO database, NO Docker stack.** | Backend unit tests via `pytest backend/tests/unit/ -q` still work (sqlite tempfile fixture). Anything else goes through `/promote-to-alpha`. Don't start uvicorn or `docker compose up` on the Mac. |
| **Alpha backend** | `melehost` — Ubuntu Linux server, LAN `192.168.20.59`, SSH alias `melehost` | Stack: `ami_postgres` + `ami_redis` + `ami_api_alpha` + `ami_tunnel`, all in `~/ami_trade/` via Docker Compose. Code rsync'd from Mac via the promotion script. |
| **Public hostname** | `https://api-alpha.agenticmarketintel.ai` | Cloudflare Tunnel (token-mode connector running on melehost). TLS terminates at CF edge; backend doesn't open inbound ports. |
| **LLM provider** | **On-prem vLLM** at `http://192.168.20.74:8000` — separate Ubuntu host on the LAN | Serving `ami-llm` (Gemma 4 31B, NVFP4 quantized, 262k context — rebranded). Gateway prefers `vllm > anthropic > mock`. Per-(plan, agent) tier routing in `app/services/tier_policy.py::pick_tier`. **Not Anthropic, not OpenAI, not mock — real LLM.** |
| **Market data** | Yahoo via `yfinance`, with deterministic mock-walk fallback | `USE_REAL_MARKET_DATA=true` in melehost's `.env`. |
| **Code transport** | rsync via [`/promote-to-alpha`](.claude/commands/promote-to-alpha.md) (slash command) | No GitHub remote yet. Mac → melehost only path. |

Detail in [`docs/08_tech/hosting.md`](docs/08_tech/hosting.md) (melehost spec), [`docs/10_delivery/promotion_protocol.md`](docs/10_delivery/promotion_protocol.md) (how code ships), [`docs/08_tech/backend_modes.md`](docs/08_tech/backend_modes.md) (Flutter Alpha/Beta/Prod modes), and the freshest state in [`HANDOVER_R.md`](HANDOVER_R.md).

If a check fails (curl returns 502 / connect refused), debug from melehost — don't fall back to "let me start a backend on the Mac":

```bash
curl -s https://api-alpha.agenticmarketintel.ai/v1/health
ssh melehost "docker ps --filter 'name=ami_'"
ssh melehost "docker logs ami_api_alpha --tail 50"
```

---

## Decision pointers

| Topic | Locked decision |
|---|---|
| Endpoint of the journey | **Training simulator, simulation-only, forever.** AMI is not licensed to give investment advice; no brokerage integration ever. |
| Markets | **US equities at MVP.** GCC/Tadawul + Bursa later. |
| Languages | **EN at alpha, AR + MS at v1.0.** Pluggable i18n. |
| Platforms | **iOS at alpha, Android-GMS at v1.0, Huawei AppGallery at v1.1.** |
| Tech stack | **Flutter** frontend, **Python (FastAPI)** backend, **GCP Cloud Run + Supabase**. |
| Design | **AMI "Hex-Reinforced Precision"** — see [`docs/05_design/ami_hex_in_flutter.md`](docs/05_design/ami_hex_in_flutter.md). |
| Brand voice | Confident, analyst-to-analyst, numbers > adjectives, no marketing puffery. |
| Pricing | Floor Pass (free, ads) / Trader $14.99 / Floor Manager $34.99 + credit packs. |
| Onboarding | **Anonymous-first.** Concierge runs a conversational interview; account claim at the end. |
| Brief Your Agent — safety floor | **PM mandate enforcement is uncoachable.** Hard floor in PM prompt + deterministic compliance check. (Feature renamed from "Coach Your Agent" in AT:R27; the conceptual term "uncoachable" stays as the safety-floor's resistance label.) |

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
2. Read [`HANDOVER_R.md`](HANDOVER_R.md) for the freshest state + immediate next steps.
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
- Don't bypass the safety floor design in Brief Your Agent.

---

## Tone with Saiful

Direct, terse, no fluff. Numbers and tradeoffs, not sales talk. Match his pace — he moves fast and decides quickly. Don't over-explain. Don't ask for confirmation he didn't ask for. Don't summarize what you just did unless he asks.

He calls Claude "buddy" sometimes. That's fine.

---

## Autonomy + handover rules

- **Inside this project folder, execute autonomously.** Don't ask "ready to commit?" — just do it. (See `memory/feedback_workflow.md`.)
- **Handover hygiene.** When Saiful asks to wrap a session, run [`/handover`](.claude/commands/handover.md) (multi-track, driven by `.claude/session-config.yml`). That's the canonical protocol — it walks preflight, subagent-worktree cleanup, consistency scan, `HANDOVER_R.md` (or the relevant track's handover doc) + `memory/project_ami_trade.md` updates, final verification, and a structured report. The next session reads files at HEAD, so uncommitted edits are invisible and stale text contradicting today's new rule will mislead the next agent — `/handover` produces a clean working tree and a consistency-scanned doc set in a fixed shape so an audit at the end is uniform. **Don't auto-trigger on context budget or "end of chapter" judgements** — Saiful decides when to wrap.
- **Never delete files outside the project folder.** Saiful's exact words: *"unless it is something you physically cannot do, just go ahead and do it. just dont go crazy and delete files outside of your project folders!"*
