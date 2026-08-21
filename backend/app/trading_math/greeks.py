"""BSM greeks — CR046 M15, opened for CR172 §5.

Delta, gamma, theta, vega, rho per SHARE; `per_contract` scales by the
contract multiplier (a parameter, never a hard-coded 100 — adjusted
contracts exist, CR172 §3).

Conventions, stated because each has a rival that silently changes the
number:

* **Theta is per CALENDAR day** (annual theta / 365). The per-trading-day
  convention (/252) differs by ~30% and both are in common use; a mark that
  decays 7 days a week is what the weekend NAV tick needs (CR172 §7).
* **Vega is per 1 volatility POINT** (IV 20% → 21%), i.e. dPrice/dSigma / 100.
* **Rho is per 1 rate POINT** (r 5% → 6%), same /100 scaling.
* Delta and gamma are unscaled (per $1 of underlying).

Pure, stdlib-only, full precision. Invalid inputs return None — a greek that
cannot be computed is `not_evaluated`, never 0.0, because 0.0 is a confident
claim of no exposure at all (DEF169).
"""

from __future__ import annotations

import math
from typing import NamedTuple

from .black_scholes import _kind, bs_d1_d2, norm_cdf, norm_pdf

CALENDAR_DAYS_PER_YEAR = 365.0


class Greeks(NamedTuple):
    """Per-share greeks under the module conventions above."""

    delta: float
    gamma: float
    theta_per_day: float
    vega_per_point: float
    rho_per_point: float


def bs_greeks(
    kind: str, spot: float, strike: float, t_years: float, rate: float,
    sigma: float, dividend_yield: float = 0.0,
) -> Greeks | None:
    """All five greeks per share, or None on invalid inputs."""
    k = _kind(kind)
    d = bs_d1_d2(spot, strike, t_years, rate, sigma, dividend_yield)
    if k is None or d is None:
        return None
    sqrt_t = math.sqrt(t_years)
    disc_q = math.exp(-dividend_yield * t_years)
    disc_r = math.exp(-rate * t_years)
    pdf_d1 = norm_pdf(d.d1)

    gamma = disc_q * pdf_d1 / (spot * sigma * sqrt_t)
    vega_annual = spot * disc_q * pdf_d1 * sqrt_t
    # The sigma-decay term is common to both rights; the carry terms differ.
    theta_decay = -spot * disc_q * pdf_d1 * sigma / (2.0 * sqrt_t)

    if k == "call":
        delta = disc_q * norm_cdf(d.d1)
        theta_annual = (
            theta_decay
            - rate * strike * disc_r * norm_cdf(d.d2)
            + dividend_yield * spot * disc_q * norm_cdf(d.d1)
        )
        rho_annual = strike * t_years * disc_r * norm_cdf(d.d2)
    else:
        delta = disc_q * (norm_cdf(d.d1) - 1.0)
        theta_annual = (
            theta_decay
            + rate * strike * disc_r * norm_cdf(-d.d2)
            - dividend_yield * spot * disc_q * norm_cdf(-d.d1)
        )
        rho_annual = -strike * t_years * disc_r * norm_cdf(-d.d2)

    return Greeks(
        delta=delta,
        gamma=gamma,
        theta_per_day=theta_annual / CALENDAR_DAYS_PER_YEAR,
        vega_per_point=vega_annual / 100.0,
        rho_per_point=rho_annual / 100.0,
    )


def per_contract(greeks: Greeks, multiplier: float = 100.0) -> Greeks | None:
    """Scale per-share greeks to one contract of `multiplier` shares."""
    if not (isinstance(multiplier, (int, float)) and math.isfinite(multiplier)
            and multiplier > 0):
        return None
    return Greeks(*(g * multiplier for g in greeks))
