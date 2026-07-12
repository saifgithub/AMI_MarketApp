# CR029 — Cost-basis lots / FIFO realised-P&L display

**Status:** proposed · **Session:** AT:R55 · **Date:** 2026-07-12
**Source:** migrated from `Silent_Scout/14_cost_basis_lots/` as part of closing and
deprecating Silent_Scout.

## What

Show per-lot cost basis and FIFO-computed realised P&L on the ticker/holding detail
screen — an educational feature (teaching tax-lot accounting), not a trading
mechanic. Tier 3, deferred by product sequencing (users should understand simple cost
basis before per-lot detail is useful), not by technical blocker.

## Why

All source data already exists in `sim_trades` (`entry_price`, `quantity`, `side`,
`closed_price`, `realised_pnl`) — this is a pure computation + display feature, no
schema change. Filed to preserve the design; deferral rationale still holds and isn't
time-sensitive to GTM.

## Design (ported)

### FIFO lot algorithm
```python
def compute_lots_fifo(holding: SimHolding, trades: List[SimTrade]) -> List[Lot]:
    # Walk trades chronologically. Each "buy" opens a new lot.
    # Each "sell" closes existing lots oldest-first (FIFO), splitting a lot
    # across multiple sells if needed, accumulating realised P&L per lot.
```
`Lot`: `entry_trade_id, entry_date, entry_price, quantity_open, quantity_closed,
realised_pl` (+ a computed `unrealised_pl` from current price). Sell quantity draws
down the oldest open lot(s) first; a sell can close part of one lot and spill into
the next if the size crosses a lot boundary.

### Display (holding detail screen)
Per-lot card: entry date, quantity open, avg cost, realised P&L (from any partial
closes), unrealised P&L (open quantity × (current price − entry price)).

## Scope

**In:** FIFO lot computation, per-lot display section on the holding/ticker detail
screen.
**Out:** LIFO variant (explicitly a "future option for tax planning" in the original
design — not needed at Tier 3); any change to `SimTrade`/`SimHolding` schema (none
needed).

## Acceptance

- Correctly reflects Saiful's product-sequencing call — do not build ahead of user
  demand; revisit post-Alpha per the original deferral trigger ("users request it").
- When built: FIFO lot math verified against a multi-trade, partial-close test case
  (buy 100 @ $150, buy 50 @ $155, sell 60 @ $160 → lot 1 partially closed, correct
  realised P&L split).
