"""CR247 Phase 1B — stock-based compensation, trailing four quarters, as filed.

The Fundamentals lane's FCF figures (the bridge, the history, the yield) all
count SBC as a cost only through net income, never against the cash-flow
lines: OCF adds SBC back as a non-cash item, so the sheet's `free_cash_flow`
is gross of the compensation the company pays in shares. The SBC-adjusted
figure — TTM FCF minus TTM SBC — is the read an analyst actually wants, and
handing the model two numbers plus an instruction to subtract is the failure
class CR179 Leg 4 closed (four recurrences of LLM arithmetic on sheet
figures). The subtraction is computed in code and rendered as one labelled
line.

Source is the EDGAR fact store, not yfinance: `ShareBasedCompensation`
(verified live against AAPL's companyconcept endpoint 2026-09-29 — 180 USD
duration rows, cumulative year-to-date per fiscal year, which is exactly the
shape `edgar_pit.quarterly_series` differences into discrete quarters). The
tag needs one `scripts/ingest_edgar_facts.py --force` run before the store
carries it; until then the overlay's loud-degrade warn fires.

Like `interest_cost`, this module reads no feature flag — the flag gates the
RENDER (`room_prompts`), so CR221 §7's control arm stays a flag flip against
one cached profile. None means no readable figure; the render then says not
available, never zero.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.core.logging import logger
from app.services import edgar_pit, edgar_tags


@dataclass(frozen=True)
class SbcTtm:
    """Trailing-four-quarter SBC in dollars, with the window it sums."""

    ttm: float
    period_start: date
    period_end: date


def resolve_sbc_ttm(
    facts: Sequence[edgar_pit._FactView], as_of: date
) -> SbcTtm | None:
    """TTM SBC as of `as_of`, or None when no honest window resolves.

    The sum comes from `edgar_pit.ttm`, so the staleness bound, the
    four-quarter floor and the 430-day span cap are that function's own — the
    window dates are re-derived from the same eligible slice purely so the
    render can name them. A negative total is a data pathology (the tag is an
    expense magnitude) and is refused rather than rendered.
    """
    series = edgar_pit.quarterly_series(facts, edgar_tags.SHARE_BASED_COMPENSATION)
    total = edgar_pit.ttm(series, as_of)
    if total is None:
        return None
    eligible = [item for item in series if item[1] <= as_of]
    window = eligible[-4:]
    if total < 0:
        logger.warn(
            "sbc_ttm_negative", total=total,
            periods=[f"{item[0]}..{item[1]}" for item in window],
            fix="ShareBasedCompensation is an expense magnitude; a negative "
                "trailing sum means the filed facts are unusable here",
        )
        return None
    return SbcTtm(ttm=total, period_start=window[0][0], period_end=window[-1][1])


def fetch_sbc_ttm(ticker: str, as_of: date) -> SbcTtm | None:
    """The stored TTM SBC for `ticker` as of `as_of`. None = not readable."""
    out = resolve_sbc_ttm(
        edgar_pit.load_facts(ticker, edgar_tags.SHARE_BASED_COMPENSATION, as_of),
        as_of,
    )
    if out is None:
        logger.info("sbc_absent", ticker=ticker.upper(), as_of=as_of.isoformat())
    return out
