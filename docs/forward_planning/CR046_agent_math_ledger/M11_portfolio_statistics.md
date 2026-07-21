# M11 — Portfolio statistics: variance, covariance, correlation, beta, wᵀΣw

**Origin:** CR054 §4.5 (BOK Wave-1 numbers) · **Status:** done (library + guards; Wave-1 lessons are the consumer)

## What
The sample statistics under diversification and modern-portfolio-theory teaching — variance,
covariance, Pearson correlation, CAPM beta, and n-asset portfolio variance `wᵀΣw` — so the BOK's
M18–M19 (Level 11) and M20 (evidence) worked examples compute their figures instead of authoring
them.

## Why opened
CR054 Wave 1 needs "correlation 0.3 cuts your portfolio vol from 16% to 13.7%"-style numbers, and
Level 11's whole point *is* those numbers (the diversification benefit is a quantitative claim).
The corpus already teaches correlation qualitatively (lesson 108); the BOK expansion makes it
numeric, which puts it under the CR046 rule.

## Formula
Sample convention (n−1) throughout, equal-length series. Presented figures round 2 dp
(`correlation`, `beta`); dimensioned quantities (`variance`, `covariance`, `portfolio_variance`)
stay unrounded because callers compose them (sqrt → volatility) and format last.
- `variance(values)` — Σ(v−v̄)²/(n−1). None below 2 observations.
- `covariance(xs, ys)` — Σ(x−x̄)(y−ȳ)/(n−1). None on length mismatch.
- `correlation(xs, ys)` — cov/√(var·var), None when either series is flat (a flat series'
  correlation is undefined — omitted, never defaulted).
- `beta(asset, market)` — cov(a,m)/var(m), None on a flat market.
- `portfolio_variance(weights, cov_matrix)` — wᵀΣw. Weights not forced to sum to 1 (long/short and
  levered teaching examples are legal). None when the matrix isn't square-and-matching, isn't
  symmetric (tolerance 1e-9), or yields a negative variance (a hand-typed non-PSD matrix) — a wrong
  number a lesson must not ship.

## Source data
Lesson-authored example return series and covariance matrices — pedagogical inputs.

## Consumed by
**No production caller yet — by design.** Wave-1/2 lesson authoring (M18–M20). A live candidate
exists downstream: the sim portfolio could later surface a real beta/correlation panel, which would
make these agent-facing — that wiring is its own future entry-changelog line, not assumed here.

## Computed in
`app/trading_math/portfolio_stats.py::variance` / `covariance` / `correlation` / `beta` /
`portfolio_variance`.

## Guard test
`tests/unit/test_trading_math_bok.py` — sample-convention variance (n−1), perfect ±1 correlations,
flat-series None, levered-clone beta of 2.0, the classic 60/40 two-asset portfolio variance
(0.01888) checked against the spelled-out teaching formula **and** the diversification claim itself
(portfolio vol < weighted-average vol), plus the shape/symmetry/non-PSD guards.

## Changelog
- 2026-07-21 (CR054-W0d, AT:coder.math): created — opened ahead of Wave-1 lesson authoring.
