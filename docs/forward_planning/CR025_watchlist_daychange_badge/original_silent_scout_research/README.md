# 12 — Watchlist % Move Badge (Tier 2)

**Folder:** `12_watchlist_badge/`  
**Purpose:** Display the daily % price change badge on watchlist tiles.  
**Scope:** Identify the exact two-line backend change and the Flutter widget change needed. Produce a paste-ready delivery brief.  
**Fit:** ★★ (Tier 2 — S). Lowest effort of all features. The schema, provider, and model are already aligned; only two wire-up points are missing.

---

## What exists today (AT:R40)

- **Schema:** `WatchlistEntryWithQuote` has `day_change_pct: float | None` (line in `watchlist.py:58,86`)
- **Provider:** `YahooQuoteProvider` returns `Quote` with `change_pct: float` (already populated)
- **Display:** `_WatchlistRow` in Flutter renders the price but NOT the `dayChangePct` field

## Status

**✅ DELIVERED** (AT:R41)

The two-line backend fix and Flutter widget changes were implemented:

- Backend wired `quote.change_pct` into `day_change_pct` (watchlist.py:58,86)
- Flutter renders daily % move badge with green/red coloring
- Watchlist row redesigned with secondary actions (primary + secondary pattern)

---

## Locked decisions

- **Color convention:** `AmiColors.hexGreen` for +% move, `AmiColors.hexRed` for -%
- **Format:** `+1.2%` / `-0.8%` (always sign, always 1 decimal place)
- **Position:** to the right of price text on the watchlist tile
- **No push required:** display-only, no notifications

---

## Hard constraints

- No schema changes
- No new endpoint
- No new provider changes

---

## Next steps (Tier 2 implementation)

A future session will apply the changes in `01_delivery_brief/implementation_brief.md` directly — it's a 10-minute fix.

---

## Why this matters

Watchlist users can't assess momentum without seeing daily move. The data is flowing end-to-end; we just need to wire it up.
