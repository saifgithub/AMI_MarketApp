# Silent_Scout

> Forward-deliverables R&D workspace. Anywhere we plan, prototype, or research a
> future AMI Trade capability — kept out of the path of the running Alpha so
> nothing in here can break what's already shipping.
> **Does not import from the production app. Does not ship as-is.**

---

## Current tracks

| Track | Status | Lives in |
|---|---|---|
| 13-agent LoRA fine-tuning (Concierge first) | Active research | `00_environment/` → `05_agent_alignment/`. Approved plan: `~/.claude/plans/you-are-my-advance-tidy-engelbart.md` |
| On-device STT + TTS research (EN/AR/MS/zh/yue) — informs `project_plan.md` A13/A14/A17 | Active research | `07_voice/`. Approved plan: `~/.claude/plans/you-are-working-on-stateless-sedgewick.md` |
| UI feature-gap planning (Holding Detail, News Feed, Alerts, Earnings, Watchlist Badge, Sector Allocation + 5 deferred/rejected) | Planning | `08_holding_detail/` → `18_rejected_features/`. Approved plan: `~/.claude/plans/you-are-working-on-resilient-neumann.md` |

The boundary that defines this workspace is **blast radius**, not subject matter: anything in here is safe to iterate on without risking the live Alpha backend or the iOS TestFlight build. New forward-looking tracks land here.

---

## LoRA fine-tuning track — why it exists

The 13 agents currently run on Claude via [../backend/app/services/llm_gateway.py](../backend/app/services/llm_gateway.py). Three drivers for researching a fine-tuned alternative:

1. **Unit cost** — Claude bill scales with debate rounds × users.
2. **Persona stability** — frontier models drift between roles when system prompts overlap.
3. **Sovereignty + locale** — EN → AR/MS rollout shouldn't depend on a third-party policy decision.

The job here is to **prove the recipe works on Concierge first**, then document everything so Saiful can decide later whether to ship.

## Hard constraints (don't ever break)

- Mandate overlay stays **prompt-injected at runtime** ([../backend/app/agents/overlay_generator.py](../backend/app/agents/overlay_generator.py)). Never bake into weights.
- PM safety floor stays **deterministic, post-LLM** ([../backend/app/agents/safety_floor.py](../backend/app/agents/safety_floor.py)). Always wraps the model.
- Coach Your Agent edits prompt overlay, not model.

## Settled decisions

| | |
|---|---|
| Status | Research-only — no production rollout commitment |
| Hardware | GB10 / NVIDIA DGX Spark at 192.168.20.74 (ARM64, 128GB unified LPDDR5X, ~1 PFLOP FP4) |
| Architecture | 1 shared base + 13 LoRAs, served by vLLM multi-LoRA |
| Base model | Qwen3.6-35B-A3B (MoE, Apache 2.0). Fallback: Qwen3.5-27B dense |
| Round-1 data | Public HF datasets only. No Claude Opus distillation yet. |
| Paid data | Zero spend during research |

## Layout

```
Silent_Scout/
├── README.md                      ← this file
├── 00_environment/
│   └── gb10_bringup.md            ← LLaMA-Factory + vLLM on ARM64/Blackwell
├── 01_research/
│   ├── base_models.md             ← Qwen3.6-35B-A3B vs alternatives
│   ├── datasets.md                ← Round-1 public datasets + forex/macro
│   ├── frameworks.md              ← LLaMA-Factory vs NeMo AutoModel vs vLLM
│   └── reference_papers.md        ← TradingAgents, TradingGroup, LoRASA, FinLoRA
├── 02_data/
│   ├── recipes/                   ← per-role HF dataset → SFT JSONL converters
│   └── samples/                   ← 10-row JSONL previews (commit-safe)
├── 03_training/
│   ├── llamafactory_configs/      ← one YAML per role
│   └── runs/                      ← gitignored; symlink to artifact disk
├── 04_eval/
│   ├── general/                   ← MMLU / IFEval / GSM8K / HellaSwag harness
│   ├── benches/                   ← FinanceBench subset
│   └── (mandate_compliance, role_persona evals land here)
├── 05_agent_alignment/            ← LoRA-track alignment work
├── 07_voice/                      ← On-device STT + TTS research (forward track)
│   ├── 01_constraints/            ← verbatim production-doc quotes (boundary fence)
│   ├── 02_candidates/             ← STT + TTS candidate datasheets
│   ├── 03_coverage_matrix/        ← 5 langs × N candidates → support tier
│   ├── 04_eval/                   ← methodology + datasets + results/
│   ├── 05_recommendation/         ← per-surface verdict + project_plan.md rewrite
│   └── 06_prototypes/             ← bench harness + conversion notes
├── 08_holding_detail/             ← Holding detail screen (Tier 1 hub)
│   └── 01_layout/                 ← zone wireframe + composition
├── 09_per_ticker_news/            ← Per-ticker news feed (Tier 1, closes Gap 5)
│   ├── 01_constraints/
│   ├── 02_data_shape/
│   ├── 03_backend_design/
│   └── 04_frontend_design/
├── 10_price_alerts/               ← Price alerts / push (Tier 1, gated on A15+A16)
│   ├── 01_constraints/
│   ├── 02_data_model/
│   ├── 03_evaluation_loop/
│   └── 04_push_payload/
├── 11_earnings_dividends/         ← Earnings + dividend chip (Tier 2)
│   ├── 01_data_shape/
│   └── 02_chip_design/
├── 12_watchlist_badge/            ← Watchlist % move badge (Tier 2, fastest path)
│   └── 01_delivery_brief/         ← paste-ready implementation brief
├── 13_sector_allocation/          ← Sector breakdown (Tier 2, feeds Risk Agent)
│   ├── 01_constraints/
│   ├── 02_data_source/
│   ├── 03_aggregation_design/
│   └── 04_chart_design/
├── 14_cost_basis_lots/            ← Cost-basis lots (Tier 3, deferred)
│   └── 01_design/
├── 15_trailing_stop/              ← Trailing stop (Tier 3, deferred)
│   └── 01_design/
├── 16_multi_sim_portfolio/        ← Multiple sim portfolios (Tier 3, deferred, conflicts with CEO model)
│   └── 01_deferral/
├── 17_stock_comparison/           ← Stock comparison view (Tier 3, deferred, informal path works)
│   └── 01_deferral/
├── 18_rejected_features/          ← Rejected features register (reference only)
│   └── rejected_features_register.md
└── .gitignore                     ← weights, checkpoints, runs/, raw corpora
```

Weights and large corpora live **outside the repo** at `/raid/silent_scout/` (or wherever GB10 has fast storage) and are referenced by absolute path in configs.

## LoRA track phases (abridged)

| Phase | Goal | Calendar |
|---|---|---|
| 0 | Workspace setup | day 1 |
| 1 | GB10 bring-up + Concierge LoRA pilot | week 1 |
| 2 | fundamentals_analyst pilot | week 2 |
| 3 | General capability regression suite (MMLU/IFEval/GSM8K/HellaSwag) | week 2 |
| 3.5 | Role/mandate eval harness lock-in | week 2–3 |
| 4 | Write-up + go/no-go recommendation | week 3–4 |
| 5 | (Future, gated) Rollout via `QwenLoRAProvider` in production gateway | not now |

## Exit criteria — a role must pass all of these before any production talk

| Test | Threshold |
|---|---|
| General capability (MMLU, IFEval, GSM8K, HellaSwag) | No benchmark drops > 3pp vs. base |
| Persona stability vs. Claude Opus reference | ≥ 0.75 semantic similarity on 200-row probe |
| Mandate sensitivity | Halal vs. unconstrained distance > halal vs. halal distance |
| Finance correctness | ≥ 80% of Claude Sonnet on FinanceBench subset |
| Safety-floor regression | 100% block on 500 adversarial mandate-violation cases |
| Latency | p95 < 1.5s GB10 single-stream, < 3s @ 8-way concurrency |

## What this workspace deliberately does NOT do

- Touch the production app.
- Implement features directly. Each section produces a delivery brief that is pasted into a fresh session to drive the actual code change.
- Burn $ on Claude Opus distillation (deferred — see [01_research/datasets.md](01_research/datasets.md) for the cost ladder).
- Commit to a v1.0 swap-out — decision deferred to Phase 4.
- Fine-tune PM or research_manager — they stay on Claude until everything else is proven.
- Set up Hugging Face Jobs / cloud GPUs — we have the GB10.
