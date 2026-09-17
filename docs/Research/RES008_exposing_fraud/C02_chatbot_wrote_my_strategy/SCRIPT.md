# C02 — SCRIPT — We asked three chatbots for 30 strategies

**Episode:** week 3 · **Verdict:** `DISPROVED` · **From:** [`VIDEO_BRIEF.md`](VIDEO_BRIEF.md) · **Numbers:** [`RESULTS.md`](RESULTS.md), [`out/results.json`](out/results.json)
**Length:** 1,281 spoken words = 8 min 32 s of speech at 150 words a minute; with the pauses marked below (charts building in silence), ≈ 9 min 5 s · **Charts:** [`charts/`](charts/)

How to read this file: **VO** is spoken word for word. **SCREEN** is what the editor shows while it
is spoken. **№** lists every number in the beat and where it comes from — if a number is not in
that list, it must not be said. Numbers are written as they should be read aloud.

---

## 1 · Cold open — 0:00

**VO**
ChatGPT trading strategy, tested — that's the search that brought you here, so here is what we
did. Ten one-line prompts, the ones these videos use. Three chatbots — ours are Claude models,
and we'll say which. Thirty strategies, coded by the chatbots themselves. Then twenty-two
stocks and funds, seven and a half years they were never tuned on, costs included. Strategies that beat
simply holding: zero. Strategies that timed their entries better than random: zero. Strategies
we could make look great in a screenshot: twenty-eight out of twenty-nine.

**SCREEN** Chart `05` — the three counters, revealed one at a time: "beat simply holding",
"beat random entries", "look profitable the way a screenshot shows it". No chat interface shown,
no vendor logo.

**№** 10 prompts, 3 chatbots, 30 strategies — `PREREGISTRATION.md` · 22 stocks and ETFs —
`RESULTS.md` header · 7.5 years (2019 to 2026-08) — holdout window, `RESULTS.md` header · beat
buy-and-hold 0 of 29, beat random (≥95th percentile) 0 of 29 — H1/H2, `out/summary.txt` ·
looks-profitable-as-shown 28 of 29 — H3, `out/summary.txt`

## 2 · The stakes — 0:35

**VO**
Here is the video you've probably seen. A chatbot writes a rule. Someone pastes it into a
strategy tester. The equity curve climbs from bottom left to top right, and the video ends there.
Your next step feels obvious: take the same rule, on the same ticker it was shown on, and put
real money behind it.

What that screenshot leaves out is everything a trader would actually want to know. Which other
stocks was the rule tried on. What holding the stock would have done over the same stretch,
without any rule at all. And what the rule does in the years after the screenshot was taken,
once the market it was shown on has moved somewhere else. We built a version of that same
strategy-tester panel — our own mock-up, not a real platform — and used it to hold every one of
those three questions next to the one number a viewer is usually given.

**SCREEN** Our own mock strategy-tester panel, "Net profit" highlighted in the corner, generic
styling, no real platform's chrome or logo.

**№** —

## 3 · What would convince us — 1:38

**VO**
Before a single strategy was generated, we wrote down what would change our minds, and committed
it in public. Two ways the claim could hold. If fifteen or more of thirty strategies beat simply
holding, net of costs, on more than half their stocks, in the years after — the claim holds. Or
if eight or more reach the top five percent against random entries, in both time periods — same
result. We also predicted three things ahead of time: at most six of thirty would beat holding,
the middle strategy would land close to where random entries land, and a flattering screenshot
would be available for almost all of them. You can check the date on that file against the date
on the results.

**SCREEN** Screen-record of `PREREGISTRATION.md` at commit `3ac320eb`; highlight "What would
support the claim instead" and H1–H3; the ten prompts scrolling underneath.

**№** ≥15 of 30 and ≥8 of 30 (claim-support thresholds); H1 "at most 6 of 30"; H2 "median S2 in
[35, 65]" and "at most 3 of 30" — all `PREREGISTRATION.md`

## 4 · The test, as taught — 2:28 (speech 1:02 + 0:08 for the counter to build)

**VO**
Here is the setup, as taught. Ten one-line prompts — the kind these videos use, word for word.
Fresh chatbots, three of them, that know nothing about this test or how it will be scored. Each
one writes its own code from its own answer, so nobody can say we mis-read what it told us.
Thirty strategies in total: ten prompts, three chatbots each.

Now the screenshot, built the way these videos build it: the single best-performing stock out of
twenty-two, no trading costs, no benchmark on the chart. Twenty-eight of twenty-nine strategies
show a profit this way. The one exception is a strategy that never places a single trade.
Best-ticker returns run from thirty-four percent to two thousand three hundred and ninety-eight
percent. Three of those strategies were built for Bitcoin instead of stocks, and on their best
coin they show between one thousand seven hundred fifteen and one thousand seven hundred
ninety-three percent.

**SCREEN** Chart `02a` — the as-shown wall: every strategy on its best ticker, returns labelled,
bars building top to bottom as a counter climbs to 28.

**№** 10 prompts × 3 chatbots = 30 strategies — `PREREGISTRATION.md` · 22 stocks and ETFs —
`RESULTS.md` header · 28 of 29 show a profit (1 never trades) — `RESULTS.md` §4 / H3 · best-ticker range 34% to 2,398%
(0.337–23.977) — `RESULTS.md` §4, `out/results.json` `as_shown.best_ticker_gross_total_return` ·
Bitcoin best-coin range 1,715% to 1,793% (17.149–17.928) — `out/results.json`
`as_shown.best_ticker_gross_total_return` for p09_haiku/opus/sonnet

## 5 · The fair test + reveal — 3:38 (speech 1:27 + 0:15: the grey line lands, then the 578-cell grid)

**VO**
Now add the one line the screenshot leaves out: simply holding that same stock, over the same
stretch. Only ten of those twenty-eight beat it. One strategy shows plus two hundred fifty-three
percent on Amazon. Amazon itself, just sitting there, returned plus three thousand two hundred
seventy-four percent over that same window.

Now the fair test. Every stock, not the best one. The years after, not the years it was shown on.
Costs included. Strategies that beat holding on more than half their stocks: zero of twenty-nine.
Across five hundred seventy-eight strategy-and-stock pairs in total, only thirty-eight won at
all — and every one of those wins landed on three stocks that went nowhere or fell, plus one
coin. A strategy that never places a single trade "beats" the market on two of those same three
stocks, for the same reason every other winner did: it simply wasn't in the market while those
stocks fell.

Then the second, harder question. Not how much a strategy made, but whether its entries showed
any skill at all. Compare each one to five hundred sets of random entries, given the same number
of trades. The middle strategy lands at the fiftieth percentile of that comparison —
tied with a coin flip. Not one of them reaches the ninety-fifth.

**SCREEN** Chart `02b` — the same wall with the grey buy-and-hold bar added to every row. Then
chart `03` — the 578-cell grid, the 38 winning cells lighting up, clustered in three columns.
Then chart `01` — placebo percentiles with the 50 and 95 lines marked.

**№** 10 of 28 beat buy-and-hold on best ticker — `RESULTS.md` §4 · AMZN +253% vs +3,274%
(2.526 vs 32.737) — `out/results.json` `strategies.p01_opus.as_shown` · beat-holding-on-most-tickers
0 of 29 — H1, `out/summary.txt` · 38 of 578 cells (6.6%) — `RESULTS.md` §2 · winning tickers BA,
DIS, PFE, ETH — `RESULTS.md` §2 · never-trades strategy beats buy-and-hold on 2 of those tickers
(BA, PFE) — `out/results.json` `strategies.p10_haiku.HOLDOUT.cells` · median S2 49.7 (50th
percentile) — `RESULTS.md` §3/§6 · 0 of 29 at or above 95th percentile — H2, `out/summary.txt` ·
500 random-entry sets per ticker — `PREREGISTRATION.md` (S2), `RESULTS.md` header · BA −32%, PFE −1%,
DIS +4% in the holdout ("went nowhere or fell") — `RESULTS.md` §2

## 6 · Why — 5:20 (speech 1:04 + 0:05)

**VO**
Why does a chatbot keep handing you the same handful of ideas. Because it has read every trading
book ever written, so it gives you the book back: moving-average filters, RSI pullbacks,
breakouts, MACD, a SuperTrend indicator. All three chatbots answered one of our ten prompts with
the same rule. And one model gave one and the same RSI pullback rule to four different prompts we
asked it. Thirty strategies is not thirty independent tries at an edge.

These rules also sit out of the market most of the time — the typical strategy here was invested
about a quarter of the time — in years when the typical stock returned two hundred forty-eight
percent just for being held. And none of this counts as genuinely unseen data for a chatbot the way it
does for us. It has read about every one of these years already. If contamination changes
anything, it should have made these numbers better, not worse.

**SCREEN** Editor-made text card, not a data chart: the five rule names as they are spoken, each
with its plain-English line from `out/catalogue.md`. No count of "families" on screen — the
catalogue has no family column and we did not classify the rules ourselves (see
`charts/README.md`). Then a card: "in the market 26% of the time" next to "holding: +248%".

**№** rule names — `out/catalogue.md` · prompt 2 answered identically by all three models;
prompts 1, 4, 5, 8 answered with the same RSI(2) rule by one model — `RESULTS.md` §1 deviation
row ("29 strategies are not 29 independent ideas") · exposure 26% (median 0.264) — `VIDEO_BRIEF.md`
beat-6 source line, `out/results.json` per-strategy `HOLDOUT.pooled.exposure_median` · median
buy-and-hold return 248% (2.483) — `out/results.json` (median of `buy_hold_net_total_return`
across cells; same figure the brief cites for beat 6)

## 7 · What is true — 6:29

**VO**
Here is what's true about the chatbots themselves, and it's worth saying plainly. Twenty-six of
thirty functions ran correctly the first time we tried them, and not one of them looked into the
future to cheat. On the whole they were also more careful than the claim made about them:
twenty-five of thirty replies promised no win rate and no return at all, and several opened by
refusing to promise a profit before giving any rule.

Two of them didn't refuse. Asked for a strategy with at least a seventy percent win rate, both
gave the same textbook pullback rule, and both pointed to published backtests: one said roughly
seventy to eighty percent, the other said often seventy percent or higher. Run for real, on the
years after: sixty-six percent for one, sixty-three point five for the other. Close to what they
claimed. Behind those percentages: seven hundred ninety-five wins out of one thousand two hundred
four trades for the first, two thousand two hundred thirty-four out of three thousand five
hundred nineteen for the second.

Now look at what those wins were actually worth. Eighteen percent and forty-one percent, on the
typical stock, over that same window. Holding the stock, doing nothing at all, made two hundred
forty-eight. A high win rate and a small share of the return, side by side — we go through the
arithmetic behind that gap in another test in this series.

**SCREEN** Quotes from the two replies on screen (ours, stored in the repo, shown verbatim). Then
a card: "66.0% win rate · +18% · holding +248%" and "63.5% win rate · +41% · holding +248%", the
second linking to the win-rate episode.

**№** 26 of 30 ran first time, 3 repaired, 1 excluded — `out/gate_results.json` counts_by_model ·
none looked ahead (look-ahead gate) — `RESULTS.md` §1 · 25 of 30 promised no win rate/return —
`RESULTS.md` §5 (also `out/catalogue.md`) · win rates 66.0% (795 of 1,204 trades) and 63.5%
(2,234 of 3,519) — `RESULTS.md` §5 · median net returns +18% and +41% against holding's +248% —
`RESULTS.md` §5

## 8 · Check the next one yourself — 8:04

**VO**
So: three questions for the next chatbot strategy a video shows you. Which other stocks was it
tried on, not just the one on screen. What did simply holding do, over that same stretch, with no
rule at all. And what happened in the years after the screenshot was taken, once the market had
moved on. A video that can't answer those three isn't showing you a strategy. It's showing you
one lucky stretch, on one lucky stock, dressed up as a method.

**SCREEN** The three questions as a card, one at a time.

**№** —

## 9 · AMI + disclaimer — 8:37 — ends 9:05

**VO**
AMI Trade is a simulator. You direct a team of twelve analysts, on simulated money, and the
record of every decision is kept for you. It is simulation-only, and it promises no edge. The
test, the code and every number from this video are in the description. This video is
educational content. Nothing in it is investment advice.

**SCREEN** AMI end card. Disclaimer card: "Educational content. AMI Trade is a simulation-only
training product. Nothing here is investment advice."

**№** —

---

## Production notes

- **Do not say** (from the brief): "ChatGPT" as the thing we tested — the hook names the search
  term only, then names our own models · "AI can't trade" / "chatbots are useless" · "these
  strategies lose money" (most made money; they made less than holding) · "0 of 30" (say "29
  scored") · anything implying the 29 strategies are 29 independent trials · anything on
  risk-adjusted returns, drawdowns, or implying holding is "safer" for a given viewer · anything
  about the other vendor's chatbot specifically.
- Beat 9's AMI line uses the exemplar's general wording, not the brief's "benchmark always on
  screen" line — the brief flags that line as unverified against the shipped app. Check it against
  the shipped app before using the more specific version in a future cut.
- `as_shown_vs_holdout.png` is not used or cued anywhere, per the brief (it plots returns relative
  to buy-and-hold and points the wrong way for this story).
- No creator, channel, title, clip, thumbnail, or real charting/trading platform is referenced
  anywhere. The mock strategy-tester panel in beat 2 is ours and must not resemble a real one.
- The two quoted replies in beat 7 are stored verbatim in `out/generated/p08_opus.json` and
  `out/generated/p08_sonnet.json`; no reply from any video is shown or quoted.
- The opening clause of beat 1 uses the genre's search phrase, which contains another vendor's
  product name. It is the brief's hook verbatim and goes with title option 1. Title choice is an
  open decision (the founder's); if option 2 or 3 is chosen, replace the clause with "A chatbot trading
  strategy, tested —" and re-record nothing else.
- EN script — flag for AR / MS translation at v1.0.
