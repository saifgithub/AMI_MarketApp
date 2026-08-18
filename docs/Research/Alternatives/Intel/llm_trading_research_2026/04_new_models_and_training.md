# New open-weight finance/trading LLMs, training material, and benchmarks — Jan–Aug 2026

Scoped to what's actually deployable on AMI's own hardware: self-hosted vLLM on an NVIDIA GB10/DGX Spark,
128GB unified LPDDR5X memory, currently running `Qwen3.6-35B-A3B-NVFP4` at 262K context. Also evaluated
last week: `InternScience/Agents-A1` (35B, general-purpose agentic model, found to have **zero** financial-
benchmark presence anywhere — see chat history / this session's earlier turns; not re-litigated here).
Every item below was opened directly (arXiv, HF model/dataset card via API + WebFetch, or blog) — not taken
from a search snippet alone.

---

## 1. New open-weight finance/trading models

### Fastino-Nemotron-3.5-Lightning-Finance — the standout finding

- https://huggingface.co/fastino/Fastino-Nemotron-3.5-Lightning-Finance ·
  blog: https://fastino.ai/blog/fastino-nemotron-3-5-lightning-finance-and-healthcare/
- **Base: `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B`** — the same model AMI already tested (dual-model
  run against Qwen3.6, see [`../quant_finance/README.md`](../quant_finance/README.md) §5). 30B MoE, 3B
  active. Uploaded 2026-08-06, blogged 2026-08-11/14. Apache-2.0.
- Training: LoRA rank 32, lr 1e-4, 2 epochs, 13,698 deduplicated examples — financial-document
  calculation, hybrid text+table QA, business-finance reasoning, numerical span extraction from SEC
  disclosures, financial entity extraction, source-grounded research trajectories. **Data provenance not
  disclosed** — the card says the training agent "sourced and curated its own data"; synthetic vs. real is
  unstated.
- **Benchmarked against general-purpose frontier models, not just finance baselines** — this is the
  comparison that mattered for last week's Agents-A1 evaluation and was missing there entirely. On FinQA
  execution accuracy this 3B-active model scores **59.23%** vs. DeepSeek-R1 671B at 65.1%, Llama 3.3 70B at
  68.2%, Kimi K2.6 at 76.0% — large gains over its own untrained base (15.86%→59.23%) but still trails
  frontier-scale generalists, **honestly reported, not oversold**. Also: TAT-QA F1 19.01→56.63, SEC-Num
  79.74%→87.60%, FinEntity macro-F1 60.16→79.54, BizFinBench 49.65%→57.46%, ConvFinQA transfer
  15.00%→57.33%.
- **Confidence: high** — verified via HF API card and blog directly.

**Methodology behind it — Pioneer Agent** (arXiv 2604.09791, 2026-04-10, Dhruv Atreja et al.): an
autonomous agent that curates its own training data and iteratively trains small LMs, validated across 8
general benchmarks plus production tasks (intent classification 84.9%→99.3%, entity F1 0.345→0.810). The
pipeline that produced the Fastino finance/healthcare releases; the paper itself isn't finance-domain.

### Kautilyaa-9B-Finance (thinkingdbx, 2026)

Mixtral-style sparse MoE, 9B total/2.6B active, Apache-2.0. Pretrained on SEC EDGAR + FNSPID, instruction-
tuned on ~4,200 curated+synthetic examples. Notably weak: 4,096-token context, one-instrument-per-context
constraint, explicitly cannot do arithmetic reliably. Only internal evals (0 hallucinated numerics/150
cases, 100% out-of-context refusal, 67% citation recall) — **no comparison against any general-purpose
model**. Hobbyist scale, low relevance to AMI's use case. **Confidence: medium** (card read directly, thin
documentation).

### Not new / not found

- **Fin-R1 and Fino1** — both **2025** releases (arXiv 2503.16252, 2502.08127), predate the Jan-2026
  window. Fin-R1 got a 2026 revision but isn't a new model. Newer benchmarks (FINESSE-Bench, see §3) still
  use them as finance-specialist baselines.
- **FinGPT / FinMA / PIXIU** — no 2026 release found. AI4Finance-Foundation's FinGPT GitHub shows no new
  2026 activity. **Could not verify** any 2026 successor exists — treat as dormant.

## 2. New instruction-tuning / RL training datasets

**coslinedev/financial-rlvr-10k-enterprise** (HF, uploaded 2026-08-17) —
https://huggingface.co/datasets/coslinedev/financial-rlvr-10k-enterprise. 10,000 rows, MIT license,
**fully synthetic**. Covers DCF valuation (Gordon Growth, discount-rate traps), Black-Scholes European call
pricing (expiry traps), WACC (zero equity+debt traps) — ~20% deliberate "adversarial trap" cases testing
whether a model detects invalid inputs vs. confidently hallucinating an answer. Built explicitly for
**RLVR** (RL with Verifiable Rewards): PPO/GRPO/DPO-compatible, 4-stage reward engine (0.20 syntax AST
check, 0.25 logic/library check, 0.30 sandboxed execution, 0.25 numerical match at ±1e-4). No training-run
results published yet. **Confidence: high** — dataset card read directly.

Smaller/lower-confidence finds, not deep-verified: `StarsMakeGalaxy/bfsi-transaction-triage-curated-600`
and `.../prometheus-bfsi-tier1-triage` (banking fraud-triage SFT sets, Apache-2.0, n<1K).

Nothing else in the Jan–Aug 2026 window stood out as a serious new SFT/RL financial-reasoning corpus.
Golden Touchstone / FinCoT / Fin-R1-Data are all 2025.

## 3. New financial-domain benchmarks/leaderboards

| Benchmark | Source | Date | Size | Top result | AMI's candidate models present? |
|---|---|---|---|---|---|
| FinTradeBench | arXiv 2603.19225 | 2026-03-19 (rev. 06-10) | 1,400 Qs, NASDAQ-100 | DeepSeek-R1 37.7% (RAG), top of 14 models (Gemini 2.5, GPT-5-mini, R1-Distill, Llama 3.3, Qwen2.5-32B, Phi-4, Mistral-7B, LFM-2.5) | **No** |
| FINESSE-Bench | arXiv 2605.15482 | 2026-05-14 (rev. 05-21) | 3,993 Qs, 8 sub-benchmarks, 56+ models | Qwen3.5-Plus-02-15 (0.8776) on exam tasks; Kimi K2.5 leads trading/technical sub-bench; finds a "transfer gap" — strong general finance-benchmark performers underperform on applied/exam tasks | **No** (Qwen3.6, Nemotron, Agents-A1 all absent) |
| BizFinBench.v2 | arXiv 2601.06401 | 2026-01-10 (rev. 07-13) | 28,860 Qs, bilingual CN/US equities | GPT-5 61.5% overall; DeepSeek-R1 best "investment efficacy" among commercial models | **No** |
| Financial Touchstone v1.2 | arXiv 2608.08634 | 2026-08-09 | 2,967 Qs / 495 international annual reports | Claude Opus 4.6 88.4% acc (top); Gemini 2.5 Pro lowest hallucination (0.08%); **open-weight Kimi K2.6 ranked 3rd**; non-reasoning GLM 5 & Mistral 3 placed 4th/5th — reasoning architecture isn't required here | **No** |

Financial Touchstone is the most directly useful of these four: an apples-to-apples proprietary-vs-open
comparison, showing open-weight models (Kimi K2.6, GLM 5) are already competitive on long-document
financial comprehension — a real existence proof that "open-weight" isn't itself the ceiling.

**HF-native leaderboards**: `TheFinAI/Open-FinLLM-Leaderboard` (tags confirmed via Spaces API:
`leaderboard, submission:manual, test:public, judge:function, eval:generation, domain:financial`), mirrored
at `finosfoundation/Open-Financial-LLM-Leaderboard` (138 likes). Both are Docker Spaces, code last touched
2026-04-16/22. **Could not verify current live rankings** — the page is JS-rendered and WebFetch only
returned a loading state. Flagging honestly rather than guessing contents; worth checking directly in a
browser if this matters.

Golden Touchstone / Touchstone-GPT (EMNLP 2025) is pre-window prior art, still the standard bilingual
reference other 2026 papers cite against.

## 4. AMI's candidate models against these new benchmarks

- **InternScience/Agents-A1**: re-checked its own model card directly — its benchmark suite (BrowseComp,
  XBench-DS-2510, Seal-0, GAIA, SciCode, MLE-Lite, HLE(-tools), HiPhO, FrontierScience-{Olympiad,Research},
  IFBench, LongBench-v2, IFEval, τ²-Bench, VitaBench, MatTools, MolBench-bind) has **zero
  financial/business/economics entries** — unchanged from last week's finding — and it doesn't appear in
  any of the four finance benchmarks in §3 either.
- **Qwen3.6-35B-A3B**: no dedicated financial benchmark found anywhere (checked artificialanalysis.ai,
  buildfastwithai, labellerr — general reasoning/code/math only: 73.4% SWE-bench, 86.0 GPQA-Diamond, 92.7
  AIME 2026, 85.2 MMLU-Pro). Absent from all four finance benchmarks in §3.
- **Nemotron-3.5-Lightning-30B-A3B**: the base itself is untested on finance benchmarks directly, but is
  the single most relevant hit of this whole search — **two concrete, actionable developments since AMI
  last tested it:**
  1. Fastino's finance LoRA derivative (§1) gives it real, honestly-reported numbers on FinQA/TAT-QA/
     SEC-Num/FinEntity/BizFinBench/ConvFinQA.
  2. NVIDIA shipped an **official NVFP4 quantization of the full base model**:
     `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` — built via NVIDIA Model Optimizer per arXiv
     2607.05147, `NemotronHForCausalLM` architecture, 52 hidden layers, matching the BF16 base.

> **Correction, 2026-08-18:** this section originally named
> `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4-DSpark` (note the `-DSpark` suffix) as "the official
> NVFP4 quant... named and tuned for AMI's exact hardware." **That was wrong**, caught during a follow-up
> hands-on pilot attempt: the `-DSpark` repo is not a deployable quantized model at all. Its own config
> shows `architectures: ["Qwen3DSparkModel"]`, 6 hidden layers, and its actual `model.safetensors` file is
> 1.35GB (verified via the file's own size header, not just repo metadata) — a small speculative-decoding
> **draft/assist** checkpoint meant to pair alongside the real model for faster serving, not a replacement
> for it. Its own README states this plainly: *"intended for DSpark-assisted serving... rather than as a
> standalone target model checkpoint."* The artifact actually meant here is the sibling repo without
> `-DSpark` in the name — corrected above. Full writeup, including why this still doesn't close the
> Agents-A1 gap as cleanly as first claimed (nobody has quantized the *finance-tuned* merged checkpoint
> yet — that's real open work, not a solved problem): [`05_nemotron_finance_pilot_brief.md`](05_nemotron_finance_pilot_brief.md).

**Bottom line for §4**: no new finance-specific model has emerged that's a *better* self-hostable candidate
than what's already in AMI's research trail. Nemotron-3.5-Lightning now has a finance-tuned LoRA (merged,
BF16 only) with honest frontier-model comparisons, and NVIDIA has an official NVFP4 quant of the base —
but nobody has combined the two yet. That combination, not either piece alone, is the actual pilot worth
running — see [05](05_nemotron_finance_pilot_brief.md) for the scoped brief.

## 5. Training-methodology research (new, even without a shipped model)

- **GIFT — LLM-Guided State-Reward Interface for Financial RL** (arXiv 2606.08450, 2026-06-07, 13
  authors). Uses an LLM *not* to trade directly but to design/refine the PPO training interface:
  factor-guided state enhancement, risk-rule-guided reward shaping, diagnostic-guided refinement from PPO
  rollout diagnostics — then **freezes the interface before evaluation** (no test-time LLM calls, avoiding
  drift/reward-hacking at inference). Improved out-of-sample risk-adjusted portfolio performance across
  market regimes in rolling-window backtests. Code/weights availability not confirmed this session.
- **GRPO for Financial Advice Generation: Outperforming Commercial LLMs under CATE Evaluation** (arXiv
  2608.11787, 2026-08-12, CC-BY-4.0). GRPO-tunes an open-weight LLM using an LLM-as-judge multi-dimensional
  rubric + safety constraints, validated with a **doubly-robust causal (CATE) estimator** rather than
  trusting the judge score. Result: ~2x estimated gross-profit lift vs. the strongest commercial baseline
  ($0.0228 vs $0.0104) with better downside protection. **Methodologically notable**: the untrained base
  model ranked *last* under the LLM-judge but *second* under the causal audit — a concrete warning about
  judge-reward gaming in financial RL, directly relevant to AMI's PM-mandate/compliance-check design
  philosophy (the "prompt instructions are not controls" principle already in `CLAUDE.md`).
- **financial-rlvr-10k-enterprise** (§2) is itself a methodology artifact worth flagging separately: a
  sandboxed-execution verifiable-reward environment for financial GRPO/RLVR, as opposed to LLM-as-judge —
  a different, arguably more robust reward paradigm than the GRPO-advice paper above.

Pre-window context only, not new: FinRL Contests (2504.02281), HARLF (2507.18560), "Financial News-Driven
LLM RL for Portfolio Management" (2411.11059) — all 2024/2025.

## What turned up nothing verifiable

- No confirmed 2026 FinGPT/FinMA/PIXIU successor release.
- Live rankings on the two HF finance leaderboards (TheFinAI / finosfoundation) — space exists and is
  tagged correctly, current standings could not be pulled (JS-rendered UI).
- Fastino's finance-LoRA training-data provenance (synthetic vs. real) — undisclosed in card and blog.
- FinTradeBench's code/data — "to be made available upon publication," not yet public as of this check.
