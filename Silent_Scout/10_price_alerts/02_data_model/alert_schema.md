# Data model: price alerts schema

## Table: price_alerts

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class PriceAlert(Base):
    __tablename__ = "price_alerts"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    ticker = Column(String(10), nullable=False)  # e.g. "AAPL"
    
    # Alert configuration
    threshold_type = Column(
        String(20),
        nullable=False
        # Options: "stop", "target", "manual_above", "manual_below"
    )
    threshold_price = Column(Float, nullable=False)
    
    # Alert state
    status = Column(
        String(20),
        default="active"
        # Options: "active", "fired", "cancelled"
    )
    
    # Trade reference (optional — if alert is tied to a specific position)
    trade_ref = Column(Integer, ForeignKey("sim_trades.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    fired_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    
    # Agent metadata
    agent_commentary = Column(String(280), nullable=True)  # 280-char Risk Agent comment
    
    # Relations
    user = relationship("User", back_populates="price_alerts")
    trade = relationship("SimTrade", back_populates="alerts")


# Update SimTrade to have reverse relation
class SimTrade(Base):
    # ... existing fields ...
    alerts = relationship("PriceAlert", back_populates="trade")
```

---

## State transitions

```
┌────────────────────────────────────────┐
│ ACTIVE (waiting for threshold breach)  │
└────────────────────────────────────────┘
    │
    ├─→ [price crosses threshold] ──→ FIRED
    │
    └─→ [user cancels] ──→ CANCELLED
```

Once fired or cancelled, alert is read-only (audit trail).

---

## Query patterns

**Find active alerts for a user:**

```python
session.query(PriceAlert).filter_by(user_id=user_id, status="active").all()
```

**Find alerts for a ticker:**

```python
session.query(PriceAlert).filter_by(ticker=ticker, status="active").all()
```

**Update alert to fired:**

```python
alert.status = "fired"
alert.fired_at = datetime.utcnow()
session.commit()
# Then fire push notification
```

---

## Threshold types

| Type | Semantics | Example | Use case |
|---|---|---|---|
| `stop` | Price falls BELOW threshold | Stop at $120 | Risk management (built-in to trade) |
| `target` | Price rises ABOVE threshold | Target $160 | Profit-taking (built-in to trade) |
| `manual_above` | Price rises ABOVE threshold | Alert when AAPL > $150 | Watchlist price watch |
| `manual_below` | Price falls BELOW threshold | Alert when AAPL < $140 | Watchlist price watch |

---

## Foreign key integrity

- `trade_ref` is nullable — alerts can exist without a trade (manual watchlist alerts)
- If a trade is closed, its linked alert is NOT deleted (audit trail); status is left as-is

---

## Indexing strategy

```python
# In the migration file:
Index("ix_price_alerts_user_status", "user_id", "status"),  # Common query
Index("ix_price_alerts_ticker_status", "ticker", "status"),  # Evaluation loop
Index("ix_price_alerts_fired_at", "fired_at"),  # Historical queries
```

---

## TTL / archival (future)

Alerts older than 30 days can be archived to a separate table (`price_alerts_archive`). Not required at Alpha, but design the schema to support this transition.
