# M16 — Implied volatility solver

**Origin:** CR172 §5 (options simulation, slice 1) · **Status:** done (library + guards; slice-1 chain enrichment is the first consumer)

## What
Inverts M14 for sigma: Newton-Raphson on the analytic vega with a maintained bracket, bisecting
whenever Newton stalls or steps outside it. Yahoo's own IV column is of unknown provenance and
occasionally absurd (CR172 §2); this is the check — and the substitute — where it matters.

## Why opened
The enrichment layer needs a sigma for every greek it computes. When the provider's IV fails the
sanity band, the only honest alternative is solving our own from the mid — deterministically,
with an explicit refusal when no answer exists.

## Formula
`implied_vol(kind, price, spot, strike, t_years, rate, dividend_yield=0)` → sigma or None.
- **Non-convergence is an explicit None, never the last iterate** — a sigma the solver could not
  pin down is not a measurement.
- A price outside the no-arbitrage band → None: such a quote implies no volatility, which on an
  illiquid chain is a real answer about the quote, not a solver failure.
- Root confined to `[1e-4, 5.0]`; unreachable inside it → None.
- **Vega collapse is real and handled honestly:** deep ITM at low vol the time value falls below
  any real tick (~1e-7) and NO solver can pin sigma from such a price. The contract is that the
  solved sigma REPRICES to the input within tolerance; sigma-recovery is only promised where the
  quote carries vol information (time value above one cent). Pseudo-precision would be the bug.

## Source data
The strike's mid (only when `classify_option_quote` says tradeable), plus M14's inputs.

## Consumed by
`services/option_chain.py::_enrich_quote` — `iv_source="solved"` marks every figure that came from
here rather than from the provider, so provenance survives to the row.

## Computed in
`app/trading_math/implied_vol.py::implied_vol`.

## Guard test
`tests/unit/test_cr172_trading_math_options.py` — price→sigma→price round trip across a
kind×sigma×strike grid (sigma recovered exactly where time value > $0.01), no-arb band refusals,
None on invalid inputs. Mutation-proven (tolerance/bracket break → red).

## Changelog
- 2026-08-20 (CR172 slice 1, AT:R73): created.
