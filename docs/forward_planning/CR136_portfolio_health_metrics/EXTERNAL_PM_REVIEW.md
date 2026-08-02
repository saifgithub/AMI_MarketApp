# CR136 Portfolio Health — external review

**Reviewer:** independent portfolio manager, acting as the "hostile reader" the CR
names as its audience.
**Scope:** `CR136_portfolio_health_metrics.md` (Rev 3), `PORTFOLIO_REVIEW_METHODOLOGY.md`
(v1.0), `SCREEN_DESIGNS.md`.
**Date:** 2026-08-02. **Status:** review only — no spec changed by this document.

---

## 0. The short answer

You asked whether this meets my needs. Two honest answers, and they differ.

**As statistics: better than almost anything retail.** Every quantitative claim in the
pack was independently re-derived from its own stated formula rather than taken on
trust. Lo's confidence interval, the 971-day threshold, the standard-error asymmetry
table, √(252/365) = 0.831, the DR²/HHI closed forms, the 60/40 DR² = 1.54 probe, the
Euler identity with a cash row, the risk-free-rate arithmetic, the drawdown example, the
FMR patent attribution — **all confirmed.** The governing principle (ship second
moments, refuse mean-return terms) is correct, correctly derived, correctly applied.
Dropping Sharpe was right. I do not often say that about a retail product.

**As a portfolio review: no, not as specified.** Of the ten questions I ask about a
book, this answers three. Underneath the good statistics sit **six defects that produce
confidently wrong output** — the failure class your own CR040/DEF059 doctrine exists to
prevent — and a **compliance exposure that contradicts a claim on your own live
website**.

The two most serious were not visible from the mathematics alone; they emerge only when
you compose the pack's own pinned decisions with each other.

| # | Finding | Severity |
|---|---|---|
| **F1** | **The cash row divides by zero inside the pinned shrinkage target.** Two of the hardest pins in the CR are numerically incompatible; the result serialises to the same `null` that means "insufficient data" | **Blocker** |
| **F2** | **The pinned estimator suppresses the warning the feature exists to give.** LW shrinkage fires the diversification rule in 29.6% of windows where the plain sample covariance fires it in 89.0% | **Blocker** |
| **F3** | **Rule R1's central claim is mathematically false** — it names the wrong holding and asserts the opposite of the truth | **Blocker** |
| **F4** | The rule engine **fires on point estimates at hard thresholds**; R3 is a coin flip | **Blocker** |
| **F5** | R3's sentence is a **return projection**, forbidden three times in the same document | **Blocker** |
| **F6** | **§F5 is personalised investment advice**, and shipping it makes a live public statement false | **Blocker** |
| F7 | The **fat-tail standard error is wrong by 2.1×**, and it justifies your sufficiency floor | Major |
| F8 | The **nominated acceptance test cannot detect the estimator's worst failure mode** | Major |
| F9 | The signature "risk vs money" visual is **substantially a cash artefact** | Major |
| F10 | Realised max drawdown is a **monotone ratchet** | Major |
| F11 | **Rolling-window echo**: risk numbers jump on days nothing happened | Major |
| F12 | You cite **TEV** and ship absolute volatility | Major |
| F13 | **VaR excluded for a reason that is factually wrong** | Major |
| F14 | Beta is a **backcast**, and no document says so | Major |
| F15 | The **validator is not implementable as specified**, and R3 fails it | Major |
| F16 | **No model validation** — code tested against numpy, model never against reality | Major |
| F17 | **T/N ≥ 5 has no basis for σₚ** and bars any book over 50 names, forever | Major |
| F18 | **No factor model**, and your IPO drop-rule has no institutional precedent | Major |
| F19 | The **register split is enforced by prompt instruction alone** — your own doctrine forbids that | Major |
| F20 | The feature **cannot ship at all** on the current data layer | Delivery |

---

## 1. Credit where it is due

**1.1 The estimability principle is right, and rare.** SE(mean) = σ/√years vs
SE(σ̂) ≈ σ/√(2T) is the correct asymmetry and your table is arithmetically correct.
Most retail products ship a Sharpe ratio. You worked out why you can't, and didn't.
That is the best decision in the pack.

**1.2 Your Lo numbers are exact**, verified against Lo's Eq. 9 (and his own Table 1
worked example reproduces: SE = 0.188 at SR = 1.50, T = 60).

*Free upgrade:* 971 days is a **50%-power** threshold — the sample size at which an
estimate landing exactly on the truth just barely excludes zero. 80% power needs
**1,982 trading days (7.9 years)**; 90% power needs 2,654 (10.5 years). Your argument is
twice as strong as you stated it. Restate it, or a reviewer who knows power analysis
will read "971 days to be distinguishable" as confusing a confidence interval with a
power calculation and use that against the rest.

**1.3 DR² over naive HHI is correct**, and 8.2× checks out. *Understated:* "up to 8.2×"
implies a ceiling. There is none — at N = 30, ρ = 0.8 it is **24.2×**. Drop "up to".

**1.4 Euler risk decomposition is the right headline.** It is what institutional risk
desks lead with, the identity holds exactly with your cash row, and "X% of your risk
from Y% of your money" is the highest-teaching-value sentence in the feature.

**1.5 You never invert Σ — and that cuts both ways.** Every horror story in the
covariance-estimation literature (Marchenko–Pastur dispersion, minimum-variance
blowups, the Ledoit–Wolf motivation itself) concerns **Σ⁻¹**. You compute quadratic
forms and one matrix–vector product. Measured: the relative sampling error of σ̂ₚ is
1/√(2T) **independent of N** — 6.20%–6.56% across N = 5…200 at T = 126, and still that
precise at N = 200 where the sample covariance is *singular* (rank 125). A fixed weight
vector never gets to select the smallest eigenvector.

This is your strongest defence against "sample covariance at T/N = 5 is garbage" and the
pack never makes it. **But it is also the reason your pinned estimator is wrong** — see
F2 — and the reason T/N ≥ 5 has no basis for σₚ — see F17. You inherited the remedy
without having the disease.

**1.6 The uncertainty contract with hard nulls is structurally right.**
`sufficient:false ⇒ null, never 0.0` is the correct enforcement primitive; stripping
insufficient blocks pre-assembly is the correct architecture; `engine_version` on
archived artefacts is correct.

---

## 2. Blockers

### F1 — The cash row divides by zero inside the pinned shrinkage target · **BLOCKER**

Two of the estimator pins are numerically incompatible.

- Pin A: *"`w` spans total portfolio value, cash included as a zero-vol row."*
- Pin B: *the estimator is the constant-correlation target of "Honey, I Shrunk the
  Sample Covariance Matrix".*

The constant-correlation target is `f_ij = r̄·√(s_ii·s_jj)`, and `r̄` is the mean of
`s_ij/√(s_ii·s_jj)`. With cash in the matrix, `s_cash,cash = 0` **exactly**, so every
term involving the cash row divides by zero.

Demonstrated on a 6-risky + cash panel at T = 126: **42 of 49 entries of both the target
and the shrunk matrix are NaN**, δ reports 1.0, and σₚ evaluates to `nan`.

A NaN reaching the JSON serialiser becomes `null` — and in your contract `null` means
*insufficient data*. So the failure presents as "not enough data yet," to every user,
forever, for a reason that has nothing to do with data sufficiency. That is precisely
the DEF038/DEF063 silent-dark-feature pattern your own conventions section names.

**Fix (specify it, don't leave it to build time).** Estimate Σ over risky holdings only,
shrink there, then append the cash row (zero variance, zero covariance). The Euler
identity and the total-value weight convention both still hold exactly.

**Related, same root:** the estimator is undefined at **N = 1** (the `r̄` denominator
`N(N−1)` is zero) and degenerate at **N = 2** (the target equals the sample covariance
exactly, so `γ̂ = ‖S − F‖²_F = 0` and `κ̂ = (π̂ − ρ̂)/0`; δ clamps to 1.0 by accident).
Both survive only by luck, and a two-stock book reporting "100% shrinkage" is
indefensible once δ is disclosed. A retail simulator produces N = 1 and N = 2 books
constantly. Short-circuit both explicitly and add them to the boundary tests.

### F2 — The pinned estimator suppresses the exact risk the feature exists to reveal · **BLOCKER**

This is the finding I would lead with if I only had one.

Ledoit–Wolf constant-correlation shrinkage replaces every pairwise correlation with a
blend toward the book's *average* correlation. On a concentrated book, the thing that
dominates portfolio variance is precisely the *anomalously high* correlation between the
two large holdings — and that is exactly the term the target deletes.

Monte Carlo, 4,000 reps, N = 10, all pairs ρ = 0.30 except one 0.85-correlated pair
carrying 30% weight each. **True DR² = 1.855**, so rule R2 (DR² < 2.0) *should* fire:

| | plain sample Σ | Ledoit–Wolf shrunk |
|---|---|---|
| R2 fires (T = 126) | **89.0%** | **29.6%** |
| R2 fires (T = 252) | 95.5% | 56.5% |
| measured DR² (T = 126) | 1.863 (+0.5%) | 2.075 (**+11.8%**, across the rule line) |
| measured σₚ (T = 126) | — | 19.76% vs true 20.98% (**5.9% too low**) |
| top risk-contribution share | — | −1.68 pp |

The mechanism is deterministic, not sampling noise. **The estimator you pinned tells
concentrated users their book is more diversified and less volatile than it is** — and
concentrated users are the population this feature exists to reach.

A 54-cell RMSE sweep (N ∈ {10,20,25} × T ∈ {126,252} × ρ̄ ∈ {.25,.40,.55} × 3 weight
profiles) has LW beating the sample covariance in 24/54 cells for σₚ, 22/54 for DR²,
21/54 for the top risk share. On twin-heavy books — the exact shape R2 targets — it is
**2/18, 0/18 and 3/18**.

**Why this happened:** Ledoit & Wolf's estimator is optimal for Frobenius loss on Σ so
that a mean–variance *optimiser* does not error-maximise on **Σ⁻¹**. CR136 never
optimises and never inverts. You adopted the remedy for a disease you don't have, and
the remedy has a side effect that lands on your headline metric.

**And δ is large and undisclosed.** Measured on real daily data (2021-08-03 → 2026-07-31,
rolling windows, 10-name tech-heavy book): δ median **0.476** at T = 126, P(δ > 0.50) =
46.9%, **P(δ = 1.00, the clamp) = 16.4%** — rising to 25.1% at T = 252. Under
multivariate-t(5) tails δ inflates ~60%, i.e. **shrinkage is heaviest exactly when the
constant-correlation prior is least likely to hold.** At δ = 1 the matrix contains no
estimated correlation structure at all: every pair is one scalar.

**Fix.** Compute σₚ, DR² and the risk shares from the plain sample covariance. If you
keep shrinkage for report-to-report stability, that is a legitimate but *different*
rationale — say so, fire R2 off the unshrunk DR², publish δ in every block derived from
Σ, and force `sufficient:false` for DR² and risk contributions above a δ threshold
(0.7 is defensible given the measured errors). Replace "shrinkage is the standard fix
for short-sample covariance instability" with the truth: it buys stability at the cost
of understating concentration.

### F3 — Rule R1's central claim is mathematically false · **BLOCKER**

R1 fires on the largest **risk share** and tells the user:

> "Trimming it reduces total risk more per dollar than any other single change."

Per-dollar reduction is governed by the **marginal** contribution MCRᵢ = (Σw)ᵢ/σₚ.
Total contribution is RCᵢ = wᵢ·MCRᵢ. Because RC is MCR *scaled by weight*, `argmax RC`
equals `argmax MCR` only when weights are equal or comonotone with MCR. A large calm
holding routinely tops the risk-share table while a small wild one has the higher MCR.

**Counterexample** (long-only, funded to cash, ρ(A,B) = 0.15, σₚ = 11.76%):

| | weight | vol | MCR | risk share |
|---|---|---|---|---|
| A | 60% | 16% | 0.1419 | **72.4%** |
| B | 10% | 55% | **0.3246** | 27.6% |
| Cash | 30% | 0% | 0.0000 | 0.0% |

R1 fires on **A** and asserts trimming A is the best per-dollar cut. Direct
recomputation of σₚ:

- trim 1% of portfolio value from **A** → 11.7580% → 11.6164% (**−14.2 bp**)
- trim 1% of portfolio value from **B** → 11.7580% → 11.4420% (**−31.6 bp**)

**Trimming B is 2.2× more effective per dollar.** R1 names A and states the opposite. In
the limit this rule can name the single *worst* per-dollar trim in the book. Your
track-U round 1 reported confirming C1–C5 and did not catch it.

Two further defects in the same template:

- **No funding convention.** "Trimming" is undefined until you say what the proceeds
  buy; trim-to-cash and trim-pro-rata give different rankings.
- **Mixed denominators.** `{risk_share}` is invested-sleeve-based (cash contributes
  zero risk) while `{weight}` is total-value-based. The sentence compares two
  different bases, and the gap it shows is inflated by cash (F9).

**Fix.** Rank on MCR — you already compute Σw, so it is free — or reword to a true
statement: *"NVDA accounts for 62% of your portfolio's risk while holding 30% of its
value."* Correct, needs no funding convention, loses nothing pedagogically.

### F4 — The rule engine fires on point estimates · **BLOCKER**

The pack is built on the premise that a point estimate without its uncertainty is
dangerous. That premise is enforced to the LLM boundary and then abandoned: R1/R2/R3
fire on bare point estimates at hard cliffs. DR² and risk-contribution standard errors
are declared `null by decision` — the one number that could gate them.

3,000 independent 126-day windows of the **same unchanged portfolio**:

| Rule | true value | fires in |
|---|---|---|
| R3 β ≥ 1.3 | β = **1.20** | 12.4% |
| R3 β ≥ 1.3 | β = **1.30** | **49.1%** |
| R3 β ≥ 1.3 | β = **1.40** | 86.0% |
| R1 risk share ≥ 40% | 40.4% | 55.3% |
| R2 DR² < 2.0 | 2.02 | 45.4% |

SE(β̂) = 0.090 at T = 126, so **any book whose true beta lies between ~1.20 and ~1.45
will switch R3 on and off between reports with nothing having changed.** From the
regression side: at your R² = 0.20 floor, SE(β̂)/β̂ = 0.1796, so β̂ = 1.30 carries a 95%
CI of **[0.84, 1.76] — containing 1.00**. R3 announces "your portfolio amplifies the
market" on a number statistically indistinguishable from one that doesn't. False-fire
rate at true β = 1.00: 2.7–6.0%. Power at true β = 1.30: 50.3%.

R1 and R2 are better behaved away from their thresholds — but all three are unstable
*at* the threshold, where a threshold rule lives.

Worse because the Finding is **archived in the journal**: consecutive reports sit
adjacent in a timeline, so the user sees advice appear and vanish and reasonably infers
their portfolio changed.

**Fix.** Fire on the confidence bound, not the point estimate; or add hysteresis (fire
at 1.35, clear at 1.25). Institutional rebalancing has used no-trade tolerance bands for
this exact reason for decades.

### F5 — R3 makes a return projection, forbidden three times in the same document · **BLOCKER**

> "A 10% market move has historically meant ~{beta_x10}% for this book over the window."

1. **A forecast in the grammar of a fact.** Your prompt skeleton says verbatim *"Never
   make return predictions or performance claims."* §F2 forbids *"any mean-return or
   performance claim."* The Finding standard forbids *"no claim outside the payload."*
2. **"Historically meant" describes history that does not exist** — Tier 1 has no
   portfolio return series (F14).
3. **A daily beta does not transfer to a 10% move.** The intervalling effect (Cohen,
   Hawawini, Maier, Schwartz & Whitcomb, *Management Science* 29(1), 1983; Hawawini
   1983; Scholes–Williams 1977; Dimson 1979) makes beta horizon-dependent, and for
   large, liquid names daily beta **overstates** the longer-horizon beta — a US
   mega-cap retail book is on the overstating side (simulated: daily β 1.050 vs monthly
   0.963, +9%, sign reversing for illiquid names). A 10% index move is also a multi-day
   event, not a daily one.

**Fix.** Delete the projection clause. "β = 1.4 (R² = 0.62, 126 days) — this book has
moved about 1.4× as much as the S&P 500 over the measurement window" is true, useful,
and carries no forecast.

### F6 — §F5 is personalised investment advice, and it falsifies a live public claim · **BLOCKER**

The section is titled "Actionable recommendations," each item carries a **severity
band**, and the templates name the user's own tickers and prescribe actions on them. The
entire mitigation is one sentence asserting the actions are "inside the sim."

Three things make this worse than it looks:

**The publisher's exclusion is unavailable.** 15 U.S.C. §80b-2(a)(11)(D) covers only a
*"bona fide newspaper, news magazine or business or financial publication of general and
regular circulation."* Lowe v. SEC, 472 U.S. 181 (1985) conditions it on impersonality —
communications must remain *"entirely impersonal"* — and SEC Rule 203A-3(a)(3) defines
impersonal advice as services *"that do not purport to meet the objectives or needs of
specific individuals or accounts."* A Finding is generated per `portfolio_id`, from that
account's own holdings, archived to that user's journal. It is account-specific by
construction and has no circulation at all. Do not rely on this exclusion in any memo.

**The perimeter is live at alpha, not at v1.0.** App Store and Play distribution
defaults to worldwide, so the UK (FCA regulated-advice perimeter), EU (MiFID II Art
4(1)(4) "personal recommendation"), Saudi CMA and Malaysian SC definitions are all in
scope now, regardless of the roadmap saying US-only at MVP. Google Play's financial
services policy names personalised advice explicitly; Apple 3.2.1(viii) is adjacent.

**It contradicts your own live website.** `website_api/app/knowledge/faq.md:45` states
the product *"does not and will not give investment advice"*, and the concierge refuses
buy/sell calls (`faq_answer.py:103`). Shipping §F5 as drafted makes a public
representation false — a misrepresentation exposure independent of licensing, and the
first inconsistency any complainant or app reviewer will find, because it is on the open
web.

**And the guard doesn't exist on the path that matters.** The degrade path ships the raw
deterministic templates when the LLM is down or its output is rejected. Whatever
prompt-level framing exists does not apply there.

**Fix (cheap, and it costs the feature nothing).** Make §F5 **conditional and
educational** rather than imperative and personal: *"When a single position accounts for
more than 40% of a portfolio's risk, the textbook response is to consider whether the
concentration is intentional"* — the user's number shown as the trigger, not as the
subject of an instruction. Same information, same teaching value, different speech act.
Rename the section. Drop the severity bands. Note that the second prong of both the US
and Malaysian adviser definitions reaches the *analysis* too, so §F1–F4 need the
disclosure fix in F19 regardless.

---

## 3. Major findings

### F7 — The fat-tail standard error is wrong by 2.1×

Line 156: *"at daily excess kurtosis ≈ 30 the true SE is ~1.9× wider."*

From Var(s²) = σ⁴(κ−1)/T and the delta method, SE(s) ≈ σ√((κ−1)/(4T)), which reduces to
σ/√(2T) at κ = 3 ✓. The inflation factor is √((κ−1)/2), independent of T and σ:

| excess kurtosis | inflation | SE at T=126, σ=20% | as % of estimate |
|---|---|---|---|
| 3.2 (⟵ what "1.9×" implies) | 1.90× | 2.39 pp | 12.0% |
| 10 | 2.45× | 3.09 pp | 15.4% |
| **30 (the doc's figure)** | **4.00×** | **5.04 pp** | **25.2%** |

At excess kurtosis 30 the factor is exactly **4.0×**. The "1.9×" corresponds to excess
kurtosis ≈ 5.2. The two numbers in that sentence are mutually inconsistent.

Your headline conclusion survives (5.04pp still swamps the 28.3pp mean-return SE at
T = 126). The *sufficiency floor* does not: you justify T ≥ 126 as "the first day the
number is defensible" on SE = 1.26pp; under your own tail assumption it is 5.04pp —
**±25% of the estimate**. A reported 20% volatility is really 15%–25%, and that is the
number F4's thresholds are compared against.

Separately, **excess kurtosis ≈ 30 is the wrong parameter for a 126-day estimator.** It
is roughly right for the S&P 500 over 1950–2011 (raw kurtosis 31.1, n = 15,548 — Burns,
Portfolio Probe, 2012), but that estimate is driven by 19 October 1987 and the same
source warns it is suspect for that reason. A 126-day window with no crash has excess
kurtosis in low single digits. Fix the factor to 4.0× and keep κ = 33, or use a
window-appropriate κ and keep ~1.9× — not both.

**Related:** the shipped `standard_error` is σ/√(2T), the SE of the **sample** standard
deviation. Your shipped point estimate comes from a deliberately biased shrinkage
estimator. The standard error you publish does not belong to the value you publish.

### F8 — The nominated acceptance test cannot detect the worst failure mode

You nominate this as *"the test that would have caught the naive-HHI defect"*: N
equal-weighted assets at uniform ρ must give DR² = 1/((1/N)+(1−1/N)ρ).

At δ = 1 — which occurs in **16.4% of real 126-day windows** (F2) — the shrunk estimator
produces that closed form *by construction*, because the target **is** a uniform-ρ
matrix. The test passes identically in the fully-degenerate state.

Demonstrated error at δ = 1 on concentrated N = 10 books: reported DR² 1.6917 vs truth
1.5717 (+7.6%) when the two big holdings sit in the same 0.85 cluster; 1.5845 vs truth
1.8182 (−12.9%) when they are genuinely uncorrelated. **The error always points toward
the average** — which is another way of saying the estimator cannot see clustering, the
one thing DR² exists to measure.

**Fix.** Replace the uniform-ρ fixture with a **non-uniform** correlation structure. A
uniform-ρ known-answer test cannot distinguish a working estimator from a clamped one.

### F9 — The signature visual is substantially a cash artefact

Cash takes **money share** but zero **risk share**, so every risky holding's risk share
exceeds its money share by construction, and the gap widens with cash. Same risky sleeve
in every row — only the cash balance changes:

| cash | σₚ | top holding risk share | money share | headline gap |
|---|---|---|---|---|
| 0% | 27.20% | 79.3% | 50.0% | +29.3 pp |
| 20% | 21.76% | 79.3% | 40.0% | +39.3 pp |
| 40% | 16.32% | 79.3% | 30.0% | **+49.3 pp** |
| 60% | 10.88% | 79.3% | 20.0% | +59.3 pp |

The concentration displayed is **identical** in all four rows. "62% of your risk on 30%
of your money" is partly a statement about the user's cash balance, and they will read
it as a statement about NVDA.

Confirmed properties: **DR² is invariant to cash**; **risk shares are invariant to
cash**; **HHI is not** — and HHI effective-N is *non-monotone* in cash (2.63 at 0% →
3.53 at 20% → 3.37 at 40% → 2.38 at 60%), so your "weight concentration" tile moves in
both directions as a user does nothing but hold cash. That tile does not measure what
its label says.

**Fix.** Compare risk share against **invested-sleeve** money share; put cash drag on its
own line (R4 exists for it). Also: R4's template says cash *"dilutes every risk number
above"* — it dilutes σₚ, not DR² and not risk shares, both of which are invariant.

### F10 — Realised max drawdown is a monotone ratchet

The pack argues MDD escapes the sample-size objection because it is descriptive. The
objection is about **horizon**, not sampling. For a driftless walk
E[MDD] = √(π/2)·σ·√T, so at constant risk it grows without bound in T.

At 20% annualised volatility, zero drift, daily monitoring, nothing about the portfolio
ever changing:

| window | expected realised max drawdown |
|---|---|
| 3 months | 10.4% |
| 6 months | 14.8% |
| 1 year | 20.7% |
| 2 years | 28.2% |

It **doubles from 3 months to 1 year**. And on an expanding window realised MDD is
monotonically non-decreasing by construction — verified, minimum day-over-day change
exactly zero. **A user who de-risks their book can never see this number improve.**

Your stated protection — never compare against a benchmark's different window — guards
the comparison nobody makes and misses the one everybody makes: their own number last
month versus this month. The Finding is archived in the journal, so consecutive reports
sit adjacent *by design*.

**Fix.** Fixed trailing window (rolling 12 months), or ship it beside its expected value
for the observed horizon: *"worst fall 18% over 126 days; a random walk at your
volatility would average 15% over the same window."* That version makes the horizon
effect the lesson instead of the bug.

### F11 — Rolling-window echo: numbers move on days nothing happened

Simulated: 600 daily returns at 20% annualised, one −8% day, 126-day window.

- The day the shock leaves: annualised vol **22.44% → 19.48%**, a discontinuous
  **−2.97 pp (−13.2%)** jump, on a day whose own return was −0.003%.
- **55× the median absolute day-over-day change** of the no-shock counterfactual.
- For the 126 days the shock sits inside, mean vol reads 21.95% vs 18.76% counterfactual
  — **one day six months ago elevates the estimate for six months.**
- EWMA(λ = 0.94): responds *at* the event, 11.2-day half-life, **no discontinuity at
  exit** (−0.04 pp, within ordinary wobble).

This is why RiskMetrics chose exponential weighting; λ = 0.94 for daily data is their
published optimum, selected by minimising one-day-ahead forecast RMSE across 480 series
(*RiskMetrics Technical Document*, 4th ed., 1996, §5.3.2). The pack does not mention the
artefact or consider any within-window weighting.

It does not stop at the volatility tile: **every** Tier-1 metric derives from the same
Σ, so beta, DR², risk contributions and benchmark volatility all step together on the
same morning, with no market event to explain it.

### F12 — You cite TEV and ship absolute volatility

Your justification is the FMR patent, whose headline output is **tracking error
volatility** decomposed by security, sector **or factor**. You ship **absolute**
volatility by security and sector — two of three axes, and the wrong risk measure.

Tracking error costs nothing. From quantities already in your payload:

```
TE = √(σₚ² + σ_b² − 2·β·σ_b²)
```

On a book with σₚ = 26.20%, σ_b = 15.87%, β = 1.301 → **TE = 16.82%**. Zero new data.

For a user whose entire mental benchmark is "am I beating the S&P," active risk is the
more relevant number and the one your cited precedent leads with. Ship it, or stop
citing TEV.

*Provenance correction while I'm here:* TEV appears in the patent's **specification**,
not its claims — a search of all 30 claims for "TEV"/"tracking error" returns zero hits.
Your substance is right; "documented at claim level" is not. Also, the CAIA URL cited for
holdings-based analysis returns **HTTP 404**.

### F13 — VaR is excluded for a reason that is factually wrong

Stated reason: *"insufficient history for tail estimation."* Valid against **historical**
VaR; not valid against **parametric** VaR, which is a monotone transform of the
volatility you already ship and gate at T ≥ 126:

| horizon | 95% VaR | on a $10k book |
|---|---|---|
| 1 day | 2.71% | $271 |
| 1 week | 6.07% | $607 |
| 1 month | 12.44% | $1,244 |

No extra history, estimator, or sufficiency floor. There *are* good reasons to refuse a
dollar figure — Gaussian VaR understates equity tails; a dollar number invites a
prediction reading. Say **those**. As written, a reviewer checks the stated reason, finds
it wrong, and starts doubting the exclusions that are well-founded.

There is also a product cost. "23% annualised volatility" is not a quantity a retail
learner has intuition for; "in a bad month this book has moved about ±12%" is. You chose
the register that is safest to defend and hardest to learn from — and simultaneously kept
max drawdown, the loss statistic with the *worst* statistical properties in the set (F10).

### F14 — Beta is a backcast and no document says so

The pack states, correctly, that no equity curve exists and Tier 1 reads no snapshot
history. It then defines beta as *"OLS slope of portfolio returns on benchmark
returns"* — including in the **externally-facing** methodology doc, to a
professional-reviewer audience, unqualified.

There are no portfolio returns. The regression must run on a **pro-forma series of
today's weights applied to past returns**. A grep of all three documents for "pro-forma",
"backcast", "constant weight" or "hypothetical" against the beta construction returns
**zero hits**.

That is a different object from a realised beta — it answers "what would this book have
done," with survivorship baked in, since the weights are the ones held *today*, after
whatever was sold. A defensible choice; an undisclosed one is not, and it is the first
thing I would circle in the external document.

### F15 — The post-generation validator is not implementable as specified

Rule 5 rejects output containing any digit sequence absent from the payload. Simulated
against a realistic payload and the §F3 content the CR **mandates**:

**False rejections of required content** — "Ledoit & Wolf (2004), *JPM* 30(4)" rejects
`2004`, `30`; "Markowitz (1952)", "Choueifaty & Coignard (2008)", "Lo (2002)" reject
their years; "the S&P **500**"; "**95**% confidence interval"; "the square root of
**252**"; "BOK lessons M**11**/M**12**"; "$10,000" on the separator.

**Non-deterministic on rounding** — 0.6249 rendered "62%" passes (substring of the raw
float); 0.6251 rendered "63%" **rejects**, because round-half-up produces a digit
sequence by construction absent from the input. Identical formatting logic passes or
fails on the third decimal.

And **R3's own deterministic template fails the validator**: `{beta_x10}` = β×10 appears
in none of the specified metric blocks, while prompt rule 2 says *"if a comparison is not
in the payload, it is not said."* The rule engine and the prompt contract contradict each
other inside one document — and the fallback rendering, the supposed safe path, is what
trips the guard.

**Fix.** Validate against a rendered-token allow-list (formatted values at display
precision, citation years, benchmark names, section ids, disclosed constants), not raw
digit substrings. Put every derived quantity in the payload or remove it from templates.

### F16 — No model validation

Acceptance checks portfolio volatility against numpy to 2 dp. That tests **arithmetic**,
not whether predicted volatility resembles what the portfolio does.

The institutional answer is a **bias test**: divide realised returns by predicted
volatility and check the z-scores have standard deviation ≈ 1 within sample-size-dependent
bounds. No risk vendor ships without one; no PM accepts a risk model without seeing one.

**You are one column away.** Tier-2 snapshots give R_t for free, but the schema has no
field for the *beginning-of-period forecast*, and the Tier-1 engine only runs on user
request. Add `predicted_vol_ann` (+ `n_observations`, `engine_version`) to the row the
daily job already writes and the model becomes permanently auditable. After one year,
T = 252 gives a bias-statistic CI of [0.911, 1.089] — tight enough to detect a 10%
mis-forecast.

The CR demotes Tier 2 to "a Tier-2 nicety" that "can slip without blocking the feature."
That is backwards: **Tier 2 is the validation layer for Tier 1.**

### F17 — T/N ≥ 5 has no basis for σₚ, and bars any book over 50 names forever

For a fixed weight vector, wᵀSw is just the sample variance of the univariate series
wᵀxₜ, so σ̂ₚ's relative sampling error is 1/√(2T), **independent of N**. Measured at
T = 126 (analytic 6.299%): N = 5 → 6.412%, N = 25 → 6.199%, N = 60 → 6.323%, N = 200 →
6.313% — and at N = 200 the sample covariance is **singular** and σ̂ₚ is just as precise.
Marchenko–Pastur eigenvalue dispersion (a 6.79:1 condition number at your exact
N = 25/T = 126 boundary) is invisible to a fixed quadratic form.

Meanwhile T/N ≥ 5 at T = 252 caps the book at **50 names**: a 51-holding portfolio
returns `sufficient:false` forever, with no better data ever arriving.

**Fix.** Scope the gate to DR² and risk contributions (which do touch off-diagonals);
drop it for σₚ, keeping T ≥ 126. And state the real justification for the other two —
target-misspecification sensitivity (F2), not matrix conditioning, which is not the
binding constraint anywhere in this feature.

### F18 — No factor model, and the IPO drop rule has no institutional precedent

You claim this is "the institutional holdings-based approach." Holdings-based is right;
the rest is not. Every institutional platform builds a **factor model**:

- **MSCI Barra USE4**: *"If the asset covariance matrix is computed naively — that is, by
  brute force — then the matrix is likely to be extremely ill-conditioned… Factor risk
  models were developed to provide a more robust solution."* 60 industry factors + style
  + country.
- **Axioma AXUS4**: 13–14 style factors, 68 GICS industry factors, plus a market factor.
- **Bloomberg PORT**: *"fundamental risk factor models… industry, country, style,
  currency, curve and spread."*
- Ledoit & Wolf position their own estimator explicitly as an **alternative** to that
  industry standard, not as it.

And on the drop rule — Barra USE4 §5.1: *"recently issued IPOs lack sufficient history to
reliably estimate their specific risk… the USE4 model blends the asset-level forecast
with the fitted value from a structural model."* Vendors **estimate** the missing
security; you **delete** it, and above 20% dropped weight you withhold the whole report.
So a user who buys a hot IPO — exactly the concentrated, high-risk behaviour this feature
should flag — is the user most likely to be shown nothing at all.

A factor model is a legitimate roadmap deferral. Claiming institutional equivalence
without one is not, and it is the claim a professional will test first.

*Related correction:* your reason for rejecting a composite score is that Morningstar's
weighting is proprietary. **It is published in full** — a 33-page public methodology with
numbered equations (total risk σ_P = √(σ_S² + σ_u²), leverage ratio L_P = σ_P/σ_B, MPRS
RS_P = L_P·R̄S_P), anchored to seven published Target Allocation Index points, and even
the ad-hoc constants are disclosed. What is *not* public is the underlying covariance
matrix. Rejecting a composite score is still the right call; the stated reason is wrong.

### F19 — The register split is enforced by prompt instruction alone

The register split is the CR's own answer to "who is this report for," and its only
enforcement is the prompt line *"Do not mix the registers."* The post-generation
validator checks exactly two things — digit sequences and a fixed adjective lexicon —
neither of which touches register.

Your own doctrine forbids this: CR038 records that agents ignore even emphatic
instructions ~70% of the time, and CLAUDE.md states *"if it must hold, make it
structural."* You applied that rigorously to nulls, stripping and digit validation, and
not here.

The spec also breaches its own line before a model is called: §F1 (plain) requires beta
"with the R² flag surfaced" and "effective independent bets (DR²)"; §F2 (plain) requires
a sufficiency-disclosure sentence; SCREEN_DESIGNS puts `126 TRADING DAYS ·
HOLDINGS-BASED` as the card subtitle — the first line a non-professional reader sees.
The recessed slate900 ledger controls *where* text sits, not *what register* it is in.

**And the disclosures are in the wrong place.** SCREEN_DESIGNS puts them "at the foot";
CR136 requires the opposite — *"limitations are disclosed BEFORE the reader finds
them."* Worse, the journal payload spec stores the five rendered sections with **no
disclosure requirement at all** — and the journal entry is what survives, gets re-read
months later, and gets screenshotted. The app already has the right string:
`disclaimerShort` = "Educational simulation. Not investment advice."

### F20 — The feature cannot ship on the current data layer

Verified in source: `_PERIOD_MAP` (`backend/app/services/market_data.py:150-157`) returns
a **daily** interval only for `"1m"` (22 bars) and `"3m"` (65 bars); `"1y"` is weekly,
`"5y"` monthly. Maximum daily series: **64 returns**. Your floor is **126**.

So on launch day **every Tier-1 metric returns `sufficient:false`** — including for a
user holding a 40-year-old mega-cap. And the prescribed copy makes it worse:
SCREEN_DESIGNS specifies *"needs 126 trading days; your oldest holding has 47"* — which
under the launch configuration is **factually false for every holding older than three
months**. The card blames the user's portfolio for our fetcher's limit.

The enabling work is four bullets in scope item 3a with no owner, no estimate, no
sequencing, alongside a 60-second history cache (`market_data.py:399`) that puts N
sequential Yahoo round-trips on every dashboard open.

Also: scope 3a claims the fix "moves SE(volatility) from 1.77pp to 0.63pp." 0.63pp is
**T = 504 (2 years)**; a 1-year fetch gives 0.89pp — half the advertised gain. Given F11,
fetch two years.

**This is the critical path.** It belongs at the top of the scope, not in a footnote.

---

## 4. Smaller findings

- **DR² can exceed the holding count** (two equal-weight positions at ρ = −0.5 give
  DR² > 2), and §F1 mandates displaying it beside the raw count. "3.1 effective bets from
  2 holdings" is not explicable. Cap the display or drop the pairing.
- **Negative risk contributions are a real long-only outcome** — nothing in the spec
  (metric, rule, test or rendering) is defined for one, the bar chart cannot draw it, and
  R1's threshold is undefined against it. It is also the most interesting case
  pedagogically ("this position is a diversifier"). Design it, don't clamp it.
- **√252 annualisation inherits the objection you used to kill Sharpe.** Lo's Eq. 19 is a
  statement about *variance*; the Sharpe result is derived from it. You cite Lo to
  exclude Sharpe and then annualise volatility by √252 without addressing serial
  correlation. Disclose the IID assumption or test for it.
- **The R² ≥ 0.20 floor never binds where you need it.** For a 5–20 name US large-cap
  book, portfolio R² against SPY runs ≈ 0.57–0.69 (Roll 1988 gives ≈ 0.20 for *single*
  daily names; aggregation lifts it); P(R² < 0.20) ≈ 0 in simulation. It passes ~100% of
  the time for the target book and binds only on 1–3 name books — exactly where beta is
  least safe. Gate on the beta CI instead.
- **R5's `{covered}` mixes bases** — dropped-holding coverage is invested-value-based
  while every Tier-1 metric is total-value-based.
- **No portfolio-age floor.** Every threshold concerns the *securities'* history, none the
  portfolio's. That is the intended benefit of holdings-based analysis, but the report
  should distinguish statements about the user's decisions from statements about the
  stocks they happen to hold.
- **Costless simulation, trimming advice.** There is no fee, commission or slippage model
  (verified — no such terms in `sim_engine.py`), and §F5 recommends trades. Barber &
  Odean (2000): the most-active households earned **11.4%** annually net vs a **17.9%**
  market return, turning over 75% of the portfolio a year — but gross returns were flat
  across turnover quintiles (18.5%–18.7%), so **97% of the measured penalty is invisible
  in a zero-cost world.** A simulator that makes trading free cannot teach the dominant
  mechanism of retail underperformance, and §F5 pushes in the opposite direction. At
  minimum, disclose the zero-cost assumption beside every recommendation.
- **The thing you are teaching is real and large.** Goetzmann & Kumar (2008), same
  brokerage dataset: **25.5% of retail portfolios held one stock; 54.9% held three or
  fewer;** only 5.7% held more than 15 — and the authors attribute it to *"naive
  diversification… without giving proper consideration to the correlations among the
  stocks."* That is precisely what DR² measures and HHI misses. The feature's premise is
  well-founded; make sure F2 doesn't blunt the instrument.

---

## 5. Does it meet my needs? The scorecard

You named "the user and their human portfolio manager" as the audience. The ten things I
look for:

| # | What I ask | CR136 |
|---|---|---|
| 1 | How much risk, over what window? | ✅ σₚ with SE, window, n |
| 2 | Where does the risk come from? | ✅ Euler decomposition by name and sector — the best part |
| 3 | How diversified, really? | ⚠️ DR² is the right metric, blunted by the pinned estimator (F2) |
| 4 | Risk *relative to my benchmark*? | ❌ No tracking error (F12) |
| 5 | Factor / style exposures? | ❌ None — you cite a factor-model patent and ship no factor model (F18) |
| 6 | What happens in a bad scenario? | ❌ No VaR, no stress test, no historical replay (F13) |
| 7 | What did I earn, and from what? | ❌ No return attribution — deliberate, and I accept the reasoning |
| 8 | What is this costing me? | ❌ No costs modelled at all |
| 9 | How liquid is the book? | ❌ Absent |
| 10 | Is the risk model any good? | ❌ No bias test (F16) |

**Two and a half of ten.** For a retail training product that is a defensible scope. But
#4, #6 and #10 are all reachable from data you already fetch, and none needs a new
estimator.

The honest framing: **this is not a portfolio-manager tool and it should stop implying it
is.** It is a well-built risk-decomposition teaching aid. Say that, and the "hostile PM"
standard becomes achievable instead of hostage to a scope you never intended to fill.

---

## 6. What I would change, in order

**Before any build starts:**

1. Fix the cash/shrinkage construction order and short-circuit N = 1, N = 2. (F1)
2. Decide the estimator on the right grounds — plain sample Σ for σₚ/DR²/risk shares, or
   shrinkage with δ published, a δ ceiling, and R2 fired off the unshrunk DR². (F2)
3. Fix R1 — rank on MCR, or reword to the true statement. (F3)
4. Gate every rule on a confidence bound or add hysteresis. (F4)
5. Delete R3's projection clause. (F5)
6. Reframe §F5 as conditional/educational, rename it, drop the severity bands — and
   reconcile with the website copy before anything ships. (F6)
7. Move the market-data work to the top of the scope with an owner. (F20)

**Before the estimator is written:**

8. Fix the fat-tail factor to 4.0× (or re-parameterise κ) and reconcile with the 126-day
   floor. (F7)
9. Replace the uniform-ρ known-answer test with a non-uniform fixture. (F8)
10. Switch the risk-vs-money visual to invested-sleeve money share. (F9)
11. Adopt EWMA, or accept and disclose the echo. (F11)
12. Add tracking error — three lines. (F12)
13. Ship MCR as its own metric — free, and it is the actionable one. (F3)
14. Scope T/N ≥ 5 to DR² and risk contributions only. (F17)

**Before it ships:**

15. Re-specify the validator against a rendered-token allow-list. (F15)
16. Fixed-window or expectation-anchored max drawdown. (F10)
17. Add `predicted_vol_ann` to the snapshot row; add a bias statistic to acceptance. (F16)
18. Label the beta as a backcast — in the external document especially. (F14)
19. Ship parametric VaR, or replace the stated reason with the true one. (F13)
20. Make the register split structural, and move disclosures to the head — including into
     the journal payload. (F19)
21. Fix the insufficient-state copy so it names our data limit, not the user's holdings. (F20)

---

## 7. How this review was produced

Every quantitative claim in the pack was independently re-derived from its own stated
formula; every counter-claim here was computed before it was written. Sources are primary
where a primary source exists.

- **Confirmed as stated:** Lo's SE formula and both derived figures ([−2.28, +4.28]; 971
  days), reproduced against Lo's own Table 1 worked example; SE(mean) = σ/√years; the SE
  asymmetry table (one 0.8% rounding slip at the 64-obs row — the doc used 0.25 years
  rather than 64/252); √(252/365) = 0.831, the 113-row/31% padding figures and the 0.845
  Monte-Carlo factor; DR² closed forms at N = 10/30, ρ = 0.2/0.8; the 60/40 DR² = 1.54
  probe; the 8.2× HHI figure; the Euler identity with a cash row; the rf = 0 Sharpe
  overstatement (2.29×); the drawdown 0.0%-vs-20% example; ~64 returns from 65 bars;
  US10157419B1's assignee, title, TEV/factor language and the BlackRock→FMR correction;
  the journal enum-coercion defect.
- **Refuted:** the 1.9× fat-tail factor (F7); R1's per-dollar claim (F3); "max drawdown
  escapes the sample-size objection" (F10); the sufficiency of the drawdown window rule
  (F10); the R² = 0.20 floor as a guardrail (§4); the 0.63pp payoff attribution (F20);
  `{beta_x10}` being in the payload (F15); the digit-validator's implementability (F15);
  "8.2×" as a ceiling (§1.3); R4's "dilutes every risk number" (F9); Morningstar MPRS
  being proprietary (F18); "documented at claim level" for TEV (F12); the T/N gate's
  relevance to σₚ (F17).
- **Computed for this review:** the R1 counterexample; the rule-threshold Monte Carlo
  (3,000 windows per point); the cash-artefact table; expected max drawdown by horizon;
  the rolling-window echo simulation vs EWMA(0.94); Ledoit–Wolf shrinkage intensity on
  simulated and real panels, plus the R2 suppression Monte Carlo (4,000 reps); the
  cash-row NaN demonstration; the σ̂ₚ precision sweep to N = 200; tracking error and
  parametric VaR from shipped quantities; and the `_PERIOD_MAP` / fee-model checks
  against source.

Literature: Lo (2002) *FAJ* 58(4); Ledoit & Wolf, *Honey, I Shrunk the Sample Covariance
Matrix*, *JPM* 30(4) 2004; Choueifaty & Coignard (2008); Choueifaty, Froidure & Reynier
(2012); Litterman, *Hot Spots and Hedges*, *JPM* 23(5) 1996; Qian (2006); Maillard,
Roncalli & Teïletche, *JPM* 36(4) 2010; Palomar, *Portfolio Optimization* §11.3 (CUP
2025); Magdon-Ismail, Atiya, Pratap & Abu-Mostafa, *J. Applied Probability* 41(1) 2004;
*RiskMetrics Technical Document* 4th ed. 1996 §5.3.2; Cohen, Hawawini, Maier, Schwartz &
Whitcomb, *Management Science* 29(1) 1983; Hawawini (1983); Scholes & Williams, *JFE*
5(3) 1977; Dimson (1979); Handa, Kothari & Wasley (1989); Roll, *R²*, *J. Finance* 43(3)
1988; Merton (1980); Barber & Odean, *Trading Is Hazardous to Your Wealth*, *J. Finance*
55(2) 2000; Goetzmann & Kumar, *Equity Portfolio Diversification*, *Review of Finance*
12(3) 2008; Meucci, *Managing Diversification* (2009); MSCI Barra USE4 Methodology Notes
§§1.3, 2.2, 5.1; Axioma AXUS4; Morningstar Portfolio Risk Score methodology; US patent
US10157419B1; 15 U.S.C. §80b-2(a)(11)(D); Lowe v. SEC, 472 U.S. 181 (1985); 17 C.F.R.
§275.203A-3(a)(3).

---

## 8. Closing

I have been adversarial because you asked for it, and because a document claiming every
quantitative claim was independently recomputed has to be right. Several were not — and
the two most serious defects are not arithmetic errors at all. They are what happens when
two individually-defensible pins are composed: cash-as-a-zero-vol-row **and**
constant-correlation shrinkage produce a NaN; shrinkage-for-stability **and**
DR²-as-the-concentration-alarm produce an estimator that mutes the alarm. Neither is
visible in any single section. Both would have shipped.

That is worth saying plainly, because your process is otherwise strong: the estimability
principle is correct, refusing Sharpe was right, Euler decomposition is the right
headline, the uncertainty contract is the right architecture, and the arithmetic is
overwhelmingly sound. Most retail risk products would not survive page one of this
review. This one survives to page six and fails on things that are all fixable in the
spec, before a line of code is written.

Fix the six blockers, move the data-layer work to the front, and stop describing it as a
tool for portfolio managers. Then it is a genuinely good teaching instrument, and the
hostile reader has nothing left to circle.
