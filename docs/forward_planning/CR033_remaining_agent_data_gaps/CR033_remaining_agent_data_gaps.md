# CR033 — Remaining agent truthfulness gaps (Market Analyst, Fundamentals Analyst, Bull Researcher)

**Status:** superseded by DEF052/DEF053/DEF054/DEF055 · **Session:** AT:R57 (filed) ·
**Superseded:** AT:R58, 2026-07-13
**Date:** 2026-07-13
**Source:** Saiful asked "any agents still not getting real data?" after CR023/CR024
(News/Social truthfulness) shipped. Auditing the rest of the 12-agent roster against
what's actually wired surfaced three more prompt-honesty gaps, plus DEF051 (filed

## Superseded (AT:R58)

Saiful asked for each gap to be tracked and tackled as an individual Defect rather than
one bundled CR, so each can close independently: **DEF052** (Market Analyst),
**DEF053** (Fundamentals Analyst), **DEF054** (Bull Researcher). Re-checking agent
wiring status after DEF051 shipped also surfaced a fourth gap this CR's own audit
missed — Bear Researcher makes the identical fabricated "Decision Journal" claim as
Bull Researcher — filed as **DEF055** (depends-on DEF054). This doc's research and
scope framing carries forward unchanged into the four Defect docs; no re-analysis was
needed, just re-packaging into the Defect register for individual tracking.
separately — that one is a compliance-input bug, not a prompt-honesty issue).

This CR is **documentation only** — no code ships under it. It records what was found;
implementation is future work, sequenced after DEF051 (which is the higher-priority,
safety-relevant fix from the same audit).

## 1. Market Analyst — technicals are 100% fabricated, always

`content/agents/market_analyst.md` claims: "Indicators: MACD, RSI, moving averages,
Bollinger Bands," "Volume profile," "Support and resistance levels," "Trend
identification." None of it is real, regardless of `use_real_market_data`:

- `room_runner.py::_profile_for_ticker()`: `rsi` is `rng.randint(35, 75)` — always
  fabricated, never computed from real price history.
- `trend` ("trading" vs "consolidating") is a coin flip (`rng.random() > 0.5`).
- `volume_tone` is a coin flip between two hardcoded strings — one of which literally
  says "above 20-day average — **real participation**" while being entirely fake.
- MACD, moving averages, and Bollinger Bands don't exist as profile fields **at all** —
  not even a synthetic placeholder. The prompt names three specific indicators the
  pipeline has never had any representation of.
- `support`/`breakout` become price-derived once `fetch_live_fundamentals()` overlays a
  real `base_price`, but the formula is a naive `price × 0.9` / `price × 1.03` — not a
  real support/resistance level from volume profile or price history, even when the
  underlying price is real.

**Provider note**: `yfinance` (already a dependency, already used for fundamentals/news/
earnings) can compute real RSI/MACD/moving averages/Bollinger Bands from its own
`history()` OHLCV data (already wired for `market_data.py`'s chart endpoint,
`MarketDataProvider.history()`) — no new external API needed, just a technical-analysis
computation layer over data already being fetched for the mobile Ticker Detail chart.
This is likely the cheapest of the three gaps in this CR to close for real, since the
raw price series is already flowing.

## 2. Fundamentals Analyst — real data, oversold scope

`content/agents/fundamentals_analyst.md` claims: "Financial statements (income, balance
sheet, cash flow)," "Earnings history and forward guidance," "Valuation multiples (P/E,
P/S, EV/EBITDA, FCF yield)," "Peer comparisons," "Capital allocation history (buybacks,
dividends, M&A)."

What's actually delivered via `fetch_live_fundamentals()` (real, via yfinance, when
configured): current price, trailing P/E only (not P/S or EV/EBITDA or FCF yield —
`fcf_margin` is a profit-margin proxy, not a valuation multiple), TTM revenue growth %,
profit margin %, net cash, 52-week range, and (since CR023, AT:R57) next earnings date.
Real, but narrower than claimed.

**Always fake, regardless of settings**: `sector_pe` (the one peer-comparison figure) is
`rng.uniform(15, 25)` — never real. No forward guidance figures exist. No capital
allocation history (buybacks/dividends/M&A) exists anywhere in the pipeline. No full
financial statements — just the handful of scalar ratios above.

## 3. Bull Researcher — fabricated Decision Journal claim

`content/agents/bull_researcher.md` claims "Historical context from the Decision
Journal" as an input. `journal_store` is write-only from the Room's perspective —
`build_journal_entry_for_run()` writes a run's outcome to the journal *after* it
completes; nothing reads past journal entries back into a *future* run's prompt. The
Bull Researcher (and by extension, anyone reasoning from the same profile) never
actually sees the user's trade history or past verdicts for this or any ticker.

Also present but out of scope for this CR (same "hardcoded sizing" pattern, arguably
lower priority): `bull_size`/`bear_size`/`upside`/`downside` in `_profile_for_ticker()`
are fixed literals (4, 2, 28, 18) regardless of any real input — the Bull/Bear
Researchers' narrative *reasoning* can inherit real fundamentals/news/sentiment data
per-ticker, but their sizing/probability conclusions never do.

## Out of scope

- DEF051 (Room's fake portfolio_value/drawdown) — filed separately, higher priority,
  safety-floor-relevant, not a prompt-honesty issue.
- Trader's fixed-percentage stop/target (`entry × 0.94` / `× 1.13`) — a design
  simplicity, not a false claim; the prompt doesn't assert real volatility-based
  stop placement.
- Research Manager, Risk Debators, Portfolio Manager, Concierge — reviewed, no
  fabricated-capability claims found (they synthesize from other agents' outputs +
  the user's real mandate/portfolio, once DEF051 is fixed).

## Acceptance (for this CR, docs-only)

- [x] All three gaps documented with file:line grounding, current as of 2026-07-13.
- [x] Distinguished from DEF051 (compliance-input bug vs. prompt-honesty gap).
- [x] Cheapest-fix note for Market Analyst (yfinance `history()` already flowing).
- [x] Filed in `docs/forward_planning/` and registered in `cr_list.md`.

## Acceptance (for future implementation CR/session)

- Market Analyst: real RSI/trend/volume computed from yfinance OHLCV when
  `use_real_market_data` is on; `content/agents/market_analyst.md` claims match actual
  runtime capability (drop MACD/moving-averages/Bollinger-Bands claims if not
  implemented, or implement them — Saiful's call on scope).
- Fundamentals Analyst: `content/agents/fundamentals_analyst.md` rewritten to describe
  actual scope (the scalar ratios delivered, not full statements/forward guidance/peer
  comparison/capital allocation) — same "correct the claim to match reality" pattern as
  CR023/CR024, unless peer comparison (at minimum) gets wired for real.
  `ALPHA_VANTAGE_API_KEY`(already provisioned for CR023) may cover fundamentals/earnings
  data too — worth checking before assuming a new provider is needed.
- Bull Researcher: either wire real recent-journal-entry context in, or drop the claim.
