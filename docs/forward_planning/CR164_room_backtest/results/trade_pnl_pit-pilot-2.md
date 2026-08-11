# CR164 — followed-the-trade P&L, batch `pit-pilot-2`

Report date 2026-08-11. Long-only; fills and exits walked over daily OHLC bars from `price_history_daily`. Same-bar stop+target counted as a STOP (marked ⚠) — daily bars cannot order two intraday touches, and assuming the favourable one would flatter the result. A gap through a level fills at the open, not the level. Positions whose stated horizon outruns the data are OPEN and marked to market, never closed early and scored as a win.

Approved trades with complete PM levels: **13**

### Entry policy: `limit`

- **Realized (stop / target / horizon): 12 trades · P&L $+1,478 on $100,000 (+1.48% of book) · win rate 4/12 (33%) · mean per-trade +3.58%**
- Still open (marked to market, UNREALIZED): none
- Never filled: 1 (entry limit never traded)

**Combined book P&L: $+1,478 (+1.48% of a $100,000 notional)** — realized + unrealized, 12 closed and 0 open.

| ticker | as_of | size | entry | fill | exit | outcome | return | P&L |
|---|---|---|---|---|---|---|---|---|
| M | 2025-07-04 | 3.0% | 12.06 | 12.01 | 20.41 | target | +70.01% | $+2,100 |
| MO | 2025-12-12 | 3.0% | 55.91 | 55.91 | 61.17 | time_stop | +9.42% | $+282 |
| BAC | 2025-08-01 | 3.0% | 44.69 | 44.69 | 48.26 | target | +7.99% | $+240 |
| STX | 2026-01-02 | 3.0% | 286.83 | 286.83 | 307.37 | target | +7.16% | $+215 |
| ABT | 2026-05-29 | 1.5% | 84.99 | — | — | never_filled | +0.00% | $+0 |
| GIS | 2025-10-17 | 3.0% | 46.13 | 46.13 | 45.26 | stop | -1.89% | $-57 |
| MCHP | 2026-03-20 | 2.5% | 62.66 | 62.66 | 61.00 | stop | -2.65% | $-66 |
| XPEV | 2025-03-14 | 1.5% | 23.73 | 23.34 | 22.31 | stop | -4.41% | $-66 |
| TMO | 2025-09-05 | 3.0% | 490.81 | 486.00 | 461.36 | stop | -5.07% | $-152 |
| STZ | 2025-03-21 | 3.0% | 170.44 | 170.44 | 160.21 | stop | -6.00% | $-180 |
| KHC | 2025-07-11 | 3.0% | 25.43 | 25.43 | 23.84 | stop | -6.25% | $-188 |
| CLSK | 2026-01-23 | 2.0% | 13.71 | 13.50 | 12.00 | stop | -11.11% | $-222 |
| CRM | 2025-04-25 | 3.0% | 265.18 | 265.18 | 227.35 | stop | -14.27% | $-428 |

### Entry policy: `market`

- **Realized (stop / target / horizon): 13 trades · P&L $+1,259 on $100,000 (+1.26% of book) · win rate 5/13 (38%) · mean per-trade +2.68%**
- Still open (marked to market, UNREALIZED): none
- Never filled: 0 (entry limit never traded)

**Combined book P&L: $+1,259 (+1.26% of a $100,000 notional)** — realized + unrealized, 13 closed and 0 open.

| ticker | as_of | size | entry | fill | exit | outcome | return | P&L |
|---|---|---|---|---|---|---|---|---|
| M | 2025-07-04 | 3.0% | 12.06 | 12.01 | 20.41 | target | +70.01% | $+2,100 |
| MO | 2025-12-12 | 3.0% | 55.91 | 55.92 | 61.17 | time_stop | +9.40% | $+282 |
| BAC | 2025-08-01 | 3.0% | 44.69 | 44.98 | 48.26 | target | +7.29% | $+219 |
| STX | 2026-01-02 | 3.0% | 286.83 | 294.25 | 307.37 | target | +4.46% | $+134 |
| ABT | 2026-05-29 | 1.5% | 84.99 | 85.17 | 87.87 | time_stop | +3.17% | $+48 |
| GIS | 2025-10-17 | 3.0% | 46.13 | 46.19 | 45.26 | stop | -2.02% | $-61 |
| TMO | 2025-09-05 | 3.0% | 490.81 | 486.00 | 461.36 | stop | -5.07% | $-152 |
| MCHP | 2026-03-20 | 2.5% | 62.66 | 64.61 | 61.00 | stop | -5.58% | $-140 |
| STZ | 2025-03-21 | 3.0% | 170.44 | 171.48 | 160.21 | stop | -6.57% | $-197 |
| KHC | 2025-07-11 | 3.0% | 25.43 | 25.55 | 23.84 | stop | -6.68% | $-200 |
| XPEV | 2025-03-14 | 1.5% | 23.73 | 24.27 | 22.31 | stop | -8.08% | $-121 |
| CLSK | 2026-01-23 | 2.0% | 13.71 | 13.50 | 12.00 | stop | -11.11% | $-222 |
| CRM | 2025-04-25 | 3.0% | 265.18 | 265.48 | 227.35 | stop | -14.36% | $-431 |

## Why the horizon matters

Stated horizons span **19–1095 days** (median 201). 6 of 13 exceed a year, so their theses are not yet gradeable — the four-week bucket returns in `backtest_report.py` answer name selection, not whether these trades worked.

