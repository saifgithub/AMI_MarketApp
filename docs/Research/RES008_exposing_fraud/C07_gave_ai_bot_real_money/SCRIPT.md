# C07 — SCRIPT — I gave an AI bot real money and it beat the market

**Episode:** week 2 · **Verdict:** `DISPROVED` · **From:** [`VIDEO_BRIEF.md`](VIDEO_BRIEF.md) · **Numbers:** [`RESULTS.md`](RESULTS.md), [`out/results_part1.json`](out/results_part1.json), [`out/results_part2.json`](out/results_part2.json)
**Length:** 1,155 spoken words = 7 min 42 s of speech at 150 words a minute; with the pauses marked below (charts building in silence), ≈ 8 min 33 s · **Charts:** [`charts/`](charts/)

How to read this file: **VO** is spoken word for word. **SCREEN** is what the editor shows while it
is spoken. **№** lists every number in the beat and where it comes from — if a number is not in
that list, it must not be said. Numbers are written as they should be read aloud.

---

## 1 · Cold open — 0:00

**VO**
AI trading bot, tested with real money: it runs for a week, it beats the market, and videos
making that claim have been watched more than six million times. We tested that a different way. We built two thousand bots that have no
skill at all — they pick stocks at random — and ran every week since 2005. In any given week,
half of them beat the market. One in seven beat it by three points. So what did that winning
week tell you?

**SCREEN** Editor-made motion graphic, not a data chart: a grid of two thousand small bot tiles,
about half flipping green each week as a calendar runs from 2005. On "half of them", cut to chart
`01` (the one-week histogram, 50.6% and 14.8% on screen). The brief's "2,000 equity lines" figure
was cut in review — see `charts/README.md`.

**№** more than six million views, across the videos making this claim — `TRACKER.md` reach (6.12M, 2 videos, measured 2026-09-17) · 2,000 bots, since 2005 —
`results_part2.json meta.n_bots`, `meta.start` · half beat the market — `zero_skill_bot.week_vs_spy.share_beats_spy`
50.6% · one in seven by three points — `share_beats_spy_by_3pt` 14.8%

## 2 · The stakes — 0:34

**VO**
After a video like that, the reasonable move is to rent the bot, or copy the rule, and size it
the way the video did — most of the account, on one trade. The video showed you one week. It
did not show you what one week is worth.

**SCREEN** Our own mock panel — "Bot P&L: +4.1% this week" in generic styling. No real interface,
no name, no logo. Panel fades to a blank question mark over a calendar showing one week
highlighted out of many.

**№** — (illustrative mock panel only; no number spoken)

## 3 · What would convince us — 0:54

**VO**
Before we ran anything, we wrote down what would change our minds, and committed it in public.
Two thresholds. If a bot with zero skill beat the index in fewer than one week in four, a
winning week would mean something on its own. And for the one rule we could actually test — the
one that was disclosed — if its entries beat ninety-five percent of random entries, in two
separate periods, that is real timing, and we would say so. We also wrote down four predictions
before seeing a single result. The disclosed rule would not beat buy-and-hold on most stocks. The
zero-skill bot would beat the index in somewhere between four and six weeks out of ten. In a
trending month, that same bot would win most of its trades by luck alone. And the track record
needed to prove a real edge would run well past three years. You can check the date on that file
against the date on the results.

**SCREEN** Screen-record of `PREREGISTRATION.md` at commit `3ac320eb`; highlight "What would
support the claim instead" and H1–H4.

**№** under 1-in-4 threshold, 95th-percentile threshold — `PREREGISTRATION.md` "What would support
the claim instead" · H1–H4 — `PREREGISTRATION.md` "Our hypothesis" / RESULTS §4

## 4 · The test, as taught — 2:00 (speech 1:02 + 0:09 for the trade list to scroll)

**VO**
The disclosed rule: an indicator called RSI. Buy when it drops under thirty, sell when it rises
above seventy. Long or flat, never short — no bet against the market, ever. We ran it on
twenty-two large stocks, next trading day's open, a small cost on every trade, over two windows:
2005 to 2018, and 2019 to this August. We also ran it on hourly bars over the last two years, to
check whether a faster clock changed the picture.

And on the daily charts, it looks wonderful. Two hundred twenty-seven wins out of two hundred
eighty-four trades in the first window. One hundred eighteen out of one hundred fifty-five in
the second. On one stock — Tesla, in the earlier window — nine trades out of nine. On another —
Apple, in the later one — nine out of nine again. That is the kind of number a video puts on
screen and moves on.

**SCREEN** Trade list scrolling, green ticks, on-screen stamp reading "derived, not
pre-registered" for as long as the win-rate figures are shown. Counter: "227 wins of 284."

**№** RSI(14), buy <30 / sell >70, 22 stocks, next-open, 2005–2018 and 2019–2026, plus 60-minute
bars ≈730 days — `results_part1.json meta` · 227/284 (DEFINE), 118/155 (HOLDOUT) —
`derived_extras.json rsi_rule_pooled_trades` · TSLA 9 of 9 (DEFINE), AAPL 9 of 9 (HOLDOUT) —
`derived_extras.json rsi_rule_pooled_trades.*.tickers_with_100pct_win_rate` (on-screen stamp:
"derived after the run")

## 5 · The fair test + reveal — 3:11 (speech 1:44 + 0:20: each comparison lands, then a beat of
silence before the bot-luck numbers)

**VO**
Two comparisons the videos do not make.

First, against simply holding the stock. The rule earned less than buy-and-hold on nineteen of
those twenty-two stocks in the first window, and twenty of twenty-two in the second. The Tesla
trade record — nine for nine — returned three hundred ninety-eight percent. Holding Tesla over
the same stretch returned one thousand one hundred ninety. The Apple record, also nine for nine,
returned two hundred forty-seven percent. Holding Apple returned eight hundred thirty-six. A
perfect win rate and a fraction of the return, in the same trade.

Second, against random entries with the same number of trades and the same holding times. The
rule's entries land at the fifty-seventh percentile in one window, fifty-eighth in the other.
Fiftieth is what no timing skill looks like. Ninety-fifth is where we said we would call it
real timing. The ranges around fifty-seven and fifty-eight come down to fifty, and stop in the
sixties.

Now the zero-skill bots on their own. Over a week, the gap between one of them and the index
stays inside about five points either way, nine times out of ten. Four winning weeks in a row —
about one month of a good run — happens to a bot with no skill roughly one time in sixteen. Run
the same two thousand bots for twenty-one years each, and the luckiest one beats the index in
fifty-four percent of its weeks. The unluckiest, forty-seven. That gap is what luck alone does
to bots that all have exactly the same, zero, amount of skill.

**SCREEN** Charts `03` then `04` — rule vs buy-and-hold per ticker, one window each; the editor
highlights TSLA on `03` and AAPL on `04`. Then chart `05` — the rule's placebo percentile at 57
and 58 with its ranges, the 50 line and the 95th-percentile band. Then chart `01` — the weekly
excess-return histogram.

**№** 19/22, 20/22 beat by buy-and-hold — `results_part1.json DEFINE/HOLDOUT.pooled.n_tickers_beat_buy_hold_net`
(22 minus 3, 22 minus 2) · TSLA net +398% vs buy-hold +1,190% — `derived_extras.json` TSLA row
(3.9824 → 398%, 11.897 → 1,190%) · AAPL net +247% vs buy-hold +836% — `derived_extras.json` AAPL
row (2.4673 → 247%, 8.3618 → 836%) · placebo percentile 57 (DEFINE), 58 (HOLDOUT), both intervals
come down to 50 and stop in the sixties — `results_part1.json mean_placebo_percentile` (DEFINE 48–68, HOLDOUT 50–66) · 95th-percentile bar — `PREREGISTRATION.md` · middle 90% of weekly
excess return ±5 points — `results_part2.json zero_skill_bot.week_excess_percentiles` (p5 −4.98%,
p95 +5.27%) · four-in-a-row 1 in 16 (6.2%) — `derived_extras.json share_of_4_consecutive_non_overlapping_weeks_all_beating_spy`
· luckiest bot 54% of weeks, unluckiest 47% — `derived_extras.json per_bot_share_of_weeks_beating_spy`
(max 0.5405, min 0.4727) · twenty-one years — `results_part2.json meta.start` / `meta.end` (2005-01-03 → 2026-08-31)

## 6 · Why — 5:15 (speech 1:12 + 0:10 on the arithmetic building)

**VO**
Here is why a week cannot tell a skilled bot from a lucky one.

A week of one bot's trades is a handful of bets on volatile stocks. By chance alone, the gap
between that bot and the index swings by about three and a quarter points a week. An edge worth
having — five points of extra return a year — works out to roughly a tenth of a point a week.
The signal you are hoping to see is more than thirty times smaller than the noise sitting on
top of it.

To see a tenth of a point standing clear of that noise, at the volatility we measured, takes
roughly four thousand five hundred weeks of results. That is about eighty-seven years. Measured
in months instead of weeks, the answer does not improve much: about nine hundred sixty-six
months, which is roughly eighty years. One good week is not evidence of an edge. It is what the
noise does, on its own, to a bot that has no edge at all — most weeks, for most bots.

**SCREEN** The arithmetic, one line at a time: measured weekly swing (3.24 points) → target edge
per week (0.1 point) → weeks needed (4,549) → years (87).

**№** weekly sigma 3.24 points — `results_part2.json sample_size_arithmetic.weekly.sigma` (0.03243)
· +5 points a year ≈ 0.1 point a week — `sample_size_arithmetic.weekly.mu_per_period` (0.00096) ·
4,549 weeks / 87 years — `sample_size_arithmetic.weekly.n_periods/n_years` · 966 months / 80 years
— `sample_size_arithmetic.monthly.n_periods/n_years` · "more than thirty times" — sigma ÷ mu_per_period =
0.03243 ÷ 0.00096 = 33.7

## 7 · What is true — 6:37 (speech 1:06)

**VO**
This cuts both ways. A losing week proves nothing either. And nothing here says the bots in
those videos are bad. Their logic is not public, so nobody can check it — including us. We are
not testing them. We are testing what one week can show about any bot.

One more thing worth knowing. The months that look best on a channel are, on average, months
where the market did the work. When the ten stocks we used were up strongly over a month, a
random long-only bot won about six trades in ten. Under ordinary conditions, it won about five
in ten. Being in a rising market and having skill are two different claims. A single good month
does not tell you which one you are looking at.

And we are assuming every one of those weeks happened exactly as shown. We did not verify a
single video's trade log, because none of the videos this claim is drawn from published one.

**SCREEN** Chart `02` — two bars, no error bars, our pre-registered 60% line, and its stamp
("prediction met narrowly") on screen for as long as the chart is. Caption: "trending = the
ten-stock basket up 8% or more over 21 trading days · 8.8% of windows".

**№** trending month win rate 60.9% vs 52.7% unconditional — `results_part2.json trending_month_conditional.trend_trade_win_rate/unconditional_trade_win_rate` · "over a month" = 21 trading days — `meta.month_window`
(spoken as "about six in ten" / "about five in ten" per brief's precision caveat — printed
intervals are far too narrow, RESULTS §1)

## 8 · Check the next one yourself — 7:43

**VO**
One question for the next trading-bot result you are shown. How many independent periods is
this — not trades, periods — and what would a bot with zero skill have done over those same
periods? One winning week is one period. It is one coin landing heads.

**SCREEN** The question as a card.

**№** —

## 9 · AMI + disclaimer — 8:02 (speech 0:19 + 0:12 end card) — ends 8:33

**VO**
AMI Trade is a simulator. You direct a team of twelve analysts, on simulated money, and the
record of every decision is kept for you. It is simulation-only, and it promises no edge. The
test, the code and every number from this video are in the description.

**SCREEN** AMI end card. Disclaimer card: "Educational content. AMI Trade is a simulation-only
training product. Nothing here is investment advice."

**№** —

---

## Production notes

- **Do not say** (from the brief): anything about a specific bot or product by name; that any
  video's results were faked or cherry-picked; "RSI doesn't work" as a general claim (this is one
  rule, long/flat, 22 large stocks); any Wilson-interval trade-win-rate figure as precise (quote
  "about six in ten" / "about five in ten" only — printed intervals are far too narrow, correlated
  trades, RESULTS §1); no claim that eighty-seven years is exact — it is two-standard-error
  arithmetic at the measured volatility, not a guarantee.
- Beat 4's win-rate figures (227/284, 118/155, the two 9-of-9 records) are derived from per-ticker
  rows after the run — true and traceable, but not pre-registered. The on-screen stamp must stay
  up for as long as those figures are.
- Beat 5's four-in-a-row and luckiest/unluckiest-bot figures are also derived, descriptive
  read-outs (`derived_extras.json`), not part of the pre-registered verdict; they are spoken
  because they are correctly sourced and consistent with H2, not because they carry extra weight.
- Beat 9's AMI line describes the product in general terms on purpose. If a more specific line is
  wanted, check it against the shipped app first.
- No creator, channel, title, clip, or thumbnail is referenced anywhere. The mock panel in beat 2
  and the bot-tile grid in beat 1 are ours and must not resemble a real interface.
- EN script — flag for AR / MS translation at v1.0.
