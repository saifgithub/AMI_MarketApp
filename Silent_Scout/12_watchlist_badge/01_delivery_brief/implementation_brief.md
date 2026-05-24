# Implementation brief — Watchlist % move badge

This is a paste-ready session brief for a single-focus implementation session. Total time: ~10 minutes.

---

## Change 1: Backend wire-up (watchlist.py)

**File:** `backend/app/api/watchlist.py`

**Change at line 58:**

```python
# BEFORE (current):
entry=e, price=price, day_change_pct=None, price_source=source,

# AFTER:
entry=e, price=price, day_change_pct=quote.change_pct, price_source=source,
```

**Context:** This call constructs `WatchlistEntryWithQuote`. The `quote` object (returned by the provider) already has `change_pct`. Instead of hardcoding `None`, pass the real value.

---

**Change at line 86:**

Same fix — find the second occurrence of `day_change_pct=None` in the same file and replace with `day_change_pct=quote.change_pct`.

---

## Change 2: Flutter rendering

**File:** `mobile/lib/screens/watchlist/watchlist_screen.dart` (or wherever `_WatchlistRow` is defined)

**Location:** Find `_WatchlistRow.build()` method. Locate the `Row` or `Column` that renders `priceText` (the price display like "$150.25").

**Add after `priceText`:**

```dart
// Existing price text:
Text(
  '${widget.entry.price.toStringAsFixed(2)}',
  style: AmiTypography.bodyMediumBold.copyWith(
    color: AmiColors.textPrimary,
  ),
),

// NEW — add this widget:
if (widget.entry.dayChangePct != null)
  Padding(
    padding: const EdgeInsets.only(left: 8.0),
    child: Text(
      '${widget.entry.dayChangePct! > 0 ? '+' : ''}${widget.entry.dayChangePct!.toStringAsFixed(1)}%',
      style: AmiTypography.bodySmall.copyWith(
        color: widget.entry.dayChangePct! >= 0
            ? AmiColors.hexGreen
            : AmiColors.hexRed,
      ),
    ),
  ),
```

**Explanation:**
- Check if `dayChangePct` is not null
- Format as `+1.2%` or `-0.8%` (sign always shown, 1 decimal place)
- Color: green if positive/zero, red if negative
- Place it to the right of the price (8px padding)

---

## Testing

1. **Backend:** Run `pytest backend/tests/unit/test_watchlist.py -k test_get_watchlist -v`. Verify `day_change_pct` is a non-zero float, not `None`.

2. **Mobile (iPhone):**
   - Open the Watchlist tab
   - Verify each ticker shows its daily move in green (+1.2%) or red (-0.8%)
   - Tap one watchlist entry to open the holding detail — should render normally
   - Force-refresh (pull down) — move badges update

---

## Verification

- No backend errors on `/v1/watchlist` endpoint
- No type errors in Flutter (dayChangePct is `float | None` → check for null)
- Watchlist screen renders without layout overflow (badge width is bounded at "−99.9%")
- Both iPhone 13 and any other target device render the badge legibly

---

## Rollback plan

If anything breaks:
- Backend: revert to `day_change_pct=None` in both lines
- Flutter: remove the `if (widget.entry.dayChangePct != null)` block

Both changes are isolated — zero ripple risk.

---

## Notes

- This is the **fastest shippable feature** of all Tier 2 items. Data already flows end-to-end; you're just wiring it.
- No new dependencies, no new endpoints, no new schemas.
- The badge is display-only — no business logic changes.
