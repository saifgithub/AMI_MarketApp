# P20 + P21 — SCRIPT — What is real: it forecasts how much, not which way

**Episode:** week 7 · **Verdict:** `HOLDS` — as a statement about risk, not a trading signal · **From:** [`VIDEO_BRIEF.md`](VIDEO_BRIEF.md) · **Numbers:** [part 03 RESULTS](../../../RES001_finding_the_edge/03_volatility_regime_sizing/RESULTS.md), [part 03 `out/results.json`](../../../RES001_finding_the_edge/03_volatility_regime_sizing/out/results.json), [part 04 RESULTS](../../../RES001_finding_the_edge/04_gamma_transition_dispersion/RESULTS.md), [part 04 `out/results.json`](../../../RES001_finding_the_edge/04_gamma_transition_dispersion/out/results.json)
**Length:** 1,147 spoken words = 7 min 39 s of speech at 150 words a minute; with the pauses marked below (charts building in silence), ≈ 9 min 14 s · **Charts:** [`charts/`](charts/)

How to read this file: **VO** is spoken word for word. **SCREEN** is what the editor shows while it
is spoken. **№** lists every number in the beat and where it comes from — if a number is not in
that list, it must not be said. Numbers are written as they should be read aloud.

---

## 1 · Cold open — 0:00

**VO**
Does the VIX predict the stock market? We test claims like that on this channel, and mostly they
fail. This one didn't. When the VIX is in the top third of its recent range, the S and P 500 moves
about twice as much over the following week as when it's in the bottom third — and that held up on
seven and a half years the rule had never seen. What it does not tell you is which way. And using
it isn't free. We'll show you the cost, and the part that got worse.

**SCREEN** Two gauges side by side. Left, labelled "HOW MUCH", needle firmly at "2×". Right,
labelled "WHICH WAY", needle wobbling at zero.

**№** "about twice as much" — Test A, holdout h=5, `holdout.AB["5"].A_vol_ratio` = 2.08 (CI
1.69–2.58) · "seven and a half years" — holdout window 2019-01-01 → 2026-08-28 (`meta.holdout`)

## 2 · The stakes — 0:38

**VO**
Most of what gets sold as market prediction is really a claim about direction: up or down. But
there's a second, quieter idea underneath a lot of these claims — volatility. Not up or down.
Just how much prices are likely to move, in either direction, over some stretch of time. If the
only thing that's reliably forecastable is that — the size of the next move, not its direction —
then the useful question stops being "what will it do" and becomes "how exposed am I, if I'm
wrong". This episode is about that second thing. Nothing here tells you which way the market is
going.

**SCREEN** Card: "Direction → ?" fading in next to "Size of move → forecastable", the second one
highlighted.

**№** —

## 3 · What would convince us — 1:27 (speech 0:40 + 0:10 on the highlighted lines)

**VO**
Before we ran anything, we wrote down what would convince us, and committed it in public. Three
tests, each with its own way to fail. Test A: does a stressed reading forecast bigger moves than a
calm one — kill condition, the interval includes one. Test B: does regime forecast direction — here
we expected nothing, and wrote in advance that a clear directional result would make us stop and
re-scope the whole study. Test C: does sizing positions by regime beat a placebo that changes size
by exactly as much, but at random — kill condition, the interval includes one.

**SCREEN** Screen-record of `PREREGISTRATION.md` at commit `55a66533`; highlight the three test
definitions and their kill lines in turn as each is spoken.

**№** commit `55a66533` — part 03 `PREREGISTRATION.md` header · kill conditions for A and C
("95% CI includes 1.0") and B's inverted kill ("CI excludes zero") — part 03 `PREREGISTRATION.md`,
"Tests and kill criteria"

## 4 · The test — 2:17 (speech 0:58 + 0:10 for the timeline to build)

**VO**
The instrument: the S and P 500 fund and the VIX, daily, two thousand five through August this
year. The VIX is a standard measure of how much the market expects itself to move. We call a day
"stressed" or "calm" — its regime — by where yesterday's VIX sits within its own trailing two
years: bottom third counts as calm, top third as stressed, using only information available the
day before, never a peek forward.

Everything about that rule was fixed once, on the years two thousand five through twenty eighteen,
before we looked at what came next. The years twenty nineteen through twenty twenty six were then
opened exactly once, as a holdout — years the rule had never seen, held back on purpose so we
couldn't quietly tune it to fit them. Three horizons: one week, two weeks, and one month ahead.

**SCREEN** Timeline bar splitting at 2019; a VIX line above it with its bottom and top thirds
shaded. Horizon labels (5, 10, 21 trading days) appear as they're named.

**№** window 2005-01-03 → 2026-08-28, 5,448 rows — part 03 RESULTS header / `meta.rows` · definition
2005–2018, holdout 2019–2026 — `meta.definition`, `meta.holdout` · terciles (calm <33.3, stressed
>66.7), 504-day trailing window — part 03 PREREGISTRATION "Regime classification" · h ∈ {5, 10, 21}
— part 03 PREREGISTRATION "Horizons"

## 5 · The reveal — 3:25 (speech 1:41 + 0:25: each chart builds, then the next)

**VO**
Test A, how much. After a stressed day, the market's volatility over the next week ran two point
four four times a calm day's, in the years we used to build the rule. In the years the rule never
saw, still two point zero eight times. All six results, three horizons in each period, sit clearly
above one. Stressed regimes really do run hotter, and it held out of sample.

Test B, which way. Five of the six results include zero — no dependable direction. And at all
three horizons, the estimate isn't even consistent in sign between the two periods: negative in
the years we built the rule, positive in the years we tested it. That is what noise looks like,
not a signal.

Test C, does knowing the regime actually help. We scaled position size down in stressed periods and
up in calm ones, capped so no position ever got smaller than half or bigger than one and a half
times normal. Then we compared that against a placebo — the exact same set of position sizes, used
the exact same number of times, just shuffled at random onto different trades, so the only thing
missing is knowing which regime you're actually in. Against that placebo, the variance of
outcomes — how spread out the results were, trade to trade — was twenty five to forty three percent
lower, on every one of six tests, in both periods. Knowing the regime did real work that randomly
varying size did not.

**SCREEN** Chart: Test A, six bars (three horizons × two periods) with intervals, reference line at
1.0, bars landing in silence. Then chart: Test B, six dots around zero with intervals, the two
periods in two colours. Then chart: Test C, six bars below a line at 1.0.

**№** Test A definition 2.44 / 2.28 / 2.04, holdout 2.08 / 1.96 / 1.76, all six CIs above 1.0 —
`definition.AB` / `holdout.AB`, `A_vol_ratio` · Test B: 5 of 6 CIs include zero; every point estimate
negative in definition, positive in holdout — `definition.AB` / `holdout.AB`, `B_ret_diff` ·
size cap 0.5–1.5 — `meta.size_clip` · Test C definition 0.57 / 0.62 / 0.62, holdout 0.63 / 0.64 /
0.75 (i.e. 25.3–43.4% variance reduction), all six CIs below 1.0 — `definition.C` / `holdout.C`,
`C_var_ratio_scaled_vs_shuffled`

## 6 · The cost — 5:31 (speech 1:12 + 0:15 for the two bar pairs)

**VO**
It isn't free. In the years the rule never saw, at the one month horizon, the average result per
trade fell from one point three four percent to one point zero four — about a fifth of the return
given up, to buy about a quarter less variance. Whether that trade-off is worth it isn't something
this data can settle: average returns can't be pinned down precisely on a sample this size, which is
exactly why you won't find a Sharpe ratio anywhere in this series.

And one thing got worse. The rule sizes up exactly when markets are calm — and calm is what usually
comes right before a shock. We measured what statisticians call fat tails: how much more likely an
extreme outcome is than you'd expect if returns behaved like a normal bell curve. In the years the
rule never saw, that measure went from six point five to sixteen at the one month horizon — more
than double. The rule smooths ordinary, everyday risk. It can concentrate the rare kind, right when
it would hurt most.

**SCREEN** Bar pair: mean per trade, holdout h=21, 1.34% → 1.04%. Then bar pair: fat-tail measure,
holdout h=21, 6.5 → 16.0, a 2020-style gap sketched faintly behind it.

**№** holdout h=21 mean per trade: constant 1.344% → scaled 1.042% (shuffled 1.271%) —
`holdout.C["21"].mean_const` / `mean_scaled` / `mean_shuffled` · ~22% of mean given up for ~25% less
variance — same cells, `C_var_ratio_scaled_vs_shuffled` · fat-tail (excess kurtosis) holdout h=21:
6.5 → 16.0 — `holdout.C["21"].kurt_const` / `kurt_scaled`

## 7 · What we got wrong, and what's merely well known — 6:58 (speech 1:05 + 0:15)

**VO**
One result we have to be straight about. Of the six direction tests, one — the one month horizon,
in the years the rule never saw — did exclude zero: plus one point six percent. By the letter of
what we wrote down in advance, that trips our own stop rule. We read it as noise: the sign flips
between the two periods, and getting one result like this out of six is roughly what chance alone
produces. But we're recording it as a deviation, not hiding it, and we're calling one month
direction an open question, not a settled null.

One more finding, from a separate test in this series. In calm periods, sectors move more
independently of each other; under stress, they move together — the correlation between sectors
rose twelve to seventeen points, in both periods we tested. That's true, and it's also one of the
best-documented facts in equity markets. Nothing new. Just confirmed, again, in our own data.

**SCREEN** The one excluded cell ringed among the six dots from beat 5. Then bars: average
correlation between sectors, calm vs stressed, both periods shown side by side.

**№** holdout h=21 direction: +1.64% (CI +0.27 … +3.13, excludes zero) — `holdout.AB["21"].B_ret_diff`
/ `B_ci` · correlation stressed − calm: +0.123 (definition), +0.174 (holdout), i.e. 12–17 points,
both CIs exclude zero — part 04 `definition.H2` / `holdout.H2`, `corr_stressed_minus_calm`

## 8 · Check the next one yourself — 8:18 (speech 0:22 + 0:05 end card)

**VO**
Three questions for the next "this indicator predicts the market" claim you see. Is it actually a
claim about how much prices will move, or about which way? Has it been tested on later years it
never saw while it was being built? And has anyone compared it against doing the exact same thing
at random?

**SCREEN** The three questions as a card, appearing one at a time.

**№** —

## 9 · AMI + disclaimer — 8:45 (speech 0:19 + 0:10 end card) — ends ≈ 9:14

**VO**
AMI Trade is a simulator. You direct a team of twelve analysts, on simulated money, and the record
of every decision is kept for you. It is simulation-only, and it promises no edge. The test, the
code and every number from this video are in the description.

**SCREEN** AMI end card. Disclaimer card: "Educational content. AMI Trade is a simulation-only
training product. Nothing here is investment advice or a recommendation to size positions in any
way."

**№** —

---

## Production notes

- **Do not say** (from the brief): "you should size down when the VIX is high" or any other
  instruction to act · "this makes money" or "better risk-adjusted returns" (the mean went down,
  and no Sharpe or mean-numerator ratio appears anywhere) · "the VIX predicts crashes" or anything
  directional · "gamma" (the proxy here is VIX level percentile — it is not the VIX futures curve
  and not dealer gamma positioning, neither of which was available; part 03 RESULTS "What this
  implies for AMI Trade").
- The sixth direction cell (holdout, one month, +1.6%, CI excludes zero) is spoken on camera in
  beat 7, not hidden, per the brief's compliance checklist.
- The cost (mean return down) and the tail result (fat-tail measure up) are both spoken on camera
  in beat 6, per the brief's compliance checklist.
- Beat 7's sector-correlation finding is introduced as "a separate test in this series" — a
  cross-reference that does not depend on release order, since P20/P21 (week 7) may publish before
  or after other episodes.
- The dispersion/H2 result is a stylised fact restated on nine sector funds, a conservative stand-in
  for single-name dispersion (part 04 RESULTS, "H2 — dispersion rotation"); the script does not
  claim it as a discovery, matching the source.
- Numbers considered but **not spoken** because they are not needed to support a beat and widen
  exposure beyond what the brief asks for: the H1 "JEX flip" 0-of-18 result (part 04 RESULTS) — the
  brief's beat 7 only calls for the H2 dispersion finding, and H1 is about a different practitioner's
  claim that this episode does not test; the definition-window kurtosis figures (part 03
  `definition.C`, e.g. 7.7 → 3.8 at h=5) — the brief's cost beat only asks for the holdout h=21
  pair, so the definition-window kurtosis numbers are omitted rather than spoken.
- No practitioner, channel, book, course, platform or vendor is named anywhere in this script,
  including in № lines and these production notes — sources are cited only by repo-relative path
  and section, per the brief's flag on RES001 naming practitioners. Searched the finished file for
  personal names: none found.
- No instruction to buy, sell, hedge, reduce, size up or size down appears anywhere; all VO is
  descriptive ("in our data, after X, Y was larger"), never imperative.
- "VIX level" is used throughout as the descriptor of the regime proxy; "gamma" and "dealer
  positioning" are never used as a claim or a name for what the proxy measures. "Gamma" appears
  only twice: in the header's citation path to the source folder (`04_gamma_transition_dispersion/`)
  and in this note explaining the rule — neither is spoken VO.
- EN script — flag for AR / MS translation at v1.0.
