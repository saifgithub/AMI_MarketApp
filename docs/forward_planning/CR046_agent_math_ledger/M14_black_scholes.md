# M14 — Black-Scholes-Merton price

**Origin:** CR172 §5 (options simulation, slice 1) · **Status:** done (library + guards; slice-1 chain enrichment is the first consumer)

## What
The BSM European option price with continuous dividend yield — the model price behind every option
figure an AMI agent presents. yfinance serves chains with bid/ask/IV but **no greeks and no
risk-free rate** (CR172 §2), so the pricer, the greeks (M15) and the IV solver (M16) are computed
here; the LLM never does the sum and neither does Yahoo.

## Why opened
CR172's whole design is "AMI computes, the PM picks an index, the user consents". A strike, premium
or greek invented by an LLM is DEF059's shape on a bigger surface, and CR038 measured what a prompt
instruction is worth against it (~70% non-compliance). Every downstream number — chain enrichment,
M17 structure metrics, the slice-2 candidate cards — roots in this price.

## Formula
`bs_price(kind, spot, strike, t_years, rate, sigma, dividend_yield=0)` — Merton's continuous-yield
extension; `bs_d1_d2` computes the shared quantiles once. Full precision (presentation rounds, not
the pricer — unlike M10's 2-dp lesson figures). Invalid inputs → None, never a guess: `t_years<=0`
is refused (at expiry the price IS intrinsic and that is M10's job), `sigma<=0` is refused (a
deterministic forward, not a priced option).

**Self-guard:** `put_call_parity_gap` — `C − P = S·e^(−qT) − K·e^(−rT)` is sigma-free, so the guard
tests catch a sign/discounting error without trusting any reference number the same code produced.

**Known error, accepted (CR172 D7):** BSM is European; US equity options are American. The gap
bites on deep-ITM puts and pre-dividend ITM calls, and nowhere else that matters at our precision.
Documented, shipped; CRR binomial only if a lesson ever needs it.

## Source data
Chain quotes + spot from the market-data provider stack; risk-free rate from `^IRX`
(`settings.risk_free_rate_ticker`, CR172 D8); dividend yield promoted from
`EarningsInfo.dividend_rate` (display-only until CR172).

## Consumed by
`services/option_chain.py::enrich_chain` (slice 1); M15/M16 build on `bs_d1_d2`/`bs_price`;
M17 → the slice-2 `option_strategist` candidate generator.

## Computed in
`app/trading_math/black_scholes.py::bs_price` / `bs_d1_d2` / `put_call_parity_gap`.

## Guard test
`tests/unit/test_cr172_trading_math_options.py` — the textbook S=100/K=100/T=1/r=5%/σ=20% pair
(10.4506 / 5.5735), parity held across a spot×sigma×yield grid, dividend yield moving call down and
put up, and None on every invalid-input class. Mutation-proven (d1 sign flip → red).

## Changelog
- 2026-08-20 (CR172 slice 1, AT:R73): created.
