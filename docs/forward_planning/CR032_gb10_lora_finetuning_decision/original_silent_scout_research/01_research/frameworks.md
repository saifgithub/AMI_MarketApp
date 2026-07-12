# Frameworks — research notes

> Verified 2026-05-13. ARM64 + Blackwell support is the gating constraint.

---

## Stack pick (one line)

**Train with LLaMA-Factory + (parallel pilot) NeMo AutoModel. Serve with vLLM `--enable-lora`. Skip Unsloth for round 1. NIM only if research graduates to a real-user pilot.**

---

## Layer-by-layer

### Fine-tuning framework

| Tool | Status on GB10 | Verdict |
|---|---|---|
| **LLaMA-Factory v0.9.4+** | GREEN — NVIDIA published an official DGX Spark recipe (Feb 2026). `pip install` works. SFT + DPO + GRPO + ORPO + KTO + PPO all supported. Multi-LoRA training compat proven. Active dev (last release Dec 2025). | **Primary.** |
| **NeMo AutoModel** | GREEN — native ARM64 / Blackwell. Official Spark guide (Mar 2026). TRL-compatible API; skips legacy NeMo's C++ build pain. | **Parallel pilot for one role** (compare against LLaMA-Factory on the same role to see if NVIDIA's path is materially faster/easier). |
| Axolotl | Untested on GB10 in this scout. Mature, config-driven, best multimodal story. | Hold. Revisit if LLaMA-Factory's data preprocessing limits us. |
| TorchTune (Meta) | PyTorch-native; weaker model coverage than LLaMA-Factory. | Pass. |
| SWIFT (ModelScope) | Supports 600+ models, MoE-LoRA. AAAI 2025. | Hold. Worth checking if Qwen3.6-A3B MoE-LoRA hits issues in LLaMA-Factory. |
| **Unsloth** | YELLOW — ARM64 wheels fragile; needs community Docker. Open issue [#1679](https://github.com/unslothai/unsloth/issues/1679). | **Skip round 1.** Revisit only if throughput is genuinely blocking. |
| TRL (HF) | Drop-down library underneath LLaMA-Factory. | Use only when LLaMA-Factory's abstraction is too thin (e.g. custom DPO loss). |
| PEFT (HF) | LoRA / QLoRA / PiSSA. Pure Python — ARM-clean. | Implicit dep — already pulled in by LLaMA-Factory. |

### Serving

| Tool | Status | Verdict |
|---|---|---|
| **vLLM `--enable-lora`** | YELLOW — ARM64 wheels not pre-compiled; build from source (~30–60 min). FP4 perf still maturing on Blackwell. Multi-LoRA serving + hot-swap proven. | **Primary serving path.** Per-request adapter selection via `model` param. |
| LoRAX (Predibase) | Optimised for 100s–1000s of adapters; built on HF TGI. | Hold. Overkill at 13 adapters. Revisit only if we ever expand to per-user LoRAs. |
| NVIDIA NIM (`-dgx-spark` variant) | GREEN — Docker image with multi-LoRA serving baked in. | **Only if research graduates to a real-user pilot.** Production-grade, but adds container ops we don't need yet. |
| HF Text-Generation-Inference (TGI) | Mature alt. | Pass — vLLM is preferred for multi-LoRA. |
| SGLang | Strong for structured output. | Hold. Revisit if PM (verdict JSON) or trader (trade-proposal JSON) needs strict structured decoding. |

### Acceleration / quantisation

| Tool | Status on ARM64 / Blackwell | Verdict |
|---|---|---|
| `bitsandbytes` (8-bit / 4-bit) | Uncertain ARM64 wheels. Often missing. | Use bfloat16 LoRA path instead. |
| NVIDIA TransformerEngine (FP8) | Native on Blackwell. | Worth trying once base path works. |
| `flash-attn` | sm_120/sm_121 landed late; pin a release that names Blackwell. | Required for sane training throughput on 35B. |
| FP4 / NVFP4 | Native on GB10 silicon. Inference-focused. | Defer to serve-side quantisation; not for training-time. |

### Synthetic data

| Tool | Status | Verdict |
|---|---|---|
| Distilabel (Argilla) v1.5+ | Active. Pipeline-based generation, Argilla annotation integration. | **Pick when distillation is unlocked.** Not in research round 1. |
| DataDreamer | ACL 2024; standardised distillation API. | Alt. Hold. |
| Bespoke Curator | Newer, focused on curation. | Hold. |
| HF AutoTrain | Managed alternative. DGX Cloud deprecated April 2025; local-Spaces mode only. | Pass. We have GB10. |

### Eval

| Tool | Status | Verdict |
|---|---|---|
| `lm-evaluation-harness` (EleutherAI) | Pure Python; CLI refactored Dec 2025. | **Primary general-capability harness** (MMLU, IFEval, GSM8K, HellaSwag — see `04_eval/general/`). |
| FinanceBench | 10k+ Q&A across 40 companies. Has baseline scores for GPT-5 + Claude Opus 4.1. | **Primary finance-correctness harness.** Use a 50–100 question subset as gating signal. |
| FinBen / FLARE | Aggregator benchmarks. | Hold. Revisit when we need broader finance eval. |
| Custom `mandate_compliance_eval.py` | Wraps `backend/app/agents/safety_floor.check_mandate_compliance`. | **Critical — block-rate gate for PM-adjacent roles.** Lives in `04_eval/`. |

---

## Versioning discipline

- Pin **every** install in `requirements.txt` per phase. ARM64 + Blackwell stack moves fast; floating versions = pain.
- Snapshot the working `pip freeze` into `00_environment/frozen_<date>.txt` after each successful phase.
- When upstream releases break us, document the broken version + the rollback in `00_environment/gb10_bringup.md` known traps.

---

## When to drop down to TRL

LLaMA-Factory wraps TRL. If we need a training recipe LLaMA-Factory doesn't expose (custom reward shaping, novel preference loss, non-standard GRPO variant), bypass via:

```python
from trl import SFTTrainer, DPOTrainer, GRPOTrainer
```

Don't do this in round 1. The whole point of LLaMA-Factory is "no custom training code."

---

## Production serving — GCP path (when we ship, not now)

LoRA adapters are portable (~100MB safetensors files); the base Qwen3.6-35B-A3B weights are portable (~70GB, copy once). Nothing about our GB10 training pipeline locks us to the GB10 for serving. This section is the **post-research reference** for "where this runs when AMI Trade actually ships."

### Train → publish → serve pipeline

1. **Train on GB10** — produces base + N LoRA adapters at `/raid/silent_scout/adapters/<role>/`.
2. **Publish artifacts** — upload base weights to GCS (or private HF repo) once; upload each adapter to the same place, re-uploadable after every retrain.
3. **Build a vLLM serving container** — Docker image with vLLM + `--enable-lora --max-loras=13`, loading adapters by name on startup.
4. **Deploy on GCP** — same container, hosting options below.
5. **Switch the gateway** — add a `QwenLoRAProvider` in [../backend/app/services/llm_gateway.py](../../backend/app/services/llm_gateway.py), wire into the existing `TIER_TO_MODEL` routing. Concierge first; trading agents migrate later as their LoRAs pass eval.

### GCP hosting options

| Option | GPU | Sweet spot | $/hr (on-demand, May 2026 ballpark) | Verdict |
|---|---|---|---|---|
| **Cloud Run with GPU (L4)** | L4 24GB | Spiky traffic, scales to zero | ~$0.65/hr while serving | **Best fit for AMI Trade alpha.** Matches existing backend deployment. Requires FP4/FP8 quant to fit 35B-A3B on a single L4. |
| **Cloud Run with GPU (L4 ×2 or L40)** | 48GB | Same shape, bigger headroom | ~$1.30/hr | Comfortable for FP8 Qwen3.6 + KV cache. Scale-to-zero retained. |
| **Vertex AI Endpoints (A100 80GB)** | A100 80GB | Stable production traffic | ~$3.67/hr | bf16 fits cleanly. Managed but expensive at 24/7. |
| **GKE with GPU node pool** | A100 / H100 | High volume | varies | Max control, max ops overhead. Skip for solo founder. |
| **Compute Engine VM (A100/H100)** | A100/H100 | Steady predictable load | A100 80GB ~$2.93/hr committed-use | Cheapest dedicated path if you can keep the GPU >50% busy. |

### Recommendation for AMI Trade alpha → v1.0

**Cloud Run with GPU, FP8-quantized Qwen3.6-35B-A3B, scale-to-zero.**

Why this and not the others:
- **Scale to zero matches the traffic shape.** AMI Trade users aren't 24/7 — they open the app, chat, leave. Most of the day there's nothing in flight. Vertex/Compute Engine bills for idle.
- **Same paradigm as the existing backend.** Cloud Run is already where the FastAPI app runs. Adding a GPU container is the smallest mental shift.
- **Cost model is sane.** For ~1k alpha users at modest usage: roughly $200–500/mo for inference vs. $2–5k/mo on Vertex 24/7 vs. $10k+/mo on Claude at the same volume.
- **Quantization is essentially free on L4/L40.** FP4/FP8 inference on Ada/Hopper — Qwen3.6-35B-A3B fits in ~17–35 GB without meaningful quality loss for our roles.

**Trap to avoid:** don't reach for Vertex AI just because Google's docs steer you there. Vertex fits ML teams with consistent traffic; it's overkill for a solo founder with bursty alpha-stage demand.

### Pragmatic hybrid (the actually-cheap option)

- **Pre-launch:** GB10 only. Free. On the LAN.
- **At launch:** GB10 keeps serving internal evals + scheduled batch jobs (mining Decision Journal for next round's DPO data). GCP Cloud Run with GPU runs only when user traffic arrives. Adapter weights live in GCS, pulled by both deployments. Same Docker image runs on either.
- **Failover story:** if the GB10 goes down (single box, no redundancy), customer-facing traffic doesn't notice — it never hit the GB10. If GCP has an outage, internal evals/batch keep running on the GB10. Independence by design.

### Artifact layout (when shipping)

```
gs://ami-trade-models/
├── qwen3.6-35b-a3b/
│   ├── base/                        ← bf16 safetensors shards
│   └── fp8/                         ← quantized variant for Cloud Run L4/L40
├── adapters/
│   ├── concierge/v1/                ← versioned LoRA per role
│   ├── fundamentals_analyst/v1/
│   └── ...
└── eval/                            ← published eval reports per release
```

Versioning rule: every adapter promotion to production gets a `vN` and a corresponding eval report. Rollback = swap the env var pointing at the active version. No model surgery on a live container.

### Switchover checklist (Phase 5 readiness — not now)

- [ ] Adapters pass all exit criteria in [../README.md §exit-criteria](../README.md).
- [ ] Docker image with vLLM + adapters builds in CI on x86_64 (Cloud Run target, not ARM64).
- [ ] Cold-start latency benchmarked — Cloud Run GPU cold-start can be 30–60s; gate behind a warm-pool config or fall back to Claude for cold sessions.
- [ ] Cost dashboard in GCP with budget alert at $X/month threshold (the actual $X depends on alpha sign-up curve).
- [ ] `QwenLoRAProvider` in `llm_gateway.py` with **automatic fallback to Claude** on any error (5xx, timeout, cold-start miss). The model is an optimization, not a single point of failure.
- [ ] Cloud Run service is in the same region as the FastAPI app (avoid cross-region latency tax).
