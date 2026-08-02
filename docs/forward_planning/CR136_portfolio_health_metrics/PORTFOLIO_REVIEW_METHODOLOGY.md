# AMI Trade — Portfolio Review Methodology

*Prepared for external review. Version 1.0 — August 2026.*

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
annualised *volatility* is `≈ σ/√(2T)` — about ±1.8 points after three
months. Mean returns are therefore not estimable at any horizon a retail
account will ever have, while volatilities, correlations, and betas are
estimable within months. Every metric in this review is a pure
second-moment or accounting quantity; **no metric with a mean-return term is
reported.**

**Deterministic computation; AI narration only.** All numbers are computed by
deterministic, unit-tested code. The AI analyst layer receives finished
figures and may only cite them — it is structurally prevented from computing,
estimating, extrapolating, or comparing beyond what is present. Generated
text is validated after the fact: any output containing a number absent from
the computed payload is rejected and replaced by a fixed template rendering.

**Degrade loudly.** A metric that cannot be estimated to the stated standard
is reported as "insufficient data," never as a number. Insufficient metrics
are removed from the AI layer's input entirely, so they cannot be narrated.

## 3. What is measured

All Tier-1 metrics derive from a single covariance matrix built from each
current holding's own daily return history — a holdings-based approach, so
the review works from the first day a portfolio exists rather than waiting
for it to accumulate a track record.

| Metric | Definition | Methodology |
|---|---|---|
| Portfolio volatility (annualised) | `√(wᵀΣw)` | Markowitz (1952); Σ estimated with Ledoit–Wolf shrinkage (see §5) |
| Beta vs. benchmark, with R² | OLS slope of portfolio returns on benchmark returns | CAPM; R² is always reported alongside — a beta with low explanatory power is flagged, not hidden |
| Diversification ratio (DR²) | `DR = (Σwᵢσᵢ)/σₚ`; DR² reported as *effective independent bets* | Choueifaty & Coignard (2008); Choueifaty, Froidure & Reynier (2012). Reported as a measure, not a literal count — DR² also penalises weight/volatility imbalance |
| Risk contribution | `wᵢ(Σw)ᵢ/σₚ²` per holding and per sector; sums to 100% | Euler decomposition — the standard institutional risk-attribution output ("X% of your risk from Y% of your money") |
| Weight concentration | Herfindahl index `Σwᵢ²` and its inverse (effective-N) | Labelled *weight concentration* only — it is correlation-blind and is never presented as a diversification measure |
| Realised maximum drawdown | Deepest peak-to-trough fall of the portfolio value series | Descriptive statistic; always presented with its observation window; never compared across different windows |

Weights span the **total** portfolio value with cash as a zero-volatility
position, so the figures describe the whole book as the user sees it. The
Euler identity is verified in testing: contributions sum to exactly 100%
with the cash row present.

## 4. What is deliberately not reported

Sharpe, Sortino, Treynor, Jensen's alpha, and the information ratio are all
excluded. Each carries a mean-return numerator. Applying Lo (2002), a
measured annualised Sharpe ratio of 1.0 over 90 trading days carries a 95%
confidence interval of approximately **[−2.3, +4.3]** — the sign is not even
determined — and a true Sharpe of 1.0 first becomes statistically
distinguishable from zero after roughly **970 trading days (~4 years)**.
Reporting such figures to a retail user presents noise as signal. They are
excluded until the day the data supports them, and that exclusion is stated
in the user-facing report rather than glossed over.

Also excluded: VaR/CVaR (insufficient history for tail estimation), factor-
model exposures (roadmap), and any composite risk score (a single blended
number requires a weighting scheme we could not defend; each metric stands
on its own published methodology instead).

## 5. Estimation methodology

- **Data:** daily closes per holding; returns computed on trading days only
  (weekend/holiday padding is excluded — including it understates annualised
  volatility by a factor of ≈0.83). Annualisation by √252 on trading-day
  series only.
- **Covariance:** Ledoit & Wolf shrinkage toward the constant-correlation
  target (*"Honey, I Shrunk the Sample Covariance Matrix,"* Journal of
  Portfolio Management, 2004), the standard remedy for sample-covariance
  instability in short windows. Shrinkage intensity is clamped to [0,1]; the
  result is positive semi-definite by construction.
- **Benchmark:** S&P 500 proxy (dividend-adjusted), date-aligned to the
  holding series by inner join on trading dates. A misaligned or short
  benchmark series fails the beta calculation loudly rather than being
  silently re-gridded.
- **Sufficiency thresholds** (a metric below its floor is not reported):
  volatility and beta require **≥ 126 trading-day observations** (six
  trading months — SE(σ̂) ≈ 1.3 points at 20% volatility); the covariance
  estimate additionally requires **T/N ≥ 5** (observations per holding). A
  holding with insufficient history is dropped and disclosed; if dropped
  weight exceeds **20%** of invested value, the entire analysis is withheld —
  a covariance matrix that ignores a fifth of the book does not describe the
  user's portfolio.
- **Uncertainty:** volatility and beta ship with standard errors
  (`σ/√(2T)`; OLS respectively). Where a defensible standard error does not
  exist at our sample sizes (DR², risk contributions), none is invented —
  the omission is documented.

## 6. Disclosures carried in every report

- **Simulation only.** All figures describe a paper-money training
  portfolio. Nothing constitutes investment advice.
- **Gross of costs.** The simulation deducts no commissions, fees, or
  slippage; all figures are gross.
- **Estimates over a stated window.** Every figure carries its observation
  window and sample size; volatility-based standard errors are reported
  under a Gaussian assumption and understate true uncertainty in fat-tailed
  markets (this caveat is stated, not hidden).
- **Data limitations first.** Dropped holdings, low-R² betas, and partial
  coverage are disclosed in the report body before the reader can discover
  them.

## 7. The report

Each review is delivered as a five-section analyst report, archived
unchanged in the user's decision journal:

1. **Headlines** — three to five one-line figures (portfolio volatility vs.
   benchmark; top risk contributor as "% of risk vs % of money"; effective
   independent bets vs. raw holding count; realised drawdown with window).
2. **Executive summary** — plain-language, descriptive only; no advice
   verbs, no judgement adjectives, no claim not traceable to a computed
   figure.
3. **Detailed analysis** — per-metric: value, standard error, sample size,
   window, estimator citation, and data-quality notes. Written for a
   professional reader.
4. **Conclusion** — ties risk level, diversification quality, and
   concentration together; introduces no new numbers.
5. **Recommendations** — generated by a deterministic rule engine with fixed
   thresholds and templates (e.g., a single holding contributing ≥ 40% of
   portfolio risk; effective bets < 2 across ≥ 8 holdings; β ≥ 1.3 with
   adequate R²). The AI layer orders and phrases triggered recommendations;
   it cannot invent one. If no rule fires, the report says so plainly.
   All recommended actions are framed within the simulation.

Plain language is used in sections 1, 2, and 5; technical register in
section 3. The registers are not mixed.

## 8. Validation

The methodology was developed under an adversarial internal review process:
every quantitative claim above (the Lo confidence intervals, the estimator
standard-error asymmetry, the correlation-blindness of the Herfindahl
index, the trading-day annualisation bias, the shrinkage-target genealogy)
was independently recomputed from stated formulas by a second reviewer
before adoption, and two claims were corrected in the process. The
implementation carries known-answer tests against closed-form cases —
including the exact configurations that would have exposed each defect
found during review — and boundary tests at every sufficiency threshold.

## References

- Markowitz, H. (1952). "Portfolio Selection." *Journal of Finance* 7(1).
- Lo, A. W. (2002). "The Statistics of Sharpe Ratios." *Financial Analysts
  Journal* 58(4).
- Ledoit, O. & Wolf, M. (2004). "Honey, I Shrunk the Sample Covariance
  Matrix." *Journal of Portfolio Management* 30(4).
- Choueifaty, Y. & Coignard, Y. (2008). "Toward Maximum Diversification."
  *Journal of Portfolio Management* 35(1).
- Choueifaty, Y., Froidure, T. & Reynier, J. (2012). "Properties of the
  Most Diversified Portfolio." *Journal of Investment Strategies* 2(2).

---

*Internal reference: CR136 Rev 3.*
