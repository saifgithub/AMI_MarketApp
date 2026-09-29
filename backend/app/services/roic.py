"""CR247 Phase 1B — return on invested capital, from the EDGAR fact store.

The Fundamentals lane carries ROE and ROA but nothing about the capital
actually employed: ROE's denominator is book equity, which buybacks shrink
(the persona already warns about exactly that), so a high ROE cannot tell a
quality business from a levered one. ROIC — operating profit after tax over
debt-plus-equity-minus-cash — is the read that can.

Every leg is a filed figure resolved through the existing tag machinery:

  * **operating income** — `edgar_tags.OPERATING_INCOME`, newest fiscal-year
    duration (the anchor period everything else must match);
  * **the effective tax rate** — `INCOME_TAX_EXPENSE` over `PRETAX_INCOME`,
    same fiscal year, stated on the rendered line as the assumption it is
    (a filed historical rate, not a forecast);
  * **invested capital** — the house gross-debt set plus equity minus cash,
    all at the anchor's `period_end`, same-moment as the numerator for
    `interest_cost`'s measured reason (Microsoft once paired a two-year-old
    numerator with a current balance sheet).

None when any leg is missing, when the tax tags disagree with the anchor's
fiscal year, or when the effective rate falls outside the sanity band — a
loss year or a net tax benefit produces a "rate" that would distort NOPAT in
the reassuring direction, which is the DEF399 shape. The comparison against
WACC is deliberately NOT computed and NOT sourced: no WACC figure exists
anywhere on this pipeline, and the rendered line says the reader supplies
their own.

Like `interest_cost`, no feature flag is read here — the flag gates the
render. The tag set needs one `scripts/ingest_edgar_facts.py --force` run
(the tax tags are new to the ingest list); until then the overlay's
loud-degrade warn fires.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.core.logging import logger
from app.services import edgar_pit, edgar_tags

# The filed effective rate is a noisy realised figure, but it is still a tax
# RATE: outside [0, 75%] it is a benefit year, a one-off, or a unit error —
# none of which a NOPAT multiple should be struck on. Measured anchors: AAPL
# FY2025 reads 15.6% ($20,719M over $132,729M).
_TAX_RATE_MAX = 0.75


@dataclass(frozen=True)
class Roic:
    """One fiscal year's ROIC, with every leg it was computed from."""

    operating_income: float
    tax_rate_pct: float
    nopat: float
    invested_capital: float
    roic_pct: float
    period_end: date


def _annual_duration_at_or_before(
    facts: Sequence[edgar_pit._FactView],
    tags: Sequence[str],
    as_of: date,
    *,
    max_age_days: int = edgar_pit.MAX_INSTANT_AGE_DAYS,
) -> tuple[float, date] | None:
    """Newest fiscal-year-length duration ending on or before `as_of`.

    Same contract as `interest_cost._annual_duration`, duplicated rather than
    imported private: that module's copy is free to grow cost-of-debt-specific
    rules without silently moving ROIC's basis.
    """
    for tag in tags:
        spans = [
            f for f in facts
            if f.tag == tag
            and f.period_start is not None
            and f.period_end <= as_of
            and (as_of - f.period_end).days <= max_age_days
            and 330 <= (f.period_end - f.period_start).days <= 380
        ]
        if spans:
            best = max(spans, key=lambda f: (f.period_end, f.filed))
            return best.value, best.period_end
    return None


def _annual_at(
    facts: Sequence[edgar_pit._FactView], tags: Sequence[str], period_end: date
) -> float | None:
    """The year-length span ending EXACTLY at `period_end`, newest-filed wins.

    The tax rate's two legs must describe the same fiscal year as the
    operating income they tax — a ratio struck across two years is not a
    rate, it is two facts wearing one name.
    """
    for tag in tags:
        spans = [
            f for f in facts
            if f.tag == tag
            and f.period_start is not None
            and f.period_end == period_end
            and 330 <= (f.period_end - f.period_start).days <= 380
        ]
        if spans:
            return max(spans, key=lambda f: f.filed).value
    return None


def resolve_roic(
    facts: Sequence[edgar_pit._FactView], as_of: date
) -> Roic | None:
    """ROIC as of `as_of`, or None when no honest computation survives."""
    anchor = _annual_duration_at_or_before(facts, edgar_tags.OPERATING_INCOME, as_of)
    if anchor is None:
        return None
    operating_income, period_end = anchor

    tax = _annual_at(facts, edgar_tags.INCOME_TAX_EXPENSE, period_end)
    pretax = _annual_at(facts, edgar_tags.PRETAX_INCOME, period_end)
    if tax is None or pretax is None:
        return None
    if pretax <= 0:
        # A pre-tax loss has no effective rate worth the name, and striking
        # NOPAT on one would dress a loss year up as a return figure.
        return None
    rate = tax / pretax
    if not (0.0 <= rate <= _TAX_RATE_MAX):
        logger.warn(
            "roic_tax_rate_implausible", rate=round(rate, 4),
            period_end=period_end.isoformat(),
            fix="the filed effective rate is outside the sanity band (a "
                "benefit year, a one-off, or a unit error) — no NOPAT is "
                "struck on it",
        )
        return None

    # The balance-sheet legs are resolved at the NUMERATOR's period end, not
    # at `as_of` — same-moment or nothing, `interest_cost`'s measured rule.
    at_or_before = [f for f in facts if f.period_end <= period_end]
    debt = edgar_pit.instant_sum(
        at_or_before, edgar_tags.DEBT_ANCHOR, edgar_tags.DEBT_OPTIONAL_ADD, period_end
    )
    equity = edgar_pit.resolve_instant(at_or_before, edgar_tags.EQUITY, period_end)
    cash = edgar_pit.instant_sum(
        at_or_before, edgar_tags.CASH_ANCHOR, edgar_tags.CASH_OPTIONAL_ADD, period_end
    )
    if debt is None or equity is None or cash is None:
        return None
    invested_capital = debt + equity - cash
    if invested_capital <= 0:
        # More cash than debt plus equity is a real shape for a cash-pile
        # company, but "capital employed" has then netted itself out of
        # existence and the ratio has no denominator. Absent, not infinite.
        return None

    nopat = operating_income * (1.0 - rate)
    return Roic(
        operating_income=operating_income,
        tax_rate_pct=round(rate * 100, 1),
        nopat=nopat,
        invested_capital=invested_capital,
        roic_pct=round(nopat / invested_capital * 100, 1),
        period_end=period_end,
    )


def fetch_roic(ticker: str, as_of: date) -> Roic | None:
    """The stored ROIC for `ticker` as of `as_of`. None = not readable."""
    tags = (
        edgar_tags.OPERATING_INCOME
        + edgar_tags.INCOME_TAX_EXPENSE
        + edgar_tags.PRETAX_INCOME
        + edgar_tags.DEBT_ANCHOR
        + edgar_tags.DEBT_OPTIONAL_ADD
        + edgar_tags.EQUITY
        + edgar_tags.CASH_ANCHOR
        + edgar_tags.CASH_OPTIONAL_ADD
    )
    out = resolve_roic(edgar_pit.load_facts(ticker, tags, as_of), as_of)
    if out is None:
        logger.info("roic_absent", ticker=ticker.upper(), as_of=as_of.isoformat())
    return out
