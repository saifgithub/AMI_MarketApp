# C01 — SCRIPT — An LSTM predicts tomorrow's stock price

**Episode:** week 5 · **Verdict:** `NOT SUPPORTED` · **From:** [`VIDEO_BRIEF.md`](VIDEO_BRIEF.md) · **Numbers:** [`RESULTS.md`](RESULTS.md), [`out/results.json`](out/results.json)
**Length:** 1,145 spoken words = 7 min 38 s of speech at 150 words a minute; with the pauses marked below (charts building in silence), ≈ 9 min 33 s · **Charts:** [`charts/`](charts/)

How to read this file: **VO** is spoken word for word. **SCREEN** is what the editor shows while it
is spoken. **№** lists every number in the beat and where it comes from — if a number is not in
that list, it must not be said. Numbers are written as they should be read aloud.

---

## 1 · Cold open — 0:00

**VO**
LSTM stock price prediction — the chart where the predicted line sits right on top of the real
one. We built it as taught: two published recipes, ten stocks, three training runs each. Then we
drew one more line on the chart. No network, no training: tomorrow's price equals today's. On
the error score these tutorials quote, that line beat the neural network in sixty runs out of
sixty. One of our own four predictions was wrong, too — we'll show you which.

**SCREEN** The five-year overlay (left panel of `out/overlay_AAPL.png`, redrawn in the series
palette — see Production notes): the real price and the forecast line following every rise and
fall. A third line — dashed, "tomorrow = today" — fades in, sitting on the real price. Counter
climbs to "60 of 60".

**№** 0 of 60 as-taught runs beat "tomorrow = today" — `A1.pooled_M1.frac_below_1` 0.0 (n 30), `A2.pooled_M1.frac_below_1` 0.0 (n 30)

## 2 · The stakes — 0:33

**VO**
That chart is usually offered as proof the network sees tomorrow coming. And if you believe it,
there's an obvious next step: trade the forecast, or pay for something that claims to trade it
for you. So the chart has to earn that. A pretty overlay isn't enough — we need to know what it's
actually made of.

**SCREEN** Our own mock notebook UI: a training loss curve falling smoothly, a label reading
"RMSE: low", no branding, no real interface.

**№** —

## 3 · What would convince us — 0:56

**VO**
Before we trained anything, we wrote down what would change our minds, in public, with a
timestamp. In a fair version of this test — no peeking at the test data while training — any one
of three things would do it: beat "tomorrow = today" on error by five percent at the midpoint, and
in at least four runs out of five; call direction better than always guessing "up", on seven
stocks out of ten; or make more money than just holding the stock. Any one of those, and the
verdict is "holds" or "partly holds".

**SCREEN** Screen-record of `PREREGISTRATION.md` at commit `3ac320eb`; highlight "What would
support the claim instead".

**№** commit `3ac320eb` — `PREREGISTRATION.md` · thresholds: 5% median improvement in ≥ 4 of 5 runs; direction beats base rate in ≥ 7 of 10 tickers; money beats buy-and-hold — `PREREGISTRATION.md` "What would support the claim instead"

## 4 · The test, as taught — 1:35 (speech 0:43 + 0:15 for the recipe card to settle)

**VO**
The recipe, as it's usually taught: feed the network a stock's own past closing prices, nothing
else, and ask it to guess the next close. A hundred days of history in the window, three stacked
layers, a hundred training passes. We also built a second, more compact version people teach —
sixty days of history, fewer layers, twenty passes. Nine large stocks and an S&P 500 fund, prices
from 2012 through this year, with the most recent slice held back and never shown during
training.

And here's the chart it produces. The forecast follows every rise and fall of the real price,
for five years. We reproduced it.

**SCREEN** Recipe card: window size, layers, epochs, target = next close. Then the five-year
overlay again, full width (left panel of `out/overlay_AAPL.png`, redrawn).

**№** 100-day window, 3 layers, 100 epochs (variant one) — `PREREGISTRATION.md`; 60-day window
(variant two) — `PREREGISTRATION.md`; 10 tickers, 2012–2026 — `PREREGISTRATION.md` "Data"

## 5 · The fair test and the reveal — 2:33 (speech 1:32 + 0:35: strip plot and bars build in silence)

**VO**
Now we zoom that same chart into sixty days. Look closely: the forecast has the right shape, but
it's late, and it sits well below the real price. Add our third line, "no change" — it hugs the
real price far more closely, for free.

Here's the error score by the numbers. On one stock, one run: the network's error was seventeen
dollars and twelve cents. "No change" scored three dollars and forty-four cents. Across all ninety
price-forecasting runs — two recipes, ten stocks, three runs each, plus a version with a common
mistake fixed — the network's typical error was two to about four and a half times bigger than
just saying "no change". Never once, in ninety runs, was the network smaller.

So that's error. Now direction. Right or wrong on up-versus-down tomorrow, the network called it
correctly forty-eight point five percent of the time. A coin gets you fifty. Simply always
guessing "up" got fifty-two point five, because the market spent more days up than down. The
forecast was worse than a coin, and worse than the laziest possible guess.

And money. Trade that forecast — long when it says up, flat otherwise — and the typical run turned
a hundred dollars into a hundred and twenty-four. Simply holding the stock turned it into a
hundred and ninety-two. Only three of thirty runs beat holding at all.

**SCREEN** Right panel of the overlay, zoomed to sixty days, the forecast visibly late and low.
Then Chart `01`: ninety dots, all sitting to the right of the "1×" line. Then Chart `02`: the
direction bars against "always up" and the coin-flip line. Then Chart `03` (traded versus held),
and Chart `05` for the same result as a curve.

**№** $17.12 vs $3.44, one run — `A1.per_ticker_seed` (AAPL, seed 0), M1.model_rmse /
M1.naive_rmse · "sits well below" carries no number: the level gap is visible in
`out/overlay_AAPL.png` but is not a field in `out/`, so no dollar figure is spoken (RESULTS §2
gives the reason — 92% of that stock's test days closed above its training range) · 2 to 4.6× typical error,
0 of 90 below 1 — `pooled_M1.median_ratio` A1 1.98, A2 3.76, B-price 4.56; `frac_below_1` 0.0 all
three (RESULTS §2) · 48.5% direction, 52.5% always-up, first recipe — `A1.pooled_M3.pooled_hit_rate` 0.4848,
RESULTS §3 "Always-up, pooled" · +24% vs +92%, 3 of 30 — median total return next-open computed
from `A1.per_ticker_seed[*].M4.next_open.model_total_return` / `bh_total_return` (RESULTS §4)

## 6 · Why this happens — 4:40 (speech 1:20 + 0:20 on the lag animation)

**VO**
Here's the mechanism. Today's closing price is already an excellent guess at tomorrow's — stocks
don't usually jump far in a day. A network that's rewarded for small errors finds that guess and
settles on it. Its forecast for tomorrow actually matches the *real* price from one to several
days *earlier* — in every single one of the sixty as-taught runs.

Slide the forecast back by a day, and its turns line up with the real ones. Over five years, a
line that is a day late looks just like a line that is on time. That's the illusion.

Two more things worth knowing. Part of that low error score comes from a common setup mistake — a
scaling step that gets to see the test prices before the network is even trained. Fix that
mistake, and the error gets worse in twenty-six of thirty runs. And when you ask this same network
to project thirty days into the future on its own, the line comes out almost flat. It carries
forward about twelve percent of the real day-to-day jitter, because there's nothing in the recipe
telling it what tomorrow's move should be — only what yesterday's price was.

**SCREEN** Lag animation: the forecast line slides one day left and its turns meet the price
line's turns (to produce — see Production notes). Then a simple diagram: "scaler sees everything"
versus "scaler sees only the past". Then the smooth 30-day recursive forecast laid over the real,
jagged 30 days (to produce).

**№** forecast best matches the price 1–5 days earlier, all 60 as-taught runs — `A1`/`A2`
`M2.peak_xcorr_lag`, all negative (RESULTS §2: first recipe 1 day in 19 of 30 runs, 2–4 in the
rest; second recipe 2–5 days in 30 of 30) · error worse in 26 of 30 runs after removing the leak — `M5_leak.median_rmse_change`
+$2.49 · 12% of real daily jitter carried forward — A1 `M6.ratio` median (computed from
`per_ticker_seed[*].M6.ratio`, RESULTS §5)

## 7 · What is true — and the prediction we got wrong — 6:20 (speech 1:41 + 0:20 on the verdict card)

**VO**
Here's where we have to be straight with you about our own test.

We predicted this forecast would carry no information at all about tomorrow's actual move — a
range that includes zero. We measured a small positive number instead: a correlation of about
zero point zero two, on a scale where one is a perfect forecast. That accounts for roughly three
hundredths of one percent of the daily movement — and by our own math the range does not include
zero. It's tiny — it never turned into better direction calls or better returns — and we
have to flag something that cuts against us here too: the range we calculated for that number
wasn't planned in advance, and we think it's probably too tight, because three of our training
runs per stock share the exact same real prices. We have not gone back and recalculated it now
that we've seen the result.

But we wrote down "zero", and we didn't get zero. So by our own rule, one of our four predictions
failed — and the honest verdict is "not supported", not "disproved". We reserve that stronger word
for when every one of our predictions holds. This time, one didn't.

One more thing a single tutorial run will never show you: the exact same recipe, same stock,
different random seed, produced wildly different behavior — one seed had its trading rule sitting
in cash on every single day, another had it in the market on more than half of them.

**SCREEN** Verdict card: "NOT SUPPORTED — 3 of 4 predictions met, 1 missed." Then Chart `04`:
the 0.02 beside the 0.81 echo of yesterday, on one scale. Then a card: three seeds, same recipe, same stock, days-in-market 0% /
0% / 58%.

**№** correlation ≈ 0.02, interval excludes zero — `A1.pooled_M2.pooled_corr_tracks_tomorrow`
0.0186 (0.0092–0.0290); `A2` 0.0133 (0.0013–0.0252) · "three hundredths of one percent of the
daily movement" — RESULTS §2 (0.03% and 0.02% of the variation in daily changes) · interval not
pre-registered and probably too narrow, not re-pooled — RESULTS §1, deviation 3 · 3 of 4 predictions met, 1 missed — RESULTS §6
(H1, H3, H4 met; H2 not met) · one stock, one recipe, three seeds: 0% / 0% / 58% days in market —
computed from per-seed `M4.next_open.share_of_days_with_nonzero_model_return` for KO across seeds
0/1/2 (0.0, 0.0023, 0.583)

## 8 · Check the next one yourself — 8:21 (speech 0:28 + 0:15 for the card)

**VO**
Three questions for the next prediction chart somebody shows you. Where is the "tomorrow equals
today" line — does anyone plot it next to theirs? What does the chart look like zoomed into one
month, instead of five years? And is it actually predicting the *change* — or just repeating the
*level* it already knows?

If a chart can't answer those three, the overlay is doing the convincing, not the network.

**SCREEN** The three questions as a card, one at a time.

**№** —

## 9 · AMI + disclaimer — 9:04 (speech 0:19 + 0:10 end card) — ends ≈ 9:33

**VO**
AMI Trade is a simulator. You direct a team of twelve analysts, on simulated money, and the
record of every decision is kept for you. It is simulation-only, and it promises no edge. The
test, the code and every number from this video are in the description.

**SCREEN** AMI end card. Disclaimer card: "Educational content. AMI Trade is a simulation-only
training product. Nothing here is investment advice."

**№** —

---

## Production notes

- **Do not say** (from the brief): "debunked", "disproved", "busted", "myth", "fraud", "scam",
  "fake", "liar", "exposed", "destroyed" · "neural networks can't predict markets" / "machine
  learning doesn't work in finance" · "the chart is fake" (it is real and reproduced) · "the
  forecast is yesterday's price" (say "trails" — it best matches price one to five days earlier) ·
  the 0.02 correlation must never appear in a title, thumbnail or Shorts cut, and is never called
  an edge or a strategy · no creator, channel, video, notebook or thumbnail referenced anywhere.
- **Not supported from `out/` — omitted.** The brief's beat 6 figure "typical daily move: median
  absolute daily change 0.56%–2.04% across the ten tickers' test segments" is flagged in the brief
  itself as "not in `results.json`; recompute before recording." It is not present anywhere in
  `out/results.json` or `out/summary.txt` (checked programmatically — no daily-change or
  volatility field exists outside M6's std-ratio). Not spoken; beat 6 explains the mechanism
  ("stocks don't usually jump far in a day") in plain words instead, with no number attached.
  Recompute and re-insert only if a reviewer wants it back in.
- The AAPL 92%-of-test-days-above-training-range level-error detail (RESULTS §2) is not in any
  brief № entry and is not spoken; it's a secondary explanation for *why* the error is large, not
  needed once beat 6 already gives the mechanism.
- Beat 5's "$17.12 vs $3.44" is one ticker/seed example (AAPL, seed 0), stated as such in the
  brief; not the pooled median. The pooled ratio (median 1.98/3.76/4.56, all 0 of 90 below 1) is
  what carries the claim; the dollar figure is illustrative and spoken as "one stock, one run"
  equivalent language ("On one stock, one run").
- RESULTS.md rounds the median total-return figures to +24% / +92%; the underlying values
  (0.2400 / 0.9161) were recomputed independently from `per_ticker_seed` and match RESULTS §4 —
  no disagreement found between RESULTS.md and `results.json` anywhere numbers were checked.
- Beat 7's KO seed-1 share (0.23%) rounds to 0% exactly as the brief's "0% / 0% / 58%" does; no
  discrepancy, just noting the rounding for a reviewer.
- Wording flagged for review: beat 5 renders 0.019 tickers-vs-coin comparison and the pooled
  "always-up" base rate (52.5%) rather than the stricter per-ticker `max_base_rate` (54.2%) —
  matching RESULTS §3's own "Always-up, pooled" column and the brief's beat-5 source note, not the
  higher per-ticker figure used only for the H3/pass-condition test in §6. Flagging in case the
  reviewer wants the stricter number surfaced instead.
- Beat 7 discloses the un-pre-registered, likely-too-narrow M2 interval on camera per the episode
  brief's explicit instruction, in beat 7 itself (not deferred to a chart footer only).
- Quote point estimates on camera; intervals live on the charts, except the 0.02 correlation range
  in beat 7, which is the point under discussion and is described in the VO as "does not include
  zero" without reading the exact bounds aloud.
- No creator, channel, title, clip, thumbnail or notebook is referenced anywhere. The mock
  notebook UI in beat 2 is ours and must not resemble a real product's interface.
- **To produce before recording (not in `charts/` yet):** the overlay redraw in the series
  palette, the one-day lag animation and the 30-day recursive-forecast figure all need the price
  and forecast series, which `out/` does not keep (only per-run summaries and daily returns).
  Saving those series is a small change to `code/make_overlay_figure.py` and a re-run on the
  research machine; until then `out/overlay_AAPL.png` is the reference picture, not a broadcast
  asset. The VO names no colours, so the redraw is free to use the series palette.
- The overlay's forecast line sits visibly below the real price in the last two years of the test
  segment (level error, RESULTS §2). The VO therefore says the forecast "follows every rise and
  fall", never that it "sits on top" of the real line — that phrase appears only in the hook, where
  it describes the genre's chart.
- EN script — flag for AR / MS translation at v1.0.
