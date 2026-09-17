# C02 — "A chatbot wrote me a profitable trading strategy" — PRE-REGISTRATION

Written 2026-09-17, before any C02 code exists and **before any strategy is generated**. Inherits
[`../PREREG_COMMON.md`](../PREREG_COMMON.md).

## The claim, as taught

Give a chatbot a one-line prompt, get a rule-based strategy, paste it into a charting platform's
strategy tester, see a profitable equity curve. Landscape class L2 — 3 videos read, 3.28M views,
≥ 8 videos in the pattern (measured 2026-09-17). Evidence shown: a tester screenshot on one
ticker, no costs, no holdout.

## Design

### Step 1 — generate (after this file is committed)

Ten prompts, fixed verbatim now. P2 and P3 are the prompts shown in the videos; the rest are the
genre's stock phrasing.

1. `Give me a profitable trading strategy for stocks using technical indicators. Provide exact entry and exit rules and parameters.`
2. `Give me an extremely simple long-only trading strategy that uses the 50 SMA.`
3. `Create a strategy to buy when price crosses over VWAP and short when price crosses below VWAP. Use a 30-period VWAP. Sell the long when the position has gained 3%, with a 1% stop loss.`
4. `What is the best indicator combination for a high win rate swing trading strategy? Give exact parameters and rules.`
5. `Give me a mean reversion trading strategy with exact parameters and rules.`
6. `Give me a trend following trading strategy with exact parameters and rules.`
7. `Create a trading strategy using RSI and MACD with exact entry and exit rules.`
8. `I want a trading strategy with at least a 70% win rate. Give me the exact rules.`
9. `Give me a Bitcoin trading strategy with exact rules that would have been profitable.`
10. `Give me a trading strategy using SuperTrend, RSI and ADX. Exact parameters please.`

Generators: three Claude models (Haiku 4.5, Sonnet 5, Opus 5), each a fresh agent that knows
nothing about RES008, its hypothesis, or how the output will be scored. Each answers every prompt
once → **30 strategies**. The answer is then expressed as a Python function
`signal(bars) -> target position in {-1, 0, +1} per bar` using only data up to that bar.

**Disclosed deviation from the videos:** they use ChatGPT; we use the chatbots available to us.
The claim class is "a chatbot wrote it", and we say which ones wrote ours.

Look-ahead gate: every function must pass the truncation test (corrupting bars after date *d*
cannot change positions up to *d*). A failure is returned to its generator once with the error;
a second failure excludes the strategy, and exclusions are counted in the results.

### Step 2 — score

Daily bars. P9 runs on `U-CRYPTO`; all others on `U-EQ`. `next_open`, costs per the common file.
Both `DEFINE` and `HOLDOUT` are reported. We tune nothing, so both are out-of-sample *for us* —
but not for the chatbot, which has read about every year of this data. That contamination runs
**in the claim's favour**, and is stated in the results.

Per strategy:

- **S1 — worth doing?** Fraction of tickers where net total return beats buy-and-hold; pooled
  paired difference in mean daily return vs buy-and-hold with block bootstrap interval.
- **S2 — any skill?** Percentile of the strategy's net total return within its own matched-random
  placebo (500 reps per ticker), pooled as the mean percentile across tickers.
- Trades, win rate, exposure, max drawdown — descriptive.

Also an **as-shown arm**: each strategy on the single best ticker for it in `DEFINE`, gross of
costs, `same_close` — the screenshot a video would have shown — next to the same strategy's
`HOLDOUT` net result across all tickers.

## Our hypothesis

H1: at most 6 of 30 strategies (20%) beat buy-and-hold net on `HOLDOUT` in more than half their
tickers. H2: the median S2 across strategies lies in [35, 65] and at most 3 of 30 sit at or above
the 95th placebo percentile in `HOLDOUT` (1.5 expected by chance). H3: the as-shown arm looks
profitable for ≥ 80% of strategies — i.e. a flattering screenshot is available for almost anything.

## What would support the claim instead

- ≥ 15 of 30 strategies beat buy-and-hold net on `HOLDOUT` in more than half their tickers; **or**
- ≥ 8 of 30 strategies at or above the 95th placebo percentile in **both** windows.

Either → `HOLDS` / `PARTLY HOLDS`. A strategy that individually clears the 95th percentile in both
windows is named in the results and gets its own follow-up, whichever way the aggregate falls.

## Not claimed

Nothing about whether a chatbot is useful for *coding* a strategy a trader already has. The test is
of the claim that the chatbot supplies the edge.
