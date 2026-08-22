"""CR172 §3/§6 — opening an option structure in the TRAINING lane.

The twin of `sim_shorts.py`, and a separate module for the same reason: the
cash model is the design. What leaves `current_cash` at open is

    net_cost + collateral

— the debit paid (or minus the credit received) plus the collateral the short
side has to pre-fund. Both halves matter and both are persisted, because
`option_lifecycle.settlement_effect` releases the collateral it was told was
posted, and a figure re-derived at settlement from a rounded price is how a
portfolio drifts by cents (CR171's rule, unchanged).

**The identity everything here holds to:** opening a structure at its own mid
does not change `total_value`. Cash falls by `net_cost + collateral`; the
portfolio's option term rises by `collateral + Σ q × multiplier × premium`,
and `Σ q × multiplier × premium` IS `net_cost`. That is why the collateral is
carried on the leg rather than netted away somewhere — see
`trading_math.option_strategy.option_leg_value`.

**Collateral is attributed to the short legs by their own liability, not split
evenly.** M17 computes collateral over the whole structure jointly (a vertical
posts `width − credit`, not the sum of its legs), so there is no per-leg figure
to read off. Settlement, however, releases per leg. The attribution used here
weights each short leg by the settlement liability it actually carries —
`strike × multiplier × |contracts|` — which is exact for every single-short
structure we generate and a real weight, not an invented one, for the
multi-short structures that come later. The structure-level figure on
`sim_option_trades` stays authoritative; the leg figures always sum to it.

**Nothing here decides.** `check_option_open` is the floor and it runs before
this module is reached; this module refuses only on affordability, which the
floor does not know about.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from app.db.models import SimOptionLegRow, SimOptionTradeRow, SimPortfolioRow
from app.schemas.trade import OptionLeg
from app.services.option_instruments import format_occ_symbol
from app.trading_math.option_strategy import (
    StrategyLeg,
    shares_needed_to_cover_calls,
    strategy_metrics,
)


class InsufficientCashError(Exception):
    """Raised when the structure costs more than the portfolio holds."""

    def __init__(self, needed: float, available: float) -> None:
        super().__init__(
            f"opening this structure needs ${needed:,.2f} and the portfolio "
            f"holds ${available:,.2f}"
        )
        self.needed = needed
        self.available = available


def cash_required_for(net_cost: float, collateral: float | None) -> float:
    """What leaves `current_cash` at open: the debit plus the collateral.

    A credit structure returns a NEGATIVE debit, so a cash-secured put posting
    $9,000 against $450 of premium received needs $8,550 — the premium is real
    and it is simply not spendable, which is `sim_shorts.cash_required_for`'s
    rule in the options shape.
    """
    return round(float(net_cost) + float(collateral or 0.0), 2)


def _liability(leg: StrategyLeg) -> float:
    """The settlement liability one SHORT leg carries; 0 for a long leg.

    A short put can be assigned and must buy the shares at the strike; a short
    call delivers shares it either holds (covered — the shares are the
    collateral, not cash) or does not (uncovered — refused by D3 before this
    module is reached). So the weight is the strike notional on short puts,
    and zero elsewhere.
    """
    if leg.quantity >= 0:
        return 0.0
    if leg.right != "put":
        return 0.0
    return abs(leg.quantity) * leg.multiplier * leg.strike


def allocate_collateral(
    legs: Sequence[StrategyLeg], collateral: float
) -> list[float]:
    """Split the structure's collateral across its legs, sum preserved.

    Weighted by each short leg's own settlement liability. When no leg carries
    one — a covered call, where shares are the collateral — the split is over
    the short legs equally, because *something* posted it and the alternative
    (silently dropping it) would release nothing at settlement and leave the
    cash stranded. The last leg absorbs the rounding so the parts sum exactly
    to the whole: a per-leg round that loses a cent loses it permanently, at
    settlement, from a user's balance.
    """
    total = round(float(collateral or 0.0), 2)
    if total <= 0:
        return [0.0 for _ in legs]
    weights = [_liability(leg) for leg in legs]
    if sum(weights) <= 0:
        weights = [1.0 if leg.quantity < 0 else 0.0 for leg in legs]
    if sum(weights) <= 0:  # collateral with no short leg at all — impossible
        weights = [1.0 for _ in legs]
    share = sum(weights)
    parts = [round(total * w / share, 2) for w in weights]
    last = max(i for i, w in enumerate(weights) if w > 0)
    parts[last] = round(parts[last] + (total - sum(parts)), 2)
    return parts


def open_structure(
    session,
    *,
    portfolio_row: SimPortfolioRow,
    user_id: UUID,
    underlying: str,
    strategy_name: str,
    legs: Sequence[StrategyLeg],
    expiry: date,
    shares_held: float = 0.0,
    verdict_ref: UUID | None = None,
    now: datetime | None = None,
) -> tuple[SimOptionTradeRow, list[SimOptionLegRow]]:
    """Write the structure, move the cash. Raises rather than half-writing.

    `ValueError` when the structure cannot be costed or a leg cannot be
    encoded as an OCC symbol — both mean the caller handed us something the
    floor should already have refused, and writing a partial position would
    leave the user holding legs that no close path can find.
    """
    now = now or datetime.now(timezone.utc)
    leg_list = list(legs)
    metrics = strategy_metrics(leg_list, shares_held=max(0.0, float(shares_held or 0.0)))
    if metrics is None:
        raise ValueError("structure could not be costed — refusing to open it")
    if metrics.collateral_required is None:
        raise ValueError(
            "structure carries an uncovered short call — the floor refuses "
            "this before it reaches the ledger"
        )

    needed = cash_required_for(metrics.net_cost, metrics.collateral_required)
    available = float(portfolio_row.current_cash)
    if needed > available + 1e-6:
        raise InsufficientCashError(needed, available)

    symbols = [
        format_occ_symbol(underlying, expiry, leg.right, leg.strike)
        for leg in leg_list
    ]
    if any(sym is None for sym in symbols):
        raise ValueError("a leg could not be encoded as an OCC symbol")

    strategy_id = uuid4()
    per_leg_collateral = allocate_collateral(leg_list, metrics.collateral_required)

    trade_row = SimOptionTradeRow(
        id=uuid4(),
        user_id=user_id,
        portfolio_id=portfolio_row.id,
        strategy_id=strategy_id,
        underlying=underlying.upper().strip(),
        strategy_name=strategy_name,
        net_cost_at_open=metrics.net_cost,
        collateral_posted=metrics.collateral_required,
        verdict_ref=verdict_ref,
        opened_at=now,
        status="open",
    )
    session.add(trade_row)

    rows: list[SimOptionLegRow] = []
    for leg, symbol, leg_collateral in zip(
        leg_list, symbols, per_leg_collateral, strict=True
    ):
        row = SimOptionLegRow(
            id=uuid4(),
            user_id=user_id,
            portfolio_id=portfolio_row.id,
            occ_symbol=symbol,
            underlying=underlying.upper().strip(),
            right=leg.right,
            strike=leg.strike,
            expiry=expiry,
            quantity=leg.quantity,
            avg_premium=leg.premium,
            multiplier=leg.multiplier,
            collateral_posted=leg_collateral,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            opened_at=now,
            state="open",
        )
        session.add(row)
        rows.append(row)

    portfolio_row.current_cash = round(available - needed, 2)
    session.flush()
    return trade_row, rows


def open_legs_for_portfolio(session, portfolio_id: UUID) -> list[OptionLeg]:
    """Every still-open option leg, oldest first — the portfolio's own view."""
    rows = session.execute(
        select(SimOptionLegRow)
        .where(
            SimOptionLegRow.portfolio_id == portfolio_id,
            SimOptionLegRow.state == "open",
        )
        .order_by(SimOptionLegRow.opened_at.asc())
    ).scalars().all()
    return [
        OptionLeg(
            id=r.id,
            occ_symbol=r.occ_symbol,
            underlying=r.underlying,
            right=r.right,
            strike=float(r.strike),
            expiry=r.expiry,
            quantity=float(r.quantity),
            avg_premium=float(r.avg_premium),
            multiplier=float(r.multiplier),
            collateral_posted=float(r.collateral_posted),
            strategy_id=r.strategy_id,
            strategy_name=r.strategy_name,
            opened_at=r.opened_at,
        )
        for r in rows
    ]


def open_call_legs_on(session, portfolio_id: UUID, underlying: str) -> list[StrategyLeg]:
    """Every still-open CALL leg on one underlying, across every structure.

    The portfolio-level view `strategy_metrics` deliberately does not have:
    it costs one structure at a time, which is right for a card and wrong for
    asking whether the book is covered. See `uncovered_call_shares`.
    """
    symbol = underlying.upper().strip()
    rows = session.execute(
        select(SimOptionLegRow).where(
            SimOptionLegRow.portfolio_id == portfolio_id,
            SimOptionLegRow.state == "open",
            SimOptionLegRow.right == "call",
            SimOptionLegRow.underlying == symbol,
        )
    ).scalars().all()
    return [
        StrategyLeg(
            right="call",
            strike=float(r.strike),
            quantity=float(r.quantity),
            premium=float(r.avg_premium),
            multiplier=float(r.multiplier),
            expiry=r.expiry.isoformat(),
        )
        for r in rows
    ]


def locked_call_cover_shares(session, portfolio_id: UUID, underlying: str) -> float:
    """Shares on this underlying already spoken for by open short calls.

    DEF356 — the portfolio-level figure, and the reason it has to exist:
    `strategy_metrics` costs ONE structure at a time, which is right for a
    card and wrong for asking whether the book is covered. Two "covered" calls
    written against one lot of 100 shares are each individually covered while
    the book is short 100, and no structure-level check can see it.

    Two callers, one rule:

      * **at open** — `shares_held` passed to `check_option_open` must be the
        holding MINUS this, or the second covered call is measured against
        shares the first already claimed;
      * **in the sweep** — this MINUS the holding is what the book is short by
        after a sale, a stop-out or an assignment took the cover away.

    The cover rule itself is `shares_needed_to_cover_calls`, the same function
    `_collateral` uses for the per-structure figure, so the two cannot
    disagree about what "covered" means (DEF098). Held shares are deliberately
    NOT summed here — `SimEngine._held_quantity` owns that, because it alone
    handles the mid-transaction case where a holding is deleted but still on
    `p_row.holdings` until the session expires it.
    """
    return shares_needed_to_cover_calls(
        open_call_legs_on(session, portfolio_id, underlying)
    )
