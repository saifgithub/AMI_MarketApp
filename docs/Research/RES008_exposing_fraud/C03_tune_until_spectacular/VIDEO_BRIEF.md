# C03 — VIDEO BRIEF — The best of 420 backtests, one window later

**Verdict:** `DISPROVED` (the procedure: pick the best backtest, no holdout) · **Pre-registration commit:** `3ac320eb` · **Results:** [`RESULTS.md`](RESULTS.md)
**Runtime target:** 10–12 min · **Format:** faceless, chart-driven, voice-over
**Claim class reach (measured 2026-09-17):** shares the chatbot-strategy videos (3 videos · 3.28M views) plus 2 more read; not separately summed

## Search intent

- **Primary keyword:** backtest overfitting tested
- **Secondary:** optimize trading strategy parameters · best backtest settings · why backtests fail live
- The primary keyword appears in the title, the first spoken sentence, and the first line of the description.

## Title options (≤ 60 characters, all literally true)

1. *We picked the best of 420 backtests. Then time passed.*
2. *Backtest overfitting tested: +11,889% became +104%*
3. *The best backtest lost to buy-and-hold on 21 of 23*

## Thumbnail concept

One equity curve that goes vertical, a dashed line where the tuning window ends, and a flat line
after it. Text: "+11,889% → +104%".

## Hook (0:00–0:20) — spoken, verbatim

> "Backtest overfitting, tested. You've seen the move: take a strategy, tweak the settings, watch
> the equity curve, keep the version that looks best — a thousand dollars into millions. We did
> exactly that, four hundred and twenty versions, twenty-three markets. On Bitcoin the winner made
> eleven thousand eight hundred percent. Then we let time pass. Over the next five and a half
> years the same settings made a hundred and four — less than just holding the coin."

## Beat sheet

| # | Beat | Time | Voice-over (gist) | On screen | Source of every number |
|:--|:--|:--|:--|:--|:--|
| 1 | Cold open | 0:00–0:20 | Hook above. | The BTC winner's curve, then the holdout appended. | `per_instrument["BTC-USD"]`: `winner_tune_return` 118.89, `winner_holdout_return` 1.041, `holdout_buy_hold_return` 1.644; `grid_size` 420; `n_instruments` 23 |
| 2 | The stakes | 0:20–0:50 | The viewer's next step is to put money behind the settings with the best screenshot — often with margin, because the screenshot assumed it. | A strategy-tester panel we drew ourselves; "Net profit" field highlighted. | — |
| 3 | What would convince us | 0:50–2:00 | Written down first: if picking the best backtest works, the winner should stay near the top afterwards — 75th percentile or better on average — and beat buy-and-hold on most markets. We predicted it would land near the middle. | `PREREGISTRATION.md`, commit `3ac320eb`. | `PREREGISTRATION.md` |
| 4 | The test, as taught | 2:00–4:00 | The same family the videos use: SuperTrend, optional RSI filter, optional ADX filter. Every combination fixed in advance: 420. Rank them on the tuning window and crown the winner — exactly what is done on camera. We get the picture: AAPL +2,135%, BTC +11,889%. | The grid as a wall of 420 small curves; the winner lights up. | `winner_tune_return`: AAPL 21.35, BTC-USD 118.89 |
| 5 | The fair test + reveal | 4:00–7:30 | Now the years the winner never saw. If selection told us nothing, the winner would land at the 50th percentile of the 420. It landed at 54.5 on average — the interval runs from 42 to 66. Seven winners stayed in the top fifth; four fell to the bottom fifth. And on 21 of 23 markets the winner earned less than holding. Then the margin: at 10×, the Bitcoin winner is liquidated 26 times inside the window it was tuned on. | `winner_holdout_percentiles.png`, dots dropping in one by one; the 50 line. `is_vs_oos_rank_BTC.png` — a cloud, not a line. T3 tally 21/23. Liquidation dates ticking on the BTC curve. | `pooled`: `mean_T1` 54.52 (41.80–66.34), `n_instruments_T3_negative` 21, `median_T2` 0.163; per-instrument T1; `part3_btc_leverage.tuning.leverage_10x.n_liquidation_events` 26, holdout 14 |
| 6 | Why | 7:30–9:30 | Selection. Try 420 of anything and the best one looks brilliant — partly because it is good, mostly because it was lucky on that window, and the backtest cannot tell you which part is which. Proof: 420 *random* in-and-out strategies, same number of trades. The best random one beat the tuned winner's backtest on all 23 markets. | Side by side: tuned winner vs best-of-420 random, 23 pairs. | `part2_random_placebo`: `best_random_tune_return` > `tuned_winner_tune_return` on 23 of 23 (AAPL 38.66 vs 21.35; BTC 135.07 vs 118.89; SPY 2.09 vs 1.19) |
| 7 | What is true | 9:30–10:40 | Trend following is a real, long-studied style, and searching parameters is normal — when you hold data back and test on it once. Most of these winners still made money afterwards, 19 of 23; the market went up and they were long. They just made less than doing nothing, after all that work. And our average of 54.5 has a wide interval: it doesn't rule out a small carry-over. It rules out the big one the procedure assumes. One more, flagged as not pre-registered: at 5× the no-liquidation backtest turns $1,000 into $6.19M — with a liquidation in January 2017, when the account stood at 2.6 times its start. | "19 of 23 still made money — long, in a rising market" card; the 5× curve with the 2017-01-05 marker, stamped "post-hoc". | `winner_holdout_return` > 0 on 19 of 23; `leverage_5x_extra_not_preregistered`: `as_shown_final_equity_multiple` 6,186.9, 1 event 2017-01-05 |
| 8 | Check the next one yourself | 10:40–11:20 | The question: what happened on data the settings were *not* chosen on? If there is no answer, the number on screen is the best of however many tries you didn't see. | The question as a card. | — |
| 9 | AMI + disclaimer | last 15 s | AMI Trade is a simulator: practise making decisions forward in time with a twelve-analyst team, on simulated money. Simulation-only, no edge promised. | AMI end card, disclaimer. | — |

## The one idea

A backtest chosen as the best of many is a measurement of how hard you searched, not of what
happens next.

## What we must not say

- Not "trend following doesn't work", not "optimisation is cheating". The test is of selection without a holdout.
- Not "the winners lost money" — 19 of 23 made money in the holdout. They lost to buy-and-hold on 21.
- The 5× example is post-hoc and must carry that label every time it appears. The pre-registered leverage result is the 10× liquidation count.
- At 10× our as-shown path does **not** look spectacular (it goes through zero on daily bars). Do not imply we reproduced a "$1k → millions" 10× screenshot; we did not.
- Survivorship: all tickers were chosen in 2026. It flatters the winner and buy-and-hold alike; say so once.
- No per-year figure is a forecast. "+1,890 points a year" describes a tuning window and is used only to show shrinkage.

## Description (first 160 characters are the search snippet)

Backtest overfitting tested: we picked the best of 420 strategy settings on 23 markets, then
measured the years it never saw. Average rank afterwards: 54th percentile.

Pre-registered before any code existed. SuperTrend with optional RSI and ADX filters, 420 fixed
combinations, tuned 2005–2018 (BTC 2014–2020), measured 2019–2026 (BTC 2021–2026), costs included.
Plus 420 random strategies per market to show what selection alone produces, and the tuned Bitcoin
winner at 10× margin.

Links: claim folder (pre-registration · code · all 9,660 grid results) · episode page · AMI Trade (UTM).
Disclaimer: educational content; AMI Trade is a simulation-only training product; nothing here is
investment advice. By policy we test claims and name no channel.

## Pinned comment

Pre-registered on 2026-09-17 in commit `3ac320eb`, before any test ran. All three of our
predictions held this time; on other claims in this series they didn't, and those episodes say so.
Every one of the 420 × 23 results is in the repo as CSV — recompute the percentiles yourself.

## Shorts cut-down (≤ 40 s)

"We picked the best of 420 backtests on 23 markets." → dots dropping onto
`winner_holdout_percentiles.png` → "Afterwards the winner ranked 54th out of 100 on average. A coin
flip is 50." Full test on the channel.

## Chart pack (from `out/`)

| Figure | Use | Restyle notes (AMI hex, 16:9, dark) |
|:--|:--|:--|
| `winner_holdout_percentiles.png` | Beat 5, Short | Animate dots in; shade 41.8–66.3 around the 54.5 mean; keep the 50 line. |
| `is_vs_oos_rank_BTC.png` | Beat 5 | Label the axes in plain words: "rank when chosen" / "rank afterwards". Keep the star. |
| `leverage_10x_BTC.png` | Beat 5 | **Redraw on a linear axis from `results.json`** — the log version drops non-positive bars and hides the wipe-outs. Mark the 26 dates. |
| BTC winner curve, tuning + holdout (to draw) | Beats 1, 4 | From `grid_returns_BTC-USD.csv` winner + a re-run of that one configuration; dashed line at 2021-01-01. |
| Tuned vs best-random bars (to draw) | Beat 6 | 23 pairs from `part2_random_placebo`. Log axis is fine here — all values positive. |

## Compliance checklist

- [ ] No creator / channel / title / clip / thumbnail referenced, on screen or spoken
- [ ] No real platform's strategy-tester UI on screen — the mock-up is ours
- [ ] "We tested this claim" language; no *fraud*, *scam*, *liar*
- [ ] Every number traced to `results.json`, with its window and interval
- [ ] Limits stated on camera: daily bars, survivorship, wide interval, 5× is post-hoc
- [ ] No strategy offered in return; ends on method
- [ ] AMI by name; simulation-only; not investment advice
- [ ] EN script flagged for AR / MS translation at v1.0
