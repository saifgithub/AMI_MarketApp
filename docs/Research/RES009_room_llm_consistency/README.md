# RES009 — Room LLM consistency: same prompt, different answer

**Goal:** Saiful noticed two Room convenes on the same ticker (IBM) gave noticeably
different agent responses and asked why. This traces the divergence to its actual
sources, then runs controlled experiments — same captured prompt replayed, temperature
varied explicitly, portfolio state forced to a clean slate, the model asked to explain
its own decision boundary, then that stated boundary tested directly — against both
production's on-prem vLLM model and a second, independent model (Kimi/Moonshot) as a
cross-check.

**Result, short version:**

1. Most of the divergence between two *different users'* Room runs is **expected,
   by-design personalization** — different mandate, different portfolio, different
   trade history baked into every agent's prompt. Not a bug.
2. On top of that: **the exact same captured prompt, replayed against the exact same
   model, produces a different stance a meaningful fraction of the time** — confirmed
   live on this ticker, at multiple temperatures, on two independent model providers.
   No `temperature`/`seed` is set anywhere in this codebase's LLM calls
   ([backend/app/services/llm_gateway.py](../../../backend/app/services/llm_gateway.py)),
   so this is the server's un-pinned default sampling behavior, happening on every
   real Room convene today.
3. **When asked directly "what would change your mind," both models gave a clean,
   confident, reproducible answer** (a revenue-growth threshold). **When that answer
   was tested by actually setting the growth figure to the stated threshold, neither
   model's real behavior matched its own explanation** — for vLLM, the model's own
   stated threshold (5%) was empirically its *least* decisive point, and its own
   *most* decisive point (3%, unanimous NEUTRAL) was one it never named.

This is not primarily a bug report. One narrow defect was found and filed separately
([DEF445](../../defect/_registry/DEF445.row.md) — a false-positive in the numeric
self-check annotator, unrelated to the consistency question). The main finding is
about what the system's variance actually looks like, and that self-reported
explanations from these models cannot be trusted as an audit method for their own
decisions.

**Scope note:** this investigation was run live, interactively, in response to a
direct question — it does not follow RES009's normal write-first-run-second discipline
(no `PREREGISTRATION.md` committed ahead of the runs). Every number below is a real,
measured result from a live run against melehost/vLLM and Kimi's production APIs
(never simulated, never estimated) — but thresholds and follow-up questions were
chosen adaptively as findings came in, which is disclosed explicitly per doc, not
concealed. Where a run's raw output could not be preserved (one temperature cascade
lost to a container restart — see [04](04_vllm_run_a_temperature_cascade.md)), that
gap is stated, not filled in from memory.

**Related, and kept in sync with this doc:**

- [`docs/tools/room_investigation/`](../../tools/room_investigation/) — the reusable
  toolkit this investigation is built on (`room_kimi_gateway.py`'s shared
  force-a-provider-and-run-a-Room core, `room_agent_replay.py` for single-agent
  replay, `room_repeat_consistency.py`/`room_risk_score_sweep.py`/
  `room_ticker_batch.py` for repeat/sweep/batch drivers, `room_llm_audit_trace.py`
  for pulling captured prompts). Every script here that ran against a real
  provider used one of these tools; new findings from using the toolkit
  (gotchas, defects caught) get written back into its own README, not just here.
- [`docs/forward_planning/CR240_llm_provider_evaluation/`](../../forward_planning/CR240_llm_provider_evaluation/CR240.md) —
  the CR this investigation's cross-provider work feeds into: evaluating hosted
  LLM providers (DeepInfra/GLM-5.3-Flash, etc.) as a production replacement for
  the self-hosted vLLM model, sized against real Room data rather than price
  tables alone. [Doc 10](10_cr240_deepinfra_cross_provider_setup.md) in this
  series is CR240's own measurement work, run and logged here because it's the
  same kind of same-ticker/cross-provider comparison every other doc in this
  series already does.

---

## How to read this

| Part | What it covers |
|:--|:--|
| [01 — Where the divergence actually comes from](01_divergence_sources.md) | Per-user context (mandate, holdings, trade history) vs. sampling noise — traced from two real production runs |
| [02 — Temperature sweep, 0.2→1.0](02_temperature_sweep.md) | Same two runs' prompts, replayed at five explicit temperatures |
| [03 — Portfolio counterfactual](03_portfolio_counterfactual.md) | Same ticker, same mandate, real convene, portfolio forced to 100% cash — does holdings state change the verdict? |
| [04 — vLLM temperature cascade, both runs](04_vllm_run_a_temperature_cascade.md) | 10x repeats at each of T=1.0/0.8/0.6/0.4, per run, looking for the temperature where the model becomes internally consistent |
| [05 — Kimi cross-check](05_kimi_cross_check.md) | The same tests against a second, independent model/provider — **includes exactly how Kimi was reached: which key, which endpoint, which model, how thinking was disabled** |
| [06 — Ask the model, then test the answer](06_pivot_and_growth_threshold_test.md) | The model's own stated decision threshold, then a direct test of that threshold across both providers |
| [07 — CR228 BAC risk_score sweep instability](07_cr228_bac_risk_score_instability.md) | risk_score=2 is a genuine ~2-in-3 coin flip on BAC; risk_score=3 is stable — instability compounds through the pipeline, not one fork point |
| [10 — CR240 DeepInfra/GLM-5.3-Flash cross-provider setup (in progress)](10_cr240_deepinfra_cross_provider_setup.md) | New toolkit (`room_ticker_batch.py`, DeepInfra support in `room_kimi_gateway.py`), two real defects caught by the AAPL smoke test (DeepInfra URL double-prefix; `backend/.env` not existing silently degrading DB/market-data settings), measured per-convene cost from the DeepInfra dashboard. The real 9-ticker batch is staged, not yet run. |

## Raw data

Every run's full prompt/response JSON is under [`out/`](out/) — nothing here is
summarized without the underlying artifact sitting next to it. The scripts that
produced them are under [`code/`](code/), copied verbatim from
`backend/scripts/ibm_*.py` at the time each was run (diagnostic-only scripts; never
part of the shipped app — see each script's own docstring for what it does and does
not touch).

| File | What it is |
|:--|:--|
| [`out/01_original_two_runs_diff.json`](out/01_original_two_runs_diff.json) | Full per-agent prompt/response diff, the two original 2026-09-25 IBM runs |
| [`out/02_temperature_sweep_0.2_to_1.0.json`](out/02_temperature_sweep_0.2_to_1.0.json) | `fundamentals_analyst` + `portfolio_manager`, both original runs, 5 temperature steps |
| [`out/03_cash_only_counterfactual.json`](out/03_cash_only_counterfactual.json) | Full 12-agent transcript, portfolio forced to $10k all-cash |
| [`out/04a-c_vllm_run_b_repeat10_T*.json`](out/) | vLLM, Run B's prompt, 10x repeats at T=1.0/0.8/0.6 |
| [`out/05a-b_kimi_run_*_repeat10_T0.6.json`](out/) | Kimi, both runs' prompts, 10x repeats at T=0.6 (the only temperature this key's models accept) |
| [`out/06a-d_pivot_probe_run_*.json`](out/) | "What would flip you to FOR" — both runs, both providers |
| [`out/07a-b_growth_threshold_run_a_*.json`](out/) | TTM revenue growth set to 2/3/4/5%, up to 10x each, both providers |

## What this is not

- Not a claim that the Room is broken. The PM verdict (the actual trading decision)
  agreed across every original run and every counterfactual tested — `pm_self_consistency_samples=5`
  ([backend/app/core/config.py](../../../backend/app/core/config.py)) is doing its job
  of absorbing this noise at the top of the pipeline.
- Not a benchmark of Kimi vs. vLLM as candidate providers — no accuracy/quality claim
  either way, only a consistency comparison on one ticker's one prompt.
- Not exhaustive — one ticker (IBM), one agent role (`fundamentals_analyst`) carries
  almost all of the depth; `portfolio_manager` and others are touched more lightly.
  A follow-up CR/RES could widen this if the pattern needs confirming elsewhere.
