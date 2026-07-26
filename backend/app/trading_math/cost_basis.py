"""FIFO cost-basis lot matching — which buy lots a sell closes, and what it realises.

CR029 (Tier 3, deferred): the per-lot cost-basis / realised-P&L display on the
holding detail screen needs to know, for a given sell, which of the earlier buys
it draws down and in what order. Tax-lot accounting convention is FIFO — the
oldest open shares are sold first, splitting a lot across the sell boundary when
the sell size doesn't line up with a single lot's remaining quantity. This module
is the CR029-MATH sub-lane's "pure FIFO engine" only: no DB, no `sim.submit`
wiring, no schema change (see docs/forward_planning/CR029_cost_basis_lots/). A
later sub-lane threads a ticker's real buy history through here.

Deliberate edge-case rules (asked for by the CR029-MATH lane brief):
    * a sell against an empty lot queue is not an error — zero lots to close,
      the whole `sell_quantity` comes back as `quantity_unmatched`.
    * `sell_quantity` greater than total open quantity ("oversell") is likewise
      not an error: FIFO-close everything available and report the shortfall in
      `quantity_unmatched` rather than raising or silently capping the sell.
      Degrade loudly (CR040) — the shortfall is data the caller must look at and
      decide what to do with (e.g. the future sim sell-path treats a nonzero
      `quantity_unmatched` as "reject the order"), not something this module
      swallows or guesses about.
    * malformed input — a non-positive `sell_quantity`/`sell_price`, or any lot
      with non-positive quantity/price — returns None. Same "unusable input, no
      figure" contract the rest of this package uses (e.g. `bond_price`,
      `drawdown_contribution`): refusing beats emitting a bogus number.
    * fractional shares are accepted, not rejected — `SimTrade.quantity`
      (schemas/trade.py) is already a float, so a fractional lot split is a
      first-class case here, not a later extension.

Conventions:
    * quantities round to 6 dp on the way out (headroom for fractional-share
      brokers while keeping binary-float noise off a displayed figure); money
      (`realised_pnl`) rounds to 2 dp, same as the rest of this package.
    * a lot fully consumed by the sell (quantity rounds to 0) is dropped from
      `open_lots` — the caller never sees a zero-quantity lot card.
    * `realised_pnl_total` is the sum of the *rounded* per-lot `realised_pnl`
      values (re-rounded once to clean float noise), not a round of the raw
      total — so a per-lot display and its total row always foot exactly, the
      way a user re-adding the rows by hand would expect.

Pure — floats/tuples in, NamedTuples out. No I/O, no pydantic.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

_EPS = 1e-9


class OpenLot(NamedTuple):
    """A buy lot's remaining unmatched shares — one per-lot display card.

    Field order matches the `(quantity, price)` pairs `fifo_sell` takes as
    input, so a caller threading multiple sells through the same queue can pass
    a previous call's `open_lots` straight back in as the next call's `open_lots`.
    """

    quantity_open: float
    entry_price: float


class LotClose(NamedTuple):
    """The slice of one open lot a sell consumed, and what it realised."""

    entry_price: float
    quantity_closed: float
    realised_pnl: float  # (sell_price − entry_price) × quantity_closed, 2 dp


class FifoSellResult(NamedTuple):
    """Everything a single sell does to a FIFO queue of open lots."""

    closes: list[LotClose]  # one entry per lot touched, oldest first
    realised_pnl_total: float  # Σ closes[i].realised_pnl, 2 dp
    open_lots: list[OpenLot]  # remaining queue after the sell, oldest first
    quantity_unmatched: float  # > 0 only when the sell outran the open queue


def fifo_sell(
    open_lots: Sequence[tuple[float, float]],
    sell_quantity: float,
    sell_price: float,
) -> FifoSellResult | None:
    """Match one sell against `open_lots` first-in-first-out.

    `open_lots`: `(quantity, price)` pairs, oldest first — either a ticker's
    original buy history or the `open_lots` a previous `fifo_sell` call
    returned (thread multiple sells through in sequence, one call per sell).
    `sell_quantity` is drawn from the front of the queue; a sell that doesn't
    line up with a lot boundary splits that lot, closing part of it and moving
    on to the next-oldest lot.

    Returns None for malformed input (see module docstring). A `sell_quantity`
    larger than the total open quantity is NOT malformed: everything available
    is closed and the gap is reported in `quantity_unmatched` rather than
    raised or silently truncated away.
    """
    if sell_quantity <= 0 or sell_price <= 0:
        return None
    for quantity, price in open_lots:
        if quantity <= 0 or price <= 0:
            return None

    remaining = sell_quantity
    closes: list[LotClose] = []
    survivors: list[OpenLot] = []
    pnl_total = 0.0

    for quantity, price in open_lots:
        if remaining <= _EPS:
            survivors.append(OpenLot(quantity_open=round(quantity, 6), entry_price=price))
            continue
        take = min(quantity, remaining)
        pnl = round((sell_price - price) * take, 2)
        pnl_total += pnl
        closes.append(
            LotClose(entry_price=price, quantity_closed=round(take, 6), realised_pnl=pnl)
        )
        remaining -= take
        leftover = quantity - take
        if leftover > _EPS:
            survivors.append(
                OpenLot(quantity_open=round(leftover, 6), entry_price=price)
            )

    quantity_unmatched = round(remaining, 6) if remaining > _EPS else 0.0

    return FifoSellResult(
        closes=closes,
        realised_pnl_total=round(pnl_total, 2),
        open_lots=survivors,
        quantity_unmatched=quantity_unmatched,
    )
