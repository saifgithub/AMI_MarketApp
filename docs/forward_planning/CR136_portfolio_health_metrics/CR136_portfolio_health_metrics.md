# CR136 — Portfolio Health: whole-portfolio, risk-based evaluation

**Status:** proposed (build queued) · **Filed:** 2026-08-02 (AT:R65)
**Revised:** 2026-08-02 (AT:R65) — **Rev 2, quant review. The Rev 1 math was
wrong in its foundation and has been replaced.** See "Rev 2 — quant review"
below.
**Revised:** 2026-08-02 (AT:R65) — **Rev 3, r1 audit integration** (track-U
audit confirmed C1–C5; sufficiency thresholds and estimator pinned).
**Revised:** 2026-08-02 (AT:R65) — **Rev 4, build-final. Integrates BOTH
adversarial external reviews** (`EXTERNAL_PM_REVIEW.md`, 21 findings, 6+1
blockers; `PM_REVIEW.md`, track K, 5 must-fixes) **after independently
re-simulating every load-bearing prescription** (7-agent verification fleet,
2026-08-02 — record in "Rev 4 — verification record" below). Several review
prescriptions were themselves corrected by measurement before being pinned.
**This revision supersedes Rev 3's estimator, rule engine, and validator
pins. Build from Rev 4 only.**
**Build docs:** [`build/`](build/) — the module-by-module development
documentation (M01–M11) the build team consumes. The pins live here; the
per-file implementation detail lives there.
**Precedes:** CR137 — Portfolio Room (reserved by number, not yet filed; see below)

## Why

AMI Trade's entire core loop is single-ticker: the 12-agent Room, the Portfolio
Manager's APPROVE/REJECT/MODIFY verdict, Convene the Room, Brief Your Agent — all
convene on **one ticker** and produce a verdict on **one proposed trade**
(`docs/initial_specs/02_agents/convene_the_room.md:3` — *"All 12 agents run on a
single ticker"*). Portfolio state is only ever read as *context* for that one-trade
verdict.

Saiful flagged the gap directly: nothing steps back and evaluates the **whole
portfolio** — diversification, risk decomposition, market sensitivity — the way
a real analyst team would. A codebase-wide check confirmed this is real:

- The only portfolio-wide feature live today is **CR026** (sector allocation +
  concentration cap) — one dimension of many.
- Two math modules exist fully built with **zero live call sites**:
  `backend/app/trading_math/portfolio_stats.py` (variance, covariance,
  correlation, CAPM beta, `wᵀΣw`) and `backend/app/trading_math/returns.py`
  (CAGR, max drawdown, Sharpe).
- No stored history of portfolio value over time exists.
- No existing CR or Defect scopes whole-portfolio evaluation.

The premise is also empirically strong: Goetzmann & Kumar (2008) — 25.5% of
retail portfolios held one stock, 54.9% held three or fewer, and the authors
attribute it to *"naive diversification… without giving proper consideration to
the correlations among the stocks."* That is precisely what this feature
measures and what weight-counting misses.

**Decided with Saiful:**

- *"Full portfolio scoped room, phase B. We go all in. This is an agentic app.
  But all math must be deterministic."* CR136 = the deterministic metrics
  engine; CR137 = the portfolio-scoped Room consuming it. Agents narrate and
  debate; they never compute (CR046 discipline, CR040 "prompt instructions are
  not controls").
- History: **backfill AND persist going forward.**
- Recommendations framing: **conditional-educational, never imperative**
  (decided 2026-08-02 on the F6 compliance finding — see "The Finding" §F5).
- ETF policy: **correlation carve-out + disclosure** (decided 2026-08-02 —
  covariance metrics ship for ETF books; weight-based outputs carry an
  explicit overlap disclosure; constituent look-through is a follow-up CR).
- Extra metrics approved into v1 (2026-08-02): **tracking error, MCR per
  holding, scenario panel, "typical bad month" (parametric)**.
- Access: **config-driven gate** — trial window for everyone (14 days or 7
  Findings, whichever exhausts sooner; daily cap), then plan-gated. See
  "Access gating".

## The governing principle — what is estimable, and what is not

Every metric decision follows from one measured asymmetry. For an asset with
20% annualised volatility, the standard error of the estimated **mean return**
is `σ/√years`, while the standard error of the estimated **volatility** is
`≈ σ/√(2T)`:

| Data available | Obs | SE of annualised **mean return** | SE of annualised **volatility** |
|---|---|---|---|
| 3 months | 64 | **40.0 pp** | 1.77 pp |
| 1 year | 252 | 20.0 pp | 0.89 pp |
| 5 years | 1,260 | 8.9 pp | 0.40 pp |
| 20 years | 5,040 | 4.5 pp | 0.20 pp |

Mean returns are **not estimable** at any horizon a retail user will ever
have. Second moments — volatility, covariance, correlation, beta — are
estimable from months.

**Therefore: any metric with a mean-return term in its numerator is not
shippable, and every metric without one is.**

- **Excluded** (mean-return numerator): Sharpe, Sortino, Treynor, Jensen's
  alpha, information ratio.
- **Included** (pure second-moment): portfolio volatility, beta+R², tracking
  error, diversification ratio, risk contribution, MCR, correlation.

Supporting figures, as verified in Rev 4 (fleet agent `closedforms`, Lo Eq. 9
re-derived + Monte Carlo): a measured annualised Sharpe of 1.0 at T=90 has a
95% CI of **[−2.28, +4.28]**; a true Sharpe of 1.0 needs **~970 trading days**
(z=1.959964; 971 at z=1.96) merely to reach a **50%-power** significance
threshold, and **1,982 trading days (7.9 years)** for 80% power (MC rejection
rates measured 49.7% / 80.2%). The honest statement is the power-labelled one.

Institutional context, stated honestly (F18): this feature is
**holdings-based, single-benchmark, covariance-estimated**. Institutional
platforms (Barra, Axioma, Bloomberg PORT; the FMR/Fidelity patent
US10157419B1) additionally build multi-factor models; a factor model is a
roadmap deferral, not something this CR claims. The patent's TEV language
appears in its **specification, not its claims** (F12 provenance correction) —
we cite its *shape* (holdings-based, decomposition-led), not claim-level
equivalence. Rev 4 adds tracking error so the decomposition-led shape is
matched by an actual relative-risk number.

## The framework

Two tiers. Tier 1 is the product; Tier 2 is realised history that accumulates
behind it **and is the validation layer for Tier 1** (F16 — promoted from
"nicety" in Rev 4).

### Tier 1 — forward-looking, holdings-based (works on day one)

Computed from **current holdings × each holding's own return history** —
needs the *securities* to have history, not the *portfolio*. All Σ-derived
numbers are **backcasts of today's weights applied to past returns** (F14) and
every surface says so.

All Tier-1 metrics derive from **one EWMA-weighted covariance matrix** built
once per evaluation over the risky holdings **plus the benchmark leg** (SPY
adjusted close). Build Σ once, derive everything:

| Metric | Definition | Notes | Basis |
|---|---|---|---|
| **Portfolio volatility** σₚ (annualised) | `√(wᵀΣw)` | SE published via **T_eff**, see estimator pins | LEVEL — total book (cash dilutes it, exactly ×(1−c)) |
| **Beta vs. SPY** + **R²** | `Cov_w(p,b)/Var_w(b)` from the same Σ; R² = weighted ρ² | R² < 0.20 sets `low_explanatory_power`; beta is a backcast and is labelled one | LEVEL — total book (also exactly ×(1−c)) |
| **Tracking error** | `√(σₚ² + σ_b² − 2βσ_b²)` | Identity verified; at σₚ=26.20/σ_b=15.87/β=1.301 → 16.82% | LEVEL |
| **Effective independent bets** DR² | `DR = (Σwᵢσᵢ)/σₚ`, squared | Cash-invariant (verified exact). Copy says "effective independent bets", never a literal count | SHARE-family — invested sleeve |
| **Risk contribution** per holding + sector | `wᵢ(Σw)ᵢ/σₚ²`, sums to 100% | The headline output. Cash contributes exactly 0; shares identical on total vs invested basis (verified to 3e-16) | SHARE — displayed on invested sleeve |
| **MCR** per holding | `(Σw)ᵢ/σₚ` | *New in Rev 4 (F3).* The true per-dollar quantity; powers any trim statement. Funding convention: trim-to-cash | SHARE-family — invested sleeve |
| **Weight concentration** HHI → effective-N | `Σvᵢ²`, `1/HHI` over **invested-sleeve** weights vᵢ | *Basis changed in Rev 4 (F9):* total-value HHI is non-monotone in cash (measured eff-N 2.63→3.53→3.37→2.38 across 0/20/40/60% cash, peak at 27.5%). Invested sleeve only; labelled "invested weight concentration"; carries the ETF-overlap disclosure. DEF149's total-value convention continues to govern the *allocation donut* — two surfaces, two labelled bases | SHARE — invested sleeve |
| **Typical bad month** | `1.645 · σₚ · √(21/252)` | *New in Rev 4 (F13).* Phrased as historical dispersion ("a 1-in-20 bad month over the window measured has been about −X%"), never a forecast; Gaussian understatement of tails disclosed. z=1.645, 1 month = 21 trading days (pins verified: reproduces 2.71%/6.07%/12.44% at σ=26.2% for 1d/1w/1mo) | LEVEL |
| **Scenario panel** | `β × episode benchmark return` | *New in Rev 4.* Fixed named episodes: COVID crash 2020-02-19→03-23 (S&P 500 ≈ −33.9%), 2022 drawdown 2022-01-03→10-12 (≈ −25.4%) — constants verified against the SPY **price** series at build time (M02 acceptance) — **amended 2026-08-02 (AT:R66)**, see the Rev 4 amendments section. Rendered only when the beta block is sufficient; labelled a backcast what-if with the R² share stated; **never** a prediction | LEVEL |

**SHARE vs LEVEL rule (F9, verified):** SHARE-type quantities (risk shares,
money shares, MCR ranks, weight concentration) are **invested-sleeve**;
LEVEL-type quantities (σₚ, β, TE, bad month, scenarios) are **total-book**. No
sentence or figure mixes bases; R4 is the only sentence allowed to bridge
them, and it names exactly what cash does: scales σₚ and β by the invested
fraction (measured exactly ×(1−c)); leaves risk shares, DR² and R² unchanged
(measured exactly invariant).

**DR² caveat (upheld + extended in Rev 4):** DR² penalises vol imbalance as
well as correlation — measured: 60/40 SPY/AGG (ρ=0.154) reads DR² 1.278,
nearly equal to the SPY+QQQ+AAPL overlap book's 1.261. DR² detects
non-diversification; **risk contributions disambiguate the cause**. Copy never
presents DR² alone as a diagnosis.

### Tier 2 — realised, snapshot-based (descriptive; the validation layer)

| Metric | Rev 4 pin |
|---|---|
| Equity curve | Ships when history exists |
| **Realised max drawdown** | **Rolling trailing 252-trading-day window** (F10 — expanding-window MDD is a monotone ratchet, verified min day-over-day change exactly 0.0; the rolling window restores improvability: measured 87.4% of paths improve after de-risking vs 0.0% expanding). Floor: **≥ 21 trading-day snapshots** before the tile renders (the old "≥2 snapshots" floor was vacuous). Window always stated. Optionally shown beside the random-walk reference for the same window (table values 10.4/14.8/20.7/28.2% at σ=20% for 3m/6m/1y/2y — provenance: discrete-daily geometric-walk simulation; the closed form √(π/2)σ√T is the continuous arithmetic-BM reference and overstates these by 17–26%, so it is not quoted as their source) |
| Realised return, window-labelled | Descriptive only |
| **`predicted_vol_ann` on every snapshot row** | *New in Rev 4 (F16).* The daily snapshot job stores the Tier-1 predicted vol (+ `n_observations`, `engine_version`) alongside realised value, making the model permanently auditable. Acceptance carries the institutional **bias test**: z = realised return / predicted vol must have sd ≈ 1 (at T=252 the acceptance band is [0.911, 1.089]) |

**No composite score.** Correction to Rev 2's stated reason (F18): Morningstar
publishes its Portfolio Risk Score methodology in full — what is proprietary
is the underlying covariance data. The decision stands on its real ground: a
composite hides the components this app exists to teach, and any weighting we
chose would be ours to defend with nothing behind it.

### Sufficiency contract (Rev 4 — supersedes Rev 3 table)

All thresholds in **trading days**, counted as returns. Code reads them from
one `SUFFICIENCY` constant block — never scattered literals.

| Metric | Floor | `standard_error` |
|---|---|---|
| σₚ | **T ≥ 126 observed returns** (window coverage: 1−λ^126 = 97.85% of EWMA weight; ESS 62.9 = 96% of asymptote — floor verified still meaningful under EWMA) | `σ̂ₚ/√(2·T_eff)` with **T_eff = 1/Σᵗwₜ² ≈ 63–66** — *not* σ/√(2T). Publishing the equal-weight formula under EWMA understates the true sampling SE by ~27% (measured 1.72pp true vs 1.26pp naive at σ=20%) |
| Beta + R² | T ≥ 126, same aligned window (inner join with SPY) | WLS SE: `SE(β̂) = (σ_ε,w/σ_b,w)/√T_eff` (numpy-fixture acceptance test) |
| Tracking error | inherits beta sufficiency | **null** — a derived quantity; its components (σₚ, σ_b, β) each publish their own SE. Same convention as bad-month/scenarios |
| DR², risk contribution, MCR | T ≥ 126 **and T/N ≥ 5** | null by decision (documented); rules gate via hysteresis instead |
| HHI / invested weight concentration | none — accounting | null always |
| Typical bad month, scenarios | inherit σₚ / beta sufficiency respectively | null (derived quantities; components carry the SEs) |
| Tier-2 rolling MDD | ≥ 21 trading-day snapshots | null always (descriptive) |

- **T/N ≥ 5 scope narrowed (F17, verified):** for a fixed weight vector the
  relative sampling error of σ̂ₚ is `1/√(2T)` **independent of N** — measured
  6.29–6.37% across N = 5…200 at T = 126, unchanged even where the sample
  covariance is singular (N=200, rank 125). The gate applies **only** to DR²,
  risk contributions and MCR (which touch off-diagonals); σₚ and beta gate on
  T alone. A 60-name book gets σₚ and beta; its DR²/shares block reads
  insufficient — with copy naming *our* limit, not the user's book.
- **Short-history holding rule:** a holding with < 126 observations is dropped
  from Σ, weights renormalised, `partial: true` + `dropped_holdings`. Dropped
  weight > 20% of **invested value** → whole Tier-1 block `sufficient: false`.
  Disclosed as a simplification: institutional models blend a structural
  estimate for young securities (Barra USE4 §5.1); we drop and say so (F18).
- **Data-hygiene gate (Rev 4, PM_REVIEW §7D):** deterministic bad-print screen
  on every return series before Σ — a same-day |return| exceeding a
  volatility-scaled bound with next-day reversal (exact algorithm in M01) marks
  the holding dropped-for-quality that window: `partial: true`,
  `dropped_holdings` entry with `reason: "data_quality"`. Never silently
  repaired, never silently included.
- **Fat-tail honesty (F7, corrected + verified):** SE inflation over Gaussian
  is `√((κ_excess+2)/2)` — at excess kurtosis 30 the factor is **4.0×**
  (5.04pp at T=126, σ=20%), but κ≈30 is a crash-inclusive long-sample figure;
  a window-realistic κ_excess of 3–6 gives **SE ≈ 2.0–2.5pp (10–13% of the
  estimate)**. §F3 discloses the realistic range and notes the crash-window
  bound. (The prior "~1.9×" text corresponded to κ≈5.2, not 30.)
- **Fat-tail vs regime honesty (PM_REVIEW must-fix 1/2):** the published SE is
  estimation error of the *window's own* σ — not forecast error. Every Finding
  carries the standing non-stationarity caveat (see §F3/§F4): the window
  describes the regime just passed; correlations converge toward 1 in crises
  (Longin & Solnik 2001; Ang & Bekaert 2002; March 2020 ≈ 0.8 pairwise). The
  scenario panel is the structural mitigation.
- **ETF policy (F21, re-graded by measurement):** ETFs are **not** excluded.
  Verified with real market data: covariance metrics price ETF overlap
  automatically — equal-weight SPY+QQQ+AAPL reads **DR² = 1.261** (not ~3),
  AAPL 41.1% of risk, ρ(SPY,QQQ) = 0.952; 50/50 SPY+QQQ reads DR² = 1.024.
  Excluding ETFs would also delete the engine's best teaching output for
  correct ETF users (60/40 SPY+AGG: SPY = 94.5% of risk at 60% of money).
  The **weight-based outputs are the blind ones**: HHI and mandate-cap checks
  count an ETF as one holding — measured understatement of true single-name
  exposure ≈ 5pp (AAPL 38.5% look-through vs 33.3% naive), enough to cross a
  35% cap silently. Pin: weight tile + R0 carry `contains_etfs: true` and the
  fixed disclosure *"counts each ETF as one holding; index-fund overlap is not
  looked through — your true single-name exposure can be higher."*
  Constituent look-through is a follow-up CR.
- **Small books (F1-adjacent, verified):** N=1 → σₚ = the holding's vol
  (valid), DR² ≡ 1 rendered as the single-holding state, risk share ≡ 100%
  with copy that a one-position book has no diversification to measure. N=2 →
  all metrics fine under the Rev 4 estimator (no LW). Explicit boundary tests.
- **Mock-data refusal** unchanged: `use_real_market_data=false` → the engine
  refuses (amber system-unavailable state, per SCREEN_DESIGNS).
- **Benchmark misalignment** unchanged: inner-join failure → beta/TE blocks
  insufficient, never re-gridded.

### Estimator pins (Rev 4 — supersedes Rev 3; every pin measured)

1. **The estimator is the EWMA-weighted sample covariance, λ = 0.97,
   weighted-demeaned, over the risky sleeve plus the benchmark leg. There is
   NO Ledoit–Wolf shrinkage on any shipped metric.** Rationale, measured:
   - LW constant-correlation shrinkage **suppresses the alarm this feature
     exists to raise** (F2, confirmed): on a twin-pair book with true
     DR² = 1.855, rule R2 fires in 89.0% of plain-sample windows vs **30.1%**
     shrunk (4,000-rep MC, T=126); shrunk σₚ biased −5.7%. The DR²
     silencing point is **δ\* = 0.4371** (analytic; the review's "~0.5"
     corrected), and the fitted δ on this book has median 0.609 — past the
     silencing point. LW is the remedy for inverting Σ; we never invert.
   - LW's target also **divides by zero on a cash row** (F1, confirmed: NaN
     matrix, σₚ = nan → serialises to the same null that means "insufficient
     data") and is undefined at N=1, degenerate at N=2 (23% of seeds hard-NaN,
     the rest a meaningless δ=1.0). Removing LW retires the whole defect
     class; if a δ diagnostic is ever added back, those short-circuits are
     mandatory.
   - EWMA(0.97) kills the **rolling-window echo** (F11, confirmed: the
     equal-weight window drops −2.9pp discontinuously the day an old shock
     exits — 50× the median daily change; EWMA responds *at* the event,
     half-life 22.8d, exit-day change −0.03pp). λ=0.97 is RiskMetrics'
     *investing* factor; 0.94 is the 1-day-VaR trading factor and would
     discard most of the disclosed window (ESS 32 vs 66).
   - Measured cost, disclosed not hidden: EWMA's ESS ≈ 65.7 makes single-report
     R2 detection on the twin book **82.1%** vs equal-weight's 89.0% — the
     price of no echo and no silencing (LW's 30.1%). Do not re-add shrinkage
     to claw it back.
2. **Cash handling:** Σ is estimated over risky holdings only; the cash row is
   appended as exact zeros. Euler identity verified exact under EWMA
   (Σ contributions = 1 to 3.3e-16 across 200 seeds; cash contributes
   exactly 0.0; quadratic form ≡ weighted portfolio-series vol to 2.3e-16 —
   structural, by bilinearity).
3. **Weight convention:** `w` spans total portfolio value, cash as the zero
   row (unchanged from Rev 3; DEF149-consistent). Display bases follow the
   SHARE/LEVEL rule above.
4. **Data window:** fetch 2 years of daily bars; estimator uses up to 504
   returns with EWMA weights (ESS 65.61 at 252d lookback vs 65.67 at 504d —
   negligible difference; 252d lookback acceptable if the data layer prefers
   it). Sufficiency floor T ≥ 126 observed returns.
5. **Benchmark:** SPY adjusted close, inner join on candle timestamps.
   `beta()`-style length-only checks are insufficient (portfolio_stats.py:58 —
   the existing function validates length, not dates); the engine aligns by
   date before any math.
6. **Annualisation:** √252, trading-day series only. IID caveat disclosed in
   §F3 (the serial-correlation objection applied to Lo also applies to √252
   annualisation — stated, not hidden).
7. **Implementation home:** `trading_math/`, stdlib-only, no numpy (package
   contract verified: `trading_math/__init__.py` — pure functions, stdlib
   only, copy-portable). N ≤ ~50, T ≤ 504 → pure Python is milliseconds.
   Known-answer fixtures generated offline against an independent numpy
   implementation, stored as literals. **Fixtures must include a non-uniform
   correlation structure** (F8, confirmed: a uniform-ρ fixture passes
   identically even when an estimator is fully degenerate — it cannot detect
   the failure mode that matters).
8. **`engine_version: "cr136.v1"`** on every block.

## The uncertainty contract (required, because an LLM consumes this)

Quants compute, agents interpret — so the quant layer's output is an **LLM
input**, and an agent will confidently narrate whatever it is handed. Every
metric block carries, structurally:

```json
{
  "metric": "portfolio_volatility",
  "value": null,
  "standard_error": null,
  "n_observations": 0,
  "t_eff": null,
  "window_days": 0,
  "sufficient": false,
  "partial": false,
  "dropped_holdings": [],
  "low_explanatory_power": null,
  "contains_etfs": false,
  "backcast": true,
  "basis": "total_value",
  "engine_version": "cr136.v1"
}
```

Hard rules (unchanged from Rev 3, plus Rev 4 fields):

- `sufficient: false` ⇒ `value` **and** `standard_error` are **null**. Never
  `0.0`. Null is what makes enforcement structural (CR038).
- `partial: true` ⇒ `dropped_holdings` non-empty (each entry carries a
  `reason`: `"short_history"` or `"data_quality"`), on every surface.
- `basis` ∈ {`total_value`, `invested_sleeve`, `weights`} — the SHARE/LEVEL
  rule made machine-readable.
- `backcast: true` on every Σ-derived block (F14) — the renderer and the Room
  must label these as today's-weights-on-past-returns.
- `t_eff` present wherever an SE uses it.
- `engine_version` everywhere; old journal entries stay interpretable.

The context builder **strips** insufficient blocks before prompt assembly —
the model never sees the metric name, so there is nothing to narrate.

## The Finding — the user-facing report

Unchanged standard: every Finding must survive a professional portfolio
manager actively looking for a reason to dismiss it — *"extremely critical, to
the point of being rude."* Numbers carry method, window, and sample size.
Limitations are disclosed **before** the reader finds them. No judgement
adjectives. No claim outside the payload.

**Disclosure placement (F19, reversed from SCREEN_DESIGNS' foot-of-report):**
the disclosure block renders at the **head** of the Finding and is stored in
the journal payload: `disclaimerShort` ("Educational simulation. Not
investment advice." — app_en.arb:1362), gross-of-fees + zero-cost simulation
line, backcast line, window + estimator line, and the standing
non-stationarity caveat. The journal entry is what survives and gets
screenshotted; it carries the same head block.

Five sections. Register split: §F1/§F2/§F5 plain language; §F3 technical; §F4
bridges. The split is now **structurally enforced** (register lexicon check —
see prompt contract), and §F1's R² mandate is amended: the flag is surfaced in
plain language (*"the market explains only X% of this book's day-to-day
moves"*), never as "R²" — the literal form would trip the register check by
design.

**§F1 Headlines** (3–5 one-liners; each = one number + its plain meaning)

- Required: σₚ with benchmark σ alongside; top risk contributor as "X% of
  risk vs Y% of invested money"; effective independent bets next to raw
  holding count; rolling-window max drawdown with window (Tier 2, when
  sufficient); beta in plain language with the explanatory-power flag when
  set.
- ≤ 16 words per headline (enforced); `partial` marker inline when built on a
  partial metric.

**§F2 Executive summary** (4–8 sentences, descriptive only)

- Required: risk-posture sentence (σₚ vs benchmark σ, TE); diversification
  sentence (DR² vs holding count, with the vol-imbalance caveat honoured);
  concentration sentence (top contributor, invested basis); window +
  sufficiency + backcast disclosure sentence.
- Forbidden: advice verbs, mean-return/performance claims, any number not in
  the payload.

**§F3 Detailed analysis** (one block per metric — the PM's section)

- Required per block: value, SE where defined (with `t_eff` stated),
  `n_observations`, `window_days`, estimator name + citation (EWMA λ=0.97,
  *RiskMetrics Technical Document* 4th ed. §5.3.2; Markowitz; Choueifaty &
  Coignard 2008; CAPM), one line of "what this measures", data-quality notes.
- Required once: the estimator disclosure (EWMA weighting, effective sample
  ≈ 66 days, why: no roll-off echo), the fat-tail honesty range, the IID/√252
  caveat, the gross-of-fees + zero-cost-sim line, the backcast statement, the
  **standing non-stationarity caveat** (verbatim pin): *"These estimates
  describe the window just past. In market stress, correlations between
  holdings rise sharply — diversification measured in calm markets can
  overstate the protection available in a crisis."*
- Cross-references CR054's M11/M12 BOK lessons.

**§F4 Conclusion** (2–4 sentences)

- Ties risk level, diversification quality, concentration. Restates window
  and limits. No new numbers.

**§F5 What the numbers point to** (renamed from "Actionable recommendations" — F6)

- **Speech-act pin (compliance):** every item is **conditional-educational** —
  a general statement of textbook practice, with the user's own number shown
  as the trigger. Never an imperative on the user's tickers, no severity
  bands, no "you should". Pattern: *"When a single position accounts for more
  than 40% of a portfolio's risk, the textbook response is to consider whether
  the concentration is intentional. In this book, NVDA accounts for 62% of
  risk while holding 30% of invested value."*
- Grounds: the publisher's exclusion is unavailable (15 U.S.C.
  §80b-2(a)(11)(D); Lowe v. SEC; SEC Rule 203A-3(a)(3) — per-account
  generation is not impersonal); worldwide store distribution puts FCA/MiFID
  II/CMA/SC perimeters in scope at alpha; and the live site states the product
  *"does not and will not give investment advice"*
  (website_api/app/knowledge/faq.md:45, faq_answer.py:103 refusal). The
  educational framing keeps the site's statement true on every path,
  **including the deterministic fallback** (which ships the same templates).
- Zero-cost disclosure beside any trimming discussion (Barber & Odean: ~97% of
  the measured activity penalty is invisible in a zero-cost sim).
- None triggered ⇒ the section says so plainly.

Presentation surfaces: the Portfolio Health card (scope 7) carries §F1 + the
entry point; the full Finding is a detail view; the journal stores the
rendered sections + payload. `sufficient: false` renders the explicit "not
enough data yet" state — whose copy names **our** data limit when that is the
cause (F20: *"price history available to the engine covers N days; 126
needed"*), never the user's holdings.

## Recommendation rule engine (deterministic — the LLM never invents advice)

Rules fire on the stripped metric context. Templates are fixed strings with
slots; **a template may not contain any number the engine did not itself
register** (F15 — this is what makes the validator's allow-list closed).
Thresholds + hysteresis bands live in the same constant block as SUFFICIENCY.

**Hysteresis (F4, verified — supersedes bare thresholds):** estimated-quantity
rules are two-line state machines: **fire** when crossing the fire line,
**stay fired** until crossing the clear line. Initial state: cleared. State is
persisted in the Finding's journal payload (`rule_states`) and read back from
the newest prior Finding for the same `portfolio_id` (same read the
idempotency check already does). CI-lower-bound gating is **rejected** by
measurement: detection collapses to ~50.8% on a genuinely high-beta (1.45)
book with 18.6% flips — worse than the point gate on both axes. Accounting
rules (R0, R5) mirror their source exactly and carry no band.

| Rule | Fire | Clear | Template (conditional-educational form) | Verified basis |
|---|---|---|---|---|
| **R0 mandate check** *(new — PM_REVIEW §7B)* | any holding's weight > its resolved mandate cap, or a sector > the resolved sector cap — **computed by the same resolvers, on the same denominator, as the trade gate** (`trading_math/sizing.py`: `resolved_single_name_cap_pct:73` / `resolved_sector_cap_pct:87`; presets `DEFAULT_RISK_TIER_CAPS:22`, `SINGLE_NAME_ABSOLUTE_CAP_PCT:35`, `DEFAULT_CONCENTRATION_TOLERANCE_CAPS:43-45`), mirroring `check_mandate_compliance` (**defined** `backend/app/agents/safety_floor.py:173`; the holdings loop that R0 mirrors is `:600-628`; called from `sim_engine.py:607-628`) | mirror of fire | "Your mandate caps a single {scope} at {cap}%. {name} is at {weight}% of your total portfolio value today." + ETF disclosure when `contains_etfs` | The most defensible rule in the set — the threshold is the user's own stated limit. No band: a violation mirrors the trade gate exactly, so the two layers can never disagree. **R0 is the one deliberate exception to the SHARE/LEVEL rule: its weights are TOTAL-VALUE, not invested-sleeve** — the gate's own denominator is `position_pct(market_value, portfolio_value)` (`trading_math/portfolio.py:35-39`) over total portfolio value, so an invested-sleeve R0 would fire where the gate does not, which is precisely the contradiction R0 exists to remove. Its `basis` field reads `total_value`, and its copy says "of your total portfolio value" so no sentence silently mixes bases |
| **R1 concentration** | top risk share ≥ **41.5%** AND risky holdings ≥ **4** | < **38.5%** | "When a single position accounts for more than 40% of a portfolio's risk, the textbook response is to consider whether the concentration is intentional. Here, {ticker} accounts for {risk_share}% of risk while holding {weight}% of invested value." | Reworded (F3 — the old per-dollar sentence is mathematically false; on the F3 book it names the holding whose trim is 2.23× *less* effective). Band ±1.5pp = 0.6× measured per-window sd (~2.2–2.4pp at T/N=5; PM_REVIEW's ±15–20pp refuted, off 4–7×): worst flip 7.7%, detection 95.6% at true 44%. n≥4 gate: small books have structurally high top shares (60/40 SPY+AGG: 94.5%) — the always-present contribution table carries the fact; the rule stays silent |
| **R2 correlated cluster** | DR² < **1.85** AND holdings ≥ 8 | > **2.15** | "You hold {n} positions but about {dr2} effective independent bets — they have tended to move together. Textbook practice adds exposures that behave differently, not more of the same." | Band ±0.15 measured: 5.5% flips, 99.3% detection (true 1.7), 1.3% false-fire (true 2.3). Mandatory under EWMA — boundary flips are 21.3% without it |
| **R2b pairwise overlap** *(new — F21)* | any pair of holdings each ≥ 5% invested weight with ρ ≥ **0.90** | ρ < **0.85** | "{a} and {b} moved almost identically over the window (correlation {rho}). Two holdings that move together provide less diversification than two that don't." | The rule that actually catches SPY+QQQ (ρ=0.952 measured) — R2's n≥8 gate structurally silences every small book (verified: DR² < 2.0 on every overlap book tested at n=2–5, R2 fired on none). Naively lowering R2's gate false-fires on 60/40 SPY+AGG (DR²=1.278 from vol imbalance at ρ=0.154); the pairwise test separates every book tested. Band 0.05 ≈ 3× SE(ρ̂) at ρ=0.9, T=126 |
| **R3 market sensitivity** | β̂ ≥ 1.3 + **0.6·SE(β̂)** AND R² ≥ 0.2 | β̂ < 1.3 − 0.6·SE(β̂) | "β = {beta} (market explains {r2_pct}% of daily moves; {window}-day window) — this book has moved about {beta}× the S&P 500 over the measured window." | Projection clause deleted (F5 — a forecast in the grammar of a fact, on history that doesn't exist, using a daily beta that doesn't transfer to a 10% multi-day move). 0.6·SE band verified: worst flip 8.0%, detection 96.0% at true β 1.45; self-scales with sample size |
| **R4 cash drag** | cash ≥ 41% of total value | < 39% | "{cash}% of your book is cash. Cash scales the whole-book volatility and beta down in proportion — it does not change how concentrated the invested sleeve is: risk shares and effective bets are unchanged by it." | Rewritten (F9 — the old "dilutes every risk number" is false: measured, cash scales σₚ and β exactly ×(1−c), leaves DR²/shares/R² exactly invariant). ±1pp band is convention (accounting quantity; suppresses drift flap) |
| **R5 data limits** | any `partial: true` | mirror | "Metrics exclude {dropped} ({reasons}). Treat the numbers as describing {covered}% of your invested value." | `{covered}` pinned to invested-value basis (1 − dropped/invested) — matches the template's own words and the 20% sufficiency rule |

Simulation-only guard unchanged: all copy lives inside the sim's educational
frame; the §F5 speech-act pin applies to every template above.

## LLM prompt contract (CR136's renderer now; CR137's Room later)

Structural rules, in enforcement order:

1. **Strip before assembly** (unchanged).
2. **Comparisons are precomputed.** Context metrics shipped for citation:
   benchmark volatility, TE, and the scenario constants. If a comparison is
   not in the payload, it is not said.
3. **Prompt skeleton** — as Rev 3, plus: *"Number-bearing statements about
   volatility, beta, diversification and risk contribution describe the
   measured window only and are backcasts of today's holdings"*, and the §F1
   plain-language R² amendment.
4. **Output is structured** (sectioned JSON; renderer owns formatting).
5. **Post-generation validation (Rev 4 — supersedes Rev 3's digit rule,
   which is deleted).** Measured: the naive digit-sequence validator rejects
   the CR's own mandated §F3 content (10–13 of 25 digit runs), flips verdicts
   on the 4th decimal of a rounding path, and rejects R3's own deterministic
   fallback — it cannot ship. The Rev 4 validator:
   - **Allowed-token allow-list**, built per Finding from the same stripped
     context, as two scale-aware sets (PCT and RAW): (a) every numeric leaf of
     every sufficient block, rendered at 0–2 dp (PCT, ×100) and 1–4 dp + verbatim
     (RAW), each under both round-half-up and round-half-even, each ±1 ulp at
     its dp; (b) every value the rule engine interpolates into any template
     (corollary: templates may not contain unregistered numbers); (c) a fixed
     constants list checked in beside SUFFICIENCY (citation years, 252, 95,
     1.96, 500, M11/M12, …); (d) `n_observations`/`window_days`/holding-count
     integers verbatim.
   - **Normalization:** tokenize digit groups incl. thousands separators;
     canonicalize (strip separators, Decimal-normalize); a token followed by
     %/pp/percent looks up PCT, else RAW — **scale-aware lookup, never the
     union** (measured: the union false-accepts "Your beta is 62.").
   - **Rejection:** any non-member token ⇒ discard the entire model output,
     log tokens + section id (degrade loudly), render the deterministic
     templates — which emit only registered tokens and therefore validate by
     construction (measured 0 self-rejections).
   - **Register check (F19, structural):** §F1/§F2/§F5 must not match a
     20-term technical lexicon (shrinkage, covariance, OLS, R², standard
     error, estimator, regression, confidence interval, kurtosis, Ledoit,
     Markowitz, Choueifaty, CAPM, pro-forma, eigen\*, quadratic, sampling
     error, heteroskedastic\*, JPM, EWMA); §F1 headlines ≤ 16 words; §F3/§F4
     exempt. Measured 0/10 false positives on plausible §F2 prose. Same
     rejection path.
   - **Documented residuals, not claimed away:** 0-dp percent tokens carry a
     ±1pp accept window (necessary — 0.625 legitimately renders 62% or 63%);
     the validator checks token membership, not metric binding — binding is
     owned by the sectioned-JSON schema + deterministic fallback.

## Journal storage plan

As Rev 3 (verified against source in Rev 4), with corrections and additions:

- `EntryType.PORTFOLIO_HEALTH_ANALYSIS = "portfolio_health_analysis"` — no DB
  migration (String column, `backend/app/db/models.py:267`), **but** the Python
  enum member is required (`journal_store.py:84-86` raises on unknown strings)
  and the mobile enum + wire mapping must ship.
  **`test_journal_entry_type_parity.py` (DEF210) needs no code edit** —
  measured at HEAD, its assertions are set-derived, so it passes only when the
  backend enum and the Dart model agree. What it actually enforces is
  **same-commit atomicity**: adding the backend member without the Dart value
  (or vice versa) fails the build. Ship both in one commit.
- Idempotency: app-level check-before-insert on `(portfolio_id, as_of)` via
  the newest `portfolio_health_analysis` entry (same read that loads
  `rule_states`). Series never spans a reset (`reset_portfolio` is
  destroy-and-recreate, sim_engine.py:394-403).
- Payload: full stripped metric context + triggered rule ids with slot values
  + `rule_states` (hysteresis) + the five rendered sections as markdown + the
  **head disclosure block** (F19 — the archived artefact carries its own
  disclosures forever).
- Mobile detail rendering: the journal detail payload path renders bare
  `Text` today (journal_detail_screen.dart:550) and unknown types fall back to
  a slate "UNKNOWN" card via the nullable `entryType` (DEF210 —
  journal.dart:40-62). CR136 adds the enum value, the wire mapping, and a
  markdown-rendering branch (`flutter_markdown_plus` ^1.0.3 already in
  pubspec.yaml:74). Until the mobile build ships, old clients degrade safely
  to the UNKNOWN card — acceptable interim, verified.

## Access gating (new in Rev 4 — Saiful's decision, 2026-08-02)

Config-driven, all knobs in `Settings` (and therefore forwarded in
docker-compose's api-alpha block — `test_config_compose_parity.py:71` fails
the build otherwise):

| Setting | Default | Meaning |
|---|---|---|
| `portfolio_health_gate_mode` | `trial` | `open` \| `trial` \| `plan` |
| `portfolio_health_trial_days` | 14 | trial window, counted from the user's **first Finding** |
| `portfolio_health_trial_findings` | 7 | trial Finding budget; window OR budget exhausting first ends the trial |
| `portfolio_health_daily_cap` | 2 | per-portfolio Findings per day (all modes) |
| `portfolio_health_plans` | `TRADER,FLOOR_MANAGER` | plans with post-trial access (and full access in `plan` mode) |

- The **Health card tiles are free for everyone in every mode** — cheap
  deterministic reads, no LLM, no journal write. Gating applies to **full
  Finding generation** only.
- Trial accounting reuses the journal as the counter: count of
  `portfolio_health_analysis` entries (soft-deleted rows included) + the
  first entry's `created_at`. No new table.
- Enforcement composes three existing services (verified): `effective_plan()`
  (entitlements.py — trial-expiry-aware), the `RateLimiter` dependency
  pattern (rate_limit.py, DEF184-bounded), and — if Finding generation is ever
  credit-metered instead — `credit_service.py`'s audited spend. Mode `plan`
  + plans list covers the post-trial state Saiful described: *"in the
  beginning, we will allow everyone at least 1 or 2 a day, and after a while
  (14 days or 7 times, whichever is sooner) the user would no longer have
  access"* — i.e. `trial` mode is the launch default; flipping to full
  plan-gating later is a config change, not a code change.
- Mobile: the card's CTA carries the trial-remaining / upgrade states (M09).

## Cohesion map

```text
price_history_daily (M01) ──► EWMA Σ (M02, one matrix incl. SPY leg)
     │                              │
     │                    metrics engine (M04) — uncertainty contract
     │                              │
     │               GET /v1/portfolio/health  (M07, gate: tiles free)
     │                              │
     │                context builder (strip insufficient)
     │                              │
     │        ┌─────────────────────┼──────────────────────┐
     │        ▼                     ▼                      ▼
     │   Health card (M09)     CR137 Room             Finding renderer (M06)
     │   §F1 tiles             (narrate only)         rules (M05) + validator
     │                                                     │
     │                                          journal_entries (M08)
     ▼                                          payload + rule_states
portfolio_value_snapshots (M03)                       ▲
  + predicted_vol_ann  ──────── bias test ────────────┘  (Tier 2 validates Tier 1)
```

Degrade matrix: mock data → refuse (amber); partial → disclosed everywhere;
insufficient → null + strip + our-limit copy; misaligned benchmark → beta/TE
insufficient; LLM down or output rejected → deterministic templates (still a
correct, complete report); gate exhausted → tiles remain, generation returns
the gate state.

## Scope (build order — data layer first, F20)

The market-data foundation is **the critical path** and is scope item 1, not
a footnote: today's `_PERIOD_MAP` (market_data.py:150-157) serves daily bars
only via `1m` (22) and `3m` (65) — max **64 daily returns** against a floor of
126, so on the current layer every Tier-1 metric reads insufficient for every
user. The 60s history TTL (market_data.py:399/:437) and the absence of any
batch primitive make per-dashboard fetches N sequential Yahoo round-trips.

Module-by-module development documentation lives in
[`build/`](build/) (M01–M11): market-data foundation; estimator core
(trading_math); snapshot job + Tier 2; metrics engine service; rule engine;
Finding renderer + validator + LLM path; API + gating; journal integration;
mobile (card + Finding + journal); backfill; verification + promotion. Each
module doc carries its own file list, function contracts, test list, and
acceptance criteria, sized for a single build session.

## Out of scope

- CR137 Portfolio Room (reserved; sketch below).
- Mean-numerator ratios (Sharpe, Sortino, Treynor, alpha, IR) — permanently,
  per the governing principle.
- **Historical/simulation VaR and CVaR** (the parametric "typical bad month"
  ships; the honest reasons for excluding the rest: Gaussian tails understate,
  dollar figures invite prediction readings — not "insufficient history",
  which was wrong for parametric VaR, F13).
- **Multi-factor risk model** (Barra/Axioma-class) — roadmap deferral,
  disclosed as such (F18).
- **ETF constituent look-through** — follow-up CR (the disclosure ships now).
- Composite single risk score (real reason stated above).
- Multi-portfolio (existing v1.0/Floor Manager gate).

---

## Rev 2 — quant review (2026-08-02) — historical record

*(Kept verbatim as the record of what Rev 1 got wrong; the Rev 2 estimator
choices were themselves superseded by Rev 4 where noted.)*

Saiful challenged the Rev 1 math: *"The quant based of Aladdin as been proven?
Do we know what it does? … So look deeper into the quant maths. Are we doing it
right? Be critical."* The review found the Rev 1 foundation wrong.

### The framing error: institutional precedent was cited, then contradicted

Rev 1 cited institutional holdings-based risk platforms as precedent and then
designed the structurally opposite system. **FMR LLC's (Fidelity's) patent**
(**US10157419B1**, "Multi-factor risk modeling platform") documents the
institutional methodology: risk derives from current holdings × factor
exposures, *not* the portfolio's historical track record. Holdings-based
analysis is the documented industry choice for short track records, and it is
why Morningstar runs both approaches. Rev 1 picked the approach that cannot
work for a new user. *(Rev 4 note: TEV appears in the patent's specification,
not its claims — the citation is to its shape, not claim-level equivalence.)*

### Seven defects found in the Rev 1 math

1. **Sharpe was statistically meaningless at the planned horizon** (Lo 2002:
   at 90 obs a measured Sharpe of 1.0 has 95% CI [−2.28, +4.28]).
2. **Naive HHI overstates diversification by up to 8.2×** (correlation-blind;
   ten ρ=0.8 mega-caps read effective-N 10.0 vs DR² 1.22). *(Rev 4 note:
   8.2× is not a ceiling — 24.2× at N=30.)*
3. **Risk-free rate defaults to 0.0** repo-wide (2.29× Sharpe overstatement at
   rf=4.5%) — moot once mean-term metrics were dropped.
4. **Calendar-day padding UNDERSTATES volatility ~15%** (√(252/365) = 0.831;
   Monte Carlo 0.845×) — trading-day gating required. *(Direction was itself
   corrected during Rev 2 — first draft had it backwards.)*
5. **Two different quantities both called "drawdown"**:
   `trading_math/portfolio.py::drawdown_pct` (vs starting capital) vs
   `returns.py::max_drawdown_pct` (peak-to-trough) — $10k→$15k→$12k reads
   0.0% vs 20%. *(Path corrected in Rev 4: it is `trading_math/portfolio.py`,
   not `services/portfolio.py`.)*
6. **`wᵀΣw` was dismissed as a stretch goal** — it is the centrepiece.
7. **`beta()` checks length, not dates** (portfolio_stats.py:58) — silent
   wrong beta on misaligned grids.

### One Rev 1 worry the codebase cleared

Time-weighted return is not required: `current_cash` writes are creation, buy,
sell only (sim_engine.py:387/891/915); no top-ups or credits exist; naive
period returns are arithmetically valid within a portfolio lifetime. The
reset endpoint is a series discontinuity, handled by keying series to
`portfolio_id`. There is **no fee/commission/slippage** in the sim — all
returns are gross; disclosed wherever performance-adjacent numbers appear.

---

## Rev 4 amendments (2026-08-02, AT:R66 — during the build)

**Scenario-episode basis: PRICE, not adjusted.** The Tier-1 table originally read
"constants verified against the SPY *adjusted* series". That sentence was
internally contradictory and is now corrected: measured 2026-08-02 against the
index sources themselves,

| source | COVID 2020-02-19→03-23 | 2022 01-03→10-12 |
|---|---|---|
| `^GSPC` — S&P 500 **price** index | **−33.92%** (pin −33.90%, 0.02pp) | **−25.43%** (pin −25.40%, 0.03pp) |
| `^SP500TR` — S&P 500 **total-return** index | −33.79% (0.11pp) | −24.49% (**0.91pp**) |
| SPY adjusted close (total return) | −33.72% (0.18pp) | −24.50% (**0.90pp**) |

The pinned constants ARE the price-index returns, to 0.02–0.03pp. They cannot
verify against a total-return series over a nine-month episode — the gap is the
dividend yield, and it exceeds M02's own 0.5pp tolerance. The price basis is also
the one the product needs: the sim pays no dividends
(`Rev 2 — one worry the codebase cleared`), so a total-return episode constant
would tell a user their book would have lost *less* than a price-only book
actually would.

`backend/scripts/cr136_generate_fixtures.py --verify-scenarios` gates on the
price basis (`auto_adjust=False`) and prints the total-return figure beside it,
un-gating. M02 §3 and M11 §3.3 are amended to match.

*The constants are unchanged. Only the sentence describing how they were
verified was wrong.*

## Rev 4 — verification record (2026-08-02)

Two independent adversarial reviews were run against the Rev 3 pack:

1. **`EXTERNAL_PM_REVIEW.md`** — hostile-reader PM review; 21 findings, 6+1
   blockers; every quantitative claim in the pack independently re-derived.
2. **`PM_REVIEW.md`** — track-K independent review; 5 must-fixes, 7
   should-fixes; overlapping but distinct coverage.

Before integrating, **every load-bearing prescription was re-simulated by a
7-agent verification fleet** (estimator, rules, closed forms, cash artefact,
ETF see-through with live market data, repo source checks, validator
prototypes — all agents executed code; simulation scripts preserved in the
session scratchpad, seeds fixed). The two reviews had themselves warned that
prescriptions asserted without simulation tend to be wrong — the external
review's own first draft had two such errors it corrected (CI-gating; δ≤0.7).
The fleet found more:

### Confirmed as prescribed (now pinned above)

F1 cash-row NaN + the risky-only fix (Euler exact to 0.0); F2 LW alarm
suppression (89.0% vs 30.1% measured); F3 R1 falsity (trim-B 2.23× better on
the counterexample book); F4 hysteresis over CI-gating (CI detection 50.8% at
true β 1.45 — rejected); F5 projection deletion; F6 educational reframe; F9
cash artefact (the review's table reproduced exactly; invested-sleeve fix
verified cash-invariant); F10 rolling-window MDD fix (87.4% of paths regain
improvability); F11 EWMA echo elimination; F15 validator failure (rejects the
CR's own mandated content) + allow-list fix (0 false accepts/rejects on 20
randomized cases); F16 bias-test column; F17 T/N gate rescoped (σₚ error
N-independent, measured to N=200 singular); F19 register lexicon check (0/10
false positives); F20 data-layer facts at exact file:line; R0 resolvers exist
as claimed (sizing.py:73/:87).

### Corrected by measurement before pinning (the reviews were wrong here)

- **F21 severity re-graded.** With real market data: covariance metrics
  already price ETF overlap (SPY+QQQ+AAPL: DR² 1.261, AAPL 41.1% of risk,
  ρ(SPY,QQQ) 0.952; SPY+QQQ alone: DR² 1.024). The reviews' "reports as
  diversified" holds **only** for weight-based outputs (~5pp single-name
  understatement), and their prescribed fix — block DR²/risk shares pending
  look-through — would have blocked precisely the metrics that already work.
  The *actual* structural gap found: **R2's n≥8 gate silences the cluster
  warning for every small book** (DR² < 2.0 on every overlap book tested at
  n=2–5; R2 fired on none) → rule R2b added.
- **PM_REVIEW's "±15–20pp" top-contributor sampling error refuted**: measured
  sd ≈ 2.2pp (±4.2pp at 95%) at its own cited operating point (N=25, T=126,
  T/N=5); worst realistic case ±6pp. Recalibrating R1 to the claimed error
  would have been calibrating to a phantom. (EXTERNAL's ±3.6pp was near-right.)
- **EWMA is more flip-prone than what it replaces** (neither review measured
  this): boundary flip rate 21.3% vs equal-weight's 8.9% — so hysteresis is
  **mandatory**, and the published SE must switch to `T_eff` or it
  understates by ~27%. The single-report detection cost (82.1% vs 89.0%) is
  disclosed above.
- **δ silencing point is 0.4371** (analytic), not "~0.5" — which *strengthens*
  F2: the review's real-data median δ (0.476) is past the silencing point.
- **The external review's own F7 table row is mislabelled** (the 1.90× row
  corresponds to excess kurtosis ≈ 5.2, not 3.2 — its own text says so).
- **F10's closed form does not generate its own table**: the values
  (10.4/14.8/20.7/28.2%) come from a discrete-daily geometric walk;
  √(π/2)σ√T overstates them 17–26%. Values kept, provenance fixed.
- **"971 days" belongs to z=1.96; 970 to z=1.959964** — both 50%-power
  figures; the 80%-power figure (1,982 days) is the honest headline.
- **Two path errors** in the reviews' source cites (services/portfolio.py →
  trading_math/portfolio.py; screens/portfolio_screen.dart →
  screens/sim/portfolio_screen.dart) — corrected in the build docs.

### The lesson, recorded

Rev 3 passed a full clause-by-clause audit; both blockers F1/F2 live in the
**composition** of individually-audited pins. And in Rev 4, several review
prescriptions — themselves written to fix those defects — were wrong until
simulated. The standing rule for this CR and its build: **no pin without a
measurement, and no measurement taken on anyone's word.** Acceptance encodes
this: every threshold, band, and estimator choice above has a corresponding
known-answer or Monte Carlo test named in the build docs.

## Acceptance

Backend unit tests (`pytest backend/tests/unit/ -q`, sqlite tempfile):

- **Known-answer estimator fixtures** generated offline vs an independent
  numpy implementation, stored as literals — **including a non-uniform
  correlation fixture** (F8) and an EWMA fixture (λ=0.97, weighted-demeaned).
- **Euler identity**: contributions sum to 1 ± 1e-9 with a cash row, under
  EWMA weighting; cash contributes exactly 0.
- **Closed forms**: DR² uniform-ρ (N=10, ρ=0.8 → 1.22) *plus* the non-uniform
  fixture; TE identity; bad-month arithmetic (2.71/6.07/12.44% at σ=26.2%).
- **Small books**: N=1 and N=2 produce defined, documented outputs.
- **Sufficiency boundaries** at ±1: 125/126 obs; T/N 4.99/5.01 (DR²/shares
  only — σₚ must PASS at T/N < 5); dropped weight 19.9/20.1%; 21-day Tier-2
  floor; SE uses T_eff (a test asserts the equal-weight formula is NOT used).
- **Bad-print gate**: synthetic spike+reversal → dropped-for-quality,
  `partial: true`, reason recorded; a genuine crash day (no reversal) passes.
- **Date alignment**: equal-length off-grid benchmark rejected.
- **Mock-mode refusal** asserted.
- **Hysteresis state machine**: fire/clear boundary tests per rule at ±ε;
  state round-trips through the journal payload; first-Finding = cleared.
- **Rule engine fire/no-fire** at every boundary incl. R0 (cap ±0.1pp — and
  R0 agrees with `check_mandate_compliance` on identical inputs), R1 n-gate
  3/4, R2b ρ 0.899/0.901 + weight floor, R4 band.
- **Validator**: mandated §F3 content passes; fabricated number rejected;
  rounding-path cases (0.6249/0.6251) both accepted; deterministic fallback
  self-validates; register lexicon catches seeded technical leak in §F2,
  passes 10 plain paragraphs; §F1 word cap.
- **Strip test** unchanged. **Journal idempotency + parity**
  (`test_journal_entry_type_parity.py` updated) unchanged.
- **Gate logic**: trial window/budget exhaustion (14d/7 findings,
  whichever sooner), daily cap, mode transitions, tiles never gated.
- **Compose parity**: new Settings fields forwarded (the existing test
  enforces this automatically).

End-to-end (melehost, per module docs M10/M11):

- Independent numpy cross-check of σₚ/β/DR²/shares on one real book to 2dp.
- **Bias-test harness live**: snapshot rows carry `predicted_vol_ann`; the
  z-statistic query runs (its acceptance band matures with data).
- Backfill dry-run → spot-check → `--apply`.
- `/promote-to-alpha`; tick idempotency in `ami_api_alpha` logs; scenario
  constants verified against the live SPY series.
- Mobile release build on iPhone 13/17: five card states, Finding render,
  journal markdown branch, trial/upgrade states; AR/MS strings flagged
  `retranslate:[ar,ms]` per the content-change rule.
- **The hostile-reader pass**: one full generated Finding reviewed against
  the standard (numbers carry method/window/n; disclosures at head; no
  judgement adjectives; every claim payload-traceable; §F5 conditional-
  educational form) — Saiful wearing the rude-PM hat.

## Risk class

New table + background job + endpoint + UI; no money movement, no
safety-floor change — but the math is the product. **Independent audit
remains warranted for the estimator module (M02) and rule engine (M05)**
specifically; the Rev 4 verification fleet's scripts double as the audit's
re-derivation pack. The compliance-sensitive change (§F5 speech act) should
be spot-checked by Saiful against the live website copy before promote.

---

## Phase B — Portfolio Room (CR137, reserved, designed in a follow-up session)

Not built in this CR — this CR's metrics engine is Phase B's prerequisite
ground truth: a **portfolio-scoped Convene the Room**, same multi-agent
architecture, same UI family (Verdict Board / collapsed transcript per CR106),
convening on the whole portfolio instead of one ticker. All math the agents
cite comes from this CR's API — **agents narrate and debate, they never
compute**.

Rough agent-role mapping to work out in that session (not decided here):
Aggressive/Conservative/Neutral Debators (closest fit — risk teams already
reason at portfolio level); Portfolio Manager (natural chair); Trader
(rebalancing-action proposals); Research Manager (adjudicates the risk
debate); the ticker-scoped analysts may not map 1:1 — a smaller coherent
roster beats stretching all 12.

**Precedent (checked 2026-08-01):** BlackRock Aladdin (quant/rules, not LLM);
FinRobot (open-source "Risk Assessment Agents… debate and refine" — closest
shape); AlphaAgents (2026); "Expert Investment Teams" (2026). None combine
institutional-grade deterministic math + a real agent committee + a consumer
education product with the user as CEO. Robo-advisor evidence (Frontiers in
Behavioral Economics) independently supports the "unflappable" framing:
automated rebalancing measurably reduces disposition effect and
trend-chasing.

**Governance note:** CR137 is reserved by number only — no row file, no doc,
until that follow-up design session actually scopes it.
