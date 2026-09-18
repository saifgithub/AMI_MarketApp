# P01 — VOICE-OVER SCRIPT — "AI predicts the stock" vs "always predict up"

**Week:** 11 · **Verdict:** `DISPROVED` · **Brief:** [VIDEO_BRIEF.md](VIDEO_BRIEF.md) ·
**Charts:** [charts/](charts/) · **Source study:**
`docs/Research/Alternatives/Intel/quant_finance/lgbm_results.md`

**Length:** 1,116 spoken words = 7 min 26 s of speech at 150 words a minute; with the pauses marked
below (charts building in silence), ≈ 9 min 07 s

> **This claim predates RES008's pre-registration discipline.** The source study fixed its method up
> front and ran two negative controls, but there is no pre-registration commit for it. Beat 3 says so
> on camera. Never imply otherwise, and never show a commit hash for this episode.

## How to read this file

**VO** is what the voice reads, verbatim. **SCREEN** is what is visible while that line is read.
**№** traces every number in the beat to the file and section it came from. Numbers are spoken as
words so the read is unambiguous; the on-screen figure is always the digits.

---

## 1 · Cold open — 0:00 (speech 0:32)

**VO**
Videos teaching "train a model, it predicts the stock" are everywhere. We built that model —
LightGBM, about forty-five features, walk-forward validated so it never sees the future. Its ranking
of up-periods against down-periods was measurably better than a coin flip. And in thirty of
thirty-two test cells — eight stocks, four horizons — it was less accurate than a rule that says
"up" every single time. Both of those are true at once. This video is about why.

**SCREEN**
`charts/01_auc_by_horizon.png` builds to the 0.5528 bar. Hold. Then the line
"edge negative in 30/32 cells" stamps across it in red.

**№** Overall AUC 0.5292 and "edge negative in 30/32 cells" — `lgbm_results.md`, "Headline results —
daily (post-fix, authoritative)", the **Overall** line. Per-horizon AUC from the same table.

---

## 2 · The stakes — 0:32 (speech 0:28)

**VO**
Here is why this matters. Somebody follows that tutorial, trains the same model, and sees a green
slide that says "AUC zero point five five — the model works." That is a true sentence. They then
start sizing real positions on the model's up-or-down calls, which is a different thing entirely,
and nothing on that green slide tells them so. The gap between those two sentences is where the
money goes.

**SCREEN**
A mock panel we drew ourselves: "YOUR MODEL SAYS: **UP** · confidence 0.55". No real product UI,
no platform chrome.

**№** No figures in this beat.

---

## 3 · What would convince us — 1:00 (speech 0:39 + 0:10 on the highlighted method lines)

**VO**
One thing to be straight about before any number lands. This test predates the pre-registration
discipline we use on this channel now, so there is no commit hash to show you for it. What the study
did fix up front was its method: strictly chronological walk-forward, so training data always comes
before test data; a purge gap, so the training window cannot touch a label that overlaps the test
window; and two negative controls that had to pass before any positive number would be trusted. That
is weaker than pre-registration. We are telling you which it is.

**SCREEN**
The "Method" section scrolls, then the "Independent leakage audit" heading. Two lines highlight:
the walk-forward split and the purge gap.

**№** Method and controls — `lgbm_results.md`, "Method" and "Independent leakage audit (and one real
bug found)" sections.

---

## 4 · The test, as taught — 1:49 (speech 0:38 + 0:15 for the chart to build)

**VO**
The recipe, as the tutorials give it. Label whether the next close is higher. Train a gradient-boosted
tree on lagged returns, moving averages, realised volatility, RSI, volume, and some cross-asset
features. Run it, and the headline number looks like success: at a one-day horizon the ranking score
is zero point five one, at five days zero point five two, at ten days zero point five three, and at
twenty days zero point five five — climbing steadily, and statistically significant at every step.
If you stopped reading here, you would think you had found something.

**SCREEN**
Feature-group list appears. Then `charts/01_auc_by_horizon.png` builds bar by bar, 1d → 20d, with
the coin-flip line at 0.50 already drawn.

**№** AUC 0.5107 (p 0.0490), 0.5190 (p 0.0066), 0.5345 (p 0.0026), 0.5528 (p 0.0005) —
`lgbm_results.md`, "Headline results — daily" table.

---

## 5 · The fair test, and the reveal — 2:42 (speech 1:27 + 0:25: two charts build in sequence)

**VO**
So the first question is whether that number is real or a leak. Two controls answer it. In the
first, the same pipeline is fed a synthetic series built so that the next bar follows the current one
ninety-five percent of the time — a series where the answer is definitely there. The pipeline
recovered it: ranking score zero point nine five. So when real signal exists, this code finds it. In
the second, the real market data is kept but the labels are scrambled, so there is definitely nothing
to find. The pipeline returned zero point four nine seven — noise, exactly as it should. That pair
matters. It means the zero point five five is not a bug and not a leak. It is real.

Now the part the headline slide leaves out. Ranking is not the same as being right. Stocks rise in
roughly fifty-nine to sixty-three percent of twenty-day windows, so a rule that ignores every feature
and simply says "up" every time scores about sixty-three percent accuracy. The model scores about
fifty-four. Compare each test cell against that always-up rule instead of against a coin flip, and
the model comes out behind in thirty of thirty-two cells — eight stocks, four horizons each. The
model knows something. It does not know enough.

**SCREEN**
`charts/02_controls.png` builds: scrambled labels, then the real result, then the injected signal.
Hold on the 0.9497 bar. Then cut to `charts/03_accuracy_vs_baseline.png`; the "always up" bar lands
visibly taller, and the "Edge negative in 30 of 32" callout appears last.

**№** Injected-signal AUC 0.9497 (daily h=1), synthetic series 95% predictable — "Independent leakage
audit". Shuffled-label control 0.4969 — "Model shootout" table. Model accuracy ~0.54, baseline ~0.63,
stocks rise ~59–63% of 20-day windows — "The central finding". 30/32 — headline table, **Overall**
line.

---

## 6 · Why — 4:34 (speech 1:33 + 0:20 for the cross-sectional card and feature list)

**VO**
Two separate failures are stacked here, and it is worth pulling them apart.

The first is the one you just saw. Asked to call absolute direction, the model is competing against
the market's own upward drift, and the drift wins. That is not a flaw in the model so much as the
wrong question to ask it.

So ask a fairer one. Instead of "will this stock go up", ask "will this stock beat the median stock
over the same twenty days". That question has no drift in it — if everything rises together, the
median rises too, and the drift cancels out. The study ran exactly that test on a panel of
thirty-two large caps across two thousand eight hundred and ninety-one dates, ninety-two thousand
rows. The ranking score came back at zero point five zero five five, with a p-value of zero point six
two. Indistinguishable from a coin flip. Take the drift away, and the signal goes with it.

The feature list says why. In both setups, the features the model leans on hardest are sixty-day
volatility, distance from the fifty-two week low, price against the two-hundred-day average, and the
volatility of Bitcoin, the S&P, and the VIX. Every one of those describes what the whole market is
doing. None of them describes this stock as against that stock. The model was never picking stocks.
It was reading the weather.

**SCREEN**
`charts/04_cross_sectional.png` — the two bars side by side, the second flat against the coin-flip
line. Then `charts/05_top_features.png`, the market-wide features highlighted.

**№** Cross-sectional mean AUC 0.5055, p = 0.6231; panel 32 large-caps × 2,891 dates = 92,512 rows —
"Cross-sectional ranking test". Top features — "Most important features (20-day horizon, by gain)".

---

## 7 · What is true — 6:27 (speech 1:22 + 0:15 for the intraday card)

**VO**
Now the other side, because this is not a video about machine learning being useless.

The ranking ability is real. It survived two independent controls and a fixed data bug, and it is
significant at the twenty-day horizon. That is a genuine finding. It is just a finding about which
*periods* look up-ish, not about which *stock* to buy — and it is only monetisable through mechanisms
that exploit ordering, like relative position sizing or long-short spreads, not through a yes-or-no
direction call. Even there the study checked the cost: the one place a positive spread survived, once
ten basis points a leg plus short borrow is charged, the spread drops to about fifteen hundredths of a
percent per period — inside the noise band.

And it only exists past the daily horizon. Tested below a day — forty-two cells, bars from one minute
to thirty, horizons from one minute to two hours, across three tickers — the edge was positive in
twenty-one of forty-two cells. A binomial test against a coin flip gives p equals one point zero
zero zero. Not weak. Exactly chance.

One more limit: point-in-time fundamentals were not available, so that route was never tested here.
Untested is not refuted.

**SCREEN**
A "what's true" card: "AUC 0.53–0.55 is real — but it is regime timing, not stock picking." Then
`charts/06_intraday_noise.png`.

**№** "Genuine, statistically detectable ability to rank" and the ordering-mechanism line — "The
central finding". Cost sensitivity ~+0.15%/period at 10bp/leg plus borrow — "Cross-sectional ranking
test" table notes. Intraday 21/42 cells, binomial p = 1.000, mean AUC 0.5081 — "Headline results —
intraday". Fundamentals unavailable — the study's limitations section.

---

## 8 · Check the next one yourself — 8:04 (speech 0:28 + 0:05 end card)

**VO**
So here is the one question to carry into the next video of this kind. When they show you the
accuracy number, ask what they compared it against. If the answer is fifty percent, they compared it
against a coin flip, and a coin flip is not the competition. The competition is the market's own
average direction. A model can beat a coin and still lose to doing nothing at all.

**SCREEN**
The question alone on a card: "Compared against 50% — or against the market's own drift?"

**№** No figures in this beat.

---

## 9 · AMI + disclaimer — 8:37 (speech 0:20 + 0:10 end card) — ends ≈ 9:07

**VO**
AMI Trade is a simulator. You practise the process with a twelve-analyst team and no real money, and
AMI walks the reasoning with you. We promise no edge, because we have not found one worth promising.
What we can give you is a place to test that for yourself.

**SCREEN**
AMI end card. Disclaimer: educational content; AMI Trade is simulation-only; nothing here is
investment advice.

**№** No figures in this beat.

---

## Production notes

- **Not pre-registered — beat 3 must survive the edit.** If beat 3 is cut for length, this episode
  cannot ship. It is the only place the script tells the viewer this claim predates the
  pre-registration discipline, and the compliance checklist requires it on camera.
- **"Edge" is accuracy minus the always-up baseline's accuracy, not profit.** No P&L was computed for
  the direction call. The script never says the model "lost money" — keep it that way in any trim.
- **30/32 is the 8-ticker batch** (8 stocks × 4 horizons). The separate 5-ticker batch was weaker,
  with every edge negative. Say "thirteen tickers" only about the study as a whole; this script does
  not, and should not start.
- **Keep daily and intraday visually separate.** Beat 7 cuts to its own card for a reason — the two
  results were produced by different tests and must not read as one finding.
- **Assets to produce before recording:** the beat-2 mock "YOUR MODEL SAYS: UP" panel, and the beat-3
  method-section scroll. Both are drawn by the editor; neither exists in `charts/`.
- **Chart 02's bar order is scrambled → real → injected**, and the subtitle follows that order. If the
  chart is re-cut, re-read the subtitle.
- EN script — flag for AR / MS translation at v1.0.
