# RES003 — Results

Run 2026-08-30, seed 20260830, 10,000 bootstrap resamples, 10,000 synthetic trades per cell.
Method frozen in [PREREGISTRATION.md](PREREGISTRATION.md), committed at `55a66533` **before**
this code existed. Raw output: [out/results.json](out/results.json).

SPY + `^VIX` daily, 5,448 rows. Definition 2005–2018 (3,523 rows), holdout 2019–2026 (1,925).

## Saiful's question: lucky, or a method?

**Both answers are true, and they are not in tension.**

- **The trophy is not evidence.** A +100% month is what a contest of that size produces by
  construction (Test E).
- **The mechanism they both credit is real.** Regime predicts forward volatility by roughly
  2×, out of sample, and regime-aligned sizing beats a placebo that varies size by exactly as
  much but at random (Tests A, C).
- **It is a risk method, not a return method** — which is precisely what both of them say.
  It buys variance reduction and it is not free: it costs mean return too (Test C).

## A — regime → forward realised volatility. **Passes.**

Stressed ÷ calm mean forward realised vol, 95% CI from a stationary block bootstrap:

| h | Definition 2005–18 | Holdout 2019–26 |
|:--|:--|:--|
| 5 | **2.44** (2.06–2.89) | **2.08** (1.69–2.58) |
| 10 | **2.28** (1.84–2.84) | **1.96** (1.55–2.49) |
| 21 | **2.04** (1.55–2.68) | **1.76** (1.36–2.24) |

All six CIs sit well above 1.0. A high-VIX-percentile day is followed by about twice the
realised volatility of a low one, and the effect survives out of sample. As pre-registered,
this was expected — it is a calibration check on the instrument, not a discovery.

## B — regime → forward direction. **Null, with one flag.**

Mean forward log return, stressed − calm:

| h | Definition 2005–18 | Holdout 2019–26 |
|:--|:--|:--|
| 5 | −0.12% (−0.56 … +0.30) | +0.44% (−0.10 … +0.97) |
| 10 | −0.25% (−1.09 … +0.54) | +0.71% (−0.24 … +1.67) |
| 21 | −0.56% (−2.22 … +1.03) | **+1.64% (+0.27 … +3.13)** |

Five of six intervals contain zero. The holdout h=21 cell does not, which by the letter of
the pre-registration trips the inverted kill.

**We read it as noise, and the reason is in the table: every point estimate flips sign
between windows.** Definition is negative at all three horizons, holdout is positive at all
three. A real directional effect does not reverse its sign across the sample split; that is
what sampling noise looks like. The holdout also contains the two largest rebounds in the
series (2020 and 2022), which is the obvious mechanism for a positive high-vol/forward-return
association in that window specifically. One cell out of six crossing at the 95% level is
also roughly what multiple comparisons produce on their own.

**Recorded as a deviation from the pre-registered rule rather than hidden.** The conclusion
we draw — regime carries no dependable directional information — is the same as the
pre-registered expectation, but a future run should treat h=21 direction as an open question,
not a settled null.

## C — does regime-aligned sizing homogenise risk? **Passes, all six cells.**

Variance of per-trade P&L, vol-scaled ÷ **shuffled placebo** (identical multiset of position
sizes, randomly permuted so dispersion is the same and only the regime alignment is removed):

| h | Definition 2005–18 | Holdout 2019–26 |
|:--|:--|:--|
| 5 | **0.57** (0.48–0.68) | **0.63** (0.50–0.82) |
| 10 | **0.62** (0.50–0.77) | **0.64** (0.49–0.84) |
| 21 | **0.62** (0.48–0.83) | **0.75** (0.56–0.93) |

Every CI is below 1.0. **Knowing the regime does work that varying size at random does not** —
a 35–40% cut in per-trade variance attributable to the alignment alone. This is the result
that answers "method or habit," and it says method.

Versus constant sizing the variance ratio is 0.60–0.75, and the 5th-percentile loss shrinks
in every cell (holdout h=21: −7.62% → −6.12%).

### It is not free, and one tail got worse

Mean per-trade P&L, constant vs scaled:

| Window | h | Constant | Scaled | Shuffled |
|:--|:--|:--|:--|:--|
| Definition | 21 | +0.756% | +0.725% | +0.751% |
| Holdout | 21 | +1.344% | **+1.042%** | +1.271% |

In the holdout the rule gives up ~22% of the mean to buy ~25% of the variance. Whether that
is a good trade is not something this study can answer — mean returns are not precisely
estimable at this sample size (Lo 2002; CR136 Rev 2 dropped Sharpe and every mean-numerator
ratio for exactly this reason). **No Sharpe is computed anywhere in this study**, and the
means above are reported only so the cost is visible, not as a claim.

More interesting: excess kurtosis *fell* sharply in the definition window (7.7 → 3.8 at h=5;
5.3 → 1.3 at h=21) but **rose in the holdout at h=21 (6.5 → 16.0)**. That is the known failure
mode of inverse-vol targeting — it sizes *up* during calm, and calm precedes vol shocks, so a
2020-style gap can arrive with the book at maximum size. The rule reduces ordinary variance
and can concentrate tail risk. Anyone building on this needs to see that sentence.

## E — is a championship win evidence of skill? **No.**

Under a null of zero skill, N entrants each draw a one-month return with monthly vol *v*.
The vol at which **+100% is the *expected maximum*** across N traders:

| Entrants | Required monthly vol | As a multiple of SPY's own 5.5% |
|:--|:--|:--|
| 50 | 32.7% | 5.98× |
| 100 | 29.0% | 5.30× |
| 300 | 25.0% | 4.58× |
| 500 | 23.6% | 4.32× |

A few hundred entrants running 4–6× SPY's volatility is unremarkable for leveraged micro
futures day trading — that is roughly 85–115% annualised vol, ordinary for the instrument and
the style. **So a +100% month as the winning entry in a contest of that size is what the
contest produces by construction, with no skill required anywhere in the field.**

This does not say the champion has no method. It says the trophy carries no information about
whether he does — and Test C is where the actual evidence lives.

## What this implies for AMI Trade

The transferable claim survives: **a volatility-regime term belongs on the risk officer's
ladder, modulating size, and must not touch direction.** It is defensible on our own data,
out of sample, against a placebo.

Three constraints any build must carry:

1. **VIX term structure is unavailable** to us (`^VIX3M`/`^VIX9D`/`^VXV` return no history
   from Yahoo — verified). VIX level percentile is the substitute. It is still forward-looking
   implied vol, but it is not the curve, and it is not GEX.
2. **Direction stays out of it.** B is a null we should keep testing, not a result to build on.
3. **The tail can get worse.** Inverse-vol sizing must be capped, and the cap is doing real
   work — not a formality.

Filing a CR is the next step if Saiful wants it built. This study does not itself change
any production code.
