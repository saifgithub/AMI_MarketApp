# M12 — Return-series metrics: CAGR, max drawdown, Sharpe

**Origin:** CR054 §4.5 (BOK Wave-1 numbers) + the CR046 D1 backlog · **Status:** done (library + guards; Wave-1 lessons are the consumer)

## What
The three performance figures the BOK's worked examples need — compound annual growth rate, deepest
peak-to-trough drawdown, and the annualised Sharpe ratio — hand-rolled as pure stdlib functions.

## Why opened — and why hand-rolled, not `empyrical-reloaded`
CR046 Decision D1 flagged adopting `empyrical-reloaded` for this family, **held back pending dep
sign-off** (lean-stack rule). The W0d lane brief resolves the tension for the BOK's slice: the three
metrics Wave 1 actually needs are trivial (a power, a running max, a mean/sd ratio), so they're
hand-rolled dependency-free and the library stays copy-portable. **No new dependency shipped.** The
wider family (Sortino, Calmar, rolling vol) stays on the D1 backlog and would revisit
`empyrical-reloaded` — D1 is narrowed, not overturned.

## Formula
All presented figures, 2 dp.
- `cagr_pct(start_value, end_value, years)` — ((end/start)^(1/years) − 1) × 100. Negative for a
  losing span; None when either value or the span is non-positive.
- `max_drawdown_pct(values)` — deepest (peak − v)/peak over a running peak, positive percent. The
  running-peak sibling of M05's point-in-time `drawdown_pct`. 0.0 for a never-falling series; None
  for an empty series or any non-positive value.
- `sharpe_ratio(returns_pct, risk_free_rate_pct=0.0, periods_per_year=252)` — mean excess return /
  sample sd of excess returns × √periods_per_year. Per-period returns in percent; the risk-free
  rate is ANNUAL, spread evenly across periods. None below 2 observations, on a flat excess series
  (zero sd — a Sharpe of "infinity" is a number a lesson must not ship), or non-positive
  `periods_per_year`.

## Source data
Lesson-authored example value/return series — pedagogical inputs. (The sim portfolio's real equity
curve is the obvious future live input; see Consumed by.)

## Consumed by
**No production caller yet — by design.** Wave-1 lesson authoring (M20–M21 + performance lessons).
Live candidates downstream: the sim portfolio summary could surface real CAGR/max-drawdown/Sharpe,
making these agent- and user-facing — that wiring is a future changelog line here, not assumed.

## Computed in
`app/trading_math/returns.py::cagr_pct` / `max_drawdown_pct` / `sharpe_ratio` (sd via
`portfolio_stats.variance` — M11 — so the sample convention has one definition).

## Guard test
`tests/unit/test_trading_math_bok.py` — the doubling anchor (2× in 10y → 7.18%/yr), a negative CAGR
for a losing span, peak-to-trough-not-first-to-last drawdown (50% beats the earlier 25%), a known
Sharpe (mean 2 / sd √2 → 22.45 annualised, 1.41 unannualised), the risk-free rate lowering the
ratio (11.22), and the None-on-nonsense guards (single observation, flat series, zero periods,
non-positive values).

## Changelog
- 2026-07-21 (CR054-W0d, AT:coder.math): created — the Sharpe/max-drawdown/CAGR slice of the D1
  backlog shipped hand-rolled (no new dependency); Sortino/Calmar/vol remain on the backlog.
