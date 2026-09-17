# 00 — The claim landscape: what "AI trading edge" means on YouTube

Surveyed 2026-09-17. All reach figures are view counts **as measured that day** by `yt-dlp`; they
are a floor for each claim class (videos we read), not a census.

**Method.** 45 search queries across three themes (chatbot-as-strategist · ML prediction and "AI"
indicators · AI bots and automation), 25 results each → roughly 880 unique videos after
de-duplication within themes. Shorts and sub-50k-view videos dropped unless recent. 38 videos
were read in full from transcript, metadata first (who publishes it and what they sell). No
channel, title or link appears in this file — provenance is in the git-ignored `_internal/`.

---

## Three findings before any test is run

**1. The claim lives in the title; the refutation is often in the video.** In 16 of the 38 videos
we read, the body undercuts the headline. A "99% win rate" title whose own on-camera backtest
comes out at 55%. A "$1,000 into $17.4M" thumbnail narrated by a creator who says, in so many
words, that he is demonstrating over-optimisation. A "best forex robots" video that shows its
own grid robot taking an account from $3,000 to ~$115,000 and then to zero. An "AI made me as
much money as possible" video that ran the prompt nine times and beat the index zero times.
Viewers who stop at the thumbnail take away the opposite of what the creator found. This is the
strongest reason the channel should attack *claims* and leave creators alone: several of them
already agree with us.

**2. "AI" is mostly a label.** The highest-reach "AI bot" video we found uses no model of any
kind — it is a rules indicator on a retail platform. The highest-reach "AI indicator" result is
two classical indicators (an ATR trailing stop and a stochastic of MACD). Where a chatbot is
involved, it typically writes or edits a static rule set once; nothing learns or adapts at
run time. Testing these claims is therefore mostly testing ordinary technical rules.

**3. The evidence offered is a screenshot.** Across the 38: no out-of-sample test except in the
handful of honest tutorials; no transaction costs in any strategy-tester result; sample sizes of
2, 7–12, 25, 47 trades behind headline win rates; windows of one week or one month for
"gave it real money" tests; leverage (6×, 10×) inflating percentage results without being
carried into the title. Something is for sale in almost every case — course, paid indicator,
bot licence, broker or exchange affiliate, prop-firm discount code.

---

## Claim classes

Reach = videos we read in that class and their combined views. `→` points at the tracker row.

| # | Claim class | Reach (read, measured 2026-09-17) | Evidence typically shown | Testable with free data? | → |
|:--|:--|:--|:--|:--|:--|
| L1 | A neural network (LSTM) trained on past closes **predicts tomorrow's price**; the predicted-vs-actual chart overlays almost perfectly | 2 videos · 1.95M (several more unread) | Overlay chart + RMSE on price level. No baseline, no trading rule, scaler fit on the whole series (one creator's own description now admits the leak) | High — recipe fully specified | C01 |
| L2 | **A chatbot wrote me a profitable strategy** from a one-line prompt | 3 videos · 3.28M (≥ 8 in pattern) | Strategy-tester screenshot on the tuning window. No costs, no holdout | High | C02 |
| L3 | **Keep tweaking until the backtest is spectacular** — filters, thresholds, position size, 10× margin ("$1k → $17.4M") | within L2; also a paid toolkit tuned on its own 2-year window (74% / 156 trades) and a chatbot-coded prop-firm bot judged on 7–12 trades | Same-window optimisation, narrated live | High | C03 |
| L4 | **A 90–99% win rate** proves the strategy works | 4 videos · 2.99M | Two hand-picked chart examples; or 25 trades; or a bare assertion | High | C04 |
| L5 | A specific **"99% win rate" scalping recipe** (ATR-trailing-stop alerts + Schaff trend cycle, fixed R target) | 2 videos · 2.17M | None / 100 manual setups that came out at 55% | High for mechanics; 5-minute history is short on free data | C05 |
| L6 | An **"AI" grid / DCA / mean-reversion robot** earns passive income in any market | 3 videos · 0.92M (dozens more in search results) | Dashboard screenshots, no numbers; or a live account shown blowing up | High for the disclosed mechanisms; closed products untestable | C06 |
| L7 | **"I gave an AI bot real money"** and it beat the market in a week / a month | 2 videos · 6.12M | One account, one run, 5 trading days or 1 month, no costs, broker sponsor | High for the disclosed RSI rule; the proprietary one is untestable | C07 |
| L8 | **A chatbot's 10 stock picks beat the index** (one prompt, one run, one year); "AI made me as much money as possible" | 2 videos · 2.76M | One portfolio per chatbot, raw return vs an index ETF | High for the statistics of the claim; forward skill is not testable on past data (hindsight) | C08 |
| L9 | An **ML "AI indicator"** (nearest-neighbour classifier on RSI / WaveTrend / CCI / ADX; k-means SuperTrend) has a 57–95% win rate | 5 videos · 1.04M | The indicator's own on-chart win-rate table (a 4-bars-forward heuristic, called unreliable by a reviewer who promotes it); "over 75%" asserted with no evidence; one promo shows 6 of 8 signals losing | Medium — open-source core is re-implementable; closed variants are not | B01 |
| L10 | **Reinforcement-learning agent** learns a profitable policy | 1 video · 0.30M | In-sample curve up, out-of-sample flat — the creator says so | High, but the creator already refuted it; see also RES001 part 01 | B02 |
| L11 | **Chatbot reads news headlines** → "beat analysts by 512%" | 2 videos · 0.10M (heavily re-cited) | A working paper's headline number, repeated without its cost sensitivity | Low — needs a timestamped headline feed | B03 |
| L12 | **Upload a chart screenshot**, get the trade | 1 read · 0.02M (a 0.9M video unread) | None | Different kind of test (consistency, not P&L) | B04 |
| L13 | **Chatbot-vs-chatbot live trading contests** | 0 read (captions unavailable) · 0.29M spotted | Leaderboard over a few weeks | Desk review only; P06 applies | B05 |
| L14 | Chatbot gives **qualitative day-trading rules**, a human executes | 2 videos · 0.41M | 2 days at 6× leverage; or 2 trades | Low — discretionary | B06 |
| L15 | Bot with **undisclosed logic** sold as "AI arbitrage" / forex robot (licence $249 – $4,500) | 2 videos · 0.64M | Dashboard or account screenshots | None — unfalsifiable as presented | B07 |

## What looked sound — and we say so

Reported so the channel never implies the whole space is dishonest.

- A data-science tutorial (0.85M views) predicts **direction**, warns against cross-validation on
  time series, runs an expanding-window backtest against the base rate, gets a modest result, and
  ends: *would I trade this? No.*
- An LSTM tutorial (0.15M) demonstrates that predicting the next **price** yields a chart that is
  "nothing but the price curve delayed by one candle". That is exactly C01's hypothesis, stated by
  someone who sells ML trading courses.
- Another LSTM tutorial (0.22M) shows its own model cannot extrapolate and says predicting stocks
  is "incredibly difficult".
- A widely watched explainer (0.59M) takes the 512% headline-sentiment study apart: the figure
  ignores costs, leans on illiquid micro-caps, is not peer reviewed, and **newer models did worse**.
- An experienced day trader (0.24M + 0.13M) states on camera that the chatbot's rules did not make
  the money — his own discretion did — and, separately, ran three paid alert services for a week
  and reported that none made money.
- A simulation video (1.08M) shows classic chart patterns emerging from purely random order flow.

## Selection for the first batch

C01–C08 were picked on **reach × testability**: each has a recipe specified tightly enough to
reproduce, free data that covers it, and an audience in the millions or high hundreds of
thousands. B01–B07 are recorded in the tracker so they are not rediscovered from scratch.
