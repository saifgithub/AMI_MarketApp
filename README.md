# AMI Trade

> The AI-first, mandate-driven trading-education app — built on a team of 12 AI agents.

**AMI Trade** is a product of **AMI (Agentic Market Intel)**. It is a mobile-first, simulation-only trading-education app where each user is the CEO of their own 12-agent analyst team. The agents are powered by the [TradingAgents](https://github.com/TauricResearch/TradingAgents) multi-agent LLM framework, personalised to each user's financial mandate (goals, horizon, risk appetite, halal compliance, constraints).

This repository will hold the Flutter mobile app, the Python backend, content, and infrastructure. The full product spec lives in [`docs/`](docs/).

---

## Status

**Pre-build.** All product, design, monetization, and technical decisions are locked. Ready to begin month-1 setup. See [`docs/initial_specs/10_delivery/pre_alpha_checklist.md`](docs/initial_specs/10_delivery/pre_alpha_checklist.md) for prerequisites.

**Target: Stealth Alpha** in 12 weeks. iOS, English, free for Founders cohort. See [`docs/initial_specs/10_delivery/stealth_alpha_scope.md`](docs/initial_specs/10_delivery/stealth_alpha_scope.md).

---

## How to navigate this spec

The PRD is structured so that build agents (or human contributors) can load only the docs relevant to their current task.

| Folder | Load when working on… |
|---|---|
| [`docs/initial_specs/00_overview/`](docs/initial_specs/00_overview/) | Vision, positioning, brand voice |
| [`docs/initial_specs/01_product/`](docs/initial_specs/01_product/) | Product loop, feature inventory, competitor comparison |
| [`docs/initial_specs/02_agents/`](docs/initial_specs/02_agents/) | The 12 agents — overlays, Convene, Coach, Concierge, safety floor |
| [`docs/initial_specs/03_onboarding/`](docs/initial_specs/03_onboarding/) | Anonymous-first onboarding, mandate creation, lifecycle |
| [`docs/initial_specs/04_education/`](docs/initial_specs/04_education/) | Lessons, Agent Academy, daily challenges, dual-gating |
| [`docs/initial_specs/05_design/`](docs/initial_specs/05_design/) | AMI hex design system applied to Flutter, IA, screens |
| [`docs/initial_specs/06_monetization/`](docs/initial_specs/06_monetization/) | Tiers, pricing, credits, ads, offers, trial mechanics |
| [`docs/initial_specs/07_localization/`](docs/initial_specs/07_localization/) | i18n architecture, AR/MS plan |
| [`docs/initial_specs/08_tech/`](docs/initial_specs/08_tech/) | Stack, architecture, auth, hosting, data model, APIs |
| [`docs/initial_specs/09_compliance/`](docs/initial_specs/09_compliance/) | Disclaimers, privacy, store rules, ad policy |
| [`docs/initial_specs/10_delivery/`](docs/initial_specs/10_delivery/) | Alpha scope, timeline, roadmap, you-do-I-do split, risks |
| [`docs/initial_specs/11_decisions/`](docs/initial_specs/11_decisions/) | Decision log, open questions |

Every folder has a `README.md` index listing its files.

---

## Key facts at a glance

| | |
|---|---|
| **Parent brand** | AMI (Agentic Market Intel) |
| **Product name** | AMI Trade |
| **Tagline** | *"Your team of analysts. Your call."* |
| **Domain** | `agenticmarketintel.ai` (sub-path or subdomain TBD) |
| **Audience** | Beginners-to-prosumers, mobile-first, EN/AR/MS markets |
| **Posture** | Simulation-only, advisory-only forever — no brokerage integration |
| **Markets at MVP** | US equities |
| **Languages at alpha** | EN; AR + MS at v1.0 |
| **Platforms at alpha** | iOS + Android-GMS (per [D-057](docs/initial_specs/11_decisions/decision_log.md#d-057--android-gms-pulled-forward-from-v10-to-alpha)); AppGallery at v1.1 |
| **Monetization** | Floor Pass (free, ads) / Trader ($14.99/mo) / Floor Manager ($34.99/mo) + credits |
| **Tech stack** | Flutter (frontend), Python + FastAPI (backend), Supabase, Google Cloud Run, OpenRouter + direct LLM keys |
| **Design language** | AMI "Hex-Reinforced Precision" (hexagonal tessellation, dark slate, Inter + JetBrains Mono) |

---

## The 12 agents

| # | Agent | Family |
|---|---|---|
| 1 | Fundamentals Analyst | Analyst |
| 2 | Market Analyst | Analyst |
| 3 | News Analyst | Analyst |
| 4 | Social Media Analyst | Analyst |
| 5 | Bull Researcher | Researcher |
| 6 | Bear Researcher | Researcher |
| 7 | Research Manager | Manager |
| 8 | Trader | Execution |
| 9 | Aggressive Debator | Risk |
| 10 | Conservative Debator | Risk |
| 11 | Neutral Debator | Risk |
| 12 | Portfolio Manager | Manager / Gatekeeper |

Plus the **AI Concierge** — the 13th "agent" — who is the user's personal assistant: lesson router, journal summariser, briefing scheduler, and product help.

Full agent specs in [`docs/initial_specs/02_agents/`](docs/initial_specs/02_agents/).

---

## License & confidentiality

Pre-launch private build. Do not distribute spec or code outside the build team without consent of the founder.
