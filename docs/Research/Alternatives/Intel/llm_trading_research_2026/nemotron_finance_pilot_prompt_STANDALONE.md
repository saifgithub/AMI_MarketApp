Pilot NVIDIA's Nemotron-3.5-Lightning-30B-A3B, NVFP4-quantized, with a finance-tuned LoRA merged in, on
GB10 (ami-host, 192.168.20.74, DGX Spark, 128GB unified memory). Test whether it's better than what's
already deployed for financial-fundamentals analysis (ratio/statement interpretation → BUY/HOLD/SELL with
reasoning), and whether it runs efficiently.

## The artifacts — read the correction before downloading anything

Three Hugging Face repos are in play:

1. `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16` — full base model, unquantized. 31.58B params, 65.8GB.
2. `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` — NVIDIA's official NVFP4 quant of that base.
   `NemotronHForCausalLM` architecture, 52 hidden layers (matches the BF16 repo). **Verify its actual
   on-disk weight size yourselves before relying on any repo metadata field for parameter count** — see
   the correction below for why.
3. `fastino/Fastino-Nemotron-3.5-Lightning-Finance` — a finance-tuned LoRA (rank 32, adapter name
   `combined-finance-e13`) **merged** into the BF16 base (not shipped as a separate adapter file — it's a
   full 14-shard checkpoint, `model_type: nemotron_h`, `NemotronHForCausalLM`, 52 layers, 31.58B params,
   65.8GB). Trained on financial-document calculation, hybrid text+table QA, SEC-disclosure numeric
   extraction, financial entity extraction. Published benchmark numbers against frontier models, not just
   finance-specialist baselines — e.g. FinQA execution accuracy 59.23% (vs. DeepSeek-R1 671B 65.1%, Llama
   3.3 70B 68.2%, Kimi K2.6 76.0%), TAT-QA F1 56.63, SEC-Num 87.60%, FinEntity macro-F1 79.54,
   BizFinBench 57.46%.

**Correction — a repo with `-DSpark` in the name is NOT a deployable model.**
`nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4-DSpark` looks at first glance like "the NVFP4 quant,
DGX-Spark-optimized" — it is not. Its own `config.json` shows `architectures: ["Qwen3DSparkModel"]` and
only 6 hidden layers, and its actual `model.safetensors` file is **1.35GB** (verified via the file's own
HTTP `content-length`/`x-linked-size`, not repo metadata — repo metadata undercounted its parameter count
too, another reason not to trust that field blindly on quantized repos). Its own README states: *"intended
for DSpark-assisted serving of Nemotron-3.5-Lightning-30B-A3B rather than as a standalone target model
checkpoint."* It's a small speculative-decoding **draft/assist** model meant to pair alongside the real
model to speed up serving — not a replacement for it, and not what you want to deploy standalone. Use repo
#2 above (no `-DSpark` suffix) instead.

## The actual open question

Nobody has published an NVFP4 quant of the *finance-tuned* merged checkpoint (#3) — Fastino only merged
their LoRA onto the unquantized BF16 base. So:

1. Confirm the vLLM version you're running actually supports `nemotron_h` / `NemotronHForCausalLM`
   natively, or needs `--trust-remote-code` (the Fastino repo ships its own `modeling_nemotron_h.py` /
   `configuration_nemotron_h.py`).
2. Decide: **(a)** serve Fastino's finance model in BF16 directly (~66GB weights — check actual free
   memory headroom on the box first), or **(b)** quantize Fastino's merged finance checkpoint to NVFP4
   yourselves using NVIDIA Model Optimizer (https://github.com/NVIDIA/Model-Optimizer — the same tool
   NVIDIA used for their own official quant) to get NVFP4 efficiency with the finance tuning included.

## Infra constraints on this box

- **Do not touch port 8000** or anything managed by the watchdog at
  `/opt/saiful/llm_research/Manager/` on ami-host (cron-driven, auto-restarts a production container via
  `docker compose`). Use a different port — check `/opt/saiful/llm_research/Manager/PORT_ALLOCATION.md`
  on ami-host for what's already assigned before picking one.
- GB10 = 128GB unified memory total (CPU+GPU shared, not discrete VRAM). Check current free memory (`free
  -h`) and running containers (`docker ps`) before loading a new ~66GB (BF16) or smaller (NVFP4) model
  alongside whatever else is already running.

## How to test it

There's an existing test rig on this same box, already used to compare Qwen3.6-35B-A3B-NVFP4 against the
unquantized base Nemotron-3.5-Lightning-30B-A3B on a real fundamentals-analysis task (AAPL):

- Collector: `/opt/saiful/llm_research/quant_finance/scripts/fundamentals_llm2.py` — pulls yfinance +
  OpenBB fundamentals, cross-verifies them, builds a structured analyst brief.
- Runner: `/opt/saiful/llm_research/quant_finance/scripts/dual_model_analysis.py` — sends the same brief
  to multiple OpenAI-compatible endpoints in parallel and captures each model's full response.
- Prior captured prompts/responses for the same AAPL case (to diff your new model's output against):
  `/opt/saiful/llm_research/quant_finance/Docs/prompts_and_responses.md` and
  `/opt/saiful/llm_research/quant_finance/Docs/REVIEW.md`.

Point the new model's OpenAI-compatible endpoint at `dual_model_analysis.py` (just a URL/port change) and
run it against the same AAPL brief. Compare against the two already-captured runs — same ticker, same
prompt, so the diff is purely the model.

**Specific thing to check, not just general vibes**: the AAPL brief includes a data point where yfinance's
`.info` (current-quarter figures) and OpenBB's default statement pull (annual figures, no `period` argument
was passed when this was built) disagree on total debt/cash. This looks like a cross-source data conflict
at first glance but isn't — it's an annual-vs-quarter basis mismatch, confirmed by comparing matched
periods directly (same-quarter yfinance figures agree with each other; the "conflict" only appears against
the annual OpenBB pull). Both an off-the-shelf model tested earlier reasoned about this as if it were a
genuine data-quality conflict, which is technically defensible reasoning but not the deepest possible read.
**Does the finance-tuned model get this right — recognizing it as a basis/period issue rather than treating
it as two sources disagreeing about the same fact?** That's a much better test of whether the finance
tuning actually improved financial-data literacy than any benchmark score.

## Success criteria

- Correctly reasons about the basis-mismatch case above.
- Latency/throughput at a usable context length, measured, not assumed.
- If you quantize it yourselves: does NVFP4 measurably degrade output quality vs. the BF16 Fastino
  checkpoint on the same prompt, side by side?
