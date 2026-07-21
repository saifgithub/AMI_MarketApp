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
  `trailingAnnualDividendYield`). Not a ×100. One documented place to flip if yfinance changes. This
  is only correct on the **1.x convention** — 0.2.x returned a decimal fraction, so the pin is
  `yfinance>=1.0` (not `>=0.2.50`) and a degrade-loudly startup check shouts if a build resolves an
  older major (see changelog).
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
- 2026-07-21 (CR046, AT:R62): **pin + convention guard.** The verification pass flagged that
  `dividend_yield_pct`'s correctness depends on the 1.x convention while the pin was `yfinance>=0.2.50`
  — a 0.2.x wheel would silently return a fraction → yield ~100× too low. Tightened `pyproject.toml`
  to `yfinance>=1.0` (both installed versions satisfy it: Mac 1.3.0, Alpha 1.5.1) with an inline
  comment tying the floor to this convention, and added a degrade-loudly check
  (`fundamentals._warn_if_yfinance_convention_stale`, decision in `_yfinance_major`) that logs
  `yfinance_below_dividend_convention_floor` once per process if the installed major < 1. Guard:
  `tests/unit/test_fundamentals.py::test_yfinance_major_parses_the_convention_floor` (+ shouts-once /
  silent-on-current). Not a new dependency — a pin tightening, so no lean-stack sign-off needed.
