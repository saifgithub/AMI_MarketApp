# Pilot brief: Nemotron-3.5-Lightning + finance LoRA on GB10

**For: the LLM team.** Compiled 2026-08-18 after a partial hands-on investigation surfaced a real
correction to the plan — read the correction before downloading anything.

## Objective

Pilot-test whether NVIDIA's Nemotron-3.5-Lightning-30B-A3B — with the Fastino finance-tuned LoRA merged
in — beats the current production stack on financial fundamentals analysis, and whether it can run
efficiently (NVFP4) on GB10 (DGX Spark, 128GB unified memory).

## Background

AMI Trade already dual-model-tested the base Nemotron-3.5-Lightning-30B-A3B (unquantized) against
Qwen3.6-35B-A3B-NVFP4 on a real fundamentals-analysis task (AAPL) —
[`../quant_finance/`](../quant_finance/). A broader 2026 literature survey then turned up two new
developments: NVIDIA published an official NVFP4 quant of that same base model, and a third party
(Fastino) published a finance-tuned LoRA on it with honest benchmark comparisons against frontier models
(FinQA, TAT-QA, SEC-Num, FinEntity, BizFinBench, ConvFinQA) — see
[`04_new_models_and_training.md`](04_new_models_and_training.md) §1, §4.

## Correction — read before downloading anything

`nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4-DSpark` is **not** a deployable quantized model. Its
own config shows `architectures: ["Qwen3DSparkModel"]`, 6 hidden layers, and a `model.safetensors` file
that's **1.35GB** — confirmed via the actual file's `x-linked-size` header, not just metadata. Its own
README states plainly: *"intended for DSpark-assisted serving of Nemotron-3.5-Lightning-30B-A3B rather
than as a standalone target model checkpoint."* It's a speculative-decoding **draft/assist** model, paired
alongside the real model to speed up serving — not a replacement for it. (`04_new_models_and_training.md`
originally characterized this as "the official NVFP4 quant" — that framing is wrong and is being corrected
here.)

The artifact you actually want is the sibling repo **without** `-DSpark`:
`nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` — architecture `NemotronHForCausalLM`,
`model_type: nemotron_h`, 52 hidden layers. That matches the Fastino finance model's architecture exactly
(also `NemotronHForCausalLM`, 52 layers) — same lineage, consistent.

## The three artifacts in play

| Repo | What it is | Size | Role |
|---|---|---|---|
| `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16` | Full base, unquantized | 31.58B params, 65.8GB | Reference — what AMI already tested |
| `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` | Official NVFP4 quant of the full base | Metadata reports 17.8B params vs. the BF16 repo's 31.58B — **verify actual size before relying on this**, quantized-repo metadata was unreliable for the DSpark case above | The efficient-serving candidate |
| `fastino/Fastino-Nemotron-3.5-Lightning-Finance` | Finance LoRA (rank 32, adapter `combined-finance-e13`) **merged** into the BF16 base — a full checkpoint, not an adapter file | 31.58B params, 65.8GB, 14 shards | The finance-tuned candidate — **not quantized by anyone yet** |

## The open question this pilot needs to answer

Nobody has published an NVFP4 quant of the finance-tuned merged model — Fastino's LoRA was only merged
onto the BF16 base. So the real work is:

1. Confirm the vLLM version on ami-host actually supports `nemotron_h`/`NemotronHForCausalLM` natively, or
   needs `--trust-remote-code` with the custom `modeling_nemotron_h.py`/`configuration_nemotron_h.py`
   shipped in the Fastino repo.
2. Decide: **(a)** serve Fastino's finance model in BF16 directly (~66GB weights — fits in 128GB unified
   memory, but check actual free headroom on ami-host first and don't crowd out what's already running),
   or **(b)** quantize Fastino's merged finance checkpoint to NVFP4 yourselves with NVIDIA Model Optimizer
   (https://github.com/NVIDIA/Model-Optimizer, the same tool used for the official quants) to get NVFP4
   efficiency with the finance tuning included.
3. **Do not touch `ami-llm` (production, port 8000)** or anything the daily watchdog manages
   (`/opt/saiful/llm_research/Manager/` — cron-driven, auto-restarts `vllm-qwen36-tf5` via
   `docker-compose.qwen36-ami-llm.yml`). Use a new port; check `PORT_ALLOCATION.md` in that Manager
   directory for what's free first.

## How to actually test it — reuse existing infra, don't rebuild

- The exact AAPL fundamentals brief already used to compare Qwen3.6 vs. base Nemotron-3.5-Lightning lives
  on ami-host: `/opt/saiful/llm_research/quant_finance/scripts/fundamentals_llm2.py` (data collector) +
  `dual_model_analysis.py` (model runner). See
  [`../quant_finance/prompts_and_responses.md`](../quant_finance/prompts_and_responses.md) for the exact
  prior prompts/responses to diff against.
- Point the new model's OpenAI-compatible endpoint at the same script and compare output against the two
  already-captured runs (Qwen3.6, base Nemotron) on the same ticker, same prompt — apples to apples.
- Also worth specifically checking: does the finance LoRA change behavior on the thing AMI's own research
  flagged as the real risk — the yfinance-vs-OpenBB debt/cash basis mismatch. See
  [`../quant_finance/VERIFICATION.md`](../quant_finance/VERIFICATION.md) — this was originally
  miscategorized as a genuine cross-source "conflict"; it's actually an annual-vs-quarter basis mismatch.
  The real test of the finance tuning is whether it reasons about *that* correctly, not just whether it
  flags something as suspicious.

## Success criteria

- Does it correctly reason about the basis-mismatch nuance above — a real test of "did the finance tuning
  improve financial data literacy" vs. "does it just sound more finance-y"?
- Latency/throughput at a usable context length vs. what's already running.
- If quantized: does NVFP4 measurably degrade output quality vs. the BF16 Fastino checkpoint on the same
  prompt?
