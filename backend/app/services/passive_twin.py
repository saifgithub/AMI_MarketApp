"""CR222 §2 — the passive twin: what the SAME money, on the SAME dates, held in a mandate-matched passive instrument and never traded, would have returned.

Portfolio Health can already say how the book moved and how much of that motion
the market explains. It cannot say the one thing that decides an individual
investor's outcome — whether the decisions were worth making at all. The twin is
that counterfactual, built from inputs that already exist: `portfolio_nav_daily`
(CR109) supplies the date grid and the capital events, `price_history_daily`
(CR136 M01) supplies the twin's closes.

**Construction.** Every `open` / `restart` row on the user's NAV series is a
deposit of that row's own NAV — `open` is the portfolio's starting capital and
`restart` is `reset_portfolio()`'s fresh stake, which is exactly the shape
`portfolio_nav_daily` infers. The twin receives that cash on that date, buys the
instrument at its close, and never trades again. A `restart` liquidates the twin
and re-deposits, because the user's own restart wipes the book — a twin that
kept compounding through a reset would be comparing against a portfolio the user
no longer has. Twin and user therefore share one date grid, one set of flow
dates and one set of flow amounts, and differ in exactly one thing: what the
money was put into.

**Two return measures, because they answer different questions.** Time-weighted
return removes the timing of the deposits (the same chain-linking
`trading_math/twr.py` already does for the equity curve); dollar-weighted return
— the IRR over the flow schedule — keeps it. Reporting only one hides half the
story: TWR alone flatters a user whose big deposit landed before a fall, and IRR
alone reads a well-timed deposit as skill at picking securities. Both are
computed for both series, and both differences are reported.

The IRR solver is a bisection on the NPV, in this module, with no new
dependency — a closed-form root does not exist and the schedules here are small,
sign-regular (deposits then one terminal value) and therefore have exactly one
root to find.

**Degrade loudly (CR040/DEF059).** A halal mandate whose Sharia-screened
instrument has not been configured yields `sufficient:false` with a cause naming
the unconfigured mapping. It NEVER falls back to the default ticker: a halal
user silently benchmarked against an unscreened S&P 500 fund would be shown a
number their own mandate forbids them to hold, with nothing on the page saying
so. A mapped ticker with no stored price history for the window is
`twin_history` for the same reason.

**Honesty rules are CR131's.** No grade, no warning, no verdict; the block has
one shape whether the user is ahead of the twin or behind it. Machine states
only — every user-facing string is M06/M09's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence
from uuid import UUID

from app.core.config import settings
from app.core.logging import logger
from app.trading_math.twr import NavPoint, time_weighted_return

# The machine states a caller may see on `insufficient_cause`. Named constants
# rather than literals because the mobile client and the renderer both branch on
# them, and a typo in one copy is a block that renders as nothing.
INSUFFICIENT_TWIN_UNMAPPED = "twin_unmapped"
INSUFFICIENT_TWIN_HISTORY = "twin_history"
INSUFFICIENT_TWIN_SHORT_WINDOW = "twin_short_window"
INSUFFICIENT_TWIN_NO_CAPITAL = "twin_no_capital"

# The machine state that rides a SUFFICIENT block between the two floors: the
# difference is published, and it carries no sampling-error estimate because
# there is no bootstrap in Portfolio Health and this CR does not build one
# (CR222 Corrections §6). Saying so is the alternative to implying a precision
# nobody measured.
DIFFERENCE_PRECISION_NO_SE = "no_sampling_error_estimate"
DIFFERENCE_PRECISION_NONE = "none"

TWIN_METRIC = "passive_twin"

# CR222 §1 toll symmetry — the machine state naming BOTH sides' cost treatment,
# present on the block only while `training_toll_enabled` is on. Off, the key is
# absent entirely and the block is byte-identical to slice B's, which is the
# same absent-not-zeroed contract the whole twin flag holds.
COST_TREATMENT_BOTH_TOLLED = "both_sides_tolled_twin_untraded_untaxed"


def _twin_toll_charged() -> bool:
    """Whether the twin's deposit-buys pay the toll — the SAME flag the user's
    own fills read, deliberately not a second one. Two switches is how the two
    sides of one comparison end up on different cost bases."""
    from app.services.training_toll import toll_enabled

    return toll_enabled()

_CAPITAL_EVENT_DEPOSITS = ("open", "restart")

# Bisection bounds on the ANNUAL rate. −0.9999 is a near-total annual loss (the
# NPV is undefined at −1) and 1e6 is a 100,000,000%/year return — orders of
# magnitude beyond any real schedule, so a sign-regular schedule's single root is
# always inside the bracket.
#
# Annual with a year-fraction exponent rather than a daily rate compounded up:
# a daily rate near the low bound raised to a multi-hundred-day power underflows
# to exactly 0.0 and the discount divides by zero, which is a solver that fails
# on the deepest losses — precisely the schedules a training account produces.
_IRR_LOW = -0.9999
_IRR_HIGH = 1e6
_IRR_ITERATIONS = 200
_DAYS_PER_YEAR = 365.0


@dataclass(frozen=True)
class CashFlow:
    """One dated flow. Negative = money in (a deposit), positive = money out.

    Sign convention is the IRR's, not the user's: the terminal NAV is the
    money the schedule gives back, so it is the one positive entry.
    """

    on: date
    amount: float


@dataclass(frozen=True)
class SeriesReturns:
    irr: float | None
    twr: float | None


def _npv(flows: Sequence[CashFlow], rate: float) -> float:
    """Present value of the schedule at an ANNUAL `rate`, discounted from the
    first flow's date by ACT/365 year fractions."""
    origin = flows[0].on
    total = 0.0
    for flow in flows:
        years = (flow.on - origin).days / _DAYS_PER_YEAR
        total += flow.amount / ((1.0 + rate) ** years)
    return total


def irr(flows: Sequence[CashFlow]) -> float | None:
    """Annualised internal rate of return over `flows`, or `None`.

    Bisection on the annual rate, ACT/365. Deterministic by construction: a
    fixed bracket, a fixed iteration count, no random restart and no dependency
    — the same schedule always produces the same number to the last bit, which
    is what lets the acceptance test compare a portfolio against its own twin to
    the cent.

    `None` when the schedule cannot have a rate: fewer than two flows, no sign
    change (all money in, or all money out), or a bracket whose endpoints do not
    straddle zero. Returning 0.0 for any of those would be a fabricated number
    in a report whose whole contract is that a null means one thing.
    """
    if len(flows) < 2:
        return None
    if not any(f.amount < 0.0 for f in flows) or not any(f.amount > 0.0 for f in flows):
        return None
    if flows[-1].on == flows[0].on:
        return None

    low, high = _IRR_LOW, _IRR_HIGH
    npv_low, npv_high = _npv(flows, low), _npv(flows, high)
    if npv_low * npv_high > 0.0:
        return None

    for _ in range(_IRR_ITERATIONS):
        mid = (low + high) / 2.0
        npv_mid = _npv(flows, mid)
        if npv_mid == 0.0:
            low = high = mid
            break
        if npv_low * npv_mid < 0.0:
            high, npv_high = mid, npv_mid
        else:
            low, npv_low = mid, npv_mid

    return (low + high) / 2.0


def _flows_for(
    dates: Sequence[date],
    navs: Sequence[float],
    events: Sequence[str | None],
    deposits: Sequence[float] | None = None,
) -> list[CashFlow]:
    """The IRR schedule for one NAV series: a deposit at each capital event, and
    the terminal NAV as the single money-out flow.

    A capital event on the FINAL date contributes a deposit and nothing else has
    happened to it yet, which is a schedule with no elapsed time — `irr` refuses
    it rather than reporting the arithmetic of a zero-length window.

    `deposits` (CR222 §1) is the amount that WENT IN at each event, which is the
    user's own NAV on both series — the twin receives the same cash on the same
    dates by definition. It defaults to `navs` and only differs once the toll is
    on: the twin's day-0 VALUE is then the deposit minus the toll it paid to buy,
    and charging the schedule the value rather than the deposit would hide the
    toll it just paid inside the amount it is measured against.
    """
    amounts = navs if deposits is None else deposits
    flows: list[CashFlow] = []
    for on, amount, event in zip(dates, amounts, events):
        if event in _CAPITAL_EVENT_DEPOSITS:
            flows.append(CashFlow(on=on, amount=-float(amount)))
    if not flows:
        return []
    flows.append(CashFlow(on=dates[-1], amount=float(navs[-1])))
    return flows


def _returns_for(
    dates: Sequence[date],
    navs: Sequence[float],
    events: Sequence[str | None],
    deposits: Sequence[float] | None = None,
) -> SeriesReturns:
    points = [
        NavPoint(as_of=d, nav=float(n), capital_event=e)
        for d, n, e in zip(dates, navs, events)
    ]
    return SeriesReturns(
        irr=irr(_flows_for(dates, navs, events, deposits)),
        twr=time_weighted_return(points),
    )


# ── Mandate mapping ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TwinInstrument:
    ticker: str
    expense_ratio_pct: float
    halal: bool


def map_twin_instrument(mandate) -> TwinInstrument | None:
    """The mandate's passive instrument, or `None` when the mapping is
    unconfigured.

    `None` is only ever the halal arm with no configured Sharia-screened ticker,
    and it is deliberately not substitutable: returning the default ticker there
    would benchmark a halal user against a fund their own mandate forbids and
    say nothing about it. The caller renders `twin_unmapped`.

    `mandate` may be a `Mandate`, a plain dict of one, or `None`; the halal
    marker lives at `compliance.halal` in all three shapes.
    """
    compliance = None
    if mandate is not None:
        compliance = (
            mandate.get("compliance") if isinstance(mandate, dict)
            else getattr(mandate, "compliance", None)
        )
    if isinstance(compliance, dict):
        halal = bool(compliance.get("halal"))
    else:
        halal = bool(getattr(compliance, "halal", False))

    if halal:
        ticker = (settings.passive_twin_halal_ticker or "").upper().strip()
        if not ticker:
            logger.warn(
                "passive_twin_halal_unmapped",
                reason=(
                    "compliance.halal is true and PASSIVE_TWIN_HALAL_TICKER is "
                    "unset — the block is published insufficient rather than "
                    "falling back to the default ticker, which the mandate "
                    "forbids this user to hold"
                ),
            )
            return None
        return TwinInstrument(
            ticker=ticker,
            expense_ratio_pct=float(settings.passive_twin_halal_expense_ratio_pct),
            halal=True,
        )

    return TwinInstrument(
        ticker=(settings.passive_twin_default_ticker or "").upper().strip(),
        expense_ratio_pct=float(settings.passive_twin_default_expense_ratio_pct),
        halal=False,
    )


# ── Block ───────────────────────────────────────────────────────────────────


def _insufficient(
    cause: str, *, ticker: str | None = None, expense_ratio_pct: float | None = None,
    market_days: int = 0,
) -> dict:
    """An insufficient twin block carries NO numbers a reader could mistake for
    a measurement — same null-forcing contract as `portfolio_health._block`, for
    the same reason: `null` has to mean exactly one thing downstream."""
    block = {
        "metric": TWIN_METRIC,
        "sufficient": False,
        "insufficient_cause": cause,
        "twin_ticker": ticker,
        "twin_expense_ratio_pct": expense_ratio_pct,
        "market_days": market_days,
        "user_irr": None,
        "user_twr": None,
        "twin_irr": None,
        "twin_twr": None,
        "irr_difference": None,
        "twr_difference": None,
        "difference_precision": DIFFERENCE_PRECISION_NONE,
    }
    return _with_cost_treatment(block)


def _with_cost_treatment(block: dict) -> dict:
    """Add the cost-treatment machine state, and ONLY while the toll is on.

    Absent, not null, when the toll is off — the flag-off block has to be
    byte-identical to slice B's, and a key holding `None` is not the same dict.
    """
    if _twin_toll_charged():
        block["cost_treatment"] = COST_TREATMENT_BOTH_TOLLED
    return block


def build_twin_block(
    *,
    nav_dates: Sequence[date],
    nav_values: Sequence[float],
    capital_events: Sequence[str | None],
    twin_closes: dict[date, float],
    instrument: TwinInstrument | None,
) -> dict:
    """The `passive_twin` block, pure — no DB, no config beyond the two floors.

    `twin_closes` is keyed by the SAME dates as the NAV grid; a date the
    instrument did not price is a hole in the twin's series, and a hole makes
    the block insufficient rather than interpolated, because an invented close
    is exactly the fabrication CR040 exists to refuse.
    """
    if instrument is None:
        return _insufficient(INSUFFICIENT_TWIN_UNMAPPED)

    ticker = instrument.ticker
    expense = instrument.expense_ratio_pct
    market_days = len(nav_dates)

    if not ticker:
        return _insufficient(INSUFFICIENT_TWIN_UNMAPPED, market_days=market_days)

    if market_days < int(settings.twin_min_market_days):
        return _insufficient(
            INSUFFICIENT_TWIN_SHORT_WINDOW,
            ticker=ticker, expense_ratio_pct=expense, market_days=market_days,
        )

    missing = [d for d in nav_dates if twin_closes.get(d) is None]
    if missing:
        logger.warn(
            "passive_twin_missing_history",
            ticker=ticker, missing_days=len(missing), market_days=market_days,
            first_missing=missing[0].isoformat(),
        )
        return _insufficient(
            INSUFFICIENT_TWIN_HISTORY,
            ticker=ticker, expense_ratio_pct=expense, market_days=market_days,
        )

    if not any(e in _CAPITAL_EVENT_DEPOSITS for e in capital_events):
        return _insufficient(
            INSUFFICIENT_TWIN_NO_CAPITAL,
            ticker=ticker, expense_ratio_pct=expense, market_days=market_days,
        )

    # The twin's own NAV, day by day. A deposit buys at that day's close; a
    # `restart` liquidates first, because the user's restart wiped the book and
    # a twin that kept compounding through it would be measuring against a
    # portfolio that no longer exists.
    #
    # CR222 §1 toll symmetry: once the toll is on, the twin's own deposit-buy is
    # a fill and pays it, so the deposit buys shares with what is left after the
    # toll. Without this the comparison is rigged in the twin's favour from the
    # first day the flag is on — the user's book pays a cost the benchmark does
    # not — which is the difference reading as skill when it is only accounting.
    # One side, not two: a deposit-buy is ONE fill and the twin never trades
    # again, so it pays once and the user pays on every fill they place. That
    # asymmetry is the real one, and it is what the block's own machine state
    # says out loud.
    charge_toll = _twin_toll_charged()
    shares = 0.0
    twin_values: list[float] = []
    for on, nav, event in zip(nav_dates, nav_values, capital_events):
        close = float(twin_closes[on])
        if event in _CAPITAL_EVENT_DEPOSITS:
            deposit = float(nav)
            if charge_toll:
                from app.services.training_toll import equity_toll

                deposit = max(0.0, deposit - equity_toll(deposit))
            shares = deposit / close
        twin_values.append(shares * close)

    user_navs = [float(v) for v in nav_values]
    user = _returns_for(nav_dates, user_navs, capital_events)
    # The twin's schedule is measured against the SAME cash the user put in,
    # never against the shares that cash bought after its own toll came out.
    # `deposits` is `user_navs` on both flag states; with the toll off the twin's
    # value at each event equals it, so this is a no-op there by construction.
    twin = _returns_for(
        nav_dates, twin_values, capital_events, deposits=user_navs,
    )

    precision = (
        DIFFERENCE_PRECISION_NO_SE
        if market_days < int(settings.twin_min_market_days_for_se)
        else DIFFERENCE_PRECISION_NONE
    )

    return _with_cost_treatment({
        "metric": TWIN_METRIC,
        "sufficient": True,
        "insufficient_cause": None,
        "twin_ticker": ticker,
        "twin_expense_ratio_pct": expense,
        "market_days": market_days,
        "user_irr": user.irr,
        "user_twr": user.twr,
        "twin_irr": twin.irr,
        "twin_twr": twin.twr,
        "irr_difference": (
            None if user.irr is None or twin.irr is None else user.irr - twin.irr
        ),
        "twr_difference": (
            None if user.twr is None or twin.twr is None else user.twr - twin.twr
        ),
        # Never an interval, and never silence about the absence of one. Between
        # the two floors this says out loud that the difference above carries no
        # sampling-error estimate; at or above the upper floor it is `none`,
        # which means the same thing for a different reason — nothing in
        # Portfolio Health estimates one at any length (CR222 Corrections §6).
        "difference_precision": precision,
    })


def build_passive_twin(user_id: UUID, *, mandate=None, nav_rows=None) -> dict | None:
    """The block for one user's TRAINING portfolio, or `None` when the flag is
    off — an absent block, not an insufficient one, because a flag-off feature
    must leave the report byte-identical to what it was before the CR.

    `nav_rows` is injectable for tests; production reads `portfolio_nav_daily`
    through CR109's own accessor so the twin can never be built on a differently
    resolved series than the equity curve the user already sees.
    """
    if not settings.portfolio_passive_twin_enabled:
        return None

    if nav_rows is None:
        from app.services.portfolio_nav_daily import nav_history

        nav_rows = nav_history(user_id)

    nav_dates = [r.as_of_date for r in nav_rows]
    nav_values = [float(r.nav) for r in nav_rows]
    capital_events = [r.capital_event for r in nav_rows]

    instrument = map_twin_instrument(mandate)
    if instrument is None or not nav_dates:
        return build_twin_block(
            nav_dates=nav_dates, nav_values=nav_values,
            capital_events=capital_events, twin_closes={}, instrument=instrument,
        )

    closes = twin_closes_for(instrument.ticker, nav_dates)
    return build_twin_block(
        nav_dates=nav_dates,
        nav_values=nav_values,
        capital_events=capital_events,
        twin_closes=closes,
        instrument=instrument,
    )


def twin_closes_for(ticker: str, wanted: Sequence[date]) -> dict[date, float]:
    """The instrument's adjusted closes on exactly `wanted`, from
    `price_history_daily`.

    A PURE read of what is stored — no fetch, no read-through. The twin is a
    counterfactual over a window that has already happened, so a fetch here
    could only add today's provenance to yesterday's answer; a missing date
    stays missing and the caller publishes `twin_history` rather than filling
    the hole. Adjusted closes, so dividends the twin would have received are in
    the series rather than silently forfeited.
    """
    if not wanted:
        return {}

    from sqlalchemy import select

    from app.db import get_session
    from app.db.models import PriceHistoryDailyRow
    from app.services.price_history import _MOCK_SOURCE

    t = (ticker or "").upper().strip()
    stmt = (
        select(PriceHistoryDailyRow)
        .where(PriceHistoryDailyRow.ticker == t)
        .where(PriceHistoryDailyRow.date >= min(wanted))
        .where(PriceHistoryDailyRow.date <= max(wanted))
    )
    if settings.use_real_market_data:
        stmt = stmt.where(PriceHistoryDailyRow.source != _MOCK_SOURCE)
    with get_session() as session:
        rows = session.execute(stmt).scalars().all()
    stored = {r.date: float(r.adj_close) for r in rows}
    return {d: stored[d] for d in wanted if d in stored}
