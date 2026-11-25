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

Same day, Saiful: **"alpha is internal"**, confirmed as every alpha-channel build (internal and external testing groups). `--bursa` is now allowed on any alpha-channel build and refused only on `--channel beta` and `--production` (`build_testflight.sh`, `build_playstore.sh`; pinned by `test_cr282_bursa_build_containment.py`). The four items reopen before Bursa reaches Beta or the store.

## Bursa batch (Saiful 2026-11-25)

Request: "run a room on around 200 tickers from bursa, chosen randomly but with a spread in mind. as much as possible do this mechanically. I want to know if we can find any approved ticker." Branch `cr282-bursa-batch`. All files in `docs/forward_planning/CR282_bursa_malaysia/bursa_batch/`; scripts in `backend/scripts/`.

1. **Universe** (`bursa_universe.py` -> `universe_2026-11-25.csv`). Yahoo screener (`yfinance` 1.3.0 `EquityQuery("eq", ["exchange", "KLS"])`), paged 250 at a time: 1,091 symbols. `is_bursa_code` accepts 1,072 and rejects 19 (warrants/structured products such as `0165PA.KL`, `0800EA.KL`, `8877R1.KL`). Sector and industry are not in the screener rows, so each comes from one extra screener query per sector and per industry, matched by symbol (0 symbols without either). Responses are cached on disk (git-ignored `_cache/`), 429s back off exponentially, a failure aborts without writing a partial file.
2. **Board is unknown.** Yahoo does not provide Main vs ACE. The "0xxx code = ACE" rule fails on the data: 364 of 1,072 codes start with 0 (far more than ACE's company count) and the series contains VITROX, INARI and FRONTKN, which are Main Market names that graduated from ACE and kept their codes. `board` is therefore `unknown` for every row, and `code_series` (`0xxx` or `other`) is recorded instead. The sample balances on `code_series`, which is a proxy, not board. A real board column needs Bursa's own listing; not fetched.
3. **Sample** (`bursa_sample.py` -> `sample_20261125.csv` + `.meta.json`, seed **20261125**, N 200). Drops: no price, zero/missing 3-month volume, no market cap (13 dropped: 12 no market cap, 1 zero volume; 1,059 eligible). Terciles are equal thirds of the eligible universe by market-cap rank (large >= RM362.3M, mid RM91.0M-RM361.9M, small < RM90.9M). Sector quotas are proportional (largest remainder), each split as evenly as possible across the three terciles, and picks inside a (sector, tercile) cell are systematic over `code_series` after a seeded shuffle so the 0xxx/other mix follows the cell. Deterministic for a seed and input file.
4. **Driver** (`bursa_batch.py`, reusing the CR035 helpers in `room_benchmark.py`). One Room per ticker on a dedicated anonymous benchmark user: minted via `POST /v1/auth/anon` with `app_version="room-benchmark"`, which is the marker every real-user count already excludes (`admin_analytics._real_users_clause`, `verdict_outcomes`, `ticker_interest`, ...). Plan patched to `trader` through the admin plan endpoint, note `CR282 bursa batch user`. Display name `Benchmark`.
5. **Mandate** is sent as the Room request's `mandate_override`, as CR035 does, not written to the DB: `risk_score` 5, every compliance filter off including `liquid_only`, everything else CR035's pinned neutral set (long-term, 30% max drawdown). `long_only` is left at its schema default (True): the Room only opens buys and Bursa has no shorting, so it blocks nothing; `--mandate-json` is not offered here, edit `BURSA_MANDATE_OVERRIDE` if that needs to change.
6. **Credits** follow CR035 exactly: on a 402 the driver calls `POST /v1/admin/users/{id}/credits` with +2,000 (CR039 meters Convene the Room; a top-up cannot be granted up-front because the plan patch resets the allowance). 200 Rooms at 8 credits is about 1,600. Uses `ADMIN_SECRET` from the environment.
7. **Resume and errors.** `runs_<batch>.jsonl` is the checkpoint (latest record per ticker wins). A re-run skips `completed` and `permanent_failure`; `failed_after_retries` re-tries. Transient (transport errors, 408/409/425/429/5xx, a Room that ends failed/cancelled/times out) retries 3 times with doubling backoff, each attempt logged on the record. A 4xx such as an unknown ticker is `permanent_failure` with the server's reason. Nothing is dropped; the exit code is non-zero if any ticker did not complete. Concurrency 1 (the CR035 default); `--concurrency K` mints K benchmark users because the Room refuses a second concurrent Room per user (409).
8. **Report** (`bursa_batch_report.py` -> `report_<batch>.md`), read-only over the saved JSONL and the sample CSV: per-ticker action, the grader's answers, deciding question and first 300 characters of the CIO reason; totals; approve rate by tercile, sector and code series; blocker frequency; every APPROVE with levels and full reason. Failed, never-run, no-coded-record, UNAVAILABLE and cached/banked runs are counted in a Warnings block, never folded into PASS.
9. **Run it** (on melehost inside `ami_api_alpha`, per the CR035 ops lesson):

```bash
scp docs/forward_planning/CR282_bursa_malaysia/bursa_batch/sample_20261125.csv melehost:/tmp/
ssh melehost "docker exec ami_api_alpha mkdir -p /tmp/cr282 && docker cp ~/ami_trade/backend/scripts/. ami_api_alpha:/app/scripts/ && docker cp /tmp/sample_20261125.csv ami_api_alpha:/tmp/cr282/"
ssh melehost "docker exec ami_api_alpha sh -c 'cd /app && python -m scripts.bursa_batch /tmp/cr282/sample_20261125.csv --batch-id bursa282-2026-11-25 --base-url http://localhost:8000 --out-dir /tmp/cr282 --dry-run'"
ssh melehost "docker exec -d ami_api_alpha sh -c 'cd /app && python -m scripts.bursa_batch /tmp/cr282/sample_20261125.csv --batch-id bursa282-2026-11-25 --base-url http://localhost:8000 --out-dir /tmp/cr282 >> /tmp/cr282/driver.log 2>&1'"
# progress / resume (same command re-run skips done tickers)
ssh melehost "docker exec ami_api_alpha sh -c 'tail -3 /tmp/cr282/driver.log; wc -l /tmp/cr282/runs_bursa282-2026-11-25.jsonl'"
# copy back BEFORE any container recreate (it wipes /tmp), then report on the Mac
ssh melehost "docker cp ami_api_alpha:/tmp/cr282/runs_bursa282-2026-11-25.jsonl /tmp/"
scp melehost:/tmp/runs_bursa282-2026-11-25.jsonl docs/forward_planning/CR282_bursa_malaysia/bursa_batch/
cd backend && .venv/bin/python -m scripts.bursa_batch_report ../docs/forward_planning/CR282_bursa_malaysia/bursa_batch/sample_20261125.csv --batch-id bursa282-2026-11-25
```

10. **Unverified.** Board; whether the live server runs the coded rule (the report's Warnings block says so loudly if `coded_decision` is absent); whether the Alpha container has `ADMIN_SECRET` in its env (CR035 ran the same way); whether re-POSTing a ticker whose first run ended `failed` starts a fresh run or re-attaches. Wall time at CR035's pace (about 3 minutes a Room) is roughly 10 hours for 200.
11. **Result (2026-11-25, `report_bursa282-2026-11-25.md`).** 200/200 completed, 0 failures, 0 cached. Ran at concurrency 2 (two benchmark users), about 1.8 minutes a Room, graded by on-prem Ling (bear=v2, thinking off). Every Room at risk score 5 with filters off, so this is the most permissive mandate the app offers, not a typical one.
    1. **24 APPROVE, 176 PASS (12.0%).** By tercile: large 13/68 (19.1%), mid 7/67 (10.4%), small 4/65 (6.2%). By code series: 0xxx 3/68, other 21/132. Strongest sector Consumer Cyclical 7/28; Energy 0/6, Utilities 0/3, Technology 1/24.
    2. **What blocks:** `trade_proposed` is listed for 166 of 176 PASS (first for 77); `terminal_vulnerability` first for 99.
    3. **Pattern:** almost every APPROVE is a cheap, net-cash or high-FCF-yield stock in a technical downtrend, sized at the 5% cap.
    4. **Liquidity:** 9 of 24 trade under RM100k a day (KITACON and LEESK about RM5k, BERTAM RM8k); 6 trade over RM1m a day (SDG, MNHLDG, TIMECOM, MTTSL, TAKAFUL, EMPIRE). The batch ran with `liquid_only` off on purpose.
    5. **Geometry the grader did not catch:** 5285.KL SDG targets +RM0.155 against a RM0.36 stop distance (reward:risk 0.43); 4006.KL ORIENT 0.80; 5000.KL HUMEIND targets +54% in 90 days (9.1:1). 5015.KL APM approves at 1% while its own reason calls the order size impractical.
    6. **Caveat:** Ling's catalyst and thesis questions were still lenient against DeepInfra (272 vs 170 and 172 vs 115 "yes" on the 300 fit Rooms). Saiful 2026-11-25: tune those two after the batch, then re-grade these 200 Rooms with the tuned wording.
    7. **Re-graded 2026-11-25 with the tuned Ling catalyst wording (`cat=v2`):** 24 APPROVE / 6 CONTESTED / 170 PASS by rule outcome (stored 24 / 5 / 171); no Room moves between APPROVE and PASS, 1 APPROVE → CONTESTED (4006.KL), 1 CONTESTED → APPROVE (7134.KL), 1 PASS → CONTESTED (5180.KL), all close-band changes at risk 5, where catalyst does not decide. Thesis wording stays shared (a stricter candidate failed the re-fit). Detail: `docs/forward_planning/CR267_beta_programme/ling_fit_2026-11-25.md`, scores `bursa_batch/regrade_bursa282-2026-11-25_ling-cat-v2.jsonl`.
