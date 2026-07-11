# CR007 — Data & news provider research: closing the fake-data gap in the 12-agent analyst team

**Status:** proposed · **Session:** AT:G1 · **Date:** 2026-07-09
**Source:** Saiful — *"agents are only as good as the data that is sent to them. we should look
at using other data and news providers."*

This CR is a **research deliverable, not an implementation** — it exists to scope real
market-data, news, and social-sentiment providers for the 12-agent analyst team, and to
document a discovered gap: two of the four Analyst agents currently reason over fabricated
placeholder text, not real data. No code changes ship under this CR; wiring in a chosen
provider and rewriting agent prompts is future implementation work.

Full report with tables: see the artifact delivered in-session. This doc is the filed,
version-controlled copy.

## Problem

CLAUDE.md documents market data as "Yahoo via yfinance, with deterministic mock-walk
fallback." A pre-research survey of the actual codebase found this is only half the picture:

1. **Market/price data** — real, if fragile: `yfinance` (an unofficial Yahoo-scraping wrapper)
   powers quotes, OHLCV history, and fundamentals (`backend/app/services/market_data.py`,
   `fundamentals.py`). Code comments already flag it as a stopgap expected to change at Beta.
2. **News/sentiment data — net-new, not an upgrade.** The News Analyst and Social Media
   Analyst — the two agents whose entire job is news/sentiment — run on
   `room_runner.py`'s `_profile_for_ticker()`, a `random.Random(hash(ticker))`-seeded generator
   producing canned strings (fake catalysts, fake sentiment scores, fake mention trends). A
   real `yfinance` news fetch and a coded-but-inactive Alpha Vantage `NEWS_SENTIMENT` connector
   (in the mounted, not-yet-wired TradingAgents framework) both already exist in the codebase
   but reach neither agent.
3. **Prompt-honesty gap** — each agent's own base prompt (`content/agents/news_analyst.md`,
   `social_media_analyst.md`) separately claims access to specific real sources (Reuters/
   Bloomberg/FT/regulatory filings; Reddit/Twitter/StockTwits/Google Trends/Discord) that don't
   exist. `room_runner.py`'s system prompt correctly discloses the narrative fields as
   "simulation scaffolding, not live data" — the two prompt layers contradict each other. Per
   Saiful's direction, this is folded into this CR's scope rather than filed as a separate
   Defect: it's inseparable from "what needs to be true before these agents are data-grounded."
4. No decision-log entry exists for the original yfinance choice, and the only existing budget
   anchor is one unsized placeholder line in `unit_economics.md` ("Real-time data (when added)
   — ~$1/MAU").

## Findings — Market / price data

Replacing yfinance's unofficial scraping. **The deciding factor turned out to be licensing,
not price** — every provider checked except Twelve Data restricts display-to-end-users at
their advertised consumer tiers; the real cost is a sales conversation, not the sticker price.

| Provider | Cheapest usable tier | $/mo | Real-time? | Computes indicators? | Display to end users? |
|---|---|---|---|---|---|
| Twelve Data | Basic (free) / Grow | 0 / 79 | Yes (US) | **Yes** — 100+, all tiers | Add-on required (transparent, priced on request) |
| Alpha Vantage | Standard | 49.99 | Yes (entitlement flag) | Yes | Unverified — not addressed publicly |
| Finnhub | Free / Premium | 0 / ~12–100 | Yes | Unconfirmed | **No** — written approval required even for internal use |
| Polygon / Massive | Starter–Advanced | 29–199 | Delayed→real-time | No | **No** — Individual ToS bars end-user-facing apps entirely |
| Tiingo | Starter / Power | 0 / 30 | EOD-oriented | No | **No** — "Internal Use Only" |
| EODHD | Free–All-in-one | 0–99.99 | EOD/delayed | No | **No** — Personal-use tier bars redistribution |

Polygon/Massive's Individual license (confirmed via the actual ToS PDF) states it's
"exclusively for your personal, non-business, and non-commercial purposes" and bars building
"an application intended for use by end users other than you" — none of its $29–$199 tiers
are usable for AMI as published; a negotiated Business agreement is required.

**Recommendation:** investigate **Twelve Data** first. It's the only provider pricing
redistribution transparently (a named add-on, not a legal landmine) and it computes 100+
technical indicators server-side on every tier including free — directly fixing the
Market/Technical Analyst's fabricated-indicator problem, not just the reliability question.
Add-on price is unpublished; get a quote before committing.

## Findings — News data

| Provider | Tier | $/mo | Sentiment? | Verdict |
|---|---|---|---|---|
| **Alpha Vantage NEWS_SENTIMENT** | Standard | **49.99** | Yes — per-article + per-ticker | **Recommended** — already coded, zero net-new integration |
| Polygon / Massive | Starter | 29 | Yes — built into payload | Strong second — bundles with market data |
| StockNewsAPI | Basic | 19.99 | Yes | Cheap validation option |
| NewsAPI.org | Business | 449 | No | Avoid — not finance-specific, ToS bars full-text reuse |
| Benzinga | Free (link-out) / Paid | 0 / ~500–900+ (secondhand anchor) | Separate paid add-on (StockSnips), unpriced | Free tier isn't a real feed; paid tier several multiples of AV |
| GDELT | Free | 0 | No | Wrong tool — macro/geopolitical, not per-ticker |

**Recommendation:** wire in **Alpha Vantage NEWS_SENTIMENT**. The connector already exists at
`tradingagents/dataflows/alpha_vantage_news.py` in the mounted (but not yet activated)
framework — zero net-new integration work, and it returns exactly what a News Analyst needs:
per-article sentiment plus a per-ticker relevance-weighted score, from 50+ major financial
outlets.

### Benzinga, in detail — follow-up on request

Benzinga is a ~30-product ecosystem (Newswire/Article APIs, Mission-Critical Datasets,
Alternative Data), not one API — easy to underestimate from a single pricing-page glance.

- **Free tier** (self-serve via AWS Data Exchange, no sales contact): headline + body
  **teaser** + link to Benzinga.com only. No full body, no image, no sentiment, no published
  rate limit. Fine for Beta's low traffic volume, but fails the actual requirement — it's a
  link-out widget, not a data feed an agent can reason over.
- **Paid tier**: never publishes a price (confirmed again — sales-gated, "request a trial,"
  claimed 1-day response). The only real dollar figure found anywhere: a reseller marketplace
  (Finazon) sells the same Benzinga-sourced news dataset self-serve at **$901/month**, and a
  calendar-data bundle at $541/month — an order-of-magnitude anchor, not confirmed direct
  pricing, but the only concrete number across dozens of sources checked. That's several
  multiples of Alpha Vantage's confirmed $49.99/mo.
- **Sentiment** is a separate product (StockSnips, 2,000 US equities, NLP score 0–100) — its
  own unpriced sales conversation on top of the news API itself, not bundled the way Alpha
  Vantage's sentiment is.
- **Redistribution rights** — Benzinga's marketing page claims the paid tier permits full
  headline+body+image embed (a positive signal, if true — the biggest risk factor everywhere
  else in this report). But the actual legal terms page (`benzinga.com/apis/licensing/terms`)
  is JS-rendered and returned no readable content to automated fetch — **this claim is
  unverified from the primary legal source**. Open it in an actual browser before treating
  "full embed" as locked in.

**Verdict:** worth a same-day trial-request email if Saiful wants a firm number, but don't
expect Benzinga to beat Alpha Vantage on cost for a 100–500-user Beta — likely priced multiples
higher, with sentiment unbundled and licensing terms still unconfirmed. Alpha Vantage remains
the recommendation; Benzinga is a Phase 3 upgrade path if coverage/latency ever becomes the
bottleneck, not a Phase 1 pick.

## Findings — Social / sentiment data

The hardest category, assessed honestly rather than forced to a clean answer — no channel
gives a cheap, ToS-clean, direct-integration path.

| Channel | Beta-accessible? | ToS-safe? | Verdict |
|---|---|---|---|
| Reddit (direct) | Cheap in $, but approval-gated | Ambiguous for commercial use | Deprioritize |
| X/Twitter (direct) | ~$150–450/mo for one ticker | Yes (paid) | Deprioritize — cost scales per ticker |
| StockTwits (direct) | **No** — not accepting new API registrations | n/a | Drop until reopened |
| Google Trends | Only via an unmaintained unofficial scraper | Grey/fragile — worse risk than yfinance | Best-effort only, label the risk |
| Discord | **No product exists** | n/a | Drop from claimed capabilities outright |
| **LunarCrush** (aggregator) | **Yes, ~$30–100/mo** | Yes | **Best bet for Beta** |

Reddit's free tier is capped at 100 QPM, scoped to non-commercial/personal use — commercial
access requires manual approval at a negotiated rate (Reddit's own docs cite ~$12K/mo for a
50M-call block; there's no small-commercial-app tier). StockTwits' developer page states it
isn't accepting new registrations at all, independent of budget. `pytrends` (the only Google
Trends option) was archived by its maintainers in April 2026.

**Recommendation:** build on **LunarCrush** as the single real data source for the Social
Media Analyst (verify small/mid-cap ticker coverage before committing). Keep Google Trends as
an explicitly-labeled best-effort signal if used at all. **Drop Discord entirely** from the
agent's claimed capabilities — there's no product to build against, not a budget gap.

## Caching strategy (added on request)

AMI is a simulation/education app, not a live trading terminal — for most tickers on a normal
day, the news/sentiment picture doesn't materially change within a 12-hour window, and a
stable narrative within a single Room session is arguably more realistic than one that shifts
because a cache happened to expire mid-session.

- **Default TTL: 12h per ticker**, for both Alpha Vantage news/sentiment and LunarCrush social
  sentiment. Doubles the existing 6h earnings-calendar cache pattern already implemented in
  `market_data.py` — same architecture, applied to the two new feeds.
- **Shortened TTL on earnings day: 1–2h.** The earnings calendar is already fetched and cached
  — cheap to check "is today an earnings date for this ticker?" and shrink news TTL only then,
  when freshness actually matters for a realistic simulation.

**Where this saves money depends on the provider's billing model:**

- **Alpha Vantage** (flat $49.99/mo, 75 req/min cap, no daily cap) — caching doesn't lower the
  subscription price directly. What it does is keep call volume trivial regardless of user
  count (cache by ticker, not by user), which is what avoids being forced onto a pricier tier
  as usage grows toward Growth scale (10K–50K MAU).
- **LunarCrush** (credit-metered, ~$0.0005/credit beyond the included 2,000) — this is where
  caching directly cuts the bill. Uncached, credit spend scales with page views; with a 12h
  per-ticker cache, it scales with distinct tickers checked per day instead — a real multi-x
  reduction in credit consumption at any meaningful traffic.

## Phased recommendation

| Phase | Cost | Scope |
|---|---|---|
| **1 — do first** | ~$80–150/mo | Wire Alpha Vantage NEWS_SENTIMENT (News Analyst) + LunarCrush (Social Media Analyst); rewrite both base prompts to match real capabilities. Highest integrity impact, lowest cost/effort. |
| **2 — pending quote** | $79–229+/mo | Get a Twelve Data redistribution add-on quote; if reasonable, replace yfinance — fixes reliability AND the fake-technical-indicator problem. |
| **3 — optional** | budget-dependent | Benzinga premium news once quoted; direct Reddit/X only if usage volume justifies the approval/cost overhead. |

## What still needs re-verification before committing budget

- **Twelve Data's** Redistribution Rights Add-On price wasn't published — get a live quote.
- **Alpha Vantage's** display/redistribution terms weren't addressed on any fetched page —
  unverified, not cleared. Confirm before shipping headlines to end users.
- **Finnhub's** premium tier price ladder is secondary-sourced only (its pricing page
  render-blocked the fetch).
- **Polygon/Massive's** Business-tier terms (the actual legal path) weren't found at a
  fetchable URL — sales quote required.
- **LunarCrush's** small/mid-cap and meme-stock coverage depth wasn't confirmed (client-
  rendered pricing page) — worth a hands-on trial before committing budget.
- Safest interim posture for any provider with unconfirmed redistribution terms: use fetched
  data only as LLM context the agent synthesizes into original commentary, not verbatim
  display to end users.
- All pricing timestamped **2026-07-09** — re-verify close to the actual purchase decision.

## Scope

This CR covers the research and its two deliverables (artifact + this doc) only.

**Out of scope** (future work, contingent on Saiful's decision):
- Actually wiring Alpha Vantage NEWS_SENTIMENT or LunarCrush into `room_runner.py`.
- Rewriting `content/agents/news_analyst.md` and `social_media_analyst.md` to match real
  capabilities.
- Building real technical-indicator computation for the Market/Technical Analyst.
- Obtaining sales quotes for Twelve Data's redistribution add-on, Benzinga, or Polygon/Massive
  Business tier.
- Recording a decision-log entry once a provider is chosen (there is none on file today).

## Acceptance

- [x] Market data, news data, and social/sentiment data each researched with pricing +
      licensing/ToS, not price alone.
- [x] Current-state gap (fabricated news/sentiment data) documented with file:line grounding.
- [x] Prompt-honesty gap folded in per Saiful's direction, with a concrete recommendation.
- [x] Phased plan with cost tiers, since budget wasn't fixed in advance.
- [x] Filed in `docs/forward_planning/` and registered in `cr_list.md`.
