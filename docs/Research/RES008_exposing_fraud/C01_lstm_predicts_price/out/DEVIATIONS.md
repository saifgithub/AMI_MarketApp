# C01 — deviations, disclosed choices, and the compute-contingency timing

None of these change a parameter, universe, window, metric, or threshold fixed in
`PREREGISTRATION.md`. Each is either the pre-authorised compute contingency, or a
literal reading of something the spec left unstated at the implementation level.

## Compute contingency (pre-authorised)

The spec fixes, in advance: *"if a single A1 run exceeds 4 minutes on this Mac,
epochs drop to 50 for all arms."*

One throwaway A1 run (AAPL, seed 0, full 2012-01-01..2026-08-31 history, lookback
100, 65% train split, 100 epochs, batch 64) was timed on both devices before
`run_c01.py` existed, to decide the device per the spec's "prefer CPU if MPS gives
nondeterministic or slower results" instruction:

| Device | Wall time, 100 epochs, one A1 run |
|---|---|
| MPS  | 51.6 s |
| CPU  | 139.3 s |

A determinism check (10 epochs, seed 0, two independent runs on MPS) produced
identical predictions (max abs diff = 0.0) on the first 20 test-window outputs, so
MPS is both faster and deterministic here. **Decision: MPS, seeds 0/1/2, 100 epochs
for A1/B-price/B-return and 20 epochs for A2 — the pre-registered defaults,
unchanged.** 51.6 s is well under the 4-minute (240 s) threshold, so the epoch-drop
contingency did NOT trigger.

## Literal-reading choices (spec did not specify the exact mechanic)

1. **Split point is on the raw series, not the window count.** "Chronological
   65/35 split" (A1) / "80/20 split" (A2) is applied to the underlying daily-close
   series (`split_at = round(n * split_frac)`); a window belongs to train or test
   according to which segment its **target** date falls in. This keeps the test
   segment's calendar size the same fraction the spec states.
2. **M1 for price arms (A1, A2, B-price):** naive forecast is `y_pred_naive(t+1) =
   close(t)` ("tomorrow = today"), consistent with the prereg's own description of
   the same baseline in H1. RMSE is computed in unscaled ($) price level, as the
   spec requires ("Price-level RMSE, exactly the metric the videos quote"), by
   inverse-transforming both the model's predictions and the true test targets
   through that arm's own fitted scaler.
3. **M1 for B-return:** spec says compare RMSE on returns against "tomorrow's
   return = 0" AND "= today's return"; both are reported (`ratio_vs_zero`,
   `ratio_vs_today`) with `ratio_vs_zero` used as the arm's M1 headline ratio
   (parallel role to the price arms' naive-persistence ratio) since a return
   series' own natural "no information" baseline is zero, not carrying yesterday's
   return forward.
4. **M2 "echoes yesterday" correlation, price arms (A1, A2, B-price):**
   implemented as corr(ŷ(t+1) − ŷ(t), y(t) − y(t−1)) exactly as the spec's
   parenthetical defines it.
4b. **M2 for B-return** (spec only gives B-return's M2 an explicit override for
   "predicted change" = the predicted return itself; it does not restate the
   full M2 formula for a return target). Read literally with that substitution:
   "tracks tomorrow" = corr(predicted return(t+1), actual return(t+1)); "echoes
   yesterday" = corr(predicted return(t+1), actual return(t)) -- the return-space
   analogue of comparing the forecast against the same-day-known value versus
   the value it is trying to predict.
5. **M4 signal timing:** position is decided at the close of bar `t = target_idx −
   1` (the last bar whose close is known when the window ending there is used to
   predict `t+1`), matching the spec's "decided at the close of t." The bars slice
   fed to `run_positions` starts one bar before the first test-segment decision so
   the engine has a well-defined prior position, then the alignment bar's return
   is dropped before pooling — only realised returns on TEST-segment bars are
   counted, per "run through `run_positions` ... over the TEST segment only."
6. **M4 buy-and-hold control:** a constant target-position of +1.0 run through the
   identical `run_positions` call (same bars, same `execution`, same `cost_bps`),
   so it pays the same entry cost the model arm would pay to first go long — the
   spec's "compare with a constant +1 position run through the same function over
   the same bars."
7. **M4 pooling:** "paired difference of daily returns pooled across tickers
   (concatenate per-ticker paired differences for seed 0; also report seeds 1 and
   2)" — implemented as: pool = concatenate each ticker's (model_daily_returns,
   bh_daily_returns) pair across tickers for a given seed, then one
   `common.bootstrap.paired_diff_ci` call over the pooled pair. `results.json`
   carries `pooled_M4` (all three seeds' bars concatenated together) plus
   `pooled_M4_seed0` / `_seed1` / `_seed2` individually, so seed 0's number the
   spec calls out by name is never conflated with the read-only seeds 1/2.
8. **M6 recursive-forecast series:** for price arms, the forecast path and the
   realised path are each converted to day-over-day differences (from the last
   known training-segment close as the anchor for both) before taking the
   standard deviation, so "daily-change standard deviation" means the same thing
   for the model path and the realised path. For B-return, the forecast IS
   already a return series, so no differencing step is applied — its own values
   are the daily changes.
9. **`results.json` omits raw bootstrap replicate arrays.** Every
   `stationary_block_bootstrap_ci` / `paired_diff_ci` call returns `estimate`,
   `lower`, `upper`, `block_len`, `n_boot` (all retained) and a `replicates` array
   of 5,000 floats (dropped before writing `results.json`). The 5,000-float arrays
   are the resampling mechanics behind the reported interval, not a number the
   writeup itself would ever quote; keeping them would have made `results.json`
   dozens of megabytes across ~40 CI calls for no reporting benefit, and Python's
   naive JSON encoding of a numpy array via `default=str` silently truncates it
   through numpy's own `...`-eliding repr, which would have been actively
   misleading if left in.
