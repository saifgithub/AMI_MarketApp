# C03 — RESULTS — "Keep tweaking until the backtest is spectacular"

**Verdict: `DISPROVED`** — for the procedure as taught: choosing the best configuration on a
window, with no holdout, and treating its backtest as what comes next.
Pre-registration: commit `3ac320eb` (2026-09-17), before any test code existed. Run: 2026-09-17 ·
23 instruments × 420 configurations × 2 windows · 2,197 s · `code/` 20 tests green. Every figure is
in [`out/results.json`](out/results.json); T1 and T2 were recomputed independently from the 23
`out/grid_returns_<TICKER>.csv` files and match.

All three pre-registered predictions were met; neither claim-supporting condition was.

---

## 1. Deviations and disclosed assumptions

No parameter, instrument, window, metric or threshold was changed. Full list in
[`out/DEVIATIONS.md`](out/DEVIATIONS.md); the ones that matter:

| # | Choice | Effect |
|:--|:--|:--|
| 1 | Filters gate **entry** only: long while SuperTrend is up; on a flat→long transition all enabled RSI/ADX filters must pass, else entry waits for the first later bar of the same uptrend where they do; exit only when SuperTrend flips. | The videos do not specify the interaction. |
| 2 | A Wilder-smoothing seeding bug was found by a failing unit test and fixed **before** the run reported here. | No reported number comes from the faulty version. |
| 3 | Part 2's random strategies use a C03-local generator matched to the grid's **median** trade count and exposure (the shared placebo matches an exact trade list, which Part 2 does not have). | Part 2 is illustration, not part of the verdict — as pre-registered. |
| 4 | BTC has no history before its tuning window, so its indicators warm up inside it; equities get ≥ 1 year of warm-up. | Data availability. |
| 5 | T4 "per year" is plain division by window length, not a compounded rate. | — |
| 6 | Liquidation reference: the entry bar's open, then the previous close (marked to market daily). | — |
| 8 | **Found after the run:** at 10× on daily bars the "as-shown" path — the one that ignores liquidation — does not look spectacular. It goes through zero: one ≥ 10% adverse day loses more than the account. `leverage_10x_BTC.png` is log-scale and silently drops those bars. | Reported in §4. The picture we expected to reproduce at 10× did not appear; it appears at 5×, which was **not** pre-registered and is labelled so. |

## 2. Part 1 — does the tuning-window winner carry forward?

For each instrument: rank all 420 configurations by tuning-window net return, take the winner, then
look at the holdout. Equities tune 2005–2018, holdout 2019 → 2026-08-31; BTC tunes 2014-09-17 →
2020, holdout 2021 → 2026-08-31. Unlevered, next-open fills, costs included.

| | |
|:--|--:|
| **Mean holdout percentile of the winner (T1)** — 50 means selection told you nothing | **54.5** (95% interval 41.8 – 66.3, bootstrap over instruments) |
| Winner at or above the 80th percentile in the holdout | 7 of 23 (AAPL, META, WMT, CSCO, T, SPY, QQQ) |
| Winner at or below the 20th percentile | 4 of 23 (JPM, PG, BA, GE) |
| Rank correlation, tuning vs holdout return across the 420 (T2), median over instruments | 0.163 — negative on 7 instruments, above 0.5 on 6 |
| **Winner's holdout return below buy-and-hold (T3 < 0)** | **21 of 23** (exceptions: META, DIS) |
| Winner lost money outright in the holdout | 4 of 23 (PG, INTC, BA, PFE) |

The instrument shown in the videos, BTC: the winning configuration returned **+11,889%** over the
tuning window and **+104%** over the holdout, where buying and holding returned +164%. Per year of
window: +1,890 points a year while it was being chosen, +18 a year afterwards. Its holdout
percentile among the 420 was 65.7.

Per-instrument table: `out/summary.txt`. Figures: `out/winner_holdout_percentiles.png`,
`out/is_vs_oos_rank_BTC.png`.

## 3. Part 2 — the best of 420 coin-flippers (illustration, not part of the verdict)

On each tuning window, 420 random long/flat strategies with the grid's median trade count and
exposure. **On all 23 instruments the best random strategy's backtest beat the tuned winner's** —
e.g. AAPL +3,866% vs +2,135%; BTC +13,507% vs +11,889%; SPY +209% vs +119%. Pick the best of a few
hundred of anything on a rising series and the backtest is spectacular; the tuned winner's headline
number is inside what selection alone produces.

## 4. Part 3 — the leverage nobody liquidates

The tuned BTC winner at 10× margin. A long position is liquidated when a bar's low is ≥ 10% below
the reference price.

| Window | Liquidation events at 10× | First | Account if it ends at the first liquidation |
|:--|--:|:--|--:|
| Tuning (2014-09 → 2020) | **26** | 2015-01-28 | 0 |
| Holdout (2021 → 2026-08) | **14** | 2021-01-04 | 0 |

At 10× on daily bars even the path that ignores liquidation ends at −100% (deviation 8).

*Not pre-registered, labelled as such in the outputs:* at **5×** the as-shown path over the tuning
window ends at 6,187 times the starting account — $1,000 into $6.19M — and contains one liquidation
event, on 2017-01-05, when the account stood at 2.6 times its start. A strategy tester with no
liquidation rule prints the first number; an exchange delivers the second.

## 5. Pre-registered hypotheses — scored

| | Prediction | Result | |
|:--|:--|:--|:--|
| H1 | Mean T1 below 65, interval including 50 | 54.5 (41.8 – 66.3) | **met** |
| H2 | T3 < 0 for the majority of instruments | 21 of 23 | **met** |
| H3 | The 10× BTC winner is liquidated at least once inside its own tuning window | 26 times | **met** |

What would have supported the claim: mean T1 ≥ 75 with the interval excluding 50 **and** T3 > 0 in
the majority — 54.5, interval includes 50, 2 of 23 — **not met**; the 10× path never liquidated in
either window — 26 and 14 events — **not met**.

→ **`DISPROVED`**.

## 6. What can and cannot be said

Can be said:

- The best of 420 backtests, carried forward, landed at the 54.5th percentile of the same 420 on
  average — statistically indistinguishable from picking one at random. On some instruments it
  stayed near the top, on others it went to the bottom; you cannot tell in advance which.
- On 21 of 23 instruments the carefully chosen winner then earned less than buying and holding.
- The spectacular number is a property of choosing, not of the strategy: the best of 420 *random*
  strategies back-tested better than the tuned winner on all 23 instruments.
- With 10× margin the chosen BTC strategy would have been liquidated 26 times inside the very
  window it was tuned on.

Cannot be said:

- That trend following is worthless or that parameter search is illegitimate. Walk-forward
  selection with a holdout is ordinary practice; the test is of selection **without** one.
- That the winners lost money: most made money in the holdout (19 of 23) — in a rising market,
  long-only — just less than holding. Every ticker was chosen in 2026 and therefore survived; that
  flatters both sides of the comparison equally.
- T1 is a mean of 23 instruments with a wide interval (41.8 – 66.3). It does not exclude a small
  carry-over; it excludes the large one the procedure assumes (≥ 75).
- Daily bars. An intraday version with stops would liquidate differently; the direction of the
  leverage finding does not depend on it, the counts do.
- The 5× figure is post-hoc and is never quoted without that label.

## 7. Reproduce

```bash
cd docs/Research/RES008_exposing_fraud
.venv/bin/python -m pytest C03_tune_until_spectacular -q
(cd C03_tune_until_spectacular/code && ../../.venv/bin/python run_c03.py)   # ≈ 37 min
```
