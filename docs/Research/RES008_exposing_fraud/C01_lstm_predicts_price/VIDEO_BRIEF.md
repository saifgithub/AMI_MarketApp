# C01 — VIDEO BRIEF — The prediction chart that sits on top of the price

**Verdict:** `NOT SUPPORTED` — three of our four predictions met, one missed, no claim condition met · **Pre-registration commit:** `3ac320eb` · **Results:** [`RESULTS.md`](RESULTS.md)
**Runtime target:** 9–11 min · **Format:** faceless, chart-driven, voice-over
**Claim class reach (measured 2026-09-17):** 2 videos read · 1.95M views

## Search intent

- **Primary keyword:** LSTM stock price prediction
- **Secondary:** AI stock price prediction tested · neural network predicts stock prices · stock prediction machine learning python
- The primary keyword appears in the title, the first spoken sentence, and the first line of the description.
- LSTM is a public architecture and is named. No tutorial, notebook or code listing from any video is shown — the code on screen is ours.

## Title options (≤ 60 characters, all literally true)

1. *LSTM stock price prediction, tested against "no change"*
2. *90 price-predicting networks vs "no change": 0 wins*
3. *Why the AI stock prediction chart looks so accurate*

## Thumbnail concept

Left half: a red "predicted" line sitting on a black price line, five years wide. Right half: the
same two lines zoomed to two months, the red one a step behind. Text: "Zoom in."

## Hook (0:00–0:25) — spoken, verbatim

> "LSTM stock price prediction — the chart where the predicted line sits right on top of the real
> one. We built it as taught: two published recipes, ten stocks, three training runs each. Then we
> drew one more line on the chart. No network, no training: tomorrow's price equals today's. On
> the error score these tutorials quote, that line beat the neural network in sixty runs out of
> sixty. One of our own four predictions was wrong, too — we'll show you which."

## Beat sheet

| # | Beat | Time | Voice-over (gist) | On screen | Source of every number |
|:--|:--|:--|:--|:--|:--|
| 1 | Cold open | 0:00–0:25 | Hook above. | The five-year overlay; a third dashed line appears; counter "60 of 60". | `results.json` → `A1.pooled_M1.frac_below_1` 0.0 (n 30), `A2.pooled_M1.frac_below_1` 0.0 (n 30) |
| 2 | The stakes | 0:25–0:50 | The chart is offered as proof the network sees tomorrow. The next step for a viewer is to trade its forecast — or pay for something that says it does. | Our own notebook mock-up: a loss curve falling, "RMSE: low". | — |
| 3 | What would convince us | 0:50–1:50 | Written down first. In a fair version — no peeking at the test data — any one of three: beats "no change" on error — by 5% at the median, and in at least four runs of five; calls direction better than always saying "up", in seven stocks of ten; or makes more money than holding. Any one, and the verdict is "holds" or "partly holds". | `PREREGISTRATION.md`, commit `3ac320eb`, the three conditions highlighted. | `PREREGISTRATION.md` |
| 4 | The test, as taught | 1:50–3:40 | The recipe: past closing prices in, next close out; 100-day window, three LSTM layers, 100 epochs. A second recipe, 60-day window. Nine large stocks and the S&P 500 fund, 2012 to 2026, last 35% held back. And here is the chart — it does look like that. We reproduced it. | Recipe card. Then `overlay_AAPL.png` left panel, restyled. | `PREREGISTRATION.md` recipe; `out/overlay_AAPL.png` |
| 5 | The fair test + reveal | 3:40–6:30 | Zoom to sixty days. The red line has the right shape — late, and well below the real price. The dashed line, "no change", hugs the price. Error score: network 17 dollars, no change 3.44. At the median the network's error was two to four-and-a-half times larger; never smaller, 90 runs of 90. Direction: right 48.5% of the time — a coin gets 50, always saying "up" got 52.5. Trading it: plus 24% where holding made plus 92. | Right panel of the overlay. M1 strip plot, 90 dots, all right of the "1.0" line. Direction bars: 48.5 / 50 / 52.5. Two equity curves. | the level gap is visible in `overlay_AAPL.png` but is not a field in `out/`, so no dollar figure is spoken; `A1.per_ticker_seed[AAPL,0].M1` 17.12 / 3.44; `pooled_M1.median_ratio` 1.98, 3.76, 4.56; `A1.pooled_M3` 0.4848, pooled always-up 0.5254 (RESULTS §3); M4 medians +24.0% vs +91.6%, 3 of 30 (RESULTS §4) |
| 6 | Why | 6:30–8:00 | Today's price is an excellent guess at tomorrow's price — on a typical day these ten moved between half a percent and two percent. A network rewarded for small price errors finds that guess. Its forecast best matches the price from one to five days *earlier*, in 60 of 60 runs. Over five years a line a day behind is indistinguishable from the real one. Two more things. The low error score is helped by a scaling step that has already seen the test prices: without it, the error got worse in 26 runs of 30. And the "next 30 days" forecast is a smooth curve because the network has almost nothing to carry forward — 12% of the real day-to-day movement. | The lag animation: slide the red line one day left and it snaps onto the black. Scaler diagram: "fit on everything" vs "fit on the past". The smooth 30-day line against a real 30 days. | `M2.peak_xcorr_lag` all negative in A1, A2 (RESULTS §2); `M5_leak` 26 of 30, median +2.49; `A1` M6 median ratio 0.121. Typical daily move: median absolute daily change 0.56%–2.04% across the ten tickers' test segments — computed from the price data, **not in `results.json`; recompute before recording** |
| 7 | What is true — and the prediction we got wrong | 8:00–9:30 | We predicted the forecast would carry *no* information about tomorrow. We measured a correlation of 0.02 — about three hundredths of one percent of the daily movement — and by our calculation it is distinguishable from zero. It didn't turn into direction or money, and our interval is probably too narrow. But we wrote "zero", we didn't get zero, and so by our own rule the verdict is "not supported", not "disproved". Also true: the same recipe with a different random seed gave a different answer — one stock's trading rule was in the market 0% of days or 58%. A tutorial shows one run. | Verdict card: "NOT SUPPORTED — 3 of 4 predictions met". The 0.02 on a scale from 0 to 1. Seed card. | `A1.pooled_M2.pooled_corr_tracks_tomorrow` 0.0186 (0.0092 … 0.0290); `A2` 0.0133 (0.0013 … 0.0252); KO share of days long 0.00 / 0.00 / 0.58 |
| 8 | Check the next one yourself | 9:30–10:10 | Three questions for any prediction chart. Where is the "no change" line? What does it look like zoomed to a month? Did it predict the *change*, or just the level? | The three questions as a card. | — |
| 9 | AMI + disclaimer | last 15 s | AMI Trade is a simulator: you direct a twelve-analyst team on simulated money, and the record is kept for you. Simulation-only, no edge promised. | AMI end card, disclaimer. | — |

## The one idea

A price forecast that trails the price by a day looks perfect on a five-year chart — and "tomorrow
equals today" does the same thing better, for free.

## What we must not say

- **Not "debunked", not "disproved".** The verdict is `NOT SUPPORTED`, the word is on screen, and beat 7 says why.
- Not "neural networks can't predict markets" or "machine learning doesn't work in finance". One recipe — closing prices in, next close out — and its evidence standard. Volatility is forecastable; we say so in another episode.
- Not "the chart is fake". We reproduced it. It is real and it is uninformative.
- Not "the forecast is yesterday's price". It best matches the price one to five days earlier and is also biased low where prices left the training range. Say "trails".
- The 0.02 is **not an edge and not a strategy**. One beat, stated with its size, never in the title, thumbnail or Short.
- Do not call the scaler step "cheating". It is a common mistake; say what it does and what it cost (26 of 30).
- The second recipe's exact network is our assumption (its source does not show it). Say so once, in beat 4.
- The test years (2021–2026, 2023–2026) were rising markets, which is why sitting out cost so much. Say so at the money figure.
- Nothing about where a viewer might have seen such a chart.

## Description (first 160 characters are the search snippet)

LSTM stock price prediction, tested: 120 networks, 10 stocks. "Tomorrow = today" beat the neural
network's error in 90 of 90 price-forecasting runs.

Pre-registered before any code existed. Two published recipes reproduced as taught, plus a fair
version with the data leak removed and a version that forecasts returns; 9 large US stocks and
SPY, 2012–2026, three random seeds each. Measured: error against "no change", what the forecast
actually follows, direction hit rate against always-up, and a long-or-flat trading rule against
buy-and-hold with costs. Three of our four predictions held and one did not — the results file
says which, and why the verdict is "not supported" rather than "disproved".

Links: claim folder (pre-registration · code · outputs) · episode page · AMI Trade (UTM).
Disclaimer: educational content; AMI Trade is a simulation-only training product; nothing here is
investment advice. By policy we test claims and name no channel.

## Pinned comment

Pre-registered on 2026-09-17 in commit `3ac320eb`, before any test ran. Three of four predictions
held. The one that did not: we predicted zero correlation between the forecast and tomorrow's move
and measured 0.02 — RESULTS.md §2 and §6. Found an error? A verified one gets a pinned correction.

## Shorts cut-down (≤ 40 s)

"This neural network predicts stock prices." → the five-year overlay → "Zoom in." → the 60-day
panel → "It's a day late. 'Tomorrow equals today' scored better — 90 runs out of 90." Full test
on the channel.

## Chart pack (from `out/`)

| Figure | Use | Restyle notes (AMI hex, 16:9, dark) |
|:--|:--|:--|
| `overlay_AAPL.png` | Beats 1, 4, 5, Short, thumbnail | Split into two full-frame charts. Left: actual + predicted only. Right: add the dashed "no change" line last, as its own animation step. Label the ticker; it is one run (seed 0) of 30 and the caption says so. |
| M1 strip plot (to draw) | Beat 5 | 90 dots from `pooled_M1.ratios` (A1, A2, B-price), log x-axis, vertical line at 1.0. |
| Direction bars (to draw) | Beat 5 | 48.5 / 50 / 52.5 for A1; small multiples for the other arms. |
| Lag animation (to draw) | Beat 6 | Any A1 run with `peak_xcorr_lag` −1; slide the forecast one day left. |
| 30-day recursive forecast vs realised (to draw) | Beat 6 | Re-run `recursive_forecast` for one ticker; `M6` holds only the ratio. |

## Compliance checklist

- [ ] No creator / channel / title / clip / thumbnail / notebook referenced, on screen or spoken
- [ ] Code and charts on screen are ours
- [ ] "We tested this claim" language; no *fraud*, *scam*, *liar*; no "debunked" for this episode
- [ ] Verdict `NOT SUPPORTED` spoken and shown, with the missed prediction
- [ ] Every number traced to `results.json` or RESULTS.md §3–§4 (recomputed figures)
- [ ] Limits stated on camera: 10 tickers, daily closes, rising test years, one assumed architecture, one run per chart
- [ ] No strategy offered in return; ends on method
- [ ] AMI by name; simulation-only; not investment advice
- [ ] EN script flagged for AR / MS translation at v1.0
