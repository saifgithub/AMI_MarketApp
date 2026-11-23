"""CR282 lane C — Bursa Malaysia order rules: board lot, tick grid, price limits, fees.

Pure (no DB, no network, no clock). The MYR book's order path calls these from
`SimEngine.submit/preview`; they exist as one module so the tables below have
exactly one home and one provenance note.

PROVENANCE — read before trusting a number:

  * Tick table: Bursa circular rr2_110411. UNVERIFIED against later amendments
    (bursamalaysia.com blocks automated fetches; confirm by hand before release).
  * Price limits: static +/-30% of the reference price, 30 sen absolute below
    RM1.00 (SC/Bursa 2021 notice, verified from primary text).
  * Fee schedule: brokerage 0.10% min RM8 and clearing 0.03% cap RM1,000 are
    research figures from broker norms — UNVERIFIED against a broker's tariff.
    Stamp duty 0.10% cap RM1,000 is secondary-sourced (remission order to
    12 Jul 2028). Ordinary-share brokerage is treated as SST-exempt [UNVERIFIED].
    These are training-simulator proxies of a Malaysian retail contract note,
    not a statement of what any broker charges.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

from app.trading_math.markets import Market, spec_for

# (inclusive lower bound of band in RM, tick in RM), ascending. A price belongs
# to the last band whose lower bound it meets.
TICK_BANDS: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal("0"), Decimal("0.005")),
    (Decimal("1.00"), Decimal("0.01")),
    (Decimal("10.00"), Decimal("0.02")),
    (Decimal("100.00"), Decimal("0.10")),
)

PRICE_LIMIT_PCT = Decimal("0.30")
PRICE_LIMIT_ABS_BELOW_RM1 = Decimal("0.30")

# Fee schedule per contract, MYR. UNVERIFIED — see module docstring.
FEE_BROKERAGE_BPS = Decimal("10")
FEE_BROKERAGE_MIN = Decimal("8.00")
FEE_CLEARING_BPS = Decimal("3")
FEE_CLEARING_CAP = Decimal("1000.00")
FEE_STAMP_BPS = Decimal("10")
FEE_STAMP_CAP = Decimal("1000.00")

_SEN = Decimal("0.01")


class MarketRuleViolation(ValueError):
    """An order the market's own rules refuse. Carries a machine `code` and a
    user-facing sentence in `str(exc)`. Routes map it to HTTP 422."""

    def __init__(self, code: str, message: str, market: Market = Market.MY) -> None:
        self.code = code
        self.market = market
        super().__init__(message)


def _d(x: float | Decimal | str) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def tick_for(price: float | Decimal) -> Decimal:
    p = _d(price)
    tick = TICK_BANDS[0][1]
    for lower, t in TICK_BANDS:
        if p >= lower:
            tick = t
    return tick


def is_on_tick(price: float | Decimal) -> bool:
    p = _d(price)
    if p <= 0:
        return False
    return (p % tick_for(p)) == 0


def nearest_valid_prices(price: float | Decimal) -> tuple[Decimal, Decimal]:
    """(valid price at or below, valid price at or above). Equal when on-grid."""
    p = _d(price)
    tick = tick_for(p)
    lower = (p / tick).to_integral_value(rounding=ROUND_FLOOR) * tick
    upper = (p / tick).to_integral_value(rounding=ROUND_CEILING) * tick
    if upper > lower:
        for band_lower, _ in TICK_BANDS:
            if lower < band_lower < upper:
                upper = band_lower
                break
    return lower, upper


def _trim(d: Decimal) -> str:
    s = f"{d:.3f}"
    if s.endswith("0"):
        s = s[:-1]
    return s


def check_board_lot(quantity: float, market: Market = Market.MY) -> None:
    lot = spec_for(market).board_lot
    q = _d(quantity)
    if q <= 0 or q % lot != 0:
        raise MarketRuleViolation(
            "board_lot",
            f"{spec_for(market).exchange_label} trades in board lots of {lot} units: "
            f"quantity must be a positive multiple of {lot} (got {quantity:g}).",
            market,
        )


def check_tick(price: float | None, label: str = "price") -> None:
    if price is None:
        return
    if not is_on_tick(price):
        lo, hi = nearest_valid_prices(price)
        near = _trim(lo) if lo == hi else f"{_trim(lo)} or RM{_trim(hi)}"
        raise MarketRuleViolation(
            "tick_size",
            f"{label} RM{_d(price):f} is not on Bursa's tick grid "
            f"(RM{_trim(tick_for(price))} ticks at this price). "
            f"Nearest valid prices: RM{near}.",
        )


def price_limit_band(reference: float | Decimal) -> tuple[Decimal, Decimal]:
    """Static price limits around the reference (previous close)."""
    ref = _d(reference)
    if ref < 1:
        width = PRICE_LIMIT_ABS_BELOW_RM1
    else:
        width = ref * PRICE_LIMIT_PCT
    return max(ref - width, Decimal("0")), ref + width


def check_price_limit(price: float | None, reference: float | None, label: str = "limit price") -> None:
    """Refuse a price outside +/-30% of `reference`. No reference => no check
    (the caller logs that loudly)."""
    if price is None or reference is None or reference <= 0:
        return
    lo, hi = price_limit_band(reference)
    p = _d(price)
    if p < lo or p > hi:
        raise MarketRuleViolation(
            "price_limit",
            f"{label} RM{p:f} is outside Bursa's daily price limits for this stock "
            f"(RM{lo:.3f} to RM{hi:.3f}, from a reference close of RM{_d(reference):.3f}).",
        )


@dataclass(frozen=True)
class BursaFees:
    brokerage: float
    clearing: float
    stamp_duty: float
    total: float

    def to_json(self) -> dict:
        return {
            "brokerage": self.brokerage,
            "clearing": self.clearing,
            "stamp_duty": self.stamp_duty,
            "total": self.total,
            "currency": "MYR",
        }


def _sen(x: Decimal) -> Decimal:
    return x.quantize(_SEN, rounding=ROUND_HALF_UP)


def bursa_fees(notional: float) -> BursaFees:
    n = abs(_d(notional))
    brokerage = _sen(max(n * FEE_BROKERAGE_BPS / 10000, FEE_BROKERAGE_MIN))
    clearing = _sen(min(n * FEE_CLEARING_BPS / 10000, FEE_CLEARING_CAP))
    stamp = _sen(min(n * FEE_STAMP_BPS / 10000, FEE_STAMP_CAP))
    return BursaFees(
        brokerage=float(brokerage),
        clearing=float(clearing),
        stamp_duty=float(stamp),
        total=float(brokerage + clearing + stamp),
    )


def reference_close_from_quote(price: float, change_pct: float) -> float:
    """Previous close implied by a quote's day-change percent. `change_pct` is
    0.0 for an unchanged day and for a degraded quote alike, in which case the
    price itself is the best reference there is."""
    if change_pct and change_pct > -100:
        return price / (1 + change_pct / 100.0)
    return price
