"""Implied volatility solver — CR046 M16, opened for CR172 §5.

Inverts M14's `bs_price` for sigma: Newton-Raphson on the analytic vega,
falling back to bisection when Newton stalls (tiny vega deep ITM/OTM, or a
step that leaves the bracket). Yahoo's own IV column is of unknown
provenance and occasionally absurd (CR172 §2), so this is the check — and
the substitute — for every strike where it matters.

**Non-convergence is an explicit None, never the last iterate.** A sigma the
solver could not pin down is not a volatility measurement, and handing back
the closest guess would be a fabricated figure with extra steps (DEF169).
None also comes back for a price outside the no-arbitrage band — such a
quote cannot imply any volatility, which on an illiquid chain is a real
answer about the quote, not a solver failure.

Pure, stdlib-only, deterministic.
"""

from __future__ import annotations

import math

from .black_scholes import _kind, bs_price
from .greeks import bs_greeks

SIGMA_LO = 1e-4
SIGMA_HI = 5.0
_TOL = 1e-6
_MAX_ITER = 60


def _no_arb_bounds(
    kind: str, spot: float, strike: float, t_years: float, rate: float,
    dividend_yield: float,
) -> tuple[float, float]:
    """(lower, upper) price bounds outside which no sigma can exist."""
    disc_spot = spot * math.exp(-dividend_yield * t_years)
    disc_strike = strike * math.exp(-rate * t_years)
    if kind == "call":
        return max(0.0, disc_spot - disc_strike), disc_spot
    return max(0.0, disc_strike - disc_spot), disc_strike


def implied_vol(
    kind: str, price: float, spot: float, strike: float, t_years: float,
    rate: float, dividend_yield: float = 0.0,
) -> float | None:
    """The sigma at which `bs_price` equals `price`, or None.

    None means: invalid inputs, a price outside the no-arbitrage band, a
    price unreachable inside [SIGMA_LO, SIGMA_HI], or non-convergence.
    """
    k = _kind(kind)
    if k is None:
        return None
    if not (isinstance(price, (int, float)) and math.isfinite(price) and price > 0):
        return None
    # Probe validity of the remaining inputs through the pricer itself.
    if bs_price(k, spot, strike, t_years, rate, 0.3, dividend_yield) is None:
        return None

    lo_bound, hi_bound = _no_arb_bounds(k, spot, strike, t_years, rate, dividend_yield)
    if not (lo_bound < price < hi_bound):
        return None

    def f(sigma: float) -> float:
        return bs_price(k, spot, strike, t_years, rate, sigma, dividend_yield) - price

    f_lo, f_hi = f(SIGMA_LO), f(SIGMA_HI)
    if f_lo > 0.0 or f_hi < 0.0:
        # Monotone in sigma: no root inside the sigma window.
        return None

    lo, hi = SIGMA_LO, SIGMA_HI
    sigma = 0.3  # standard warm start; Newton converges in a handful of steps
    for _ in range(_MAX_ITER):
        diff = f(sigma)
        if abs(diff) < _TOL:
            return sigma
        # Maintain the bracket around the root for the fallback.
        if diff < 0.0:
            lo = sigma
        else:
            hi = sigma
        g = bs_greeks(k, spot, strike, t_years, rate, sigma, dividend_yield)
        vega = g.vega_per_point * 100.0 if g is not None else 0.0
        if vega > 1e-10:
            step = sigma - diff / vega
        else:
            step = lo  # force the bisection branch below
        # Newton stepping outside the live bracket means it is diverging —
        # bisect instead of following it.
        sigma = step if lo < step < hi else (lo + hi) * 0.5
    return None
