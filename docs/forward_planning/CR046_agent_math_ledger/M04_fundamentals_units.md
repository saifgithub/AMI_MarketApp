# M04 — Fundamentals unit conversions

**Origin:** DEF016-era · **Status:** done (not yet migrated to the library)

## What
Normalizing raw yfinance fundamentals into the units the agents cite — so a Fundamentals Analyst
states "revenue +18%", "net cash $4,200M", "FCF yield 3.1%" instead of raw decimals/absolutes it
would otherwise mangle.

## Formula
- `rev_growth`, `profit_margin` (→ fcf_margin): `round(value × 100)` (decimal → %).
- `net_cash`: `round((totalCash − totalDebt) / 1_000_000)` (→ $M).
- `fcf_yield`: `round(freeCashflow / marketCap × 100, 1)` (→ %).
- P/S, EV/EBITDA, PEG, dividend yield, 52-week range, analyst target/rating — pre-formatted.
- Synthetic low/high/support/breakout as fixed multiples of price when the 52-week range is absent.

## Source data
`yfinance.Ticker(t).info`.

## Consumed by
Fundamentals Analyst (Room profile block + 1-on-1 `build_live_data_block`).

## Computed in
`app/services/fundamentals.py::fetch_live_fundamentals` (with inner NaN-guarded `_num`).

## Guard test
`tests/unit/test_fundamentals.py` — NaN-as-absent, unit normalization (rev_growth ×100), multiple
extraction, missing-key omission.

## Changelog
- Seeded into the ledger 2026-07-20 (CR046, AT:R62) to record where this math lives.
- **Backlog:** migrate the pure unit-conversion helpers into `trading_math/` (a `units`/`fundamentals`
  module) so they're reusable and testable in isolation, same as M01/M02.
