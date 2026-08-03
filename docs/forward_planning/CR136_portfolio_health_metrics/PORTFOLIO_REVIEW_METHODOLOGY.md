# AMI Trade — Portfolio Review Methodology

*Prepared for external review. Version 2.1 — August 2026.*

---

## 1. Purpose

AMI Trade is a simulation-only trading-education application. This document
describes the methodology behind its **Portfolio Health** review: a whole-
portfolio risk analysis generated for each user's simulated portfolio and
presented as a structured analyst report. It is written so that a
professional reviewer — a portfolio manager, risk officer, or quantitatively
literate adviser — can evaluate every choice on its merits. Every metric
traces to a named, published methodology; nothing is proprietary or opaque.

## 2. Design principles

**Only report what can be estimated.** The standard error of an annualised
*mean* return is `σ/√years` — roughly ±40 percentage points with three months
of data and still ±4.5 points after twenty years. The standard error of
annualised *volatility* is `≈ σ/√(2·T_eff)` — about ±1.8 points after three
months. Mean returns are therefore not estimable at any horizon a retail
account will ever have, while volatilities, correlations, and betas are
estimable within months. Every metric in this review is a pure second-moment
or accounting quantity; **no metric with a mean-return term is reported.**

**Deterministic computation; narration only.** All numbers are computed by
deterministic, unit-tested code. AMI's language layer receives finished figures
and may only cite them — it is structurally prevented from computing,
estimating, extrapolating, or comparing beyond what is present. Generated text
is validated after the fact against the computed payload: any output containing
a figure absent from that payload is rejected and replaced by a fixed template
rendering. The instruction to behave is not the control; the validator is.

**Degrade loudly.** A metric that cannot be estimated to the stated standard is
reported as "insufficient data", never as a number. When a metric is
insufficient its value and its standard error are **null** — never `0.0`, which
would read as a confident measurement of no risk — and the metric is removed
from the language layer's input entirely, so there is nothing left to narrate.

**One basis per sentence.** Two bases run through the whole review and no figure
may mix them: **LEVEL** quantities (volatility, beta, tracking error, typical
bad month, scenario panel) are measured over the **total book, cash included**;
**SHARE** quantities (risk contributions, marginal contribution to risk, weight
concentration) are measured over the **invested sleeve**. Every stored metric
carries its own basis field, so the rule is machine-checkable rather than a
convention a writer has to remember.

There is **one deliberate exception**, and it is stated rather than hidden: a
sentence reporting a breach of the user's own mandate quotes the holding's
weight over **total** value, because the mandate is enforced at the trade ticket
on that same denominator. Reported on the invested sleeve it would name
violations the enforcing surface does not — measured on a $10,000 book holding
50% cash, three phantom breaches against the ticket's zero. Where a figure is
shown to a user *and* enforced against them, agreeing with the enforcement
outranks basis uniformity; the metric's basis field records which one applies.

## 3. What is measured

All Tier-1 metrics derive from a **single covariance matrix** built from each
current holding's own daily return history — a holdings-based approach, so the
review works from the first day a portfolio exists rather than waiting for it to
accumulate a track record. The benchmark is estimated as one more leg of that
same matrix, so the portfolio and its benchmark can never be measured over
different windows.

| Metric | Definition | Basis | Methodology |
|---|---|---|---|
| Portfolio volatility (annualised) | `√(wᵀΣw) · √252` | LEVEL | Markowitz (1952); Σ estimated by exponentially weighted moving average, λ = 0.97 (§5) |
| Beta vs. benchmark, with R² | `Cov_w(p,b)/Var_w(b)`; `Cov_w(p,b)²/(Var_w(p)·Var_w(b))` — both read off the joint matrix | LEVEL | CAPM. R² is always reported alongside; a beta with low explanatory power is flagged, never hidden |
| Tracking error (annualised) | `√(σₚ² + σ_b² − 2βσ_b²)` | LEVEL | The book's volatility *relative to* the benchmark. Derived, so it publishes no standard error of its own — its three components each carry theirs |
| Diversification ratio (DR²) | `DR = (Σwᵢσᵢ)/σₚ`; DR² reported as *effective independent bets* | SHARE | Choueifaty & Coignard (2008); Choueifaty, Froidure & Reynier (2012). A measure, not a literal count — and never presented alone (caveat below) |
| Risk contribution | `wᵢ(Σw)ᵢ/σₚ²` per holding and per sector; sums to 100% | SHARE | Euler decomposition — the standard institutional attribution output ("X% of your risk from Y% of your money") |
| Marginal contribution to risk | `∂σₚ/∂wᵢ = (Σw)ᵢ/σₚ`, annualised | SHARE | The sensitivity of book volatility to a marginal unit of each holding |
| Invested weight concentration | Herfindahl index `Σwᵢ²` and its inverse (effective-N), over the **invested sleeve** | SHARE | Labelled *weight concentration* only: it is correlation-blind and is never presented as a diversification measure |
| Typical bad month | `1.645 · σₚ · √(21/252)` | LEVEL | A dispersion statement at the 5th percentile of a monthly horizon under the stated Gaussian assumption — explicitly not a forecast and not a loss estimate |
| Scenario panel | `β × r_benchmark` over named historical episodes | LEVEL | A **backcast what-if**: today's holdings and today's beta applied to a past benchmark move. Not a prediction, and labelled as such wherever it renders |
| Realised maximum drawdown | Deepest peak-to-trough fall of the stored portfolio-value series over a **rolling trailing 252-trading-day window**, floor **≥ 21 stored snapshots** | LEVEL | Descriptive statistic; the window is always stated, and figures from different windows are never compared |
| Realised return over the window | `V_last/V_first − 1` over the same stored value series, **never annualised**, floor **≥ 2 stored snapshots and a positive opening value** | LEVEL | An accounting fact of the stored series rather than an estimate — see §4 for why this is not an exception to the mean-return exclusion |

**Why weight concentration moved to the invested sleeve** (changed from version
1.0): the total-value Herfindahl index is *non-monotone in cash* — measured,
effective-N runs 2.63 → 3.53 → 3.37 → 2.38 across 0/20/40/60% cash on an
otherwise identical sleeve. A "diversification" number that rises and then falls
while the user does nothing but hold cash is describing the cash, not the book.

**Why cash is a zero row appended after estimation:** it makes the effect of
cash exact rather than approximate. A cash weight `c` scales σₚ and β by exactly
`(1 − c)` and leaves risk shares, DR² and R² exactly invariant. The alternative
— feeding a constant series into the estimator — asks a covariance estimator to
handle a degenerate input for no analytic gain.

**The DR² caveat, carried wherever DR² appears:** it penalises volatility
imbalance as well as correlation, so a correctly diversified 60/40 equity/bond
book (ρ = 0.154) reads 1.278 while a triple-overlap equity book reads 1.261 —
nearly the same number for opposite reasons. Risk contributions are what
disambiguate the cause, which is why no surface presents DR² on its own.

## 4. What is deliberately not reported

Sharpe, Sortino, Treynor, Jensen's alpha, and the information ratio are all
excluded. Each carries a mean-return numerator. Applying Lo (2002), a measured
annualised Sharpe ratio of 1.0 over 90 trading days carries a 95% confidence
interval of approximately **[−2.3, +4.3]** — the sign is not even determined —
and a true Sharpe of 1.0 first becomes statistically distinguishable from zero
after roughly **970 trading days (~4 years)**. Reporting such figures to a
retail user presents noise as signal. They are excluded until the day the data
supports them, and that exclusion is stated in the user-facing report rather
than glossed over.

**The realised return of §3 is not an exception to this.** What is excluded is
the *expected* return term — a quantity inferred from a sample and projected
forward, whose sampling error swamps it at every horizon a retail account has.
Realised return is the arithmetic of what already happened to a stored value
series, reported with its window attached, never annualised, never extrapolated,
and never placed over a risk figure to form a ratio. The moment it were
annualised it would become an estimate of the excluded kind, which is why the
implementation computes it as a simple cumulative return and stores no
annualised form.

Also excluded: VaR/CVaR (insufficient history for tail estimation),
factor-model exposures (roadmap), look-through into ETF constituents (roadmap —
its absence is disclosed on the concentration tile rather than assumed away),
and any composite risk score (a single blended number requires a weighting
scheme we could not defend; each metric stands on its own published methodology
instead).

## 5. Estimation methodology

- **Data:** daily closes per holding; returns computed on trading days only
  (weekend/holiday padding is excluded — including it understates annualised
  volatility by a factor of ≈ 0.83). Annualisation by √252 on trading-day
  series only. Trading days are defined by which bars exist; no trading
  calendar is imported anywhere.
- **Covariance — EWMA, λ = 0.97, weighted-demeaned, population style.** Weights
  are normalised over the *available* window, newest last:
  `Σ_ab = Σⱼ wⱼ (r_aj − μ_a)(r_bj − μ_b)` with `μ_a = Σⱼ wⱼ r_aj`. Method:
  *RiskMetrics — Technical Document*, 4th ed., §5.3.2.

  **Why not shrinkage** (changed from version 1.0, and the choice an external
  reviewer is most likely to challenge): a rectangular window produces a
  **roll-off echo** — measured, the reported figure drops 2.9 percentage points
  *discontinuously* on the day an old shock leaves the window, roughly 50× the
  median daily change, for a reason that has nothing to do with the portfolio.
  EWMA responds at the event instead (half-life 22.8 days; exit-day change
  0.03pp). Shrinkage toward a structured target addresses a different problem —
  sample-covariance instability at large N — which does not bind at the N ≤ ~30
  book sizes this review sees, and it damps precisely the correlation moves the
  review exists to surface.

  **The measured cost, disclosed rather than hidden:** EWMA's effective sample
  is ≈ 66 observations, which puts single-report detection of a newly
  correlated cluster at **82.1%** against a rectangular window's 89.0%. That
  trade — a slightly less sensitive single reading, in exchange for a figure
  that never jumps for calendar reasons — is the deliberate choice, and the
  effective window is stated on the user's own card.
- **Standard errors are computed on the EFFECTIVE sample.** Volatility ships
  `SE(σ̂ₚ) = σ̂ₚ/√(2·T_eff)` where `T_eff = 1/Σⱼwⱼ²` — not `σ̂/√(2T)`. Under
  exponential weighting the equal-weight formula **understates the true
  sampling error by ~27%** (measured: 1.72pp true against 1.26pp naive at
  σ = 20%), and publishing a confidence interval tighter than the data supports
  is the exact failure the uncertainty contract exists to prevent. Beta ships a
  weighted-least-squares standard error consistent with the same weights. Where
  a defensible standard error does not exist at these sample sizes (DR², risk
  contributions), none is invented — the omission is documented in the report.
- **Benchmark:** S&P 500 proxy (dividend-adjusted), estimated as a leg of the
  same joint matrix and date-aligned to the holding series by inner join on
  trading dates. A misaligned or short benchmark series fails the beta
  calculation **loudly** rather than being silently re-gridded: a series that
  does not share trading days with the book is unusable, not approximable.
- **Sufficiency thresholds** (a metric below its floor is not reported):
  volatility and beta require **≥ 126 trading-day observations**; the covariance
  estimate additionally requires **T/N ≥ 5** (observations per holding) before
  risk may be attributed across holdings. A holding with insufficient history is
  dropped and disclosed; if dropped weight exceeds **20%** of invested value the
  entire analysis is withheld — a covariance matrix that ignores a fifth of the
  book does not describe the user's portfolio. Realised drawdown requires **≥
  21** stored daily snapshots.
- **Data hygiene:** a series showing a spike-and-reversal print pattern is
  treated as a data fault and its holding is dropped with that reason recorded —
  distinctly from "not enough history", and distinctly again from "our price
  feed was unavailable". A report must never tell a user their holding is too
  young when the truth is that a fetch failed.

## 6. Disclosures carried in every report

Disclosures render **at the head of the report, before the first figure**, and
are stored inside the archived artefact. A user can reopen a review a year later
and screenshot it; the caveats have to still be attached when they do.

- **Simulation only.** All figures describe a paper-money training portfolio.
  Nothing constitutes investment advice.
- **Gross of costs.** The simulation deducts no commissions, fees, or slippage;
  all figures are gross, and execution is modelled at zero cost.
- **Backcast, and labelled as such.** Every figure applies **today's holdings
  and today's weights to past returns**. It describes how the current book would
  have behaved, not how the user's actual past portfolio did behave.
- **Estimates over a stated window.** Every figure carries its observation
  window, sample size and effective sample size; volatility-based standard
  errors assume Gaussian returns and understate true uncertainty in fat-tailed
  markets.
- **Non-stationarity.** Correlations and volatilities are estimated from a
  window that has already happened. They change — typically at exactly the
  moment a diversification assumption is being relied upon — and no figure here
  should be read as a property of the portfolio rather than a measurement of a
  period.
- **Data limitations first.** Dropped holdings, low-R² betas, partial coverage
  and unavailable feeds are disclosed in the report body before the reader can
  discover them.

## 7. The report

Each review is delivered as a five-section analyst report, archived unchanged in
the user's decision journal:

1. **Headlines** — three to five one-line figures (portfolio volatility vs.
   benchmark; top risk contributor as "% of risk vs % of money"; effective
   independent bets vs. raw holding count; realised drawdown with window).
2. **Executive summary** — plain-language, descriptive only; no advice verbs,
   no judgement adjectives, no claim not traceable to a computed figure.
3. **Detailed analysis** — per-metric: value, standard error, sample size,
   effective sample size, window, estimator citation, and data-quality notes.
   Written for a professional reader.
4. **Conclusion** — ties risk level, diversification quality and concentration
   together; introduces no new numbers.
5. **What the numbers point to** — generated by a deterministic rule engine with
   fixed thresholds, hysteresis bands and fixed templates (e.g. a single holding
   contributing ≥ 40% of portfolio risk; effective bets below a floor across a
   sufficiently large holding count; β outside a band with adequate R²). AMI's
   language layer orders and phrases the sentences the rule engine produced; it
   cannot invent one, **and it is not trusted to refrain** — the validator
   described in §2 checks every rendered figure against the payload before the
   report is stored and falls back to the deterministic rendering if any figure
   fails. If no rule fires, the report says so plainly.

   The speech act of this section is **conditional and educational**: it states
   what a textbook response to a measured condition would consider, never an
   imperative addressed to the user's own holdings, and it carries no severity
   bands. The section is titled "What the numbers point to" rather than
   "Recommendations" for exactly that reason — AMI is a training simulator and
   is not licensed to advise.

Plain language is used in sections 1, 2 and 5; technical register in section 3.
The registers are not mixed: the literal "R²" appears only in section 3, and
renders elsewhere as "the market explains X% of this book's day-to-day moves".

## 8. Validation

The methodology was developed under an adversarial internal review process:
every quantitative claim above (the Lo confidence intervals, the
effective-sample standard-error asymmetry, the roll-off echo measurement, the
correlation-blindness of the Herfindahl index and its non-monotonicity in cash,
the trading-day annualisation bias, the DR² ambiguity) was independently
recomputed from stated formulas by a second reviewer before adoption, and
several claims were corrected in the process. The implementation carries
known-answer tests against closed-form cases — including the exact
configurations that would have exposed each defect found during review — and
boundary tests at every sufficiency threshold.

**A standing empirical check, not a one-time one.** Each portfolio's daily value
is stored alongside the volatility the model predicted for that day. If the
model is calibrated, the realised daily return divided by the predicted daily
volatility has a standard deviation of 1. That statistic is recomputed monthly
per portfolio and logged; at a full year of observations (T = 252) the decision
band is **[0.911, 1.089]**, and a reading outside it raises a defect against the
estimator. Below that sample size the reading is recorded as immature and is not
judged — quoting a decision band against thirty observations would be the same
over-confidence these design principles reject.

The published figures are additionally cross-checked against an independent
reimplementation, and this check is a **required gate at each promotion** rather
than a claim about the past: a separate harness reads the same stored closes,
redoes the joins and the returns, recomputes every metric from the formulas
above in a different numerical library, and diffs against what the live system
published, requiring agreement to two decimal places in the rendered unit. It
applies the same data-hygiene exclusions the live engine applies, so the two
sides are answering one question of one dataset, and it reports any excluded
rows rather than absorbing them silently.

The harness itself was calibrated against the shipped implementation before
first use — on a synthetic series its covariance matched to 8.1e-20 and every
derived figure to better than 1e-12 — so that a disagreement on live data is
attributable to the system under test rather than to the instrument. As of this
version the first live run is pending promotion of the described system.

## References

- Markowitz, H. (1952). "Portfolio Selection." *Journal of Finance* 7(1).
- Lo, A. W. (2002). "The Statistics of Sharpe Ratios." *Financial Analysts
  Journal* 58(4).
- J.P. Morgan / Reuters (1996). *RiskMetrics — Technical Document*, 4th ed.
  (exponentially weighted covariance estimation, §5.3.2).
- Choueifaty, Y. & Coignard, Y. (2008). "Toward Maximum Diversification."
  *Journal of Portfolio Management* 35(1).
- Choueifaty, Y., Froidure, T. & Reynier, J. (2012). "Properties of the Most
  Diversified Portfolio." *Journal of Investment Strategies* 2(2).

---

*Internal reference: CR136 Rev 4.*
