# M01 — Technical indicators

**Origin:** DEF052 (AT:R58) · **Status:** done

## What
Real RSI, moving-average trend read, volume tone, and recent-range support/breakout for a ticker —
so the Market Analyst states measured technicals instead of fabricating them (pre-DEF052 they were
100% invented by the LLM or an rng).

## Formula
- **RSI(14) — Cutler's:** simple average of gains/losses over 14 periods; `100 − 100/(1+RS)`,
  `RS = avg_gain/avg_loss`; 100.0 when no losses. **Not Wilder's** (see CR046 D1 / `library_survey.md`).
- **SMA(20), SMA(50):** mean of the last N closes.
- **Trend:** "trading" when price and both SMAs align (all up or all down), else "consolidating".
- **Volume tone:** 5-day avg vs 20-day avg, ±10% bands → above / below / in-line.
- **Support / breakout:** `min(lows[-50:])` / `max(highs[-50:])`.

## Source data
yfinance OHLCV via `MarketDataProvider.history(ticker, "3m")` — no new external feed.

## Consumed by
Market Analyst (Room profile block + 1-on-1 `build_technicals_context_block`).

## Computed in
`app/trading_math/indicators.py` (`rsi`, `rsi_tone`, `sma`) — pure. Orchestrated (I/O, NaN-guard,
trend/volume/range) by `app/services/technicals.py::compute_technicals`, which re-exports the three
pure functions under their original private names.

## Guard test
`tests/unit/test_trading_math.py` (pure functions, incl. a Cutler-not-Wilder assertion),
`tests/unit/test_technicals.py` (orchestration, NaN guards, 50-day lookback).

## Changelog
- 2026-07-13 (DEF052): created — real indicators replace fabricated ones.
- 2026-07-20 (CR046, AT:R62): `rsi`/`rsi_tone`/`sma` migrated verbatim into `trading_math/indicators.py`;
  `technicals.py` now delegates. Byte-identical. Decision D1: hand-rolled, kept Cutler's.
