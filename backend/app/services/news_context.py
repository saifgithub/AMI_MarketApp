"""Live ticker news for the agent pipeline (Room + 1-on-1) — combines sources.

Distinct from the mobile Ticker Detail news feed (market_data.py's
MarketDataProvider.news(), served at GET /v1/sim/news/{ticker}) even though
the Yahoo backend below wraps that same provider stack — this module's job is
producing agent-prompt-ready text for the News Analyst, not an API response.

Two sources, combined when both are available:
  - Yahoo (free, always tried): wraps `get_market_data_provider().news()` —
    the same yfinance-backed, 5-min-cached feed already serving mobile. No
    sentiment score.
  - Alpha Vantage NEWS_SENTIMENT (paid, additive — only tried when
    `alpha_vantage_api_key` is set): per-article, per-ticker
    relevance-weighted sentiment (call shape ported from the read-only
    TradingAgents mount's alpha_vantage_news.py::get_news() — see CR023).
    Presence of the key is the on/off switch, same convention as
    resend_api_key / google_audiences elsewhere in config.py.

When both are configured, headlines are merged (deduped by title, Alpha
Vantage's version preferred on a collision since it carries a sentiment tag)
and sorted by recency. Either source alone still works — Alpha Vantage isn't
a hard dependency, and a Yahoo outage doesn't take Alpha Vantage down with it.

A third source serves Bursa (`.KL`) names only (CR282 lane E2): Malay Mail's
public Money RSS, behind `MY_NEWS_RSS_ENABLED` (default off) — see
`my_news_rss.py`. Items that name the company join the same merge, de-dup and
cap as the two above; up to two market-wide items (Bursa Malaysia / FBM KLCI /
ringgit) are then added beside the cap, publisher-labelled as market context, and
only when company news survived the recency floor. A US ticker never reaches it.

Both sources: never raise, return nothing on any failure.

  - Room runner pulls this once per Convene and overlays the real top
    headline onto the News Analyst's `catalyst` field.
  - 1-on-1 runner pulls per-message, gated to the News Analyst only (unlike
    fundamentals, headlines are analyst-specific, not shared across agents).
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import NamedTuple, Protocol

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.services.prompt_safety import sanitize_for_prompt
from app.services import my_news_rss
from app.services.market_data import NewsItem, get_market_data_provider
from app.trading_math.markets import Market, market_for

# CR147 B.2 / CR179 Leg 3 — 3 → 5. Three headlines was the News Analyst's
# ENTIRE payload, and its assembled sheet measured 1,342 chars against ~4,000
# for any downstream agent: the desk with the thinnest evidence was the one
# asked to separate signal from noise.
#
# Sized against a measurement, not a preference. With summaries now carried
# (see `format_headline`), the block runs 772–1,130 chars at 3 and 1,203–1,836
# at 5, across NVDA/BAC/KTOS/GRAB. Input context is not the constraint — the
# biggest real assembled prompt is ~12% of this model's window.
#
# **Why 5 and not 10**, which is what yfinance returns: relevance decays down
# the feed, and it decays into off-ticker material rather than into noise about
# the ticker. BAC's list already reaches a CNBC state-economy ranking by the
# top of the feed; ten would mostly buy articles the analyst has to discard,
# and every one of those is a chance to reason about the wrong company.
#
# Note this bounds the ALPHA VANTAGE call too (a metered API), not just Yahoo.
# That is currently free of charge because no AV key is configured (DEF063 —
# the feed is parked pending a metered-tier budget decision); if it is ever
# turned on, this constant is one of the two knobs that decides its bill.
DEFAULT_HEADLINE_LIMIT = 5
_ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
# DEF492 — one AV call per ticker serves every caller (Room, 1-on-1, sim news
# route, Sector Watch): the cache is keyed by ticker alone and each caller
# slices its own `limit` off the front. It was keyed `ticker:limit`, so callers
# asking for different limits each paid a separate metered call. TTLs are
# settings (`alpha_vantage_news_cache_ttl_seconds`,
# `alpha_vantage_news_negative_ttl_seconds`), read at call time.
_ALPHA_VANTAGE_FETCH_LIMIT = 10
_ALPHA_VANTAGE_REASON_MAX = 300


class LiveDataState(Enum):
    """CR090 — the 3-state liveness marker for a live-data analyst feed (News,
    Social). Structural, NOT a prompt string (CR038: prompt instructions are
    not controls). `room_runner`/`agent_runner` (CR090-ROOM) branch on this to
    charge the surcharge, disclose the paywall, or fall back honestly.

    Shared type: this enum is the SINGLE marker for both news_context and
    social_context — `social_context` imports it from here so the ROOM lane
    branches on one type, not two.

    Three states, deliberately distinct so a gated feed can never masquerade as
    "no data" (the DEF059 inversion trap):

      LIVE          — the real feed fired with real data. THIS is what the
                      surcharge (`credit_service.live_data_surcharge`) charges
                      for. Only LIVE carries a payload.
      WITHHELD_PAID — live data IS available but the user isn't entitled
                      (short on credits / no entitlement). The loud "this
                      agent's live feed is a paid feature" signal. NEVER a
                      silent synthetic substitution — the payload is withheld
                      structurally, not quietly swapped.
      UNAVAILABLE   — genuinely no live data exists (uncached ticker, provider
                      down, quota exhausted, no key). The existing honest
                      illustrative-synthetic fallback path (CR023/CR024).
      WITHHELD_TENURE — CR098 D3: this analyst is off the user's roster for
                      their plan + account age (the tenure-drip pull-back),
                      a THIRD reason distinct from WITHHELD_PAID. Routing a
                      roster withhold through WITHHELD_PAID would tell the
                      client "buy credits" (won't bring the analyst back —
                      only account age or upgrade does); routing it through
                      UNAVAILABLE claims nobody has the data, which is false
                      and shows no CTA. Never charged, never fetched — the
                      roster gate short-circuits before any probe runs.
    """

    LIVE = "live"
    WITHHELD_PAID = "withheld_paid"
    UNAVAILABLE = "unavailable"
    WITHHELD_TENURE = "withheld_tenure"


def live_data_state(*, available: bool, entitled: bool) -> LiveDataState:
    """Classify a live-data feed into the 3-state marker from two facts the
    caller establishes: did live data actually come back (`available`), and is
    this turn's user entitled to it (`entitled`).

    Pure and total — the only place the state is decided, so the DEF059
    inversion is structurally impossible: available-but-not-entitled can ONLY
    map to WITHHELD_PAID, never to UNAVAILABLE and never to a silent LIVE.
    """
    if not available:
        return LiveDataState.UNAVAILABLE
    return LiveDataState.LIVE if entitled else LiveDataState.WITHHELD_PAID


class LiveHeadline(NamedTuple):
    """One real news headline, prompt-ready. `sentiment` is only ever set by
    Alpha Vantage — Yahoo's plain-headlines feed has no scoring."""

    title: str
    link: str
    publisher: str
    published_at: int  # Unix epoch seconds, 0 if unknown
    sentiment: str | None
    source: str  # "yfinance" | "alpha_vantage" | "malaymail_rss"
    # CR147 B.2 — the provider's own abstract. A headline is frequently not
    # enough to know what happened: BAC's top item reads "New Study Reveals
    # Strongest State Economies", and only the summary says it is a CNBC
    # ranking. Measured present on 40/40 articles. NOT truncated: this file
    # already reasons that "a headline is an ASSERTION, and a truncated
    # assertion can invert its meaning", which applies at least as strongly to
    # a summary, and input context is not a constraint (the biggest real prompt
    # is ~12% of this model's window).
    summary: str = ""


class NewsSource(Protocol):
    def fetch(self, ticker: str, limit: int) -> list[LiveHeadline] | None: ...


class _YfinanceSource:
    """Free, always-on — delegates to the already-configured, already-cached
    market-data provider stack rather than a second parallel yfinance client.
    """

    def fetch(self, ticker: str, limit: int) -> list[LiveHeadline] | None:
        try:
            items = get_market_data_provider().news(ticker.upper().strip(), limit=limit)
        except Exception as exc:
            logger.warn("news_context_yfinance_error", ticker=ticker, error=str(exc)[:200])
            return None
        if not items:
            return None
        return [
            LiveHeadline(
                title=i.title, link=i.link, publisher=i.publisher,
                published_at=i.published_at, sentiment=None, source="yfinance",
                summary=getattr(i, "summary", "") or "",
            )
            for i in items
        ]


class _AlphaVantageSource:
    """NEWS_SENTIMENT. TTL-cached per ticker, shared by every caller.

    DEF492 — Alpha Vantage answers HTTP 200 with a JSON body that has no `feed`
    when it refuses a call: `{"Information": "..."}` for a daily-quota hit, a
    premium-only endpoint or an invalid key; `{"Note": "..."}` on the older
    per-minute throttle. That text is the only thing that says WHY, so it is
    kept (never the key) and surfaced in the warn log and via `last_failure`.
    A refusal is cached for `alpha_vantage_news_negative_ttl_seconds` so a dark
    feed is not re-asked on every Room / page view.
    """

    def __init__(self, timeout_seconds: float = 4.0) -> None:
        self._client = httpx.Client(timeout=timeout_seconds)
        self._cache: dict[str, tuple[list[LiveHeadline], float]] = {}
        self._negative: dict[str, tuple[str, float]] = {}
        self._last_failure: dict[str, str] = {}
        self._lock = RLock()

    def last_failure(self, ticker: str) -> str | None:
        """Why the most recent fetch for `ticker` produced nothing (None after a success)."""
        with self._lock:
            return self._last_failure.get(ticker.upper().strip())

    def _refused(self, sym: str, reason: str, *, cache: bool) -> None:
        reason = reason[:_ALPHA_VANTAGE_REASON_MAX]
        if settings.alpha_vantage_api_key:
            reason = reason.replace(settings.alpha_vantage_api_key, "<redacted>")
        with self._lock:
            self._last_failure[sym] = reason
            if cache:
                self._negative[sym] = (
                    reason, time.time() + settings.alpha_vantage_news_negative_ttl_seconds,
                )

    def fetch(self, ticker: str, limit: int) -> list[LiveHeadline] | None:
        sym = ticker.upper().strip()
        now = time.time()
        with self._lock:
            hit = self._cache.get(sym)
            if hit is not None and hit[1] > now:
                return hit[0][:limit]
            neg = self._negative.get(sym)
            if neg is not None and neg[1] > now:
                return None

        try:
            resp = self._client.get(_ALPHA_VANTAGE_URL, params={
                "function": "NEWS_SENTIMENT",
                "tickers": sym,
                "limit": str(max(limit, _ALPHA_VANTAGE_FETCH_LIMIT)),
                "apikey": settings.alpha_vantage_api_key,
            })
        except httpx.HTTPError as exc:
            self._refused(sym, f"network_error: {str(exc)[:150]}", cache=False)
            logger.warn("news_context_alpha_vantage_network_error", ticker=sym, error=str(exc)[:200])
            return None
        if resp.status_code != 200:
            self._refused(sym, f"http_{resp.status_code}", cache=False)
            logger.warn("news_context_alpha_vantage_bad_status", ticker=sym, status=resp.status_code)
            return None
        try:
            body = resp.json()
            feed = body.get("feed") or []
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            self._refused(sym, f"unparseable_body: {str(exc)[:150]}", cache=False)
            logger.warn("news_context_alpha_vantage_parse_error", ticker=sym, error=str(exc)[:200])
            return None

        items = [h for h in (self._to_headline(a, sym) for a in feed) if h is not None]
        if not items:
            self._refused(sym, _alpha_vantage_refusal_text(body), cache=True)
            logger.warn(
                "news_context_alpha_vantage_no_feed",
                ticker=sym,
                reason=self.last_failure(sym),
                negative_ttl_s=settings.alpha_vantage_news_negative_ttl_seconds,
            )
            return None
        with self._lock:
            self._cache[sym] = (items, now + settings.alpha_vantage_news_cache_ttl_seconds)
            self._negative.pop(sym, None)
            self._last_failure.pop(sym, None)
        return items[:limit]

    @staticmethod
    def _to_headline(article: dict, ticker: str) -> LiveHeadline | None:
        title = article.get("title")
        if not title:
            return None
        sentiment = article.get("overall_sentiment_label")
        for ts in article.get("ticker_sentiment") or []:
            if ts.get("ticker") == ticker:
                sentiment = ts.get("ticker_sentiment_label", sentiment)
                break
        return LiveHeadline(
            title=title,
            link=article.get("url", ""),
            publisher=article.get("source", "unknown"),
            published_at=_parse_alpha_vantage_time(article.get("time_published")),
            sentiment=sentiment,
            source="alpha_vantage",
            summary=str(article.get("summary", "") or "").strip(),
        )


def _alpha_vantage_refusal_text(body: object) -> str:
    """The provider's own words for an HTTP-200 body that carried no articles.

    `Information` / `Note` / `Error Message` are Alpha Vantage's quota, premium
    and bad-key channels. A body with none of them and an empty feed is a
    genuine "no articles for this ticker", named as such rather than guessed at.
    """
    if isinstance(body, dict):
        for field in ("Information", "Note", "Error Message"):
            text = body.get(field)
            if text:
                return f"{field}: {str(text)}"
        return f"empty_feed (no Information/Note; body keys: {sorted(body.keys())[:8]})"
    return f"non_object_body ({type(body).__name__})"


def alpha_vantage_failure_reason(ticker: str) -> str | None:
    """Why Alpha Vantage last gave nothing for `ticker`, for callers' own loud logs."""
    reason = getattr(get_alpha_vantage_source(), "last_failure", None)
    return reason(ticker) if callable(reason) else None


def _parse_alpha_vantage_time(raw: str | None) -> int:
    """Alpha Vantage timestamps are "YYYYMMDDTHHMMSS" UTC. 0 (renders as
    "date unknown") on any parse failure — never raises."""
    if not raw:
        return 0
    try:
        return int(datetime.strptime(raw, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return 0


_alpha_vantage_source: NewsSource | None = None


def get_alpha_vantage_source() -> NewsSource:
    """Singleton (holds an httpx.Client + TTL cache worth reusing). Tests can
    call `set_alpha_vantage_source()` to inject a fake."""
    global _alpha_vantage_source
    if _alpha_vantage_source is None:
        _alpha_vantage_source = _AlphaVantageSource()
    return _alpha_vantage_source


def set_alpha_vantage_source(source: NewsSource | None) -> None:
    global _alpha_vantage_source
    _alpha_vantage_source = source


# CR147 Tier B.1 — the recency floor. NOT a chosen number: CR147's own
# acceptance criterion is *"re-run the age parse over a fresh epoch: >7d must be
# 0, or the run must be UNAVAILABLE"*, so 7 days is the threshold the CR was
# accepted against.
#
# What it fixes is a label, not a shortage. Probed live across 8 tickers,
# yfinance returned 10 articles for 7 of them; SNOA got 3, and its NEWEST was
# **354 days old** — rendered under a header that says the catalyst is real "as
# of this call". More headlines was never the fix; refusing to call a year-old
# article recent is.
_NEWS_RECENCY_FLOOR_DAYS = 7


def _within_recency_floor(item: LiveHeadline, *, now: float) -> bool:
    """An item counts as recent only when its age is KNOWN and inside the floor.

    `published_at == 0` means the source gave no date (`_relative_age` renders
    it "date unknown"). An item whose age cannot be established cannot be
    certified recent, so it is dropped rather than passed through — the
    alternative is exactly the thing the floor exists to stop, a headline of
    unknown vintage under a live-as-of-this-call header (CR040).
    """
    if not item.published_at:
        return False
    return (now - item.published_at) <= _NEWS_RECENCY_FLOOR_DAYS * 86400


def fetch_alpha_vantage_news_items(ticker: str, limit: int) -> list[NewsItem] | None:
    """DEF461 — Alpha Vantage headlines shaped as the mobile `NewsItem`, for the
    ticker-detail feed (`GET /v1/sim/news`) and Sector Watch.

    Those two surfaces read only the Yahoo-backed provider stack, so when Yahoo
    returned nothing on Alpha they were dark even though the Room's
    NEWS_SENTIMENT calls (this same source) were returning 200. No recency
    floor here — that floor is an agent-prompt honesty rule; a ticker-detail
    list shows what the source has, dated. None when no key is configured, on
    any failure, or when the source has nothing. Never raises.
    """
    if not settings.alpha_vantage_api_key:
        return None
    try:
        headlines = get_alpha_vantage_source().fetch(ticker, limit) or []
    except Exception as exc:
        logger.warn("sim_news_alpha_vantage_error", ticker=ticker, error=str(exc)[:200])
        return None
    items = [
        NewsItem(
            title=h.title, link=h.link, publisher=h.publisher,
            published_at=h.published_at, summary=h.summary,
        )
        for h in headlines
    ]
    return items or None


def fetch_live_news(ticker: str, limit: int = DEFAULT_HEADLINE_LIMIT) -> list[LiveHeadline] | None:
    """Real recent headlines, combining sources when more than one is
    configured. Never raises. Yahoo is always tried; Alpha Vantage is tried
    too when `alpha_vantage_api_key` is set — either can fail independently
    without taking the other down.

    Items older than `_NEWS_RECENCY_FLOOR_DAYS` (or of unknown date) are dropped
    here, at the one choke point BOTH surfaces share — the Room's
    `resolve_news_feed` and the 1-on-1 `build_news_context_block`. Filtering in
    the resolver instead would have left the 1-on-1 block rendering year-old
    headlines under the same live header.

    Returning None when nothing survives is what makes the disclosure honest for
    free: `resolve_news_feed` classifies an empty feed as UNAVAILABLE, the Room
    renders its existing synthetic-catalyst disclosure, and `n_available` in
    `_resolve_and_charge_feeds` stops counting news — so the 2-credit live-data
    surcharge is no longer charged for a feed we just refused to trust.
    """
    try:
        yahoo_items = _YfinanceSource().fetch(ticker, limit) or []
    except Exception as exc:
        logger.warn("news_context_fetch_error", source="yfinance", ticker=ticker, error=str(exc)[:200])
        yahoo_items = []

    av_items: list[LiveHeadline] = []
    if settings.alpha_vantage_api_key:
        try:
            av_items = get_alpha_vantage_source().fetch(ticker, limit) or []
        except Exception as exc:
            logger.warn("news_context_fetch_error", source="alpha_vantage", ticker=ticker, error=str(exc)[:200])
            av_items = []

    # CR282 lane E2 — a Bursa name also reads Malay Mail's Money feed. Company
    # items join the one merge below (same cap, same de-dup, same recency sort);
    # market-wide items are added after it, beside the cap, as market context.
    my_company: list[LiveHeadline] = []
    my_market: list[LiveHeadline] = []
    if market_for(ticker) is Market.MY and settings.my_news_rss_enabled:
        try:
            found = my_news_rss.items_for(ticker)
        except Exception as exc:
            logger.warn("news_context_fetch_error", source="malaymail_rss", ticker=ticker, error=str(exc)[:200])
            found = None
        if found is not None:
            my_company = [_my_headline(i, my_news_rss.ATTRIBUTION) for i in found.company]
            my_market = [_my_headline(i, my_news_rss.MARKET_ATTRIBUTION) for i in found.market]

    merged = _merge_headlines(av_items, yahoo_items, my_company, limit=limit)
    now = datetime.now(timezone.utc).timestamp()
    recent = [item for item in merged if _within_recency_floor(item, now=now)]
    if len(recent) < len(merged):
        # Loud, not silent (CR040): if this fires on every ticker the feed is
        # not "working with a filter", it is dead, and the count is the only
        # thing that says so before the disclosure quietly flips to synthetic.
        logger.info(
            "news_context_recency_floor_dropped",
            ticker=ticker,
            dropped=len(merged) - len(recent),
            kept=len(recent),
            floor_days=_NEWS_RECENCY_FLOOR_DAYS,
        )
    if recent and my_market:
        # Market context rides only with company news: on its own it is not news
        # about this company, so it must not flip the feed LIVE (and be charged).
        seen = {h.title.strip().lower() for h in recent}
        recent += [
            h for h in my_market
            if h.title.strip().lower() not in seen and _within_recency_floor(h, now=now)
        ]
    return recent or None


def _my_headline(item: my_news_rss.FeedItem, publisher: str) -> LiveHeadline:
    return LiveHeadline(
        title=item.title, link=item.link, publisher=publisher,
        published_at=item.published_at, sentiment=None, source=my_news_rss.SOURCE_LABEL,
    )


class NewsFeed(NamedTuple):
    """CR090 — the News Analyst's live feed for one Room/1-on-1 turn, tagged
    with the 3-state liveness marker. `headlines` is populated ONLY when
    `state is LiveDataState.LIVE`; for WITHHELD_PAID and UNAVAILABLE it is
    empty — the paid payload is never handed to a non-entitled turn, and the
    caller (CR090-ROOM) renders the loud paywall marker or the honest synthetic
    fallback off `state` instead."""

    state: LiveDataState
    headlines: tuple[LiveHeadline, ...]


def resolve_news_feed(
    ticker: str,
    *,
    entitled: bool,
    limit: int = DEFAULT_HEADLINE_LIMIT,
) -> NewsFeed:
    """Resolve the News Analyst's live feed + its 3-state marker for a turn.

    Additive to the existing binary path — `fetch_live_news` (and every current
    caller of it) is untouched. This is the entitlement-aware entry point the
    ROOM lane consumes: it probes the (cache-first) live feed to learn whether
    live data is *available*, classifies with `live_data_state`, and returns the
    payload ONLY for a LIVE (available + entitled) turn. A WITHHELD_PAID turn
    gets the marker with an empty payload — the surcharge charges nothing and
    the room must disclose the paywall, never silently render synthetic (DEF059).

    Note for CR090-ROOM: probing availability for a non-entitled user still hits
    the (cached) feed. If protecting the Alpha Vantage / Adanos quota against
    non-entitled probes matters, gate this call to entitled turns and treat the
    non-entitled case as WITHHELD_PAID directly — the classifier is exposed
    (`live_data_state`) so you can compose that flow without a live fetch.
    """
    items = tuple(fetch_live_news(ticker, limit) or ())
    state = live_data_state(available=bool(items), entitled=entitled)
    return NewsFeed(
        state=state,
        headlines=items if state is LiveDataState.LIVE else (),
    )


def _merge_headlines(*groups: list[LiveHeadline], limit: int) -> list[LiveHeadline]:
    """Dedupe by normalized title (first-seen wins — pass the
    sentiment-carrying source first so it wins any collision), then sort by
    recency and cap to `limit` so combining sources doesn't blow out the
    prompt just because two feeds are configured."""
    seen: set[str] = set()
    merged: list[LiveHeadline] = []
    for group in groups:
        for item in group:
            key = item.title.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    merged.sort(key=lambda h: h.published_at, reverse=True)
    return merged[:limit]


def format_headline(item: LiveHeadline) -> str:
    """One headline for prompt injection: "title" (publisher, relative age)
    [+ sentiment tag when Alpha Vantage supplied one] [+ the provider's summary].

    CR147 B.2 / CR179 Leg 3 — the summary rides here, in the ONE renderer both
    surfaces share (`room_runner._build_profile`, `room_prompts`' extra
    headlines, and the 1-on-1 `build_news_context_block` all call this), so the
    Room and the 1-on-1 block cannot state a different amount about the same
    article.

    **Why a headline alone was not enough.** Measured across NVDA/GRAB/KTOS/BAC,
    all 40 articles carry a summary, and the headline is frequently not a
    statement of what happened: BAC's top item reads *"New Study Reveals
    Strongest State Economies, Only 1 State Was Better Than Texas"*, and only
    the summary reveals it is a CNBC ranking rather than anything about the
    bank. An agent asked to separate signal from noise on titles like that is
    being asked to guess.

    NOT truncated. This module already reasons that *"a headline is an
    ASSERTION, and a truncated assertion can invert its meaning"*; a summary is
    the same object at greater length. Input context is not the constraint —
    measured, the biggest real assembled prompt is ~12% of this model's window,
    and the observed summary maximum is 500 chars.
    """
    # DEF370 (M10) — was `.replace("\n", " ")`, which handled the newline and
    # not the box-drawing glyphs our own section headers are made of. One rule
    # for both feeds now; a headline is as attacker-authorable as a Reddit post.
    title = sanitize_for_prompt(item.title)
    # RETRO-SECURITY MINOR-2 (round 2) — `item.publisher` sat here unsanitised
    # beside the sanitised title and summary. It is aggregator-supplied rather
    # than headline-authored, so less attacker-controlled in practice, but it
    # is still third-party text from the same feed item and the auditor named
    # it explicitly: the same rule now covers all three fields this renderer
    # interpolates.
    publisher = sanitize_for_prompt(item.publisher) or "unknown publisher"
    line = f"\"{title}\" ({publisher}, {_relative_age(item.published_at)})"
    if item.sentiment:
        line += f" — sentiment: {item.sentiment}"
    summary = sanitize_for_prompt(getattr(item, "summary", ""))
    if summary:
        line += f" — {summary}"
    return line


# Corporate-form and filler words dropped before matching a company name against
# a headline. "Corporation" appears in thousands of unrelated articles; the
# distinctive token is what identifies the issuer.
_NAME_STOPWORDS: frozenset[str] = frozenset({
    "inc", "inc.", "corp", "corp.", "corporation", "co", "co.", "company",
    "ltd", "ltd.", "limited", "plc", "holdings", "holding", "group", "the",
    "technologies", "technology", "systems", "international", "&", "and",
    "class", "common", "stock", "n.v.", "s.a.", "ag", "se",
})

# Leading words that are ordinary nouns before they are company names. A first
# token from this set identifies an INDUSTRY, not an issuer, and matching on it
# manufactures the false attribution this module exists to prevent — measured:
# "Bank" (Bank of America) matched an oil-market article about central banks,
# and an earlier all-tokens pass matched "Defense" (Kratos Defense & Security)
# to an article about Ondas. For these the FULL name phrase must appear, or the
# ticker symbol must.
_GENERIC_LEAD_WORDS: frozenset[str] = frozenset({
    "bank", "american", "america", "national", "general", "united", "global",
    "first", "advanced", "pacific", "standard", "central", "capital", "federal",
    "western", "eastern", "northern", "southern", "atlantic", "continental",
    "premier", "superior", "allied", "consolidated", "universal",
})


def _issuer_tokens(ticker: str, long_name: str | None) -> set[str]:
    """The strings that identify this issuer in a headline: its symbol, and the
    FIRST distinctive word of its name.

    **Only the first**, and that is the whole design. A first pass took every
    non-stopword token and produced two false positives immediately, on live
    data: `Kratos Defense & Security Solutions` matched *"Ondas Wins Israeli
    Defense Tender"* on the word **Defense** — an article about a different
    company in the same industry. An industry word is not an issuer, and a
    defence company's headlines are full of "defense".

    The first distinctive token is how a company is actually referred to in
    prose — NVIDIA, Grab, Kratos, Micron, Tesla — so it is both the tightest
    and the most natural match.
    """
    tokens = {ticker.upper().strip()}
    words = [w.strip(",.:;()[]\'\"") for w in (long_name or "").split()]
    kept = [w for w in words if w and w.lower() not in _NAME_STOPWORDS]
    if kept:
        lead = kept[0].lower()
        if len(lead) > 2 and lead not in _GENERIC_LEAD_WORDS:
            tokens.add(kept[0].upper())
        elif len(kept) > 1:
            # Generic lead: only the full phrase identifies the issuer.
            tokens.add(" ".join(kept).upper())
    return {t for t in tokens if t}


def headline_is_on_ticker(
    item: LiveHeadline, ticker: str, long_name: str | None = None
) -> bool:
    """Does this article actually mention the company under discussion?

    Matched against the title AND the summary, because the summary is often
    where the issuer is named — the same reason CR147 B.2 carries it.

    **Word-boundary matched, not substring.** A plain `in` test made `BAC`
    match the word **back**, which put an oil-market article under Bank of
    America's catalyst line on live data. A three-letter ticker is a substring
    of ordinary English often enough that substring matching does not merely
    add noise — it manufactures the exact false attribution this function
    exists to prevent.
    """
    if item.source == my_news_rss.SOURCE_LABEL and item.publisher == my_news_rss.ATTRIBUTION:
        # Matched against this company's own names by `my_news_rss.match_items`
        # (whole-word, suffix-stripped); the press often uses a name the
        # registered long name does not lead with (Maybank / Malayan Banking).
        return True
    haystack = f"{item.title or ''} {getattr(item, 'summary', '') or ''}".upper()
    return any(
        re.search(rf"\b{re.escape(tok)}\b", haystack)
        for tok in _issuer_tokens(ticker, long_name)
    )


def pick_catalyst(
    headlines: list[LiveHeadline], ticker: str, long_name: str | None = None
) -> tuple[LiveHeadline, bool]:
    """DEF291 — the headline that becomes `profile["catalyst"]` for all twelve
    agents, and whether it is actually about this company.

    **The feed has no relevance ranking and `_merge_headlines` sorts by recency
    alone.** CR147 measured the consequence: 26 of 54 headlines (48%) are
    on-ticker, and the TOP one — the one that becomes the catalyst — is
    **off-ticker in 9 of 18 convenes (50%)**. AVGO's Room led with *"The
    Toughest Questions AMD Faced On Its Latest Call"*, presented to twelve
    agents under the label *"Recent catalyst/headline"*.

    That label is the defect. An off-ticker article is not noise the agent can
    route around — it is an ATTRIBUTION, asserting that this is the catalyst for
    the name under discussion, which is a fabricated fact at the data layer
    rather than a gap in one.

    Returns the most recent ON-TICKER headline when one exists, else the most
    recent overall with `False` — the caller labels it rather than suppressing
    it. Suppression would be worse: a real, recent, sector-relevant article is
    still worth reading, and dropping the whole feed for an imperfect match
    would trade a labelling bug for a data one.
    """
    for item in headlines:
        if headline_is_on_ticker(item, ticker, long_name):
            return item, True
    return headlines[0], False


def _relative_age(published_at: int) -> str:
    if not published_at:
        return "date unknown"
    delta_s = max(0.0, datetime.now(timezone.utc).timestamp() - published_at)
    if delta_s < 3600:
        return f"{max(1, int(delta_s // 60))}m ago"
    if delta_s < 86400:
        return f"{int(delta_s // 3600)}h ago"
    return f"{int(delta_s // 86400)}d ago"


def build_news_context_block(ticker: str) -> str | None:
    """System-prompt-ready block of real headlines — 1-on-1 path, News
    Analyst only. Mirrors fundamentals.build_live_data_block's contract.
    """
    if not settings.use_real_market_data:
        return None
    items = fetch_live_news(ticker)
    if not items:
        return None
    sym = ticker.upper()
    has_sentiment = any(i.sentiment for i in items)
    lines = [f"─── LIVE NEWS — {sym} ───"]
    lines += [f"- {format_headline(i)}" for i in items]
    if has_sentiment:
        lines.append(
            f"(Real headlines for {sym}, sourced live. Some carry a sentiment "
            f"tag from Alpha Vantage — treat it as one input, not a verdict. "
            f"Headlines without a tag still need your own signal-vs-noise "
            f"read. Do NOT invent a macro-calendar date; if it's not above, "
            f"say you don't have it.)"
        )
    else:
        lines.append(
            f"(Real headlines for {sym}, sourced live. No sentiment score is "
            f"attached — synthesizing signal vs noise is your job. Do NOT "
            f"invent a numeric sentiment score or a macro-calendar date; if "
            f"it's not above, say you don't have it.)"
        )
    return "\n".join(lines)
