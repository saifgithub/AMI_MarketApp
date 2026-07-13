# CR023 — Wire the News Analyst to a real live news feed (Alpha Vantage NEWS_SENTIMENT)

**Status:** proposed · **Session:** AT:R55 · **Date:** 2026-07-12
**Source:** Saiful — asked for a check on whether Room agents get real live feeds
("specially the news and social media agents... we should at least use whatever feed
we have now"), then filed this as an implementation CR once the check confirmed the gap.

This CR is **documentation only** — no code ships under it. It designs the wiring;
implementation is a future session, gated on Saiful provisioning an Alpha Vantage key.

## Problem

The News Analyst — one of 12 Room agents, one of 4 whose entire job is data synthesis —
receives zero real news data. `room_runner.py::_profile_for_ticker()` (lines 236-240)
injects hardcoded strings into every ticker's profile:

```
catalyst: "Q3 earnings (beat by ~4%)"          — identical for every ticker
forward_catalyst: "FOMC decision in 11 days, sector earnings in 3 weeks"  — hardcoded
macro_tone: "constructive but fragile"          — hardcoded
fed_tone: "data-dependent with a dovish lean"    — hardcoded
```

This block is shared by all 12 agents (`room_prompts.py::_format_profile()`,
lines 140-177) and is explicitly disclosed to the LLM as "simulation scaffolding" —
so the News Analyst is not hallucinating, it's narrating a fixed script. Meanwhile its
own base prompt (`content/agents/news_analyst.md`) claims "Real-time news feeds
(Reuters, Bloomberg, FT, regional sources)... Macro indicator calendar... Earnings
calendar... Regulatory filings" — none of which exist anywhere in the pipeline.

A real, working news fetcher already exists (`market_data.py`'s yfinance-backed
`.news()`, 5-min cache, exposed at `GET /v1/sim/news/{ticker}`) but is wired only to
the mobile Ticker Detail screen — `room_runner.py`, `room_prompts.py`,
`agent_prompts.py`, and `overlay_generator.py` never import `market_data.py`. It is
completely disconnected from the agent/Room pipeline.

**CR007** (`docs/forward_planning/CR007_agent_data_provider_research/`, AT:G1,
2026-07-09) already researched this exact gap and recommends going past yfinance's
plain headlines to a provider with per-article sentiment scoring, since that's what a
News Analyst actually needs to do its job (distinguish signal from noise, not just
list headlines). This CR adopts that recommendation rather than wiring the existing
yfinance fetcher as-is.

## Provider — Alpha Vantage NEWS_SENTIMENT (per CR007, re-confirmed 2026-07-12)

| | |
|---|---|
| Tier | Standard |
| Cost | **$49.99/mo** (confirmed live 2026-07-12 — unchanged from CR007's 2026-07-09 figure) |
| Rate limit | 75 req/min, **no daily cap** on paid tiers |
| Coverage | 50+ major financial outlets, per-article + per-ticker relevance-weighted sentiment |
| Integration effort | **Near-zero** — a working connector already exists at
  `/Volumes/Extreme Pro/TradingAgent/tradingagents/dataflows/alpha_vantage_news.py::get_news(ticker, start_date, end_date)`
  in the read-only TradingAgents mount. Port the call pattern (don't import across the
  mount boundary — CLAUDE.md: integrate against read-only mounts, don't depend on them
  at runtime). |
| Licensing | Display/redistribution terms unconfirmed on any fetched page (per CR007)
  — safest posture: use as LLM context the agent synthesizes into its own commentary,
  never verbatim display to end users. This CR's design already does that (the News
  Analyst narrates, it doesn't quote raw feed text into the UI). |

Alpha Vantage was already the CR007 recommendation for News specifically because the
connector cost is near-zero and the sentiment score is exactly the derived signal a
News Analyst prompt asks for ("distinguish signal from noise... state expected vs
actual").

## Design

### New setting
`ALPHA_VANTAGE_API_KEY: str | None = None` in `backend/app/core/config.py`, alongside
the existing `use_real_market_data` flag. Set in `infra/alpha.env` (gitignored),
shipped via `/promote-to-alpha` step 4 like every other secret. Absent key → feature
disabled, falls back to today's synthetic block (see Degradation below).

### Fetcher module
New `backend/app/services/news_provider.py`, mirroring the shape of
`fundamentals.py::fetch_live_fundamentals()` (never-raises contract, returns `None` on
any failure):

```python
def fetch_live_news(ticker: str) -> NewsSentiment | None:
    """Alpha Vantage NEWS_SENTIMENT, ticker-scoped. Never raises."""
```

Returns a small dataclass: top N articles (title, source, published_at, url) +
an aggregate per-ticker relevance-weighted sentiment score. Ports the call shape from
the TradingAgents mount's `alpha_vantage_news.py::get_news()` (params: `tickers`,
`time_from`, `time_to`) — that function itself is not imported; this CR's
implementation is a fresh, minimal client scoped to what the News Analyst needs (no
`get_global_news` / `get_insider_transactions` — out of scope, see below).

### Wiring — Room path
`room_runner.py::_profile_for_ticker()` (lines 236-240): when
`ALPHA_VANTAGE_API_KEY` is set and `fetch_live_news(ticker)` succeeds, replace
`catalyst`/`forward_catalyst`/`macro_tone`/`fed_tone` with fields derived from the real
articles + sentiment score. `_format_profile()` (`room_prompts.py:140-177`) needs no
structural change — same keys, real values — but its "simulation scaffolding"
disclosure header should note when a field is live vs. synthetic, since the two will
now coexist per-ticker (live if the API call succeeded this cache window, synthetic
otherwise).

### Wiring — 1-on-1 path
`overlay_generator.py::_news_block()` (lines 168-199) currently only adds
mandate-conditioned *instructions* ("filter headlines to...", "down-weight
retail-noise sources...") with no actual headlines. Extend it to call the same
`fetch_live_news()` and inject real article summaries + sentiment alongside the
existing mandate-filtering instructions. This is also Silent_Scout's `05_agent_alignment`
Gap 5 "1-on-1" half and directly supersedes the stale "already shipped" claim in
`Silent_Scout/09_per_ticker_news/README.md` (that doc's NewsStrip/endpoint work shipped
for the mobile UI; the News-Analyst-context wiring it also claims did not — this CR is
where that actually happens).

### Caching
12h TTL per ticker (per CR007's caching strategy — AMI is a simulation/education app;
the news picture doesn't meaningfully change within a session, and a stable narrative
within one Room run is more realistic than one that shifts mid-session on cache
expiry). Shortened to 1-2h on earnings day (reuse the existing earnings-calendar fetch
to check "is today an earnings date for this ticker?" cheaply). Cache keyed by ticker,
not by user — call volume stays flat regardless of user count, which is what keeps
Alpha Vantage's flat $49.99/mo tier viable as usage grows.

### Graceful degradation
No key set, or the API call fails/times out/rate-limits → fall back to today's
synthetic `_profile_for_ticker()` strings. Never error the agent turn. Log the
fallback once per run (not once per call) to avoid log spam.

### Prompt rewrite
`content/agents/news_analyst.md` — replace:
```
- Real-time news feeds (Reuters, Bloomberg, FT, regional sources)
- Macro indicator calendar (CPI, NFP, Fed decisions, ECB, etc.)
- Earnings calendar
- Regulatory filings (8-K, S-1, etc.)
```
with language describing what's actually delivered: Alpha Vantage's multi-outlet
sentiment-scored news feed, ticker-relevance-weighted, with the earnings calendar
already integrated elsewhere in the profile (`fundamentals.py`). Drop the macro
calendar and regulatory filings claims entirely — no source for either exists, and
this CR doesn't add one (macro/regulatory data is a separate future gap, not folded
into this CR — see Out of scope).

## Out of scope

- Wiring `get_global_news()` / `get_insider_transactions()` from the same Alpha Vantage
  connector — narrower fetch for News Analyst's ticker-scoped need only.
- Macro indicator calendar, regulatory filings feeds — no provider chosen, separate
  future gap.
- Replacing yfinance for market/price data (CR007 Phase 2 — Twelve Data, pending quote).
- The Social Media Analyst (CR024, filed alongside this CR).
- Actual implementation — this CR is the design doc only.

**Update, same session:** Silent_Scout closed (AT:R55, Saiful decision — "its utility
has come to an end"). Its News-Analyst-relevant research
(`05_agent_alignment/` — the gap analysis + agent data matrix + validation suite that
originally documented this gap, and `09_per_ticker_news/` — the already-partially-
shipped mobile news feature, corrected in place) is preserved under
[`original_silent_scout_research/`](original_silent_scout_research/) in this CR's
folder rather than lost. The stale "shipped" claim mentioned above has been corrected
in place at its new location.

## Acceptance (for this CR, docs-only)

- [x] Gap documented with file:line grounding, current as of 2026-07-12.
- [x] Provider decision inherited from CR007, not re-researched from scratch; pricing
      re-confirmed live.
- [x] Wiring points named precisely for both Room and 1-on-1 paths.
- [x] Caching + degradation strategy specified.
- [x] Prompt-rewrite scope specified.
- [x] Filed in `docs/forward_planning/` and registered in `cr_list.md`.

## Acceptance (for future implementation CR/session)

- `ALPHA_VANTAGE_API_KEY` unset → behavior byte-identical to today (regression guard).
- With a valid key, News Analyst prompts (Room + 1-on-1) contain real per-ticker
  articles + sentiment score instead of the hardcoded strings.
- API failure/timeout never surfaces as a Room/1-on-1 error to the user.
- `content/agents/news_analyst.md` claims match actual runtime capability.
- Cache respects 12h/1-2h-on-earnings-day TTL, keyed by ticker.

## Implementation (AT:R57)

Saiful provisioned `ALPHA_VANTAGE_API_KEY` mid-session (added to the root `.env`
locally, mirrored into `infra/alpha.env` for the next `/promote-to-alpha`) and asked
for the *combining* design, not a single-provider select: **Yahoo (free) is always
tried; Alpha Vantage (paid, now live) is merged in alongside it whenever the key is
set** — not a mode switch, and not Yahoo-until-upgraded as this doc originally
specced. Either source can fail independently without taking the other down.

New `backend/app/services/news_context.py` — not the originally-specced
`news_provider.py` name, since that name implied a single active provider; this
module's `LiveHeadline` NamedTuple carries an optional `sentiment` field (only ever
populated by Alpha Vantage) so both sources share one shape. `_YfinanceSource` wraps
the already-cached `get_market_data_provider().news()` (no new caching needed — the
existing 5-min `CachingProvider._news_cache` TTL is enough, not this doc's originally
specced 12h/earnings-day scheme, which was sized for a metered client Yahoo isn't).
`_AlphaVantageSource` hits the real `NEWS_SENTIMENT` endpoint (call shape verified
against the live API, not just the TradingAgents mount's connector — confirmed the
real response's `feed[].ticker_sentiment[]` array carries a sentiment label **per
mentioned ticker**, not one label per article, so the fetcher matches the requested
ticker's own `ticker_sentiment_label` rather than the article's `overall_sentiment_label`
falling back to the latter only if the requested ticker isn't listed). Its own 30-min
TTL cache (billed API, unlike Yahoo's already-free path). `_merge_headlines()` dedupes
by normalized title (Alpha Vantage's sentiment-carrying version wins a collision),
sorts by recency, caps to the combined limit so running both sources doesn't blow out
the prompt.

Wired into `room_runner.py::_profile_for_ticker()` (overlays `catalyst` with the real
top headline; `forward_catalyst`/`macro_tone`/`fed_tone`/`fed_impact` stay synthetic —
no real source exists for those) and `agent_runner.py`'s 1-on-1 path (News-Analyst-gated,
reusing the ticker already extracted for the shared fundamentals block — no change to
`overlay_generator.py::_news_block()`'s shared `(agent_id, mandate) -> str` contract).
`room_prompts.py::_format_profile()`'s disclosure header became granular (fundamentals,
news, and forward/macro/sentiment each labeled independently) since a profile can now
have live fundamentals AND live news AND still-synthetic sentiment simultaneously —
the old binary header couldn't say that honestly.

Also folded in the earnings-calendar closure this doc's own "Prompt rewrite" section
incorrectly claimed was already done: `MarketDataProvider.earnings()` (already
yfinance-backed, already 6h-cached) is now surfaced as `next_earnings_date` in the
Room profile — real data instead of a bare disclaimer, at near-zero marginal cost.

`content/agents/news_analyst.md` rewritten to describe the combined-source, no-fixed-
outlet-list, sentiment-where-available, no-macro-calendar/regulatory-filings reality.

48 new/extended tests across `test_news_context.py` (new, 25 tests — both sources,
merge/dedupe, caching, degradation), `test_room_runner.py`, `test_room_prompts`
coverage inside the same file, `test_overlay_generator.py`, `test_agent_prompts.py`,
and new `test_one_on_one_news_injection.py`. Backend suite 592 → 640, all green.

Status: `proposed` → **`in_progress`** — real headlines, sentiment (where available),
and earnings now flow into both surfaces; the CR's stated acceptance items are
substantively met, but "in_progress" (not "done") because Alpha Vantage's activation
was confirmed structurally and against the live API's real response shape during this
session, not yet verified end-to-end through a live Room run on Alpha — that's the
natural next-session confirmation once this promotes.
