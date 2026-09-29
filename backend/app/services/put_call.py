"""CR247 Phase 1B — the put/call ratio for the Flow & Positioning lane.

The lane (Social Media Analyst) reads retail sentiment off Reddit and has
never had a POSITIONING figure: what the options market is actually doing
with contracts, as opposed to what posters say. The nearest four listed
expiries' chains are already fetchable through the provider stack
(`market_data.MarketDataProvider.option_chain`, CR172); this module
aggregates them into the two ratios the desk reaches for — put volume over
call volume, and put open interest over call open interest — both computed
in code, never by the model (CR179 Leg 4), with the expiry window and the
contract counts stated on the line so the sample is visible.

Volume and open interest are summed only over strikes where the provider
served the field (`OptionQuote` carries None, never a zero, for an unserved
field — CR172 §4). A ratio is withheld, not zeroed, when its side of the
chain served nothing or when the call leg sums to zero (a division by zero
is an infinite ratio, not a large one). The whole figure is unavailable —
None, loudly — when the provider serves no expiries, when any chain in the
stated window fails, or when a chain arrives from a synthetic source: a
mock-walk "chain" would be a positioning signal about a market that does not
exist (the DEF169 shape, refused upstream by `option_chain.py` for greeks
and refused here for aggregates).

The fetch is live-only. There is no historical options store
(`AsOfStoreProvider` declines chains by design), so an as-of profile build
marks the field unavailable with that reason rather than reading today's
chain into a past-dated sheet (the DEF334 lesson).
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.logging import logger
from app.services.market_data import (
    SYNTHETIC_HISTORY_SOURCES,
    OptionChain,
    get_market_data_provider,
)

# The nearest four listed expiries. Four weeklies is about a month of the
# board, four monthlies about a quarter — the window is stated on the line
# either way, so the reader never has to guess which market this aggregates.
_EXPIRIES_SAMPLED = 4


@dataclass(frozen=True)
class PutCallRatio:
    """The two ratios and every figure they were summed from."""

    volume_ratio: float | None
    oi_ratio: float | None
    put_volume: int | None
    call_volume: int | None
    put_open_interest: int | None
    call_open_interest: int | None
    contracts: int
    expiries: int
    expiry_first: datetime.date
    expiry_last: datetime.date
    chain_date: datetime.date


def _sum_served(chains: Sequence[OptionChain], side: str, field: str) -> int | None:
    """Sum one field over one side of every chain; None if it was never served.

    None-as-zero would be wrong here: an unserved field summed as zero renders
    "0 puts traded" — a confident claim of no activity where the truth is "the
    provider did not say". A field served for NO strike is absent, not zero.
    """
    total = 0
    served = 0
    for chain in chains:
        quotes = chain.calls if side == "call" else chain.puts
        for q in quotes:
            value = getattr(q, field)
            if value is not None:
                total += int(value)
                served += 1
    return total if served else None


def aggregate_chains(
    chains: Sequence[OptionChain], chain_date: datetime.date
) -> PutCallRatio | None:
    """Aggregate already-fetched chains. Pure — the math is testable offline."""
    if not chains:
        return None
    put_volume = _sum_served(chains, "put", "volume")
    call_volume = _sum_served(chains, "call", "volume")
    put_oi = _sum_served(chains, "put", "open_interest")
    call_oi = _sum_served(chains, "call", "open_interest")
    volume_ratio = (
        round(put_volume / call_volume, 2)
        if put_volume is not None and call_volume
        else None
    )
    oi_ratio = (
        round(put_oi / call_oi, 2)
        if put_oi is not None and call_oi
        else None
    )
    if volume_ratio is None and oi_ratio is None:
        return None
    return PutCallRatio(
        volume_ratio=volume_ratio,
        oi_ratio=oi_ratio,
        put_volume=put_volume,
        call_volume=call_volume,
        put_open_interest=put_oi,
        call_open_interest=call_oi,
        contracts=sum(len(c.calls) + len(c.puts) for c in chains),
        expiries=len(chains),
        expiry_first=chains[0].expiry,
        expiry_last=chains[-1].expiry,
        chain_date=chain_date,
    )


def fetch_put_call_ratio(ticker: str) -> PutCallRatio | None:
    """The put/call ratios over the nearest expiries, or None — loudly."""
    t = ticker.upper().strip()
    provider = get_market_data_provider()
    today = datetime.datetime.now(datetime.UTC).date()
    try:
        listed = provider.expiries(t)
    except Exception as exc:
        logger.warn("put_call_expiries_error", ticker=t, error=f"{type(exc).__name__}: {exc}")
        return None
    if not listed:
        logger.warn("put_call_no_expiries", ticker=t)
        return None
    chosen = [d for d in sorted(listed) if d >= today][:_EXPIRIES_SAMPLED]
    if not chosen:
        logger.warn("put_call_no_future_expiries", ticker=t, today=today.isoformat())
        return None
    chains: list[OptionChain] = []
    for expiry in chosen:
        try:
            chain = provider.option_chain(t, expiry)
        except Exception as exc:
            logger.warn(
                "put_call_chain_error", ticker=t, expiry=expiry.isoformat(),
                error=f"{type(exc).__name__}: {exc}",
            )
            return None
        if chain is None:
            logger.warn("put_call_chain_unavailable", ticker=t, expiry=expiry.isoformat())
            return None
        if chain.source in SYNTHETIC_HISTORY_SOURCES:
            logger.warn(
                "put_call_synthetic_chain_refused", ticker=t,
                expiry=expiry.isoformat(), source=chain.source,
            )
            return None
        chains.append(chain)
    return aggregate_chains(chains, today)


def put_call_line(ratio: PutCallRatio | None, *, live: bool = True) -> str | None:
    """The one computed line. Ratios the provider could not support are
    stated as not served rather than dropped silently — a volume ratio missing
    beside an open-interest ratio present is a fact about the feed."""
    if ratio is None:
        return None
    marker = " (AMI's own quotient, LIVE)" if live else " (AMI's own quotient)"
    parts: list[str] = []
    if ratio.volume_ratio is not None:
        parts.append(
            f"volume {ratio.volume_ratio:.2f} "
            f"({ratio.put_volume:,} puts / {ratio.call_volume:,} calls)"
        )
    else:
        parts.append("volume not served by the provider")
    if ratio.oi_ratio is not None:
        parts.append(
            f"open interest {ratio.oi_ratio:.2f} "
            f"({ratio.put_open_interest:,} puts / {ratio.call_open_interest:,} calls)"
        )
    else:
        parts.append("open interest not served by the provider")
    window = (
        f"{ratio.expiries} expiries {ratio.expiry_first.isoformat()} to "
        f"{ratio.expiry_last.isoformat()}, {ratio.contracts:,} contracts, "
        f"chain as of {ratio.chain_date.isoformat()}"
    )
    return f"Put/call ratio{marker}: " + ", ".join(parts) + f" — {window}"
