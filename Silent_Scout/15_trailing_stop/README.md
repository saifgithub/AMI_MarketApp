# 15 — Trailing Stop (Tier 3)

**Folder:** `15_trailing_stop/`  
**Purpose:** Add a trailing stop option to existing stop orders — automatically raises stop as price moves up.  
**Scope:** Design schema extension, recompute logic in the price polling loop, Trade Ticket UI field. Deferred to Tier 3.  
**Fit:** ★★ (Tier 3 — S). Stop already exists; trailing is one more field + a recompute step in section 10's polling loop.

---

## What exists

- `SimTradeRow.stop` already exists (fixed price stop)
- Price polling infrastructure exists (section 10)
- Risk Agent can recommend stops (already in agent prompt)

---

## Design

Add `trail_pct: float | None` to `SimTradeRow` (e.g., 5.0 = 5% trailing).

In the price polling loop (section 10), compute:
```
stop = max(stop, current_price * (1 - trail_pct / 100))
```

---

## Constraints

- Trailing and fixed stop are mutually exclusive per trade
- Expressed as % (e.g., 5.0 = 5%)
- No schema changes to `SimHolding`; only `SimTrade`

---

## Scope boundaries

**DO design:** schema extension, recompute algorithm, Trade Ticket UI, Risk Agent hook.  
**DO NOT:** implement or wire up.

---

## Tier 3 rationale

Users master fixed stops first. Trailing stops are an advanced optimization deferred until Beta.

---

## Production references

- [models.py:299](../../backend/app/db/models.py) — SimTradeRow.stop
- [sim_engine.py](../../backend/app/services/sim_engine.py) — trade submission (where trail_pct would be set)
