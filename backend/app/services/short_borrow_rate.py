"""CR171 §4 — resolving a stock-borrow rate from inputs we actually observe.

Mechanically the fee is trivial (`mark × quantity × rate / 365`, the same shape
as `games_scoring.trade_fee`). The hard part is `rate`, and the honest answer is
that **no free source publishes a numeric stock-loan rate.** Real borrow spans
roughly 0.25%/yr on liquid large-caps to over 100%/yr on hard-to-borrow squeeze
names — a 400× range. Inventing a per-ticker number inside that range would be
exactly the fabrication CR040 and DEF252 exist to prevent, so this module
derives a **coarse tier** from an observable input and records which layer
answered, rather than producing a precise figure it cannot justify.

Three layers, in the `FallbackProvider` shape `market_data.py` already uses:

  **Layer 1 — Alpaca `easy_to_borrow`.** The best signal available to us: live,
  and binary in exactly the dimension that drives cost. **Blocked on
  credentials** — `grep -iE '^ALPACA'` returns nothing in either the repo's
  `.env` or melehost's, measured 2026-08-11, and `/v2/assets` is 401 without a
  key. It must be a HOUSE key, not the per-user OAuth token we store: pricing a
  global model off one user's session couples it to that session and breaks
  when they disconnect. `alpaca_service._paper_get` already supports
  `auth_mode="apikey"`, so this is a config item, not a code change. Left as a
  named, unreachable branch rather than omitted, so the gap is visible in the
  code that would use it. (Reading an asset attribute is not brokerage
  integration — we route no order and connect to no execution venue, matching
  D-069. Stated so it is not re-litigated.)

  **Layer 2 — yfinance `shortPercentOfFloat`.** Available today. Measured
  2026-08-11: AAPL 1.0%, TSLA 2.0%, GME 13.5% — a 13× spread on exactly the
  axis borrow cost runs along, scarcity of lendable float. Tiered COARSELY and
  never with a formula: AAPL's value comes back as `0.01`, two decimals, so
  anywhere from 0.5% to 1.5%. The input's precision does not justify a precise
  output.

  **Layer 2's known failure, and why Layer 1 matters.** `dateShortInterest`
  measured 27 days stale and updates monthly. For an ordinary name that is
  fine — borrow on liquid stock barely moves. But the case where borrow cost
  *matters*, a name going 5%/yr → 80%/yr in a week, is exactly where a
  month-old figure is not merely stale but **anti-informative**: we would price
  cheapest precisely when reality is most expensive. Recorded here rather than
  discovered later.

  **Layer 3 — a flat default.** `short_borrow_default_rate_annual_pct`.

**Resolve ONCE, at open, and store the answer on the row** with the input and
as-of date that justified it. Do not re-resolve daily: a monthly-updating input
re-read every day manufactures the appearance of a live rate. Same posture as
the stored Sharia (CR075) and classification snapshots, and the same provenance
discipline as CR170's `last_price_source`.

A missing field falls to the next layer **and logs at warning** — never
silently assume cheap.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import logger

#: §4's table. Ordered ascending by threshold; the first row whose upper bound
#: the observation is under wins. Four tiers, not a curve — see the module
#: docstring on why a formula over this input would be false precision.
_SHORT_INTEREST_TIERS: tuple[tuple[float, float], ...] = (
    (2.5, 0.5),    # AAPL, TSLA
    (10.0, 3.0),
    (20.0, 12.0),  # GME
    (float("inf"), 30.0),
)


@dataclass(frozen=True)
class BorrowRate:
    """A resolved rate and the evidence for it.

    `source` names the layer that answered, so *"why was this position charged
    3%?"* is answerable from the DB rather than from this file. `basis` and
    `as_of` carry the observation itself — a rate with no visible input is the
    number nobody can check, which is how the fabricated-figure failure starts.
    """

    rate_pct: float
    source: str
    basis: float | None = None
    as_of: str | None = None


def _tier_for(short_pct_of_float: float) -> float:
    for ceiling, rate in _SHORT_INTEREST_TIERS:
        if short_pct_of_float < ceiling:
            return rate
    return _SHORT_INTEREST_TIERS[-1][1]  # pragma: no cover — inf is total


def resolve_borrow_rate(ticker: str, *, info: dict | None = None) -> BorrowRate:
    """The layered resolve. `info` is the yfinance `.info` dict when the caller
    already holds one; passing it makes this a pure function.

    Never raises. A short that cannot be priced still opens — at the default
    rate, loudly logged — because refusing to open a position over a missing
    optional field would be a worse failure than charging a flat 3%.
    """
    t = ticker.upper().strip()

    # Layer 1 — Alpaca. Unreachable until a house key exists; see the module
    # docstring. Deliberately not stubbed with a plausible-looking value.

    # Layer 2 — short interest.
    if info is None:
        info = _fetch_info(t)
    raw = info.get("shortPercentOfFloat") if info else None
    if isinstance(raw, (int, float)) and raw >= 0:
        # yfinance reports this as a FRACTION (0.01 = 1%), and the §4 table is
        # in percent. Getting this backwards would put every liquid name in the
        # top tier — a 60x overcharge that would look like a working feature.
        pct = float(raw) * 100.0
        return BorrowRate(
            rate_pct=_tier_for(pct),
            source="short_interest",
            basis=round(pct, 4),
            as_of=str(info.get("dateShortInterest") or "") or None,
        )

    # Layer 3 — the flat default.
    logger.warning(
        "short_borrow_rate_defaulted",
        ticker=t,
        rate_pct=settings.short_borrow_default_rate_annual_pct,
        reason="no shortPercentOfFloat and no Alpaca key",
    )
    return BorrowRate(
        rate_pct=float(settings.short_borrow_default_rate_annual_pct),
        source="default",
    )


def _fetch_info(ticker: str) -> dict:
    """One `.info` read, at short-open time only. Never on a portfolio read.

    Same `.` → `-` normalisation as `classification_universe` (DEF108: BF.B was
    silently unscreened for want of it).
    """
    try:
        import yfinance as yf

        return yf.Ticker(ticker.replace(".", "-")).info or {}
    except Exception:
        logger.warning("short_borrow_info_fetch_failed", ticker=ticker)
        return {}


def daily_borrow_fee(*, mark: float, quantity: float, rate_pct: float) -> float:
    """§4's fee. 365, not 252 — borrow accrues on calendar days, including the
    weekend a position is held over, which is one of the few places a simulator
    can teach a real carrying cost honestly."""
    return round(mark * quantity * (rate_pct / 100.0) / 365.0, 2)
