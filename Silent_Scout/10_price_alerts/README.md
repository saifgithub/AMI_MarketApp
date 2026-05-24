# 10 — Price Alerts / Push Notifications (Tier 1)

**Folder:** `10_price_alerts/`  
**Purpose:** Design the alert feature that fires when a trade's stop or a manual threshold is crossed, with optional agent commentary.  
**Scope:** Design the alert data model, the evaluation loop (price poll vs stop threshold), the push payload shape, and the agent commentary format. Research only; no production code written here.  
**Fit:** ★★★ (Tier 1 — M). Hard dependency on A15+A16 (external). Research proceeds independently; delivery deferred until OneSignal cert lands.

---

## Why this exists

The mandate already captures stop logic per trade (`SimTradeRow.stop`). The infrastructure for push (A15 OneSignal + APNs, A16 push endpoint) is committed but blocked on external dependency (Saiful's cert provisioning). This section designs the alert feature assuming push eventually ships.

---

## Locked decisions

- **Hard dependency:** A15 (OneSignal + APNs) and A16 (push endpoint) must ship first. This section is research, not blocked by their external status.
- **Push abstraction:** OneSignal is the chosen layer (per project_plan.md).
- **Platform matrix:** FCM for Android-GMS, APNs for iOS (per `core_loop_and_features.md:192–193`).
- **Threshold types:** stop price, target price, manual above/below.
- **Agent commentary:** Risk Analyst or Concierge explains why the alert fired in the push payload (280-char slot).

---

## Agent connections

- **Risk Analyst:** when a stop fires, the push payload includes a one-sentence Risk Agent commentary explaining the move or the risk implication.
- **Concierge:** can accept "alert me when AAPL crosses $175" as a voice/text command and write the alert rule.

---

## External dependency map

```
A15 (OneSignal cert, APNs cert) ← Saiful-external
   ↓
A16 (push endpoint in backend) ← Claude
   ↓
A10 (this feature — price alerts) ← Claude, depends on A16 shipping
```

---

## Scope boundaries

**DO design:**
- Alert data model (`price_alerts` table schema)
- Evaluation loop (polling frequency, state transitions)
- Push payload shape (OneSignal JSON spec)
- Agent commentary injection format
- Fallback when push is unavailable (alert stored but not pushed)

**DO NOT implement:**
- Actually code the alert table migration
- Actually code the evaluation loop in the backend
- Actually wire OneSignal credentials (A15)
- Actually implement the push endpoint (A16)

---

## Sub-folders

- `01_constraints/` — A15/A16 references
- `02_data_model/` — `price_alerts` table design
- `03_evaluation_loop/` — polling logic and state transitions
- `04_push_payload/` — OneSignal JSON spec

---

## Production references

- [project_plan.md](../../docs/10_delivery/project_plan.md) — A15, A16 timeline
- [models.py:299](../../backend/app/db/models.py) — `SimTradeRow.stop` field
- [room.py:125](../../backend/app/api/room.py) — existing `TODO B1: fire APNs push notification here` stub
- [core_loop_and_features.md:192–193](../../docs/01_product/core_loop_and_features.md) — FCM/APNs decision

---

## Next steps (when A16 ships)

A future session will:

1. Create `price_alerts` table migration in `backend/app/db/alembic/`
2. Implement `evaluate_price_alerts()` task in `backend/app/tasks/price_alerts.py` (5-min polling loop via apscheduler)
3. Wire the alert endpoint `POST /v1/alerts/price` and `GET /v1/alerts/price`
4. Inject agent commentary into the push payload in `overlay_generator.py`
