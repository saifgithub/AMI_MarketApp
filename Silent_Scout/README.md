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
| Android dev groundwork (KSA test device, future build prep) | Active | `06_android/` |
| On-device STT + TTS research (EN/AR/MS/zh/yue) — informs `project_plan.md` A13/A14/A17 | Active research | `07_voice/`. Approved plan: `~/.claude/plans/you-are-working-on-stateless-sedgewick.md` |

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
├── 06_android/                    ← Android dev groundwork (forward track)
│   └── test_device_selection.md   ← KSA Android test-device procurement
├── 07_voice/                      ← On-device STT + TTS research (forward track)
│   ├── 01_constraints/            ← verbatim production-doc quotes (boundary fence)
│   ├── 02_candidates/             ← STT + TTS candidate datasheets
│   ├── 03_coverage_matrix/        ← 5 langs × N candidates → support tier
│   ├── 04_eval/                   ← methodology + datasets + results/
│   ├── 05_recommendation/         ← per-surface verdict + project_plan.md rewrite
│   └── 06_prototypes/             ← bench harness + conversion notes
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
- Burn $ on Claude Opus distillation (deferred — see [01_research/datasets.md](01_research/datasets.md) for the cost ladder).
- Commit to a v1.0 swap-out — decision deferred to Phase 4.
- Fine-tune PM or research_manager — they stay on Claude until everything else is proven.
- Set up Hugging Face Jobs / cloud GPUs — we have the GB10.
