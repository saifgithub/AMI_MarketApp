# CR077 — Prompt caching is already on, delivers 0% on Room prompts, and could not have helped much anyway

**Status:** proposed · **Track:** AT:R59 (protect-the-Room lane — brief only, the build team implements)
**Filed:** 2026-07-23

---

## What Saiful asked

> *"research llm caching. lots of our messages to the llm are static, especially for the agents.
> is there a way we can speed up the processing by pre-caching a major part of the prompt?"*

The premise is right — the agent prompts *are* largely static. The conclusion doesn't follow, and
the measurements say so in two independent ways. This CR records what was measured, then proposes
the change that is actually worth making.

---

## Answer in three numbers

All measured 2026-07-23 against the live serving host `192.168.20.74:8000`
(vLLM `0.23.1.dev0+g0fc695fc6`, model `ami-llm` = `RedHatAI/Qwen3.6-35B-A3B-NVFP4`).

1. **Prefix caching is already enabled.** `vllm:cache_config_info{enable_prefix_caching="True"}`.
   Nothing needs turning on. Lifetime hit rate 17,151,568 / 50,924,616 queried tokens = **33.7%**.
2. **It delivers exactly zero on Room prompts.** The cache block size on this model is
   **2,096 tokens**, and vLLM only caches *whole* blocks. Every Room agent's system prompt is
   1,143–2,264 tokens. Measured cliff: a **2,095**-token prompt repeated verbatim → **0** cache-hit
   tokens; a **2,096**-token prompt → 2,096 hit tokens. Reuse is always a multiple of 2,096
   (observed: 2096, 4192, 6288, 14672).
3. **Prefill is ~4% of a turn.** Decode runs at **33.0 tok/s** single-stream (200 tokens in 6.07 s;
   400 in 11.89 s — same rate, so it is a clean measurement). Prefilling a whole 1,300-token Room
   prompt costs **~0.29 s**. A 250-token agent turn costs **~7.6 s** to generate. Perfect caching of
   100% of every prompt would cut a convene by about **4%**.

**So: pre-caching the static part of the prompt is not the lever.** The Room is decode-bound, not
prefill-bound. Even the best possible version of what was asked for is a rounding error.

---

## Why the cache misses everything (the mechanism, for the record)

`ami-llm` is a Mamba/attention **hybrid**. vLLM must make the attention page size ≥ the Mamba page
size, so it auto-resolves `block_size` upward — 528 tokens for the small models in this family,
**2,096** for ours (`_block_size_resolved="True"`, `user_specified_block_size="False"`,
`mamba_cache_mode="align"`). Prefix caching is block-granular, so anything below one block caches
nothing at all. This is a known open upstream issue, not a misconfiguration on our side —
vllm-project/vllm [#40696](https://github.com/vllm-project/vllm/issues/40696) is titled almost
exactly this problem.

Our prompts sit under the cliff by construction. Measured, per agent, with an empty transcript:

| agent | base `.md` | + mandate overlay | full system prompt |
|---|---:|---:|---:|
| fundamentals_analyst | 587 | 904 | 1,408 |
| market_analyst | 436 | 768 | 1,271 |
| news_analyst | 457 | 846 | 1,349 |
| social_media_analyst | 532 | 975 | 1,479 |
| bull_researcher | 397 | 768 | 1,279 |
| bear_researcher | 382 | 732 | 1,244 |
| research_manager | 295 | 674 | 1,187 |
| trader | 360 | 740 | 1,255 |
| aggressive_debator | 338 | 684 | 1,193 |
| conservative_debator | 309 | 652 | 1,160 |
| neutral_debator | 271 | 635 | 1,143 |
| portfolio_manager | 551 | 1,387 | 2,264 |

The "static part" a cache would hold is the **+overlay** column: 635–1,387 tokens. All of it below
2,096. And the 12 agents share **no** common prefix — `build_agent_prompt()` puts the per-agent
`content/agents/<id>.md` at token 0, so the twelve prompts diverge on their first token.

A partial-share test confirms the reuse rule exactly: with a 2,976-token shared prefix followed by
differing per-agent tails, the second request reused **2,096** tokens regardless of tail length
(81 / 641 / 1,601 tokens tested). Reusable tokens = `floor(shared_prefix / 2096) × 2096`. The 880
tokens in the partial block are recomputed every time.

**One trap worth recording** for anyone who does pursue this: in `align` cache mode the Mamba
checkpoint is only kept at the last block boundary before the prompt ends. If that boundary lands
in request-unique tokens rather than in the shared prefix, vLLM discards the *whole* prefix match —
including attention blocks that matched perfectly — and the hit rate silently drops to zero
(vllm-project/vllm [#45238](https://github.com/vllm-project/vllm/issues/45238)). It did not trigger
in the tests above, but it is a silent-failure mode in exactly the design a prompt-reordering fix
would create. That is the CR040 "degrade loudly" class arriving from inside the inference server.

---

## What the lever actually is

Concurrency. Measured on the same host, `min_tokens=200` forced on every stream so the token counts
are exact, and each stream salted with a unique prefix so no cache cross-talk:

| concurrent streams | wall clock | aggregate | per-stream | vs. running them one after another |
|---:|---:|---:|---:|---:|
| 1 | 6.07 s | 33.0 tok/s | 33.0 tok/s | — |
| 2 | 7.01 s | 57.1 tok/s | 28.5 tok/s | **1.73×** |
| 4 | 8.78 s | 91.1 tok/s | 22.8 tok/s | **2.77×** |
| 8 | 10.63 s | 150.5 tok/s | 18.8 tok/s | **4.57×** |

The GPU has enormous headroom for this: `num_gpu_blocks=1664` × 2,096 = **3.49M tokens** of KV
cache, at `gpu_memory_utilization=0.5` — half the card is not being used at all.

`room_runner.py:1375-1393` runs every agent strictly sequentially — a `for phase` loop wrapping a
`for agent_id in phase.agents` loop, each `_speak_one_agent()` fully awaited before the next starts.
Of the six phases, exactly one has agents that could plausibly run together:

| phase | agents | can they run concurrently? |
|---|---|---|
| ANALYSTS | fundamentals, market, news, social | **arguably yes** — four independent domains |
| RESEARCHERS | bull, bear | no — bear answers bull |
| SYNTHESIS | research_manager | n/a |
| EXECUTION | trader | n/a |
| RISK | aggressive, conservative, neutral | no — they explicitly debate each other |
| VERDICT | portfolio_manager | n/a |

Running the four analysts concurrently turns ~4 × 6.1 s into ~8.8 s at the measured 4-stream rate —
**about 15 s off a convene**, roughly 4× what perfect prompt caching could ever deliver.

---

## The catch, and it is mine to raise

**This is not a free optimisation. It changes what the Room is.**

Every agent prompt today contains `Transcript so far:` (`room_prompts.py:214`) and the instruction
*"Build on the transcript — do not repeat what's already been said"* (`:220-222`). Run the four
analysts concurrently and each one is blind to the other three. Two things follow:

1. The four analysts will **repeat each other**, because the instruction telling them not to now
   refers to an empty transcript. The user reads four contributions and sees redundancy.
2. The Room stops being a debate in its first phase and becomes four parallel monologues that a
   later agent stitches together.

Whether that is acceptable is a **Room-quality** judgement, not a latency one, and it must be
decided by reading real output — not by reasoning about it. Upstream TradingAgents treats the four
analysts as independent, which is evidence it is survivable, but our prompts were written on the
assumption they are not.

So the deliverable below is gated on an A/B, and the A/B is the actual work.

---

## Scope

**Phase 1 — decide the analyst-concurrency question on evidence (blocking, cheap).**
Run the same 5 tickers through the Room twice: sequential analysts (today) and concurrent analysts.
Diff the four analyst contributions for repetition and for content loss. Deliverable is the two
transcripts plus a recommendation. If output quality holds, Phase 2 ships; if it doesn't, this CR
closes at Phase 1 with a documented "no" and the 15 s stays on the table. **No code ships before
this.**

**Phase 2 — parallelise the ANALYSTS phase only (gated on Phase 1).**
`asyncio.gather` over `phase.agents` where the phase is marked independent; the streaming
`RoomEvent` order must stay deterministic so the mobile client renders the four analysts in a fixed
order regardless of which finishes first. RESEARCHERS / RISK stay sequential — they are debates and
the dependency is the point. Add a per-phase `parallel: bool` on `_Phase` rather than special-casing
the label, so the decision is visible in one place.

**Phase 3 — raise `gpu_memory_utilization` on the vLLM host (ops, independent of the above).**
Currently `0.5`. Raising it gives more concurrent sequences and a larger prefix cache. This is a
serve-arg on `192.168.20.74`, which this workstation has no SSH access to — Saiful or the architect
applies it. Measure before/after; do not assume.

**Explicitly out of scope: restructuring the prompts to build a shared cacheable prefix.**
It would require hoisting a ≥2,096-token common preamble in front of the per-agent persona — moving
the persona to the *end* of the prompt, which collides head-on with the safety-floor ordering rule
(`agent_prompts.py:64-65`: the floor is appended last *so it dominates instruction ordering*) and
with CR038's finding that agents follow instructions ~70% of the time in the first place. Paying a
Room-quality risk of that size to recover 4% of wall clock is a bad trade. Revisit only if upstream
vLLM lands sub-block caching for hybrid models, at which point it becomes free.

---

## Guard

If Phase 2 ships, a test must assert the phases that are marked parallel are exactly the phases
whose agents do not read each other's output. The failure mode — someone later marks RISK parallel
because it looks like a list of three independent debators — silently deletes the risk debate while
every test still passes and the UI still renders three contributions. That is the shape of DEF084:
a feature that looks present and isn't.

Second guard, cheap: assert `enable_prefix_caching` is on and log the measured hit rate at startup.
Right now nobody would notice if it were switched off, which is how it stayed at 0% on Room traffic
without anyone knowing.

---

## Verification

1. `cd backend && .venv/bin/python -m pytest tests/unit/ -q` green, with the new phase-parallelism
   guard proven red before the fix.
2. Phase 1's two transcripts, side by side, with the repetition count stated as a number.
3. Convene wall-clock before and after, measured on Alpha, same ticker, three runs each. No
   estimates.
4. `vllm:prefix_cache_hits_total` / `queries_total` sampled before and after Phase 3.

---

## Governance

Commit tag `(AT:R59 CR077)`. Relates to **CR040** (degrade loudly — the align-mode silent-zero
failure mode, and the missing prefix-cache observability), **CR038** (prompt instructions are not
controls — why the prompt-reordering route is refused), and **DEF084** (a feature that looks present
and isn't — the shape the Phase-2 guard exists to prevent).

**Note for the next session:** CLAUDE.md's runtime table still describes the LLM as *"Gemma 4 31B,
NVFP4"*. The serving host reports `RedHatAI/Qwen3.6-35B-A3B-NVFP4`. The rebrand to `ami-llm` holds;
the underlying model in the table is stale.
