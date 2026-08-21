"""OCC option symbols — CR172 §1's canonical instrument identity.

The 21-character OCC key: root (6 chars, space-padded) + YYMMDD + C|P +
strike × 1000 (8 digits, zero-padded). `AAPL  260116C00250000` is the AAPL
2026-01-16 $250 call.

An OCC symbol must NEVER be routed through `require_ticker_exists` or the
Sharia ticker regex — both reject it by construction (CR172 §1). The
*underlying* is what passes those gates and what every screen keys on, which
is why `sim_option_legs.underlying` is a real column and this module's parse
result carries it separately rather than leaving callers to slice prefixes.

Pure functions, stdlib-only; no config, no I/O. Malformed input returns
None — a symbol that does not parse is not an instrument, and inventing one
from a near-miss would misprice a position silently.
"""

from __future__ import annotations

import datetime
import math
import re
from typing import NamedTuple

_OCC_RE = re.compile(
    r"^(?P<root>[A-Z]{1,6}) {0,5}"      # root, space-padded to 6
    r"(?P<date>\d{6})"                   # YYMMDD
    r"(?P<right>[CP])"                   # call | put
    r"(?P<strike>\d{8})$"                # strike x 1000, zero-padded
)

_ROOT_RE = re.compile(r"^[A-Z]{1,6}$")

OCC_SYMBOL_LENGTH = 21


class OccSymbol(NamedTuple):
    """A parsed OCC identity. `right` uses M10's "call"/"put" vocabulary."""

    underlying: str
    expiry: datetime.date
    right: str    # "call" | "put"
    strike: float


def format_occ_symbol(
    underlying: str, expiry: datetime.date, right: str, strike: float
) -> str | None:
    """The 21-char OCC symbol, or None when any part cannot be encoded."""
    if not isinstance(underlying, str):
        return None
    root = underlying.strip().upper()
    if not _ROOT_RE.match(root):
        return None
    if not isinstance(expiry, datetime.date) or isinstance(expiry, datetime.datetime):
        return None
    if not (2000 <= expiry.year <= 2099):
        return None
    r = right.strip().lower() if isinstance(right, str) else ""
    if r not in ("call", "put"):
        return None
    if not (isinstance(strike, (int, float)) and math.isfinite(strike) and strike > 0):
        return None
    strike_thousandths = round(strike * 1000)
    if strike_thousandths > 99_999_999:
        return None
    return (
        f"{root:<6}"
        f"{expiry.strftime('%y%m%d')}"
        f"{'C' if r == 'call' else 'P'}"
        f"{strike_thousandths:08d}"
    )


def parse_occ_symbol(symbol: str) -> OccSymbol | None:
    """Parse a 21-char OCC symbol, or None on anything malformed."""
    if not isinstance(symbol, str) or len(symbol) != OCC_SYMBOL_LENGTH:
        return None
    match = _OCC_RE.match(symbol)
    if match is None:
        return None
    raw_date = match.group("date")
    try:
        expiry = datetime.date(
            2000 + int(raw_date[0:2]), int(raw_date[2:4]), int(raw_date[4:6])
        )
    except ValueError:
        return None
    strike = int(match.group("strike")) / 1000.0
    if strike <= 0:
        return None
    return OccSymbol(
        underlying=match.group("root"),
        expiry=expiry,
        right="call" if match.group("right") == "C" else "put",
        strike=strike,
    )
