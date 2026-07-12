# CR030 — Dividend fields for the earnings chip

**Status:** proposed · **Session:** AT:R55 · **Date:** 2026-07-12
**Source:** migrated from `Silent_Scout/11_earnings_dividends/` as part of closing and
deprecating Silent_Scout.

## What

The earnings half of this feature already shipped (`GET /v1/sim/earnings/{ticker}`,
6h cache, `_EarningsPill` on the ticker detail screen — AT:R42). The **dividend half
never shipped** — the original Silent_Scout doc claimed "✅ DELIVERED" for both, which
overstated scope. Confirmed as of 2026-07-12: the live endpoint returns only
`earnings_date`, `quarter`, `eps_estimate` — no `exDividendDate`/`dividendRate`
anywhere in backend or the pill widget.

## Why

Small, well-researched gap-closer on top of an already-shipped feature — the yfinance
field survey is complete (reliability percentages, edge cases, null-handling all
already worked out below); this is a targeted addition, not new research.

## Design (ported)

### Fields (yfinance `Ticker.info`)
`exDividendDate` (unix ts, ~70% coverage, null for non-dividend payers) and
`dividendRate` (float, annual per-share, `0.0` if none). Reuse the same ~5-min cache
TTL pattern as `fetch_live_fundamentals()`.

### Null handling
No `exDividendDate` → not a dividend payer → hide the dividend sub-chip entirely
(don't render "N/A"). `dividendRate == 0.0` with an `exDividendDate` present (rare —
suspended dividend) → show the date without a rate.

### API shape
Extend the existing earnings response rather than a new endpoint:
```json
{
  "ticker": "AAPL", "earnings_date": "...", "quarter": "...", "eps_estimate": 2.04,
  "ex_dividend_date": "2026-09-19T00:00:00Z",
  "dividend_rate": 0.96
}
```

### UI
Extend `_EarningsPill` (or add an adjacent small chip) with "Ex-div: Sep 19 · $0.96"
when present; hidden when the ticker doesn't pay a dividend. Same hide-on-empty
pattern already used for the earnings pill and news section.

## Scope

**In:** the two new fields on the existing earnings endpoint + chip.
**Out:** dividend yield computation (`dividendRate / current_price`) — optional,
easy to add later, not required for the display.

## Acceptance

- `GET /v1/sim/earnings/{ticker}` includes `ex_dividend_date`/`dividend_rate` when
  yfinance has them, omits/nulls cleanly otherwise.
- Chip hides correctly for non-dividend-paying tickers (e.g., TSLA at time of
  writing); shows correctly for a known dividend payer (e.g., AAPL).
- No regression to the already-shipped earnings-only display.
