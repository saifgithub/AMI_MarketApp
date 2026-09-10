"""CR222 §1 (Ruling 1, option B) — the training lane's transaction cost, CHARGED.

Until this module the training lane moved exactly the notional: no commission,
no spread, no toll. In the measured brokerage record that omission is not a
rounding detail — the average household earned 18.7% gross and 16.4% net
against a 17.9% market (Barber & Odean 2000), so the toll, not stock selection,
is what turned a gross win into a net loss. A simulator that omits it teaches
the wrong lesson at exactly the point the evidence says matters most.

**A proxy, and labeled as one.** The rate is a flat spread-plus-commission
estimate, not a measured half-spread. Charging a flat proxy is honest as long as
nothing calls it a measurement; the follow-on handle `measured-toll` captures
the live bid-ask at fill and charges the real half-spread. Deliberate parity
with `games_scoring.FEE_BPS`/`FEE_MIN` — the two lanes should not disagree about
what a round trip costs without a stated reason, and there is none.

**No backfill (Ruling 1).** Nothing here re-costs a historical fill. The toll
attaches only to a fill executed while `training_toll_enabled` is on, and every
portfolio's cumulative toll therefore starts at 0 on the day the flag flips.
That is why the cumulative figure is DERIVED by summing the per-row amounts
rather than kept as a running counter on the portfolio: a counter would have to
be seeded for every existing portfolio, and a seed is a backfill wearing a
different name. A trade row written before flag-on carries NULL, and NULL sums
to nothing.

**Restart semantics come free from the same choice.** `reset_portfolio()` is a
destroy-and-recreate — a fresh `sim_portfolios` UUID, with every `sim_trades`,
`sim_short_positions` and `sim_option_trades` row of the old book explicitly
deleted — which is exactly the event `portfolio_nav_daily` records as `restart`.
A cumulative summed over the new portfolio's own rows is therefore 0 again the
moment the book is wiped, with no reset code to write and none to forget.

**Shorts pay the toll on the fill and nothing else changes.** The borrow accrual
in `short_borrow_rate.py` is a holding cost per day; this is a transaction cost
per fill. They measure different things, so charging both is not double-charging
— but the toll must never be folded into the borrow rate, and the borrow rate
must never grow a fill term, or the two become one number nobody can decompose.

The RATES are pure — `equity_toll`, `option_toll` and `premium_notional` reach
nothing, so the arithmetic a fill is charged can be checked in isolation from
whatever wrote the row. `cumulative_toll_for` and `build_toll` read the DB, and
nothing here reaches the network at all. Machine states only; every user-facing
sentence is M06/M09's.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import logger

TOLL_METRIC = "toll"

# The machine state a caller sees when the flag is on but the book has not been
# charged anything yet — a real, measured zero, distinct from "not measured".
TOLL_NO_CHARGES_YET = "toll_no_charges"


def toll_enabled() -> bool:
    return bool(settings.training_toll_enabled)


def equity_toll(notional: float) -> float:
    """`training_toll_bps` of `notional`, floored at `training_toll_min`, in cents.

    `abs()` for `games_scoring.trade_fee`'s reason: there is no such thing as a
    free or negative cost, so a malformed caller still pays the floor.
    """
    bps = abs(float(notional)) * (float(settings.training_toll_bps) / 10_000.0)
    return round(max(bps, float(settings.training_toll_min)), 2)


def option_toll(premium_notional: float) -> float:
    """`training_toll_option_bps` of the PREMIUM notional (Σ q × multiplier ×
    premium), floored at the same minimum.

    A separate rate because retail option spreads are an order of magnitude
    wider than equity ones — the default 50 bps is already deliberately
    conservative against Bryzgalova, Pavlova & Sikorskaya (2023)'s measured
    ~8%-of-premium retail round trips, and it is labeled an estimate wherever it
    is shown. The base is premium, never the strike notional: the strike is
    collateral, and charging a spread on posted collateral would price a cash-
    secured put like a hundred shares of stock.
    """
    bps = abs(float(premium_notional)) * (
        float(settings.training_toll_option_bps) / 10_000.0
    )
    return round(max(bps, float(settings.training_toll_min)), 2)


def premium_notional(legs) -> float:
    """Σ |quantity| × multiplier × premium over a structure's legs.

    ABSOLUTE quantity, so a two-leg spread is charged on both legs rather than
    on the net: the user crosses two spreads to open it and would cross two to
    close it. Netting a long against a short would make a costless collar look
    free to trade, which is the opposite of the one thing this CR is about.
    """
    return sum(
        abs(float(leg.quantity)) * float(leg.multiplier) * float(leg.premium)
        for leg in legs
    )


def cumulative_toll_for(portfolio_id) -> float:
    """Σ `toll_charged` over every row of THIS portfolio that records a fill.

    Derived, never counted. Three consequences follow from that one choice and
    all three are the point:

      * **No backfill.** A pre-flag row carries NULL and sums to nothing, so no
        portfolio's cumulative moves because of a fill the toll never applied to.
      * **Restart is free.** `reset_portfolio()` destroys the portfolio row and
        every row below it, then recreates with a fresh UUID — the event
        `portfolio_nav_daily` calls `restart`. Scoped to `portfolio_id`, this
        sum is 0 again on a wiped book with no reset code to write.
      * **No drift.** A counter and the rows it counts are two copies of one
        fact; there is only one here.

    Scoped by `portfolio_id`, not `user_id`, which is also what keeps a game
    run's Amendment-D fees out: those land on a different portfolio row, and
    they are not tolls (`_execute_fill` writes `toll_charged` only for callers
    that pass one, and `submit_game_trade` never does).
    """
    from sqlalchemy import func, select

    from app.db import get_session
    from app.db.models import (
        SimOptionTradeRow,
        SimShortPositionRow,
        SimTradeRow,
    )

    total = 0.0
    with get_session() as session:
        for model in (SimTradeRow, SimShortPositionRow, SimOptionTradeRow):
            value = session.execute(
                select(func.sum(model.toll_charged)).where(
                    model.portfolio_id == portfolio_id
                )
            ).scalar()
            total += float(value or 0.0)
    return round(total, 2)


def build_toll_block(*, cumulative_toll: float, gross_pnl: float) -> dict:
    """The `toll` block for Portfolio Health §F, pure.

    `gross_pnl` is P&L BEFORE the toll — the book's own P&L with the cumulative
    toll added back — so `share_of_gross_pnl_pct` answers "how much of what this
    book made did the cost of trading take". The share is `None`, never 0.0,
    whenever the denominator is at or below zero: a share of a loss is not a
    percentage anybody can read, and a fabricated 0.0 there would say the toll
    cost nothing.
    """
    cumulative = round(float(cumulative_toll), 2)
    gross = round(float(gross_pnl), 2)
    share = (
        None if gross <= 0.0 else (cumulative / gross) * 100.0
    )
    return {
        "metric": TOLL_METRIC,
        "cumulative_toll": cumulative,
        "gross_pnl": gross,
        "share_of_gross_pnl_pct": share,
        "toll_bps": float(settings.training_toll_bps),
        "toll_min": float(settings.training_toll_min),
        "toll_option_bps": float(settings.training_toll_option_bps),
        "charges": None if cumulative > 0.0 else TOLL_NO_CHARGES_YET,
    }


def build_toll(*, portfolio, total_value: float | None) -> dict | None:
    """The `toll` block for one training portfolio, or `None` when the flag is
    off — an ABSENT block, not a zeroed one, because a flag-off report must be
    byte-identical to what it was before this CR (the same contract
    `passive_twin.build_passive_twin` holds).

    `gross_pnl` is reconstructed as `total_value + cumulative − starting_capital`:
    the toll has already left cash, so adding it back is what makes the
    denominator "what this book made before the cost of trading". Deposits do
    not enter, because a training book takes none — `starting_capital` and a
    `restart` are the only capital events, and a restart resets both terms
    together.

    `total_value is None` means the caller's context did not carry a valuation,
    which cannot produce an honest gross P&L. The block is omitted and the
    omission is LOGGED (CR040): a zero there would report a book that made
    nothing, and the share of it would then be a division nobody can read.
    """
    if not toll_enabled():
        return None
    if total_value is None:
        logger.warn(
            "training_toll_block_omitted",
            portfolio_id=str(getattr(portfolio, "id", None)),
            reason=(
                "the caller's context carried no total_value, so gross P&L "
                "cannot be reconstructed — the block is omitted rather than "
                "published against a fabricated zero"
            ),
        )
        return None
    cumulative = cumulative_toll_for(portfolio.id)
    return build_toll_block(
        cumulative_toll=cumulative,
        gross_pnl=float(total_value) + cumulative - float(portfolio.starting_capital),
    )
