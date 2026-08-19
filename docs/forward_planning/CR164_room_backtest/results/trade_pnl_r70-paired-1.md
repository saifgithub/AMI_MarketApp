# CR164 — followed-the-trade P&L, batch `r70-paired-1`

Report date 2026-08-19. Long-only; fills and exits walked over daily OHLC bars from `price_history_daily`. Same-bar stop+target counted as a STOP (marked ⚠) — daily bars cannot order two intraday touches, and assuming the favourable one would flatter the result. A gap through a level fills at the open, not the level. Positions whose stated horizon outruns the data are OPEN and marked to market, never closed early and scored as a win.

Approved trades with complete PM levels: **9**

### Entry policy: `limit`

- **Realized (stop / target / horizon): 9 trades · P&L $+4,436 on $100,000 (+4.44% of book) · win rate 5/9 (56%) · mean per-trade +16.18%**
- Still open (marked to market, UNREALIZED): none
- Never filled: 0 (entry limit never traded)

**Combined book P&L: $+4,436 (+4.44% of a $100,000 notional)** — realized + unrealized, 9 closed and 0 open.

| ticker | as_of | size | entry | fill | exit | outcome | return | P&L |
|---|---|---|---|---|---|---|---|---|
| KSS | 2025-07-18 | 3.0% | 9.29 | 9.29 | 19.15 | target | +106.18% | $+3,185 |
| M | 2025-07-04 | 3.0% | 12.06 | 12.01 | 14.87 | target | +23.84% | $+715 |
| AVGO | 2025-08-29 | 3.0% | 295.23 | 287.24 | 353.19 | target | +22.96% | $+689 |
| KHC | 2025-07-11 | 3.0% | 25.43 | 25.43 | 27.08 | target | +6.50% | $+195 |
| MA | 2025-07-11 | 3.0% | 546.77 | 546.77 | 550.26 | time_stop | +0.64% | $+19 |
| BKNG | 2026-02-13 | 3.0% | 164.83 | 164.46 | 162.09 | stop | -1.44% | $-43 |
| DKNG | 2025-07-18 | 3.0% | 43.72 | 43.72 | 42.57 | stop | -2.63% | $-79 |
| MO | 2025-12-12 | 1.5% | 55.91 | 55.91 | 53.46 | stop | -4.38% | $-66 |
| GIS | 2025-10-17 | 3.0% | 46.13 | 46.13 | 43.36 | stop | -6.00% | $-180 |

### Entry policy: `market`

- **Realized (stop / target / horizon): 9 trades · P&L $+4,348 on $100,000 (+4.35% of book) · win rate 5/9 (56%) · mean per-trade +15.86%**
- Still open (marked to market, UNREALIZED): none
- Never filled: 0 (entry limit never traded)

**Combined book P&L: $+4,348 (+4.35% of a $100,000 notional)** — realized + unrealized, 9 closed and 0 open.

| ticker | as_of | size | entry | fill | exit | outcome | return | P&L |
|---|---|---|---|---|---|---|---|---|
| KSS | 2025-07-18 | 3.0% | 9.29 | 9.39 | 19.15 | target | +104.03% | $+3,121 |
| M | 2025-07-04 | 3.0% | 12.06 | 12.01 | 14.87 | target | +23.84% | $+715 |
| AVGO | 2025-08-29 | 3.0% | 295.23 | 287.24 | 353.19 | target | +22.96% | $+689 |
| KHC | 2025-07-11 | 3.0% | 25.43 | 25.55 | 27.08 | target | +6.02% | $+180 |
| MA | 2025-07-11 | 3.0% | 546.77 | 547.09 | 550.26 | time_stop | +0.58% | $+17 |
| BKNG | 2026-02-13 | 3.0% | 164.83 | 164.46 | 162.09 | stop | -1.44% | $-43 |
| DKNG | 2025-07-18 | 3.0% | 43.72 | 43.76 | 42.57 | stop | -2.72% | $-82 |
| MO | 2025-12-12 | 1.5% | 55.91 | 55.92 | 53.46 | stop | -4.39% | $-66 |
| GIS | 2025-10-17 | 3.0% | 46.13 | 46.19 | 43.36 | stop | -6.14% | $-184 |

## Why the horizon matters

Stated horizons span **33–180 days** (median 90). 0 of 9 exceed a year, so their theses are not yet gradeable — the four-week bucket returns in `backtest_report.py` answer name selection, not whether these trades worked.

