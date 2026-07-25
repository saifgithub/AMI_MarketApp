"""Tests for the News Analyst's live-news helper (Room + 1-on-1, CR023 AT:R57).

Yahoo is exercised via `set_market_data_provider` with a fake provider (same
pattern as test_sim_history.py). Alpha Vantage is exercised against a mocked
httpx.Client (same pattern as test_market_data.py's YahooQuoteProvider tests)
— no live network calls.
"""

from __future__ import annotations

import time

import httpx
import pytest

from app.core.config import settings
from app.services import news_context
from app.services.market_data import NewsItem, set_market_data_provider
from app.services.news_context import (
    LiveHeadline,
    _AlphaVantageSource,
    _merge_headlines,
    build_news_context_block,
    fetch_live_news,
    format_headline,
    set_alpha_vantage_source,
)


# ── Fakes ────────────────────────────────────────────────────────────────


class _FakeMarketDataProvider:
    name = "fake"

    def __init__(self, items: list[NewsItem] | None):
        self._items = items

    def news(self, ticker: str, limit: int = 5):
        return self._items

    def quote(self, ticker):
        return None

    def get_price(self, ticker):
        return None

    def history(self, ticker, period):
        return None

    def earnings(self, ticker):
        return None


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None):
        self.status_code = status_code
        self._json = json_body or {}

    def json(self) -> dict:
        return self._json


class _FakeClient:
    def __init__(self, response) -> None:
        self._response = response
        self.calls = 0

    def get(self, url: str, params: dict | None = None):
        self.calls += 1
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _av_body(*articles: dict) -> dict:
    return {"items": str(len(articles)), "feed": list(articles)}


def _article(title="Headline", ticker="AAPL", sentiment="Bullish", ts="20260713T104325", source="MarketBeat", url="https://example.com/a"):
    return {
        "title": title,
        "url": url,
        "time_published": ts,
        "source": source,
        "overall_sentiment_label": "Somewhat-Bullish",
        "ticker_sentiment": [
            {"ticker": ticker, "relevance_score": "0.9", "ticker_sentiment_score": "0.3", "ticker_sentiment_label": sentiment},
        ],
    }


# ── _YfinanceSource (via fetch_live_news, no Alpha Vantage key) ──────────


def test_fetch_live_news_returns_none_when_yahoo_has_nothing():
    set_market_data_provider(_FakeMarketDataProvider(None))
    assert fetch_live_news("XYZQ") is None


def test_fetch_live_news_returns_none_when_provider_raises(monkeypatch):
    # Hermetic: with no Alpha Vantage key, Yahoo is the only source, so a
    # raising provider must yield None. Without this the suite falls through
    # to a live AV call on any machine that has a real key in its env (DEF106).
    monkeypatch.setattr(settings, "alpha_vantage_api_key", "")

    class _Boom:
        name = "boom"

        def news(self, ticker, limit=5):
            raise RuntimeError("network is on fire")

    set_market_data_provider(_Boom())
    assert fetch_live_news("AAPL") is None


def test_fetch_live_news_uses_yahoo_when_no_alpha_vantage_key(monkeypatch):
    monkeypatch.setattr(settings, "alpha_vantage_api_key", "")
    items = [NewsItem(title="Yahoo headline", link="https://y", publisher="Yahoo", published_at=int(time.time()))]
    set_market_data_provider(_FakeMarketDataProvider(items))

    # A source that would blow up if ever called — proves AV is skipped
    # entirely when unconfigured, not just that its result is discarded.
    class _MustNotBeCalled:
        def fetch(self, ticker, limit):
            raise AssertionError("Alpha Vantage must not be called without a key")

    set_alpha_vantage_source(_MustNotBeCalled())

    out = fetch_live_news("AAPL")
    assert out is not None
    assert len(out) == 1
    assert out[0].title == "Yahoo headline"
    assert out[0].sentiment is None
    assert out[0].source == "yfinance"


# ── Combining Yahoo + Alpha Vantage ───────────────────────────────────────


def test_fetch_live_news_combines_both_sources_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "alpha_vantage_api_key", "test-key")
    now = int(time.time())
    set_market_data_provider(_FakeMarketDataProvider(
        [NewsItem(title="Yahoo exclusive", link="https://y", publisher="Yahoo", published_at=now - 60)]
    ))

    class _FakeAV:
        def fetch(self, ticker, limit):
            return [LiveHeadline(
                title="AV exclusive", link="https://av", publisher="MarketBeat",
                published_at=now, sentiment="Bullish", source="alpha_vantage",
            )]

    set_alpha_vantage_source(_FakeAV())

    out = fetch_live_news("AAPL", limit=5)
    assert out is not None
    titles = {h.title for h in out}
    assert titles == {"Yahoo exclusive", "AV exclusive"}
    # Sorted by recency — AV's newer item first.
    assert out[0].title == "AV exclusive"


def test_fetch_live_news_dedupes_by_title_preferring_sentiment_source(monkeypatch):
    """Same headline surfaced by both sources — Alpha Vantage's (sentiment-
    tagged) version should win the dedupe, not Yahoo's bare one."""
    monkeypatch.setattr(settings, "alpha_vantage_api_key", "test-key")
    now = int(time.time())
    set_market_data_provider(_FakeMarketDataProvider(
        [NewsItem(title="Same Headline", link="https://y", publisher="Yahoo", published_at=now)]
    ))

    class _FakeAV:
        def fetch(self, ticker, limit):
            return [LiveHeadline(
                title="Same Headline", link="https://av", publisher="MarketBeat",
                published_at=now, sentiment="Bullish", source="alpha_vantage",
            )]

    set_alpha_vantage_source(_FakeAV())

    out = fetch_live_news("AAPL")
    assert out is not None
    assert len(out) == 1
    assert out[0].source == "alpha_vantage"
    assert out[0].sentiment == "Bullish"


def test_fetch_live_news_falls_back_to_alpha_vantage_alone_when_yahoo_empty(monkeypatch):
    monkeypatch.setattr(settings, "alpha_vantage_api_key", "test-key")
    set_market_data_provider(_FakeMarketDataProvider(None))

    class _FakeAV:
        def fetch(self, ticker, limit):
            return [LiveHeadline(
                title="AV only", link="https://av", publisher="MarketBeat",
                published_at=int(time.time()), sentiment="Neutral", source="alpha_vantage",
            )]

    set_alpha_vantage_source(_FakeAV())

    out = fetch_live_news("AAPL")
    assert out is not None
    assert out[0].title == "AV only"


def test_fetch_live_news_alpha_vantage_failure_does_not_break_yahoo(monkeypatch):
    monkeypatch.setattr(settings, "alpha_vantage_api_key", "test-key")
    items = [NewsItem(title="Yahoo survives", link="https://y", publisher="Yahoo", published_at=int(time.time()))]
    set_market_data_provider(_FakeMarketDataProvider(items))

    class _FakeAV:
        def fetch(self, ticker, limit):
            raise RuntimeError("AV is down")

    set_alpha_vantage_source(_FakeAV())

    out = fetch_live_news("AAPL")
    assert out is not None
    assert out[0].title == "Yahoo survives"


def test_fetch_live_news_returns_none_when_both_sources_empty(monkeypatch):
    monkeypatch.setattr(settings, "alpha_vantage_api_key", "test-key")
    set_market_data_provider(_FakeMarketDataProvider(None))

    class _FakeAV:
        def fetch(self, ticker, limit):
            return None

    set_alpha_vantage_source(_FakeAV())
    assert fetch_live_news("XYZQ") is None


# ── _merge_headlines ───────────────────────────────────────────────────────


def test_merge_headlines_sorts_by_recency_and_caps_to_limit():
    now = int(time.time())
    old = LiveHeadline(title="Old", link="", publisher="A", published_at=now - 1000, sentiment=None, source="yfinance")
    new = LiveHeadline(title="New", link="", publisher="A", published_at=now, sentiment=None, source="yfinance")
    mid = LiveHeadline(title="Mid", link="", publisher="A", published_at=now - 500, sentiment=None, source="yfinance")
    merged = _merge_headlines([old, new, mid], limit=2)
    assert [h.title for h in merged] == ["New", "Mid"]


# ── _AlphaVantageSource ──────────────────────────────────────────────────


def test_alpha_vantage_returns_none_on_network_error():
    src = _AlphaVantageSource()
    src._client = _FakeClient(httpx.ConnectError("dns fail"))
    assert src.fetch("AAPL", 3) is None


def test_alpha_vantage_returns_none_on_bad_status():
    src = _AlphaVantageSource()
    src._client = _FakeClient(_FakeResponse(429, {}))
    assert src.fetch("AAPL", 3) is None


def test_alpha_vantage_returns_none_on_empty_feed():
    src = _AlphaVantageSource()
    src._client = _FakeClient(_FakeResponse(200, _av_body()))
    assert src.fetch("AAPL", 3) is None


def test_alpha_vantage_parses_ticker_specific_sentiment():
    """An article mentions multiple tickers — must pick AAPL's own
    ticker_sentiment_label, not the article's overall_sentiment_label."""
    src = _AlphaVantageSource()
    article = _article(ticker="AAPL", sentiment="Bullish")
    article["overall_sentiment_label"] = "Somewhat-Bearish"  # deliberately different
    src._client = _FakeClient(_FakeResponse(200, _av_body(article)))

    out = src.fetch("AAPL", 3)
    assert out is not None
    assert out[0].sentiment == "Bullish"
    assert out[0].source == "alpha_vantage"


def test_alpha_vantage_falls_back_to_overall_sentiment_when_ticker_missing():
    src = _AlphaVantageSource()
    article = _article(ticker="MSFT")  # requested ticker (AAPL) not in ticker_sentiment
    article["overall_sentiment_label"] = "Neutral"
    src._client = _FakeClient(_FakeResponse(200, _av_body(article)))

    out = src.fetch("AAPL", 3)
    assert out is not None
    assert out[0].sentiment == "Neutral"


def test_alpha_vantage_skips_articles_with_no_title():
    src = _AlphaVantageSource()
    body = _av_body({"time_published": "20260713T104325"})  # no title
    src._client = _FakeClient(_FakeResponse(200, body))
    assert src.fetch("AAPL", 3) is None


def test_alpha_vantage_caches_within_ttl():
    src = _AlphaVantageSource()
    fake = _FakeClient(_FakeResponse(200, _av_body(_article())))
    src._client = fake
    src.fetch("AAPL", 3)
    src.fetch("AAPL", 3)
    assert fake.calls == 1


def test_alpha_vantage_parse_time_unparseable_becomes_zero():
    src = _AlphaVantageSource()
    article = _article()
    article["time_published"] = "not-a-date"
    src._client = _FakeClient(_FakeResponse(200, _av_body(article)))
    out = src.fetch("AAPL", 3)
    assert out is not None
    assert out[0].published_at == 0


# ── format_headline ──────────────────────────────────────────────────────


def test_format_headline_includes_title_publisher_and_relative_age():
    h = LiveHeadline(title="Big news", link="", publisher="Reuters",
                      published_at=int(time.time()) - 3600, sentiment=None, source="yfinance")
    out = format_headline(h)
    assert "Big news" in out
    assert "Reuters" in out
    assert "ago" in out


def test_format_headline_handles_missing_published_at():
    h = LiveHeadline(title="Old news", link="", publisher="X", published_at=0, sentiment=None, source="yfinance")
    assert "date unknown" in format_headline(h)


def test_format_headline_includes_sentiment_tag_when_present():
    h = LiveHeadline(title="Big news", link="", publisher="Reuters",
                      published_at=int(time.time()), sentiment="Bullish", source="alpha_vantage")
    out = format_headline(h)
    assert "sentiment: Bullish" in out


def test_format_headline_omits_sentiment_when_absent():
    h = LiveHeadline(title="Big news", link="", publisher="Reuters",
                      published_at=int(time.time()), sentiment=None, source="yfinance")
    assert "sentiment" not in format_headline(h)


# ── build_news_context_block ─────────────────────────────────────────────


def test_build_news_context_block_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", False)
    assert build_news_context_block("AAPL") is None


def test_build_news_context_block_returns_none_when_no_headlines(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(news_context, "fetch_live_news", lambda t, limit=3: None)
    assert build_news_context_block("AAPL") is None


def test_build_news_context_block_formats_headlines_without_sentiment(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", True)
    items = [
        LiveHeadline(title="First", link="", publisher="Yahoo", published_at=int(time.time()), sentiment=None, source="yfinance"),
        LiveHeadline(title="Second", link="", publisher="Yahoo", published_at=int(time.time()), sentiment=None, source="yfinance"),
    ]
    monkeypatch.setattr(news_context, "fetch_live_news", lambda t, limit=3: items)

    block = build_news_context_block("AAPL")
    assert block is not None
    assert "LIVE NEWS — AAPL" in block
    assert "First" in block and "Second" in block
    assert "No sentiment score is attached" in block
    assert "σ" not in block


def test_build_news_context_block_notes_sentiment_when_present(monkeypatch):
    monkeypatch.setattr(settings, "use_real_market_data", True)
    items = [
        LiveHeadline(title="Tagged", link="", publisher="MarketBeat", published_at=int(time.time()), sentiment="Bullish", source="alpha_vantage"),
    ]
    monkeypatch.setattr(news_context, "fetch_live_news", lambda t, limit=3: items)

    block = build_news_context_block("AAPL")
    assert block is not None
    assert "sentiment tag from Alpha Vantage" in block
