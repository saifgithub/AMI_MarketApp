# Five questions to ask of any trading claim

The one-pager behind the series. Every episode applies the same five; this page is the lead
magnet, the pinned link, and the seed of an in-app lesson. Each example is a measured result from a
closed RES008 claim — the number, its folder, nothing borrowed.

Written for a viewer who has just watched a video promising an edge and is about to act on it.

---

## 1. Was the test written down before it was run?

If the rules, the markets and the pass mark are chosen *after* looking at the results, the result
is a description of the search, not of the strategy.

> We fixed 420 versions of one strategy in advance, picked the best on 2005–2018, and followed it
> into 2019–2026. It ranked at the **54.5th percentile** of the same 420 afterwards (interval
> 41.8–66.3) — about where a random pick lands. The best of 420 *random* strategies had a better
> backtest than the tuned winner on **23 of 23** markets. — [C03](C03_tune_until_spectacular/RESULTS.md)

**Ask:** where is the version of this that was written before the result existed?

## 2. What happened on data it was not built on?

A backtest on the window you tuned on cannot fail. Only the period after it can.

> On Bitcoin the chosen settings made **+11,889%** over the window they were chosen on, and
> **+104%** over the following five and a half years, when holding the coin made +164%. — [C03](C03_tune_until_spectacular/RESULTS.md)
>
> Asked to pick ten stocks "as of January 2019", chatbots landed at the **94th percentile** of
> random portfolios — and all 30 replies said they already knew what came next. A back-test inside
> a model's training period measures memory. — [C08](C08_chatbot_stock_picks/RESULTS.md)

>
> Thirty strategies written by chatbots: as a screenshot — best ticker, no costs, no benchmark —
> **28 of 29** showed a profit. On the seven and a half years they were not shown on, across 22
> stocks, **0 of 29** beat simply holding. — [C02](C02_chatbot_wrote_my_strategy/RESULTS.md)

**Ask:** which dates were held back, and what happened on them?

## 3. Is the number on screen the whole account, after costs?

Dashboards count what flatters: closed trades, gross of fees, without the position still open.

> A grid bot's own "grid profit" figure was positive in **99.65%** of 9,522 ninety-day runs. The
> account — including the coins it was still holding — was down in **36.80%** of them. With 5×
> margin, **32.54%** of runs were liquidated. — [C06](C06_ai_grid_bot_passive_income/RESULTS.md)
>
> A scalping recipe on 5-minute bars came out at about zero per trade before costs. Ordinary
> costs — 5 to 10 basis points a side — were **half of the trade's entire risk**, every trade.
> — [C05](C05_99pct_scalping_recipe/RESULTS.md)

**Ask:** is that equity including open positions, after fees — and what did it look like through a falling market?

## 4. What would a strategy with no skill have done?

Without a placebo you cannot tell a strategy from its market. Compare with random entries under
the same rules, and with simply holding.

> Two thousand bots that pick stocks at random beat the index in **50.6%** of weeks, by three
> points or more in **14.8%**. The one rule that was disclosed — buy RSI under 30, sell over 70 —
> **won about 8 trades in 10** and still ranked at the **57th–58th percentile** against random
> entries, earning less than buy-and-hold on 19–20 of 22 stocks. — [C07](C07_gave_ai_bot_real_money/RESULTS.md)
>
> Random ten-stock portfolios drawn from *today's* well-known companies "beat the index" in **68%**
> of back-tests — because today's list already knows who survived. — [C08](C08_chatbot_stock_picks/RESULTS.md)
>
> Set a target 1.5 times as far away as the stop and an entry with no information wins about
> **40%** of the time; at 2 times, 33%. A recipe advertised at 99% won **33% to 44%** across 9,363
> trades — within about four points of that arithmetic in every version. — [C05](C05_99pct_scalping_recipe/RESULTS.md)

>
> A neural network's price forecast overlays the real price almost perfectly. So does "tomorrow's
> price = today's" — and on the error score the tutorials quote, that beat the network in
> **90 of 90** runs. — [C01](C01_lstm_predicts_price/RESULTS.md)

**Ask:** what did random entries — and doing nothing — earn over the same period?

## 5. Is it enough results to mean anything?

Small samples of noisy things look like skill about half the time.

> One ten-stock portfolio over one year: the middle 90% of pure-luck outcomes spans about
> **28 points**. Beating the index by 13 happens to one random portfolio in six. — [C08](C08_chatbot_stock_picks/RESULTS.md)
>
> At the measured week-to-week noise, a genuine five-points-a-year edge needs about
> **87 years** of weekly results to stand clear of zero. One winning week is one. — [C07](C07_gave_ai_bot_real_money/RESULTS.md)

>
> 22 wins in 25 trades is "88%" — with a 95% interval from **70% to 96%**. And a win rate alone
> says little even when it is solid: coin-flip entries won **89.2%** of 54,000 trades with a small
> target and a wide stop, and lost money after costs. — [C04](C04_win_rate_proves_edge/RESULTS.md)

**Ask:** how many independent results is this, and how wide is luck over that many?

---

## What this page is not

It is not a strategy and it does not tell you what to buy. Passing all five does not make a
strategy good; failing one means the evidence offered cannot tell you either way. We apply the same
five to ourselves: every test in this series was pre-registered in a public commit, and where our
own predictions failed — they did, in four of the eight claims — the results say so first.

AMI Trade is a simulation-only training product. Nothing here is investment advice.
