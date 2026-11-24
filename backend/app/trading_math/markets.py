"""CR282 lane A — the market registry: one place that says what each market is.

Everything market-specific (currency, clock, lot size, benchmark, which product
lines exist) hangs off a `Market` here instead of being re-derived from a
ticker's shape at each call site. US is the default for every ticker, so a
caller that never asks about markets behaves exactly as before CR282.

Pure: no DB, no network. Bursa is gated by `MARKET_BURSA_ENABLED` (default off,
off in Beta); `market_enabled` is the single place that reads the flag.

Later lanes fill the holes this module deliberately leaves: calendar/holidays
(lane B), fees and board-lot sizing, the MYR book, the Bursa reference list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings


class Market(str, Enum):
    US = "US"
    MY = "MY"


@dataclass(frozen=True)
class MarketSpec:
    market: Market
    exchange_label: str
    currency: str
    currency_symbol: str
    timezone: str
    yahoo_suffix: str
    board_lot: int
    benchmark_ticker: str
    options_supported: bool
    alpaca_supported: bool
    shorts_supported: bool


MARKETS: dict[Market, MarketSpec] = {
    Market.US: MarketSpec(
        market=Market.US,
        exchange_label="US equities",
        currency="USD",
        currency_symbol="$",
        timezone="America/New_York",
        yahoo_suffix="",
        board_lot=1,
        benchmark_ticker="SPY",
        options_supported=True,
        alpaca_supported=True,
        shorts_supported=True,
    ),
    Market.MY: MarketSpec(
        market=Market.MY,
        exchange_label="Bursa Malaysia",
        currency="MYR",
        currency_symbol="RM",
        timezone="Asia/Kuala_Lumpur",
        yahoo_suffix=".KL",
        board_lot=100,
        benchmark_ticker="^KLSE",
        options_supported=False,
        alpaca_supported=False,
        shorts_supported=False,
    ),
}

# Bursa stock codes are four digits, occasionally with a trailing letter on
# Yahoo (`5099.KL`, `0166.KL`). Shape only — existence is the reference list's job.
_BURSA_CODE_RE = re.compile(r"^[0-9]{4,5}[A-Z]?\.KL$")  # 5 digits: ACE/LEAP codes (e.g. 03068) on the SC list


def spec_for(market: Market) -> MarketSpec:
    return MARKETS[market]


def format_money(amount: float, market: Market = Market.US, *, signed: bool = False) -> str:
    """The house money format, server side (mirrors mobile `formatMoney`).

    Sign before the symbol (`-$8.08`, `+RM11.00`), thousands separators, two
    decimals; an amount that rounds to zero prints unsigned (`$0.00`, or
    `+$0.00` when `signed`) so `-0.0` never reads `+-$0.00` (DEF531).
    """
    body = f"{abs(amount):,.2f}"
    if body == "0.00" or amount > 0:
        sign = "+" if signed else ""
    else:
        sign = "-"
    return f"{sign}{spec_for(market).currency_symbol}{body}"


def market_for(ticker: str) -> Market:
    """`.KL` => Malaysia; everything else (including indices and OCC symbols) => US."""
    t = (ticker or "").upper().strip()
    if t.endswith(MARKETS[Market.MY].yahoo_suffix):
        return Market.MY
    return Market.US


def market_enabled(market: Market) -> bool:
    """US is always on. Every other market sits behind its own flag."""
    if market is Market.US:
        return True
    if market is Market.MY:
        return bool(settings.market_bursa_enabled)
    return False


def ticker_market_enabled(ticker: str) -> bool:
    return market_enabled(market_for(ticker))


def is_bursa_code(ticker: str) -> bool:
    return bool(_BURSA_CODE_RE.match((ticker or "").upper().strip()))


def accepted_without_reference(ticker: str) -> bool:
    """A Bursa code the flag lets through on SHAPE alone.

    There is no Bursa row in `ticker_reference` yet, so with the flag on the
    existence guard would reject every `.KL` code. Until the Bursa ticker list
    lands (later CR282 lane) shape is the only check available; with the flag
    off this is always False and `.KL` is rejected exactly as before.
    """
    return market_enabled(Market.MY) and is_bursa_code(ticker)


def yahoo_symbol(ticker: str) -> str:
    """Our symbol -> Yahoo's. US class shares use a hyphen (BRK.B -> BRK-B);
    an exchange-suffixed symbol (1155.KL) and index symbols (^KLSE) keep their
    dot/caret — the suffix IS Yahoo's venue marker."""
    t = ticker.upper().strip()
    if market_for(t) is not Market.US:
        return t
    return t.replace(".", "-")


class MarketUnsupported(ValueError):
    """A product line (options, Alpaca mirror) that a market does not have."""

    def __init__(self, market: Market, feature: str) -> None:
        self.market = market
        self.feature = feature
        super().__init__(
            f"{feature} is not available for {MARKETS[market].exchange_label}"
        )
