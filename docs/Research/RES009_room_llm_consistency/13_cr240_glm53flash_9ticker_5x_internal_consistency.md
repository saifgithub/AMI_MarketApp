# 13 — CR240: GLM-5.3-Flash internal consistency, 9 tickers × 5 draws

**Status: run complete.** Saiful, 2026-09-26: "let's check internal
consistency for glm5.3-flash. I suggest running the 9 tickers 4x more to
get to 5x number." Draw 1 is doc 11's original 9-ticker batch
([`out/10b_9tickers_deepinfra_glm53flash.jsonl`](out/10b_9tickers_deepinfra_glm53flash.jsonl));
draws 2-5 are new, run sequentially this session.

## Method

Same as doc 11: full `RoomRunner.run()` convenes, `risk_score=3`, real
market data, DeepInfra `zai-org/GLM-5.3-Flash`, `room_ticker_batch.py`. 4
additional independent draws of the same 9-ticker list (BAC, JPM, MA, MO,
SLB, SO, T, V, WFC), each its own `--batch-id`/fresh synthetic `user_id`,
run sequentially (not concurrently) to avoid overlapping API load. AAPL was
NOT included in this repeat — it was only ever a single extra data point in
doc 11, not part of the "9 Kimi-approved tickers" set this consistency
check targets.

Raw data: draws 2-5 at
[`out/122_9tickers_deepinfra_glm53flash_draw2.jsonl`](out/122_9tickers_deepinfra_glm53flash_draw2.jsonl)
through
[`out/125_9tickers_deepinfra_glm53flash_draw5.jsonl`](out/125_9tickers_deepinfra_glm53flash_draw5.jsonl)
(+ matching `_users.json`, `.log` per draw); draw 1 is doc 11's
`10b_9tickers_deepinfra_glm53flash.jsonl`.

## Result: GLM-5.3-Flash is internally unstable on 7 of 9 tickers

| Ticker | Draw 1 | Draw 2 | Draw 3 | Draw 4 | Draw 5 | Distribution |
|---|---|---|---|---|---|---|
| BAC | APPROVE 5/5 | PASS 0/5 | APPROVE 5/5 | APPROVE 3/5 | APPROVE 5/5 | 4 APPROVE / 1 PASS |
| JPM | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 | **5/5 unanimous** |
| MA | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 | **5/5 unanimous** |
| MO | PASS 0/5 | PASS 0/5 | APPROVE 5/5 | PASS 0/5 | APPROVE 5/5 | 3 PASS / 2 APPROVE |
| SLB | PASS 2/5 | PASS 0/5 | APPROVE 5/5 | PASS 1/5 | APPROVE 5/5 | 3 PASS / 2 APPROVE |
| SO | PASS 0/5 | PASS 0/5 | PASS 0/5 | APPROVE 5/5 | PASS 1/5 | 4 PASS / 1 APPROVE |
| T | PASS 0/5 | PASS 0/5 | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 | 2 PASS / 3 APPROVE |
| V | APPROVE 5/5 | PASS 0/5 | APPROVE 5/5 | PASS 0/5 | APPROVE 5/5 | 3 APPROVE / 2 PASS |
| WFC | APPROVE 4/5 | PASS 0/5 | APPROVE 5/5 | APPROVE 5/5 | APPROVE 5/5 | 4 APPROVE / 1 PASS |

**Only JPM and MA are unanimous across all 5 draws.** The other 7 tickers
flip action (PASS↔APPROVE) at least once across 5 draws on the identical
ticker, mandate (`risk_score=3`), and real market snapshot per draw (spot
prices were not diffed draw-to-draw in this pass — see "What this doesn't
answer" below). This is a materially bigger instability signal than doc
11's single-draw DeepInfra-vs-Kimi comparison suggested: that comparison's
4/9 "disagreements" looked like GLM-5.3-Flash being more conservative than
Kimi in a consistent direction. With 5 draws in hand, it's clearer that
several of those tickers (BAC, SLB, T, V, WFC) are not stably APPROVE or
stably PASS on GLM-5.3-Flash at all — draw 1 (the one compared against Kimi
in doc 11) could easily have landed on either side by chance.

**Read draw 1's disagreement conclusions in doc 11 in this light**: MO, SLB,
SO, T were flagged there as "Kimi APPROVE / DeepInfra PASS." With the full
5-draw picture, SO is the only one of those four that stays mostly-PASS
(4/5); MO and SLB are roughly 50/50; T actually leans APPROVE (3/5) once
more draws are in. **The single-draw comparison in doc 11 understated how
unstable GLM-5.3-Flash's own verdict is on this set** — this doesn't mean
doc 11's numbers were wrong, it means one draw was never enough to
characterize the model, the same lesson this session's earlier CR228
Kimi/vLLM work already learned (RES009 07) and had to re-learn here on a
third provider.

## What this doesn't answer yet

- **Is this GLM-5.3-Flash-specific, or does Kimi/vLLM show the same
  magnitude of instability on these same 9 tickers at 5 draws each?** The
  original Kimi r3 batch (`docs/forward_planning/
  CR228_risk_appetite_differentiation/results/runs_cr228-r3-kimi-nothink-20260926.jsonl`)
  is only 1 draw per ticker for this set — no Kimi 5x repeat exists for
  MO/SLB/JPM/MA/BAC specifically (only SO/T/V/WFC got the deep 5x-plus
  treatment earlier this session, and that was cross-provider Kimi vs.
  vLLM, not this same GLM-5.3-Flash comparison). Without a matching 5x Kimi
  run on all 9, there's no baseline to say whether 7/9-unstable is worse,
  the same, or better than what Kimi/vLLM would show on this identical set.
- **Root cause not traced.** Doc 11's SO/T root-cause work (research_manager
  multi-modality, STANCE-tag/body-text mismatch) was done on vLLM/Kimi, not
  GLM-5.3-Flash — this doc does not repeat that tracing for GLM-5.3-Flash's
  own instability. Whether the same failure modes apply here is unknown.
- **Spot-price drift between draws not checked.** Each draw ran at a
  different wall-clock time (sequential, ~50-90 min apart); if the real
  market snapshot moved between draws (even slightly, since these are real
  intraday quotes), that's a confound this doc has not ruled out the way
  doc 11 ruled it out for the single-draw DeepInfra-vs-Kimi comparison
  (there, same-day batches had identical spot prices). Worth checking
  before treating 100% of the flip as sampling noise.

## Cost

See [`out/12_cost_tracking_9ticker_5x_consistency.json`](out/12_cost_tracking_9ticker_5x_consistency.json)
for the before/after dashboard figures. `before_4x_run` is recorded
(identical to doc 11's post-10-room-batch figure); `after_4x_run` is
pending Saiful's next dashboard pull.
