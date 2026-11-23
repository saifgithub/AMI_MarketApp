# CR282 — Bursa Malaysia equities

Status: in progress (scoping). Filed 2026-11-23 by the CR267 coordinator.

Saiful, 2026-11-23: *"File the bursa scoping CR and work on it. That's the next priority."*

The decision log places Bursa Malaysia in Phase 2 ("US equities only at MVP. GCC/Tadawul + Bursa Malaysia in Phase 2"). No Bursa work existed before this CR. Scope document follows in this folder once the research lands.

## Rulings (Saiful, 2026-11-23)

1. **Currency: a separate MYR book.** Each user gets a second simulated portfolio in ringgit for Bursa stocks. No FX feed; each book has one calendar, one benchmark (FBM KLCI vs S&P) and one fee schedule.
2. **Phase 1: trade + Room, honest gaps.** MYR book, Bursa ticker list, calendar and sessions, board lots and fees, FBM KLCI benchmark, SC Shariah list, and the Room on `.KL` stocks, with desks that have no Malaysian data saying "not available for this market". Games and Malaysian filings/macro feeds are phase 2.
3. **Beta gate: build behind a flag.** Built and tested on Alpha; off in Beta builds until counsel answers the CMSA 2007 investment-advice question (added to S6).

## What already exists

1. Mobile `Bourse { us, sa, my }` enum with default `.KL` tickers (`mobile/lib/services/yahoo_finance_service.dart`), pinned to `us` in `ticker_tape_provider.dart:20`.
2. Lesson 004 (US markets vs Bursa) in en/ms/ar; `ms` locale; `Asia/Kuala_Lumpur` already used by daily challenges; the output guard already recognises RM/MYR.
3. Schema hooks: `ticker_reference.exchange`, `sharia_universe_snapshots.standard`, `game_fields.benchmark_ticker`, `users.locale/timezone`.

## Market facts (research 2026-11-23; [V] = from primary text, [S] = search snippet of a Bursa page, [U] = unverified)

1. **Sessions (MYT, Mon–Fri) [S]:** pre-open 08:30, continuous 09:00–12:30; pre-open 14:00, continuous 14:30–16:45, pre-close 16:45, closing auction 16:50, trading-at-last 16:50–17:00.
2. **Board lot 100 [S]**; 1–99 units trade on a separate odd-lot market. The simulator enforces multiples of 100.
3. **Tick sizes [S, circular rr2_110411]:** < RM1.00: 0.005 · RM1.00–9.99: 0.01 · RM10.00–99.98: 0.02 · ≥ RM100: 0.10.
4. **Price limits [V, SC/Bursa 2021 notice]:** static ±30% of reference price (30 sen below RM1.00); FBM KLCI circuit breaker at −10/−15/−20%.
5. **Settlement:** T+2 [secondary]. Not modelled in phase 1 (the US book does not model settlement either).
6. **Short selling:** only Approved Securities (RSS, Rule 8.22(5)); intraday short selling open to all, suspended per stock on a 15% fall. **Phase 1: no shorts on Bursa.**
7. **Holidays:** 2026 closures confirmed from Bursa notices (1 Jan; 2 Feb; 17–18 Feb; 20–23 Mar; 27 May; 1–2 Jun; 25 Aug; 31 Aug; 16 Sep) plus gazetted days not yet confirmed (1 May; 17 Jun; 9 Nov Deepavali observed; 25 Dec). 2027 derived from Cabinet circular GI/15/2026 (Hari Raya, Qurban, Deepavali "subject to change"). Lunar dates mean a **data table, refreshed from Bursa's annual notice**, never a formula.
8. **Costs a Malaysian retail trade carries:** brokerage ~0.10% min RM8 [U, broker norm]; clearing 0.03% cap RM1,000 [U]; stamp duty 0.10% cap RM1,000 (remission order to 12 Jul 2028) [secondary]; SST exempt on ordinary-share brokerage [U].
9. **Benchmark:** FBM KLCI, Yahoo `^KLSE` (index candles only).

## Data sources per desk (phase 1 = honest gaps)

| Desk / input | US today | Bursa phase 1 | Phase 2 |
|---|---|---|---|
| Prices, candles, technicals (Market Analyst) | yfinance | yfinance `.KL`, 15-min delayed (Yahoo help, ICE-sourced) | same |
| Fundamentals | yfinance + SEC XBRL | yfinance `.info`/statements only; XBRL lanes say "not available for this market" | Bursa annual reports / paid feed |
| Filings, 8-K, insider (News, Fundamentals) | SEC EDGAR | not available | Bursa announcements (no free API; FinancialReports.eu paid) |
| News | yfinance + Alpha Vantage | yfinance; Malay Mail money RSS (Bernama) | Star / Edge feeds |
| Macro (Macro & Events) | BLS (flagged), FOMC dates | BNM OPR (2.75%, MPC 5 Nov 2026), OpenDOSM CPI/GDP API (CC BY 4.0, 4 req/min) | full BNM Open API |
| Social (Flow & Positioning) | Reddit (Adanos) | thin; returns none, already degrades | — |
| Risk-free rate / ERP (WACC) | ^TNX, US ERP | MGS 10-year + Malaysian ERP (lane E) | — |
| Shariah screen | S&P 500 via SPUS | SC Malaysia SAC list (`standard="SC_MALAYSIA"`): twice yearly, last Friday of May and November; 29 May 2026 list = 886 securities; next due Fri 27 Nov 2026 | — |

## Open questions (not blocking the build; blocking release)

1. **CMSA 2007 / SC Guidance Note on investment advice** — counsel brief Question 4. Applies to the Room in every market, not only Bursa.
2. **Bursa market-data licence** for showing delayed prices in an app (Yahoo terms are not a Bursa licence; HKEX requires a licence even for delayed data). Action for Saiful: ask Bursa data sales (distribution is via ICE).
3. To confirm against Bursa primary text (bursamalaysia.com blocks automated fetches): tick table, auction times, clearing tariff, 2027 holiday notice. SC list file format and reuse terms.

## Build plan (phase 1, all behind `MARKET_BURSA_ENABLED`, default off)

1. **Lane A — market registry** (in progress): `market_for(ticker)` from the `.KL` suffix; per-market currency, timezone, board lot, benchmark, options/Alpaca/short support; flag; symbol fixes (Sharia regex, yfinance dot→dash keeping suffixes, omnibox regex, exchange labels); options and Alpaca refused for `.KL`; `market_state` routed per market.
2. **Lane B — calendar and sessions:** per-market session model with Bursa's lunch break; holiday tables (2026 confirmed + 2027 derived, flagged); `market_state`, resting-order expiry, Room bank trading-day key per market.
3. **Lane C — MYR book:** `market` column on portfolios (migration), one MYR portfolio per user created on first Bursa trade (starting capital RM50,000, confirmed by Saiful 2026-11-23), board-lot check, tick-size rounding, ±30% price limit, Bursa fee schedule, no shorts/options; ticker reference loader for Bursa codes.
4. **Lane D — SC Shariah list:** second `standard`, semi-annual staleness window, per-market resolve; copy no longer says "S&P 500" for Bursa.
5. **Lane E — Room on `.KL`:** market-aware fact sheet (RM, FBM KLCI relative strength, BNM/DOSM macro, MGS rate), desk lane text "not available for this market" where SEC inputs are dark, prompts free of US-only claims for MY.
6. **Lane F — app:** currency formatter from the ticker's market (~100 `$` sites), MYR book in Portfolio, market switch, Bursa copy, flag dart-define.
7. Phase 2 (separate CR rows when started): Games on Bursa, Malaysian filings feed, content localisation of US-centric lessons and challenges.

## Acceptance (phase 1)

On Alpha with the flag on: search `1155.KL`, convene a Room whose stored record shows MYR, FBM KLCI and every unavailable desk input named; buy 100 units into the MYR book with Bursa fees; a 150-unit order is refused with the board-lot reason; the Shariah verdict cites the SC list and its as-of date; a Bursa holiday shows the market closed. With the flag off, nothing changes (full suite + UAT). Off in Beta builds until counsel Question 4 and the data licence are answered.
