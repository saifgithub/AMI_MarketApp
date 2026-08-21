# M15 — BSM greeks

**Origin:** CR172 §5 (options simulation, slice 1) · **Status:** done (library + guards; slice-1 chain enrichment is the first consumer)

## What
Delta, gamma, theta, vega, rho — per share, with `per_contract` scaling by the contract multiplier
(a parameter, never a hard-coded 100: adjusted contracts exist, CR172 §3). yfinance serves **no
greeks at all**, so these are the only greeks in the product.

## Why opened
CR172 §9's `max_portfolio_delta`/`max_portfolio_vega` mandate caps, §10's candidate cards
(`net_greeks{}`) and §11's delta-adjusted portfolio-health treatment all need greeks that trace to
a deterministic function. A greek that cannot be computed returns None — never 0.0, because 0.0 is
a confident claim of no exposure at all (DEF169).

## Formula
`bs_greeks(kind, spot, strike, t_years, rate, sigma, dividend_yield=0)` → `Greeks` NamedTuple.
Conventions stated because each has a rival that silently changes the number:
- **Theta per CALENDAR day** (annual/365). The per-trading-day convention (/252) differs by ~30%,
  and a mark that decays 7 days a week is what the slice-2 weekend NAV tick needs (CR172 §7).
- **Vega per 1 volatility point** (dPrice/dσ ÷ 100); **rho per 1 rate point** (÷ 100).
- Delta/gamma unscaled (per $1 of underlying).

## Source data
Same inputs as M14; sigma is the enrichment layer's `iv_used` (provider IV when sane, else M16).

## Consumed by
`services/option_chain.py::enrich_chain` (slice 1); M16's Newton step (analytic vega);
M17's `combine_greeks` → slice-2 candidate cards and portfolio greek aggregation.

## Computed in
`app/trading_math/greeks.py::bs_greeks` / `per_contract`.

## Guard test
`tests/unit/test_cr172_trading_math_options.py` — every greek checked against central finite
differences of `bs_price` itself (reference-free: a transcribed constant cannot green a broken
formula), the /365-not-/252 theta convention pinned by ratio, put delta negative, `per_contract`
scaling. Mutation-proven (theta /365 → /252 → red).

## Changelog
- 2026-08-20 (CR172 slice 1, AT:R73): created.
