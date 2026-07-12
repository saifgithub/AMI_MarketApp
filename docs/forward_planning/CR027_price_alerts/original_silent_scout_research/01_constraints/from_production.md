# Constraints from production

## A15/A16 timeline (project_plan.md)

**A15:** OneSignal + APNs cert provisioning  
Status: `⏳ blocked external` (Saiful's cert work)

**A16:** Push endpoint implementation  
Status: `◯ unstarted` (depends on A15)

This feature (A10 in backlog) is unblocked but cannot ship until A16 exists.

---

## Stop field exists (models.py:299)

```python
class SimTradeRow(Base):
    __tablename__ = "sim_trades"
    
    stop: float | None = Column(Float, nullable=True)  # stop-loss price
    # ... other fields ...
```

The stop field already exists. Alert evaluation is just comparing `current_price < stop`.

---

## Existing push TODO (room.py:125)

```python
def _run_room_consensus(user_id, ...):
    # ... consensus logic ...
    
    # TODO B1: fire APNs push notification here when consensus is ready
    # notification = {
    #     "title": "Consensus: BUY AAPL",
    #     "body": "12 agents agree...",
    #     "deepLink": "/sim/AAPL"
    # }
```

This stub shows where push infrastructure will live. Price alerts follow the same pattern.

---

## FCM/APNs decision (core_loop_and_features.md:192–193)

> **Push notifications (iOS + Android)**
> - iOS: APNs (Apple Push Notification service)
> - Android-GMS: FCM (Firebase Cloud Messaging)
> - Abstraction: OneSignal as the unified layer

This decision is locked; no platform-specific code in the backend.

---

## Safety floor: mandate-aware alerts

Alerts must respect the user's mandate. If the mandate forbids shorting, don't alert on target prices that exceed mandate bounds. This is gated by `safety_floor.py` compliance checks.
