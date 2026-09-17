# C03 — SCRIPT — We picked the best of 420 backtests. Then time passed.

**Episode:** week 4 · **Verdict:** `DISPROVED` · **From:** [`VIDEO_BRIEF.md`](VIDEO_BRIEF.md) · **Numbers:** [`RESULTS.md`](RESULTS.md), [`out/results.json`](out/results.json)
**Length:** 1,329 spoken words = 8 min 52 s of speech at 150 words a minute; with the pauses marked below (charts building in silence), ≈ 10 min 39 s · **Charts:** [`charts/`](charts/)

How to read this file: **VO** is spoken word for word. **SCREEN** is what the editor shows while it
is spoken. **№** lists every number in the beat and where it comes from — if a number is not in
that list, it must not be said. Numbers are written as they should be read aloud.

---

## 1 · Cold open — 0:00

**VO**
Backtest overfitting, tested. You've seen the move: take a strategy, tweak the settings, watch the
equity curve, keep the version that looks best — a thousand dollars into millions. We did exactly
that, four hundred and twenty versions, twenty-three markets. On Bitcoin the winner made eleven
thousand eight hundred percent. Then we let time pass. Over the next five and a half years the same
settings made a hundred and four — less than just holding the coin.

**SCREEN** The BTC winner's curve building from a $1 start through the tuning window, then the
holdout years appended on the same axis (`04` — milestones only, dashed at 2021-01-01).

**№** 420 versions — `grid_size` · 23 markets — `n_instruments` · BTC tuning-window return
+11,889% (spoken "eleven thousand eight hundred percent") — `per_instrument["BTC-USD"].winner_tune_return`
· holdout return +104% — `winner_holdout_return` · buy-and-hold same window +164% — `holdout_buy_hold_return`
· five and a half years — `per_instrument["BTC-USD"].holdout_window` (2021-01-01 → 2026-08-31)

## 2 · The stakes — 0:31

**VO**
"Best of four hundred and twenty" sounds like effort, and it is. It is also a filter. Try enough
settings and something on the far right of the distribution is guaranteed to look spectacular,
whether or not it means anything. If you believe the backtest is the strategy, the reasonable next
step is to trade those exact settings, often on margin, because the screenshot made margin look
safe. What the screenshot doesn't show you is the one number that matters: what those settings did
on days they were never shown.

**SCREEN** A strategy-tester panel we drew ourselves — generic styling, no real vendor's UI —
"Net profit" field highlighted, "Holdout" field left blank.

**№** — (no new numbers this beat)

## 3 · What would convince us — 1:07 (speech 0:38 + 0:05 for the file highlight)

**VO**
Before we ran anything, we wrote down what would change our minds, and committed it in public. If
picking the best backtest works, the winner should stay near the top afterward: seventy-fifth
percentile or better on average, with a range that doesn't include the middle, and it should beat
buying and holding on most markets. That's what would support the claim. We also predicted where
it would actually land: below the sixty-fifth percentile, with a range that does include the
middle. You can check the date on that file against the date on the results.

**SCREEN** Screen-record of `PREREGISTRATION.md` at commit `3ac320eb`; highlight the 75th-percentile
support condition and the H1 prediction line.

**№** 75th percentile threshold, below-65 prediction (H1) — `PREREGISTRATION.md`

## 4 · The test, as taught — 1:50 (speech 0:44 + 0:15 for the grid wall to build)

**VO**
We built the same family of rule the tuning videos use. A trend line that flips long or flat, an
optional filter on momentum, an optional filter on trend strength. Every combination of settings
fixed in advance, before a single backtest ran: four hundred and twenty of them. Run all four
hundred and twenty on the tuning window, rank them by return, crown the winner. That is exactly
what happens on camera in these videos, nothing hidden. Twenty-three markets: twenty-two large stocks
and funds, and Bitcoin. On Apple the winning settings made two thousand one hundred and thirty-five
percent over the tuning window. On Bitcoin, eleven thousand eight hundred and eighty-nine.

**SCREEN** Editor-built from `out/grid_returns_BTC-USD.csv`: a wall of 420 tiles, one per setting,
each showing that setting's tuning-window return; they sort by return and the winner lights up.
Tiles with numbers, not curves — no per-setting equity curve was saved, so none is drawn.

**№** 420 combinations, 23 markets — `grid_size`, `n_instruments` · AAPL tuning-window return
+2,135% — `per_instrument["AAPL"].winner_tune_return` · BTC tuning-window return +11,889% —
`per_instrument["BTC-USD"].winner_tune_return`

## 5 · The fair test and the reveal — 2:49 (speech 1:29 + 0:30: dots dropping, the scatter, the 21/23 tally)

**VO**
Now the years the winner never saw. Stocks and funds were tuned on data through 2018 and measured
from 2019 to August 2026. Bitcoin was tuned through 2020 and measured from 2021 to August 2026.

If picking the best backtest told you nothing about what comes next, the winner should land, on
average, at the fiftieth percentile of that same four hundred and twenty — a coin flip. Across our
twenty-three markets, the winner landed at fifty-four point five, on average. The range runs from
forty-two to sixty-six. Seven winners stayed in the top fifth afterward. Four fell to the bottom
fifth. Which group any one winner joins, you cannot tell from the tuning window alone.

Here is the harder number. On twenty-one of twenty-three markets, the chosen winner then earned
less than simply buying and holding that same market. Not less than the best setting — less than
doing nothing.

And Bitcoin, the instrument in the hook: the winning settings returned eleven thousand eight
hundred and eighty-nine percent while being chosen. Over the next five and a half years, one
hundred and four percent. Buying and holding Bitcoin over those same years returned one hundred and
sixty-four. Among the four hundred and twenty, the chosen winner's holdout percentile was
sixty-six: ahead of about two thirds of them, and still behind holding.

**SCREEN** Chart `01` — dots dropping in one at a time, the 50 line, the 41.8–66.3 band shading
around the 54.5 mean. Then chart `02` — the BTC scatter of tuning rank vs holdout rank, a cloud
not a line, the winner's star landing away from the diagonal.

**№** mean holdout percentile (T1) 54.5, interval 41.8–66.3 — `pooled.mean_T1`,
`mean_T1_ci_lower`, `mean_T1_ci_upper` · 7 of 23 at or above the 80th percentile, 4 of 23 at or
below the 20th — RESULTS §2 table · 21 of 23 below buy-and-hold (T3) —
`pooled.n_instruments_T3_negative` · BTC tuning +11,889%, holdout +104%, buy-and-hold +164%,
holdout percentile 65.7 — `per_instrument["BTC-USD"]` (`winner_tune_return`,
`winner_holdout_return`, `holdout_buy_hold_return`, `T1_holdout_percentile`)

## 6 · Why — 4:48 (speech 1:23 + 0:15 for the paired bars to build)

**VO**
Here is why. Try four hundred and twenty of anything on a window of history, and the best one will
look brilliant — partly because it may fit something real, and partly because that window has its
own noise, and the best-of-many search finds whichever setting happened to line up with it. The
backtest cannot tell you which part is skill and which part is luck, because it only ever looked at
one path.

Here's the proof. On each market's own tuning window, we also ran four hundred and twenty
strategies that enter and exit at random — no trend line, no filter, matched only to trade about as
often, and be in the market about as much, as the real settings were. The best of those four hundred and twenty random strategies beat
the tuned winner's own backtest. On all twenty-three markets. On Apple: the random winner made
three thousand eight hundred and sixty-six percent against the tuned winner's two thousand one
hundred and thirty-five. On Bitcoin: thirteen thousand five hundred and seven against eleven
thousand eight hundred and eighty-nine. Picking the best of many is not a skill the tuned rule has
and randomness doesn't. It is what picking the best of many does, to anything.

**SCREEN** Chart `05` — 23 paired bars, tuned winner vs best-of-420 random, log axis, all 23 pairs
visible with the random bar reaching further every time.

**№** best random beat tuned winner on 23 of 23 markets — `part2_random_placebo` across
`per_instrument` · AAPL +3,866% vs +2,135% — `best_random_tune_return` vs `winner_tune_return`
(AAPL), ×100 for percent, matches RESULTS §3 · BTC +13,507% vs +11,889% — `best_random_tune_return`
vs `winner_tune_return` (BTC-USD), matches RESULTS §3

## 7 · The margin nobody liquidates — 6:26 (speech 1:22 + 0:20 for the liquidation dates ticking)

**VO**
One more piece, because it's the part that gets skipped: margin. Take the Bitcoin winner and trade
it at ten times leverage, the way these videos often show it. We measure this on daily bars, one
close and one low a day — an intraday version would liquidate on different days, though not a
different direction. A position is wiped out the day the market moves ten percent against it.
Inside the very window that produced the winning settings, that happened twenty-six times. In the
years afterward, fourteen more times. At ten times leverage, on those daily bars, the path that
ignores those wipeouts doesn't even look spectacular — it runs straight through zero.

Here's a number we did not plan to report, so we're labelling it exactly that: not pre-registered.
At five times leverage instead of ten, the path that ignores liquidation turns one thousand dollars
into six point one nine million. It also contains one day where the market moved twenty percent
against the position — at five times leverage, the whole account — in January 2017, when that
account stood at two point six times its starting size. A backtest with no liquidation rule prints the six million. A broker prints
zero.

**SCREEN** Chart `03` — the 10× linear-axis rebuild, tuning and holdout side by side, liquidation
dates ticking in as red vertical lines. Then chart `06` — the 5× path, its "after the fact — not
pre-registered" stamp on screen for as long as it is shown, with the 2017-01-05 marker.

**№** 10× liquidation events: 26 in tuning, 14 in holdout —
`part3_btc_leverage.tuning.leverage_10x.n_liquidation_events`, `.holdout...` · 5× final equity
multiple 6,186.9× ($1,000 → $6.19M), 1 liquidation event, 2017-01-05, account at 2.6× its start at
that point — `leverage_5x_extra_not_preregistered.as_shown_final_equity_multiple`, RESULTS §4 · 20%
adverse move at 5× — `leverage_5x_extra_not_preregistered.adverse_threshold` (0.2) · 10% at 10× —
`leverage_10x.adverse_threshold` (0.1) ·
daily-bars limit (no new number) — RESULTS §6 ("Daily bars. An intraday version with stops would
liquidate differently; the direction of the leverage finding does not depend on it, the counts do")

## 8 · What is true — 8:08 (speech 1:32 + 0:10 on the cards)

**VO**
A few things this test does not say. It doesn't say trend following is worthless, or that
searching for good settings is cheating. Testing many settings and holding some data back to check
the survivor is ordinary, careful practice. What we tested is choosing the best backtest with
nothing held back at all.

It doesn't say the winners lost money. Most of them didn't: nineteen of twenty-three were still
positive in the holdout. The market was rising and they were long. They simply made less than
doing nothing — after all that searching for the best possible setting. And every one of our
twenty-three markets was chosen in 2026, meaning every one of them survived to today. That flatters
the tuned winner and buying and holding equally, so it doesn't change which one wins the
comparison — but it means neither side in this video represents a company or a coin that could have
gone to zero along the way.

And our headline number, fifty-four point five, has a wide range around it, forty-two to sixty-six.
That range doesn't rule out some small edge surviving the search. It rules out the large one the
whole procedure assumes — landing near the top, most of the time. It's the same shape of failure
we found in the chatbot-strategy test in this series: pick the best of many, mistake the pick for
skill.

**SCREEN** Card: "19 of 23 still made money — long, in a rising market." Then a small "chosen in
2026 · survivorship applies to both sides" note. Then a second card: "54.5, range 42 to 66."

**№** 19 of 23 winners positive in the holdout — derived: 23 minus the 4 outright losers listed in
RESULTS §2 (`winner_holdout_return < 0` for PG, INTC, BA, PFE) · 23 markets, 2026 — `n_instruments`,
survivorship note per RESULTS §6 ("Every ticker was chosen in 2026 and therefore survived; that
flatters both sides of the comparison equally") · mean T1 54.5, interval 41.8–66.3 —
`pooled.mean_T1` and interval, repeated from beat 5

## 9 · Check the next one yourself — 9:50 (speech 0:36 + 0:13 end card) — ends 10:39

**VO**
One question for the next backtest you're shown. What did these exact settings do on data they
were not chosen on? If there's no answer on screen, the number you're looking at measures how many
versions got tried, not what happens next.

AMI Trade is a simulator. You direct a team of twelve analysts, on simulated money, and the
record of every decision is kept for you. It is simulation-only, and it promises no edge. The test,
the code, and every number from this video are in the description.

**SCREEN** The question as a card. AMI end card. Disclaimer card: "Educational content. AMI Trade
is a simulation-only training product. Nothing here is investment advice."

**№** —

---

## Production notes

- **Do not say** (from the brief): "trend following doesn't work" · "optimisation is cheating" ·
  "the winners lost money" (19 of 23 made money in the holdout; they lost only to buy-and-hold, on
  21 of 23) · anything implying the as-shown 10× path reproduces a "$1k → millions" screenshot — it
  goes through zero on daily bars, it does not. The 5× figure is post-hoc and must carry that label
  on screen every time it appears (beat 7).
- Survivorship (beat 8) and the daily-bars limit on the leverage finding (beat 7) are both stated
  on camera, once each, per the brief's compliance checklist — not left in notes only.
- No per-year figure is spoken as a forecast anywhere in this script; T4's per-year shrinkage
  numbers from RESULTS §2 are not used in VO at all.
- No creator, channel, title, clip, or thumbnail is referenced anywhere. The strategy-tester panel
  in beat 2 is ours and must not resemble a real platform's UI.
- Beat 9's AMI line describes the product in general terms on purpose, matching the exemplar. If a
  more specific line is wanted, check it against the shipped app first.
- EN script — flag for AR / MS translation at v1.0.
