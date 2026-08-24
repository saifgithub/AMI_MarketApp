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
from collections.abc import Sequence
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


# ── CR204 — book-level aggregation ───────────────────────────────────────


class GreekLeg(NamedTuple):
    """One option position, in the units aggregation needs.

    `greeks` are PER SHARE (this module's convention throughout). `contracts`
    is signed — negative for a short leg — and `multiplier` is shares per
    contract, so the contract-level exposure is
    `greek x multiplier x contracts` and the sign falls out of the position
    rather than being applied by the caller.
    """

    occ_symbol: str
    greeks: Greeks | None
    contracts: float
    multiplier: float


class BookGreeks(NamedTuple):
    """A whole book's directional and volatility exposure, or an honest gap.

    `share_equivalent_delta` combines options and equity into ONE number, and
    the unit is deliberately *shares of the underlying*: an option's delta is
    per share, a share's own delta is 1.0, and the two only add after the
    option's is multiplied through `multiplier x contracts`. Anything else is
    adding a per-share figure to a position count.

    `unevaluable` is the point of the type. A delta summed over only the legs
    that HAD greeks is a number that reads as the whole book and is not — the
    CR040 case, on the figure a risk cap would be enforced against. When it is
    non-empty the totals describe a SUBSET and the caller must say so rather
    than compare them to a limit.
    """

    share_equivalent_delta: float
    vega_per_point: float
    unevaluable: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return not self.unevaluable


def aggregate_book_greeks(
    legs: Sequence[GreekLeg] = (), *, equity_shares: float = 0.0,
) -> BookGreeks:
    """Total delta (in share equivalents) and vega across options and equity.

    **Vega is summed, not weighted.** `vega_per_point` is already a dollar
    change per one-point move in implied volatility, so summing gives the
    book's dollar sensitivity to a parallel one-point shift. A weighted
    average would answer a different question (the book's *typical* vega) and
    could not be compared against a dollar cap at all. The parallel-shift
    assumption is a real simplification — vol does not move uniformly across
    strikes and expiries — and it is stated here rather than hidden, because
    the alternative is a per-tenor surface this product does not have.

    Equity contributes 1.0 delta per share and no vega, which is what makes
    the combined number meaningful: a covered call's short delta genuinely
    offsets the shares behind it.
    """
    delta = float(equity_shares)
    vega = 0.0
    unevaluable: list[str] = []

    for leg in legs:
        if leg.greeks is None:
            unevaluable.append(leg.occ_symbol)
            continue
        if not all(math.isfinite(v) for v in (
            leg.greeks.delta, leg.greeks.vega_per_point,
            leg.contracts, leg.multiplier,
        )):
            # A non-finite input is not a measurement either. Silently
            # summing it would make the whole total NaN, which reads as a
            # broken screen rather than as one leg we could not price.
            unevaluable.append(leg.occ_symbol)
            continue
        scale = leg.multiplier * leg.contracts
        delta += leg.greeks.delta * scale
        vega += leg.greeks.vega_per_point * scale

    return BookGreeks(
        share_equivalent_delta=delta,
        vega_per_point=vega,
        unevaluable=tuple(unevaluable),
    )
