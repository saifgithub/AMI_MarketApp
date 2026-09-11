"""CR221 C7 — what the company actually paid per share for its own stock.

One request line from one agent, and it is the question the buyback figures
already on the sheet cannot answer. R35 renders dollars repurchased over the
trailing four quarters and their share of market cap; neither says whether
management bought well. A board that spent $7bn near the 52-week high and one
that spent it near the low have run the same line item to opposite effect.

The computation is a quotient of two figures the filer states: dollars
repurchased (`edgar_tags.BUYBACKS`, already ingested for R35) over shares
acquired (`edgar_tags.BUYBACK_SHARES`, added by this slot). It is **AMI's own
arithmetic on two filed figures, not a reported average price**, and the line
says so — filers that do disclose an average execution price compute it on
their own basis, and the two need not agree.

**Both legs must span the same quarters, and the four must be consecutive.**
The two tags are separate series and a filer may report one for a quarter it
omits the other. Pairing a four-quarter dollar total with a three-quarter
share total would divide by a number too small and overstate the price paid —
in the reassuring direction for a buyback near the highs, which is exactly the
DEF399 shape. So the resolver pairs quarter by quarter on `(period_start,
period_end)`.

Pairing alone is not enough, and the live probe proved it: measured on CAT's
companyfacts 2026-09-11, the dollar tag resolves 26 discrete quarters and the
share tag 47, but the newest four they share are **Q1 of 2023, 2024, 2025 and
2026** — the same calendar quarter four years running. Summing those gives
$13,543M over 26.1M shares and a $518.82 "trailing-twelve-month" average
price spanning three and a quarter years. That is `ttm()`'s documented hazard
(a hole in the middle summing three quarters of one year with one of another)
arriving through a second series, so the window is required to be contiguous:
four quarters whose periods run end-to-end and together span roughly a year.
CAT is therefore an ABSENT state today, not a number.

**Deere tags no share count**, measured in CR221 §4b (CAT n=197 points, Deere
none), so uneven filer coverage is the normal case and the absent state is
the common outcome, not an error.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.core.logging import logger
from app.services import edgar_pit, edgar_tags

# A filer can report a tiny residual share count against real dollars (an
# odd-lot settlement, a plan true-up). Dividing by it prints a five-figure
# "average price". Below this the quotient is not a price and is refused.
MIN_SHARES = 1_000.0
# Above this the quotient is not a per-share price either — it is a unit or
# scaling error in the filing or the ingest. Berkshire A shares trade near
# $700k, so the ceiling is set well clear of the most expensive US listing.
MAX_PRICE = 2_000_000.0


@dataclass(frozen=True)
class BuybackPrice:
    """The implied average execution price, with the window it rests on."""

    avg_price: float
    dollars: float
    shares: float
    period_start: date
    period_end: date
    quarters: int


def resolve_buyback_price(facts, as_of: date) -> BuybackPrice | None:
    """The implied average price over the last four quarters carrying BOTH
    legs, or None when either leg is missing, short, or implausible.

    None is the expected outcome for a filer that tags no share count, and
    the overlay renders it as an explicit absence rather than a zero.
    """
    dollar_series = edgar_pit.quarterly_series(facts, edgar_tags.BUYBACKS)
    share_series = edgar_pit.quarterly_series(facts, edgar_tags.BUYBACK_SHARES)
    if not dollar_series or not share_series:
        return None

    shares_by_period = {(start, end): value for start, end, value in share_series}
    paired = [
        (start, end, dollars, shares_by_period[(start, end)])
        for start, end, dollars in dollar_series
        if (start, end) in shares_by_period and end <= as_of
    ]
    if len(paired) < 4:
        logger.warn(
            "buyback_price_legs_unpaired",
            paired_quarters=len(paired),
            dollar_quarters=len(dollar_series), share_quarters=len(share_series),
            fix="dollars repurchased and shares acquired must span the SAME four "
                "quarters; the filer tags one without the other, so no implied "
                "price is stated (Deere tags no share count at all)",
        )
        return None

    window = paired[-4:]
    # Contiguity: each quarter must start where the previous ended (a day's
    # slack for filers whose periods abut rather than share a boundary), and
    # the four together must span about a year. Without this the newest four
    # SHARED quarters can be Q1 of four consecutive years — measured on CAT.
    for earlier, later in zip(window, window[1:]):
        if abs((later[0] - earlier[1]).days) > 7:
            logger.warn(
                "buyback_price_window_not_contiguous",
                periods=[f"{item[0]}..{item[1]}" for item in window],
                fix="the four quarters carrying both legs are not consecutive "
                    "(a filer tagging one leg only in some quarters) — summing "
                    "them would label a multi-year total as trailing-twelve-month",
            )
            return None
    span = (window[-1][1] - window[0][0]).days
    if not (330 <= span <= 400):
        logger.warn(
            "buyback_price_window_not_a_year", span_days=span,
            periods=[f"{item[0]}..{item[1]}" for item in window],
            fix="four paired quarters that do not span about a year are not a "
                "trailing-twelve-month window",
        )
        return None
    dollars = sum(item[2] for item in window)
    shares = sum(item[3] for item in window)
    if dollars <= 0 or shares < MIN_SHARES:
        return None
    price = dollars / shares
    if not (0 < price < MAX_PRICE):
        logger.warn(
            "buyback_price_implausible", price=price, dollars=dollars, shares=shares,
            fix="the quotient is outside any real per-share price — treat the "
                "filed figures as unusable rather than rendering it",
        )
        return None

    return BuybackPrice(
        avg_price=price, dollars=dollars, shares=shares,
        period_start=window[0][0], period_end=window[-1][1], quarters=len(window),
    )
