# P01 — VIDEO BRIEF — The model that "beats the market" without beating "always up"

**Verdict:** `DISPROVED` (as recorded in `01_prior_work.md` / `TRACKER.md`: "edge negative in 30/32
cells vs always-up; AUC 0.5055 once beta removed") · **Source study:**
`docs/Research/Alternatives/Intel/quant_finance/lgbm_results.md` · **Results:** the source file
itself (this claim predates RES008's per-claim `RESULTS.md` convention)
**Runtime target:** 9–11 min · **Format:** faceless, chart-driven, voice-over
**Claim class reach:** not measured — prior work

> This claim was tested before RES008 existed, under the Intel/quant_finance study's own method
> (walk-forward LightGBM, not a pre-registration commit). It was **not pre-registered** in the
> RES008 sense — say so on camera; do not imply a pre-registration commit exists for this one.

## Search intent

- **Primary keyword:** does AI predict stock direction
- **Secondary:** machine learning stock prediction tested · LightGBM stock prediction results · AUC vs accuracy stock model
- The primary keyword appears in the title, the first spoken sentence, and the first line of the description.

## Title options (≤ 60 characters, all literally true)

1. *We tested "AI predicts the stock." It loses to "always up."* (57)
2. *ML stock prediction tested: AUC 0.53, edge below zero* (55)
3. *We tested ML stock direction. Edge was negative 30/32.* (56)

## Thumbnail concept

One chart, one number, at most four words. Two bars: "model" vs "always up" accuracy, model bar
shorter. Four words: "Beats a coin. Not 'up'."

## Hook (0:00–0:20) — spoken, verbatim

> "Videos teaching 'train a model, it predicts the stock' are everywhere. We built that model —
> LightGBM, about forty-five features, walk-forward validated so it never sees the future. Its
> ranking of up-periods against down-periods was measurably better than a coin flip. And in thirty
> of thirty-two test cells — eight stocks, four horizons — it was less accurate than a rule that
> says 'up' every single time. Both of those are true at once. This video is about why."

## Beat sheet

| # | Beat | Time | Voice-over (gist) | On screen | Source of every number |
|:--|:--|:--|:--|:--|:--|
| 1 | Cold open | 0:00–0:20 | Hook above. | AUC number appears, then the "edge negative in 30/32" line stamped over it. | `lgbm_results.md` "Headline results — daily (post-fix, authoritative)" table: overall AUC 0.5292; "Overall: AUC 0.5292, t=6.83, p<0.0001 — but edge negative in 30/32 cells." |
| 2 | The stakes | 0:20–0:50 | A viewer who copies this trains the same kind of model, sees a green "AUC 0.55, model works" slide, and starts sizing real trades on its up/down calls. | Generic "your model says: UP" mock panel we drew ourselves — no real product UI. | — |
| 3 | What would convince us | 0:50–2:00 | Not a formal pre-registration for this one — it predates that discipline — but the study fixed its method up front: strictly chronological walk-forward, a purge gap so training can't touch test-window labels, and two negative controls before trusting any positive number. | Scroll of the "Method" section + "Independent leakage audit" section. | `lgbm_results.md` "Method" and "Independent leakage audit (and one real bug found)" sections |
| 4 | The test, as taught | 2:00–4:00 | The recipe as the tutorials show it: label the direction of the next close, train a gradient-boosted tree on lagged returns, moving averages, realised vol, RSI, volume, cross-asset features. Run it and the headline number looks good. | Feature list; AUC-by-horizon bar chart climbing 1d → 20d. | `lgbm_results.md` "Headline results — daily" table: 1d AUC 0.5107 (p 0.0490), 5d 0.5190 (p 0.0066), 10d 0.5345 (p 0.0026), 20d 0.5528 (p 0.0005) |
| 5 | The fair test + reveal | 4:00–7:00 | First check: is the AUC real or a leak? An injected-signal control (a series built to be 95%-predictable) recovers AUC 0.95 — the pipeline can find real signal when it's there. A shuffled-label control lands at 0.4969 — noise, as it should. So the 0.53–0.55 AUC is real. But "real" isn't "profitable": stocks drift up 59–63% of the time over 20 days, so "always predict up" scores ~63% accuracy while the model's accuracy is ~54%. Converted into an edge-vs-baseline number, it's negative in 30 of 32 cells. | Two-control diagram (injected-signal 0.9497/0.9485, shuffled-label 0.4969) next to the headline 0.53–0.55. Then the accuracy-vs-baseline bar: model ~54% vs baseline ~63%. Then "edge negative: 30/32 cells". | Injected-signal AUC 0.9497 (daily h=1), 0.9485 (intraday h=1 bar) — "Independent leakage audit" section. Shuffled-label control AUC 0.4969 — "Model shootout" table. "accuracy is ~0.54" vs "naive baseline scores ~0.63" — "The central finding" section. "edge negative in 30/32 cells" — headline table + "Overall" line |
| 6 | Why | 7:00–9:00 | Two separate failures stacked. First: predicting absolute up/down, the model is fighting the market's own upward drift, and drift wins. Second: strip the drift out by asking a harder, fairer question — does this stock beat the *median* stock over the same 20 days? — and the signal itself disappears: AUC 0.5055, barely different from a coin flip. The top features in both setups are the same market-wide numbers (60-day volatility, distance from the 52-week low, BTC/SPY/VIX volatility) — they describe the whole market's mood, not this stock versus that one. | Cross-sectional AUC card next to the single-ticker one. Feature-importance list, market-wide items highlighted. | Cross-sectional test: "Mean AUC 0.5055, p = 0.6231" — "Cross-sectional ranking test" section (panel: 32 large-caps × 2,891 dates, 92,512 rows). Top features — "Most important features (20-day horizon, by gain)" list: `vol_60d`, `pct_off_52w_low`, `month`, `px_over_ma200`, `btc_vol20`, `spy_vol20`, `vix_vol20`, `ma20_over_ma50` |
| 7 | What is true | 9:00–10:00 | The raw ranking ability is real and survives two independent checks — that's not nothing, and it's not the claim either. It's a weak signal about which *periods* look up-ish, not which *stock* to buy, and it only shows up past the one-day horizon: anything under a day was indistinguishable from noise. Even the study's own cost-sensitivity check shows the one place a positive spread survived (fold-level cross-sectional Q5−Q1) shrinks toward the noise band once trading costs are added. | "What's true" card: "AUC 0.53–0.55, real — but it's regime timing, not stock picking." Intraday-noise card. | "AUC is significantly above 0.50 … genuine, statistically detectable ability to rank" — "The central finding" section. Intraday: "Positive edge in 21/42 cells — binomial p = 1.000 … Exactly chance", mean AUC 0.5081 (p=0.069) — "Headline results — intraday" section. Cost sensitivity: "at 10bp/leg plus short borrow, the spread drops to ~+0.15%/period — inside the noise band" — "Cross-sectional ranking test" table notes |
| 8 | Check the next one yourself | 10:00–10:40 | One question for any "my model predicts the stock" video: did they compare accuracy to simply predicting the market's own average direction — not to 50%? A model can beat a coin flip and still lose to doing nothing. | The question as a card. | — |
| 9 | AMI + disclaimer | last 15 s | AMI Trade is a simulator: practise process with a twelve-analyst team and no real money. We promise no edge. | AMI end card, disclaimer. | — |

## The one idea

A model can be right significantly more than half the time and still lose money, because the bar
it has to clear isn't "better than a coin flip" — it's "better than the market's own drift."

## What we must not say

- "Edge" in the source is **accuracy minus the always-up baseline's accuracy** — not profit. Never say
  the model "lost money"; no P&L was computed for the direction call.
- The 30/32 figure is the 8-ticker batch (8 × 4 horizons). The separate 5-ticker batch was weaker
  with all edges negative; say "13 tickers" only for the study as a whole.
- This study predates RES008's pre-registration discipline. Do not say or imply "pre-registered"
  or show a commit hash for this claim — the source file records a method and controls, not a
  pre-registration commit.
- Do not say ML "can't" predict stocks, full stop. The raw AUC is genuinely above 0.50 and survives
  two independent controls (injected-signal, shuffled-label) — say plainly that the ranking signal
  is real, just not tradeable as a direction call once beta/drift is accounted for.
- Do not extend this to intraday claims as if they were the same finding — intraday was tested
  separately and came back indistinguishable from noise (21/42 cells positive, binomial p=1.000);
  keep the two results separate on camera.
- Do not claim this rules out fundamentals-based or alternative-data approaches — the study states
  plainly that point-in-time fundamentals data was unavailable (yfinance's free tier), so that
  route was never tested, not refuted.
- No annualising or extrapolating any AUC or edge number. Use only the horizons and figures printed
  in the source table.
- No creator, channel, video title or thumbnail is named or shown.

## Description (first 160 characters are the search snippet)

Does AI predict stock direction? We tested it: walk-forward LightGBM, AUC above a coin flip, yet
less accurate than "always predict up" in 30 of 32 cells (8 stocks × 4 horizons).

Full method: 45 features, 5-fold walk-forward with a purge gap, an injected-signal control (AUC
0.95, proving the pipeline finds real signal when it exists) and a shuffled-label control (0.497,
proving it doesn't hallucinate signal). Then a harder cross-sectional test that strips out market
drift — and the AUC drops to 0.5055, indistinguishable from chance.

Links: source study · episode page · AMI Trade (UTM).
Disclaimer: educational content; AMI Trade is a simulation-only training product; nothing here is
investment advice. By policy we test claims and name no channel.

## Pinned comment

This claim was tested prior to RES008 and is not pre-registered in the commit sense — the method
and controls are recorded in the source file linked below. Source:
`docs/Research/Alternatives/Intel/quant_finance/lgbm_results.md`. Found an error? Tell us; a
verified one gets a pinned correction.

## Shorts cut-down (≤ 40 s)

"AI stock model: accuracy beats a coin flip." → bar chart: model ~54% vs "always up" ~63% →
"Better than a coin flip. Worse than a rule that always says up." Full test on the channel.

## Chart pack (from source study)

No chart images exist in the source folder (`docs/Research/Alternatives/Intel/quant_finance/` has
only `.md` results files, `scripts/`, and raw `data/*.csv` — no rendered figures). Everything below
needs to be drawn.

| Figure | Use | Restyle notes (AMI hex, 16:9, dark) — source numbers |
|:--|:--|:--|
| AUC-by-horizon bar chart (to draw) | Beat 4 | Daily AUC 0.5107 (1d) → 0.5190 (5d) → 0.5345 (10d) → 0.5528 (20d), from `lgbm_results.md` "Headline results — daily" table |
| Two-control diagram (to draw) | Beat 5 | Injected-signal AUC 0.9497 (daily h=1) / 0.9485 (intraday) vs shuffled-label AUC 0.4969, vs headline 0.53–0.55, from "Independent leakage audit" and "Model shootout" sections |
| Accuracy-vs-baseline bar (to draw) | Beat 5 | Model accuracy ~0.54 vs "always up" baseline ~0.63 ("stocks rise ~59–63% of 20-day windows"), from "The central finding" section; "edge negative in 30/32 cells" from the headline table |
| Cross-sectional AUC card (to draw) | Beat 6 | Mean AUC 0.5055, p = 0.6231, from "Cross-sectional ranking test" table (5-fold panel, 32 tickers × 2,891 dates) |
| Feature-importance list (to draw) | Beat 6 | `vol_60d`, `pct_off_52w_low`, `month`, `px_over_ma200`, `btc_vol20`, `spy_vol20`, `vix_vol20`, `ma20_over_ma50`, from "Most important features (20-day horizon, by gain)" |
| Intraday-noise card (to draw) | Beat 7 | 21/42 cells positive edge, binomial p = 1.000; mean AUC 0.5081, p = 0.069, from "Headline results — intraday" section |

## Compliance checklist

- [ ] No creator / channel / title / clip / thumbnail referenced, on screen or spoken
- [ ] States plainly this claim predates pre-registration discipline — no commit hash implied
- [ ] "We tested this claim" language; no *fraud*, *scam*, *liar*
- [ ] Every number traced to `lgbm_results.md`, with its section heading
- [ ] Limits of the test stated on camera (intraday separate, fundamentals untested, raw AUC is real)
- [ ] No strategy offered in return; ends on method
- [ ] AMI by name; simulation-only; not investment advice
- [ ] EN script flagged for AR / MS translation at v1.0
