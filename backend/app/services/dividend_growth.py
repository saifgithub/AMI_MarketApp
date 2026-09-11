"""CR221 C8 — how fast the dividend has actually grown, from payments that happened.

Three request lines from three agents wanted a dividend growth rate. The
sheet already carries the trailing yield, the indicated annual rate and the
payout ratio, all of which describe the dividend *now*; none of them says
whether it has been rising, and the payout ratio alone cannot distinguish a
covered dividend that has been flat for a decade from one compounding at 13%.

The input is CR206's `dividend_history` — the payments that were really made,
indexed by ex-date. It is already fetched for the options desk, so this adds
no network call.

**Why the rate basis, not the calendar-year sum.** The obvious computation is
to sum each year's payments and compare. Measured on the live feed 2026-09-11,
that is wrong for a monthly payer: Realty Income's May 2024 ex-date slipped to
2024-06-03, so 2024 holds 11 payments and 2025 holds 13. The calendar sums
then fall 3.062 -> 2.872 and rise again to 3.490, printing a cut and a 21%
surge in a series where the company raised its rate every single month. The
sum basis reads 5.90% CAGR against the rate basis's 2.25% — a 3.65-point lie
about the thing the analyst asked for. So the series compared is the **last
regular payment of each year** (the declared rate as it stood at year end),
which is immune to how many ex-dates the calendar happened to contain. The
annual sums are still reported beside it, because a reader who wants cash
received per share should have it, and the two are labelled as what they are.

**Three more structural rules, each derived from a measured case.**

- *Specials are excluded and named.* Costco's $15.00 of 2023-12-27 and $10.00
  of 2020-12-01, and TSMC's $1.276 of 2019-06-24, are not the dividend rate.
  A payment above three times the median payment of its own year and the two
  neighbouring years is treated as special, excluded from both bases, and
  stated on the line. The three-year neighbourhood is what keeps a company
  that genuinely trebled its dividend from having the raise called a special.
- *The window must be contiguous.* Disney paid nothing in 2020, 2021 and 2022.
  "The last five complete years" would bridge that suspension and report a
  CAGR as though payments never stopped. The walk back stops at the first
  missing year, and a suspension is therefore visible as a short window rather
  than hidden inside a long one.
- *The current year is dropped.* It is partial by construction, and including
  it prints a cut every January.

At least three complete contiguous years are required; below that there is no
growth rate worth the name and the resolver returns None, which the overlay
renders as an explicit absence.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import median

from app.core.logging import logger
from app.services.market_data import DividendPayment

MAX_YEARS = 5
MIN_YEARS = 3
# A payment this many times its neighbourhood's median is a special, not the
# rate. Costco's $15.00 against a $1.02 regular is 14.7x; the largest genuine
# single-year raise in the probe set (GE 2024, 4.4x off a suppressed base)
# sits under it because the median spans the raise's own year.
SPECIAL_MULTIPLE = 3.0


@dataclass(frozen=True)
class DividendGrowth:
    """The measured growth of the declared rate, with everything it rests on."""

    first_year: int
    last_year: int
    rate_by_year: tuple[tuple[int, float], ...]
    total_by_year: tuple[tuple[int, float], ...]
    cagr_pct: float
    raised_years: int
    comparisons: int
    payments_per_year: tuple[tuple[int, int], ...]
    specials: tuple[tuple[date, float], ...]
    partial_year: int | None
    truncated_by_gap: bool


def _regular_and_special(
    by_year: dict[int, list[DividendPayment]], year: int
) -> tuple[list[DividendPayment], list[DividendPayment]]:
    neighbourhood = [
        p.amount_per_share
        for y in (year - 1, year, year + 1)
        for p in by_year.get(y, ())
    ]
    if not neighbourhood:
        return [], []
    ceiling = median(neighbourhood) * SPECIAL_MULTIPLE
    regular = [p for p in by_year[year] if p.amount_per_share <= ceiling]
    special = [p for p in by_year[year] if p.amount_per_share > ceiling]
    return regular, special


def resolve_dividend_growth(
    payments: list[DividendPayment] | None, today: date
) -> DividendGrowth | None:
    """The growth of the declared rate over the longest contiguous run of
    complete years, up to `MAX_YEARS`, or None when there is not enough.

    `None` in and `[]` in are both None out: a provider failure and a company
    that has never paid a dividend are different facts, but neither is a
    growth rate, and the overlay distinguishes them by its own state.
    """
    if not payments:
        return None

    by_year: dict[int, list[DividendPayment]] = defaultdict(list)
    for payment in payments:
        by_year[payment.ex_date.year].append(payment)
    for year in by_year:
        by_year[year].sort(key=lambda p: p.ex_date)

    partial = today.year if today.year in by_year else None
    complete = sorted(y for y in by_year if y != today.year)
    if not complete:
        return None

    # Walk back from the newest complete year while the years are contiguous.
    run = [complete[-1]]
    for year in reversed(complete[:-1]):
        if year != run[-1] - 1:
            break
        run.append(year)
        if len(run) == MAX_YEARS:
            break
    truncated_by_gap = len(run) < MAX_YEARS and len(complete) > len(run)
    years = sorted(run)

    rates: list[tuple[int, float]] = []
    totals: list[tuple[int, float]] = []
    counts: list[tuple[int, int]] = []
    specials: list[tuple[date, float]] = []
    for year in years:
        regular, special = _regular_and_special(by_year, year)
        specials.extend((p.ex_date, p.amount_per_share) for p in special)
        if not regular:
            # A year whose every payment read as special is not a year we can
            # place on the series; treat it as a gap rather than guess.
            return None
        rates.append((year, regular[-1].amount_per_share))
        totals.append((year, sum(p.amount_per_share for p in regular)))
        counts.append((year, len(regular)))

    if len(rates) < MIN_YEARS:
        logger.warn(
            "dividend_growth_window_too_short",
            years=[y for y, _ in rates], need=MIN_YEARS,
            fix="the payer's contiguous complete-year history is shorter than "
                "the minimum window (a recent initiation, a resumed dividend, "
                "or a suspension inside the window) — no growth rate is stated",
        )
        return None

    first_rate, last_rate = rates[0][1], rates[-1][1]
    spans = rates[-1][0] - rates[0][0]
    if first_rate <= 0 or spans <= 0:
        return None
    cagr = ((last_rate / first_rate) ** (1 / spans) - 1) * 100
    raised = sum(1 for i in range(1, len(rates)) if rates[i][1] > rates[i - 1][1])

    return DividendGrowth(
        first_year=rates[0][0],
        last_year=rates[-1][0],
        rate_by_year=tuple(rates),
        total_by_year=tuple(totals),
        cagr_pct=cagr,
        raised_years=raised,
        comparisons=len(rates) - 1,
        payments_per_year=tuple(counts),
        specials=tuple(sorted(specials)),
        partial_year=partial,
        truncated_by_gap=truncated_by_gap,
    )
