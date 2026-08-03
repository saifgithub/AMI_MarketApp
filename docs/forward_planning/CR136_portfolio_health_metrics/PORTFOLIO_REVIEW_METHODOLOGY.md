# AMI Trade — Portfolio Review Methodology

*Prepared for external review. Version 2.3 — August 2026.*

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
deterministic, unit-tested code. The language layer never computes, estimates,
or extrapolates: it receives finished figures and may only cite them.

Two structural controls enforce that, and neither is an instruction the model
is trusted to follow.

**The strip.** A metric that fails its sufficiency test is removed from the
model's input entirely before any prompt exists, so there is nothing to
narrate — the metric's name never reaches the model.

**The language layer does not supply figures.** It writes prose containing named
references — `{{vol_ann_pct}}` — and every reference is replaced afterwards by
the computed value of *that named metric*, formatted by the same code the
deterministic report uses. A figure therefore cannot be attached to a metric it
does not belong to: the reference names the metric, and the substitution reads
that metric's value.

Output is discarded in full — and the reader receives the deterministic
rendering — if it names a reference that does not exist, if a reference is
malformed, or if it states a quantity in any other notation: a numeral in any
script (`20`, `٢٠`, `½`), a number spelled out ("twenty", "a fifth", "double"),
or a percent unit word.

This replaced an earlier design that let the model write figures and checked
afterwards that each appeared somewhere in the computed payload. That check
constrained the *vocabulary* of numbers but not their *assignment*: on an
ordinary book roughly half of all whole-number percentages appear somewhere in
the payload, so a real figure quoted against the wrong metric would pass. It
was found by independent audit before release, and the correction was to make
mis-attribution unrepresentable rather than to detect it more cleverly.

**What this does and does not guarantee.** Every figure published is computed,
and is published against the metric it was computed for. What the screens do not
police is unquantified language: "most of the risk sits in one name" states no
number, so nothing rejects it. They are also deliberately blunt in the other
direction — an ordinary phrase like "concentrated in a single name" is rejected,
because a count is a number. The residual risk is therefore availability first
(a model that will not follow the convention loses its narration to the
deterministic template, which costs prose and never accuracy) and, for
unquantified prose, tone. Every rejection is logged with its reason, so both are
measured rather than assumed.

The audit that found the earlier design also found that banning digits alone
still let a quantity through in words — "your beta is roughly double the market"
against a measured beta of 0.89. The screens above are the closure of that
finding, and this section has been corrected twice against measurement rather
than once against intent.

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
   sufficiently large holding count; β outside a band with adequate R²). This
   section is never phrased by the language layer at all: it ships exactly as the rule
   engine rendered it, on every path, because it is the section closest to
   advice and a phrasing control is not something to rely on there. If no rule
   fires, the report says so plainly.

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

## 9. Frequently asked questions

Sections 1–8 are written for a professional reader. This section answers the
same questions in two registers: plain language first, then — for the same
question, where the plain answer leaves something out that a technical reader
would want — the mechanism underneath it.

### In plain language

**What is Portfolio Health, in one sentence?**
It's a report on how risky your simulated portfolio is and how spread out that
risk is — never on whether it made money, and never a suggestion to buy or
sell anything.

**Does it tell me if I'm making or losing money?**
Only one line does — "realised return", the plain arithmetic of how your
stored portfolio value actually moved over the shown window. Everything else
in the report is about risk, not return, on purpose (see the next question).

**Why doesn't it show a "risk-adjusted return" score, or a Sharpe ratio?**
Because with the amount of history a real account has, that kind of number is
mostly noise wearing the shape of a signal — it can say your strategy looks
great or terrible almost at random, and only starts meaning something after
several years of daily data. Risk numbers (like volatility) become reliable
much sooner, which is why the report is built entirely from those instead.

**Why does it sometimes say "insufficient data" instead of giving me a
number?**
Because a number the app isn't confident in is worse than no number — it
looks precise even when it isn't. Every metric has a minimum amount of price
history it needs before it's shown; below that, you get an honest "not enough
data yet" instead of a guess dressed up as a fact.

**Is AMI (the AI) making these numbers up?**
No. Every figure is produced by fixed, tested calculation code before AMI ever
sees it. AMI's only job is to put the already-computed numbers into sentences.
If it ever tried to state a number that isn't one of the real computed
figures, that sentence gets thrown out automatically and replaced with a
plain, pre-written one instead.

**Why did my risk number change even though I didn't buy or sell anything?**
Markets move relative to each other every day, and the report reflects the
most recent relationship between your holdings — so those relationships
(and the risk number built from them) can shift on their own even when your
holdings don't.

**Is holding a lot of cash the same as being diversified?**
No, and the report is careful not to imply that. Cash lowers your risk
number, but a separate "concentration" figure is deliberately not described
as a diversification measure, because it can't tell the difference between
"spread across unrelated holdings" and "mostly sitting in cash."

**Can I trust these numbers if I only hold a few positions?**
The report tells you when it can't be confident — a holding with too short a
price history is dropped from the calculation and that's disclosed to you,
and if too much of your portfolio had to be dropped that way, the whole
report is withheld rather than shown on a shaky basis.

**Does this affect whether I'm allowed to make a trade?**
Only one line in the report — the one about your own trading rules ("mandate")
— is built to match the same numbers your trade ticket already checks, so it
never tells you that you've broken a rule your ticket says you haven't (or
the reverse).

**Will this ever tell me what to do?**
No. The closing section describes what a textbook would generally say about a
pattern like the one measured — it's written as "here's a general
consideration," never as an instruction about your holdings. AMI Trade is a
training simulator and isn't licensed to give investment advice.

**Is any of this about real money?**
No — every figure describes a paper-money practice portfolio, and every
report says so up front.

### For a technical reader

**Why EWMA(λ=0.97) rather than a rolling window or a shrinkage estimator?**
§5 — a rectangular window's roll-off echo (a measured
2.9pp discontinuous drop when an old shock exits the window) is a bigger
practical defect at this scale than the sample-covariance instability
shrinkage addresses, which doesn't bind at the N ≤ ~30 book sizes here.

**Why does the standard error use `T_eff` instead of raw `T`?** Because the
weights aren't uniform, the effective number of independent observations is
smaller than the raw count; using raw `T` in `σ̂/√(2T)` understates the true
sampling error by ~27% at these weights (§5) — the SE ships as
`σ̂ₚ/√(2·T_eff)` specifically to avoid publishing false precision.

**How is beta/R² estimated — a standalone regression, or read off the same
matrix?** Off the same joint EWMA matrix that produces the portfolio's own
variance (§3) — the benchmark is one more leg of that matrix rather than a
separately-windowed series, so portfolio and benchmark can never disagree
about which days they were measured over.

**Why is DR² never shown without risk contributions alongside it?** DR²
conflates volatility imbalance with correlation — a correctly diversified
60/40 book and a triple-overlapping equity book can produce nearly the same
DR² for opposite reasons (§3). Risk contributions are what disambiguates the
cause.

**Exactly what makes a metric "insufficient"?** ≥126 trading-day observations
for volatility/beta; additionally `T/N ≥ 5` before risk can be attributed
across holdings; a holding is dropped (and disclosed) below its own floor,
and the whole analysis is withheld if dropped weight exceeds 20% of invested
value; realised drawdown needs ≥21 stored snapshots; realised return needs
≥2 with a positive opening value (§5).

**How is the language layer mechanically prevented from fabricating a
number, not just instructed not to?** It supplies no figures at all (§2). It
writes named references and the system substitutes the computed value of that
named metric, so a figure cannot be attached to the wrong metric —
mis-attribution is unrepresentable rather than detected. A quantity written any
other way — a numeral in any script, a number spelled out, a percent unit word,
or a malformed reference — discards the output in full and the deterministic
report is served instead. What is *not* screened is unquantified language such
as "most of the risk"; that carries no figure and is not rejected. Separately,
an insufficient metric is stripped from the model's input before a prompt
exists, so it cannot be narrated at all.

**Where does the SHARE/LEVEL basis rule have a stated exception?** Mandate-
breach reporting (R0) is total-value basis by design, so it agrees with the
trade gate's own denominator rather than the invested-sleeve convention every
other SHARE metric uses (§2) — the metric's stored `basis` field records
which applies, so this is machine-checkable rather than a convention.

**How is calibration monitored in production, not just verified once at
launch?** The F16 bias check (§8): each portfolio's realised daily return
divided by that day's predicted volatility should have a standard deviation
of 1 if the model is calibrated; recomputed monthly per portfolio, with a
decision band of [0.911, 1.089] at a full year of observations, and readings
below that sample size are recorded as immature rather than judged.

**How is the live output independently verified before users see it?** A
separate harness re-reads the same stored closes, redoes the joins/returns,
and recomputes every published figure in a different numerical library,
applying the same data-hygiene exclusions the live engine applies, requiring
agreement to two decimal places (§8) — a required gate at each promotion, not
a one-time check.

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
