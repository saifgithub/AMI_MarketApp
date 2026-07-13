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

## Interim measure (AT:R57)

Saiful's directive this session was "news and social media analyst needs to be
truthful now" — but unlike CR023's News Analyst (which had a free real-data path via
Yahoo already sitting disconnected), this CR's own research already established there
is **no free real-data path for social sentiment**. LunarCrush remains exactly as
gated as this doc always specified: unconfirmed pricing, needs a trial account, no
code lands until that happens. Nothing here changes that — this CR is **not closed**
and stays `proposed`.

What shipped instead was a truthfulness-only fix, three layers deep:

1. `content/agents/social_media_analyst.md` — "Inputs" and "Output style" rewritten
   to drop the Reddit/Twitter/StockTwits/Google Trends/Discord access claims entirely,
   replaced with explicit "no live feed connected, reason illustratively, never
   present a specific number as if measured" framing.
2. `backend/app/agents/overlay_generator.py::_social_block()` — dropped the
   "r/wallstreetbets" naming and the implied-real ">2σ unusual activity" framing from
   the 1-on-1 mandate-overlay instructions.
3. `backend/app/services/room_runner.py::_profile_for_ticker()`'s synthetic sentiment
   values reworded — dropped the fake-precision `σ`-suffixed decimal and the
   single hardcoded "up 40% week-over-week" string that was identical for literally
   every ticker regardless of the per-ticker `rng` seed (the least defensible
   fabrication in the whole profile). Values are now ticker-varied and explicitly
   hedged ("elevated intensity (illustrative)" style). Keys unchanged, so no schema
   ripple through `_format_profile`/`_TEMPLATES`.

**Most severe finding, not scoped when this CR was filed:** `room_runner.py`'s
`_TEMPLATES[AgentId.SOCIAL_MEDIA_ANALYST]` — the **scripted, non-LLM fallback**
rendered verbatim to real users whenever `gateway.has_real_provider()` is False or an
agent's LLM call times out — literally said *"Retail sentiment on {ticker}...
(Stocktwits {sentiment_score}σ over the week). Reddit /r/investing mentions
{mention_trend}..."*, naming real platforms by name in **user-facing** text, with no
live-vs-scripted disclosure anywhere in `api/room.py` or the mobile client. This was
more urgent than the LLM-prompt framing this CR originally scoped and is now fixed
in the same template rewrite.

`room_prompts.py::_format_profile()`'s disclosure header (shared with CR023) now
labels sentiment/mention/influencer fields as "ALWAYS illustrative — no live feed
connected" regardless of any other field's live/synthetic state.

Covered by new/extended tests in `test_room_runner.py` (scripted-fallback platform-
name ban, no-σ check, mention_trend now varies by ticker) and
`test_overlay_generator.py` (`_social_block()` drops named-platform/fake-precision
claims). Backend suite 592 → 640, all green.

Status (superseded below, same session): real Reddit sentiment shipped via Adanos
after the LunarCrush blocker below — see "Implementation via Adanos."

## LunarCrush trial finding (same session, AT:R57)

Saiful signed up for a LunarCrush account and provisioned `LUNARCRUSH_API_KEY`
mid-session. Live-probed the v4 public API directly (`stocks/list/v1`,
`stocks/aapl/v1`, `topic/aapl/v1`, `coins/list/v1` — crypto included as a sanity
check that the key works at all) before writing any client code, same discipline as
CR023's Alpha Vantage verification. **Every endpoint returned the same response:**

```text
HTTP 402: "You must have an active Individual or higher subscription to use this endpoint."
```

The key itself authenticates (this is a 402, not a 401 invalid-key error) — the
account's current plan simply doesn't include API access at all. This sharpens this
doc's prior "exact tier pricing unconfirmed" framing into something concrete: **a
bare LunarCrush signup is not sufficient — API access requires upgrading to their
"Individual" tier or higher**, and the real price of that tier is still unknown
(their pricing page is still the client-rendered JS page CR007 and this doc's
provider-research section already flagged as unfetchable by automated means).

No client code was written against this key — writing a parser against an API that
returns nothing but a paywall error on every probe would be pure guesswork, not the
verified-against-a-real-response discipline CR023's Alpha Vantage client used.
Presented Saiful with three options (upgrade-and-verify / code-blind-now /
drop-and-stay-honesty-only); **he'll check/upgrade the LunarCrush plan** and this
picks back up once the account can actually answer API calls.

## Implementation via Adanos (same session, AT:R57-continued)

Saiful redirected to Adanos (`https://api.adanos.org`) — a Reddit-only stock
sentiment aggregator recommended by third-party research as a usable free tier
(250 calls/month) — and provisioned `ADANOS_API_KEY`. Their own docs page
(`api.adanos.org/docs`) is a client-rendered SPA, same unfetchable-via-automation
issue as LunarCrush's and Finnhub's pricing pages — so the base URL and endpoint
path were confirmed from Adanos's own homepage content (first-party, not a
third-party guess) before a single live credential ever left the Mac, per the
harness's own credential-materialization safeguard (an initial guessed
domain+path combination was correctly blocked). One live call to
`GET /reddit/stocks/v1/stock/AAPL` (`X-API-Key` header) confirmed the real
response shape — a trimmed copy of that exact response is the test fixture in
`test_social_context.py`, not a guessed shape. Response headers confirmed the
250/month budget concretely: `x-ratelimit-limit-monthly: 250`,
`x-account-type: free`.

**New `backend/app/services/social_context.py`** — mirrors `news_context.py`'s
shape: `SocialSentiment` NamedTuple (ticker, buzz_score, sentiment_score, mentions,
bullish_pct, bearish_pct, trend, period_days, top 3 subreddits, up to 3 real post
snippets), `_AdanosSource` (httpx client + 24h TTL cache — the free tier's 250/month
budget means checking more than ~8 distinct tickers/day would exceed quota, so
long caching by ticker is what keeps this viable), `fetch_live_sentiment(ticker)`
(never raises, returns `None` when `adanos_api_key` is unset), and `format_*`
helpers used by both surfaces. Real post text (`sample_snippets`) is Reddit
community content, not ours to display verbatim — it's exposed only via
`build_social_context_block()` for the 1-on-1 LLM-prompt block (which the agent
must synthesize, never echo), and deliberately never stored in the Room profile
dict, since that dict also feeds the scripted (non-LLM) fallback template shown
directly to real users.

**Wiring** — `room_runner.py::_profile_for_ticker()` overlays
`sentiment_tone`/`sentiment_score`/`mention_trend`/`influencer_take`/`pattern`
with real Adanos-derived values when available (aggregate stats only — subreddit
names, mention counts, buzz score — never a raw post snippet, keeping the
scripted-fallback surface safe); sets `profile["social_source"] = "live"`.
`agent_runner.py`'s 1-on-1 path gets a Social-Media-Analyst-gated
`build_social_context_block()` injection, mirroring CR023's News-Analyst gating —
this is where the real post snippets appear, LLM-only, with an explicit
"do NOT quote verbatim or attribute to a user" instruction.
`room_prompts.py::_format_profile()`'s disclosure header gained a third
independent category (social, alongside fundamentals and news) — a profile can
now have any combination of live fundamentals/news/social simultaneously.

**Scripted-fallback template correction** — the `_TEMPLATES[SOCIAL_MEDIA_ANALYST]`
entry from this session's earlier (honesty-only) pass had hardcoded "in this
illustrative scenario... no live social feed connected" directly into the template
text — true at the time, but would have started lying the moment Adanos went live,
since the template renders unconditionally regardless of data source. Reverted to
neutral wording (matching `NEWS_ANALYST`'s existing pattern): the template no longer
asserts real-or-synthetic itself; the field **values** now self-disclose
("elevated intensity (illustrative)" when synthetic, "+0.30 (live Reddit sentiment,
Adanos)" when real).

**Prompt + overlay corrections** — `content/agents/social_media_analyst.md` and
`overlay_generator.py::_social_block()` (both rewritten earlier this session to
say "no live feed connected, full stop") were revised again to be conditionally
accurate: Reddit-only real data where configured, Twitter/X/StockTwits/Google
Trends/Discord still categorically nonexistent, illustrative reasoning as the
documented fallback when Adanos has nothing for a ticker.

**Tests** — new `test_social_context.py` (23 tests, fixture-verified against the
real captured response), new `test_one_on_one_social_injection.py` (4 tests,
mirrors CR023's News-only-gating test), plus extensions to `test_room_runner.py`
(profile overlay, independence from fundamentals/news, scripted-template
neutrality) and fixes to the 4 tests whose assertions encoded the now-outdated
"no real data exists at all" assumption. Backend suite 640 → 673, all green.

Status: `proposed` → **`in_progress`** — real Reddit sentiment now flows into both
Room and 1-on-1 paths; not `done` because Twitter/X, StockTwits, Google Trends, and
Discord remain entirely unconnected (LunarCrush, if ever unblocked, or a
Twitter-specific source would be the path to closing those) — this CR's full
multi-platform scope is still only partially met.
