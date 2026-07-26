"""CR029 — per-lot cost-basis / FIFO realised-P&L reconstruction.

Reconstructs a ticker's tax-lot picture *at read time* from the existing
`sim_trades` order history — no new schema, no migration, no change to the
sell path. The educational feature (teaching tax-lot accounting on the
holding-detail screen) needs, per open buy lot: entry date/price, how much of
that lot is still open, how much has been closed and what it realised, and the
unrealised P&L on the open remainder. See
docs/forward_planning/CR029_cost_basis_lots/.

This module is a thin *reconstruction* over the audited FIFO primitive: the
lot-matching math itself lives in `trading_math.cost_basis.fifo_sell`
(CR029-MATH, already integrated + audited). We only walk the order stream and
apply that primitive — we do not re-derive FIFO here.

Reconciling the two ways a sim position realises P&L (engine reality vs. the
CR029 design doc's clean "buys open, sells close" picture):

    1. An explicit `side='sell'` order (`SimEngine.submit`) draws down the
       open buy lots oldest-first at the sell fill price. This is the classic
       FIFO case and the one `fifo_sell` handles — we thread each sell through
       the running open-lot queue.

    2. A *buy* row can self-close via stop/target (`evaluate_outcomes`) or a
       manual close (`manual_close`): the buy row itself gets `closed_price` +
       `realised_pnl` stamped on it and flips to `won`/`lost`/`closed`. Such a
       row never emits a separate `sell` row, so we treat it as a lot that
       opened at `entry_price` and is now *fully* closed, carrying the row's
       already-recorded `realised_pnl`. It does NOT enter the sell-order FIFO
       queue — doing so would double-count shares the engine already accounted
       for at close.

Because self-closed buys and `sell` orders are disjoint records (a self-close
never produces a sell row), the two mechanisms compose without double-counting.

Known drift (DEF110, out of CR029 scope): `evaluate_outcomes` stamps realised
P&L on a stop/target-hit buy row but does NOT reduce the `sim_holdings` row, so
a holding's aggregate `quantity` can disagree with the sum of open lots
reconstructed here. Saiful ruled a stop/target hit SHOULD close the position
(DEF110) — which confirms treating won/lost buys as *fully closed* here is
correct; the fix belongs in the sim engine, not this module. This module
reflects the *trade ledger* faithfully.

Pure — no DB, no I/O beyond a degrade-loud log on malformed input. The DB read
+ current-price fetch live in `SimEngine.holding_lots`, which delegates here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import NamedTuple

from app.core.logging import logger
from app.trading_math import fifo_sell

_EPS = 1e-9


class Lot(NamedTuple):
    """One buy lot's reconstructed cost-basis picture — one per-lot card."""

    entry_trade_id: str
    entry_date: str  # ISO 8601 (the buy's opened_at)
    entry_price: float
    quantity: float  # original buy quantity
    quantity_open: float  # still held from this lot
    quantity_closed: float  # sold / stopped out of this lot
    realised_pnl: float  # from the closed portion, 2 dp
    unrealised_pnl: float | None  # open_qty × (current − entry); None if price unknown
    status: str  # "open" | "partially_closed" | "closed"


@dataclass
class _LotAcc:
    """Mutable accumulator used while walking the order stream."""

    entry_trade_id: str
    entry_date: object  # datetime (or anything with isoformat())
    entry_price: float
    quantity: float
    quantity_open: float
    quantity_closed: float
    realised_pnl: float
    self_closed: bool = False


def _side_str(side: object) -> str:
    """Normalise a Side enum / raw string to a lowercase 'buy' | 'sell'."""
    val = getattr(side, "value", side)
    return str(val).strip().lower()


def _is_self_closed_buy(trade: object) -> bool:
    """A buy row that closed itself via stop/target/manual (won/lost/closed)."""
    return str(getattr(trade, "status", "open")).lower() in {"won", "lost", "closed"}


def _apply_sell(lots: list[_LotAcc], sell_qty: float, sell_price: float) -> None:
    """Draw `sell_qty` at `sell_price` from the open buy lots, FIFO."""
    open_refs = [
        lot for lot in lots if lot.quantity_open > _EPS and not lot.self_closed
    ]
    snapshot = [(lot.quantity_open, lot.entry_price) for lot in open_refs]
    result = fifo_sell(snapshot, sell_qty, sell_price)
    if result is None:
        # Malformed input (non-positive qty/price, or a corrupt lot) — degrade
        # loudly (CR040) rather than emit a bogus lot table.
        logger.warn(
            "cost_basis_fifo_sell_rejected",
            sell_qty=sell_qty,
            sell_price=sell_price,
            open_lots=len(open_refs),
        )
        return
    # fifo_sell draws strictly front-to-back and appends exactly one close per
    # lot it touches, in queue order — so closes[i] maps to open_refs[i].
    for i, close in enumerate(result.closes):
        lot = open_refs[i]
        lot.quantity_open = round(lot.quantity_open - close.quantity_closed, 6)
        lot.quantity_closed = round(lot.quantity_closed + close.quantity_closed, 6)
        lot.realised_pnl = round(lot.realised_pnl + close.realised_pnl, 2)
    if result.quantity_unmatched > _EPS:
        # A sell that outran the open lots. The engine's submit() guards
        # against overselling a holding, so this only fires on ledger
        # inconsistency — surface it, don't swallow it.
        logger.warn(
            "cost_basis_oversell",
            sell_qty=sell_qty,
            unmatched=result.quantity_unmatched,
        )


def _freeze(acc: _LotAcc, current_price: float | None) -> Lot:
    entry_date = acc.entry_date
    iso = entry_date.isoformat() if hasattr(entry_date, "isoformat") else str(entry_date)

    if current_price is not None and acc.quantity_open > _EPS:
        unrealised: float | None = round(
            (float(current_price) - acc.entry_price) * acc.quantity_open, 2
        )
    else:
        unrealised = None

    if acc.quantity_open <= _EPS:
        lot_status = "closed"
    elif acc.quantity_closed > _EPS:
        lot_status = "partially_closed"
    else:
        lot_status = "open"

    return Lot(
        entry_trade_id=acc.entry_trade_id,
        entry_date=iso,
        entry_price=acc.entry_price,
        quantity=round(acc.quantity, 6),
        quantity_open=round(max(acc.quantity_open, 0.0), 6),
        quantity_closed=round(acc.quantity_closed, 6),
        realised_pnl=round(acc.realised_pnl, 2),
        unrealised_pnl=unrealised,
        status=lot_status,
    )


def compute_lots_fifo(
    trades: Iterable[object],
    current_price: float | None = None,
) -> list[Lot]:
    """Reconstruct FIFO cost-basis lots for one ticker from its trade history.

    `trades` are order records (anything exposing `id`, `side`, `quantity`,
    `entry_price`, `opened_at`, `status`, `realised_pnl` — e.g. sim_engine's
    `SimTrade`), for a single ticker. Ordering is re-derived here (by
    `opened_at`, then `id` for a stable tie-break), so callers need not
    pre-sort. `current_price` drives the per-lot unrealised P&L on the open
    remainder; pass None to omit it.

    Returns one `Lot` per buy, in buy order — open, partially closed, and
    fully closed alike (a fully-closed lot still carries its realised P&L, an
    educational data point). See the module docstring for how `sell` orders
    and self-closed buys are reconciled.
    """
    ordered = sorted(
        trades, key=lambda t: (getattr(t, "opened_at", None), str(getattr(t, "id", "")))
    )

    lots: list[_LotAcc] = []
    for t in ordered:
        side = _side_str(getattr(t, "side", ""))
        if side == "buy":
            qty = float(t.quantity)
            acc = _LotAcc(
                entry_trade_id=str(getattr(t, "id", "")),
                entry_date=getattr(t, "opened_at", None),
                entry_price=float(t.entry_price),
                quantity=qty,
                quantity_open=qty,
                quantity_closed=0.0,
                realised_pnl=0.0,
            )
            if _is_self_closed_buy(t):
                acc.quantity_open = 0.0
                acc.quantity_closed = qty
                acc.realised_pnl = round(float(getattr(t, "realised_pnl", 0.0) or 0.0), 2)
                acc.self_closed = True
            lots.append(acc)
        elif side == "sell":
            _apply_sell(lots, float(t.quantity), float(t.entry_price))
        else:
            logger.warn("cost_basis_unknown_side", side=side, trade_id=str(getattr(t, "id", "")))

    return [_freeze(acc, current_price) for acc in lots]
