# CR136 — External PM review (hostile-reader pass)

**What this is:** the professional-portfolio-manager review the methodology doc
(`PORTFOLIO_REVIEW_METHODOLOGY.md`) was written to invite — *"prepared for
external review … a portfolio manager, risk officer, or quantitatively literate
adviser."* Requested by Saiful 2026-08-02; performed against **CR136 Rev 3**,
the methodology doc v1.0, `SCREEN_DESIGNS.md`, the auditor spec pack, and both
track-U audit rounds. Reviewer independently recomputed the doc's load-bearing
figures and checked the mandate/safety-floor layer (`trading_math/sizing.py`,
`agents/safety_floor.py`, `agents/overlay_generator.py`) before forming views.

TRACK: K · ROLE: Kimi · INSTANCE: -

**Status:** review artifact. None of the demands below are adopted changes —
disposition (accept / reject / defer) is the architect's call, item by item.

---

## Verdict

**The statistical spine is sound — better than most retail risk products.
But as designed, it measures the recent past with more forward-looking
confidence than the data holds, and its advice layer is pinned by heuristics
in a document that derives everything else.** Conditional approval. Five
must-fixes before this should go in front of a client.

## What survives hostile reading (credit, because it's earned)

- The governing principle is correct and independently recomputed: Lo (2002)
  SE on a measured annualized Sharpe of 1.0 at T=90 gives 95% CI
  **[−2.28, +4.28]**; **~970 trading days** to significance. Refusing to ship
  Sharpe at retail horizons is statistically right.
- The holdings-based pivot (Rev 2) is the correct architecture; matches
  institutional practice (FMR patent US10157419B1 substance verified
  line-by-line by the track-U auditor).
- Ledoit–Wolf cited **by title** (constant-correlation target, JPM 2004),
  PSD by convexity — correct.
- DR² over HHI, with the 60/40/ρ=0 → 1.54 probe disclosed. Honest.
- Null-not-zero, strip-before-assembly, post-generation digit validation with
  deterministic fallback — the structurally correct way to put an LLM on top
  of quant output.
- Plumbing pinned correctly: trading-day-only series, √252, SPY adjusted
  close, inner-join date alignment, mock-mode refusal.

## Must-fix (ship-blockers)

1. **The framework measures one regime and quietly assumes it persists.**
   A 126–252 day equal-weighted window estimates the covariance of the regime
   just passed. Correlations are non-stationary and spike in crises (Longin &
   Solnik, *JF* 2001; Ang & Bekaert, *RFS* 2002; March 2020: S&P 500 pairwise
   correlations converged toward ~0.8, CBOE implied correlation at record
   levels). A user whose window ends February 2020 gets a "4 effective bets"
   report two weeks before the book correlates to one. The doc caveats fat
   tails but never addresses non-stationarity — the larger error by an order
   of magnitude. **Demand:** standing regime caveat in every Finding, plus
   the scenario panel (item 6) as the structural mitigation.
2. **The uncertainty contract quantifies the wrong uncertainty; the most
   consequential estimator choice is the only unpinned one.** `σ/√(2T)` is
   estimation error about *the window's own* σ; the user reads volatility as
   forward-looking, and forecast error under vol clustering is far larger.
   Every estimator is pinned except **uniform time weighting** — implicit,
   unnamed, unjustified in a document whose standard is "every choice traces
   to a named methodology." Industry standard for short-window risk is EWMA
   (RiskMetrics Technical Document, 1996, λ=0.94 daily). Uniform windows also
   produce the roll-off artifact: a vol spike exits the 126-day window and σ̂
   drops discontinuously — the user reads "risk fell" when nothing changed.
   Not mandating EWMA; demanding the choice be pinned, cited, and the
   roll-off artifact stated in the methodology doc.
3. **The advice layer is five underived heuristics in a document that derives
   everything else.** R1 40%, R2 DR²<2.0 ∧ N≥8, R3 β≥1.3, R4 cash≥40% — no
   stated basis, and they are cliffs on continuous quantities (40.0% → 40.1%
   flips the report). **Demand:** derivation, calibration, or an explicit
   "engineering judgment, to be calibrated" admission per threshold, plus
   hysteresis/near-threshold bands. Also: R3's template ("a 10% market move
   has historically meant ~{β×10}% for this book") is a fitted-value statement
   stripped of dispersion — with R²=0.3 and σₚ=25%, residual σ around that
   fitted value is ~21pp. Attach residual dispersion or rephrase.
4. **It ignores the user's own mandate — the most defensible rule available.**
   The safety floor already enforces a single-name position cap, a
   sector-concentration cap (default 40%, tolerance-tiered), and a
   max-positions limit — per-user, mandate-derived. The Finding's rule engine
   references none of it: two concentration verdicts that can contradict each
   other in front of the same user. Add rule R0 evaluating the book against
   the user's own configured caps ("NVDA is 30% of your book against your
   stated 20% single-name cap"). Product-coherence defect, not a math one.
5. **The signature number has no measured error — and nothing requires
   measuring it.** "62% of your risk comes from NVDA" is a ratio of estimated
   covariance terms; Michaud (1989) is the canonical warning that Σ estimation
   error amplifies in derived quantities. At T/N = 5 the sampling error on a
   top-contributor share is plausibly ±15–20pp, yet R1 fires a directive at a
   hard 40% line on it. Rev 2 ran a Monte Carlo for the calendar-padding
   defect; no equivalent operating-point study is in acceptance. **Demand,
   pre-ship:** simulation study at the actual operating points (T=126/252,
   N=5–40, realistic correlation structures) measuring estimator RMSE for σₚ,
   β, DR², and top-contributor share vs known-truth Σ; publish the error
   magnitudes in the methodology doc; calibrate R1's threshold to them.

## Should-fix (not ship-blockers)

6. **No scenario panel.** VaR/CVaR exclusion is correct, but applying
   historical benchmark episodes (Mar 2020: −34% in 23 sessions; 2022: −25%
   over ~9 months) through current β needs no tail estimation and fits the
   estimability principle exactly. The FMR patent the design leans on has
   scenario simulation at its core; the design cites the patent and omits its
   central output.
7. **TEV is missing.** The patent's headline output, a pure second-moment
   quantity computable from the same Σ plus the benchmark leg already being
   fetched. Answers "how different is this book from the benchmark?" — in
   neither the shipping set nor the out-of-scope list. An omission, not a
   decision.
8. **No ETF look-through.** SPY + QQQ + AAPL reads as three positions; the
   report never says "you own Apple three times." Morningstar X-Ray is the
   retail-standard tool; needs holdings data, not a factor model. Top-three
   lesson for an education app.
9. **The Tier-2 drawdown floor (≥2 snapshots) is vacuous.** Max drawdown of a
   two-point series carries zero information, shipped under the "descriptive"
   exemption. Gate descriptive stats too: minimum ~21 trading days before the
   tile renders.
10. **Report-to-report change is uncontextualized.** Daily user-triggered
    Findings on slow-moving statistics, with no "what changed and is it
    bigger than estimation error" framing, trains over-monitoring of noise —
    the behavioral failure CR137's own cited research argues against. The
    SEs ship; use them between reports.
11. **Digit-sequence validation needs a normalization rule.** "23%" vs
    "22.98%" vs "0.2298" — undefined rounding/format equivalence means either
    constant fallback firing (LLM layer becomes dead code) or holes. Pin it
    in the contract.
12. **Data hygiene gate.** No outlier screen on the return series feeding Σ;
    one bad adjusted close from yfinance prints a phantom ±40% "return"
    straight into covariance. Add a volatility-scaled bad-print filter.

## Does it meet the need?

Without must-fixes 1–5, the Finding is an elegant, well-cited measurement of
the recent past whose advice layer a professional would discount to zero.
With them, it is a report a PM would forward to a client unredacted.

## References cited in this review

- Lo, A. W. (2002). "The Statistics of Sharpe Ratios." *FAJ* 58(4).
- Longin, F. & Solnik, B. (2001). "Extreme Correlation of International
  Equity Markets." *Journal of Finance* 56(2).
- Ang, A. & Bekaert, G. (2002). "International Asset Allocation with Regime
  Shifts." *Review of Financial Studies* 15(4).
- J.P. Morgan (1996). *RiskMetrics Technical Document*, 4th ed. (EWMA,
  λ=0.94 daily).
- Michaud, R. O. (1989). "The Markowitz Optimization Enigma: Is 'Optimized'
  Optimal?" *Financial Analysts Journal* 45(1).
- Ledoit, O. & Wolf, M. (2004). "Honey, I Shrunk the Sample Covariance
  Matrix." *JPM* 30(4).
- Choueifaty, Y. & Coignard, Y. (2008). "Toward Maximum Diversification."
  *JPM* 35(1).
- FMR LLC, US10157419B1, "Multi-factor risk modeling platform."
