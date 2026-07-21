"""Bond math — price, yield to maturity, and duration of a level-coupon bond.

CR046 M09, opened for CR054 Wave 1 (BOK Level 9 / M13 "Fixed income & rates"):
every bond worked example in a lesson routes through these instead of being
authored by hand, so a lesson can't ship a wrong price/yield/duration
(CR054 §4.5 — numbers computed, never authored). Standard discrete-compounding
textbook math over a level-coupon cash-flow schedule.

Conventions: rates are annual percents (5 → 5%), paid/compounded
`payments_per_year` times a year; `years × payments_per_year` must land on a
whole number of periods — anything else returns None (refusing beats silently
mis-discounting a fractional period). Price and durations round at the
presented-figure boundary (2 dp); YTM keeps 3 dp so basis points survive.

Pure — floats in, a float or None out.
"""

from __future__ import annotations


def _periods(years: float, payments_per_year: int) -> int | None:
    """Whole number of coupon periods, or None when the schedule is unusable."""
    if years <= 0 or payments_per_year <= 0:
        return None
    n = years * payments_per_year
    if abs(n - round(n)) > 1e-9 or round(n) < 1:
        return None
    return int(round(n))


def _pv(face: float, coupon: float, y: float, n: int) -> float:
    """Present value of `n` level coupons + face at per-period yield `y`."""
    if y == 0:
        return coupon * n + face
    discount = (1 + y) ** -n
    return coupon * (1 - discount) / y + face * discount


def bond_price(
    face: float,
    coupon_rate_pct: float,
    ytm_pct: float,
    years: float,
    payments_per_year: int = 2,
) -> float | None:
    """Price of a level-coupon bond: PV of coupons + face at the YTM, 2 dp.

    Returns None for an unusable schedule (see `_periods`), a non-positive
    face, a negative coupon rate, or a yield at/below -100% annualised.
    """
    n = _periods(years, payments_per_year)
    if n is None or face <= 0 or coupon_rate_pct < 0:
        return None
    y = ytm_pct / 100 / payments_per_year
    if y <= -1:
        return None
    coupon = face * coupon_rate_pct / 100 / payments_per_year
    return round(_pv(face, coupon, y, n), 2)


def bond_ytm(
    price: float,
    face: float,
    coupon_rate_pct: float,
    years: float,
    payments_per_year: int = 2,
) -> float | None:
    """Yield to maturity (annual percent, 3 dp) implied by a bond's price.

    Solved by bisection — price is strictly decreasing in yield, so the root is
    unique. Returns None when the price is unattainable inside the searched
    yield band (-90% to +1000% annualised) or any input is unusable.
    """
    n = _periods(years, payments_per_year)
    if n is None or price <= 0 or face <= 0 or coupon_rate_pct < 0:
        return None
    m = payments_per_year
    coupon = face * coupon_rate_pct / 100 / m

    def price_at(ytm_pct: float) -> float:
        return _pv(face, coupon, ytm_pct / 100 / m, n)

    lo, hi = -90.0, 1000.0
    if not (price_at(hi) <= price <= price_at(lo)):
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if price_at(mid) > price:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 3)


def _macaulay(
    face: float,
    coupon_rate_pct: float,
    ytm_pct: float,
    years: float,
    payments_per_year: int,
) -> float | None:
    """Unrounded Macaulay duration in years — shared by both public durations."""
    n = _periods(years, payments_per_year)
    if n is None or face <= 0 or coupon_rate_pct < 0:
        return None
    m = payments_per_year
    y = ytm_pct / 100 / m
    if y <= -1:
        return None
    coupon = face * coupon_rate_pct / 100 / m
    price = _pv(face, coupon, y, n)
    if price <= 0:
        return None
    weighted = 0.0
    for i in range(1, n + 1):
        cash_flow = coupon + (face if i == n else 0.0)
        weighted += (i / m) * cash_flow * (1 + y) ** -i
    return weighted / price


def macaulay_duration(
    face: float,
    coupon_rate_pct: float,
    ytm_pct: float,
    years: float,
    payments_per_year: int = 2,
) -> float | None:
    """PV-weighted average time (years, 2 dp) to a bond's cash flows.

    A zero-coupon bond's duration is exactly its maturity — the classic
    teaching anchor.
    """
    mac = _macaulay(face, coupon_rate_pct, ytm_pct, years, payments_per_year)
    return None if mac is None else round(mac, 2)


def modified_duration(
    face: float,
    coupon_rate_pct: float,
    ytm_pct: float,
    years: float,
    payments_per_year: int = 2,
) -> float | None:
    """Price sensitivity to yield (years, 2 dp): Macaulay / (1 + y/m).

    The "a 1-pt rate rise moves the price about -D%" number a rates lesson
    presents.
    """
    mac = _macaulay(face, coupon_rate_pct, ytm_pct, years, payments_per_year)
    if mac is None:
        return None
    return round(mac / (1 + ytm_pct / 100 / payments_per_year), 2)
