"""What this company actually pays to borrow (CR221 A3, DEF399).

Six request lines from four agents asked for an average interest rate or cost
of debt, and CR221 §4 first ruled the item IN HAND — a division of the
`Interest Expense` row `fundamentals.py` already reads for interest coverage.
Measuring that premise is what produced DEF399: for an issuer whose captive
finance arm books its interest inside cost of revenue, the yfinance row is the
LEFTOVER non-operating line. Caterpillar's FY2025 income statement carries
$1,359M of Financial Products interest plus $502M excluding it; the row reads
$529M, 28% of the $1,861M consolidated total.

So the numerator comes from EDGAR instead, on one of two bases that are named
rather than blended:

  * **accrued** — `InterestExpense`, the income-statement concept, TTM from
    discrete quarters where the filer reports enough of them, else the fiscal
    year;
  * **cash** — `InterestPaidNet`, the cash-flow supplemental, annual only.

Caterpillar is why both exist: it tags NO income-statement interest concept in
`companyfacts` at all, because its two interest lines are dimensional and that
API serves the consolidated non-dimensional fact only (CR221 §6's finding, on
a second item). Its cost of debt is therefore cash-basis or nothing.

**Where the two bases disagree by more than `_BASIS_DISAGREEMENT_LIMIT`, this
module returns nothing.** A gap that size means one of the tags is not
consolidated, and which one cannot be determined without reading the filing —
Harley-Davidson ($31M accrued against $331M paid) and Ford ($7,613M against
$3,501M) are the measured cases. Choosing the more flattering of two numbers
we cannot reconcile is exactly the defect above; a declared absence is the
honest output, and the ratio is logged so the cases are countable.

Numerator and denominator both come from the same fact store at the same
`as_of`, so this is PIT-correct and reusable on a backtest date. Like
`debt_maturity`, it reads no feature flag: `None` means no readable figure.

**Known bias in the denominator, measured and deliberately not patched.** The
house gross-debt definition (`DEBT_ANCHOR` + `DEBT_OPTIONAL_ADD`) sums to
$36,210M for Caterpillar at 2025-12-31, against $45,146M from the live sheet,
because CAT tags its current maturities of long-term debt dimensionally and
`LongTermDebtCurrent` / `DebtCurrent` resolve to nothing. A short denominator
biases the rate HIGH — CAT reads 5.1% where the fuller base gives ~4.3%. The
missing piece is exactly `debt_maturity`'s year-one bucket ($7,120M), so the
two items compose, but adding it here conditionally would double-count for
every filer that DOES tag current debt and would silently redefine gross debt
for one consumer only. Recorded as a bound on the figure rather than fixed
behind the reader's back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from app.core.logging import logger
from app.services import edgar_pit, edgar_tags
from app.trading_math.valuation import cost_of_debt_pct

# Above this ratio between the accrual and cash figures, one of them is not the
# consolidated number — measured at 10.7x (HOG) and 2.2x (F), against <1.1x for
# every filer in the cohort that reads correctly.
_BASIS_DISAGREEMENT_LIMIT = 2.0

ACCRUED_TTM = "accrued interest expense, trailing four quarters"
ACCRUED_ANNUAL = "accrued interest expense, fiscal year"
CASH_ANNUAL = "cash interest paid, fiscal year"


@dataclass(frozen=True)
class InterestCost:
    """Annual interest and the rate it implies, with the basis it was struck on.

    `basis` is not decoration. An accrued-TTM figure and a cash-paid annual
    figure are different measurements, and a render that prints the rate
    without saying which one it used invites the same conflation DEF399 is.
    """

    annual_interest: float
    basis: str
    period_end: date
    gross_debt: float
    cost_of_debt_pct: float | None


def _annual_duration(
    facts: Sequence[edgar_pit._FactView],
    tags: Sequence[str],
    as_of: date,
    *,
    max_age_days: int = edgar_pit.MAX_INSTANT_AGE_DAYS,
) -> tuple[float, date] | None:
    """Newest fiscal-year-length duration ending on or before `as_of`.

    Aged out at `max_age_days`, and that bound is load-bearing rather than
    defensive: Microsoft's newest `InterestExpense` in `companyfacts` is FY2024,
    while its balance sheet resolves at 2026-06-30, so without this the rate
    read 7.3% from a two-year-old numerator over a current denominator. A
    company that has not filed an annual interest figure in over a year is
    data-dark for this ratio, not cheap to borrow.
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


def _accrued(
    facts: Sequence[edgar_pit._FactView], as_of: date
) -> tuple[float, str, date] | None:
    series = edgar_pit.quarterly_series(facts, edgar_tags.INTEREST_ACCRUAL)
    trailing = edgar_pit.ttm(series, as_of)
    if trailing is not None:
        return trailing, ACCRUED_TTM, series[-1][1]
    annual = _annual_duration(facts, edgar_tags.INTEREST_ACCRUAL, as_of)
    if annual is not None:
        return annual[0], ACCRUED_ANNUAL, annual[1]
    return None


def resolve_interest_cost(
    facts: Sequence[edgar_pit._FactView], as_of: date
) -> InterestCost | None:
    """Cost of debt as of `as_of`, or None when no basis survives the checks."""
    accrued = _accrued(facts, as_of)
    cash = _annual_duration(facts, edgar_tags.INTEREST_CASH, as_of)

    if accrued and cash and _bases_disagree(abs(accrued[0]), abs(cash[0]), as_of):
        return None

    chosen = accrued or (
        (cash[0], CASH_ANNUAL, cash[1]) if cash else None
    )
    if chosen is None:
        return None

    value, basis, period_end = chosen
    # The denominator is resolved at the NUMERATOR's period end, not at
    # `as_of`. A ratio whose two legs describe different moments is not a
    # rate: Microsoft paired FY2024 interest with a 2026-06-30 balance sheet
    # and computed 7.3%. Same moment, or nothing.
    #
    # The list is filtered rather than the date merely passed down, because
    # `resolve_instant_dated` has no upper bound on `period_end` — it leans on
    # `load_facts`' `filed <= as_of` to make a future balance sheet impossible,
    # which is true of the DATE THE CALLER ASKED FOR and not of an earlier one
    # substituted here.
    at_or_before = [f for f in facts if f.period_end <= period_end]
    gross_debt = edgar_pit.instant_sum(
        at_or_before, edgar_tags.DEBT_ANCHOR, edgar_tags.DEBT_OPTIONAL_ADD, period_end
    )
    if gross_debt is None:
        return None

    return InterestCost(
        annual_interest=abs(value),
        basis=basis,
        period_end=period_end,
        gross_debt=gross_debt,
        cost_of_debt_pct=cost_of_debt_pct(value, gross_debt),
    )


def _bases_disagree(accrued: float, cash: float, as_of: date) -> bool:
    if not accrued or not cash:
        return False
    ratio = max(accrued, cash) / min(accrued, cash)
    if ratio <= _BASIS_DISAGREEMENT_LIMIT:
        return False
    logger.warn(
        "interest_cost_bases_disagree",
        as_of=as_of.isoformat(), accrued=accrued, cash=cash, ratio=round(ratio, 2),
    )
    return True


def fetch_interest_cost(ticker: str, as_of: date) -> InterestCost | None:
    """The stored cost of debt for `ticker` as of `as_of`. None = not readable."""
    tags = (
        edgar_tags.INTEREST_ACCRUAL
        + edgar_tags.INTEREST_CASH
        + edgar_tags.DEBT_ANCHOR
        + edgar_tags.DEBT_OPTIONAL_ADD
    )
    cost = resolve_interest_cost(edgar_pit.load_facts(ticker, tags, as_of), as_of)
    if cost is None:
        logger.info(
            "interest_cost_absent", ticker=ticker.upper(), as_of=as_of.isoformat()
        )
    return cost
