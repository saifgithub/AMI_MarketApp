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
3. **SC list reuse permission.** The SC site disclaimer bars reproducing or storing its content "in another site or retrieval system" without prior written permission. We store stock codes only. Ask the SC for written permission before the flag goes on for users (lane D, 2026-11-24).
4. To confirm against Bursa primary text (bursamalaysia.com blocks automated fetches): tick table, auction times, clearing tariff, 2027 holiday notice. SC list file format and reuse terms.

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

## Lane C — MYR book (built 2026-11-24, branch `lane/cr282-myr-book`)

1. Migration `cr282a0b0c0d1`: `sim_portfolios.market` (NOT NULL, default `'US'`). The MYR book is `kind="training_my"`, `market="MY"`, RM50,000, created on the first Bursa action. A distinct kind (not a second `training` row) is what keeps every existing `kind == "training"` lookup a US-only single-row read.
2. Rules live in `backend/app/trading_math/bursa_rules.py`: board lot 100, tick grid, ±30% price limit (30 sen below RM1), fee schedule. Tick table: circular rr2_110411, **UNVERIFIED against later amendments**. Fees: brokerage 0.10% min RM8 and clearing 0.03% cap RM1,000 are **UNVERIFIED research figures**; stamp duty 0.10% cap RM1,000 is secondary-sourced; no SST on ordinary-share brokerage is UNVERIFIED.
3. A Bursa order that breaks a market rule raises `MarketRuleViolation` and the sim routes return HTTP 422 `{code, message, market}`; mandate refusals keep their existing 200 `ok:false` shape.
4. `sweep_resting_orders` gates per market: US orders when NYSE is open, `.KL` orders when `is_market_open(Market.MY)`. Market orders fill at the delayed quote at any time, as the US book does.
5. Bursa ticker list: no source with clear terms found (Bursa blocks automated fetches; third-party listing sites not scraped). The per-exchange loader and refresh scoping are built (`load_bursa_reference`, `upsert_reference(bursa=True)`); until a code CSV is supplied `.KL` stays accepted on shape.
6. Deferred: NAV/TWR snapshots, portfolio history and the nightly NAV tick still cover the US book only; Bursa bracket closes are not journaled.

## Lane log

1. **Lane A** (market registry) merged `aff7a6d3`, suite 9539/0.
2. **Lane B** (calendar, sessions, holiday table 2026–2027) merged `58d0f56f`, suite 9589/0. 2027 observed days derived (Awal Muharram observed Tue 8 Jun 2027). The resting-order sweep's US-only gate went to lane C.
3. **Lane D** (SC Shariah list) merged 2026-11-24. The SC list is a 41-page bilingual PDF read from the stable index page (`SHARIA_SC_LIST_URL`). The 29 May 2026 list has 886 compliant securities out of 1,099. A `.KL` stock absent from the list resolves SCREENED_OUT: the list classifies every Main/ACE/LEAP security, so absence means reviewed and non-compliant. Islamic REITs/ETFs (separate SC files) are over-blocked for now. The SC methodology changed in Nov 2025 to a single 5% business-activity benchmark; the financial ratios stay below 33%. **New dependency: `pypdf`** (pure Python, BSD), in `pyproject.toml` and `uv.lock`. Follow-ups: the 5-digit ACE/LEAP codes (e.g. `03068`) fail lane A's `^[0-9]{4}[A-Z]?\.KL$`, to fix after lane C; the first real list release on Fri 27 Nov 2026 must be checked once it is ingested.

## Lane E — the Room on `.KL` (built 2026-11-24, branch `lane/cr282-room`)

1. **US is byte-identical, and proven.** Every Bursa behaviour hangs off `profile["market"] == "MY"` (set only for `.KL`), `market_for(ticker)`, or a `<!-- market:my -->` block in four agent `.md` files; for US each is absent. `tests/unit/test_cr282_room_us_byte_identical.py` re-renders a frozen production-shaped US sheet (every desk's sheet, every desk's full Room prompt under three mandates, the Risk Officer prompt, the trader grammar, the FOMC text) and the derived prompt version of every agent against `fixtures/cr282_room_us_golden.json`, generated BEFORE any lane-E change. Policy version unchanged, so no banked US Room re-keys.
2. **Currency.** A MY sheet and Room prompt are localised at the render seam (`room_market.localize_money`: a `$` before a digit becomes `RM`; cashtags are left alone) rather than at ~240 formatter sites; the MYR book block, the Risk Officer prompt, scripted turns and the base prompts' placeholders follow. Prices carry three decimals on Bursa (tick RM0.005 below RM1.00); the Execution Desk's constrained-decoding grammar takes `RM\d{1,6}\.\d{2,3}`.
3. **Liquidity floors (`liquid_only`, enforced by the safety floor).** Per market: US $500M cap / $1M a day (unchanged); MY **RM2,100M cap / RM4.2M a day** = the dollar floors at an ASSUMED RM4.20/USD (no FX feed). Strict reading: most Bursa small and mid caps fall below it. Revisit with real Bursa turnover before the flag goes on for users.
4. **Benchmark.** `^KLSE` one-year change vs the stock's own one-year change, both from daily bars over the same window; Yahoo's `SandP52WeekChange` is dropped for `.KL` (guarded in `_profile_for_ticker`: no KLCI legs means no relative-strength line, never an S&P figure).
5. **SEC-dark inputs** are not fetched (`resolve_cik` returns None for `.KL`; every EDGAR overlay is skipped) and each is named `not available for this market (Bursa Malaysia filings are not yet ingested)` on the desk that would have shown it: executive change, filings index, insider ratio / 10b5-1 / cluster, 8-K flags (News lane); peer basket, filed-statement detail, filings index (Fundamentals lane); put/call (Social lane). Named regardless of the US feature flags.
6. **Macro.** `trading_math/bnm_calendar.py`: OPR 2.75% (held at the 5 Nov 2026 MPC), MPC decision days 2026 and 2027 from BNM's MPS of 5 Nov 2026; past 4 Nov 2027 the sheet says the next date is unknown. OpenDOSM headline CPI (`services/opendosm_cpi.py`, year-on-year from the published index, 1-day cache) behind `OPENDOSM_CPI_ENABLED`, default off; the sheet says so when off or unreachable.
7. **WACC.** `WACC_MY_RISK_FREE_PCT` 3.9 (10y MGS 3.864% on 16 Nov 2026) and `WACC_MY_ERP_PCT` 6.0 (approximate, not checked against a published table). Dated settings, named on the line; review by 2027-02-01.
8. **The Room reads the MYR book** (holdings block, sector context, risk-limit context, valuation snapshot, bank digest) and keys on the MY trading day; US argument lists are unchanged.
9. **Deferred.** Portfolio Health copy (`portfolio_rules.py`, "S&P 500" beta wording) and portfolio analytics for the MYR book (lane C deferred NAV/TWR); Malay Mail / Bernama news feed (built: Lane E2 below); Social (Reddit) is left to degrade on its own.

## Lane E2 — Malaysian news feed (built 2026-11-24, branch `cr282-my-news-rss`)

Closes the "Malay Mail / Bernama news feed" item deferred in Lane E.

1. **Feed.** `services/my_news_rss.py` reads `https://www.malaymail.com/feed/rss/money` (HTTP 200 with a `Mozilla/5.0` User-Agent; 50 items on 2026-11-24, each with title, link, pubDate and full `<content:encoded>`). Stdlib `xml.etree`, no new dependency; DOCTYPE/ENTITY refused. Parsed feed cached in-process 15 minutes; a failed fetch is never cached and never an empty list.
2. **What leaves the module.** Headline, link and date only. `<content:encoded>` and `<description>` are never read.
3. **Matching (`.KL` only).** The Room's Yahoo `shortName`/`longName` (plus a two-entry dated alias table: 5099.KL AirAsia, 1155.KL Maybank) have corporate-form words stripped (Berhad, Bhd, Holdings, Group, Corporation, Co, Ltd, Limited, Plc, Sdn, Inc) and are matched against titles on whole words, case-insensitive. A name that reduces to one generic word (Bank, Capital, Malaysia, ...) is dropped; a name of 3 letters or fewer matches upper-case only and never if it is a common word. Up to 2 market-wide items (title mentions Bursa Malaysia, FBM KLCI or ringgit; not already a company item) are added as market context.
4. **Merge.** In `news_context.fetch_live_news`, label `malaymail_rss`, publisher "Malay Mail" (market items: "Malay Mail (market-wide, not company news)"). Company items join the existing merge (title de-dup, recency sort, cap 5, 7-day floor). **Change to the cap rule:** the market items ride beside the cap of 5, so a `.KL` list can run to 7, and only when company news survived: market context alone returns no feed (UNAVAILABLE), so it is never charged as live data. A matched Malay Mail company item counts as on-ticker for `pick_catalyst` (the press says Maybank, the registered name leads with Malayan).
5. **Switch.** `MY_NEWS_RSS_ENABLED`, default false in code, forwarded in `docker-compose.yml`. The `.KL` News turn's coded AMI note says "not enabled on this deployment" when off and "unavailable this call" when on but the fetch failed; when live it states the items are headline/link/date only and market-wide ones are context. `MY_SHEET_REVISION` 3 -> 4, and the `.KL` bank variant gains `|my_news=on` while the switch is on, so a sheet banked in one state is never reused in the other. US Rooms are unchanged (pinned in `test_cr282_my_news_rss.py`).
6. **Terms status.** Bernama's copyright terms (copyrights.php, clause 3) require express consent for reproduction or transmission. Malay Mail asserts copyright; its terms page could not be read by an automated fetch. Saiful's ruling (2026-11-24): build it and switch it on in Alpha; permission is being requested before testers; the switch is how it is turned off. Beta stays off until permission is in hand.
7. **Known limits.** Company items need a Yahoo name (a failed name lookup leaves only market items, which return no feed). Matching is on titles, so an article that names the company only in its body is missed, and an article that mentions a company as a source ("says CIMB Securities") matches. The sheet is frozen per day: a Room banked while the feed was down keeps the "unavailable" note until the bank turns over.

## Deploy

1. Phase 1 code (lanes A–F) live on Alpha in deploy #23 `alpha-2026-11-24-1` (`bda0b21e`) with `MARKET_BURSA_ENABLED` off. The UAT API cases UAT-PLAT-009, SIM-035, SIM-036, ROOM-033 and GAME-007 pass against Alpha, proving Bursa is dark there and US unchanged.
2. Next: the flag-on acceptance run (UAT-SIM-037, ROOM-034, WATCH-017, JRNL-012) with the backend flag on in Alpha and an internal app build with `AMI_BURSA=true`.
3. Open for Saiful before the flag goes on: the Bursa liquidity floors (lane E used the US floors at RM4.20/USD, which is strict for Bursa) and the Malaysian ERP of 6.0% (approximate).

## Rulings (Saiful, 2026-11-24)

1. **Bursa on in Alpha, SC list included.** `MARKET_BURSA_ENABLED=true` in Alpha's env (config-only recreate of deploy #23). The SC list ingested on first boot: 886 compliant, 18 non-compliant, as of 2026-05-29. `1155.KL` validates as Bursa Malaysia. Written SC permission is still to be requested before release to users.
2. **Liquidity floors: Bursa-specific**, derived from real Bursa turnover, documented, confirmed by Saiful before the flag goes on for users.

## Bursa liquidity floors (measured 2026-11-24, branch `lane/cr282-bursa-floors`)

1. Measured 882 `.KL` names (SC list codes + 18 large names). Lane E's RM2,100M / RM4.2M passed 64 (7%). Recommended **RM300M cap, RM250k/day** passes 221 (25%; 246 on the enforced avg-volume x price metric). **Pending Saiful's confirmation.** Detail: [`bursa_liquidity_floors_2026-11-24.md`](bursa_liquidity_floors_2026-11-24.md).

## Counsel ruling (2026-11-24)

Saiful, relaying counsel: "On all 3, since these are internal testers, counsel says we are covered." The three are counsel brief Question 4 (CMSA investment advice), Question 5 (Bursa market data via Yahoo) and Question 6 (SC Shariah-list reuse), plus the Malay Mail / Bernama news permission. Scope confirmed by Saiful the same day: **internal groups only** (TestFlight internal group, Play internal track). Nothing changes in the builds: `--bursa` stays internal-only and is still refused on Beta and store builds (`test_cr282_bursa_build_containment.py`). Before Bursa reaches Beta (external) testers or the store, all four reopen.
