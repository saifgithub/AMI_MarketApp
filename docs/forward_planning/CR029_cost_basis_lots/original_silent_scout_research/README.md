# 14 — Cost-Basis Lots / Weighted-Avg Display (Tier 3)

**Folder:** `14_cost_basis_lots/`  
**Purpose:** Display per-lot cost basis and FIFO/LIFO-computed realised P&L on the holding detail screen.  
**Scope:** Design the lot aggregation algorithm and display format. Educational use case.  
**Fit:** ★★ (Tier 3 — S). Teaching FIFO/LIFO tax treatment is an Academy focus; deferred until users request it.

---

## What exists

- `SimHolding` has `avg_cost` (weighted average)
- `SimTrade` has `entry_price`, `quantity`, `side`, `closed_price`, `realised_pnl`
- Trade history is already displayed on holding detail

---

## Scope

**DO design:** FIFO lot algorithm, per-lot P&L computation, display on holding detail.  
**DO NOT:** implement or wire up.

---

## Why Tier 3

Users need to understand cost basis before this matters. Post-Alpha, once we've taught users the basics, this educational feature becomes valuable.

---

## Key insight

All data already exists in `sim_trades` records. No schema change needed. This is a pure display + education feature.

---

## Production references

- [models.py:287–310](../../backend/app/db/models.py) — SimTradeRow structure
- [holding_detail_screen.dart](../../mobile/lib/screens/sim/holding_detail_screen.dart) — trade history section (where lots would appear)

---

## Next steps

After this section is researched, a future session will implement the lot aggregation and display.
