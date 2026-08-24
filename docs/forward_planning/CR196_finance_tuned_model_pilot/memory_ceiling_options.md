# CR196 — the activation-memory ceiling: options, and a question for NVIDIA

Written 2026-08-24 (AT:R70) while run 2 trains. Every OOM in this CR traces to one
constraint; this records the options for removing it rather than working around it again.

## The constraint, stated once

alpha-spark is a DGX Spark GB10: Grace CPU + Blackwell GPU share **one 121GB LPDDR5X pool**
(`nvidia-smi` reports FB Memory as N/A — there is no separate framebuffer). So:

```
62GB frozen bf16 base  +  activations for the longest sequence  +  OS/page cache  <=  121GB
```

`NemotronHForCausalLM` raises *"does not support gradient checkpointing"*, so the activation
term is **uncapped** — it scales linearly with sequence length and there is no recompute
option to bound it. Measured consequences:

| cutoff | outcome |
|---|---|
| 8,192 | OOM (run 1) |
| 5,120 | ran 400 steps clean as a probe; OOM-killed at step 185 and again at 375 on the full run |
| 4,096 | running; peak 99GB vs 106GB at 5,120 |

5,120 failing *non-deterministically* is the signature: with `batch_size=1`, peak memory is set
by the longest single row drawn, and only 10 rows in 20,021 need 5,120 tokens. It was a dice
roll on when one came up, not a leak. Capping the tail removed the roll.

## Why this is Nemotron-specific, and why we keep it anyway

Two costs are genuinely attributable to the architecture:

1. **No gradient checkpointing.** This is the whole problem. Any dense Llama/Qwen-class model
   supports it and would bound activations at ~sqrt(layers) cost.
2. **Unsloth does not work on this checkpoint** — it loads, then dies at train start with
   `Cannot copy out of meta tensor; no data!`. Unsloth is the ~60–70% VRAM / ~2× speed path,
   i.e. exactly the headroom we lack. Its absence forced plain TRL+PEFT, the least
   memory-optimised option available.
   (A related-but-different Unsloth failure on this family is reported in
   [unslothai/unsloth#3810](https://github.com/unslothai/unsloth/discussions/3810): LoRA merge
   fails on `...experts.N.up_proj.SCB` name mismatches. Our `merge_lora_to_disk.py` already
   sidesteps that with a shard-wise CPU merge.)

MoE does **not** buy memory back: the 128×24 routed experts are resident in bf16 regardless of
which are activated, so 31.6B total is the number that matters for memory, and "3.3B active"
buys compute only.

Against that: this base won the basis rubric **43/44 vs Qwen3.6's 21/43**. "Harder to train"
and "worth training" are the same fact here. Switching bases costs a verified quality edge and
a full eval re-run, to solve something whose immediate fix was a 32-row filter.

## Options, cheapest first

| # | option | cost | what it buys | status |
|---|---|---|---|---|
| 1 | Cap sequence length, drop the tail | trivial (0.16% of rows) | ~20% peak cut | **done** — run 2 is on it |
| 2 | **NeMo AutoModel** instead of TRL+PEFT | ~1 day to port | NVIDIA's own validated path for Nemotron-H; documents **activation checkpointing** and PEFT, with explicit DGX Spark 128GB single-node support | **untried — the best unexplored lead** |
| 3 | **QLoRA** (4-bit base) | ~half day | 62GB base → ~18GB; would end the ceiling outright | untried; bnb on aarch64/Blackwell already falls back to a CUDA 13.0 build, so viability is unproven |
| 4 | Hand-rolled `torch.utils.checkpoint` around layers | 1–2 days, risky | bounds activations | not attempted; Mamba mixers may not be recompute-safe |
| 5 | Different base model | days + lose the quality edge | removes the problem | last resort |

**Option 2 is the one to try next**, and only if run 2's acceptance justifies more investment.
It was in the original Phase-0 harness plan (Unsloth → NeMo AutoModel → TRL+PEFT) and was
skipped when Unsloth failed — we fell straight through to the fallback without testing the
middle option, which is the one NVIDIA actually validates for this architecture.

## Draft post for the NVIDIA developer forum

> **Subject: LoRA fine-tuning Nemotron-H (hybrid Mamba-MoE) on DGX Spark — activation checkpointing?**
>
> I'm LoRA fine-tuning a Nemotron-3.5-Lightning derivative (31.6B, `nemotron_h`, bf16) with
> TRL+PEFT on a DGX Spark GB10 (121GB unified memory), rank 32 on attention q/k/v/o + Mamba
> `in_proj` + shared-expert up/down (93 modules, 22.7M trainable).
>
> `NemotronHForCausalLM.gradient_checkpointing_enable()` raises "does not support gradient
> checkpointing". With `batch_size=1` and no recompute, activation memory scales linearly with
> sequence length against a fixed 62GB of frozen weights, so effective context is bounded by
> memory rather than by the model: 4,096 tokens peaks at ~99GB and trains fine, 5,120 OOM-kills
> the box non-deterministically (whenever a max-length row is drawn), 8,192 never starts.
>
> 1. Is activation/gradient checkpointing supported for the Nemotron-H backbone anywhere in the
>    stack — NeMo AutoModel, Megatron Bridge? The AutoModel docs list both activation
>    checkpointing and LoRA/QLoRA PEFT; is recompute actually wired up for the **Mamba mixer**
>    layers, or attention-only?
> 2. Is there a recommended configuration for LoRA on this family at 8k+ context on a single
>    128GB unified-memory node?
> 3. Is QLoRA (4-bit base) expected to work for `nemotron_h` on aarch64/Blackwell? bitsandbytes
>    reports no prebuilt binary for CUDA 13.1 and loads a 13.0 build.
>
> Separately: Unsloth loads this checkpoint but dies at train start with `Cannot copy out of
> meta tensor; no data!` — is `nemotron_h` a known gap there?

## Sources

- [Nemotron-H paper (arXiv 2504.03624)](https://arxiv.org/html/2504.03624v4)
- [NeMo AutoModel docs](https://docs.nvidia.com/nemo/automodel/latest)
- [NeMo AutoModel checkpointing guide](https://docs.nvidia.com/nemo/automodel/latest/guides/checkpointing.html)
- [Nemotron deployment guides — DGX Spark single node](https://docs.nvidia.com/nemotron/nightly/deployment-guides.html)
- [unslothai/unsloth discussion #3810](https://github.com/unslothai/unsloth/discussions/3810)
