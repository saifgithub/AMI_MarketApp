# 08 — Holding Detail Screen (Tier 1)

**Folder:** `08_holding_detail/`  
**Purpose:** Design the incremental layout for the holding detail screen — the hub that hosts candlestick chart, per-ticker news feed, earnings/dividend chip, and stop/target visualization.  
**Scope:** Layout and zone architecture. **DELIVERED:** UX restructure (Holding→Ticker rename, watching card variant, actions-row redesign), wireframe implemented in holding_detail_screen.dart.  
**Fit:** ★★★ (Tier 1 — M). Highest unlock-per-effort: without a host screen, none of the Tier 1 features have a home.

---

## What exists today (AT:R40)

- Screen: `mobile/lib/screens/sim/holding_detail_screen.dart`
- Route: `/sim/{ticker}` (IA screen 08)
- Current state: renders `_ComingSoonCard` (lines 95, 373) with placeholder text `holdingDetailComingSoonBody` describing "Candlestick chart · per-ticker news · earnings calendar"
- Quick-actions row already exists (trade, ask analyst, convene room, close position)
- Trade history list already rendered below

The `_ComingSoonCard` is the explicit build target for this feature.

---

## Locked decisions

- **Route:** stays `/sim/{ticker}` — no new route.
- **Screen in IA:** screen 08 stays unchanged.
- **Candlestick chart:** already in development in production (not designed here).
- **No schema changes:** this is layout work only — all data already flows end-to-end.
- **Zone collapsing:** each zone gracefully disappears when data is absent (no "coming soon" fallback).

---

## Agent connections

- **Market Analyst:** primary analytical tenant (already wired in `_QuickActions._ask()`).
- **News Analyst:** gains real data feed via section 09 (news strip).
- **Risk Agent:** reads stop/target from the holding detail to flag mandate breaches and suggest trailing stop (section 15).

---

## Hard constraints

- No new route.
- No changes to `SimHoldingRow` schema.
- Each zone is independently additive — chart ships first, news next, earnings last. Do not gate one zone behind another.

---

## What this track does NOT do

- Implement the candlestick chart (→ production in-dev).
- Implement the news strip (→ section 09).
- Implement the earnings chip (→ section 11).
- Implement the stop/target chip (→ section 15).

This track specifies WHERE each of these lands and HOW they stack. The implementation work is in those sections.

---

## Zone dependencies

See `01_layout/zone_wireframe.md` for the full vertical scroll order and zone toggle logic.

---

## Production references

- [holding_detail_screen.dart](../../mobile/lib/screens/sim/holding_detail_screen.dart) — lines 95, 373 (`_ComingSoonCard`)
- [screen_inventory.md](../../docs/05_design/screen_inventory.md) — screen 08 definition
- [app_en.arb](../../mobile/lib/l10n/app_en.arb) — key `holdingDetailComingSoonBody` (to be updated after layout ships)
