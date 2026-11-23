# CR282 — Bursa Malaysia equities

Status: in progress (scoping). Filed 2026-11-23 by the CR267 coordinator.

Saiful, 2026-11-23: *"File the bursa scoping CR and work on it. That's the next priority."*

The decision log places Bursa Malaysia in Phase 2 ("US equities only at MVP. GCC/Tadawul + Bursa Malaysia in Phase 2"). No Bursa work existed before this CR. Scope document follows in this folder once the research lands.

## Rulings (Saiful, 2026-11-23)

1. **Currency: a separate MYR book.** Each user gets a second simulated portfolio in ringgit for Bursa stocks. No FX feed; each book has one calendar, one benchmark (FBM KLCI vs S&P) and one fee schedule.
2. **Phase 1: trade + Room, honest gaps.** MYR book, Bursa ticker list, calendar and sessions, board lots and fees, FBM KLCI benchmark, SC Shariah list, and the Room on `.KL` stocks, with desks that have no Malaysian data saying "not available for this market". Games and Malaysian filings/macro feeds are phase 2.
3. **Beta gate: build behind a flag.** Built and tested on Alpha; off in Beta builds until counsel answers the CMSA 2007 investment-advice question (added to S6).
