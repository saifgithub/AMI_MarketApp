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

Both sources: never raise, return nothing on any failure.

  - Room runner pulls this once per Convene and overlays the real top
    headline onto the News Analyst's `catalyst` field.
  - 1-on-1 runner pulls per-message, gated to the News Analyst only (unlike
    fundamentals, headlines are analyst-specific, not shared across agents).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import NamedTuple, Protocol

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.services.market_data import get_market_data_provider

DEFAULT_HEADLINE_LIMIT = 3
_ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
_ALPHA_VANTAGE_CACHE_TTL = 1800.0  # 30 min — billed API, news doesn't stale that fast


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
    source: str  # "yfinance" | "alpha_vantage"


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
            )
            for i in items
        ]


class _AlphaVantageSource:
    """Paid, additive — NEWS_SENTIMENT. TTL-cached (30 min) since this is a
    metered API, unlike Yahoo's already-cached free path.
    """

    def __init__(self, timeout_seconds: float = 4.0) -> None:
        self._client = httpx.Client(timeout=timeout_seconds)
        self._cache: dict[str, tuple[list[LiveHeadline], float]] = {}
        self._lock = RLock()

    def fetch(self, ticker: str, limit: int) -> list[LiveHeadline] | None:
        sym = ticker.upper().strip()
        key = f"{sym}:{limit}"
        now = time.time()
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None and hit[1] > now:
                return hit[0]

        try:
            resp = self._client.get(_ALPHA_VANTAGE_URL, params={
                "function": "NEWS_SENTIMENT",
                "tickers": sym,
                "limit": str(limit),
                "apikey": settings.alpha_vantage_api_key,
            })
        except httpx.HTTPError as exc:
            logger.warn("news_context_alpha_vantage_network_error", ticker=sym, error=str(exc)[:200])
            return None
        if resp.status_code != 200:
            logger.warn("news_context_alpha_vantage_bad_status", ticker=sym, status=resp.status_code)
            return None
        try:
            feed = resp.json().get("feed") or []
        except (ValueError, KeyError, TypeError) as exc:
            logger.warn("news_context_alpha_vantage_parse_error", ticker=sym, error=str(exc)[:200])
            return None

        items = [h for h in (self._to_headline(a, sym) for a in feed[:limit]) if h is not None]
        if not items:
            return None
        with self._lock:
            self._cache[key] = (items, now + _ALPHA_VANTAGE_CACHE_TTL)
        return items

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
        )


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


def fetch_live_news(ticker: str, limit: int = DEFAULT_HEADLINE_LIMIT) -> list[LiveHeadline] | None:
    """Real recent headlines, combining sources when more than one is
    configured. Never raises. Yahoo is always tried; Alpha Vantage is tried
    too when `alpha_vantage_api_key` is set — either can fail independently
    without taking the other down.
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

    merged = _merge_headlines(av_items, yahoo_items, limit=limit)
    return merged or None


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
    [+ sentiment tag when Alpha Vantage supplied one]."""
    title = (item.title or "").replace("\n", " ").strip()
    line = f"\"{title}\" ({item.publisher or 'unknown publisher'}, {_relative_age(item.published_at)})"
    if item.sentiment:
        line += f" — sentiment: {item.sentiment}"
    return line


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
