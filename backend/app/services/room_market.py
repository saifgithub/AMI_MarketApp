"""Market-awareness for the Room's fact sheet and prompts (CR282 lane E).

The Room is built for US equities; a Bursa Malaysia (`.KL`) Room differs in its
currency, its benchmark, its macro datum, and which inputs exist at all. Every
difference lives behind `profile["market"]`, a key that only a MY sheet carries,
so a US sheet is byte-identical to what it was before CR282 — the Room bank's
policy version hashes every agent's derived prompt, and any change to US text
would re-key every banked US Room (`test_cr282_room_us_byte_identical.py`).

What lives here: the market of a sheet, the ringgit rendering of dollar-shaped
figures, and the one place that words "not available for this market" for the
inputs that come from SEC EDGAR (no Bursa equivalent is ingested yet).
"""

from __future__ import annotations

import re
from typing import Any

from app.trading_math.markets import Market, market_for, spec_for

#: The one phrase every dark input uses, so a reader (and a test) can find them all.
NOT_AVAILABLE_FOR_MARKET = (
    "not available for this market (Bursa Malaysia filings are not yet ingested)"
)

_DOLLAR_AMOUNT_RE = re.compile(r"\$(?=\d)")


def market_of_profile(profile: dict[str, Any] | None) -> Market:
    """US unless the sheet says otherwise. Only a MY sheet carries the key."""
    if profile and profile.get("market") == Market.MY.value:
        return Market.MY
    return Market.US


def is_my(profile: dict[str, Any] | None) -> bool:
    return market_of_profile(profile) is Market.MY


def localize_money(text: str, market: Market) -> str:
    """Render the dollar-shaped amounts in `text` in the market's currency.

    A `$` directly before a digit is an amount, whatever the formatter that
    wrote it; a `$` anywhere else (a cashtag in a headline) is left alone. US is
    returned unchanged — the same object, not a copy.
    """
    if market is Market.US:
        return text
    return _DOLLAR_AMOUNT_RE.sub(spec_for(market).currency_symbol, text)


def ticker_market(ticker: str | None) -> Market:
    return market_for(ticker or "")


def na_line(label: str, what: str = "") -> str:
    """One explicit dark-input line, in the sheet's `Label: not available …` shape."""
    extra = f" ({what})" if what else ""
    return (
        f"{label}: {NOT_AVAILABLE_FOR_MARKET}{extra}. Do not supply it from memory."
    )


def my_header_bullet() -> str:
    return (
        "- Market: Bursa Malaysia. Money on this sheet is in ringgit (RM) and the "
        "benchmark is the FBM KLCI. Inputs that come from SEC EDGAR have no Bursa "
        "equivalent ingested yet and are listed below as "
        f"\"{NOT_AVAILABLE_FOR_MARKET}\" — a division of the market, not a data "
        "fault: never supply them from memory, and never cite an SEC form for this issuer."
    )


def my_forward_catalyst_header() -> str:
    return (
        "- Forward catalyst: the Bank Negara Malaysia (BNM) Overnight Policy Rate and "
        "the countdown to the next MPC decision below are REAL, from BNM's published "
        "calendar."
    )


def my_dark_lines(*, news: bool, fundamentals: bool, social: bool) -> list[str]:
    """The SEC-dark inputs a desk with these lanes would otherwise have been shown,
    each named as not available for this market rather than omitted."""
    from app.services.edgar_8k import EXEC_CHANGE_LABEL
    from app.services.edgar_filings_feed import FEED_LABEL as FILINGS_LABEL
    from app.services.edgar_forensics import (
        CLUSTER_BUY_LABEL,
        EIGHT_K_FLAGS_LABEL,
        INSIDER_PLAN_TAG_LABEL,
        INSIDER_RATIO_LABEL,
    )

    out: list[str] = []
    if fundamentals:
        out.append(na_line(
            "Peer comparison", "the same-industry peer basket is built from SEC SIC codes",
        ))
        out.append(na_line(
            "Filed-statement detail",
            "debt maturity ladder, cost of debt, debt split, segment and geographic revenue, "
            "SBC-adjusted free cash flow, ROIC, buyback average price and dividend growth "
            "are read from SEC XBRL filings",
        ))
    if news or fundamentals:
        out.append(na_line(FILINGS_LABEL))
    if news:
        out.append(na_line(EXEC_CHANGE_LABEL))
        out.append(na_line(INSIDER_RATIO_LABEL))
        out.append(na_line(INSIDER_PLAN_TAG_LABEL))
        out.append(na_line(CLUSTER_BUY_LABEL))
        out.append(na_line(EIGHT_K_FLAGS_LABEL))
    if social:
        out.append(na_line("Put/call ratio", "Bursa single-stock options do not exist in this app"))
    return out
