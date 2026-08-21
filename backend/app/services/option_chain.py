"""Option-chain enrichment — CR172 slice 1's deterministic pricing pipeline.

yfinance serves a chain with bid/ask/IV but **no greeks and no risk-free
rate** (CR172 §2). This module closes that gap without ever letting a model
near the arithmetic: every figure it adds is a `trading_math` call (M14–M16),
so a greek on any downstream surface is traceable to a deterministic
function, never to the LLM and never to Yahoo's unexplained columns.

Per strike it computes: the CR170-extended three-state fillability verdict
(`classify_option_quote`), the mid, the IV actually used — the provider's
own figure when it is sane, else solved from the mid via M16, else declared
absent — and the M15 greeks. A strike that cannot be priced carries an
explicit `greeks_reason`, never a zero: 0.0 delta is a confident claim of no
exposure (DEF169).

The risk-free rate is quoted from `settings.risk_free_rate_ticker` (`^IRX`,
the 13-week T-bill yield — CR172 D8) through the ordinary provider stack. A
synthetic source is REFUSED: the mock walk prices `^IRX` like a $300 stock,
and 300% would flow into every greek while looking like a number. Same for a
synthetic spot under a real chain. Both refusals log loudly (CR040).

`enrich_chain` is pure given its inputs (chain, spot, rate, yield, clock) —
that is what makes the math unit-testable without a network. The
`get_enriched_chain` wrapper does the fetching. Sync, deliberately, like the
rest of `market_data` — route handlers wrap calls in `asyncio.to_thread`.
"""

from __future__ import annotations

import datetime
from typing import NamedTuple

from app.core.config import settings
from app.core.logging import logger
from app.services.market_data import (
    SYNTHETIC_HISTORY_SOURCES,
    OptionChain,
    OptionQuote,
    classify_option_quote,
    get_market_data_provider,
)
from app.trading_math import Greeks, bs_greeks, implied_vol

# Sanity band for a provider-served IV (CR172 §2: "provenance unknown,
# occasionally absurd"). Outside it we solve our own from the mid instead.
IV_SANE_LO = 0.005
IV_SANE_HI = 5.0

# A 13-week T-bill outside [0%, 25%] is not a plausible reading of `^IRX`;
# refuse it rather than price every option off a corrupt quote.
RISK_FREE_RATE_MAX = 0.25

# US equity options settle at 16:00 ET; 21:00 UTC covers EDT (20:00) with a
# one-hour margin the pricing cannot feel at our precision.
_EXPIRY_CUTOFF_UTC = datetime.time(21, 0)
_SECONDS_PER_YEAR = 365.0 * 86400.0


class RiskFreeRate(NamedTuple):
    """A usable annualised rate (decimal fraction) plus its leaf source."""

    rate: float
    source: str


def get_risk_free_rate() -> RiskFreeRate | None:
    """The `^IRX` yield as a decimal fraction, or None — never a guess.

    None when the quote is missing, synthetic, or outside the sanity band.
    The caller renders greeks as `not_evaluated`; it never substitutes a
    made-up constant (CR040).
    """
    ticker = settings.risk_free_rate_ticker
    quote = get_market_data_provider().quote(ticker)
    if quote is None:
        logger.warn("risk_free_rate_unavailable", ticker=ticker)
        return None
    if quote.source in SYNTHETIC_HISTORY_SOURCES:
        logger.warn(
            "risk_free_rate_synthetic_refused",
            ticker=ticker, source=quote.source,
        )
        return None
    rate = quote.price / 100.0
    if not (0.0 <= rate <= RISK_FREE_RATE_MAX):
        logger.warn(
            "risk_free_rate_implausible", ticker=ticker, price=quote.price,
        )
        return None
    return RiskFreeRate(rate=rate, source=quote.source)


class EnrichedOptionQuote(NamedTuple):
    """One strike with its computed figures and their provenance."""

    quote: OptionQuote
    right: str                 # "call" | "put"
    mid: float | None
    state: str                 # tradeable | worthless | unusable
    state_reason: str
    iv_used: float | None
    iv_source: str | None      # "provider" | "solved" | None
    greeks: Greeks | None      # per SHARE (M15 conventions)
    greeks_reason: str | None  # set exactly when greeks is None


class EnrichedChain(NamedTuple):
    """A chain plus every deterministic figure slice 1 can attach to it."""

    chain: OptionChain
    spot: float
    spot_source: str
    rate: float | None         # None ⇒ every greek is not_evaluated
    rate_source: str | None
    dividend_yield: float
    t_years: float
    calls: tuple[EnrichedOptionQuote, ...]
    puts: tuple[EnrichedOptionQuote, ...]


def year_fraction_to_expiry(
    expiry: datetime.date, now: datetime.datetime
) -> float:
    """Years from `now` to the expiry settlement cutoff; 0.0 when past."""
    cutoff = datetime.datetime.combine(
        expiry, _EXPIRY_CUTOFF_UTC, tzinfo=datetime.timezone.utc,
    )
    return max(0.0, (cutoff - now).total_seconds() / _SECONDS_PER_YEAR)


def _enrich_quote(
    quote: OptionQuote, right: str, spot: float, rate: float | None,
    dividend_yield: float, t_years: float,
) -> EnrichedOptionQuote:
    state, reason = classify_option_quote(quote.bid, quote.ask)
    mid: float | None = None
    if quote.bid is not None and quote.ask is not None and state != "unusable":
        mid = (quote.bid + quote.ask) / 2.0

    iv_used: float | None = None
    iv_source: str | None = None
    greeks: Greeks | None = None
    greeks_reason: str | None = None

    if t_years <= 0.0:
        greeks_reason = "expired"
    elif rate is None:
        greeks_reason = "no_risk_free_rate"
    else:
        provider_iv = quote.implied_vol
        if provider_iv is not None and IV_SANE_LO <= provider_iv <= IV_SANE_HI:
            iv_used, iv_source = provider_iv, "provider"
        elif state == "tradeable" and mid is not None and mid > 0:
            solved = implied_vol(
                right, mid, spot, quote.strike, t_years, rate, dividend_yield,
            )
            if solved is not None:
                iv_used, iv_source = solved, "solved"
        if iv_used is None:
            greeks_reason = "no_usable_iv"
        else:
            greeks = bs_greeks(
                right, spot, quote.strike, t_years, rate, iv_used,
                dividend_yield,
            )
            if greeks is None:
                greeks_reason = "greeks_inputs_invalid"

    return EnrichedOptionQuote(
        quote=quote, right=right, mid=mid, state=state, state_reason=reason,
        iv_used=iv_used, iv_source=iv_source, greeks=greeks,
        greeks_reason=greeks_reason,
    )


def enrich_chain(
    chain: OptionChain, spot: float, rate: float | None,
    rate_source: str | None = None, dividend_yield: float = 0.0,
    now: datetime.datetime | None = None, spot_source: str = "",
) -> EnrichedChain | None:
    """Attach fillability, IV-used and greeks to every strike. Pure.

    `rate=None` is honoured, not repaired: every strike then carries
    `greeks_reason="no_risk_free_rate"` while bid/ask/fillability still
    serve — the chain degrades visibly instead of vanishing.
    """
    if spot <= 0:
        return None
    now = now or datetime.datetime.now(datetime.timezone.utc)
    t_years = year_fraction_to_expiry(chain.expiry, now)
    return EnrichedChain(
        chain=chain,
        spot=spot,
        spot_source=spot_source,
        rate=rate,
        rate_source=rate_source,
        dividend_yield=dividend_yield,
        t_years=t_years,
        calls=tuple(
            _enrich_quote(q, "call", spot, rate, dividend_yield, t_years)
            for q in chain.calls
        ),
        puts=tuple(
            _enrich_quote(q, "put", spot, rate, dividend_yield, t_years)
            for q in chain.puts
        ),
    )


def get_enriched_chain(
    underlying: str, expiry: datetime.date
) -> EnrichedChain | None:
    """Fetch + enrich one (underlying, expiry) chain, or None — loudly.

    None when the provider serves no chain (mock provider, outage, bad
    expiry) or no honest spot. A real chain priced against a synthetic spot
    is refused outright: the greeks would be fabrications wearing real
    strikes.
    """
    t = underlying.upper().strip()
    provider = get_market_data_provider()
    chain = provider.option_chain(t, expiry)
    if chain is None:
        logger.warn(
            "option_chain_unavailable", underlying=t, expiry=expiry.isoformat(),
        )
        return None
    spot_quote = provider.quote(t)
    if spot_quote is None or spot_quote.price <= 0:
        logger.warn("option_chain_no_spot", underlying=t)
        return None
    if spot_quote.source in SYNTHETIC_HISTORY_SOURCES:
        logger.warn(
            "option_chain_synthetic_spot_refused",
            underlying=t, source=spot_quote.source,
        )
        return None

    risk_free = get_risk_free_rate()

    dividend_yield = 0.0
    earnings = provider.earnings(t)
    if earnings is not None and earnings.dividend_rate:
        # CR172 §2 — `dividend_rate` promoted from display-only to a pricer
        # input: annual per-share USD over spot = continuous-yield proxy.
        dividend_yield = earnings.dividend_rate / spot_quote.price

    return enrich_chain(
        chain,
        spot=spot_quote.price,
        rate=risk_free.rate if risk_free else None,
        rate_source=risk_free.source if risk_free else None,
        dividend_yield=dividend_yield,
        spot_source=spot_quote.source,
    )


def pick_expiry(
    ticker: str, horizon_days: int, requested: datetime.date | None
) -> datetime.date | None:
    """The listed expiry to structure against.

    Lives here rather than beside either caller: the Room (`room_runner`) and
    the `/propose` route must structure against the SAME expiry for the same
    horizon, or the menu the CIO chose from is priced on a different board than
    the one the ticket opens against.

    Requested wins when it is genuinely listed — a requested expiry that is
    not listed is refused rather than snapped to a neighbour, because a
    structure priced on a different expiry than the one asked for is a
    different trade. Otherwise: the first expiry at or beyond the horizon, and
    if the board ends before the horizon, the last one it lists.
    """
    provider = get_market_data_provider()
    listed = provider.expiries(ticker)
    if not listed:
        return None
    if requested is not None:
        return requested if requested in listed else None
    horizon = datetime.date.today() + datetime.timedelta(days=horizon_days)
    beyond = [d for d in sorted(listed) if d >= horizon]
    return beyond[0] if beyond else sorted(listed)[-1]
