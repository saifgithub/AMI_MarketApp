# R01 — MIT OCW 18.642, Topics in Mathematics with Applications in Finance (Fall 2024)

Surveyed 2026-09-21, at Saiful's explicit request, framed differently from every other RES008
item to date: *"they may not claim an edge, but they do have the edge"* — this is prospecting a
legitimate MIT course for genuine, extractable, testable technique, not hunting for an
overclaimed recipe to debunk. Course:
`https://ocw.mit.edu/courses/18-642-topics-in-mathematics-with-applications-in-finance-fall-2024/`.
Cross-reference: `PREREG_COMMON.md` (this repo's fixed bar) and
`../../R_market_ml_landscape/R01_wunder_fund_challenge/VERDICT.md` (house style + the "escalate
past AI-summarized WebFetch to primary sources" lesson, applied throughout below).

## What it is

A real MIT undergraduate/graduate course (Fall 2024, 26 sessions, 2×/week, 1.5h each), not a
retail product and not aimed at a trading audience. Core instructor **Dr. Peter Kempthorne**
(MIT), with regular co-instructors **Dr. Vasily Strela** (RBC Capital Markets) and **Dr. Jake
Xia** (Harvard Management Company, and independently a hedge-fund-side portfolio manager whose
own research is presented in Lecture 13). Prerequisites: differential equations, probability/
statistics, linear algebra — this is a quantitatively serious course, not a survey course.

**Grading**: Homework 40%, group presentations 20%, participation 10%, final paper 30%
(confirmed from the Syllabus page). No final exam. A mid-semester group project (lectures
15–17) and a final paper (lecture 26) round out the term; the paper is a 10–15 page individual
effort even when it continues group-project work, graded on math content, writing quality, and
logical flow. Neither the group-project topics (student-chosen from a list of 15, e.g. "How
Human Fallacies Lead to Market Anomalies," "Delta-Hedging — the Basics of Options Trading
Strategies") nor the ~37 final-paper topics (option pricing, portfolio optimization, pairs
trading, momentum, crypto, LSTM/RL applications) constitute course-endorsed claims — they are
student work, ungraded on originality of a "working" strategy, and none is published or
independently reviewable from the OCW site.

**The "Investment Game"** (hedgehogcamp.ai does not appear; the actual mechanic, confirmed from
the course's own page, is simpler): each student picks one publicly traded stock/ETF/currency/
bond, buys at the 2024-09-13 close, can switch once on 2024-10-11, sells at the 2024-11-15
close, and tracks daily P&L on a spreadsheet. Explicitly **does not count toward the final
grade**; the only stakes are the instructors naming the top three performers at term's end. This
is a paper-trading morale exercise over a ~9-week window with n=1 in each participant's hands —
not a technique, not a claim, and far too short and uncontrolled a window to be a testable
mechanism under this repo's method (RES008 never evaluates single-name, single-window, n=1
outcomes as evidence either way).

**Instructor roster matches the brief exactly**: guest lectures from Jeff Shen (BlackRock
Investment Institute, quant equity), Andrew Gunstensen (Mizuho, linear rates), Stefan Andreev
(Two Sigma, PCA in fixed income), James Shepherd (Quantile Technologies/LSEG, counterparty risk),
Andrew W. Lo (MIT Sloan, biomedical portfolio finance), Tarek Mansour (Kalshi, founder), Ross
Garon (Millennium Management, systematic trading), and John Hull (University of Toronto, intro
to ML). 34 lecture-notes files across 26 sessions confirmed present.

**Two guest lectures are IP-restricted and unavailable in any form** — no slides, no video, no
transcript, confirmed by direct 404s and by search results stating explicitly *"Lectures 3 and
22 are not available because guest lecturers did not give IP permission"*:
- **Lecture 3 — Jeff Shen (BlackRock), "Quantitative Equity Investing."** The single guest most
  likely to contain a real systematic-equity edge claim, and it is the one lecture OCW withheld
  entirely. Cannot be assessed at all — not even at the title-only level beyond the calendar
  entry.
- **Lecture 22 — Ross Garon (Millennium Management), "The Spectrum of Systematic Trading
  Strategies in Liquid Instruments."** Same restriction, same result: title only, no content.

This is a real gap, not a dodge on our part — see "Revisit if" below.

## Lecture by lecture findings

Depth key: **Deep** = primary-source PDF/transcript read directly (via WebFetch or downloaded-
PDF page extraction). **Title** = calendar/week-page description only, not independently
verified against primary content. **Restricted** = confirmed unavailable, no assessment
possible beyond the calendar title.

| # | Topic | Speaker | Depth | Tool vs. claim | Performance/edge claim quoted | Testability verdict |
|--:|---|---|---|---|---|---|
| 1 | Intro, financial terms, bond math | Kempthorne/Xia/Strela | Title | Tool (bond math: duration, convexity, yield curves) | None | Not a claim; foundational math |
| 2 | Linear algebra applied to finance | Kempthorne | Title | Tool (vectors/matrices, portfolio valuation, arbitrage, Markov chains) | None | Not a claim |
| 3 | Quantitative equity investing | Jeff Shen, BlackRock | **Restricted** | Unknown | Unknown — cannot assess | Cannot assess; IP-restricted, zero content available |
| 4 | Linear algebra (cont.); probability theory | Kempthorne | Title | Tool (eigenvalues/SVD, probability distributions, moments, covariance) | None | Not a claim |
| 5 | Probability (cont.); stochastic processes I | Kempthorne | Title | Tool (PCA intro, CLT, utility optimization, martingales) | None | Not a claim |
| 6 | Stochastic processes I (cont.); regression | Kempthorne | Title | Tool (martingales, random walks, gambler's ruin, multiple regression) | None | Not a claim |
| 7 | Linear rates, products, and models | Andrew Gunstensen, Mizuho | Title | Tool (LIBOR→SOFR transition, yield-curve construction, swap valuation — market-structure knowledge) | None | Not a claim; describes how a market works, not how to beat it |
| 8 | Regression analysis (cont.) | Kempthorne | Deep (week-page) | Tool (OLS derivation, hat matrix, t/F-tests, GLS) | None | Not a claim |
| 9 | **Principal Component Analysis in finance** | **Stefan Andreev, Two Sigma** | **Deep (full 38-slide deck read)** | **Both** — starts as pure tool, ends with a named, disclosed, backtested trading construction | **Yes — see prose section below** | **Genuine promotion candidate — see below** |
| 10 | Counterparty risk optimization | James Shepherd, Quantile/LSEG | **Deep (full 51-slide deck read)** | Tool (VaR/ES coherent risk measures, historical simulation, convex optimization for initial-margin minimization) | None — explicit "Legal Notice"-free but no performance claim of any kind; this is risk *measurement* infrastructure, not alpha generation | Not a claim; a margin-optimization framework has no "beats buy-and-hold" analogue |
| 11 | Regression (cont.) | Kempthorne | Title | Tool (ridge/lasso/PCR, CAPM empirical estimation, ETF sector regression) | None | Not a claim |
| 12 | Time series analysis | Kempthorne | Title | Tool (stationarity, autocorrelation, AR/MA/ARMA) | None | Not a claim |
| 13 | Portfolio management | Jake Xia | **Deep (full 38-slide deck read)** | Both — endowment-model framework (tool) plus Xia's own unpublished research (a proposed Sharpe-ratio replacement, a crowd-behavior/power-law model of markets) | None — his "New GL Ratio" and crowd model are presented as research questions/frameworks, explicitly not validated with a live or backtested track record on this deck | Not yet a testable claim as presented — no backtest, no live figures; a theoretical framework only (see prose section) |
| 14 | Stochastic processes II | Kempthorne | Title | Tool (Brownian motion, reflection principle, Brownian bridge) | None | Not a claim |
| 15–17 | Mid-semester group project presentations | Students | Restricted (not available to OCW learners) | N/A | N/A | Not applicable — ungraded student work, not course-endorsed content |
| 18 | Applying data science/AI to biomedical portfolios | Andrew W. Lo, MIT Sloan | Title only (transcript exists per OCW metadata but could not be located/fetched after 3 attempts) | Tool/framework (portfolio-theory-based financing structures — "megafunds" — for pooling biomedical R&D risk to attract capital) | Not independently verified in this pass; Lo's parallel peer-reviewed research program on this exact topic is a financial-engineering/structuring framework, not a trading signal | Not a trading-edge claim by nature — it's about capital structure for R&D financing, not market timing or security selection; not falsifiable as a "beats the market" claim because it isn't one |
| 19 | Volatility modeling | Kempthorne | Title | Tool (Garman-Klass, Rogers-Satchell estimators, historical vol case study) | None | Not a claim |
| 20 | Building a regulated exchange for event trading | Tarek Mansour, Kalshi | **Deep (full 13-page transcript read)** | Neither — a founder fireside chat/Q&A on market structure, regulation, and entrepreneurship | Business metrics only: "over a billion dollars of volume in the last month," "30–40% institutional, rest retail," a passing mention that "a lot of hedge funds were arbitraging the election market with other assets like crypto or S&P" (no mechanism, no numbers) | Not a testable trading claim — no strategy, no backtest; volume/growth figures are about Kalshi the business, not about a technique |
| 21 | Black-Scholes, risk-neutral valuation | Kempthorne/Strela/Xia | Title | Tool (derivative pricing framework) | None | Not a claim |
| 22 | Spectrum of systematic trading strategies | Ross Garon, Millennium | **Restricted** | Unknown | Unknown — cannot assess | Cannot assess; IP-restricted, zero content available |
| 23 | Introduction to machine learning | John Hull, U. Toronto | Title | Tool (supervised/unsupervised/RL concepts, neural nets for option pricing, RL for hedging) | None found in available description | Not a claim as described; a methods survey |
| 24 | Stochastic calculus | Kempthorne | Title | Tool (Brownian motion with drift, Itô integrals/isometry) | None | Not a claim |
| 25 | Stochastic calculus (cont.); SDEs | Kempthorne | Title | Tool (Itô's formula, Black-Scholes PDE derivation, geometric Brownian motion, Ornstein-Uhlenbeck) | None | Not a claim |
| 26 | Final paper presentations | Students | Restricted (not available to OCW learners) | N/A | N/A | Not applicable — ungraded/unreviewed student work |

**Depth tally**: 5 lectures read in full primary-source depth (9, 10, 13, 20, plus the Wunder-
style deep read of week-pages for 8); 2 confirmed IP-restricted with zero content (3, 22); the
remaining ~19 assessed at title/calendar-description level only (appropriate per the brief's own
triage — these are the pure-math tool lectures where a light pass was directed) and not
independently verified against primary PDFs beyond what the week-page summaries state.

## The genuine finding: Lecture 9 (Stefan Andreev, Two Sigma) — PCA in fixed income

This is the one lecture in the course that does what Saiful's framing predicted: a practitioner
teaches a general tool (PCA) and then, in the second half of his own deck, discloses a specific,
mechanically complete, honestly-reported trading construction built on it. Read in full (38
slides, `mit18_642_f24_lec09.pdf`, dated September 2024). Andreev's background, stated on slide
2: 18 years as a fixed-income quant — Morgan Stanley (2006–2014), Citadel (2014–2019), Two Sigma
(2020–present, "Quantitative Researcher at Fixed Income RV Fund").

**The tool half (slides 1–19)** is standard, well-taught PCA: derivation via eigendecomposition/
SVD, the OLS-vs-PCA distinction, demeaning/standardizing data, and the specific finance
application of PCA to the US Treasury yield curve — three named factors (**Level, Slope,
Curvature** = PC1/PC2/PC3), a 2-year rolling lookback for covariance estimation, and macro
interpretation of loadings-instability episodes (2008 crisis, taper tantrum, COVID, 2022
tightening are all visibly flagged on the PC1-loadings-stability chart). Nothing here is a
tradeable claim — it's the standard fixed-income-quant PCA workflow, taught competently and
attributed to no proprietary secret.

**The trading construction (slides 20–25), quoted/described precisely:**

- **PC-neutral portfolios**, defined mechanically: given features `[a, b]`, find `α_b` such that
  the portfolio `P = a − α_b·b` has zero weight on PC1 — i.e. a curve trade (e.g. a 2s10s
  steepener sized by PC1 loadings) that is explicitly hedged against the level factor. Extended
  to PC1+PC2-neutral "flies" (3-leg trades, e.g. a 2s10s30s belly fly) via the same linear-algebra
  construction. This is a fully specified, replicable mechanism — not vague. The deck states the
  honest tradeoffs on the very next slide ("PC residual portfolios: Pros/Cons") — lower volatility
  per unit notional cuts both ways: "transaction cost / volatility ratio is much higher" and it
  "requires much higher notional traded to achieve the same target volatility," which "requires
  financing of the bond and long positions... can cause friction... in times of high stress."
  This is a practitioner disclosing the real cost structure, not selling a strategy.
- **"PC-Neutral fly mean reversion strategy" (slide 24), with an actual backtest shown on-slide**:
  construct a PC1/PC2-neutral fly, signal = EWMA z-score of cumulative fly returns (delayed one
  day "to ensure actionability"), position = −signal. The P&L chart (2000–2024, in units of daily
  vol risk) is labeled directly on the chart: **"Sharpe Ratio = 0.09."** Andreev does not inflate
  this — 0.09 is a weak, close-to-noise number and he presents it plainly next to the mean-
  reverting-but-drifting cumulative-return chart, which itself shows a multi-year negative drift
  from ~2008 onward. This is a rare thing in RES008's experience: a disclosed backtest with a
  self-reported number the presenter does not spin upward.
- **PCA-for-hedging worked example (slide 33)**, mechanically complete and dated: thesis "German
  companies will outperform their European peers," period 2010-01-01 to 2011-01-01, sized to
  100mm EUR annualized daily vol. **Option 1** (buy DAX outright): 500mm EUR notional, 75mm EUR
  return, **Sharpe Ratio = 0.75**. **Option 2** (construct a PC1-neutral portfolio — long DAX,
  short the other six European indices weighted by PC1 loadings): 1,500mm EUR notional (due to
  lower vol-per-notional), 230mm EUR return, **Sharpe Ratio = 2.3**. The slide is explicit that
  this is a one-year, single-thesis illustration of the *mechanism* (hedging out the shared "Euro
  Stocks" PC1 factor to isolate a specific relative-value view), not a claimed repeatable edge —
  and the deck's own "PCA Limitations" slide (34) states plainly: "PCA does not imply a causal
  relationship," "robustness can be an issue," and results "can be misleading" if the data isn't
  well-described by a cardinal direction at the center of mass. The very next slide ("Ideas for
  Final Project") explicitly invites students to test robustness across different lookback
  windows and time granularities — i.e. the instructor himself frames this as an open research
  question, not a proven live strategy.
- Every slide of business content ends with a one-line **Legal Notice** (slide 37): "Nothing in
  this presentation constitutes investment, legal, accounting, or tax advice." Consistent with
  Two Sigma's own compliance posture, not a marketing claim.

**Why this is different from everything else RES008 has tested.** C01–C0N and the OSS-stack/
market-ML surveys have repeatedly found either (a) no disclosed mechanism at all, (b) a vague
mechanism dressed in a specific-sounding claim, or (c) a real mechanism with an inflated/
unfalsifiable performance number. Andreev's slide 24 is the opposite failure mode of all three:
**fully disclosed mechanism, honestly reported weak result.** A Sharpe of 0.09 over 24 years on
a PC-neutral fly is, by any practitioner's own admission, not something Two Sigma is running as
a standalone strategy — it's a *pedagogical example of the mechanism*, with the real number
attached instead of a flattering one. That is exactly the kind of practitioner honesty Saiful's
framing predicted this course might contain, and it is genuinely rare enough in this project's
experience to be worth naming directly.

## Candidates for promotion to a C## pre-registration

**One clear candidate: the PC-neutral yield-curve fly / curve-steepener construction (Lecture 9,
Stefan Andreev, Two Sigma).**

- **What would be tested**: not the specific 0.09-Sharpe backtest (RES008 never tests via
  Sharpe ratio — see `PREREG_COMMON.md`), but the *underlying mechanism*: does a PC1/PC2-neutral
  Treasury curve position (built from Fed daily-yield data, rolling 2-year lookback, per
  Andreev's exact construction) beat (a) a matched-notional random-entry placebo and/or (b) a
  naive unhedged curve trade of the same thesis, net of costs, over RES008's fixed
  `DEFINE`/`HOLDOUT` windows? This is fully falsifiable and fully mechanically specified —
  PC weights, lookback window, and neutrality condition are all given exactly in the deck's math
  (slides 10–11, 20).
- **Why it clears the bar `PREREG_COMMON.md` sets** where most surveyed material doesn't: it is
  neither a vague "buy when X" folk rule nor an unfalsifiable "our model works" claim — it is a
  named, linear-algebra-complete construction with a stated (if weak) historical result the
  presenter did not oversell. Testing it honors — rather than gotcha's — a practitioner who
  already told the class the honest number.
- **What would NOT be a fair test**: treating the 2010–2011 German-DAX PC1-neutral example
  (Sharpe 2.3) as "the claim." That slide is explicitly a one-year illustration of the hedging
  *mechanism* with a single, cherry-picked-by-construction thesis window, not a repeatable
  strategy claim — Andreev's own limitations slide and "ideas for final project" slide (asking
  students to investigate lookback-window robustness) confirm he intends it pedagogically, not as
  an edge assertion. Any pre-registration should test the *mechanism* (PC-neutral curve fly with
  mean-reversion signal, per slide 24) over RES008's fixed multi-year windows, not re-run his
  9-month illustration.
- **Complexity note for whoever picks this up**: this requires Treasury/swap yield-curve data at
  multiple tenors (2/3/5/7/10/30Y at minimum) rather than RES008's existing `U-EQ`/`U-CRYPTO`/
  `U-FX` universes — Fed nominal-yield-curve data (`https://www.federalreserve.gov/data/nominal-
  yield-curve.htm`, the same source Andreev cites) is free and appropriate; this would need a new
  fixed-income universe definition in a claim-specific `PREREGISTRATION.md`, narrowing
  `PREREG_COMMON.md` per its own allowed pattern.

**No other candidate clears the bar.** Jake Xia's Lecture 13 research (a proposed Sharpe-ratio
replacement, a crowd-behavior/power-law model) is intellectually serious and self-attributed as
his own working-paper research, but is presented purely as theory — no backtest, no live
figures, nothing falsifiable as given. It would need to be operationalized from scratch (define
the exact "GL ratio" sizing rule, define what "crowd reactive state" means operationally) before
it's even a candidate; as taught, it's a framework, not a technique. Everything else surveyed is
either a pure math/stats tool (no claim to test) or unavailable (Lectures 3, 22).

## Our verdict

**Something in between — mostly a rigorous tools course, with one genuine, honestly-disclosed
trading mechanism.** Saiful's framing ("they may not claim an edge, but they do have the edge")
is partially right and partially not, and it's worth being precise about which part: the *course*
overwhelmingly does not claim an edge — 19 of 26 sessions are pure mathematical/statistical
machinery (linear algebra, probability, stochastic calculus, regression, time series) taught for
their own sake, with zero performance claims of any kind. But it is not accurate to say the whole
course "has the edge" hidden in it either — most of the applications lectures (Gunstensen on
rates market structure, Shepherd on counterparty-risk measurement, Mansour's founder story, Xia's
theoretical frameworks) describe *how markets and risk management work*, not *how to beat them*,
and contain no tradeable mechanism at all, disclosed or otherwise.

The one place the course does hand over something genuinely testable is Andreev's Lecture 9 —
and it's a strong example precisely because of the intellectual honesty framing Saiful asked to
be applied here: a real Two Sigma practitioner taught the general tool, then extended it into a
specific, mechanically complete trading construction, and reported the actual (weak) backtest
number rather than a flattering one. That is worth crediting directly and worth promoting to a
real pre-registration — not because it's likely to show a large edge (a Sharpe of 0.09 as
self-reported is not encouraging), but because it is one of the few pieces of material RES008
has surveyed across all three `R_*` folders that is both fully falsifiable *and* honestly
sourced, which is the combination this project exists to find.

## Why this verdict

- 19 of 26 lectures are load-bearing math/stats infrastructure (PCA mechanics, regression, time
  series, stochastic calculus, Black-Scholes derivation) — genuinely excellent teaching material,
  zero performance claims, not applicable to RES008's testing method by design (there is nothing
  to falsify in "here is how to compute an eigendecomposition").
- Of the 7 named industry-guest lectures, 2 are completely inaccessible (Shen/BlackRock,
  Garon/Millennium — the two guests statistically most likely to discuss live systematic-equity
  or multi-strategy edge, given their firms), 1 is a founder/business-story fireside chat with no
  trading content (Mansour/Kalshi), 1 is pure risk-measurement infrastructure with no edge claim
  (Shepherd/Quantile), 1 is a theoretical framework not yet operationalized as a testable claim
  (Xia's own research, Lecture 13), 1 is a capital-structuring/securitization framework rather
  than a market-timing or security-selection claim (Lo/Sloan, not independently verified this
  pass), and exactly 1 (Andreev/Two Sigma, Lecture 9) discloses a complete, falsifiable mechanism
  with an honestly-reported result.
- This matches the base rate RES008 has found across `R_oss_stack` and `R_market_ml_landscape`:
  genuinely testable, honestly disclosed mechanisms are rare, but this project's method is
  specifically built to recognize one when it appears rather than dismiss serious material by
  reflex. Andreev's slide 24 and slide 33 both show real practitioner-grade financial engineering
  applied transparently — crediting that accurately, while still being honest that the headline
  self-reported number is weak, is exactly the posture Saiful asked for.

## Revisit if

- OCW ever lifts the IP restriction on Lecture 3 (Jeff Shen, BlackRock, quantitative equity
  investing) or Lecture 22 (Ross Garon, Millennium, systematic trading strategies) — both are
  higher-probability sources of a concrete equity or multi-strategy edge claim than anything
  reviewed here, and both are currently a hard zero, not a "probably nothing."
- A primary-source transcript or slide deck for Lecture 18 (Andrew W. Lo, biomedical portfolios)
  becomes fetchable — this pass relied on the week-page description plus general knowledge of
  Lo's public "megafund" research program, not a direct read of this specific lecture's content;
  flagged above as not independently verified.
- Someone wants to operationalize Jake Xia's "GL ratio" (Lecture 13) or crowd/power-law model
  into a concrete, testable sizing rule — as taught it's a framework, not yet a claim, but it
  is a named, self-attributed piece of original research (not a folk rule) and could become a
  legitimate C## candidate once a specific operational definition exists.
- A future episode wants a positive/credit-where-due contrast case against the more typical
  YouTube overclaiming episodes RES008 has tested — Andreev's Lecture 9 (disclosed mechanism,
  honestly weak self-reported result) is a clean, named, non-scammy example of what responsible
  disclosure of a real trading construction looks like, structurally similar in spirit to the
  Wunder Fund case (`R_market_ml_landscape/R01`) but for a *trading mechanism* rather than a
  *forecasting contest*.
- Someone picks up the PC-neutral curve-fly candidate for an actual `C##/PREREGISTRATION.md` —
  the mechanism, lookback window, and data source are all specified above and in the source deck;
  it would be the first RES008 claim requiring a fixed-income/yield-curve universe rather than
  `U-EQ`/`U-CRYPTO`/`U-FX`.
