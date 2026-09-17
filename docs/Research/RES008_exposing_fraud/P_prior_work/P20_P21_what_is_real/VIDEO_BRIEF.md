# P20 + P21 — VIDEO BRIEF — The claim that held: you can forecast *how much*, not *which way*

**Verdict:** `HOLDS` — as a statement about risk, not about returns (as recorded in
`01_prior_work.md` / `TRACKER.md`) · **Source studies:**
`docs/Research/RES001_finding_the_edge/03_volatility_regime_sizing/` (pre-registration commit
`55a66533`, 2026-08-30) and `…/04_gamma_transition_dispersion/` (commit `a85a6e40`, 2026-08-30) ·
**Results:** [part 03](../../../RES001_finding_the_edge/03_volatility_regime_sizing/RESULTS.md) ·
[part 04](../../../RES001_finding_the_edge/04_gamma_transition_dispersion/RESULTS.md)
**Runtime target:** 9–11 min · **Format:** faceless, chart-driven, voice-over
**Claim class reach:** not measured — prior work

> **Series role.** Week 7. After six episodes of claims that failed, this is the one that passed
> the same kind of test — and the episode has to be as plain about what it costs as the others were
> about what failed. It is **not** a recommendation to size positions in any way. It reports what
> was forecastable in the data and what was not.

## Search intent

- **Primary keyword:** does the VIX predict the stock market
- **Secondary:** can you predict market volatility · volatility regime position sizing tested · VIX high what happens next
- The primary keyword appears in the title, the first spoken sentence, and the first line of the description.

## Title options (≤ 60 characters, all literally true)

1. *Does the VIX predict the stock market? How much, not where*
2. *We test trading claims. This one held. It isn't free.*
3. *What the VIX forecasts, tested on 21 years: size, not side*

## Thumbnail concept

Two gauges side by side. Left, labelled "HOW MUCH", needle firmly at "2×". Right, labelled "WHICH
WAY", needle wobbling at zero. Text: "One of these works."

## Hook (0:00–0:25) — spoken, verbatim

> "Does the VIX predict the stock market? We test claims like that on this channel, and mostly
> they fail. This one didn't. When the VIX is in the top third of its recent range, the S&P 500
> moves about twice as much over the following week as when it's in the bottom third — and that
> held up on seven and a half years the rule had never seen. What it does not tell you is which
> way. And using it isn't free. We'll show you the cost, and the part that got worse."

## Beat sheet

| # | Beat | Time | Voice-over (gist) | On screen | Source of every number |
|:--|:--|:--|:--|:--|:--|
| 1 | Cold open | 0:00–0:25 | Hook above. | Two gauges: "how much" at 2×, "which way" at zero. | Part 03 Test A, holdout h=5: 2.08 (1.69–2.58); holdout = 2019-01-01 → 2026-08-28 |
| 2 | The stakes | 0:25–0:55 | Most of what is sold as prediction is about direction. If the only dependable forecast is about the *size* of moves, then the useful question changes from "what will it do" to "how much am I exposed if I'm wrong". | Card: "Direction → ? · Size of move → forecastable". | — |
| 3 | What would convince us | 0:55–2:00 | Written down first, three tests, each with a way to fail. A: stressed-to-calm ratio of future volatility — fails if its interval includes 1. B: direction — we *expected nothing*, and wrote that a clear directional result would make us stop and re-scope. C: does sizing by regime beat a placebo that varies size by exactly as much, at random — fails if the interval includes 1. | Pre-registration on screen, commit `55a66533`, the three kill lines highlighted. | Part 03 `PREREGISTRATION.md` |
| 4 | The test | 2:00–3:40 | The S&P 500 fund and the VIX, daily, 2005 to August 2026. "Regime" is where yesterday's VIX sits within its own last two years — bottom third calm, top third stressed — using only information available the day before. Everything fixed on 2005–2018; 2019–2026 opened once. Horizons of one week, two weeks, a month. | Timeline with the split; a VIX line with its terciles shaded. | 5,448 rows; definition 3,523, holdout 1,925; 504-day trailing percentile; h ∈ {5, 10, 21} — part 03 PREREGISTRATION / RESULTS header |
| 5 | The reveal | 3:40–6:10 | **How much:** future volatility after a stressed day is 2.4 times a calm day's at one week in the first period — and 2.1 times in the unseen period. All six intervals clear of 1. **Which way:** five of six intervals include zero, and every estimate flips sign between the two periods — negative before 2019, positive after. **Sizing:** scale exposure down when volatility is high, up when it's low, capped at half and one-and-a-half. Against a placebo with the identical sizes shuffled at random, the variance of results is 25 to 43 percent lower, in all six tests, both periods. Knowing the regime did work that varying size at random did not. | Table A as bars with intervals and a line at 1. Table B as dots around zero, the two periods in two colours. Table C as bars below a line at 1. | Test A: 2.44 / 2.28 / 2.04 (definition), 2.08 / 1.96 / 1.76 (holdout), all intervals > 1 · Test B table · Test C: 0.57 / 0.62 / 0.62 and 0.63 / 0.64 / 0.75, all intervals < 1; clip 0.5–1.5 (`meta.size_clip`) |
| 6 | The cost | 6:10–7:40 | It isn't free. In the unseen period, at one month, the average result per trade fell from 1.34 percent to 1.04 — about a fifth of the return given up, for about a quarter less variance. Whether that's a good exchange is not something this data can settle; average returns can't be pinned down that precisely on a sample this size, which is why there's no Sharpe ratio anywhere in our work. And one thing got *worse*. The rule sizes up when markets are calm — and calm is what comes before a shock. In the unseen period the fat-tail measure at one month went from 6.5 to 16. It smooths ordinary risk and can concentrate the rare kind. | Two bars: mean 1.34 → 1.04. Then the kurtosis pair 6.5 → 16.0 with a 2020-style gap sketched behind. | "It is not free" table: holdout h=21 +1.344% → +1.042% (shuffled +1.271%) · excess kurtosis holdout h=21 6.5 → 16.0; definition 5.3 → 1.3 · 5th-percentile loss holdout h=21 −7.62% → −6.12% |
| 7 | What we got wrong, and what's merely well known | 7:40–9:10 | One of the six direction cells — one month ahead, unseen period — did exclude zero: plus 1.6 percent. By the letter of what we wrote, that trips our own stop rule. We read it as noise, because the sign flips between periods and one in six is what chance gives you — but we record it as a deviation and call one-month direction open, not settled. A sharper version of the directional idea — that a *switch* into the stressed regime predicts a fall — got zero of eighteen. And a second thing that held: in calm regimes sectors move more independently; under stress they move together, correlation up 12 to 17 points. True in both periods — and one of the best-documented facts in equity markets. Real, and nobody's secret. | The one cell highlighted among six. "0 of 18". Correlation bars calm vs stressed, both periods. | Test B holdout h=21: +1.64% (+0.27 … +3.13) · part 04 H1: 0 of 18 · part 04 H2: calm ÷ stressed dispersion 1.287 (1.105–1.495) and 1.388 (1.207–1.612); pairwise correlation stressed − calm +0.123 and +0.174 (0.403 → 0.577 in the holdout) |
| 8 | Check the next one yourself | 9:10–9:50 | Two questions. Is the claim about *how much* or *which way*? And what did it cost — what got worse? | The two questions as a card. | — |
| 9 | AMI + disclaimer | last 15 s | AMI Trade is a simulator: you direct a twelve-analyst team on simulated money. Simulation-only, no edge promised; nothing here is a recommendation to size a position in any way. | AMI end card, disclaimer. | — |

## The one idea

Volatility regime forecasts the size of the next moves, not their direction — so it is a fact about
risk, it has a price, and it is not an edge.

## What we must not say

- **Not advice.** Never "you should size down when the VIX is high", never "use this". The episode reports what was forecastable. AMI is not licensed to give investment advice.
- Not "this makes money" and not "better risk-adjusted returns". The mean went *down*. No Sharpe, no ratio with a mean in the numerator, anywhere.
- Not "the VIX predicts crashes", "predicts the market" or anything directional. Five of six direction intervals include zero and the signs flip.
- Do not hide the sixth cell. The holdout one-month direction result excludes zero and, by the letter, trips the pre-registered stop rule. It is a recorded deviation and is said on camera.
- Do not drop the kurtosis result. The rule reduces ordinary variance and can concentrate tail risk; the source says anyone building on it "needs to see that sentence".
- The regime proxy is the VIX level percentile. It is **not** the VIX futures curve and **not** dealer gamma positioning — neither was available. Say "VIX level" and never "gamma".
- The dispersion result uses nine sector funds, a conservative stand-in for single stocks. It is a stylised fact, not a discovery, and the episode says so.
- The source studies were prompted by specific practitioners' claims and name them. **The episode, its description and its pinned comment name nobody** and do not characterise anyone. See the flag below.
- One index, one country, daily bars, 2005–2026, long-only random entries. Nothing beyond that.

## Description (first 160 characters are the search snippet)

Does the VIX predict the stock market? Tested on 21 years: it forecasts how much the S&P 500
moves — about 2× — not which way. And using it has a cost.

Pre-registered before any code existed. SPY and VIX, daily, 2005–2026; every threshold fixed on
2005–2018 and the years 2019–2026 opened once. Three tests: volatility regime against future
volatility, against future direction, and regime-scaled position sizes against a placebo with the
same sizes shuffled at random. Plus what it cost in average return, the tail measure that got
worse, and one cell where our own rule went against us.

Links: study folder (pre-registration · code · outputs) · episode page · AMI Trade (UTM).
Disclaimer: educational content; AMI Trade is a simulation-only training product; nothing here is
investment advice or a recommendation to size positions in any way. By policy we test claims and
name no channel.

## Pinned comment

Pre-registered on 2026-08-30 (commits `55a66533` and `a85a6e40`), before any test ran. One
direction cell out of six excluded zero and, by the letter of our rule, should have stopped us —
we recorded it as a deviation rather than hide it (results, Test B). The sizing rule lowered the
average return and raised the tail measure in the unseen period; both are in the results. Found an
error? A verified one gets a pinned correction.

## Shorts cut-down (≤ 40 s)

"When the VIX is high, what happens next?" → bars: future volatility about 2× → "Which way? Five of
six tests: nothing. And the sign flipped." → "It forecasts how much. Not where." Full test on the
channel.

## Chart pack (from the source studies' `out/results.json`)

| Figure | Use | Notes (AMI style, 16:9, dark) |
|:--|:--|:--|
| Test A bars with intervals (to draw) | Beats 1, 5, Short | Six bars (3 horizons × 2 periods), reference line at 1.0. From part 03 `definition.AB` / `holdout.AB`. |
| Test B dots around zero (to draw) | Beats 5, 7 | Six dots with intervals, the two periods in two colours so the sign flip is visible; the one excluded cell ringed in beat 7. |
| Test C variance ratios (to draw) | Beat 5 | Six bars below a line at 1.0, from `definition.C` / `holdout.C`. |
| Cost pair (to draw) | Beat 6 | Mean per trade constant vs scaled vs shuffled, holdout h=21; kurtosis constant vs scaled, both periods at h=21. |
| Sector correlation, calm vs stressed (to draw) | Beat 7 | From part 04 `definition.H2` / `holdout.H2`. |
| Two-gauge card (to draw) | Beat 1, thumbnail | "How much" needle at the holdout h=5 ratio; "which way" at the holdout h=5 difference. |

## Compliance checklist

- [ ] No creator / channel / practitioner / contest / product referenced, on screen or spoken
- [ ] No recommendation of any kind; "what the data showed" language throughout; disclaimer line includes "not a recommendation to size positions"
- [ ] "VIX level", never "gamma"; no VIX-curve or dealer-positioning claim
- [ ] The deviation (direction, one month, holdout) stated on camera
- [ ] The cost (mean down) and the tail result (kurtosis up) stated on camera
- [ ] No Sharpe or any mean-based ratio
- [ ] Every number traced to the two source RESULTS files / their `out/results.json`
- [ ] Ends on method
- [ ] AMI by name; simulation-only; not investment advice
- [ ] EN script flagged for AR / MS translation at v1.0

## Flag before this episode (or P04 / P06) is published

The RES001 write-ups that hold this evidence name the practitioners whose claims prompted them and
pass judgement on those claims by name. RES008's publication rule is claims, not people. Before an
episode description links to a RES001 folder, either (a) link the episode page and this brief
instead, or (b) re-host a name-free summary of the evidence under RES008. Decision: Saiful.
