# CR025 — Watchlist day-change % badge

**Status:** proposed · **Session:** AT:R55 · **Date:** 2026-07-12
**Source:** migrated from `Silent_Scout/12_watchlist_badge/` as part of closing and
deprecating Silent_Scout (Saiful — "its utility has come to an end"). The design
below was already complete and paste-ready; filing it as a proper CR rather than
losing it when the workspace closes.

## What

Watchlist rows show price but no daily %-move badge. `backend/app/api/watchlist.py`
hardcodes `day_change_pct=None` at both call sites (lines 58, 86) that construct
`WatchlistEntryWithQuote` — confirmed still true as of 2026-07-12. The file's own
docstring says this was deliberate: "Day-change% is omitted for now — the configured
market_data provider doesn't surface the previous close yet... When that lands, drop
it into the schema with no client change." That precondition is already met:
`market_data.py`'s `Quote` object already carries `change_pct`
(`YahooQuoteProvider`, populated at `market_data.py:298-303`) — `watchlist.py` just
needs to read it instead of discarding it.

## Why

Cheapest fix in the entire former-Silent_Scout backlog — display-only, no schema
change, no new dependency, data already flows end-to-end. Was previously mismarked
"✅ DELIVERED (AT:R41)" in the Silent_Scout doc despite never having shipped; that
false status is why nobody picked it up. Filing for real now.

## Design (ported from the original implementation brief, verified still accurate)

**Backend** — `backend/app/api/watchlist.py`, both `day_change_pct=None` call sites
(lines 58, 86): change to `day_change_pct=quote.change_pct`. (The provider call should
be `provider.quote(ticker)` rather than a price-only shim, if that's not already what
feeds `quote` at these call sites — confirm at implementation time.)

**Mobile** — `_WatchlistRow` in `mobile/lib/screens/sim/portfolio_screen.dart`
(confirmed current location, not `watchlist_screen.dart` as the original brief
guessed): after the price `Text`, add a conditional badge —
`+1.2%` / `-0.8%` (sign always shown, 1 decimal), green (`AmiColors.hexGreen`) if
≥ 0, red (`AmiColors.hexRed`) if negative, 8px left padding, only rendered when
`dayChangePct != null`.

**Testing:** `pytest backend/tests/unit/test_watchlist.py -k test_get_watchlist -v`
should assert a non-null float, not `None`. Manual: Watchlist tab shows colored %
badges; pull-to-refresh updates them; no layout overflow at the "−99.9%" width
extreme.

**Rollback:** both changes are isolated (display-only) — revert `day_change_pct=None`
backend-side and drop the conditional widget mobile-side. Zero ripple risk.

## Scope

**In:** the two backend field wire-ups; the Flutter badge widget.
**Out:** anything beyond daily %-move (e.g., a sparkline, multi-day trend) — future
CR if wanted.

## Acceptance

- `GET /v1/watchlist` returns real `day_change_pct` floats, not `None`, for tickers
  with a live quote.
- Watchlist rows render the badge, correctly colored, correctly signed.
- Existing `test_watchlist.py` coverage updated to assert the real value.
- No layout regression on either test device (iPhone 13, Galaxy Note Fan / A17).
