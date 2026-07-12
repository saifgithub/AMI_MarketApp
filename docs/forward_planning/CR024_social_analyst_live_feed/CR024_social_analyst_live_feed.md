# CR024 — Wire the Social Media Analyst to a real social-sentiment source (LunarCrush)

**Status:** proposed · **Session:** AT:R55 · **Date:** 2026-07-12
**Source:** Saiful — same check that produced CR023; filed alongside it as the social
half of the same gap.

This CR is **documentation only** — no code ships under it.

## Problem

The Social Media Analyst has no real social/sentiment feed anywhere in the backend.
`room_runner.py::_profile_for_ticker()` (lines 241-245) generates every sentiment field
from a `random.Random(hash(ticker.upper()))` seed — deterministic per ticker, not
fetched from anywhere:

```
sentiment_tone   — coin-flip ("moderately bullish" / "mixed")
sentiment_score  — f"+{rng.uniform(0.3, 1.8):.1f}"σ, pseudo-random
mention_trend    — hardcoded "up 40% week-over-week"
influencer_take  — hardcoded phrase
pattern          — hardcoded phrase
```

Its base prompt (`content/agents/social_media_analyst.md`) claims "Reddit... Twitter/X
cashtags... StockTwits sentiment scores... Google Trends... Discord communities" — a
`grep -rniE "reddit|twitter|stocktwits|social.?media"` across `backend/app` confirms
none of these integrations exist: no HTTP client, no SDK, no API key for any of them,
anywhere in the codebase. Unlike the News Analyst (CR023, where a real yfinance news
feed already exists just disconnected from agents), this is **net-new** — there is
nothing partially built to wire up.

## Provider research (inherits CR007, re-verified 2026-07-12)

CR007 (`docs/forward_planning/CR007_agent_data_provider_research/`, AT:G1, 2026-07-09)
already surveyed this category — the hardest of the three (market/news/social) it
covered, "assessed honestly rather than forced to a clean answer":

| Channel | Verdict (CR007) | Still true 2026-07-12? |
|---|---|---|
| Reddit (direct) | Deprioritize — ~$12K/mo commercial tier, no small-app pricing | Not re-checked; no reason to expect a change in 3 days |
| X/Twitter (direct) | Deprioritize — $150-450/mo *per ticker*, cost scales badly | Same |
| StockTwits (direct) | Drop — not accepting new API registrations at all | Same |
| Google Trends (`pytrends`) | Best-effort only — unofficial scraper, archived by maintainers April 2026 | Same, and now further stale (archived, not just unmaintained) |
| Discord | Drop entirely — no product exists | Same |
| **LunarCrush** (aggregator) | **Best bet — ~$30-100/mo** | **Re-confirmed live today**: still operational, API/developer docs live, claims "2,000+ stocks" coverage (not crypto-only) — consistent with viability. **Exact tier pricing still unconfirmed** — `lunarcrush.com/pricing/` is client-rendered (JS), same limitation CR007 hit on 2026-07-09. No new information on small/mid-cap depth. |

**No new research needed beyond this freshness check** — CR007's conclusion holds:
build on LunarCrush, treat exact tier cost and small/mid-cap coverage as **unconfirmed
until a hands-on trial signup**, same caveat CR007 already flagged. This CR does not
change that recommendation; it inherits it.

**Recommendation, unchanged from CR007:** before committing budget, Saiful (or a
future session with API access) creates a LunarCrush trial account, pulls a handful of
representative tickers (large-cap + a couple of the app's actual popular tickers, not
just AAPL/TSLA) to confirm coverage depth and get the real per-tier price, since the
pricing page won't render for an automated fetch.

## Design

### New setting
`LUNARCRUSH_API_KEY: str | None = None` in `backend/app/core/config.py`, same pattern
as CR023's `ALPHA_VANTAGE_API_KEY`. Absent key → feature disabled, falls back to
today's synthetic block.

### Fetcher module
New `backend/app/services/social_provider.py`, same never-raises contract as CR023's
`news_provider.py`:

```python
def fetch_live_sentiment(ticker: str) -> SocialSentiment | None:
    """LunarCrush social-intelligence data, ticker-scoped. Never raises."""
```

Returns a dataclass covering whatever LunarCrush's v4 API actually exposes per-ticker
(social sentiment score, mention/engagement volume, trend direction) — exact field
mapping is implementation-time work once a trial account confirms the real response
shape; this design doc fixes the *seam*, not the payload schema.

### Wiring — Room path
`room_runner.py::_profile_for_ticker()` (lines 241-245): when
`LUNARCRUSH_API_KEY` is set and `fetch_live_sentiment(ticker)` succeeds, replace the
5 synthetic fields (`sentiment_tone`, `sentiment_score`, `mention_trend`,
`influencer_take`, `pattern`) with real values derived from the LunarCrush response.
Same `_format_profile()` seam as CR023 — no structural prompt-builder change needed.

### Wiring — 1-on-1 path
`overlay_generator.py::_social_block()` (lines 168-199, alongside `_news_block()`) —
same treatment as CR023's `_news_block()` extension: inject real sentiment data
alongside the existing mandate-conditioned instructions, instead of nothing.

### Caching
Same 12h TTL per ticker as CR023, shortened on earnings day. Matters more here than
for Alpha Vantage: LunarCrush is credit-metered (~$0.0005/credit beyond an included
allowance per CR007), so caching by ticker rather than by user/pageview is what keeps
the bill scaling with distinct tickers checked per day, not with traffic.

### Graceful degradation
Identical pattern to CR023: no key, API failure, or credit exhaustion → synthetic
fallback, never error the turn, log once per run.

### Prompt rewrite
`content/agents/social_media_analyst.md` — replace the Reddit/Twitter/StockTwits/
Google Trends/Discord list with language describing LunarCrush's actual aggregate
social-intelligence coverage (cross-platform sentiment score + engagement/mention
trend, sourced from an aggregator, not a claimed direct read of any single platform).
Keep the "no @handles, no DM scraping" anonymity framing — it's still the right
posture for an aggregated signal too.

## Out of scope

- Confirming LunarCrush's exact tier price/small-cap coverage — requires a live trial
  account, not deskwork; flagged as the explicit next step before budget commitment.
- Direct Reddit/Twitter/StockTwits/Discord integration — ruled out by CR007 on
  cost/ToS/availability grounds, not revisited here.
- Google Trends best-effort signal — CR007 left this as an optional label-the-risk
  addition; not folded into this CR (LunarCrush alone is the recommended path).
- The News Analyst (CR023, filed alongside this CR).
- Actual implementation — this CR is the design doc only.

## Acceptance (for this CR, docs-only)

- [x] Provider recommendation inherited from CR007 with a live freshness check, not
      re-researched from zero.
- [x] Gap documented as net-new (no partial integration exists, unlike CR023's news
      fetcher).
- [x] Wiring points named precisely for both Room and 1-on-1 paths.
- [x] Explicit "unconfirmed, needs a trial account" flag carried forward rather than
      guessed at.
- [x] Filed in `docs/forward_planning/` and registered in `cr_list.md`.

## Acceptance (for future implementation CR/session)

- A LunarCrush trial has confirmed real per-tier pricing and coverage for a
  representative ticker set before any code lands.
- `LUNARCRUSH_API_KEY` unset → behavior byte-identical to today (regression guard).
- With a valid key, Social Media Analyst prompts (Room + 1-on-1) contain real
  sentiment/mention/trend data instead of the `rng`-seeded placeholders.
- API failure/credit exhaustion never surfaces as a Room/1-on-1 error to the user.
- `content/agents/social_media_analyst.md` claims match actual runtime capability.
