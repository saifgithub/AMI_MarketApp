"""Black-Scholes-Merton option pricing — CR046 M14, opened for CR172 §5.

The pricer behind every option figure an AMI agent presents: yfinance serves
chains with bid/ask/IV but **no greeks and no risk-free rate**, so the model
price, the greeks (M15) and the IV solver (M16) are all computed here — the
LLM never does the sum, and neither does Yahoo.

European exercise, continuous dividend yield (Merton's extension). US equity
options are American; the gap bites on deep-ITM puts and pre-dividend ITM
calls and nowhere else that matters at our precision — CR172 D7 ships BSM
with the error documented rather than putting a binomial tree in the mark
path for a difference smaller than Yahoo's own quote staleness.

Pure — primitives in, floats out, full precision (rounding is the
presentation layer's job, unlike M10's 2-dp lesson figures). Invalid inputs
return None, never a guess: a caller that cannot price must say so
(`not_evaluated`), not render a fabricated number (DEF169).

`put_call_parity_gap` is the module's self-guard: C − P must equal
S·e^(−qT) − K·e^(−rT) for any (S, K, T, r, q), independent of sigma. The
guard tests hold it at ~0; a sign or discounting mistake in either branch
breaks parity before it breaks a human's eyeball check.
"""

from __future__ import annotations

import math
from typing import NamedTuple

_SQRT_2 = math.sqrt(2.0)
_SQRT_2PI = math.sqrt(2.0 * math.pi)


def norm_cdf(x: float) -> float:
    """Standard normal CDF via the stdlib error function."""
    return 0.5 * (1.0 + math.erf(x / _SQRT_2))


def norm_pdf(x: float) -> float:
    """Standard normal density."""
    return math.exp(-0.5 * x * x) / _SQRT_2PI


def _kind(kind: str) -> str | None:
    """Same normalisation contract as M10's `option.py`."""
    if not isinstance(kind, str):
        return None
    normalised = kind.strip().lower()
    return normalised if normalised in ("call", "put") else None


def _inputs_valid(
    spot: float, strike: float, t_years: float, rate: float, sigma: float,
    dividend_yield: float,
) -> bool:
    values = (spot, strike, t_years, rate, sigma, dividend_yield)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        return False
    # T must be strictly positive: at expiry the price IS the intrinsic value
    # and M10's `option_intrinsic_value` already owns that arithmetic — a
    # pricer that silently switched formulas at T=0 would hide which one a
    # figure came from. Sigma must be strictly positive for the same reason:
    # sigma=0 is a deterministic forward, not a priced option.
    return (
        spot > 0 and strike > 0 and t_years > 0 and sigma > 0
        and dividend_yield >= 0 and rate > -1.0
    )


class D1D2(NamedTuple):
    """The two BSM quantiles, computed once and shared by price and greeks."""

    d1: float
    d2: float


def bs_d1_d2(
    spot: float, strike: float, t_years: float, rate: float, sigma: float,
    dividend_yield: float = 0.0,
) -> D1D2 | None:
    """d1/d2 with continuous dividend yield, or None on invalid inputs."""
    if not _inputs_valid(spot, strike, t_years, rate, sigma, dividend_yield):
        return None
    vol_sqrt_t = sigma * math.sqrt(t_years)
    d1 = (
        math.log(spot / strike)
        + (rate - dividend_yield + 0.5 * sigma * sigma) * t_years
    ) / vol_sqrt_t
    return D1D2(d1=d1, d2=d1 - vol_sqrt_t)


def bs_price(
    kind: str, spot: float, strike: float, t_years: float, rate: float,
    sigma: float, dividend_yield: float = 0.0,
) -> float | None:
    """BSM price per share, full precision, or None on invalid inputs."""
    k = _kind(kind)
    d = bs_d1_d2(spot, strike, t_years, rate, sigma, dividend_yield)
    if k is None or d is None:
        return None
    disc_spot = spot * math.exp(-dividend_yield * t_years)
    disc_strike = strike * math.exp(-rate * t_years)
    if k == "call":
        return disc_spot * norm_cdf(d.d1) - disc_strike * norm_cdf(d.d2)
    return disc_strike * norm_cdf(-d.d2) - disc_spot * norm_cdf(-d.d1)


def put_call_parity_gap(
    call_price: float, put_price: float, spot: float, strike: float,
    t_years: float, rate: float, dividend_yield: float = 0.0,
) -> float | None:
    """(C − P) − (S·e^(−qT) − K·e^(−rT)) — zero when parity holds.

    The self-guard the M14 tests pin: parity is sigma-free, so it catches a
    discounting or sign error in `bs_price` without trusting any reference
    number the same code produced.
    """
    values = (call_price, put_price, spot, strike, t_years, rate, dividend_yield)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        return None
    if spot <= 0 or strike <= 0 or t_years <= 0:
        return None
    forward_gap = (
        spot * math.exp(-dividend_yield * t_years)
        - strike * math.exp(-rate * t_years)
    )
    return (call_price - put_price) - forward_gap
