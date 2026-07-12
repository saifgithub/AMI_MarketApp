# Reference papers + prior work

> Curated 2026-05-13. Skim before writing the dataset converters in `02_data/recipes/`.

---

## Directly relevant — multi-agent trading + LoRA

### TradingAgents (TauricResearch, Dec 2024)
- Paper: [arxiv 2412.20138](https://huggingface.co/papers/2412.20138)
- Repo: [github.com/TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
- **Why it matters:** The framework AMI Trade is built on. 13-role structure (analysts → researchers → trader → risk → PM) defined here.
- **No fine-tuned weights published.** We're pioneering SFT on this framework.
- **Read for:** original agent prompts (compare against `content/agents/*.md`), debate protocol shape.

### TradingGroup → Qwen3-Trader-8B-PEFT (Aug 2025)
- Paper: [arxiv 2508.17565](https://arxiv.org/abs/2508.17565)
- **Why it matters:** Direct template for what we're trying to do. They LoRA-distilled multi-agent trading trajectories into Qwen3-8B, int8-quantised, 0.53% trainable params. Beat the base Qwen3-8B and GPT-4o-mini on two datasets.
- **Take this as the proof-of-concept.** Our shape is the same but with 13 LoRAs instead of one merged adapter.

### LoRASA — Low-Rank Agent-Specific Adaptation (Feb 2026)
- Paper: [arxiv 2502.05573](https://arxiv.org/abs/2502.05573)
- **Why it matters:** Per-agent LoRA updates on actor networks; merges into backbone at inference (no router overhead). Heterogeneous multi-agent behaviour with minimal resource cost.
- **Read for:** the merge-vs-route trade-off. We plan vLLM hot-swap, but LoRASA's merge-at-inference is a fallback if hot-swap proves rough on Blackwell.

### FinLoRA benchmark (May 2025)
- Paper: [arxiv 2505.19819](https://arxiv.org/abs/2505.19819)
- **Why it matters:** Benchmarks LoRA methods on general + professional financial tasks. Reports avg 36% gain over base across recipes. Reality check for our own eval numbers — if our LoRA gains < 20% on FinanceBench subset, something is wrong with our recipe.

### FinGPT (2023, ongoing)
- Paper: [arxiv 2306.06031](https://arxiv.org/abs/2306.06031)
- Repo + org: [AI4Finance-Foundation/FinGPT](https://github.com/AI4Finance-Foundation/FinGPT), [HF FinGPT org](https://huggingface.co/FinGPT)
- **Why it matters:** Open BloombergGPT alternative. Llama-3.1-8B + LoRA rank 16 = 8.3M trainable params (<0.1% of model). Real-time data curation from 34 sources.
- **Read for:** their LoRA rank / target modules / LR schedule choices. They're the most active open finance-LoRA group on the planet.

---

## Adjacent — useful patterns

### OpenCharacter (Jan 2025)
- Paper: [arxiv 2501.15427](https://arxiv.org/html/2501.15427v1)
- **Why it matters:** Large-scale character synthesis + persona SFT with Llama-3 8B base. Closest published shape to "single base + many personas." Concierge persona-anchoring pattern.

### Pretrained LLM + LoRA as Decision Transformer (Nov 2024)
- Paper: [arxiv 2411.17900](https://arxiv.org/abs/2411.17900)
- **Why it matters:** GPT-2 + LoRA for offline RL trading. Shows LoRA can capture temporal patterns in financial data with parameter efficiency. Pattern reference, not implementation.

### Sentiment-Based Ensemble Trading (Feb 2024)
- Paper: [arxiv 2402.01441](https://arxiv.org/abs/2402.01441)
- **Why it matters:** Dynamic agent switching per market condition vs. fixed ensembles. Architecture hint for how our research_manager could route between aggressive_debator / neutral_debator / conservative_debator dynamically.

### Adaptive Multi-Agent Bitcoin Trading (Nov 2025)
- Paper: [arxiv 2510.08068](https://arxiv.org/abs/2510.08068)
- **Why it matters:** Verbal feedback loop ("Reflect agent") provides daily/weekly critiques WITHOUT fine-tuning. Worth keeping prompt-engineering tracks alive — fine-tuning isn't always the answer.

### Expert Investment Teams (Feb 2026)
- Paper: [arxiv 2602.23330](https://arxiv.org/abs/2602.23330)
- **Why it matters:** Fine-grained task decomposition vs. coarse-grained. Beats GPT-4o-mini. Reinforces the value of role specialisation we're already committed to.

---

## Infra / serving

### vLLM multi-LoRA (Feb 2026)
- Blog: [blog.vllm.ai/2026/02/26/multi-lora.html](https://blog.vllm.ai/2026/02/26/multi-lora.html)
- **Why it matters:** AWS + SageMaker production recipe. Our serving template.

### vLLM Semantic Router (Oct 2025)
- Blog: [blog.vllm.ai/2025/10/27/semantic-router-modular.html](https://blog.vllm.ai/2025/10/27/semantic-router-modular.html)
- **Why it matters:** DualPathUnifiedClassifier for routing between LoRA adapters + base. Could be the right path for "is this question for fundamentals_analyst or news_analyst" arbitration.

### NVIDIA DGX Spark playbooks
- Repo: [github.com/NVIDIA/dgx-spark-playbooks](https://github.com/NVIDIA/dgx-spark-playbooks)
- Build hub: [build.nvidia.com/spark](https://build.nvidia.com/spark)
- **Why it matters:** 40+ recipes including Unsloth fine-tuning, NeMo fine-tuning, vLLM setup, FLUX.1 LoRA, multi-agent chatbots. Updated through May 2026.

---

## Read order if starting cold

1. **TradingAgents paper** — understand the framework first.
2. **TradingGroup paper** — see someone do approximately what we're planning to do.
3. **LLaMA-Factory v0.9.4 README** — pick training recipe.
4. **vLLM multi-LoRA blog** — pick serving recipe.
5. **FinLoRA benchmark paper** — calibrate eval expectations.
6. **NVIDIA DGX Spark playbook for LLaMA-Factory** — execute.

Everything else is supplemental.
