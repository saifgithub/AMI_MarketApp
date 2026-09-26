# 11 — CR240: 10-ticker DeepInfra/GLM-5.3-Flash vs. Kimi comparison

**Status: run complete.** Saiful, 2026-09-26: "You can run the 10 room convene
now" (after confirming dashboard before-stats). This is the real measurement
[doc 10](10_cr240_deepinfra_cross_provider_setup.md) staged but held off on.

## Method

Full `RoomRunner.run()` convenes (12 agents, PM 5x self-consistency sampling),
`risk_score=3`, real market data (`USE_REAL_MARKET_DATA=true` exported
explicitly — see doc 10's defect #2), DeepInfra's `zai-org/GLM-5.3-Flash` via
`room_ticker_batch.py` (`docs/tools/room_investigation/room_ticker_batch.py`).
Two batches: the 9 tickers that scored `action=APPROVE, approve_votes=5/5` in
the original Kimi r3 batch (`docs/forward_planning/
CR228_risk_appetite_differentiation/results/runs_cr228-r3-kimi-nothink-20260926.jsonl`)
— BAC, JPM, MA, MO, SLB, SO, T, V, WFC — run first, one fresh synthetic
`user_id` for the whole 9-ticker batch; then AAPL run separately afterward
with its own fresh `user_id`, per Saiful's instruction (AAPL had already been
used once as this toolkit's wiring smoke test, on mock data — not reused for
this comparison, this is a fresh real-data run).

Raw data: [`out/10b_9tickers_deepinfra_glm53flash.jsonl`](out/10b_9tickers_deepinfra_glm53flash.jsonl)
+ [`.log`](out/10b_9tickers_deepinfra_glm53flash.log),
[`out/10c_aapl_deepinfra_glm53flash_realdata.jsonl`](out/10c_aapl_deepinfra_glm53flash_realdata.jsonl)
+ [`.log`](out/10c_aapl_deepinfra_glm53flash_realdata.log). Compared against
the original Kimi r3 batch's own JSONL (linked above, not copied here — it's
CR228's data, not this investigation's).

## Result: 6/10 match

| Ticker | DeepInfra GLM-5.3-Flash | Kimi (r3, original) | Match | Spot price (both) | DeepInfra duration |
|---|---|---|---|---|---|
| BAC | APPROVE 5/5 | APPROVE 5/5 | ✅ | $56.70 | 380.8s |
| JPM | APPROVE 5/5 | APPROVE 5/5 | ✅ | $343.06 | 360.0s |
| MA | APPROVE 5/5 | APPROVE 5/5 | ✅ | $567.65 | 307.8s |
| MO | **PASS 0/5** | APPROVE 5/5 | ❌ | $68.82 | 388.5s |
| SLB | **PASS 2/5** | APPROVE 5/5 | ❌ | $51.54 | 405.2s |
| SO | **PASS 0/5** | APPROVE 5/5 | ❌ | $82.88 | 339.6s |
| T | **PASS 0/5** | APPROVE 5/5 | ❌ | $25.38 | 348.0s |
| V | APPROVE 5/5 | APPROVE 5/5 | ✅ | $367.38 | 311.0s |
| WFC | APPROVE 4/5 | APPROVE 5/5 | ✅ (near) | $82.97 | 273.1s |
| AAPL | PASS 0/5 | PASS 0/5 | ✅ | $341.07 | 380.8s |

**Spot prices are identical between the two batches on every ticker** — both
ran against the same real market snapshot (or coincidentally identical
pricing), which rules out "the two batches saw different market data" as the
explanation for the 4 disagreements below. This is a real model/provider
divergence on identical (or near-identical) input, not a data artifact.

## Reading the 4 disagreements

All 4 disagreements are the same direction: **Kimi APPROVEd, GLM-5.3-Flash
PASSed** (never the reverse in this batch) — GLM-5.3-Flash is more
conservative on this set, not just noisier. Two of the four (SO, T) are
tickers this session's earlier CR228 investigation already found to be
genuinely cross-provider-unstable between Kimi and vLLM too (see the earlier
session's SO/T findings — SO's `research_manager` stage is multi-modal
[~17/20 replay draws neutral across both Kimi and vLLM], T's vLLM-side
instability traced to a STANCE-tag/body-text mismatch). **This is consistent
with SO and T sitting in genuinely marginal, provider-sensitive territory
generally** — GLM-5.3-Flash landing on PASS for both is not necessarily a
GLM-5.3-Flash-specific miss, it may be the same instability this
investigation already found showing up against a third provider.

MO and SLB are new — not part of the earlier SO/T/V/WFC deep-dive, so no
existing root-cause to lean on. Whether these are also marginal-vote
territory (would need a Kimi repeat-consistency check on MO/SLB specifically
to know if Kimi's own APPROVE 5/5 is stable) or a genuine GLM-5.3-Flash
quality gap on this specific reasoning task is **not yet determined** — this
doc does not conclude either way, consistent with RES009's own discipline of
not extrapolating past what was actually measured.

**Not yet done, natural next step if this warrants deeper investigation:**
5x Kimi (or vLLM) repeat-consistency check on MO and SLB specifically, the
same pattern [07](07_cr228_bac_risk_score_instability.md) used for BAC, to
establish whether Kimi's own APPROVE 5/5 on those two is a settled result or
one draw of an unstable distribution — before concluding GLM-5.3-Flash
"got it wrong."

## Cost

Saiful's dashboard stats immediately before this batch (`zai-org/GLM-5.3-Flash`,
2026-09-01→2026-10-01 window): 109,485 in / 9,440 out / 14,592 cached-in
tokens (this already includes the earlier AAPL smoke-test's cost from doc
10 — cost isolation for THIS 10-room batch needs an after-batch dashboard
pull, not yet taken as of this doc). Once that after-figure is in, the
delta gives the real cost of 10 full Room convenes on GLM-5.3-Flash,
directly comparable to doc 10's single-convene figure ($0.00678).

## What this is not

- Not a verdict on whether GLM-5.3-Flash is "worse" than Kimi for
  production — 6/10 agreement with the ALL-4-disagreements-in-the-same-
  direction pattern (more conservative, never more aggressive) could read
  either way depending on which failure mode (false PASS vs. false APPROVE)
  the product cares more about avoiding; that's a product call, not a
  measurement conclusion.
- Not a comparison against the CURRENT production model (self-hosted
  Qwen3.8-Flash-Next/vLLM) on these same 10 tickers — CR240 §5's original
  plan called for a 3-way comparison (GLM-5.3-Flash / GLM-5.3 flagship /
  current vLLM); this doc only has DeepInfra-vs-Kimi so far, since the
  original CR228 vLLM r3 batch was on 4 tickers (SO/T/V/WFC), not the 9+1
  set run here. A vLLM r3 run on the same 10 tickers would complete the
  3-way comparison CR240 actually asked for.
- Not the GLM-5.3 flagship comparison — still not run, per Saiful's "no, we
  will not use the flagship yet" (this session, before the 10-ticker batch).
