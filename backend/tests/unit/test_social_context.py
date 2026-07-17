"""Tests for the Social Media Analyst's live-sentiment helper (Room + 1-on-1,
CR024 AT:R57-continued).

The success-path fixture below is a trimmed copy of a REAL response captured
live from Adanos's `/reddit/stocks/v1/stock/AAPL` endpoint during
verification — not a guessed shape. httpx is mocked for all other cases
(same pattern as test_market_data.py / test_news_context.py) — no live
network calls in tests, and no more calls against the real (250/month) quota
than the one used to capture this fixture.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.config import settings
from app.services import social_context
from app.services.social_context import (
    SocialSentiment,
    _AdanosSource,
    build_social_context_block,
    fetch_live_sentiment,
    format_community_read,
    format_mention_trend,
    format_pattern,
    format_sentiment_score,
    format_sentiment_tone,
    set_adanos_source,
)


# ── Fakes ────────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None,
                 headers: dict | None = None):
        self.status_code = status_code
        self._json = json_body
        # Adanos returns the monthly/burst budget on every response; CR041 logs
        # it, so the fake carries a realistic set by default.
        self.headers = headers if headers is not None else {
            "x-ratelimit-limit-monthly": "250",
            "x-ratelimit-remaining-monthly": "246",
            "x-ratelimit-used-monthly": "4",
            "x-ratelimit-remaining-burst": "99",
        }

    def json(self) -> dict:
        if self._json is None:
            raise ValueError("no body")
        return self._json


class _FakeClient:
    def __init__(self, response) -> None:
        self._response = response
        self.calls = 0

    def get(self, url: str, headers: dict | None = None):
        self.calls += 1
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


# Trimmed copy of a REAL response captured live from
# https://api.adanos.org/reddit/stocks/v1/stock/AAPL during AT:R57
# verification (2026-07-13).
REAL_AAPL_RESPONSE = {
    "ticker": "AAPL",
    "company_name": "Apple Inc",
    "found": True,
    "buzz_score": 80.11,
    "mentions": 1993,
    "sentiment_score": 0.002,
    "positive_count": 435,
    "negative_count": 407,
    "neutral_count": 1151,
    "total_upvotes": 38369,
    "unique_posts": 410,
    "subreddit_count": 41,
    "trend": "falling",
    "bullish_pct": 22,
    "bearish_pct": 20,
    "period_days": 7,
    "top_subreddits": [
        {"subreddit": "wallstreetbets", "mentions": 904, "sentiment_score": -0.053, "buzz_score": 73.3, "count": 904},
        {"subreddit": "stocks", "mentions": 255, "sentiment_score": 0.014, "buzz_score": 64.5, "count": 255},
        {"subreddit": "mauerstrassenwetten", "mentions": 175, "sentiment_score": 0.0, "buzz_score": 34.9, "count": 175},
        {"subreddit": "stockmarket", "mentions": 163, "sentiment_score": 0.051, "buzz_score": 62.0, "count": 163},
        {"subreddit": "ValueInvesting", "mentions": 121, "sentiment_score": 0.103, "buzz_score": 53.2, "count": 121},
    ],
    "top_mentions": [
        {
            "text_snippet": "Apple sues OpenAI alleging trade secret theft, says scheme was 'at every level'",
            "sentiment_score": -0.298, "sentiment_label": "negative", "upvotes": 16862,
            "subreddit": "wallstreetbets", "created_utc": "2026-07-10T20:47:44",
        },
        {
            "text_snippet": "NVDA made ATH a month ago, AAPL hitting ATHs every week.",
            "sentiment_score": 0.17, "sentiment_label": "positive", "upvotes": 3072,
            "subreddit": "wallstreetbets", "created_utc": "2026-07-09T11:20:20",
        },
    ],
}


# ── _AdanosSource.fetch ────────────────────────────────────────────────────


def test_adanos_returns_none_on_network_error(monkeypatch):
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    src = _AdanosSource()
    src._client = _FakeClient(httpx.ConnectError("dns fail"))
    assert src.fetch("AAPL") is None


def test_adanos_returns_none_on_bad_status(monkeypatch):
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    src = _AdanosSource()
    src._client = _FakeClient(_FakeResponse(402, {"error": "subscription required"}))
    assert src.fetch("AAPL") is None


def test_adanos_returns_none_on_malformed_json(monkeypatch):
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    src = _AdanosSource()
    src._client = _FakeClient(_FakeResponse(200, None))
    assert src.fetch("AAPL") is None


def test_adanos_returns_none_when_ticker_not_found(monkeypatch):
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    src = _AdanosSource()
    src._client = _FakeClient(_FakeResponse(200, {"ticker": "XYZQ", "found": False}))
    assert src.fetch("XYZQ") is None


def test_adanos_parses_real_response_shape(monkeypatch):
    """The fixture is a trimmed copy of a real captured response — this is
    the actual shape-verification test, not a guess."""
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    src = _AdanosSource()
    src._client = _FakeClient(_FakeResponse(200, REAL_AAPL_RESPONSE))

    out = src.fetch("AAPL")
    assert out is not None
    assert out.ticker == "AAPL"
    assert out.buzz_score == 80.11
    assert out.mentions == 1993
    assert out.sentiment_score == 0.002
    assert out.bullish_pct == 22
    assert out.bearish_pct == 20
    assert out.trend == "falling"
    assert out.period_days == 7
    assert out.top_subreddits == ("wallstreetbets", "stocks", "mauerstrassenwetten")  # capped at 3
    assert len(out.sample_snippets) == 2
    assert "Apple sues OpenAI" in out.sample_snippets[0]


def test_adanos_handles_missing_optional_fields_gracefully(monkeypatch):
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    src = _AdanosSource()
    src._client = _FakeClient(_FakeResponse(200, {"ticker": "AAPL", "found": True}))

    out = src.fetch("AAPL")
    assert out is not None
    assert out.top_subreddits == ()
    assert out.sample_snippets == ()
    assert out.trend == "flat"


def test_adanos_caches_within_ttl(monkeypatch):
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    src = _AdanosSource()
    fake = _FakeClient(_FakeResponse(200, REAL_AAPL_RESPONSE))
    src._client = fake
    src.fetch("AAPL")
    src.fetch("AAPL")
    assert fake.calls == 1


# ── fetch_live_sentiment ───────────────────────────────────────────────────


def test_fetch_live_sentiment_returns_none_without_key(monkeypatch):
    monkeypatch.setattr(settings, "adanos_api_key", "")
    set_adanos_source(None)  # must not even be constructed
    assert fetch_live_sentiment("AAPL") is None


def test_fetch_live_sentiment_delegates_to_source_when_key_set(monkeypatch):
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")

    class _FakeSource:
        def fetch(self, ticker):
            return SocialSentiment(
                ticker=ticker, buzz_score=80.0, sentiment_score=0.0, mentions=100,
                bullish_pct=30, bearish_pct=20, trend="rising", period_days=7,
                top_subreddits=("stocks",), sample_snippets=(),
            )

    set_adanos_source(_FakeSource())
    out = fetch_live_sentiment("AAPL")
    assert out is not None
    assert out.mentions == 100


def test_fetch_live_sentiment_swallows_exceptions(monkeypatch):
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")

    class _BoomSource:
        def fetch(self, ticker):
            raise RuntimeError("boom")

    set_adanos_source(_BoomSource())
    assert fetch_live_sentiment("AAPL") is None


# ── format_* helpers ───────────────────────────────────────────────────────


_BULLISH = SocialSentiment(
    ticker="AAPL", buzz_score=80.0, sentiment_score=0.42, mentions=2000,
    bullish_pct=40, bearish_pct=10, trend="rising", period_days=7,
    top_subreddits=("wallstreetbets", "stocks"), sample_snippets=("a real post",),
)
_BEARISH = _BULLISH._replace(bullish_pct=10, bearish_pct=40)
_MIXED = _BULLISH._replace(bullish_pct=20, bearish_pct=22)


def test_format_sentiment_tone_bullish():
    assert format_sentiment_tone(_BULLISH) == "bullish"


def test_format_sentiment_tone_bearish():
    assert format_sentiment_tone(_BEARISH) == "bearish"


def test_format_sentiment_tone_mixed_within_threshold():
    assert format_sentiment_tone(_MIXED) == "mixed"


def test_format_sentiment_score_includes_source_attribution():
    out = format_sentiment_score(_BULLISH)
    assert "+0.42" in out
    assert "Adanos" in out


def test_format_mention_trend_includes_count_and_trend():
    out = format_mention_trend(_BULLISH)
    assert "2,000" in out
    assert "rising" in out


def test_format_community_read_lists_subreddits():
    out = format_community_read(_BULLISH)
    assert "r/wallstreetbets" in out
    assert "r/stocks" in out


def test_format_community_read_handles_no_subreddits():
    empty = _BULLISH._replace(top_subreddits=())
    out = format_community_read(empty)
    assert "no dominant community" in out


def test_format_pattern_includes_buzz_and_split():
    out = format_pattern(_BULLISH)
    assert "80" in out
    assert "40%" in out and "10%" in out


# ── build_social_context_block ────────────────────────────────────────────


def test_build_social_context_block_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", False)
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    assert build_social_context_block("AAPL") is None


def test_build_social_context_block_returns_none_without_key(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "adanos_api_key", "")
    assert build_social_context_block("AAPL") is None


def test_build_social_context_block_returns_none_when_fetch_fails(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    monkeypatch.setattr(social_context, "fetch_live_sentiment", lambda t: None)
    assert build_social_context_block("AAPL") is None


def test_build_social_context_block_formats_real_data_with_snippet_caveat(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    monkeypatch.setattr(social_context, "fetch_live_sentiment", lambda t: _BULLISH)

    block = build_social_context_block("AAPL")
    assert block is not None
    assert "LIVE SOCIAL SENTIMENT — AAPL" in block
    assert "Reddit only" in block
    assert "a real post" in block
    assert "do NOT quote verbatim" in block
    assert "No Twitter/X, StockTwits" in block


def test_build_social_context_block_omits_snippet_section_when_none(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    no_snippets = _BULLISH._replace(sample_snippets=())
    monkeypatch.setattr(social_context, "fetch_live_sentiment", lambda t: no_snippets)

    block = build_social_context_block("AAPL")
    assert block is not None
    assert "Sample community reactions" not in block


# ── Durable cache (CR041) ──────────────────────────────────────────────────
#
# The cache used to be a dict on the source instance, so it died with the
# process — and api-alpha is recreated on every promotion. Against a
# 250-calls/month free tier that meant a 150-ticker benchmark re-burned the
# whole budget on each restart. These tests pin the properties that make the
# 30-day reuse plan arithmetically possible.


def _clear_social_cache() -> None:
    from app.db import get_session
    from app.db.models import SocialSentimentCacheRow

    with get_session() as s:
        s.query(SocialSentimentCacheRow).delete()


def test_cache_survives_a_new_source_instance(monkeypatch):
    """The restart scenario: a fresh _AdanosSource (new process) must serve
    from Postgres without spending another call."""
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    _clear_social_cache()

    first = _AdanosSource()
    first._client = _FakeClient(_FakeResponse(200, REAL_AAPL_RESPONSE))
    assert first.fetch("AAPL") is not None
    assert first._client.calls == 1

    # Simulates the container being recreated: brand-new instance, empty L1.
    second = _AdanosSource()
    second._client = _FakeClient(_FakeResponse(200, REAL_AAPL_RESPONSE))
    got = second.fetch("AAPL")
    assert got is not None
    assert got.mentions == REAL_AAPL_RESPONSE["mentions"]
    assert second._client.calls == 0, "restart re-burned quota — CR041 regression"


def test_not_found_is_cached_so_it_costs_one_call_not_one_per_convene(monkeypatch):
    """An uncovered ticker used to cost a live call on every single convene."""
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    _clear_social_cache()

    src = _AdanosSource()
    src._client = _FakeClient(_FakeResponse(200, {"ticker": "XYZQ", "found": False}))
    assert src.fetch("XYZQ") is None
    assert src._client.calls == 1

    fresh = _AdanosSource()
    fresh._client = _FakeClient(_FakeResponse(200, {"ticker": "XYZQ", "found": False}))
    assert fresh.fetch("XYZQ") is None
    assert fresh._client.calls == 0, "negative not cached — quota leak (CR041)"


def test_cache_refetches_once_stale(monkeypatch):
    """Staleness is measured against SOCIAL_CACHE_TTL_DAYS at read time."""
    from datetime import datetime, timedelta, timezone

    from app.db import get_session
    from app.db.models import SocialSentimentCacheRow

    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    monkeypatch.setattr(settings, "social_cache_ttl_days", 30)
    _clear_social_cache()

    src = _AdanosSource()
    src._client = _FakeClient(_FakeResponse(200, REAL_AAPL_RESPONSE))
    src.fetch("AAPL")

    # Age the row past the TTL.
    with get_session() as s:
        row = s.get(SocialSentimentCacheRow, "AAPL")
        row.fetched_at = datetime.now(timezone.utc) - timedelta(days=31)

    fresh = _AdanosSource()
    fresh._client = _FakeClient(_FakeResponse(200, REAL_AAPL_RESPONSE))
    assert fresh.fetch("AAPL") is not None
    assert fresh._client.calls == 1, "stale row was served instead of refetched"


def test_cache_within_ttl_is_not_refetched(monkeypatch):
    """The other half of the TTL contract — a 29-day-old row is still good."""
    from datetime import datetime, timedelta, timezone

    from app.db import get_session
    from app.db.models import SocialSentimentCacheRow

    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    monkeypatch.setattr(settings, "social_cache_ttl_days", 30)
    _clear_social_cache()

    src = _AdanosSource()
    src._client = _FakeClient(_FakeResponse(200, REAL_AAPL_RESPONSE))
    src.fetch("AAPL")
    with get_session() as s:
        s.get(SocialSentimentCacheRow, "AAPL").fetched_at = (
            datetime.now(timezone.utc) - timedelta(days=29)
        )

    fresh = _AdanosSource()
    fresh._client = _FakeClient(_FakeResponse(200, REAL_AAPL_RESPONSE))
    assert fresh.fetch("AAPL") is not None
    assert fresh._client.calls == 0


def test_cached_payload_round_trips_every_field(monkeypatch):
    """Cache fidelity: what comes back from Postgres must equal the live parse,
    or the benchmark silently compares different data across runs."""
    monkeypatch.setattr(settings, "adanos_api_key", "test-key")
    _clear_social_cache()

    live = _AdanosSource()
    live._client = _FakeClient(_FakeResponse(200, REAL_AAPL_RESPONSE))
    direct = live.fetch("AAPL")

    cached = _AdanosSource()
    cached._client = _FakeClient(_FakeResponse(200, REAL_AAPL_RESPONSE))
    from_cache = cached.fetch("AAPL")

    assert from_cache == direct
