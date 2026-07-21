# M04 — Fundamentals unit conversions

**Origin:** DEF016-era · **Status:** done (pure conversions migrated to `trading_math/valuation.py`)

## What
Normalizing raw yfinance fundamentals into the units the agents cite — so a Fundamentals Analyst
states "revenue +18%", "net cash $4,200M", "FCF yield 3.1%" instead of raw decimals/absolutes it
would otherwise mangle.

## Formula
- `ratio_to_pct(value, decimals)`: `round(value × 100)` — rev_growth, profit_margin (whole %);
  fcf_yield via `fcf_yield_pct(fcf, mktcap)` (1 dp).
- `net_cash_millions(cash, debt)`: `round((cash − debt) / 1_000_000)` (→ $M); `net_position_phrase`
  labels a negative as **net debt**, not "net cash $-42000M".
- `dividend_yield_pct(raw)`: pass-through round — yfinance 1.5.1 returns `dividendYield` **already as
  a percent** (verified live: KO 2.58, T 5.06, AAPL 0.33; the ×100 fraction is
  `trailingAnnualDividendYield`). Not a ×100. One documented place to flip if yfinance changes.
- P/S, EV/EBITDA, PEG (now `trailingPegRatio`, legacy `pegRatio` fallback), analyst target/rating —
  pre-formatted.
- Synthetic low/high/support/breakout as fixed multiples of price when the 52-week range is absent —
  now flagged `week52_range_live` so the 1-on-1 block only claims "52-week range" for the real values.

## Source data
`yfinance.Ticker(t).info`.

## Consumed by
Fundamentals Analyst (Room profile block + 1-on-1 `build_live_data_block`).

## Computed in
`app/trading_math/valuation.py` (pure conversions) — orchestrated (yfinance I/O, NaN-guarded `_num`,
key selection) by `app/services/fundamentals.py::fetch_live_fundamentals`.

## Guard test
`tests/unit/test_trading_math.py` — the pure conversions (`ratio_to_pct`, `fcf_yield_pct`,
`net_cash_millions`/`net_position_phrase`, `dividend_yield_pct`). `tests/unit/test_fundamentals.py` —
orchestration: NaN-as-absent, key naming (`profit_margin`), 52-week-range labeling, missing-key omission.

## Changelog
- Seeded into the ledger 2026-07-20 (CR046, AT:R62) to record where this math lives.
- 2026-07-21 (CR046, AT:R62): pure conversions **migrated** into `trading_math/valuation.py`;
  `fundamentals.py` delegates. Same audit closed three data-honesty issues found in the sweep:
  - **D-b:** `profitMargins` was keyed `fcf_margin` and rendered "FCF margin" in the Room — a metric
    it is not (FCF margin ≠ profit margin). Renamed `profit_margin` end-to-end; label fixed.
  - **D-c:** the synthetic ±5% price band no longer claims "52-week range" in the 1-on-1 block
    (labelled a placeholder via `week52_range_live`); the Room template's "Last week's range" →
    "52-week range" (the field holds 52-week data).
  - **D-d:** `dividend_yield` verified **correct** on the pinned yfinance 1.5.1 (already a percent) —
    no value change; the convention is now documented in one place. `pegRatio` → `trailingPegRatio`
    (legacy fallback) so the PEG line stops silently disappearing.
