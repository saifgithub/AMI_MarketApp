"""Live Reddit stock-sentiment for the agent pipeline (Room + 1-on-1) — CR024.

Adanos (`https://api.adanos.org`) is a Reddit-only stock-sentiment aggregator
— presence of `settings.adanos_api_key` turns this on, same convention as
`alpha_vantage_api_key` in news_context.py. It does NOT cover Twitter/X,
StockTwits, Google Trends, or Discord — those remain unconnected, same as
before this CR. Free tier is 250 calls/month (confirmed via response headers
during AT:R57 live verification), so this module caches aggressively (24h
TTL) — at that budget, checking more than ~8 distinct tickers/day would
exceed the monthly quota, so caching by ticker (not by user/pageview) is
what keeps this viable as usage grows, same reasoning as news_context.py's
Alpha Vantage cache.

Real post text (`top_mentions[].text_snippet`) is Reddit community content,
not ours to display verbatim — it's exposed ONLY via `format_social_context()`
for the 1-on-1 LLM-prompt block (which the agent synthesizes, never echoes
raw), and deliberately NEVER stored in the Room profile dict, since that
dict also feeds the scripted (non-LLM) fallback template rendered directly
to real users. Aggregate stats (buzz score, sentiment, subreddit names,
mention counts) are safe for both surfaces.

Never raises, returns None on any failure.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import NamedTuple

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.services.news_context import LiveDataState, live_data_state

_ADANOS_BASE_URL = "https://api.adanos.org/reddit/stocks/v1/stock"
# L1 in-process TTL. The durable cache is Postgres (CR041) — this only spares
# a DB round-trip inside one process's lifetime, so it stays short.
_L1_TTL = 300.0


class SocialSentiment(NamedTuple):
    """Aggregate Reddit sentiment for one ticker over `period_days`."""

    ticker: str
    buzz_score: float
    sentiment_score: float
    mentions: int
    bullish_pct: int
    bearish_pct: int
    trend: str
    period_days: int
    top_subreddits: tuple[str, ...]
    sample_snippets: tuple[str, ...]


def _cache_read(sym: str) -> tuple[bool, SocialSentiment | None] | None:
    """(hit, sentiment) from the durable cache, or None when absent/stale.
    A cached `found=False` is a hit returning None — that's the point (it stops
    an uncovered ticker costing a live call on every convene)."""
    from sqlalchemy import select

    from app.db import get_session
    from app.db.models import SocialSentimentCacheRow

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.social_cache_ttl_days)
    try:
        with get_session() as s:
            row = s.execute(
                select(SocialSentimentCacheRow).where(
                    SocialSentimentCacheRow.ticker == sym
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            fetched = row.fetched_at
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=timezone.utc)
            if fetched < cutoff:
                return None
            if not row.found:
                return (True, None)
            return (True, _AdanosSource._from_payload(sym, row.payload or {}))
    except Exception as exc:  # noqa: BLE001 — cache must never break a convene
        logger.warn("social_cache_read_failed", ticker=sym, error=str(exc)[:200])
        return None


def _cache_write(sym: str, sentiment: SocialSentiment | None) -> None:
    from app.db import get_session
    from app.db.models import SocialSentimentCacheRow

    try:
        with get_session() as s:
            row = s.get(SocialSentimentCacheRow, sym)
            payload = dict(sentiment._asdict()) if sentiment is not None else None
            if payload is not None:
                payload["top_subreddits"] = list(payload.get("top_subreddits") or ())
                payload["sample_snippets"] = list(payload.get("sample_snippets") or ())
            if row is None:
                s.add(SocialSentimentCacheRow(
                    ticker=sym, found=sentiment is not None, payload=payload,
                    fetched_at=datetime.now(timezone.utc),
                ))
            else:
                row.found = sentiment is not None
                row.payload = payload
                row.fetched_at = datetime.now(timezone.utc)
    except Exception as exc:  # noqa: BLE001
        logger.warn("social_cache_write_failed", ticker=sym, error=str(exc)[:200])


class _AdanosSource:
    def __init__(self, timeout_seconds: float = 4.0) -> None:
        self._client = httpx.Client(timeout=timeout_seconds)
        self._cache: dict[str, tuple[SocialSentiment | None, float]] = {}
        self._lock = RLock()

    def fetch(self, ticker: str) -> SocialSentiment | None:
        sym = ticker.upper().strip()
        now = time.time()
        with self._lock:
            hit = self._cache.get(sym)
            if hit is not None and hit[1] > now:
                return hit[0]

        cached = _cache_read(sym)
        if cached is not None:
            with self._lock:
                self._cache[sym] = (cached[1], now + _L1_TTL)
            return cached[1]

        try:
            resp = self._client.get(
                f"{_ADANOS_BASE_URL}/{sym}",
                headers={"X-API-Key": settings.adanos_api_key},
            )
        except httpx.HTTPError as exc:
            logger.warn("social_context_adanos_network_error", ticker=sym, error=str(exc)[:200])
            return None
        # Budget telemetry (CR041): the free tier is 250/month and the only
        # signal is these headers. Log every live call so exhaustion is visible
        # before the agent silently reverts to inventing sentiment (CR037).
        remaining = resp.headers.get("x-ratelimit-remaining-monthly")
        logger.info(
            "social_context_adanos_call",
            ticker=sym,
            status=resp.status_code,
            monthly_remaining=remaining,
            monthly_used=resp.headers.get("x-ratelimit-used-monthly"),
            burst_remaining=resp.headers.get("x-ratelimit-remaining-burst"),
        )
        try:
            if remaining is not None and int(remaining) <= 10:
                logger.warn(
                    "social_context_adanos_budget_nearly_exhausted",
                    monthly_remaining=remaining,
                    resets=resp.headers.get("x-ratelimit-reset-monthly"),
                    note="Social Analyst reverts to synthetic sentiment at zero (CR037)",
                )
        except ValueError:
            pass
        if resp.status_code != 200:
            logger.warn("social_context_adanos_bad_status", ticker=sym, status=resp.status_code)
            return None
        try:
            body = resp.json()
        except ValueError as exc:
            logger.warn("social_context_adanos_parse_error", ticker=sym, error=str(exc)[:200])
            return None
        if not body.get("found"):
            # Cache the negative: Adanos has no coverage for this ticker, and
            # re-asking every convene burned one call each time (CR041).
            _cache_write(sym, None)
            with self._lock:
                self._cache[sym] = (None, now + _L1_TTL)
            return None

        sentiment = self._to_sentiment(sym, body)
        _cache_write(sym, sentiment)
        with self._lock:
            self._cache[sym] = (sentiment, now + _L1_TTL)
        return sentiment

    @staticmethod
    def _from_payload(ticker: str, payload: dict) -> SocialSentiment:
        return SocialSentiment(
            ticker=ticker,
            buzz_score=float(payload.get("buzz_score") or 0.0),
            sentiment_score=float(payload.get("sentiment_score") or 0.0),
            mentions=int(payload.get("mentions") or 0),
            bullish_pct=int(payload.get("bullish_pct") or 0),
            bearish_pct=int(payload.get("bearish_pct") or 0),
            trend=str(payload.get("trend") or "flat"),
            period_days=int(payload.get("period_days") or 7),
            top_subreddits=tuple(payload.get("top_subreddits") or ()),
            sample_snippets=tuple(payload.get("sample_snippets") or ()),
        )

    @staticmethod
    def _to_sentiment(ticker: str, body: dict) -> SocialSentiment:
        top_subreddits = tuple(
            s["subreddit"] for s in (body.get("top_subreddits") or [])[:3] if s.get("subreddit")
        )
        sample_snippets = tuple(
            m["text_snippet"] for m in (body.get("top_mentions") or [])[:3] if m.get("text_snippet")
        )
        return SocialSentiment(
            ticker=ticker,
            buzz_score=float(body.get("buzz_score") or 0.0),
            sentiment_score=float(body.get("sentiment_score") or 0.0),
            mentions=int(body.get("mentions") or 0),
            bullish_pct=int(body.get("bullish_pct") or 0),
            bearish_pct=int(body.get("bearish_pct") or 0),
            trend=str(body.get("trend") or "flat"),
            period_days=int(body.get("period_days") or 7),
            top_subreddits=top_subreddits,
            sample_snippets=sample_snippets,
        )


_source: _AdanosSource | None = None


def get_adanos_source() -> _AdanosSource:
    """Singleton (holds an httpx.Client + the 24h TTL cache). Tests can call
    `set_adanos_source()` to inject a fake."""
    global _source
    if _source is None:
        _source = _AdanosSource()
    return _source


def set_adanos_source(source: _AdanosSource | None) -> None:
    global _source
    _source = source


def fetch_live_sentiment(ticker: str) -> SocialSentiment | None:
    """Real Reddit sentiment for `ticker` via Adanos. Never raises. Returns
    None if `adanos_api_key` is unset — callers gate on that separately
    (mirrors news_context.py's shape) so this stays a pure fetch."""
    if not settings.adanos_api_key:
        return None
    try:
        return get_adanos_source().fetch(ticker)
    except Exception as exc:
        logger.warn("social_context_fetch_error", ticker=ticker, error=str(exc)[:200])
        return None


class SocialFeed(NamedTuple):
    """CR090 — the Social Media Analyst's live feed for one Room/1-on-1 turn,
    tagged with the shared 3-state `LiveDataState` marker. `sentiment` is set
    ONLY when `state is LiveDataState.LIVE`; for WITHHELD_PAID and UNAVAILABLE
    it is None — the paid Reddit payload is never handed to a non-entitled turn,
    and the caller (CR090-ROOM) branches on `state` to disclose the paywall or
    fall back to the honest synthetic block."""

    state: LiveDataState
    sentiment: SocialSentiment | None


def resolve_social_feed(ticker: str, *, entitled: bool) -> SocialFeed:
    """Resolve the Social Analyst's live feed + its 3-state marker for a turn.

    Additive to the existing binary path — `fetch_live_sentiment` and its
    callers are untouched. Mirrors `news_context.resolve_news_feed`: probes the
    (cache-first, quota-metered) Adanos feed to learn whether live sentiment is
    *available*, classifies with the shared `live_data_state`, and returns the
    payload ONLY for a LIVE (available + entitled) turn. A WITHHELD_PAID turn
    gets the marker with `sentiment=None` — never a silent synthetic swap
    (DEF059), and the surcharge charges nothing for it.

    Same quota note as the news resolver: probing availability for a
    non-entitled user still consults the (24h-cached) feed; if protecting
    Adanos's 250-call/month budget against non-entitled probes matters, the ROOM
    lane can gate this to entitled turns and compose WITHHELD_PAID directly via
    the exposed `live_data_state` classifier.
    """
    s = fetch_live_sentiment(ticker)
    state = live_data_state(available=s is not None, entitled=entitled)
    return SocialFeed(
        state=state,
        sentiment=s if state is LiveDataState.LIVE else None,
    )


def format_sentiment_tone(s: SocialSentiment) -> str:
    if s.bullish_pct > s.bearish_pct + 5:
        return "bullish"
    if s.bearish_pct > s.bullish_pct + 5:
        return "bearish"
    return "mixed"


def format_sentiment_score(s: SocialSentiment) -> str:
    return f"{s.sentiment_score:+.2f} (live Reddit sentiment, Adanos)"


def format_mention_trend(s: SocialSentiment) -> str:
    return f"{s.mentions:,} Reddit mentions over {s.period_days}d, trend: {s.trend}"


def format_community_read(s: SocialSentiment) -> str:
    if not s.top_subreddits:
        return "no dominant community this period"
    return f"most active in r/{', r/'.join(s.top_subreddits)}"


def format_pattern(s: SocialSentiment) -> str:
    return f"buzz score {s.buzz_score:.0f}/100, bullish {s.bullish_pct}% / bearish {s.bearish_pct}%"


def build_social_context_block(ticker: str) -> str | None:
    """System-prompt-ready block of real Reddit sentiment — 1-on-1 path,
    Social Media Analyst only. Includes a couple of real post snippets as
    LLM-only synthesis context — the agent must never quote them verbatim
    or attribute to a specific user (enforced in the block's own text and
    in content/agents/social_media_analyst.md).
    """
    if not settings.use_real_market_data or not settings.adanos_api_key:
        return None
    s = fetch_live_sentiment(ticker)
    if s is None:
        return None
    sym = ticker.upper()
    lines = [
        f"─── LIVE SOCIAL SENTIMENT — {sym} (Reddit only, via Adanos) ───",
        f"{format_mention_trend(s)}. {format_pattern(s)}.",
        f"{format_community_read(s)}.",
    ]
    if s.sample_snippets:
        lines.append("Sample community reactions (context only — do NOT quote verbatim or attribute to a user):")
        lines += [f"- {snippet[:200]}" for snippet in s.sample_snippets]
    lines.append(
        "(Real Reddit-only aggregate for this ticker. No Twitter/X, StockTwits, "
        "Google Trends, or Discord data exists. Synthesize the vibe in your own "
        "words — never echo a snippet verbatim, never imply you read a specific post.)"
    )
    return "\n".join(lines)
