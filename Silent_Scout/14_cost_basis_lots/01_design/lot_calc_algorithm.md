# Lot calculation algorithm

## FIFO lot aggregation

Given a sequence of trades on a holding:

```
Trade 1: +100 shares @ $150 (entry)
Trade 2: +50 shares @ $155 (entry)
Trade 3: -60 shares @ $160 (exit)
```

FIFO sequencing:
- Exit uses first-in shares: 60 of the 100 from Trade 1
- Remaining: 40 shares from Trade 1 @ $150, 50 shares from Trade 2 @ $155

---

## Per-lot realised P&L

For Trade 3 (exit at $160):
- Lot 1: 60 shares × ($160 − $150) = $600 realised gain
- (Remaining 40 shares in Lot 1 stay open)

---

## Display format on holding detail

```
Cost Basis Analysis (FIFO)

Lot 1 (Trade entry: May 1)
  Quantity: 40 shares open
  Avg Cost: $150
  Realised P&L: $600 (from 60 @ $160)
  Unrealised: +$400 (40 × ($160 − $150))

Lot 2 (Trade entry: May 3)
  Quantity: 50 shares open
  Avg Cost: $155
  Realised P&L: $0
  Unrealised: +$250 (50 × ($160 − $155))
```

---

## Algorithm implementation

```python
def compute_lots_fifo(holding: SimHolding, trades: List[SimTrade]) -> List[Lot]:
    """Compute FIFO lots for a holding."""
    
    lots = []
    open_quantity = 0
    
    for trade in sorted(trades, key=lambda t: t.created_at):  # chronological
        if trade.side == "buy":
            # Add a new lot
            lots.append(Lot(
                entry_trade_id=trade.id,
                entry_date=trade.created_at,
                entry_price=trade.entry_price,
                quantity_open=trade.quantity,
            ))
            open_quantity += trade.quantity
        
        elif trade.side == "sell":
            # Use FIFO to close lots
            remaining = trade.quantity
            for lot in lots:
                if remaining <= 0:
                    break
                
                quantity_closed = min(remaining, lot.quantity_open)
                cost_basis = quantity_closed * lot.entry_price
                proceeds = quantity_closed * trade.closed_price
                realised_pl = proceeds - cost_basis
                
                lot.quantity_closed += quantity_closed
                lot.quantity_open -= quantity_closed
                lot.realised_pl += realised_pl
                
                remaining -= quantity_closed
            
            open_quantity -= trade.quantity
    
    return lots
```

---

## Lot data structure

```python
class Lot(BaseModel):
    entry_trade_id: int
    entry_date: datetime
    entry_price: float
    
    quantity_open: float
    quantity_closed: float
    
    realised_pl: float  # sum of all realised P&L from closures
    
    @property
    def unrealised_pl(self) -> float:
        # Computed dynamically based on current price
        pass
```

---

## Notes

- LIFO variant (sell most recent purchases first) is a future option for tax planning
- At Tier 3, FIFO only
- No changes to `SimTrade` schema; pure computation from existing data
