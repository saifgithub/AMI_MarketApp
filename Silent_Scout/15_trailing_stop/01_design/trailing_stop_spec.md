# Trailing stop specification

## Schema extension

```python
class SimTrade(Base):
    # ... existing fields ...
    
    stop = Column(Float, nullable=True)  # fixed stop or current trailing stop
    trail_pct = Column(Float, nullable=True)  # trailing % (e.g., 5.0 for 5%)
    
    # Constraint: stop XOR trail_pct (not both, not neither)
```

---

## Recompute algorithm

In the section 10 price polling loop:

```python
def update_trailing_stops(trades: List[SimTrade], quotes: Dict[str, Quote]):
    """Recompute trailing stops based on current prices."""
    for trade in trades:
        if trade.trail_pct is None:
            continue  # Fixed stop only
        
        current_price = quotes[trade.ticker].price
        
        # Trailing stop: never goes down, only up
        new_stop = current_price * (1 - trade.trail_pct / 100)
        
        if trade.stop is None or new_stop > trade.stop:
            trade.stop = new_stop
            logger.info(f"Trade {trade.id} trailing stop updated to ${new_stop:.2f}")
```

---

## Trade Ticket UI field

In `mobile/lib/screens/sim/trade_ticket_screen.dart`, add a toggle:

```dart
// Existing: fixed stop input
TextField(label: "Stop price (fixed)", ...)

// NEW: trailing stop checkbox
CheckboxListTile(
  title: Text("Use trailing stop?"),
  value: useTrailingStop,
  onChanged: (v) => setState(() => useTrailingStop = v ?? false),
),

// NEW: trailing % input (visible only if trailing is checked)
if (useTrailingStop)
  TextField(
    label: "Trailing %",
    hint: "e.g., 5 for 5%",
    keyboardType: TextInputType.number,
    controller: trailPercentController,
  ),
```

---

## Submission logic

```python
def submit_trade(trade_req: TradeRequest, user: User):
    """Handle trade submission with trailing stop logic."""
    
    # Parse request
    stop = trade_req.stop if not trade_req.use_trailing else None
    trail_pct = trade_req.trail_pct if trade_req.use_trailing else None
    
    if stop is None and trail_pct is None:
        raise ValueError("Must specify either fixed or trailing stop")
    
    if stop is not None and trail_pct is not None:
        raise ValueError("Cannot use both fixed and trailing stop")
    
    # Create trade
    trade = SimTrade(
        user_id=user.id,
        ticker=trade_req.ticker,
        quantity=trade_req.quantity,
        entry_price=current_price,
        stop=stop,
        trail_pct=trail_pct,
        # ... other fields ...
    )
    
    db.session.add(trade)
    db.session.commit()
```

---

## Risk Agent hook

In `overlay_generator.py`, add a recommendation:

```python
def _risk_block(self):
    """Risk analysis including trailing stop recommendations."""
    
    # Recommend trailing stop if position has moved significantly
    holding = self.portfolio.holdings[self.ticker]
    if holding.unrealised_pnl > holding.avg_cost * 0.10:  # Up 10%
        self.context['suggestion'] = (
            "Your position is up 10%. Consider locking in gains "
            "with a trailing stop (5% recommended)."
        )
```

---

## Edge cases

1. **Price drops below trailing:** stop is breached → trade closes (same as fixed stop)
2. **Price rises sharply then falls:** trailing stop rises with it, only moving up
3. **New all-time high:** trailing stop adjusts up to new high − trail_pct%

---

## No changes to SimHolding

Trailing stops are per-trade, not per-holding. A holding can have multiple trades with different trail_pct values.
