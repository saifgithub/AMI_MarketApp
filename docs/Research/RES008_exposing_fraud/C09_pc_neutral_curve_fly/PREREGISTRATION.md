# C09 — "PC-neutral Treasury curve fly mean reversion" — PRE-REGISTRATION

Written 2026-09-22, before any C09 code runs. Inherits [`../PREREG_COMMON.md`](../PREREG_COMMON.md)
and narrows it as stated below (fixed-income universe, yield-curve data source, and a portfolio-
construction step that `common/backtest.py`'s single-instrument engine does not natively express).

Source: MIT OCW 18.642, Fall 2024, Lecture 9, "Principal Component Analysis in Finance," guest
lecturer Stefan Andreev (Two Sigma, 18 years fixed-income quant: Morgan Stanley, Citadel, Two
Sigma). Full survey and rationale for promoting this specific lecture:
[`../R_academic_sources/R01_mit_ocw_18642/VERDICT.md`](../R_academic_sources/R01_mit_ocw_18642/VERDICT.md#the-genuine-finding-lecture-9-stefan-andreev-two-sigma--pca-in-fixed-income),
`TRACKER.md` row B15. Saiful, 2026-09-22: promote it — "run the full research."

## The claim, as taught

Slide 24 of Andreev's deck (`mit18_642_f24_lec09.pdf`): construct a PC1/PC2-neutral Treasury curve
"fly" (a 3-leg position sized so it carries zero net exposure to the first two principal components
of the yield curve — level and slope), signal off an EWMA z-score of the fly's own cumulative
returns (a mean-reversion bet on the residual, PC-neutral spread), position sized as the negative of
that z-score, one-day execution delay "to ensure actionability." Andreev's own on-slide backtest,
2000–2024, reports **Sharpe Ratio = 0.09** — a weak number he presents plainly, next to a chart
showing multi-year negative drift from ~2008 onward. He does not claim this is a standalone strategy
Two Sigma runs; the next two slides ("PCA Limitations," "Ideas for Final Project") explicitly frame
it as a mechanism illustration and invite students to test lookback-window robustness themselves.

**What we are testing is the mechanism, not his number.** RES008 never tests via Sharpe ratio (see
`PREREG_COMMON.md`), so 0.09 is not a bar to clear or miss — it's the reason this claim is a fair
promotion in the first place (a disclosed mechanism with an honest self-reported result, not an
inflated one). The question we pre-register: does a PC-neutral Treasury curve fly, built exactly on
Andreev's construction, beat (a) a matched-notional random-entry placebo and/or (b) a naive unhedged
curve trade of the same thesis, net of costs, over RES008's fixed windows?

## Disclosed deviations from `PREREG_COMMON.md` and from Andreev's exact construction

1. **New universe, `U-RATES`** (fixed-income duration buckets, not `U-EQ`/`U-CRYPTO`/`U-FX`) —
   see below. `PREREG_COMMON.md` permits a claim file to narrow it with a stated universe; this is
   that narrowing, not a deviation from method.
2. **PCA estimation uses Andreev's own primary data source** (U.S. Treasury daily par yield curve,
   `home.treasury.gov`, the same source cited on his slides) — untradeable spot yields, used only
   to *estimate* the PC loadings and the fly's hedge ratios. This matches his construction exactly.
3. **Execution/P&L uses tradeable duration-bucket ETFs, not the untradeable yield curve itself** —
   Andreev's own slides price the fly directly in yield-space (basis points of yield, converted to
   a notional P&L via DV01), which has no cost model and no real fill mechanism. RES008 never tests
   a synthetic, untradeable spread; every claim here is priced through real, liquid, next-open-fill
   instruments with real costs. This is a genuine adaptation of his mechanism into something with a
   real net-of-costs answer — flagged explicitly as a deviation from "exactly what the slide prices"
   even though it is the same PC-neutral construction, same signal, same lookback.
4. **No leverage, no repo/financing cost model.** Andreev's own "Pros/Cons" slide states a PC-neutral
   fly needs "much higher notional traded... requires financing of the bond and long positions" to
   hit the same target vol as an unhedged trade. RES008 does not model financing cost or leverage
   anywhere (`PREREG_COMMON.md`); this test compares the *hedged* and *unhedged* constructions at
   their natural (unlevered) notional, which understates the hedged version's real-world cost
   relative to Andreev's vol-matched comparison — disclosed here so a smaller apparent edge for the
   PC-neutral fly is not mistaken for a fair like-for-like against his slide 33 example.

## Universe — `U-RATES` (new, fixed-income duration buckets)

| Ticker | Bucket | Approx. duration |
|:--|:--|:--|
| `SHY` | 1–3 year Treasury | ~1.9y |
| `IEI` | 3–7 year Treasury | ~4.6y |
| `IEF` | 7–10 year Treasury | ~7.5y |
| `TLH` | 10–20 year Treasury | ~12.6y |
| `TLT` | 20+ year Treasury | ~17.5y |

All five are iShares Treasury ETFs chosen for liquidity and the longest available histories among
duration-bucket Treasury ETFs (`SHY`/`IEF`/`TLT` since 2002-07, `IEI`/`TLH` since 2007-01). Standing
in for "the curve" at five points, roughly matching Andreev's 2/5/10/30-year tenor examples without
requiring futures-margin accounting RES008 has no model for. PCA loadings themselves are estimated
from the actual Treasury par-yield tenors (see below), not from the ETFs — the ETFs are the
execution layer only.

## Data

- **Yield curve (PCA estimation only):** U.S. Treasury daily par yield curve, downloaded per
  calendar year from `home.treasury.gov`'s published CSV
  (`daily-treasury-rates.csv/{YEAR}/all?type=daily_treasury_yield_curve&field_tdr_date_value={YEAR}&page&_format=csv`),
  columns `2 Yr`, `5 Yr`, `7 Yr`, `10 Yr`, `20 Yr`, `30 Yr` (Andreev's own tenor selection, slide 8).
  Cached locally under `code/cache/`, not committed (mirrors `common/data.py`'s convention).
- **Execution instruments:** `U-RATES` ETFs above, daily OHLCV via `common/data.py::load_daily`
  (adjusted, cached, `PREREG_COMMON.md`'s standard).

## Windows (fixed, per `PREREG_COMMON.md` with a stated exception)

- `DEFINE` 2007-01-01 → 2018-12-31 (all five `U-RATES` members have data from 2007-01 onward —
  `IEI`/`TLH` inception — so `DEFINE` starts later than `PREREG_COMMON.md`'s default 2005-01-01;
  this is the stated exception the common file allows for instruments with shorter history).
- `HOLDOUT` 2019-01-01 → 2026-08-31 (unchanged from `PREREG_COMMON.md`).
- PC loadings are estimated on a rolling 2-year lookback of daily yield changes (Andreev's own
  window, slide 11), refit daily, using only data available at or before that day's close — no
  lookahead. The first ~2 years of `DEFINE` (2007-01 → 2008-12) therefore has no tradeable signal
  and is excluded from all reported statistics; it exists only to seed the rolling window.

## Construction, specified exactly (per Andreev, slides 10–11, 20, 24)

1. **Daily yield changes.** For each date *t*, Δy(t) = yield(t) − yield(t−1) across the six
   Treasury par tenors (`2Yr, 5Yr, 7Yr, 10Yr, 20Yr, 30Yr`).
2. **Rolling PCA.** On each date *t*, fit PCA (via SVD on the demeaned, non-standardized Δy
   covariance — Andreev's slide 5 uses raw yield changes, not standardized, since all tenors share
   units) over the trailing 2 years (≈504 trading days) of Δy, using only data through *t*. Take the
   first two components: PC1 (level — loadings roughly equal-signed across tenors) and PC2 (slope —
   loadings roughly monotonic in tenor, opposite-signed at the short vs. long end). Sign convention:
   fixed at each refit date so PC1's mean loading is positive (loadings and signals are otherwise
   sign-ambiguous from SVD alone).
3. **PC-neutral fly, mapped onto `U-RATES`.** Using the loadings on the tenors nearest each ETF's
   duration bucket (`SHY`≈2Yr, `IEI`≈5Yr, `IEF`≈7Yr/10Yr midpoint, `TLH`≈20Yr, `TLT`≈30Yr), solve for
   portfolio weights `w` across the five ETFs such that the resulting position has zero net loading
   on PC1 and PC2 simultaneously (a linear system: 2 constraints, 5 instruments, solved via
   least-squares to the minimum-notional solution when underdetermined) — Andreev's "PC-neutral
   fly" extended from his 3-leg treasury example to `U-RATES`'s 5 buckets, same neutrality
   condition (slides 20–21).
4. **Signal.** Daily fly return = `w · r_ETF(t)` (weighted ETF returns, not yield changes, once in
   the execution layer). EWMA z-score of the cumulative fly return series (Andreev's own smoothing;
   default half-life 20 trading days, the standard EWMA span used for daily vol estimates elsewhere
   in this repo's `common/`). Position size = `-z_score`, capped at ±3 (a stated cap Andreev's own
   slide does not specify a number for; ±3 is disclosed here, not tuned post-hoc, and matches this
   repo's existing scalar-signal convention).
5. **One-day execution delay** ("to ensure actionability," Andreev's own phrase, slide 24) — signal
   computed on close(t), position taken at open(t+1). This is exactly RES008's `next_open` default
   in `common/backtest.py`; no custom engine needed for this leg.
6. **Costs.** 5 bps per side per ETF leg (equities/ETF rate from `PREREG_COMMON.md`), charged on
   every notional change in every one of the five legs, every day the composite position's weights
   change (turnover is expected to be higher than a single-instrument RES008 test — a 5-leg
   portfolio rebalanced daily by a continuously-varying z-score — and is reported explicitly since
   turnover-driven cost drag is itself part of what "beats buy-and-hold net of costs" must survive).

## Arms

- **Arm A — PC-neutral fly (the claim).** The construction above, positions in all five `U-RATES`
  legs simultaneously, net PC1/PC2 exposure ≈ 0 by construction, net notional scaled to a fixed
  total gross exposure (not vol-targeted — no financing-cost model exists here to make a vol-target
  comparison fair; see "Disclosed deviations" #4).
- **Arm B — naive unhedged curve trade (same thesis, no PC-neutrality).** The same EWMA
  mean-reversion signal applied directly to a single 2s10s-style spread trade (`IEF` minus `SHY`,
  the closest `U-RATES` analogue to Andreev's slide-33 comparison), same signal construction, same
  execution delay, same costs, no PC-hedging step. Tests specifically whether the PC-neutrality
  step (not just "mean-reversion on a curve spread") is what does any work.
- **Arm C — matched random-entry placebo.** `common/placebo.py::matched_random_entries` applied to
  Arm A's realized trade list (same count, same holding-period multiset, same costs), matching
  RES008's standard placebo control (`PREREG_COMMON.md`'s "skill" test).
- **Arm D — buy-and-hold benchmark**, each `U-RATES` member individually and an equal-weight
  `U-RATES` basket (`PREREG_COMMON.md`'s "worth doing" test).

## Statistics

Per `PREREG_COMMON.md`: stationary block bootstrap (5,000 resamples, 95% percentile, fixed seed) on
Arm A vs. Arm C (skill) and Arm A vs. Arm D (worth doing). No Sharpe ratio anywhere in the reported
results — Andreev's own 0.09 is quoted once, in this file and in `RESULTS.md`'s framing section, as
the source claim's own number, never recomputed or relied on as our metric. No annualized figure
from a window under three years (both `DEFINE` and `HOLDOUT` clear this once the 2-year PCA seed
period is excluded). No p-values.

## Our hypothesis

H1 (mechanism does nothing net of costs): Arm A's `HOLDOUT` total return, net of costs, does not
beat Arm C's placebo distribution's 95% interval, and does not beat Arm D's buy-and-hold on the same
instruments. A 5-leg daily-rebalanced portfolio pays cost drag on every one of ~5 legs on most
trading days as the continuous z-score signal shifts weights, which is expected to be materially
larger than Andreev's own frictionless yield-space accounting disclosed — consistent with his own
weak (0.09) self-reported Sharpe and his own slide's stated cost/vol-ratio warning.

H2 (PC-neutrality specifically adds nothing over naive mean-reversion): Arm A does not clear Arm B
by more than bootstrap noise — i.e. hedging out level/slope does not, on its own, turn a mean-
reversion signal on curve spreads into something that clears a placebo, matching Andreev's own
"PCA does not imply a causal relationship" limitations slide.

## What would support the claim instead

- Arm A clears both Arm C (skill) and Arm D (worth doing) on `HOLDOUT`, with the bootstrap interval
  excluding zero — a real, if modest, PC-neutral curve-fly edge net of costs, which would be a
  genuinely rare finding for this project (the first `HOLDS` or `PARTLY HOLDS` sourced from a
  disclosed, honest, practitioner-taught mechanism rather than an overclaimed one).
- Arm A meaningfully outperforms Arm B (PC-neutrality is doing real work, not just curve-spread mean
  reversion in general) — would validate the specific value of Andreev's hedging construction, not
  merely "curve spreads mean-revert."

## Not claimed

We are not testing Andreev's own 2000–2024 backtest number, his slide-33 German-DAX/PC1-neutral
equity-hedging example (explicitly a one-year mechanism illustration per his own limitations slide,
not a repeatable strategy — see `R_academic_sources/R01_mit_ocw_18642/VERDICT.md`), or any claim
that Two Sigma runs this as a standalone strategy. We are testing the mechanism he disclosed,
mapped honestly onto tradeable instruments, against RES008's own fixed bar.
