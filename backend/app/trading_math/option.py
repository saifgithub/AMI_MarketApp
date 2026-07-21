"""Option payoff & break-even — the expiry arithmetic of a call or put.

CR046 M10, opened for CR054 Wave 1 (BOK Level 9 / M15 "Options & derivatives
literacy"): the payoff-diagram points and break-evens in lessons are computed
here, never authored by hand (CR054 §4.5). All figures are the LONG side,
per share — a short side is the exact negation, which a lesson states rather
than re-derives.

Pure — primitives in, a float (2 dp) or None out. `kind` is "call" or "put"
(case-insensitive); anything else returns None so a template typo can't
silently print a call's numbers for a put.
"""

from __future__ import annotations


def _kind(kind: str) -> str | None:
    if not isinstance(kind, str):
        return None
    normalised = kind.strip().lower()
    return normalised if normalised in ("call", "put") else None


def option_intrinsic_value(
    kind: str, strike: float, underlying: float
) -> float | None:
    """What the option is worth if exercised now, per share (2 dp, floored at 0).

    Call: max(0, underlying - strike). Put: max(0, strike - underlying).
    `underlying` may be 0 (the bankruptcy case a put lesson teaches); a
    negative price or non-positive strike returns None.
    """
    k = _kind(kind)
    if k is None or strike <= 0 or underlying < 0:
        return None
    if k == "call":
        return round(max(0.0, underlying - strike), 2)
    return round(max(0.0, strike - underlying), 2)


def option_payoff(
    kind: str, strike: float, price_at_expiry: float, premium: float
) -> float | None:
    """Long P&L per share at expiry (2 dp): intrinsic value - premium paid.

    Below/at the worthless point this is exactly -premium — the "max loss is
    what you paid" fact every payoff diagram anchors on.
    """
    intrinsic = option_intrinsic_value(kind, strike, price_at_expiry)
    if intrinsic is None or premium < 0:
        return None
    return round(intrinsic - premium, 2)


def option_break_even(kind: str, strike: float, premium: float) -> float | None:
    """Underlying price at expiry where the long position's P&L is zero (2 dp).

    Call: strike + premium. Put: strike - premium — None when the premium
    swallows the whole strike (a put can't break even at or below a zero
    stock price).
    """
    k = _kind(kind)
    if k is None or strike <= 0 or premium < 0:
        return None
    if k == "call":
        return round(strike + premium, 2)
    if premium >= strike:
        return None
    return round(strike - premium, 2)
