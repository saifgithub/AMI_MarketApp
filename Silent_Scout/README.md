# Silent_Scout

> Research-only workspace for fine-tuning the 13 AMI Trade agents (12 trading + Concierge).
> **Does not import from the production app. Does not ship.** Approved plan lives at `~/.claude/plans/you-are-my-advance-tidy-engelbart.md`.

---

## Why this exists

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
└── .gitignore                     ← weights, checkpoints, runs/, raw corpora
```

Weights and large corpora live **outside the repo** at `/raid/silent_scout/` (or wherever GB10 has fast storage) and are referenced by absolute path in configs.

## Phases (abridged)

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
- Burn $ on Claude Opus distillation (deferred — see [01_research/datasets.md](01_research/datasets.md) for the cost ladder).
- Commit to a v1.0 swap-out — decision deferred to Phase 4.
- Fine-tune PM or research_manager — they stay on Claude until everything else is proven.
- Set up Hugging Face Jobs / cloud GPUs — we have the GB10.
