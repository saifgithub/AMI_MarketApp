# Base Models — research notes

> Verified 2026-05-12 / 2026-05-13. URLs are live as of writing. Re-verify before download.

---

## Recommendation

**Primary:** [Qwen/Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)
**Fallback:** [Qwen/Qwen3.5-27B](https://huggingface.co/Qwen/Qwen3.5-27B)

Both Apache 2.0. Both fit on GB10's 128GB unified memory. Both ship with multilingual coverage (201 languages) — important for the AR + MS v1.0 roadmap.

---

## Qwen3 family (live on HF today)

| Model | Params | Active/token | Ctx | License | Released | Notes |
|---|---|---|---|---|---|---|
| **Qwen3.6-35B-A3B** ⭐ | 35B total | 3B (MoE) | 262K (1M ext.) | Apache 2.0 | Apr 2026 | Primary. MoE → LoRA touches small active set → fast on GB10. Thinking mode preserved for later RL. |
| Qwen3.6-27B | 27B | 27B (dense) | 262K (1M ext.) | Apache 2.0 | Apr 2026 | Dense alt if MoE-LoRA tooling is rough. Higher per-token compute than 35B-A3B. |
| **Qwen3.5-27B** | 27B | 27B (dense) | 262K | Apache 2.0 | Feb 2026 | Fallback. Three months of community shake-out. MMLU-Pro 86.1, IFEval 95.0. |

**Why MoE matters on a single GB10:** Qwen3.6-35B-A3B activates only 3B params per token. Backward pass on a LoRA adapter touches the active experts only. Effectively you're training a 3B-class model on per-step compute, while serving with a 35B-class model's representational capacity. This is the single biggest reason it's first pick on this hardware.

---

## Architectures considered and passed on

| Path | Verdict | Why |
|---|---|---|
| Qwen3-7B-class | Not now | We share base across 13 LoRAs already. Going smaller buys cost we don't pay on GB10. |
| Single multi-task model, role-token routed | Fallback only | Simpler infra; personas blur; adding a 14th role re-trains everything. |
| Prompt + RAG only | Not the goal | Already what we do with Claude. Silent_Scout exists to test if we can do better. |

---

## Other open-weight families evaluated

| Model | Verdict | Note |
|---|---|---|
| GLM-4.5 / 4.6 (355B / 32B active) | Pass | Overkill; CN-leaning training mix. |
| DeepSeek-V3 (671B) | Pass | Too large for single GB10; mono-language. |
| DeepSeek-R1-Distill-Qwen-14B/32B | Hold | Reasoning-strong; revisit if Qwen3.6 base under-reasons on bear_researcher / conservative_debator. |
| Llama 4 Scout (17B active / 109B MoE, Apr 2026) | Pass | English-biased; no AR/MS edge. |
| Gemma 4 (31B, Apr 2026) | Pass | Gemma license fine print > Apache 2.0 for our use. |
| Mixtral-8x7B / Magistral | Pass | Slower-evolving than Qwen3.x; weaker reasoning at the same params. |
| Phi-4-mini / reasoning-vision | Pass | Compact but ~50 languages; no AR/MS coverage. |
| FinMA-7B-full ([TheFinAI](https://huggingface.co/TheFinAI/finma-7b-full)) | Hold | Pre-tuned on PIXIU. Possible warm-start for news/sentiment analysts in a later round. |

---

## Decision rule for Phase 1

1. Start on **Qwen3.6-35B-A3B**.
2. If at any point in the first week:
   - LLaMA-Factory + LoRA path on the MoE is unstable (training crashes, NaN losses, kernel errors on Blackwell), OR
   - The `--enable-lora` adapter routing in vLLM doesn't work for MoE models,
3. Drop to **Qwen3.5-27B** dense and continue without further investigation.
4. Document the swap in `Silent_Scout/03_training/runs/_log.md`.

The point is to **fail fast** on the bleeding-edge stack and still hit the Concierge pilot in week 1.

---

## Links to verify weekly

- [Qwen3.6 collection](https://huggingface.co/collections/Qwen/qwen36)
- [Qwen3.5 collection](https://huggingface.co/collections/Qwen/qwen35)
- [DeepSeek-R1 distills](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B)
- [NVIDIA DGX Spark playbooks](https://github.com/NVIDIA/dgx-spark-playbooks) — has the Qwen-on-Spark recipes
