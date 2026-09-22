# C09 — RESULTS — "PC-neutral Treasury curve fly mean reversion"

**Verdict: `NOT SUPPORTED`.** Pre-registration written 2026-09-22, before any code ran. Run:
2026-09-22 · `U-RATES` (SHY/IEI/IEF/TLH/TLT) daily bars 2007-01 → 2026-08, Treasury.gov daily par
yield curve 2007-01 → 2026-08 for PCA estimation · `code/01_run_test.py` · every figure below is in
[`out/results.json`](out/results.json).

Both pre-registered hypotheses (H1: mechanism does not beat costs/placebo; H2: PC-neutrality adds
nothing over naive mean-reversion) held. Neither "what would support the claim instead" condition
was met.

---

## 1. Deviations from pre-registration

| # | What | Why it matters |
|:--|:--|:--|
| 1 | None beyond what `PREREGISTRATION.md` already disclosed up front (the `U-RATES` universe, the ETF-vs-yield execution split, the no-financing-cost simplification, the DEFINE window starting 2007 not 2005). No post-hoc changes to signal, universe, costs, or windows. | Pre-registration held exactly as written. |

## 2. Headline numbers (HOLDOUT, 2019-01-01 → 2026-08-31, net of costs)

| Arm | Total return | 95% CI (block bootstrap) | Trades |
|:--|--:|:--|--:|
| **A — PC-neutral fly (the claim)** | **−23.8%** | [−27.8%, −19.8%] | 2,305 (across 5 legs) |
| B — naive unhedged IEF−SHY spread | −38.6% | [−54.7%, −18.0%] | 878 |
| D — buy-and-hold, equal-weight `U-RATES` basket | +3.3% | — | — |
| D — buy-and-hold, per instrument | SHY +16.6% · IEI +12.8% · IEF +7.1% · TLH −7.6% · TLT −14.9% | — | — |

**Arm A vs. Arm D (worth doing?):** paired difference −27.1 points, 95% CI **[−82.0, +7.9]** points.
The interval's upper edge nearly reaches zero, but the point estimate and most of the interval sit
deep in negative territory — buy-and-hold clearly the better outcome over this window, not a clean
statistical loss but nowhere close to a win either.

**Arm A vs. Arm C, the placebo (skill?):** per `U-RATES` leg, 500 matched random-entry replications
(same trade count, same holding-period multiset, same costs) on the same HOLDOUT window:

| Leg | Placebo mean return | Arm A's leg contribution is not separately reported (composite position), but Arm A's total (−23.8%) sits **inside** this cluster, not below it |
|:--|--:|:--|
| SHY | −18.9% | |
| IEI | −20.9% | |
| IEF | −19.7% | |
| TLH | −20.2% | |
| TLT | −22.0% | |

The random-entry placebo, matched only on trade count/holding-period/costs with **zero signal**,
loses about as much as Arm A does. This is the single most important number in this test: it means
Arm A's negative return is **not a signal-quality failure** distinguishable from noise — a
zero-information control trading the same instruments, same frequency, same costs, over the same
window loses a similar amount. The story here is dominated by turnover cost drag and negative carry
during a rising-rate period (2019–2023 real yields), which any high-frequency long/short construction
in this instrument set would have suffered, signal or no signal.

**Arm A vs. Arm B (does PC-neutrality specifically help?):** paired difference +14.8 points, 95% CI
**[−3.6, +28.5]** points — includes zero. Arm A's point estimate is better than Arm B's, but not
distinguishably so at 95% confidence. H2 (PC-neutrality adds nothing over naive mean-reversion) is
not cleanly falsified, but it is not cleanly supported either — read as "consistent with no
detectable benefit from the hedging step, on this data," not "proven equivalent."

## 3. DEFINE window (2007–2018), for context only

Not part of the verdict (HOLDOUT is the pre-registered test window), but consistent with the same
story: Arm A −28.7% (CI [−34.5%, −22.9%]), Arm B −60.3% — both arms lose money across the 2007-2018
window too, which spans the entire 2008 crisis and taper-tantrum period Andreev's own slides flag as
loading-instability episodes. A PC-neutral construction refit daily is expected to churn hardest
exactly when PC loadings are least stable, which is exactly when this window's worst drawdowns
cluster.

## 4. Why this result, in Andreev's own terms

Andreev's own "Pros/Cons" slide (quoted in `PREREGISTRATION.md` and the source VERDICT.md) warned
that a PC-neutral fly's "transaction cost / volatility ratio is much higher" than an unhedged trade
and "requires much higher notional traded to achieve the same target volatility." This test's
result is a direct, real-cost demonstration of exactly that warning: a 5-leg, daily-rebalanced,
continuously-resized position pays cost drag on most trading days, and that drag — not a flawed
PC-neutrality construction — is the dominant force in this result (the placebo comparison in §2
makes this precise: zero-signal random entries in the same instruments lose a comparable amount).
This is consistent with, not a refutation of, Andreev's own self-reported weak Sharpe (0.09,
2000–2024, his own frictionless yield-space accounting) — his own number already signaled this
mechanism does not clear a meaningful bar even before RES008's real-ETF cost model was applied.

## 5. What this does and does not say about Andreev's material

This result does **not** mean Stefan Andreev's teaching was wrong, misleading, or overclaimed — the
opposite is the point of promoting this claim in the first place (see
[`../R_academic_sources/R01_mit_ocw_18642/VERDICT.md`](../R_academic_sources/R01_mit_ocw_18642/VERDICT.md)).
He disclosed a weak, honestly-reported number and explicitly framed the construction as a mechanism
illustration, not a strategy recommendation — RES008's own real-cost, real-instrument test landing
at "does not beat buy-and-hold, does not clearly beat a placebo" is the outcome his own slide
predicted, just measured independently and on tradeable instruments rather than his frictionless
yield-space accounting. This is the rare case where a `NOT SUPPORTED` verdict corroborates the
source's own honesty rather than exposing an overclaim — worth stating plainly, since every other
`NOT SUPPORTED`/`DISPROVED` verdict in this project has been the latter.

## 6. Revisit if

- Someone wants to test a lower-turnover variant (e.g. weekly rather than daily rebalancing, or a
  wider EWMA half-life) — this test used Andreev's own daily-refit, 20-day half-life construction
  exactly as taught; a materially different parameterization would be a new claim, not a re-run of
  this one.
- Treasury futures (rather than ETFs) become modelable in this repo — futures carry no financing
  drag the way a levered ETF-notional position implicitly does, and would remove the single largest
  disclosed deviation from Andreev's own frictionless construction (`PREREGISTRATION.md` §"Disclosed
  deviations" #4). This is the most likely reason a futures-based re-run could land differently.
