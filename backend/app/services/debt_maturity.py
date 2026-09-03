"""The debt maturity ladder, point-in-time from stored EDGAR facts (CR221 A1).

The Room asked for this 14 times across 6 agents in CR219's banked convenes —
the second-broadest item in CR221's register, and the cheapest: SEC
`companyfacts` already carries the five `LongTermDebtMaturities...` tags, so
the whole item is five tag entries and a resolver over facts the ingest now
stores.

Two properties this module exists to hold, both of them CR219 failure classes:

**One vintage.** Year one is the anchor; every other bucket is admitted only
if it resolves at the anchor's own `period_end`. A bucket last tagged in an
older filing is DROPPED, never backfilled — a ladder half from FY2025 and half
from FY2024 reads as one schedule and is not one.

**A stated basis.** The ladder is long-term debt PRINCIPAL. It is not gross
debt, and saying so is not pedantry: at 2025-12-31 Caterpillar's five buckets
sum to $28,160M while the fact sheet's gross debt is $45,146M, because the
ladder omits both short-term borrowings ($5,514M) and everything maturing
beyond year five. An agent handed the ladder next to gross debt with no basis
note reads the $17B gap as a contradiction and burns a turn on it — which is
the exact failure CR219 was opened to stop. So the resolver carries the two
reconciling figures it can source at the same date, and `beyond_year_five` is
derived (noncurrent debt less years two through five) rather than left as an
unexplained remainder.

That derivation is refused, not estimated, whenever it would be a guess: a
partial ladder makes the subtraction inflate the residual by the missing
buckets, and a negative residual means the two disclosures disagree. Deere is
the live case for the first refusal — it tags all five buckets but no
`LongTermDebtNoncurrent` at its FY end, so its ladder ships with
`beyond_year_five=None` rather than a fabricated one.

Layering follows `edgar_pit`: `resolve_debt_maturity` is PURE (hand-built
fixtures, no DB), `fetch_debt_maturity` is the one DB touch. Neither reads the
feature flag — `settings.room_debt_maturity_enabled` is checked at the render
call site, so a `None` from this module means one thing only: the filer
discloses no ladder we can read.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from app.core.logging import logger
from app.services import edgar_pit, edgar_tags


@dataclass(frozen=True)
class DebtMaturityLadder:
    """Principal repayments by year, all resolved at one `period_end`.

    `buckets` holds only what the filer DISCLOSED at that date, in ladder
    order, so `len(buckets) < 5` is a short ladder and must be rendered as
    one. `beyond_year_five` is derived and may be absent; the two reconciling
    figures are absent whenever they do not resolve at `period_end`.
    """

    period_end: date
    buckets: tuple[tuple[str, float], ...]
    disclosed_total: float
    beyond_year_five: float | None
    long_term_debt_noncurrent: float | None
    excluded_short_term_borrowings: float | None

    @property
    def is_complete(self) -> bool:
        """All five disclosed buckets present at the one date."""
        return len(self.buckets) == len(edgar_tags.DEBT_MATURITY_LADDER)


def _value_at(
    facts: Sequence[edgar_pit._FactView], tag: str, period_end: date
) -> float | None:
    """The value of `tag` stated AT `period_end`, newest filing wins.

    Pinning the date is the mixed-vintage guard; taking the newest `filed`
    within it is how an amendment supersedes the original, the same rule
    `resolve_instant_dated` uses.
    """
    candidates = [f for f in facts if f.tag == tag and f.period_end == period_end]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.filed).value


def resolve_debt_maturity(
    facts: Sequence[edgar_pit._FactView],
    as_of: date,
    *,
    max_age_days: int = edgar_pit.MAX_INSTANT_AGE_DAYS,
) -> DebtMaturityLadder | None:
    """The ladder as of `as_of`, or None when no readable ladder exists."""
    anchor_label, anchor_tag = edgar_tags.DEBT_MATURITY_LADDER[0]
    anchor = edgar_pit.resolve_instant_dated(
        facts, (anchor_tag,), as_of, max_age_days=max_age_days
    )
    if anchor is None:
        return None
    _, period_end = anchor

    buckets: list[tuple[str, float]] = []
    for label, tag in edgar_tags.DEBT_MATURITY_LADDER:
        value = _value_at(facts, tag, period_end)
        if value is not None:
            buckets.append((label, value))

    noncurrent = _value_at(facts, edgar_tags.LONG_TERM_DEBT_NONCURRENT, period_end)
    beyond = _beyond_year_five(buckets, noncurrent, period_end)

    return DebtMaturityLadder(
        period_end=period_end,
        buckets=tuple(buckets),
        disclosed_total=sum(v for _, v in buckets),
        beyond_year_five=beyond,
        long_term_debt_noncurrent=noncurrent,
        excluded_short_term_borrowings=_value_at(
            facts, edgar_tags.SHORT_TERM_BORROWINGS, period_end
        ),
    )


def _beyond_year_five(
    buckets: Sequence[tuple[str, float]],
    noncurrent: float | None,
    period_end: date,
) -> float | None:
    """Noncurrent debt less years two through five, when that is arithmetic.

    Requires the complete ladder: with a bucket missing, the subtraction
    silently rolls it into the residual. Requires a non-negative result: a
    negative one means the ladder and the balance sheet disagree, and the
    honest rendering of a disagreement is absence, not a number.
    """
    if noncurrent is None or len(buckets) != len(edgar_tags.DEBT_MATURITY_LADDER):
        return None
    residual = noncurrent - sum(v for _, v in buckets[1:])
    if residual < 0:
        logger.warn(
            "debt_maturity_residual_negative",
            period_end=period_end.isoformat(),
            noncurrent=noncurrent,
            years_two_to_five=sum(v for _, v in buckets[1:]),
        )
        return None
    return residual


def fetch_debt_maturity(ticker: str, as_of: date) -> DebtMaturityLadder | None:
    """The stored ladder for `ticker` as of `as_of`. None = nothing readable.

    Reads only facts `filed <= as_of`, so this is usable on a backtest date
    without leakage, exactly like the rest of `edgar_pit`.
    """
    tags = edgar_tags.DEBT_MATURITY_TAGS + (
        edgar_tags.LONG_TERM_DEBT_NONCURRENT,
        edgar_tags.SHORT_TERM_BORROWINGS,
    )
    ladder = resolve_debt_maturity(edgar_pit.load_facts(ticker, tags, as_of), as_of)
    if ladder is None:
        logger.info(
            "debt_maturity_absent", ticker=ticker.upper(), as_of=as_of.isoformat()
        )
    return ladder
